"""M2.3 public-boundary coverage for the root FastAPI gateway."""

from __future__ import annotations

import http.client
import json
import multiprocessing
import os
import socket
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("VAMS_ENV", "test")
os.environ.setdefault("GATEWAY_ADMIN_PASSWORD", "m2-3-test-password")

from gateway import server
from gateway.replay_store import (
    ReplayStorageInitializationError,
    RevocationIdentity,
    SQLiteDurableReplayStore,
    SQLiteReplayConfiguration,
    signer_identity_digest,
)
from gateway.request_auth import GatewayAuthenticationError, ReplayOutcome
from gateway.route_policy import (
    ROUTE_RULES,
    WEBSOCKET_RULES,
    RouteClassification,
    RoutePolicyError,
    classify_request,
    validate_route_policy,
)
from gateway.route_security import GatewayRouteSecurityMiddleware
from neuron.runtime_safety import load_runtime_policy
from neuron.tests.m2_gateway_helpers import (
    AUDIENCE,
    SIGNER,
    compact_json,
    signed_headers,
)


# Deliberately independent of the production route-policy helper.
EXPECTED_ROUTE_LEDGER = {
    ("/openapi.json", "GET", "framework_only"),
    ("/openapi.json", "HEAD", "framework_only"),
    ("/docs", "GET", "framework_only"),
    ("/docs", "HEAD", "framework_only"),
    ("/docs/oauth2-redirect", "GET", "framework_only"),
    ("/docs/oauth2-redirect", "HEAD", "framework_only"),
    ("/redoc", "GET", "framework_only"),
    ("/redoc", "HEAD", "framework_only"),
    ("/", "GET", "authenticated_read"),
    ("/heartbeat", "POST", "privileged_state_change"),
    ("/nodes", "GET", "authenticated_read"),
    ("/health", "GET", "public"),
    ("/compose", "POST", "privileged_state_change"),
    ("/compose/{instance_id}", "DELETE", "privileged_state_change"),
    ("/compose/instances", "GET", "authenticated_read"),
    ("/compose/blueprints", "GET", "public"),
    ("/services/blocks", "GET", "public"),
    ("/services/macros", "GET", "public"),
    ("/economics/status", "GET", "authenticated_read"),
    ("/economics/epochs", "GET", "authenticated_read"),
    ("/economics/epochs/{epoch_id}", "GET", "authenticated_read"),
    ("/economics/estimate-apr", "GET", "public"),
    ("/da/status", "GET", "authenticated_read"),
    ("/da/anchors", "GET", "authenticated_read"),
    ("/v1/vdso/intents/simulate", "POST", "privileged_state_change"),
    ("/v1/vdso/intents", "POST", "privileged_state_change"),
    ("/v1/vdso/intents/{intent_id}", "GET", "authenticated_read"),
    ("/v1/vdso/objects/{object_id}", "GET", "authenticated_read"),
    ("/v1/vdso/adapters", "GET", "authenticated_read"),
    ("/v1/vdso/sidecars", "POST", "privileged_state_change"),
    ("/v1/vdso/sidecars/{content_hash}", "GET", "authenticated_read"),
    ("/v1/vdso/disclosures/verify", "POST", "privileged_state_change"),
}


class _SyntheticInstance:
    blueprint = SimpleNamespace(required_service_blocks=[])
    allocation = SimpleNamespace(total_hourly_cost=1.0)

    @staticmethod
    def to_dict() -> dict[str, str]:
        return {"instance_id": "synthetic-m2-3"}


class _RecordingComposer:
    """Stand-in protected handler for auth/replay tests.

    The real Composer simulation is demo-only (see
    test_local_mode_composer_simulation_stays_unavailable); this recorder
    isolates M2 authentication semantics from that gate.
    """

    def __init__(self, counter=None) -> None:
        self.calls = 0
        self.fail = False
        self._counter = counter

    def assert_simulation_available(self) -> None:
        return None

    def provision_blueprint(self, _name: str):
        self.calls += 1
        if self._counter is not None:
            with self._counter.get_lock():
                self._counter.value += 1
        if self.fail:
            raise server.ComposerError("synthetic handler failure")
        return _SyntheticInstance()


