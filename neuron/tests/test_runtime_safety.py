import pytest

from neuron.runtime_safety import LiveModeSafetyError, is_live_environment


def test_local_environment_allows_explicit_mock(monkeypatch):
    monkeypatch.delenv("VAMS_ENV", raising=False)
    monkeypatch.setenv("OMS_MOCK_MODE", "true")

    from neuron.sdk.oms_identity import OMSIdentityVerifier

    verifier = OMSIdentityVerifier(mock_mode=True)
    assert is_live_environment() is False
    assert verifier.is_verified("0x99abc") is True


@pytest.mark.parametrize(
    ("env_name", "factory"),
    [
        ("OMS_MOCK_MODE", lambda: __import__("neuron.sdk.oms_identity", fromlist=["OMSIdentityVerifier"]).OMSIdentityVerifier()),
        ("TRAILS_MOCK_MODE", lambda: __import__("neuron.sdk.trails_client", fromlist=["TrailsClient"]).TrailsClient()),
        ("COINME_MOCK_MODE", lambda: __import__("neuron.payments.coinme_client", fromlist=["CoinmeClient"]).CoinmeClient()),
        ("AVAIL_MOCK_MODE", lambda: __import__("neuron.sdk.avail_substrate", fromlist=["AvailDASDK"]).AvailDASDK()),
        ("EIGENDA_MOCK_MODE", lambda: __import__("neuron.sdk.eigenda_kzg", fromlist=["EigenDASDK"]).EigenDASDK()),
        ("IAGON_MOCK_MODE", lambda: __import__("neuron.sdk.iagon_storage", fromlist=["IagonStorageSDK"]).IagonStorageSDK()),
    ],
)
def test_live_environment_rejects_mock_clients(monkeypatch, env_name, factory):
    monkeypatch.setenv("VAMS_ENV", "testnet")
    monkeypatch.setenv(env_name, "true")

    with pytest.raises(LiveModeSafetyError):
        factory()


def test_live_environment_rejects_default_oms_secret(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")
    monkeypatch.setenv("OMS_MOCK_MODE", "false")
    monkeypatch.delenv("OMS_API_KEY", raising=False)

    from neuron.sdk.oms_identity import OMSIdentityVerifier

    with pytest.raises(LiveModeSafetyError):
        OMSIdentityVerifier()


def test_local_non_mock_clients_require_explicit_api_keys(monkeypatch):
    monkeypatch.delenv("VAMS_ENV", raising=False)
    monkeypatch.delenv("OMS_API_KEY", raising=False)
    monkeypatch.delenv("TRAILS_API_KEY", raising=False)
    monkeypatch.delenv("COINME_API_KEY", raising=False)

    from neuron.sdk.oms_identity import OMSIdentityVerifier
    from neuron.sdk.trails_client import TrailsClient
    from neuron.payments.coinme_client import CoinmeClient

    with pytest.raises(LiveModeSafetyError, match="OMS_API_KEY"):
        OMSIdentityVerifier(mock_mode=False)
    with pytest.raises(LiveModeSafetyError, match="TRAILS_API_KEY"):
        TrailsClient(mock_mode=False)
    with pytest.raises(LiveModeSafetyError, match="COINME_API_KEY"):
        CoinmeClient(mock_mode=False)


def test_live_environment_rejects_da_stub_adapters(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")

    from neuron.da.adapters.eigenda_adapter import EigenDAAdapter
    from neuron.da.adapters.avail_adapter import AvailDAAdapter

    with pytest.raises(LiveModeSafetyError):
        EigenDAAdapter()
    with pytest.raises(LiveModeSafetyError):
        AvailDAAdapter()


def test_live_environment_excludes_audit_log_stub_routes(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")

    from neuron.da.models import DAProtocol
    from neuron.da.performance_audit import PerformanceAuditLog

    audit_log = PerformanceAuditLog(mock_mode=False)
    assert set(audit_log.adapters) == {DAProtocol.CELESTIA}


def test_live_environment_rejects_enabling_da_stub_routes(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")

    from neuron.da.performance_audit import PerformanceAuditLog

    with pytest.raises(LiveModeSafetyError):
        PerformanceAuditLog(
            mock_mode=False,
            config={"enabled_protocols": ["celestia", "eigenda"]},
        )


def test_live_environment_rejects_bridge_mock(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")

    from neuron.bridge_executor import BridgeExecutor, MultiISMVerifier

    with pytest.raises(LiveModeSafetyError):
        MultiISMVerifier(mock_mode=True)
    with pytest.raises(LiveModeSafetyError):
        BridgeExecutor(mock_mode=True)


def test_live_environment_rejects_incomplete_interrupt_routes(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")

    from neuron.sdk.interrupt_handler import InterruptVectorTable

    with pytest.raises(LiveModeSafetyError):
        InterruptVectorTable(mock_mode=True)
    with pytest.raises(LiveModeSafetyError, match="audited real handler"):
        InterruptVectorTable(mock_mode=False)


def test_live_environment_rejects_arweave_mock_upload(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")

    from neuron.storage.arweave import ArweaveStorage

    with pytest.raises(LiveModeSafetyError):
        ArweaveStorage()
