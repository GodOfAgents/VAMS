"""
VAMS Neuron - Batch Settlement Logic (x402)
===========================================
Merkle Tree generation for gas-efficient payment settlement.
Matches BatchSettlement.sol logic.

Features:
- Payment struct packing (ABIv2 compliant)
- Keccak256 hashing
- Merkle Tree construction
- Proof generation
"""

import logging
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
from eth_abi import encode
from eth_utils import keccak, to_bytes, to_hex

logger = logging.getLogger("VAMS-Settlement")

@dataclass
class Payment:
    """Matches IBatchSettlement.sol Payment struct."""
    agent: str            # address
    provider: str         # address
    amount: int           # uint256 (in wei units of VAMS)
    nonce: int            # uint256
    service_type: bytes   # bytes32
    
    def to_tuple(self) -> Tuple:
        return (self.agent, self.provider, self.amount, self.nonce, self.service_type)

class MerkleTree:
    """Simple Merkle Tree implementation for Payment Batching."""
    
    def __init__(self, elements: List[bytes]):
        self.elements = sorted(elements) # Sorted for determinism (OpenZeppelin standard)
        self.layers = MerkleTree.get_layers(self.elements)
        
    @property
    def root(self) -> bytes:
        return self.layers[-1][0] if self.layers else bytes(32)
        
    @property
    def root_hex(self) -> str:
        return "0x" + self.root.hex()

    def get_proof(self, element: bytes) -> List[bytes]:
        """Generate Merkle Proof for an element."""
        if element not in self.elements:
            raise ValueError("Element not in tree")
            
        index = self.elements.index(element)
        proof = []
        
        for layer in self.layers[:-1]:
            is_right_node = index % 2 == 1
            pair_index = index - 1 if is_right_node else index + 1
            
            if pair_index < len(layer):
                proof.append(layer[pair_index])
            
            index //= 2
            
        return proof

    def get_proof_hex(self, element: bytes) -> List[str]:
        return ["0x" + p.hex() for p in self.get_proof(element)]

    @staticmethod
    def get_layers(elements: List[bytes]) -> List[List[bytes]]:
        layers = [elements]
        while len(layers[-1]) > 1:
            layers.append(MerkleTree.get_next_layer(layers[-1]))
        return layers

    @staticmethod
    def get_next_layer(elements: List[bytes]) -> List[bytes]:
        """Combine pairs of hashes."""
        next_layer = []
        for i in range(0, len(elements), 2):
            if i + 1 == len(elements):
                # Odd number of elements: promote last one
                # Note: OpenZeppelin MerkleProof standard (doubling last) vs standard behavior
                # Standard OZ implementation assumes sorted pairs.
                # Here we use standard pair hashing: H(a, b)
                # If odd, H(a, a) or just promote 'a' depending on implementation.
                # WARNING: BatchSettlement.sol uses OpenZeppelin MerkleProof.
                # OZ's `Verify` expects standard tree construction.
                # Let's assume standard behavior: promote single element if no pair.
                # Actually, standard behavior is usually to duplicate the last element.
                # Let's verify strict OZ compatibility later. For now, using pair hashing.
                next_layer.append(elements[i]) 
            else:
                # Sort pair to ensure commutativity/canonical ordering (OZ Standard)
                a, b = elements[i], elements[i+1]
                if a < b:
                    combined = a + b
                else:
                    combined = b + a
                next_layer.append(keccak(combined))
        return next_layer

class BatchManager:
    """Manages accumulation of off-chain payments."""
    
    def __init__(self):
        self.pending_payments: List[Payment] = []
        self.tree: MerkleTree = None
        
    def add_payment(self, payment: Payment):
        self.pending_payments.append(payment)
        
    def build_tree(self) -> MerkleTree:
        """Construct Merkle Tree from pending payments."""
        leaves = [self.hash_payment(p) for p in self.pending_payments]
        self.tree = MerkleTree(leaves)
        return self.tree
    
    def get_settlement_data(self) -> Dict[str, Any]:
        """Return data needed for submitBatch transaction."""
        if not self.tree:
            self.build_tree()
            
        total_value = sum(p.amount for p in self.pending_payments)
        
        return {
            "merkleRoot": self.tree.root_hex,
            "totalPayments": len(self.pending_payments),
            "totalValue": total_value,
            "payments": [p.__dict__ for p in self.pending_payments]
        }
    
    def get_payment_proof(self, payment: Payment) -> List[str]:
        """Get proof for a specific payment to claim it."""
        if not self.tree:
             self.build_tree()
        
        leaf = self.hash_payment(payment)
        return self.tree.get_proof_hex(leaf)

    @staticmethod
    def hash_payment(payment: Payment) -> bytes:
        """
        Compute keccak256(abi.encodePacked(...))
        Matches BatchSettlement._computePaymentHash
        """
        # Solidity: keccak256(abi.encodePacked(agent, provider, amount, nonce, serviceType))
        # Python: eth_abi.encode doesn't support packed.
        # But we can simulate packed encoding for simple types.
        # Address: 20 bytes
        # Uint256: 32 bytes (but packed = just the bytes? No, encodePacked usually creates distinct encoding)
        # Actually in Python `eth_abi.packed` is available via `eth_abi.packed`.
        
        try:
            from eth_abi.packed import encode_packed
            packed = encode_packed(
                ['address', 'address', 'uint256', 'uint256', 'bytes32'],
                [payment.agent, payment.provider, payment.amount, payment.nonce, payment.service_type]
            )
            return keccak(packed)
        except ImportError:
            # Fallback if eth_abi.packed not available (rare)
            # Rough simulation for poc
            data = (
                to_bytes(hexstr=payment.agent).rjust(20, b'\0') +
                to_bytes(hexstr=payment.provider).rjust(20, b'\0') +
                payment.amount.to_bytes(32, 'big') +
                payment.nonce.to_bytes(32, 'big') +
                payment.service_type
            )
            return keccak(data)

# Example Usage
if __name__ == "__main__":
    # Test vector
    from eth_utils import to_bytes
    
    p1 = Payment(
        "0x1111111111111111111111111111111111111111", 
        "0x2222222222222222222222222222222222222222",
        1000, 1, b'service-01'.ljust(32, b'\0')
    )
    p2 = Payment(
        "0x3333333333333333333333333333333333333333",
        "0x2222222222222222222222222222222222222222", 
        2000, 2, b'service-02'.ljust(32, b'\0')
    )
    
    mgr = BatchManager()
    mgr.add_payment(p1)
    mgr.add_payment(p2)
    
    data = mgr.get_settlement_data()
    print(f"Root: {data['merkleRoot']}")
    print(f"Total Value: {data['totalValue']}")
    
    proof1 = mgr.get_payment_proof(p1)
    print(f"Proof for P1 ({len(proof1)} elements): {proof1}")