@dataclass
class _GatewayFixture:
    database: str
    composer: _RecordingComposer


@pytest.fixture
def configured_gateway(monkeypatch, tmp_path):
    database = str(tmp_path / "m2-3-replay.sqlite3")
    monkeypatch.setenv("VAMS_ENV", "local")
    monkeypatch.setenv("VAMS_MOCK_MODE", "false")
    monkeypatch.setenv("GATEWAY_ADMIN_PASSWORD", "m2-3-test-password")
    monkeypatch.setenv("GATEWAY_ADMIN_DID", SIGNER)
    monkeypatch.setenv("GATEWAY_AUTH_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("GATEWAY_AUTH_REPLAY_DB", database)
    monkeypatch.delenv("GATEWAY_ALLOWED_ORIGINS", raising=False)
    recorder = _RecordingComposer()
    monkeypatch.setattr(server, "composer", recorder)
    monkeypatch.setattr(server, "COMPOSER_AVAILABLE", True)
    # Startup would otherwise rebind the real (demo-only) Composer over the recorder.
    monkeypatch.setattr(server, "_bind_resource_composer", lambda _policy: None)
    server.nodes.clear()
    yield _GatewayFixture(database, recorder)
    server.nodes.clear()


def test_local_mode_composer_simulation_stays_unavailable(monkeypatch, tmp_path):
    monkeypatch.setenv("VAMS_ENV", "local")
    monkeypatch.setenv("VAMS_MOCK_MODE", "false")
    monkeypatch.setenv("GATEWAY_ADMIN_PASSWORD", "m2-3-test-password")
    monkeypatch.setenv("GATEWAY_ADMIN_DID", SIGNER)
    monkeypatch.setenv("GATEWAY_AUTH_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("GATEWAY_AUTH_REPLAY_DB", str(tmp_path / "local-gate.sqlite3"))
    monkeypatch.delenv("GATEWAY_ALLOWED_ORIGINS", raising=False)
    calls = []
    real_bind = server._bind_resource_composer

    def bind_then_watch(policy):
        real_bind(policy)
        original = server.composer.provision_blueprint
        monkeypatch.setattr(server.composer, "provision_blueprint",
                            lambda *a, **k: calls.append(1) or original(*a, **k))

    monkeypatch.setattr(server, "_bind_resource_composer", bind_then_watch)
    server.nodes.clear()
    body = compact_json({"blueprint_name": "ServiceBlock_OMS_v1"})
    with TestClient(server.app) as client:
        response = _compose_request(client, nonce=900, body=body)
    server.nodes.clear()
    assert response.status_code == 503
    assert calls == []


def _compose_request(client, *, nonce: int, headers=None, body=None, target="/compose"):
    raw_body = compact_json({"blueprint_name": "ServiceBlock_OMS_v1"})
    effective_body = raw_body if body is None else body
    effective_headers = headers or signed_headers(
        "POST", "/compose", body=raw_body, nonce=nonce
    )
    return client.post(target, content=effective_body, headers=effective_headers)


def _response_code(response) -> str:
    return response.json()["detail"].removeprefix("gateway_request_denied:")


def _reservation_count(database: str) -> int:
    read_only_uri = f"file:{database}?mode=ro"
    with sqlite3.connect(read_only_uri, uri=True) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM replay_reservations"
        ).fetchone()
    assert row is not None
    return int(row[0])


def _emit_failure_outcome(**record) -> None:
    print("FAILURE_OUTCOME_JSON=" + json.dumps(record, sort_keys=True))


def test_closed_route_ledger_matches_every_registered_route_exactly():
    observed = {
        (rule.path, rule.method, rule.classification.value) for rule in ROUTE_RULES
    }
    assert observed == EXPECTED_ROUTE_LEDGER
    assert len(ROUTE_RULES) == len({(rule.path, rule.method) for rule in ROUTE_RULES})
    assert WEBSOCKET_RULES == ()
    validate_route_policy(server.app)


def test_route_policy_rejects_unclassified_registration_and_duplicate_alias():
    drifted = FastAPI()

    @drifted.get("/unclassified")
    async def unclassified():
        return {"unsafe": True}

    with pytest.raises(RoutePolicyError, match="closed policy"):
        validate_route_policy(drifted)


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_state_changing_methods_are_protected_by_default(method):
    assert classify_request(method, "/nodes") is RouteClassification.PRIVILEGED_STATE_CHANGE


def test_alias_head_options_and_unknown_classification_is_closed():
    assert classify_request("HEAD", "/nodes") is RouteClassification.DISABLED
    assert classify_request("OPTIONS", "/compose") is RouteClassification.FRAMEWORK_ONLY
    assert classify_request("GET", "/nodes/") is RouteClassification.DISABLED
    assert classify_request("GET", "/not-registered") is None


def test_public_routes_remain_reachable_and_sensitive_read_requires_m2(
    configured_gateway,
):
    with TestClient(server.app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/compose/blueprints").status_code == 200
        denied = client.get("/nodes")
        allowed = client.get(
            "/nodes", headers=signed_headers("GET", "/nodes", nonce=2)
        )
    assert denied.status_code == 401
    assert _response_code(denied) == "missing_version"
    assert allowed.status_code == 200


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("missing", "missing_version"),
        ("malformed", "malformed_nonce"),
        ("expired", "expired"),
        ("future", "issued_in_future"),
        ("audience", "audience_mismatch"),
        ("version", "unsupported_version"),
        ("algorithm", "unsupported_algorithm"),
        ("signature", "invalid_signature"),
        ("signer", "unknown_signer"),
    ],
)
def test_invalid_authentication_never_executes_or_consumes_nonce(
    configured_gateway, case, expected
):
    nonce = 100
    body = compact_json({"blueprint_name": "ServiceBlock_OMS_v1"})
    now = int(time.time())
    if case == "expired":
        headers = signed_headers(
            "POST",
            "/compose",
            body=body,
            nonce=nonce,
            issued_at=now - 120,
            expires_at=now - 1,
        )
    elif case == "future":
        headers = signed_headers(
            "POST",
            "/compose",
            body=body,
            nonce=nonce,
            issued_at=now + 301,
            expires_at=now + 420,
        )
    elif case == "audience":
        headers = signed_headers(
            "POST",
            "/compose",
            body=body,
            nonce=nonce,
            audience="vams.gateway.other",
        )
    else:
        headers = signed_headers("POST", "/compose", body=body, nonce=nonce)
        if case == "missing":
            del headers["X-VAMS-Auth-Version"]
        elif case == "malformed":
            headers["X-VAMS-Auth-Nonce"] = "not-a-nonce"
        elif case == "version":
            headers["X-VAMS-Auth-Version"] = "VAMS-GATEWAY-AUTH/0"
        elif case == "algorithm":
            headers["X-VAMS-Auth-Algorithm"] = "RSA-PSS-SHA256"
        elif case == "signature":
            headers["X-VAMS-Auth-Signature"] = "00" * 64
        elif case == "signer":
            headers["X-VAMS-Auth-Signer"] = "did:key:" + "01" * 64

    with TestClient(server.app) as client:
        denied = _compose_request(client, nonce=nonce, headers=headers, body=body)
        assert configured_gateway.composer.calls == 0
        accepted = _compose_request(client, nonce=nonce, body=body)

    assert denied.status_code == 401
    assert _response_code(denied) == expected
    assert accepted.status_code == 200
    assert configured_gateway.composer.calls == 1


