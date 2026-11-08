import os
import threading

from fastapi.testclient import TestClient

os.environ["VAMS_ENV"] = "test"

from gateway import server
from neuron.tests.m2_gateway_helpers import AUDIENCE, SIGNER


def test_gateway_lifecycle_shutdown_is_idempotent_and_fail_closed(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("GATEWAY_ADMIN_PASSWORD", "SecureTestPassword123!")
    monkeypatch.setenv("VAMS_ENV", "testnet")
    monkeypatch.setenv("VAMS_MOCK_MODE", "false")
    monkeypatch.setenv("GATEWAY_ALLOWED_ORIGINS", "https://gateway.example")
    monkeypatch.setenv("GATEWAY_ADMIN_DID", SIGNER)
    monkeypatch.setenv("GATEWAY_AUTH_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("GATEWAY_HEARTBEAT_CERT_FINGERPRINTS", "aa")
    monkeypatch.setenv(
        "GATEWAY_AUTH_REPLAY_DB", str(tmp_path / "replay.sqlite3")
    )

    for _ in range(2):
        with TestClient(server.app, client=("127.0.0.1", 50000)) as client:
            response = client.post(
                "/compose",
                json={"blueprint_name": "ServiceBlock_OMS_v1"},
                headers={"X-VAMS-Ingress-Version": "envoy-1.39.1-v1"},
                auth=("admin", "SecureTestPassword123!"),
            )
            assert response.status_code == 401
            assert response.json()["detail"] == (
                "gateway_request_denied:missing_version"
            )
            assert server.cleanup_task is not None
            assert server.keeper is not None and server.keeper._running
        assert server.cleanup_task is None
        assert server.keeper is not None and not server.keeper._running
        assert not any(
            thread.name == "vams-economics-keeper" and thread.is_alive()
            for thread in threading.enumerate()
        )
