"""
VAMS Neuron - Trust Aggregator Client (v2 — Plugin Architecture)
================================================================
Collection interface for locally discovered proof plugins. Provider evidence
requires its own authentic verification; collection does not submit a transaction
or query an on-chain plugin registry. Both unbound submission methods are
unavailable pending an authenticated action/root-bound backend and finality receipt.
Legacy research/TEE/identity fixtures are restricted to non-live runtimes.
"""

from typing import Dict, List, Any, Optional
from enum import IntEnum
from web3 import Web3

# Import plugin system
from ..trust_plugins import discover_plugins
from ..trust_plugins.tee_plugin import BaseProofPlugin, ProofResult, TEEProofPlugin
from ..trust_plugins.zkml_plugin import ZKMLProofPlugin
from ..runtime_safety import LiveModeSafetyError, load_runtime_policy

# Legacy imports preserved for backward compatibility
from .phala_tee import PhalaTEE
from .parallel_web import ParallelWebClient


# =============================================================
#   LEGACY — Preserved for backward compatibility
# =============================================================

class VAMSProofType(IntEnum):
    """Legacy Decagon proof types (kept for backward compat)."""
    ERC8004_IDENTITY = 0
    COINBASE_WALLET = 1
    POLYGON_ID = 2
    PARALLEL_RESEARCH = 3
    PHALA_EXECUTION = 4
    SXT_SQL_PROOF = 5
    MCP_CONNECTION = 6
    SPECTRAL_CREDIT = 7
    AUTONOLAS_CONSENSUS = 8
    WORLD_ID_HUMAN = 9


# =============================================================
#   PLUGIN-AWARE CLIENT (v2)
# =============================================================

class TrustAggregatorClient:
    """
    Collect from proof plugins and expose non-live legacy fixtures.

    Submission is unavailable. Construction does not load an ambient VAMS signer.
    """
    
    def __init__(self, rpc_url: str, contract_address: str):
        self.rpc_url = rpc_url
        self.contract_address = contract_address
        
        # OFC08: Standard Web3 Initialization
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        # Collection needs no signing material. Unbound submission is unavailable;
        # a future action-authorized signer must use a separate explicit boundary.
        self.private_key = None
        self.signer = None
        self.account = None
        
        # Legacy providers
        self.phala = PhalaTEE()
        self.parallel = ParallelWebClient()
        
        # Plugin system
        self.plugins: Dict[bytes, BaseProofPlugin] = {}
        self._discover_plugins()

    def _discover_plugins(self):
        """Auto-discover available proof plugins."""
        for plugin in discover_plugins():
            self.plugins[plugin.proof_type()] = plugin
            print(f"  [Plugin] Registered: {plugin.name()} "
                  f"(weight: {plugin.trust_weight()} bps)")

    def list_registered_plugins(self) -> List[Dict[str, Any]]:
        """List all registered proof plugins with their metadata."""
        return [
            {
                "name": plugin.name(),
                "proof_type": plugin.proof_type().hex(),
                "trust_weight": plugin.trust_weight(),
                "trust_weight_pct": f"{plugin.trust_weight() / 100:.1f}%",
            }
            for plugin in self.plugins.values()
        ]

    def collect_plugin_proofs(
        self, 
        service_hash: bytes, 
        delivery_hash: bytes,
        **kwargs,
    ) -> Dict[bytes, ProofResult]:
        """
        Collect proofs from all available plugins.
        
        Returns a dict mapping proof_type -> ProofResult for each
        plugin that successfully generated a proof.
        """
        proofs = {}
        
        print("[TrustAggregator v2] Collecting plugin proofs...")
        
        for proof_type_id, plugin in self.plugins.items():
            try:
                result = plugin.generate_proof(
                    service_hash=service_hash,
                    delivery_hash=delivery_hash,
                    **kwargs,
                )
                if result.valid:
                    proofs[proof_type_id] = result
                    print(f"  [+] {plugin.name()}: Generated "
                          f"(weight: {result.trust_weight} bps)")
                else:
                    print(f"  [-] {plugin.name()}: Invalid proof generated")
            except Exception:
                # Provider exceptions and callbacks can contain private data.
                # Failure reporting must not invoke another plugin callback.
                print("  [-] Proof plugin failed")

        return proofs

    def submit_plugin_bundle(self, proofs: Dict[bytes, ProofResult]):
        """
        Reject plugin submission until a verified transaction backend exists.
        """
        if type(proofs) is not dict:
            raise LiveModeSafetyError(
                "TrustAggregatorClient plugin submission is unavailable; no transaction was submitted"
            )

        if ZKMLProofPlugin.PROOF_TYPE_ID in proofs:
            raise LiveModeSafetyError(
                "TrustAggregatorClient rejects ZKML proofs until an approved verifier is integrated"
            )

        tee_result = proofs.get(TEEProofPlugin.PROOF_TYPE_ID)
        if tee_result is not None:
            if type(tee_result) is not ProofResult:
                raise LiveModeSafetyError(
                    "TrustAggregatorClient rejects malformed TEE evidence"
                )
            metadata = tee_result.metadata
            classification = (
                metadata.get("evidence_classification")
                if type(metadata) is dict
                else None
            )
            if type(classification) is not str or classification != "live-provider":
                raise LiveModeSafetyError(
                    "TrustAggregatorClient rejects non-authoritative TEE evidence"
                )

        raise LiveModeSafetyError(
            "TrustAggregatorClient plugin submission is unavailable; no transaction was submitted"
        )

    # =============================================================
    #   LEGACY — Preserved for backward compatibility
    # =============================================================
        
    def collect_available_proofs(self) -> Dict[int, bytes]:
        """
        LEGACY: Return local-only fixtures; never use as authoritative evidence.
        Use collect_plugin_proofs() for the separate plugin interface.
        """
        load_runtime_policy().authorize_component_mock(
            "TrustAggregatorClient legacy proof fixtures", True
        )

        proofs = {}
        
        print("[TrustAggregator] Collecting non-authoritative local legacy fixtures...")
        
        try:
            results = self.parallel.search("VAMS heartbeat check")
            proof = self.parallel.generate_proof_of_research(results)
            proofs[VAMSProofType.PARALLEL_RESEARCH] = proof
            print("  [+] Local research fixture collected")
        except Exception as e:
            print(f"  [-] Parallel Research: Failed ({e})")

        try:
            quote = b"mock_sgx_quote" 
            proofs[VAMSProofType.PHALA_EXECUTION] = quote
            print("  [+] Local SGX placeholder collected")
        except Exception as e:
            print(f"  [-] Phala Execution: Failed ({e})")
            
        proofs[VAMSProofType.ERC8004_IDENTITY] = b"mock_erc721_ownership"
        print("  [+] Local identity placeholder collected")
        
        return proofs
    
    def submit_bundle(self, proofs: Dict[int, bytes]):
        """
        Reject legacy submission until a verified transaction backend exists.
        """
        raise LiveModeSafetyError(
            "TrustAggregatorClient legacy submission is unavailable; no transaction was submitted"
        )


if __name__ == "__main__":
    import hashlib
    
    client = TrustAggregatorClient("http://localhost:8545", "0x...")
    
    # Show registered plugins
    print("\nRegistered Plugins:")
    for p in client.list_registered_plugins():
        print(f"  {p['name']}: {p['trust_weight_pct']}")
    
    # Collect and submit plugin proofs
    service_hash = hashlib.sha256(b"test-service-request").digest()
    delivery_hash = hashlib.sha256(b"test-service-response").digest()
    
    proofs = client.collect_plugin_proofs(service_hash, delivery_hash)
    client.submit_plugin_bundle(proofs)