def test_duplicate_security_header_is_rejected_without_nonce_consumption(
    configured_gateway,
):
    body = compact_json({"blueprint_name": "ServiceBlock_OMS_v1"})
    valid = signed_headers("POST", "/compose", body=body, nonce=210)
    duplicate = list(valid.items()) + [("X-VAMS-Auth-Version", valid["X-VAMS-Auth-Version"])]
    with TestClient(server.app) as client:
        denied = client.post("/compose", content=body, headers=duplicate)
        accepted = _compose_request(client, nonce=210, body=body)
    assert denied.status_code == 401
    assert _response_code(denied) == "duplicate_version"
    assert accepted.status_code == 200
    assert configured_gateway.composer.calls == 1


@pytest.mark.parametrize(
    "case",
    [
        "method",
        "path",
        "query_order",
        "query_encoding",
        "body",
        "content_type",
        "multipart",
    ],
)
def test_request_binding_tamper_fails_before_handler_and_reservation(
    configured_gateway, case
):
    nonce = 300
    body = compact_json({"blueprint_name": "ServiceBlock_OMS_v1"})
    target = "/compose"
    effective_body = body
    if case == "method":
        headers = signed_headers("PUT", "/compose", body=body, nonce=nonce)
    elif case == "path":
        headers = signed_headers("POST", "/heartbeat", body=body, nonce=nonce)
    elif case == "query_order":
        headers = signed_headers(
            "POST", "/compose", body=body, raw_query="a=1&b=2", nonce=nonce
        )
        target = "/compose?b=2&a=1"
    elif case == "query_encoding":
        headers = signed_headers(
            "POST", "/compose", body=body, raw_query="a=%20", nonce=nonce
        )
        target = "/compose?a=+"
    elif case == "body":
        headers = signed_headers("POST", "/compose", body=body, nonce=nonce)
        effective_body = compact_json({"blueprint_name": "different"})
    elif case == "content_type":
        headers = signed_headers("POST", "/compose", body=body, nonce=nonce)
        headers["Content-Type"] = "text/plain"
    else:
        headers = signed_headers("POST", "/compose", body=body, nonce=nonce)
        headers["Content-Type"] = "multipart/form-data; boundary=synthetic"

    with TestClient(server.app) as client:
        denied = client.post(target, content=effective_body, headers=headers)
        assert configured_gateway.composer.calls == 0
        accepted = _compose_request(client, nonce=nonce, body=body)

    assert denied.status_code in {401, 415}
    assert accepted.status_code == 200
    assert configured_gateway.composer.calls == 1


