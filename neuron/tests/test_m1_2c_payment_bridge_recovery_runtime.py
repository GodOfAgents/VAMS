"""Public-boundary coverage for M1.2c live containment."""

from __future__ import annotations

import hashlib

import pytest

from neuron.bridge_executor import BridgeExecutor, BridgeStatus, ICBClient, MultiISMVerifier
from neuron.da_router import DARouter
from neuron.mev_protection import BatchAuctionSettler, EncryptedMempool, MEVProtection
from neuron.neuron import VamsNeuron
from neuron.payments.coinme_client import CoinmeClient
from neuron.payments.payment_channel import PaymentChannelManager
from neuron.payments.x402 import X402Client
from neuron.runtime_safety import LiveModeSafetyError, RuntimeConfigurationError
from neuron.sdk.akash_orchestrator import AkashOrchestratorSDK
from neuron.sdk.cognitive_drift import CognitiveDriftDetector
from neuron.sdk.iagon_storage import IagonStorageSDK
from neuron.sdk.interrupt_handler import InterruptSignal, InterruptStatus, InterruptVectorTable
from neuron.sdk.x402_recovery import EscrowStateClient
from neuron.sentinel.sentinel_node import VAMSSentinelNode
from neuron.verifiers.celestia_light_client import CelestiaLightClient


NON_LIVE_MODES = ("test", "local", "demo")
LIVE_MODES = ("staging", "testnet", "production")


@pytest.mark.parametrize("mode", NON_LIVE_MODES)
def test_explicit_non_live_simulations_are_visibly_non_authoritative(mode, tmp_path):
    coinme = CoinmeClient(mock_mode=True, environ={"VAMS_ENV": mode})
    checkout = coinme.create_checkout(5.0, "USD", "synthetic-destination")
    assert checkout["status"] == "simulated"
    assert checkout["simulated"] is True
    assert checkout["evidence_classification"] == "non-authoritative"
    assert checkout["session_id"].startswith("simulated:")

    channel = PaymentChannelManager(
        persistence_path=str(tmp_path / "channels.json"),
        mock_mode=True,
        environ={"VAMS_ENV": mode},
    )
    channel_id = channel.create_channel("0x" + "11" * 20, "0x" + "22" * 20, 10)
    receipt = channel.sign_payment(channel_id, 1, "synthetic-service")
    assert receipt is not None
    assert receipt["signature"].startswith("simulated:")
    assert receipt["simulated"] is True
    assert receipt["evidence_classification"] == "non-authoritative"

    bridge = BridgeExecutor(mock_mode=True, environ={"VAMS_ENV": mode})
    result = bridge.execute("Cardano", b"synthetic-payload")
    assert result.status is BridgeStatus.VERIFIED
    assert result.simulated is True
    assert result.evidence_classification == "non-authoritative"
    assert result.icb_message is not None
    assert result.icb_message.payload_hash == hashlib.sha256(b"synthetic-payload").hexdigest()

    ivt = InterruptVectorTable(mock_mode=True, environ={"VAMS_ENV": mode})
    interrupt = ivt.raise_interrupt(InterruptSignal.SIG_TOOL_INVOKE, {"tool": "synthetic"})
    assert interrupt.status is InterruptStatus.VERIFIED
    assert interrupt.result["mock"] is True
    assert interrupt.proof["type"] == "mock_attestation"


@pytest.mark.parametrize("mode", LIVE_MODES)
@pytest.mark.parametrize(
    "factory",
    (
        lambda env: CoinmeClient(mock_mode=False, environ=env, api_key="provider-key", base_url="https://provider.invalid"),
        lambda env: CoinmeClient(mock_mode=True, environ=env),
        lambda env: PaymentChannelManager(mock_mode=False, environ=env),
        lambda env: X402Client(mock_mode=False, environ=env),
        lambda env: BridgeExecutor(mock_mode=False, environ=env),
        lambda env: MultiISMVerifier(mock_mode=False, environ=env),
        lambda env: ICBClient(environ=env),
        lambda env: InterruptVectorTable(mock_mode=False, environ=env),
        lambda env: EscrowStateClient(mock_mode=False, environ=env),
        lambda env: IagonStorageSDK(mock_mode=False, environ=env, api_key="provider-key"),
        lambda env: AkashOrchestratorSDK(mock_mode=False, environ=env),
        lambda env: EncryptedMempool(mock_mode=False, environ=env),
        lambda env: BatchAuctionSettler(environ=env),
        lambda env: CelestiaLightClient(mock_mode=False, environ=env),
        lambda env: DARouter(mock_mode=False, environ=env),
        lambda env: VAMSSentinelNode(mock_mode=False, environ=env),
        lambda env: VamsNeuron(mock_mode=False, environ=env),
        lambda env: CognitiveDriftDetector(mock_mode=False, environ=env),
    ),
)
def test_every_incomplete_payment_bridge_and_recovery_surface_is_blocked_live(mode, factory, monkeypatch):
    monkeypatch.setenv("VAMS_ENV", mode)
    with pytest.raises(LiveModeSafetyError, match="live|mock mode"):
        factory({"VAMS_ENV": mode})


