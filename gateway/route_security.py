"""ASGI enforcement of the closed M2.3 gateway route policy."""

from __future__ import annotations

import ipaddress

from starlette.requests import Request
from starlette.responses import JSONResponse

from gateway.request_auth import (
    AuthenticatedGatewayRequest,
    GatewayAuthenticationError,
    GatewayRequestAuthenticator,
)
from gateway.route_policy import (
    RouteClassification,
    RoutePolicyError,
    classify_request,
    is_protected,
)
from neuron.runtime_safety import RuntimePolicy, load_runtime_policy


AUTHENTICATED_REQUEST_STATE = "vams_authenticated_gateway_request"
TRUSTED_INGRESS_HEADER = b"x-vams-ingress-version"
TRUSTED_INGRESS_VALUE = b"envoy-1.39.1-v1"
FORWARDED_FOR_HEADER = b"x-forwarded-for"
_HTTP_METHODS_WITH_JSON_BODY = frozenset({"POST", "PUT", "PATCH"})


class GatewayRouteSecurityMiddleware:
    """Authenticate classified routes before routing or handler execution."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        scope_type = scope.get("type")
        if scope_type == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope_type != "http":
            await self.app(scope, receive, send)
            return

        ingress_error = _validate_trusted_ingress(scope)
        if ingress_error is not None:
            await self._reject(scope, receive, send, 403, ingress_error)
            return

        method = scope.get("method")
        path = scope.get("path")
        try:
            classification = classify_request(method, path)
        except RoutePolicyError:
            await self._reject(scope, receive, send, 500, "route_policy_failure")
            return
        if classification is None or classification is RouteClassification.DISABLED:
            await self._reject(scope, receive, send, 404, "route_not_available")
            return
        if not is_protected(classification):
            await self.app(scope, receive, send)
            return

        framing_error = _validate_protected_headers(scope)
        if framing_error is not None:
            await self._reject(scope, receive, send, 400, framing_error)
            return

        request = Request(scope, receive)
        try:
            raw_body = await request.body()
        except Exception:
            await self._reject(scope, receive, send, 400, "malformed_body")
            return
        body_error = _validate_protected_body(str(method), raw_body, scope)
        if body_error is not None:
            await self._reject(scope, receive, send, 415, body_error)
            return

        app = scope.get("app")
        authenticator = getattr(
            getattr(app, "state", None), "gateway_authenticator", None
        )
        if not isinstance(authenticator, GatewayRequestAuthenticator):
            await self._reject(scope, receive, send, 503, "authenticator_unavailable")
            return
        try:
            authenticated = await authenticator.authenticate(request)
        except GatewayAuthenticationError as exc:
            status = 503 if exc.code in {
                "key_unavailable",
                "replay_unavailable",
                "storage_failure",
            } else 401
            await self._reject(scope, receive, send, status, exc.code)
            return
        except Exception:
            await self._reject(scope, receive, send, 503, "authentication_failure")
            return

        state = scope.setdefault("state", {})
        state[AUTHENTICATED_REQUEST_STATE] = authenticated
        sent = False

        async def replay_receive():
            nonlocal sent
            if sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            sent = True
            return {"type": "http.request", "body": raw_body, "more_body": False}

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _reject(scope, receive, send, status: int, code: str) -> None:
        response = JSONResponse(
            status_code=status,
            content={"detail": f"gateway_request_denied:{code}"},
        )
        await response(scope, receive, send)


def authenticated_gateway_request(scope) -> AuthenticatedGatewayRequest | None:
    state = scope.get("state", {}) if isinstance(scope, dict) else {}
    candidate = state.get(AUTHENTICATED_REQUEST_STATE)
    return candidate if isinstance(candidate, AuthenticatedGatewayRequest) else None


def _header_values(scope, name: bytes) -> list[bytes]:
    headers = scope.get("headers", [])
    return [value for key, value in headers if key.lower() == name]


def _runtime_policy(scope) -> RuntimePolicy:
    app = scope.get("app") if isinstance(scope, dict) else None
    policy = getattr(getattr(app, "state", None), "runtime_policy", None)
    return policy if isinstance(policy, RuntimePolicy) else load_runtime_policy()


def _loopback_peer(scope) -> bool:
    client = scope.get("client")
    if not isinstance(client, (tuple, list)) or not client:
        return False
    try:
        return ipaddress.ip_address(str(client[0])).is_loopback
    except ValueError:
        return False


def _validate_trusted_ingress(scope) -> str | None:
    """Require the reviewed Envoy transport boundary for every live request.

    The peer must be the loopback Envoy connection itself. Uvicorn must run
    with proxy-header processing disabled; otherwise it replaces the peer with
    the client address Envoy writes into X-Forwarded-For, and every remote
    client is refused here.
    """
    if not _runtime_policy(scope).is_live:
        return None
    if not _loopback_peer(scope):
        client = scope.get("client")
        forwarded = _header_values(scope, FORWARDED_FOR_HEADER)
        if (
            isinstance(client, (tuple, list))
            and client
            and forwarded == [str(client[0]).encode("latin-1")]
            and _header_values(scope, TRUSTED_INGRESS_HEADER) == [TRUSTED_INGRESS_VALUE]
        ):
            # Name the misconfiguration instead of a generic peer refusal.
            return "ingress_peer_rewritten_by_proxy_headers"
        return "untrusted_ingress_peer"
    if _header_values(scope, TRUSTED_INGRESS_HEADER) != [TRUSTED_INGRESS_VALUE]:
        return "untrusted_ingress_marker"
    return None


def trusted_ingress_client(scope) -> str | None:
    """Return the client address asserted by the reviewed Envoy ingress.

    Only a loopback peer carrying the exact ingress marker and exactly one
    X-Forwarded-For value qualifies. Envoy removes client-supplied forwarding
    headers and writes that value from the downstream TCP address. Anything
    else returns None, and callers must fall back to the transport peer.
    """
    if not _loopback_peer(scope):
        return None
    if _header_values(scope, TRUSTED_INGRESS_HEADER) != [TRUSTED_INGRESS_VALUE]:
        return None
    forwarded = _header_values(scope, FORWARDED_FOR_HEADER)
    if len(forwarded) != 1:
        return None
    try:
        return str(ipaddress.ip_address(forwarded[0].decode("ascii").strip()))
    except (UnicodeDecodeError, ValueError):
        return None


def _validate_protected_headers(scope) -> str | None:
    if _header_values(scope, b"transfer-encoding"):
        return "unsupported_transfer_encoding"
    if _header_values(scope, b"content-encoding"):
        return "unsupported_content_encoding"
    content_types = _header_values(scope, b"content-type")
    if len(content_types) > 1:
        return "ambiguous_content_type"
    if scope.get("method") in _HTTP_METHODS_WITH_JSON_BODY and not _header_values(
        scope, b"content-length"
    ):
        return "missing_content_length"
    return None


def _validate_protected_body(method: str, body: bytes, scope) -> str | None:
    content_types = _header_values(scope, b"content-type")
    if method in _HTTP_METHODS_WITH_JSON_BODY:
        if content_types != [b"application/json"]:
            return "unsupported_content_type"
    elif body:
        return "body_not_allowed"
    elif content_types:
        return "content_type_not_allowed"
    return None