def test_encoded_path_trailing_slash_and_head_cannot_bypass_policy(
    configured_gateway,
):
    with TestClient(server.app) as client:
        assert client.post("/compose/", content=b"{}").status_code == 404
        assert client.post("/compose%2F", content=b"{}").status_code == 404
        assert client.head("/nodes").status_code == 404
    assert configured_gateway.composer.calls == 0


def test_cors_preflight_cannot_execute_state_change(configured_gateway):
    with TestClient(server.app) as client:
        response = client.options(
            "/compose",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-VAMS-Auth-Version",
            },
        )
    assert response.status_code == 200
    assert configured_gateway.composer.calls == 0


@pytest.mark.asyncio
async def test_protected_stream_without_content_length_is_rejected_before_route():
    downstream_called = False

    async def downstream(scope, receive, send):
        nonlocal downstream_called
        downstream_called = True

    middleware = GatewayRouteSecurityMiddleware(downstream)
    messages = iter(
        [{"type": "http.request", "body": b"{}", "more_body": False}]
    )
    sent = []

    async def receive():
        return next(messages)

    async def send(message):
        sent.append(message)

    await middleware(
        {
            "type": "http",
            "method": "POST",
            "path": "/compose",
            "raw_path": b"/compose",
            "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
        },
        receive,
        send,
    )
    assert downstream_called is False
    assert sent[0]["status"] == 400
    assert b"missing_content_length" in sent[1]["body"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ([(b"content-length", b"x")], b"malformed_content_length"),
        (
            [(b"content-length", b"0"), (b"content-length", b"0")],
            b"ambiguous_content_length",
        ),
        ([(b"transfer-encoding", b"chunked")], b"unsupported_transfer_encoding"),
    ],
)
async def test_outer_framing_failures_are_uniform_and_do_not_reach_route(
    headers, expected
):
    downstream_called = False

    async def downstream(scope, receive, send):
        nonlocal downstream_called
        downstream_called = True

    middleware = server.RequestSizeLimitMiddleware(downstream)
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    await middleware(
        {"type": "http", "method": "POST", "path": "/compose", "headers": headers},
        receive,
        send,
    )
    assert downstream_called is False
    assert sent[0]["status"] == 400
    assert expected in sent[1]["body"]


def test_success_executes_once_and_handler_failure_still_consumes_nonce(
    configured_gateway,
):
    with TestClient(server.app) as client:
        first = _compose_request(client, nonce=401)
        replay = _compose_request(client, nonce=401)
        configured_gateway.composer.fail = True
        failed = _compose_request(client, nonce=402)
        failed_replay = _compose_request(client, nonce=402)

    assert first.status_code == 200
    assert replay.status_code == 401
    assert failed.status_code == 422
    assert failed_replay.status_code == 401
    assert configured_gateway.composer.calls == 2