@pytest.mark.parametrize(
    ("factory", "variable"),
    (
        (lambda env, value: CoinmeClient(mock_mode=value, environ=env), "COINME_MOCK_MODE"),
        (lambda env, value: PaymentChannelManager(mock_mode=value, environ=env), "PAYMENT_CHANNEL_MOCK_MODE"),
        (lambda env, value: X402Client(mock_mode=value, environ=env), "X402_MOCK_MODE"),
        (lambda env, value: BridgeExecutor(mock_mode=value, environ=env), "BRIDGE_MOCK_MODE"),
        (lambda env, value: InterruptVectorTable(mock_mode=value, environ=env), "VAMS_IVT_MOCK"),
        (lambda env, value: EscrowStateClient(mock_mode=value, environ=env), "ESCROW_STATE_MOCK_MODE"),
        (lambda env, value: IagonStorageSDK(mock_mode=value, environ=env), "IAGON_MOCK_MODE"),
        (lambda env, value: AkashOrchestratorSDK(mock_mode=value, environ=env), "AKASH_MOCK_MODE"),
        (lambda env, value: EncryptedMempool(mock_mode=value, environ=env), "MEV_MOCK_MODE"),
        (lambda env, value: CelestiaLightClient(mock_mode=value, environ=env), "CELESTIA_LIGHT_MOCK_MODE"),
        (lambda env, value: DARouter(mock_mode=value, environ=env), "DA_ROUTER_MOCK_MODE"),
        (lambda env, value: VAMSSentinelNode(mock_mode=value, environ=env), "SENTINEL_MOCK_MODE"),
        (lambda env, value: VamsNeuron(mock_mode=value, environ=env), "NEURON_MOCK_MODE"),
        (lambda env, value: CognitiveDriftDetector(mock_mode=value, environ=env), "COGNITIVE_SYNC_MOCK_MODE"),
    ),
)
def test_scoped_flags_reject_malformed_and_conflicting_configuration(factory, variable, monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "local")
    with pytest.raises(RuntimeConfigurationError, match=f"Malformed {variable}"):
        factory({"VAMS_ENV": "local", variable: "TRUE"}, None)
    with pytest.raises(RuntimeConfigurationError, match="Conflicting mock configuration"):
        factory({"VAMS_ENV": "local", variable: "false"}, True)


def test_missing_flags_never_select_simulation(tmp_path):
    environment = {"VAMS_ENV": "local"}
    with pytest.raises(LiveModeSafetyError, match="COINME_API_KEY"):
        CoinmeClient(environ=environment)
    with pytest.raises(LiveModeSafetyError, match="no authoritative"):
        PaymentChannelManager(
            persistence_path=str(tmp_path / "channels.json"), environ=environment
        )
    with pytest.raises(LiveModeSafetyError, match="no authoritative"):
        X402Client(environ=environment)
    with pytest.raises(LiveModeSafetyError, match="no authoritative"):
        BridgeExecutor(environ=environment)
    with pytest.raises(LiveModeSafetyError, match="no authoritative"):
        EscrowStateClient(environ=environment)
    with pytest.raises(LiveModeSafetyError, match="no authoritative"):
        EncryptedMempool(environ=environment)


def test_bridge_proof_and_payload_hash_remain_separate_values():
    client = ICBClient(environ={"VAMS_ENV": "test"})
    payload = b"synthetic-payload"
    message = client.build_bridge_message("polygon", "cardano", payload)
    bridge_proof = b"proof:" + b"a" * 64

    assert message.payload_hash == hashlib.sha256(payload).hexdigest()
    assert bridge_proof != bytes.fromhex(message.payload_hash)
    assert client.verify_bridge_proof(bridge_proof, message.payload_hash) is True
    assert client.verify_bridge_proof(bytes.fromhex(message.payload_hash), message.payload_hash) is False


