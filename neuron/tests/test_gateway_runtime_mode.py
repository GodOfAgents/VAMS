import logging
import multiprocessing
import os
import threading

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("GATEWAY_ADMIN_PASSWORD", "SecureRuntimeModeTestPassword123!")
os.environ["VAMS_ENV"] = "test"

from gateway import server
from neuron.tests.m2_gateway_helpers import AUDIENCE, SIGNER
from neuron.runtime_safety import RuntimeConfigurationError


def _configure_gateway(
    monkeypatch, mode: str, *, mock: bool = False, replay_path=None
) -> None:
    monkeypatch.setenv("VAMS_ENV", mode)
    monkeypatch.setenv("VAMS_MOCK_MODE", "true" if mock else "false")
    monkeypatch.setenv("GATEWAY_ADMIN_PASSWORD", "SecureRuntimeModeTestPassword123!")
    monkeypatch.setenv("GATEWAY_AUTH_AUDIENCE", AUDIENCE)
    if mode in {"staging", "testnet", "production"}:
        if replay_path is not None:
            monkeypatch.setenv("GATEWAY_AUTH_REPLAY_DB", str(replay_path))
        monkeypatch.setenv("GATEWAY_ADMIN_DID", SIGNER)
        monkeypatch.setenv("GATEWAY_HEARTBEAT_CERT_FINGERPRINTS", "aa")
        monkeypatch.setenv("GATEWAY_ALLOWED_ORIGINS", "https://gateway.example")
    else:
        monkeypatch.delenv("GATEWAY_AUTH_REPLAY_DB", raising=False)
        monkeypatch.delenv("GATEWAY_ADMIN_DID", raising=False)
        monkeypatch.delenv("GATEWAY_HEARTBEAT_CERT_FINGERPRINTS", raising=False)
        monkeypatch.delenv("GATEWAY_ALLOWED_ORIGINS", raising=False)


def _assert_no_gateway_activity() -> None:
    assert server.cleanup_task is None
    assert server.active_runtime_policy is None
    assert server.keeper is None or not server.keeper._running
    assert not any(
        thread.name == "vams-economics-keeper" and thread.is_alive()
        for thread in threading.enumerate()
    )


@pytest.mark.parametrize(
    "mode", ["test", "local", "demo", "staging", "testnet", "production"]
)
def test_gateway_lifespan_accepts_every_canonical_mode(monkeypatch, tmp_path, mode):
    _configure_gateway(
        monkeypatch,
        mode,
        replay_path=tmp_path / f"{mode}-replay.sqlite3",
    )

    live = mode in {"staging", "testnet", "production"}
    client_kwargs = {"client": ("127.0.0.1", 50000)} if live else {}
    headers = {"X-VAMS-Ingress-Version": "envoy-1.39.1-v1"} if live else {}
    with TestClient(server.app, **client_kwargs) as client:
        response = client.get("/health", headers=headers)
        assert response.status_code == 200
        runtime = response.json()["runtime"]
        assert runtime["mode"] == mode
        assert runtime["runtime_classification"] == (
            "live" if live else "non-live"
        )
    _assert_no_gateway_activity()


@pytest.mark.parametrize("mode", ["test", "local", "demo"])
def test_gateway_lifespan_allows_explicit_mock_only_for_non_live_modes(
    monkeypatch, mode
):
    _configure_gateway(monkeypatch, mode, mock=True)

    with TestClient(server.app) as client:
        runtime = client.get("/health").json()["runtime"]
        assert runtime == {
            "mode": mode,
            "runtime_classification": "non-live",
            "evidence_classification": "non-authoritative",
            "gateway_mock_enabled": True,
        }
    _assert_no_gateway_activity()


@pytest.mark.parametrize("mode", ["staging", "testnet", "production"])
def test_gateway_lifespan_rejects_mock_in_live_modes(monkeypatch, mode):
    _configure_gateway(monkeypatch, mode, mock=True)

    with pytest.raises(RuntimeConfigurationError, match=mode):
        with TestClient(server.app):
            pass
    _assert_no_gateway_activity()


@pytest.mark.parametrize("mode", [None, "", " ", "Testnet", "unknown"])
def test_gateway_rejects_bad_mode_before_owned_background_activity(
    monkeypatch, mode
):
    if mode is None:
        monkeypatch.delenv("VAMS_ENV", raising=False)
    else:
        monkeypatch.setenv("VAMS_ENV", mode)
    monkeypatch.setenv("VAMS_MOCK_MODE", "false")
    monkeypatch.setenv("GATEWAY_ADMIN_PASSWORD", "SecureRuntimeModeTestPassword123!")
    starts = []
    audit_initializations = []
    if server.keeper is not None:
        monkeypatch.setattr(server.keeper, "start", lambda: starts.append("keeper"))
    monkeypatch.setattr(
        server,
        "PerformanceAuditLog",
        lambda **_kwargs: audit_initializations.append("audit"),
    )

    with pytest.raises(RuntimeConfigurationError, match="VAMS_ENV"):
        with TestClient(server.app):
            pass

    assert starts == []
    assert audit_initializations == []
    _assert_no_gateway_activity()


def test_repeated_successful_and_rejected_startups_leave_no_owned_activity(
    monkeypatch,
):
    baseline_children = {child.pid for child in multiprocessing.active_children()}

    for _ in range(2):
        _configure_gateway(monkeypatch, "test", mock=True)
        with TestClient(server.app) as client:
            assert client.get("/health").status_code == 200
        _assert_no_gateway_activity()

        _configure_gateway(monkeypatch, "testnet", mock=True)
        with pytest.raises(RuntimeConfigurationError, match="testnet"):
            with TestClient(server.app):
                pass
        _assert_no_gateway_activity()

    assert {child.pid for child in multiprocessing.active_children()} == baseline_children


def test_gateway_reports_only_sanitized_runtime_classification(
    monkeypatch, caplog
):
    _configure_gateway(monkeypatch, "demo", mock=True)
    secret = "DoNotLogThisRuntimeTestCredential"
    monkeypatch.setenv("GATEWAY_ADMIN_PASSWORD", secret)

    with caplog.at_level(logging.INFO, logger="vams.gateway"):
        with TestClient(server.app) as client:
            response = client.get("/health")
            runtime = response.json()["runtime"]
            assert response.headers["X-VAMS-Runtime-Mode"] == "demo"
            assert response.headers["X-VAMS-Runtime-Classification"] == "non-live"
            assert response.headers["X-VAMS-Evidence-Classification"] == (
                "non-authoritative"
            )

    assert runtime["mode"] == "demo"
    assert runtime["evidence_classification"] == "non-authoritative"
    assert "classification=non-live" in caplog.text
    assert "evidence=non-authoritative" in caplog.text
    assert secret not in caplog.text
    _assert_no_gateway_activity()