def test_revoked_signer_is_denied_before_handler(configured_gateway):
    now = int(time.time())
    with TestClient(server.app) as client:
        store = server.app.state.auth_replay_store
        store.revoke_signer(
            RevocationIdentity(signer_identity_digest(SIGNER)),
            effective_at=now,
            now=now,
        )
        denied = _compose_request(client, nonce=450)
    assert denied.status_code == 401
    assert _response_code(denied) == "revoked_nonce"
    assert configured_gateway.composer.calls == 0


@pytest.mark.parametrize("failure", ["locked", "missing"])
def test_storage_uncertainty_denies_with_zero_side_effects(
    configured_gateway, failure
):
    blocker = None
    with TestClient(server.app) as client:
        if failure == "locked":
            blocker = sqlite3.connect(
                configured_gateway.database, timeout=1, isolation_level=None
            )
            blocker.execute("BEGIN IMMEDIATE")
        elif failure == "missing":
            os.unlink(configured_gateway.database)
        try:
            denied = _compose_request(client, nonce=500)
        finally:
            if blocker is not None:
                blocker.rollback()
                blocker.close()
    reservation_count = (
        _reservation_count(configured_gateway.database)
        if failure == "locked"
        else None
    )
    _emit_failure_outcome(
        scenario_id=f"storage_{failure}",
        terminal_category=_response_code(denied),
        protected_handler_call_count=configured_gateway.composer.calls,
        reservation_cardinality=(
            reservation_count if reservation_count is not None else "UNKNOWN"
        ),
    )
    assert denied.status_code == 503
    assert _response_code(denied) == "storage_failure"
    assert configured_gateway.composer.calls == 0
    if failure == "locked":
        assert reservation_count == 0
    else:
        # The configured database was removed; absence of a readable database
        # does not establish the reservation state.
        assert reservation_count is None


def test_trigger_storage_failure_denies_before_handler_and_reserves_nothing(
    configured_gateway, caplog
):
    marker = "synthetic-storage-error-detail"
    with TestClient(server.app) as client:
        with sqlite3.connect(configured_gateway.database) as connection:
            connection.execute(
                "CREATE TRIGGER synthetic_replay_failure BEFORE INSERT "
                f"ON replay_reservations BEGIN SELECT RAISE(ABORT, '{marker}'); END"
            )
        denied = _compose_request(client, nonce=501)
        reservation_count = _reservation_count(configured_gateway.database)
        with sqlite3.connect(configured_gateway.database) as connection:
            connection.execute("DROP TRIGGER synthetic_replay_failure")

    _emit_failure_outcome(
        scenario_id="storage_trigger_abort",
        terminal_category=_response_code(denied),
        protected_handler_call_count=configured_gateway.composer.calls,
        reservation_cardinality=reservation_count,
    )
    assert denied.status_code == 503
    assert _response_code(denied) == "storage_failure"
    assert marker not in denied.text
    assert marker not in caplog.text
    assert configured_gateway.composer.calls == 0
    assert reservation_count == 0


def test_unavailable_replay_outcome_is_sanitized_and_denied_before_handler(
    configured_gateway, monkeypatch
):
    with TestClient(server.app) as client:
        replay_store = server.app.state.auth_replay_store
        monkeypatch.setattr(
            replay_store,
            "reserve_and_consume",
            lambda *_args, **_kwargs: ReplayOutcome.UNAVAILABLE,
        )
        denied = _compose_request(client, nonce=502)
        reservation_count = None

    _emit_failure_outcome(
        scenario_id="replay_unavailable",
        terminal_category=_response_code(denied),
        protected_handler_call_count=configured_gateway.composer.calls,
        reservation_cardinality="UNKNOWN",
    )
    assert denied.status_code == 503
    assert _response_code(denied) == "replay_unavailable"
    assert configured_gateway.composer.calls == 0
    # This controlled outcome source is not a database observation.
    assert reservation_count is None