def test_live_recovery_rejects_before_any_owned_effect():
    class EffectProbe:
        calls = 0

        def __getattr__(self, name):
            self.calls += 1
            raise AssertionError(name)

    probe = EffectProbe()
    with pytest.raises(LiveModeSafetyError, match="live execution is disabled"):
        from neuron.sdk.x402_recovery import X402InterruptHandler

        X402InterruptHandler(
            "agent",
            probe,
            probe,
            probe,
            probe,
            mock_mode=False,
            environ={"VAMS_ENV": "testnet"},
        )
    assert probe.calls == 0


def test_runtime_configuration_is_immutable(tmp_path):
    clients = (
        CoinmeClient(mock_mode=True, environ={"VAMS_ENV": "local"}),
        PaymentChannelManager(
            persistence_path=str(tmp_path / "channels.json"),
            mock_mode=True,
            environ={"VAMS_ENV": "local"},
        ),
        BridgeExecutor(mock_mode=True, environ={"VAMS_ENV": "local"}),
        InterruptVectorTable(mock_mode=True, environ={"VAMS_ENV": "local"}),
        EscrowStateClient(mock_mode=True, environ={"VAMS_ENV": "local"}),
        IagonStorageSDK(mock_mode=True, environ={"VAMS_ENV": "local"}),
        AkashOrchestratorSDK(mock_mode=True, environ={"VAMS_ENV": "local"}),
        EncryptedMempool(mock_mode=True, environ={"VAMS_ENV": "local"}),
    )
    for client in clients:
        field = "_mock_mode" if hasattr(client, "_mock_mode") else "mock_mode"
        with pytest.raises(RuntimeConfigurationError, match="immutable"):
            setattr(client, field, False)


def test_provider_failure_is_sanitized_and_never_becomes_a_rate():
    class FailingTransport:
        @staticmethod
        def get(*args, **kwargs):
            raise RuntimeError("credential=secret-value")

    client = CoinmeClient(
        mock_mode=False,
        environ={"VAMS_ENV": "local"},
        api_key="provider-key",
        base_url="https://provider.invalid",
        transport=FailingTransport(),
    )
    with pytest.raises(LiveModeSafetyError, match="rate provider request failed") as exc_info:
        client.get_conversion_rate("USD", "VAMS")
    assert "secret-value" not in str(exc_info.value)


def test_mev_orchestrator_requires_explicit_simulation():
    with pytest.raises(LiveModeSafetyError, match="no authoritative"):
        MEVProtection(environ={"VAMS_ENV": "demo"})
    mev = MEVProtection(mock_mode=True, environ={"VAMS_ENV": "demo"})
    tx = mev.submit_protected_transaction_sync(b"synthetic")
    assert tx.status.value == "committed"


def test_legacy_da_probe_never_falls_back_to_simulated_success():
    class FailedResponse:
        @staticmethod
        def raise_for_status():
            raise RuntimeError("provider unavailable")

    class FailedTransport:
        @staticmethod
        def post(*args, **kwargs):
            return FailedResponse()

    simulated = CelestiaLightClient(
        mock_mode=True, environ={"VAMS_ENV": "test"}
    )
    assert simulated.sample_availability("synthetic-root") is True

    provider_probe = CelestiaLightClient(
        mock_mode=False,
        environ={"VAMS_ENV": "test"},
        transport=FailedTransport(),
    )
    assert provider_probe.sample_availability("synthetic-root") is False


def test_cognitive_sync_simulation_is_explicit_and_non_authoritative():
    with pytest.raises(LiveModeSafetyError, match="no authoritative"):
        CognitiveDriftDetector(environ={"VAMS_ENV": "demo"})

    detector = CognitiveDriftDetector(
        theta=0.01,
        mock_mode=True,
        environ={"VAMS_ENV": "demo"},
    )
    detector.set_global_state({"epoch": 1})
    detector.measure_drift("agent-a", {"epoch": 2})
    result = detector.trigger_sync_pulse()
    assert result.status.value == "committed"
    assert result.simulated is True
    assert result.evidence_classification == "non-authoritative"
