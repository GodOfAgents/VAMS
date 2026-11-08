"""Closed HTTP route classification for the root VAMS gateway (M2.3)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from starlette.routing import Mount, WebSocketRoute, compile_path


class RoutePolicyError(RuntimeError):
    """Sanitized route-policy failure safe for startup reporting."""


class RouteClassification(str, Enum):
    PUBLIC = "public"
    AUTHENTICATED_READ = "authenticated_read"
    PRIVILEGED_STATE_CHANGE = "privileged_state_change"
    FRAMEWORK_ONLY = "framework_only"
    DISABLED = "disabled"


@dataclass(frozen=True)
class RouteRule:
    path: str
    method: str
    name: str
    classification: RouteClassification
    justification: str

    def __post_init__(self) -> None:
        if not self.path.startswith("/") or self.method != self.method.upper():
            raise RoutePolicyError("gateway route policy is malformed")
        if not self.name or not self.justification:
            raise RoutePolicyError("gateway route policy is incomplete")


def _rule(
    path: str,
    method: str,
    name: str,
    classification: RouteClassification,
    justification: str,
) -> RouteRule:
    return RouteRule(path, method, name, classification, justification)


_PUBLIC_CATALOG = "read-only non-sensitive catalog with no external or durable effect"
_SENSITIVE_READ = "administrative or operational state requires M2 authentication"
_PRIVILEGED = "state-changing method is protected by default before effects"
_FRAMEWORK = "FastAPI-generated documentation surface; no application side effect"


# This tuple is intentionally explicit. A newly registered route or method is a
# startup/test failure until a reviewer adds exactly one classification here.
ROUTE_RULES: tuple[RouteRule, ...] = (
    _rule("/openapi.json", "GET", "openapi", RouteClassification.FRAMEWORK_ONLY, _FRAMEWORK),
    _rule("/openapi.json", "HEAD", "openapi", RouteClassification.FRAMEWORK_ONLY, _FRAMEWORK),
    _rule("/docs", "GET", "swagger_ui_html", RouteClassification.FRAMEWORK_ONLY, _FRAMEWORK),
    _rule("/docs", "HEAD", "swagger_ui_html", RouteClassification.FRAMEWORK_ONLY, _FRAMEWORK),
    _rule("/docs/oauth2-redirect", "GET", "swagger_ui_redirect", RouteClassification.FRAMEWORK_ONLY, _FRAMEWORK),
    _rule("/docs/oauth2-redirect", "HEAD", "swagger_ui_redirect", RouteClassification.FRAMEWORK_ONLY, _FRAMEWORK),
    _rule("/redoc", "GET", "redoc_html", RouteClassification.FRAMEWORK_ONLY, _FRAMEWORK),
    _rule("/redoc", "HEAD", "redoc_html", RouteClassification.FRAMEWORK_ONLY, _FRAMEWORK),
    _rule("/", "GET", "dashboard", RouteClassification.AUTHENTICATED_READ, _SENSITIVE_READ),
    _rule("/heartbeat", "POST", "receive_heartbeat", RouteClassification.PRIVILEGED_STATE_CHANGE, _PRIVILEGED),
    _rule("/nodes", "GET", "list_nodes", RouteClassification.AUTHENTICATED_READ, _SENSITIVE_READ),
    _rule("/health", "GET", "health_check", RouteClassification.PUBLIC, "minimal liveness and sanitized runtime classification"),
    _rule("/compose", "POST", "compose_resources", RouteClassification.PRIVILEGED_STATE_CHANGE, _PRIVILEGED),
    _rule("/compose/{instance_id}", "DELETE", "deprovision_resources", RouteClassification.PRIVILEGED_STATE_CHANGE, _PRIVILEGED),
    _rule("/compose/instances", "GET", "list_composed_instances", RouteClassification.AUTHENTICATED_READ, _SENSITIVE_READ),
    _rule("/compose/blueprints", "GET", "list_available_blueprints", RouteClassification.PUBLIC, _PUBLIC_CATALOG),
    _rule("/services/blocks", "GET", "list_service_blocks", RouteClassification.PUBLIC, _PUBLIC_CATALOG),
    _rule("/services/macros", "GET", "list_macro_blocks", RouteClassification.PUBLIC, _PUBLIC_CATALOG),
    _rule("/economics/status", "GET", "get_economics_status", RouteClassification.AUTHENTICATED_READ, _SENSITIVE_READ),
    _rule("/economics/epochs", "GET", "list_epochs", RouteClassification.AUTHENTICATED_READ, _SENSITIVE_READ),
    _rule("/economics/epochs/{epoch_id}", "GET", "get_epoch", RouteClassification.AUTHENTICATED_READ, _SENSITIVE_READ),
    _rule("/economics/estimate-apr", "GET", "estimate_apr", RouteClassification.PUBLIC, "pure read-only estimate with no durable or external effect"),
    _rule("/da/status", "GET", "da_status", RouteClassification.AUTHENTICATED_READ, _SENSITIVE_READ),
    _rule("/da/anchors", "GET", "da_anchors", RouteClassification.AUTHENTICATED_READ, _SENSITIVE_READ),
    _rule("/v1/vdso/intents/simulate", "POST", "simulate_intent", RouteClassification.PRIVILEGED_STATE_CHANGE, _PRIVILEGED),
    _rule("/v1/vdso/intents", "POST", "submit_intent", RouteClassification.PRIVILEGED_STATE_CHANGE, _PRIVILEGED),
    _rule("/v1/vdso/intents/{intent_id}", "GET", "get_intent", RouteClassification.AUTHENTICATED_READ, _SENSITIVE_READ),
    _rule("/v1/vdso/objects/{object_id}", "GET", "get_object", RouteClassification.AUTHENTICATED_READ, _SENSITIVE_READ),
    _rule("/v1/vdso/adapters", "GET", "list_adapters", RouteClassification.AUTHENTICATED_READ, _SENSITIVE_READ),
    _rule("/v1/vdso/sidecars", "POST", "upload_ciphertext_sidecar", RouteClassification.PRIVILEGED_STATE_CHANGE, _PRIVILEGED),
    _rule("/v1/vdso/sidecars/{content_hash}", "GET", "get_sidecar_commitment", RouteClassification.AUTHENTICATED_READ, _SENSITIVE_READ),
    _rule("/v1/vdso/disclosures/verify", "POST", "verify_disclosure", RouteClassification.PRIVILEGED_STATE_CHANGE, "POST is protected by default even though this handler is computational"),
)

WEBSOCKET_RULES: tuple[RouteRule, ...] = ()
_STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_PROTECTED = frozenset(
    {
        RouteClassification.AUTHENTICATED_READ,
        RouteClassification.PRIVILEGED_STATE_CHANGE,
    }
)


def _compile_rules() -> tuple[tuple[RouteRule, re.Pattern[str]], ...]:
    seen: set[tuple[str, str]] = set()
    compiled = []
    for rule in ROUTE_RULES:
        key = (rule.path, rule.method)
        if key in seen:
            raise RoutePolicyError("gateway route policy contains a duplicate")
        seen.add(key)
        if rule.method in _STATE_CHANGING_METHODS and (
            rule.classification is not RouteClassification.PRIVILEGED_STATE_CHANGE
        ):
            raise RoutePolicyError("state-changing gateway route is not privileged")
        compiled.append((rule, compile_path(rule.path)[0]))
    return tuple(compiled)


_COMPILED_RULES = _compile_rules()


def is_protected(classification: RouteClassification) -> bool:
    return classification in _PROTECTED


def classify_request(method: str, path: str) -> RouteClassification | None:
    """Classify one decoded ASGI method/path without following redirects."""

    if not isinstance(method, str) or not isinstance(path, str):
        return None
    method = method.upper()
    matching_paths = [
        rule
        for rule, pattern in _COMPILED_RULES
        if pattern.fullmatch(path) is not None
    ]
    exact = [rule for rule in matching_paths if rule.method == method]
    if len(exact) == 1:
        return exact[0].classification
    if len(exact) > 1:
        raise RoutePolicyError("gateway route classification is ambiguous")

    # CORS preflight is framework-only. It never invokes an application route.
    if method == "OPTIONS" and matching_paths:
        return RouteClassification.FRAMEWORK_ONLY
    # Unregistered state-changing methods at a known path still authenticate
    # before the router returns 405. This prevents a future method-alias bypass.
    if method in _STATE_CHANGING_METHODS and matching_paths:
        return RouteClassification.PRIVILEGED_STATE_CHANGE
    if matching_paths:
        return RouteClassification.DISABLED

    # Starlette's automatic slash redirect is deliberately disabled at this
    # boundary so an alternate target cannot inherit a different policy.
    alternate = path[:-1] if path.endswith("/") and path != "/" else path + "/"
    if any(pattern.fullmatch(alternate) is not None for _, pattern in _COMPILED_RULES):
        return RouteClassification.DISABLED
    return None


def _iter_registered_routes(routes: Iterable[object]):
    for route in routes:
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            yield from _iter_registered_routes(original_router.routes)
            continue
        if isinstance(route, Mount):
            child_routes = getattr(route.app, "routes", ())
            for child_path, methods, name, websocket in _iter_registered_routes(child_routes):
                yield route.path.rstrip("/") + child_path, methods, name, websocket
            continue
        if isinstance(route, WebSocketRoute):
            yield route.path, frozenset(), route.name, True
            continue
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        name = getattr(route, "name", None)
        if isinstance(path, str) and methods:
            yield path, frozenset(str(method) for method in methods), str(name), False


def validate_route_policy(app) -> None:
    """Fail startup unless registered routes equal the reviewed closed ledger."""

    actual: set[tuple[str, str, str]] = set()
    duplicate_actual: set[tuple[str, str]] = set()
    actual_keys: set[tuple[str, str]] = set()
    websockets: set[tuple[str, str]] = set()
    for path, methods, name, websocket in _iter_registered_routes(app.routes):
        if websocket:
            websockets.add((path, name))
            continue
        for method in methods:
            key = (path, method)
            if key in actual_keys:
                duplicate_actual.add(key)
            actual_keys.add(key)
            actual.add((path, method, name))

    expected = {(rule.path, rule.method, rule.name) for rule in ROUTE_RULES}
    expected_websockets = {(rule.path, rule.name) for rule in WEBSOCKET_RULES}
    if duplicate_actual or actual != expected or websockets != expected_websockets:
        raise RoutePolicyError("gateway route inventory does not match the closed policy")