def test_lost_ack_after_real_reservation_remains_duplicate_and_denied(
    configured_gateway, monkeypatch
):
    marker = "synthetic-lost-ack-detail"
    with TestClient(server.app) as client:
        replay_store = server.app.state.auth_replay_store
        reserve = replay_store.reserve_and_consume
        calls = 0

        def reserve_then_lose_ack(*args, **kwargs):
            nonlocal calls
            calls += 1
            outcome = reserve(*args, **kwargs)
            if calls == 1:
                raise RuntimeError(marker)
            return outcome

        monkeypatch.setattr(
            replay_store, "reserve_and_consume", reserve_then_lose_ack
        )
        first = _compose_request(client, nonce=503)
        count_after_lost_ack = _reservation_count(configured_gateway.database)
        replay = _compose_request(client, nonce=503)
        count_after_replay = _reservation_count(configured_gateway.database)

    _emit_failure_outcome(
        scenario_id="lost_ack_then_duplicate",
        terminal_category="storage_failure_then_duplicate",
        first_response_category=_response_code(first),
        replay_response_category=_response_code(replay),
        protected_handler_call_count=configured_gateway.composer.calls,
        reservation_cardinality_after_lost_ack=count_after_lost_ack,
        reservation_cardinality_after_replay=count_after_replay,
    )
    assert first.status_code == 503
    assert _response_code(first) == "storage_failure"
    assert marker not in first.text
    assert replay.status_code == 401
    assert _response_code(replay) == "duplicate_nonce"
    assert configured_gateway.composer.calls == 0
    assert calls == 2
    assert count_after_lost_ack == 1
    assert count_after_replay == count_after_lost_ack


def test_corrupt_storage_denies_startup_before_any_handler(
    configured_gateway,
):
    with open(configured_gateway.database, "wb") as stream:
        stream.write(b"synthetic-corrupt-database")
    os.chmod(configured_gateway.database, 0o600)
    with pytest.raises(ReplayStorageInitializationError) as failure:
        with TestClient(server.app):
            pass
    _emit_failure_outcome(
        scenario_id="corrupt_storage_startup",
        terminal_category="corrupt_storage_rejected",
        exception_class=type(failure.value).__name__,
        protected_handler_call_count=configured_gateway.composer.calls,
        reservation_cardinality="UNKNOWN",
    )
    assert configured_gateway.composer.calls == 0
    assert server.cleanup_task is None


def test_sanitized_auth_failure_does_not_echo_request_material(
    configured_gateway, caplog
):
    marker = "m2-3-sensitive-request-marker"
    body = compact_json({"blueprint_name": marker})
    headers = signed_headers("POST", "/compose", body=body, nonce=550)
    headers["X-VAMS-Auth-Signature"] = "00" * 64
    with TestClient(server.app) as client:
        response = client.post("/compose", content=body, headers=headers)
    assert response.status_code == 401
    assert marker not in response.text
    assert marker not in caplog.text
    assert SIGNER not in response.text
    assert SIGNER not in caplog.text


