"""
VAMS Neuron - Service Delivery Proofs (x402)
============================================
Cryptographic proofs of service delivery for atomic payments.
Matches Architecture Section 13.3.

Proof Types:
1. Hash Preimage (Simple logic tasks)
2. TEE Attestation (Private compute)
3. ZK-ML Verification (Model inference)
"""

import hashlib
import time
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Union

class ProofType(Enum):
    HASH_PREIMAGE = "hash_preimage"
    TEE_ATTESTATION = "tee_attestation"
    ZK_SNARK = "zk_snark"

@dataclass
class ServiceDeliveryProof:
    """Base class for all delivery proofs."""
    proof_type: ProofType
    service_id: str
    consumer: str
    provider: str
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.proof_type.value,
            "service_id": self.service_id,
            "consumer": self.consumer,
            "provider": self.provider,
            "timestamp": self.timestamp
        }
    
    def verify(self, expected_commitment: str) -> bool:
        """Verify proof against on-chain commitment."""
        raise NotImplementedError

@dataclass
class HashPreimageProof(ServiceDeliveryProof):
    """
    Simple proof: Provider reveals preimage `p` such that H(p) = commitment.
    Used for: Simple logic tasks, data retrieval.
    """
    preimage: str = ""
    
    def __post_init__(self):
        if self.proof_type != ProofType.HASH_PREIMAGE:
            self.proof_type = ProofType.HASH_PREIMAGE

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["preimage"] = self.preimage
        return data

    def verify(self, expected_commitment: str) -> bool:
        """
        Verify that SHA256(preimage) matches commitment.
        Commitment format: "sha256:0x..."
        """
        if not self.preimage:
            return False
            
        algo, target_hash = expected_commitment.split(":")
        if algo != "sha256":
            return False
            
        hashed = hashlib.sha256(self.preimage.encode()).hexdigest()
        return f"0x{hashed}" == target_hash or hashed == target_hash.replace("0x", "")

@dataclass
class TEEAttestationProof(ServiceDeliveryProof):
    """
    TEE Proof: Signed quote from SGX/Nitro enclave.
    Used for: Private compute, model inference.
    """
    quote: str = ""           # Base64 encoded quote
    signature: str = ""       # Enclave signature
    measurement: str = ""     # MRENCLAVE / PCR0
    
    def __post_init__(self):
        if self.proof_type != ProofType.TEE_ATTESTATION:
            self.proof_type = ProofType.TEE_ATTESTATION

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "quote": self.quote,
            "signature": self.signature,
            "measurement": self.measurement
        })
        return data

    def verify(self, expected_commitment: str) -> bool:
        """
        Verify TEE quote against expected measurement (PCR0/MRENCLAVE).
        Commitment format: "sgx:mrenclave" or "nitro:pcr0"
        """
        # In a real implementation, this would verify the Intel/AWS signature chain.
        # For simulation/soft-verification:
        platform, expected_measurement = expected_commitment.split(":")
        return self.measurement.lower() == expected_measurement.lower()

@dataclass
class ZKMLProof(ServiceDeliveryProof):
    """
    ZK-ML Proof: SNARK proving model inference execution.
    Used for: Verifiable inference without TEE.
    """
    snark_proof: str = ""     # Serialized proof (e.g. Groth16)
    public_inputs: str = ""   # Model hash, input hash, output hash
    
    def __post_init__(self):
        if self.proof_type != ProofType.ZK_SNARK:
            self.proof_type = ProofType.ZK_SNARK

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "snark_proof": self.snark_proof,
            "public_inputs": self.public_inputs
        })
        return data

    def verify(self, expected_commitment: str) -> bool:
        """
        Verify ZK proof. 
        Commitment format: "zk:verifier_address" or "zk:model_hash"
        """
        # Real verification requires running a verifier (e.g. snarkjs or py-binding)
        # For now, we assume if proof exists it's valid (stub)
        return len(self.snark_proof) > 0

def create_proof(
    proof_type: str, 
    service_id: str, 
    consumer: str, 
    provider: str, 
    payload: Dict[str, Any]
) -> ServiceDeliveryProof:
    """Factory function to create appropriate proof object."""
    
    ptype = ProofType(proof_type)
    
    if ptype == ProofType.HASH_PREIMAGE:
        return HashPreimageProof(
            proof_type=ptype,
            service_id=service_id,
            consumer=consumer,
            provider=provider,
            preimage=payload.get("preimage", "")
        )
    elif ptype == ProofType.TEE_ATTESTATION:
        return TEEAttestationProof(
            proof_type=ptype,
            service_id=service_id,
            consumer=consumer,
            provider=provider,
            quote=payload.get("quote", ""),
            signature=payload.get("signature", ""),
            measurement=payload.get("measurement", "")
        )
    elif ptype == ProofType.ZK_SNARK:
        return ZKMLProof(
            proof_type=ptype,
            service_id=service_id,
            consumer=consumer,
            provider=provider,
            snark_proof=payload.get("proof", ""),
            public_inputs=payload.get("inputs", "")
        )
    else:
        raise ValueError(f"Unknown proof type: {proof_type}")
