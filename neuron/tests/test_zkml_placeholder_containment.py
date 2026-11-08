from pathlib import Path

import pytest

from neuron.runtime_safety import LiveModeSafetyError
from neuron.sdk.trust_aggregator import TrustAggregatorClient
from neuron.trust_plugins import discover_plugins
from neuron.trust_plugins.tee_plugin import ProofResult
from neuron.trust_plugins.zkml_plugin import ZKMLProofPlugin

SERVICE_HASH = b"\x11" * 32
DELIVERY_HASH = b"\x22" * 32


def test_placeholder_cannot_generate_or_verify_proof():
    plugin = ZKMLProofPlugin()
    generated = plugin.generate_proof(SERVICE_HASH, DELIVERY_HASH)

    assert not generated.valid
    assert generated.proof_data == b""
    assert generated.trust_weight == 0
    assert generated.metadata == {"evidence_classification": "disabled-placeholder"}
    assert not plugin.verify_proof(SERVICE_HASH, DELIVERY_HASH, b"\x01" * 4096)


def test_placeholder_is_excluded_from_automatic_discovery():
    assert all(
        plugin.proof_type() != ZKMLProofPlugin.PROOF_TYPE_ID
        for plugin in discover_plugins()
    )


def test_sdk_rejects_manually_injected_zk_proof_before_submission():
    client = TrustAggregatorClient.__new__(TrustAggregatorClient)
    fabricated = ProofResult(
        valid=True,
        proof_type=ZKMLProofPlugin.PROOF_TYPE_ID,
        proof_data=b"\x01" * 256,
        trust_weight=2000,
        metadata={"evidence_classification": "live-provider"},
    )

    with pytest.raises(LiveModeSafetyError, match="ZKML"):
        client.submit_plugin_bundle({ZKMLProofPlugin.PROOF_TYPE_ID: fabricated})


def test_standard_deployment_script_does_not_enable_zkml():
    deploy_script = (
        Path(__file__).resolve().parents[2]
        / "contracts"
        / "script"
        / "DeployPlugins.s.sol"
    ).read_text()
    assert "ZKMLProofPlugin" not in deploy_script
    assert "zkmlPlugin" not in deploy_script