def test_live_startup_missing_m2_configuration_fails_before_activity(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("VAMS_ENV", "testnet")
    monkeypatch.setenv("VAMS_MOCK_MODE", "false")
    monkeypatch.setenv("GATEWAY_ADMIN_PASSWORD", "m2-3-test-password")
    monkeypatch.setenv("GATEWAY_ADMIN_DID", SIGNER)
    monkeypatch.setenv("GATEWAY_HEARTBEAT_CERT_FINGERPRINTS", "aa" * 32)
    monkeypatch.setenv("GATEWAY_ALLOWED_ORIGINS", "https://gateway.example")
    monkeypatch.setenv("GATEWAY_AUTH_REPLAY_DB", str(tmp_path / "live.sqlite3"))
    monkeypatch.delenv("GATEWAY_AUTH_AUDIENCE", raising=False)
    with pytest.raises(GatewayAuthenticationError, match="missing_audience"):
        with TestClient(server.app):
            pass
    assert server.cleanup_task is None


class _LoopbackServer:
    def __init__(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("127.0.0.1", 0))
        self.socket.listen(128)
        self.port = self.socket.getsockname()[1]
        self.server = uvicorn.Server(
            uvicorn.Config(server.app, log_level="error", lifespan="on")
        )
        self.thread = threading.Thread(
            target=self.server.run,
            kwargs={"sockets": [self.socket]},
            name="m2-3-loopback-server",
        )

    def start(self) -> None:
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started and self.thread.is_alive():
            if time.monotonic() >= deadline:
                pytest.fail("loopback gateway did not start within bounded timeout")
            threading.Event().wait(0.01)
        if not self.server.started:
            pytest.fail("loopback gateway failed during startup")

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(10)
        self.socket.close()
        if self.thread.is_alive():
            pytest.fail("loopback gateway did not stop within bounded timeout")


def _loopback_request(port, method, target, *, body=b"", headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request(method, target, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def test_real_loopback_http_replay_survives_server_restart(configured_gateway):
    headers = signed_headers("GET", "/nodes", nonce=600)
    first_server = _LoopbackServer()
    first_server.start()
    try:
        assert _loopback_request(first_server.port, "GET", "/health")[0] == 200
        assert _loopback_request(
            first_server.port, "GET", "/nodes", headers=headers
        )[0] == 200
    finally:
        first_server.stop()

    restarted = _LoopbackServer()
    restarted.start()
    try:
        status, payload = _loopback_request(
            restarted.port, "GET", "/nodes", headers=headers
        )
    finally:
        restarted.stop()
    assert status == 401
    assert b"duplicate_nonce" in payload


def _serve_in_process(listener, ready, stop):
    instance = uvicorn.Server(
        uvicorn.Config(server.app, log_level="error", lifespan="on")
    )

    def signal_state():
        deadline = time.monotonic() + 10
        while not instance.started and time.monotonic() < deadline:
            if stop.wait(0.01):
                return
        ready.put(instance.started)
        stop.wait(15)
        instance.should_exit = True

    monitor = threading.Thread(target=signal_state, daemon=True)
    monitor.start()
    instance.run(sockets=[listener])


def test_real_http_workers_share_atomic_replay_and_revocation(
    configured_gateway, monkeypatch
):
    if os.name != "posix":
        pytest.skip("multi-process loopback contract requires POSIX fork")
    context = multiprocessing.get_context("fork")
    counter = context.Value("i", 0)
    monkeypatch.setattr(server, "composer", _RecordingComposer(counter))
    monkeypatch.setattr(server, "COMPOSER_AVAILABLE", True)

    # Initialize the durable schema before workers contend for it.
    with TestClient(server.app):
        pass

    listeners = []
    processes = []
    ready = context.Queue()
    stop = context.Event()
    try:
        for _ in range(2):
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 0))
            listener.listen(128)
            listeners.append(listener)
            process = context.Process(
                target=_serve_in_process, args=(listener, ready, stop)
            )
            process.start()
            processes.append(process)
        assert [ready.get(timeout=12) for _ in processes] == [True, True]
        ports = [listener.getsockname()[1] for listener in listeners]
        body = compact_json({"blueprint_name": "ServiceBlock_OMS_v1"})
        headers = signed_headers("POST", "/compose", body=body, nonce=700)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(
                    _loopback_request,
                    port,
                    "POST",
                    "/compose",
                    body=body,
                    headers=headers,
                )
                for port in ports
            ]
            results = [future.result(timeout=8) for future in futures]
        assert sorted(status for status, _ in results) == [200, 401]
        assert counter.value == 1

        store = SQLiteDurableReplayStore(
            SQLiteReplayConfiguration(configured_gateway.database),
            load_runtime_policy(),
        )
        now = int(time.time())
        store.revoke_signer(
            RevocationIdentity(signer_identity_digest(SIGNER)),
            effective_at=now,
            now=now,
        )
        for nonce, port in enumerate(ports, start=701):
            revoked_headers = signed_headers(
                "POST", "/compose", body=body, nonce=nonce
            )
            status, payload = _loopback_request(
                port,
                "POST",
                "/compose",
                body=body,
                headers=revoked_headers,
            )
            assert status == 401
            assert b"revoked_nonce" in payload
        assert counter.value == 1
    finally:
        stop.set()
        for process in processes:
            process.join(12)
            if process.is_alive():
                process.terminate()
                process.join(5)
        for listener in listeners:
            listener.close()
        assert all(process.exitcode == 0 for process in processes)
