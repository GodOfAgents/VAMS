"""Disabled placeholder for future ZKML proof integration.

No ZK prover/verifier relation is selected for VAMS yet. This class remains
importable for compatibility, but it cannot generate or verify authoritative
proofs and is excluded from automatic plugin discovery.
"""

from typing import Any, Optional

from web3 import Web3

from .tee_plugin import BaseProofPlugin, ProofResult


class ZKMLProofPlugin(BaseProofPlugin):
    """Fail-closed placeholder; a real verifier requires a reviewed M4 design."""

    PROOF_TYPE_ID = Web3.keccak(text="ZKML_VERIFICATION")

    def __init__(self, verifier_endpoint: Optional[str] = None):
        # Retained for constructor compatibility. No endpoint is trusted here.
        self.verifier_endpoint = verifier_endpoint

    def proof_type(self) -> bytes:
        return self.PROOF_TYPE_ID

    def name(self) -> str:
        return "ZKML Inference Proof (disabled)"

    def trust_weight(self) -> int:
        return 0

    def generate_proof(
        self,
        service_hash: bytes,
        delivery_hash: bytes,
        **kwargs: Any,
    ) -> ProofResult:
        """Return an explicit non-authoritative result until a backend is approved."""
        return ProofResult(
            valid=False,
            proof_type=self.PROOF_TYPE_ID,
            proof_data=b"",
            trust_weight=self.trust_weight(),
            metadata={"evidence_classification": "disabled-placeholder"},
        )

    def verify_proof(
        self,
        service_hash: bytes,
        delivery_hash: bytes,
        proof_data: bytes,
    ) -> bool:
        """Never treat placeholder bytes as a cryptographic proof."""
        return False
