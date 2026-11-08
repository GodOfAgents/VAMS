import os
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, root_dir)

os.environ.setdefault("GATEWAY_ADMIN_PASSWORD", "SecureTestPassword123!")
os.environ["VAMS_ENV"] = "test"

from gateway import server
from neuron.tests.m2_gateway_helpers import (
    AUDIENCE,
    SIGNER,
    compact_json,
    signed_headers,
)


def test_did_signature_is_single_use(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "test")
    monkeypatch.setenv("GATEWAY_ADMIN_DID", SIGNER)
    monkeypatch.setenv("GATEWAY_AUTH_AUDIENCE", AUDIENCE)
    headers = signed_headers("GET", "/nodes")

    with TestClient(server.app) as client:
        assert client.get("/nodes", headers=headers).status_code == 200
        replay = client.get("/nodes", headers=headers)

    assert replay.status_code == 401
    assert replay.json()["detail"] == "gateway_request_denied:duplicate_nonce"


def test_live_gateway_rejects_basic_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("VAMS_ENV", "testnet")
    monkeypatch.setenv("GATEWAY_ADMIN_DID", SIGNER)
    monkeypatch.setenv("GATEWAY_AUTH_AUDIENCE", AUDIENCE)
    monkeypatch.setenv(
        "GATEWAY_AUTH_REPLAY_DB", str(tmp_path / "basic-auth.sqlite3")
    )
    monkeypatch.setenv("GATEWAY_ALLOWED_ORIGINS", "https://gateway.example")
    monkeypatch.setenv("GATEWAY_HEARTBEAT_CERT_FINGERPRINTS", "aa")
    with TestClient(server.app, client=("127.0.0.1", 50000)) as client:
        response = client.post(
            "/compose",
            json={"blueprint_name": "ServiceBlock_OMS_v1"},
            headers={"X-VAMS-Ingress-Version": "envoy-1.39.1-v1"},
            auth=("admin", "SecureTestPassword123!"),
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "gateway_request_denied:missing_version"


def test_live_gateway_startup_requires_admin_did(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")
    monkeypatch.setenv("GATEWAY_ALLOWED_ORIGINS", "https://gateway.example")
    monkeypatch.delenv("GATEWAY_ADMIN_DID", raising=False)
    monkeypatch.setenv("GATEWAY_HEARTBEAT_CERT_FINGERPRINTS", "aa")

    with pytest.raises(RuntimeError, match="GATEWAY_ADMIN_DID is required"):
        with TestClient(server.app):
            pass


def test_live_gateway_startup_requires_heartbeat_cert_allowlist(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")
    monkeypatch.setenv("GATEWAY_ALLOWED_ORIGINS", "https://gateway.example")
    monkeypatch.setenv("GATEWAY_ADMIN_DID", "did:key:" + "00" * 64)
    monkeypatch.delenv("GATEWAY_HEARTBEAT_CERT_FINGERPRINTS", raising=False)

    with pytest.raises(RuntimeError, match="GATEWAY_HEARTBEAT_CERT_FINGERPRINTS is required"):
        with TestClient(server.app):
            pass


def test_live_gateway_rejects_wildcard_cors(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")

    with pytest.raises(RuntimeError, match="Wildcard CORS origins"):
        server.resolve_allowed_origins("*")


def test_live_gateway_requires_explicit_cors_origins(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")
    monkeypatch.delenv("GATEWAY_ALLOWED_ORIGINS", raising=False)

    with pytest.raises(RuntimeError, match="GATEWAY_ALLOWED_ORIGINS is required"):
        server.resolve_allowed_origins()


def test_gateway_rejects_oversized_request_before_parsing():
    client = TestClient(server.app)
    response = client.post(
        "/heartbeat",
        content=b"x",
        headers={"Content-Length": str(1_048_577)},
    )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_gateway_rejects_chunked_oversized_request_without_length():
    downstream_called = False

    async def downstream(scope, receive, send):
        nonlocal downstream_called
        downstream_called = True

    middleware = server.RequestSizeLimitMiddleware(downstream, max_bytes=4)
    messages = iter(
        [
            {"type": "http.request", "body": b"123", "more_body": True},
            {"type": "http.request", "body": b"45", "more_body": False},
        ]
    )
    sent = []

    async def receive():
        return next(messages)

    async def send(message):
        sent.append(message)

    await middleware(
        {"type": "http", "method": "POST", "path": "/heartbeat", "headers": []},
        receive,
        send,
    )

    assert downstream_called is False
    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 413


def test_live_gateway_main_binds_loopback(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")

    with patch("gateway.server.uvicorn.run") as run:
        server.main()

    assert run.call_args.kwargs["host"] == "127.0.0.1"


def test_live_heartbeat_requires_verified_client_cert(monkeypatch, tmp_path):
    monkeypatch.setenv("VAMS_ENV", "testnet")
    monkeypatch.setenv("GATEWAY_ADMIN_DID", SIGNER)
    monkeypatch.setenv("GATEWAY_AUTH_AUDIENCE", AUDIENCE)
    monkeypatch.setenv(
        "GATEWAY_AUTH_REPLAY_DB", str(tmp_path / "heartbeat.sqlite3")
    )
    monkeypatch.setenv("GATEWAY_ALLOWED_ORIGINS", "https://gateway.example")
    monkeypatch.setenv("GATEWAY_HEARTBEAT_CERT_FINGERPRINTS", "aa")
    body = compact_json({"payload": "{}", "signature": "00"})

    with TestClient(server.app, client=("127.0.0.1", 50000)) as client:
        headers = signed_headers("POST", "/heartbeat", body=body)
        headers["X-VAMS-Ingress-Version"] = "envoy-1.39.1-v1"
        response = client.post(
            "/heartbeat",
            content=body,
            headers=headers,
        )

    assert response.status_code == 401
    assert "mTLS client certificate verification is required" in response.json()["detail"]


def test_live_heartbeat_accepts_allowed_client_cert(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")
    monkeypatch.setenv("GATEWAY_HEARTBEAT_CERT_FINGERPRINTS", "AA:BB")
    request = type(
        "Request",
        (),
        {"headers": {
            "X-VAMS-Client-Cert-Verified": "SUCCESS",
            "X-VAMS-Client-Cert-Fingerprint": "aa:bb",
        }},
    )()

    assert server.verify_heartbeat_client_certificate(request) == "aabb"


def test_live_heartbeat_rejects_unlisted_client_cert(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")
    monkeypatch.setenv("GATEWAY_HEARTBEAT_CERT_FINGERPRINTS", "AA:BB")
    request = type(
        "Request",
        (),
        {"headers": {
            "X-VAMS-Client-Cert-Verified": "SUCCESS",
            "X-VAMS-Client-Cert-Fingerprint": "cc:dd",
        }},
    )()

    with pytest.raises(server.HTTPException) as exc:
        server.verify_heartbeat_client_certificate(request)
    assert exc.value.status_code == 403
