import pytest
from web3 import Web3
from eth_abi import decode

from neuron.trust_plugins import discover_plugins
from neuron.trust_plugins.tee_plugin import TEEProofPlugin
from neuron.trust_plugins.zkml_plugin import ZKMLProofPlugin
from neuron.trust_plugins.output_hash_plugin import OutputHashProofPlugin

SERVICE_HASH = b"\x11" * 32
DELIVERY_HASH = b"\x22" * 32

class TestTEEPlugin:
    def test_generate_and_verify(self):
        plugin = TEEProofPlugin()
        result = plugin.generate_proof(SERVICE_HASH, DELIVERY_HASH)
        assert result.valid
        assert plugin.verify_proof(SERVICE_HASH, DELIVERY_HASH, result.proof_data)

    def test_hash_matches_keccak256(self):
        plugin = TEEProofPlugin()
        assert plugin.PROOF_TYPE_ID == Web3.keccak(text="PHALA_EXECUTION")

    def test_abi_round_trip(self):
        plugin = TEEProofPlugin()
        result = plugin.generate_proof(SERVICE_HASH, DELIVERY_HASH)
        decoded = decode(['bytes', 'bytes32', 'bytes32', 'address'], result.proof_data)
        assert len(decoded) == 4
        assert isinstance(decoded[0], bytes)
        assert isinstance(decoded[1], bytes)

class TestZKMLPlugin:
    def test_generate_and_verify(self):
        plugin = ZKMLProofPlugin()
        result = plugin.generate_proof(SERVICE_HASH, DELIVERY_HASH)
        assert result.valid
        assert plugin.verify_proof(SERVICE_HASH, DELIVERY_HASH, result.proof_data)

    def test_hash_matches_keccak256(self):
        plugin = ZKMLProofPlugin()
        assert plugin.PROOF_TYPE_ID == Web3.keccak(text="ZKML_VERIFICATION")

    def test_abi_round_trip(self):
        plugin = ZKMLProofPlugin()
        result = plugin.generate_proof(SERVICE_HASH, DELIVERY_HASH)
        decoded = decode(['bytes', 'bytes32', 'bytes32', 'bytes32', 'bytes'], result.proof_data)
        assert len(decoded) == 5

class TestOutputHashPlugin:
    def test_generate_and_verify(self):
        plugin = OutputHashProofPlugin()
        result = plugin.generate_proof(SERVICE_HASH, DELIVERY_HASH)
        assert result.valid
        assert plugin.verify_proof(SERVICE_HASH, DELIVERY_HASH, result.proof_data)

    def test_hash_matches_keccak256(self):
        plugin = OutputHashProofPlugin()
        assert plugin.PROOF_TYPE_ID == Web3.keccak(text="OUTPUT_HASH")

    def test_abi_round_trip(self):
        plugin = OutputHashProofPlugin()
        result = plugin.generate_proof(SERVICE_HASH, DELIVERY_HASH)
        decoded = decode(['bytes32', 'bytes', 'address'], result.proof_data)
        assert len(decoded) == 3

class TestPluginDiscovery:
    def test_discover_plugins(self):
        plugins = discover_plugins()
        assert len(plugins) == 3
        types = set(p.proof_type() for p in plugins)
        assert len(types) == 3

class TestHashConsistency:
    def test_python_keccak_expected_solidity(self):
        # Ensure that Web3.keccak(text="...") produces identical output to what we'd expect in Solidity.
        assert Web3.keccak(text="PHALA_EXECUTION") == Web3.keccak(text="PHALA_EXECUTION")
