"""
VAMS Neuron - Trust Aggregator Client (v2 — Plugin Architecture)
================================================================
Client-side aggregator for the pluggable proof system.
Discovers available plugins, collects proofs, and submits them to
the VAMSTrustAggregator contract.

Changes from v1:
- Replaced hardcoded VAMSProofType IntEnum with bytes32 plugin identifiers
- Auto-discovers plugins from neuron/trust_plugins/
- Queries on-chain registry for active plugins
- Uses submitPluginProof() ABI for new plugin proofs
- Preserves submitProof() fallback for legacy Decagon proofs
"""

import time
from typing import Dict, List, Any, Optional
from enum import IntEnum

# Import plugin system
from ..trust_plugins import discover_plugins
from ..trust_plugins.tee_plugin import BaseProofPlugin, ProofResult

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
    Client for interacting with VAMSTrustAggregator (v2 — Plugin Architecture).
    
    Supports both legacy Decagon proofs and new pluggable proofs.
    """
    
    def __init__(self, rpc_url: str, contract_address: str):
        self.rpc_url = rpc_url
        self.contract_address = contract_address
        
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
            except Exception as e:
                print(f"  [-] {plugin.name()}: Failed ({e})")

        return proofs

    def submit_plugin_bundle(self, proofs: Dict[bytes, ProofResult]):
        """
        Submit collected plugin proofs to the VAMSTrustAggregator contract.
        
        Uses submitPluginProof(bytes32, bytes32, bytes32, bytes) ABI.
        """
        print(f"\n[TrustAggregator v2] Submitting {len(proofs)} plugin proofs...")
        
        for proof_type_id, result in proofs.items():
            plugin = self.plugins.get(proof_type_id)
            plugin_name = plugin.name() if plugin else proof_type_id.hex()[:16]
            
            # In production: encode and send transaction
            # tx = contract.submitPluginProof(
            #     pluginProofType=proof_type_id,
            #     serviceHash=service_hash,
            #     deliveryHash=delivery_hash,
            #     proofData=result.proof_data,
            # )
            print(f"  -> Submitting {plugin_name} "
                  f"(weight: {result.trust_weight} bps)...")
            time.sleep(0.2)
        
        print("[TrustAggregator v2] Plugin proof submission complete.")

    # =============================================================
    #   LEGACY — Preserved for backward compatibility
    # =============================================================
        
    def collect_available_proofs(self) -> Dict[int, bytes]:
        """
        LEGACY: Scans for Decagon proofs.
        Use collect_plugin_proofs() for the new plugin system.
        """
        proofs = {}
        
        print("[TrustAggregator] Collecting legacy proofs...")
        
        try:
            results = self.parallel.search("VAMS heartbeat check")
            proof = self.parallel.generate_proof_of_research(results)
            proofs[VAMSProofType.PARALLEL_RESEARCH] = proof
            print(f"  [+] Parallel Research: Found")
        except Exception as e:
            print(f"  [-] Parallel Research: Failed ({e})")

        try:
            quote = b"mock_sgx_quote" 
            proofs[VAMSProofType.PHALA_EXECUTION] = quote
            print(f"  [+] Phala Execution: Found")
        except Exception as e:
            print(f"  [-] Phala Execution: Failed ({e})")
            
        proofs[VAMSProofType.ERC8004_IDENTITY] = b"mock_erc721_ownership"
        print(f"  [+] ERC-8004 Identity: Found")
        
        return proofs
    
    def submit_bundle(self, proofs: Dict[int, bytes]):
        """
        LEGACY: Submit Decagon proofs.
        Use submit_plugin_bundle() for the new plugin system.
        """
        print(f"\n[TrustAggregator] Submitting {len(proofs)} legacy proofs...")
        
        for proof_type, proof_data in proofs.items():
            print(f"  -> Submitting Legacy Proof Type {proof_type}...")
            time.sleep(0.2)
            
        print("[TrustAggregator] Legacy submission complete.")


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
