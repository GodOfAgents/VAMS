"""
VAMS Neuron - L1 State Anchoring (Layer 3: Logic)
==================================================
Simulates the "Merkle root on Ethereum" concept for the Immortal Agent guarantee.

Pillar 2 of Immortal Agents: L1 STATE ANCHORING
- Every workflow state is hashed into a Merkle root
- Root is "submitted" to L1 (simulated in PoC+)
- This ensures state survives even VAMS L3 death
"""

import hashlib
import time
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class AnchorReceipt:
    """Receipt from L1 state anchor submission."""
    merkle_root: str
    tx_hash: str
    block_number: int
    timestamp: float
    checkpoints_included: int
    simulated: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "merkle_root": self.merkle_root,
            "tx_hash": self.tx_hash,
            "block_number": self.block_number,
            "timestamp": self.timestamp,
            "checkpoints_included": self.checkpoints_included,
            "simulated": self.simulated
        }


class L1StateAnchor:
    """
    Simulates L1 State Anchoring (Pillar 2 of Immortal Agents).
    
    In production: Submits Merkle root of workflow state to Ethereum/Polygon CDK.
    In PoC+: Generates hash and logs "anchor transaction" with fake tx hash.
    
    The Five Pillars of Immortal Agents (from ARCHITECTURE_v0-3-0.md):
    1. DURABLE EXECUTION (DBOS) - Checkpointing ✓
    2. L1 STATE ANCHORING - This module ✓
    3. TRANSPARENT FAILOVER - SDK auto-reroutes
    4. REQUEST GUARANTEE - Queue with retry
    5. PERMANENT MEMORY (Arweave) - Future implementation
    """
    
    # Simulated L1 parameters
    SIMULATED_CHAIN = "Polygon CDK (simulated)"
    SIMULATED_BLOCK_TIME = 2  # seconds
    BASE_BLOCK_NUMBER = 19_283_102
    
    def __init__(self):
        self._anchor_count = 0
        self._last_block = self.BASE_BLOCK_NUMBER
    

    def compute_merkle_root(self, checkpoint_data: List[Dict[str, Any]]) -> str:
        """
        Compute proper Merkle root from checkpoint data.
        Uses SHA256 (or Keccak if using web3) for tree construction.
        """
        if not checkpoint_data:
            return "0x" + "0" * 64
        
        # 1. Create leaf hashes
        leaves = []
        for cp in checkpoint_data:
            leaf_data = json.dumps(cp, sort_keys=True).encode('utf-8')
            # Using keccak256 would be better for ETH compatibility, but sticking to 
            # consistent hashing for now (sha256). For real prod, switch to keccak.
            leaf_hash = hashlib.sha256(leaf_data).digest()
            leaves.append(leaf_hash)
            
        if not leaves:
            return "0x" + "0" * 64

        # 2. Build tree
        while len(leaves) > 1:
            next_level = []
            for i in range(0, len(leaves), 2):
                if i + 1 < len(leaves):
                    # Combine pair: H(a + b)
                    combined = leaves[i] + leaves[i+1]
                else:
                    # Promote single leaf (or duplicate)
                    # OpenZeppelin standard usually duplicates for balanced proof
                    combined = leaves[i] + leaves[i]
                
                next_level.append(hashlib.sha256(combined).digest())
            leaves = next_level
            
        return f"0x{leaves[0].hex()}"
    
    def submit_anchor(self, merkle_root: str, checkpoints_count: int = 0) -> AnchorReceipt:
        """
        Submit state anchor to L1.
        
        If Web3 client is configured, sends real transaction.
        Otherwise falls back to simulation.
        """
        self._anchor_count += 1
        self._last_block += 1
        
        tx_hash = ""
        block_number = self._last_block
        simulated = True
        
        # Try real Web3 submission
        try:
            from neuron.web3.registration import AgentRegistryClient
            client = AgentRegistryClient()
            if client.contract:
                # Convert hex string "0x..." to bytes
                root_bytes = bytes.fromhex(merkle_root[2:])
                # Agent ID would be configured in real node, using dummy for now or derived
                # For demo, we just use a hash of "agent"
                agent_id = hashlib.sha256(b"agent").digest() 
                
                tx_hash_str = client.submit_checkpoint(root_bytes, agent_id)
                tx_hash = tx_hash_str
                block_number = client.w3.eth.block_number
                simulated = False
        except ImportError:
            pass # Module not found or dependency missing
        except Exception as e:
            print(f"Warning: Web3 submission failed: {e}. Falling back to simulation.")
            
        if simulated:
            # Generate simulated tx hash
            tx_data = f"{merkle_root}:{self._anchor_count}:{time.time()}"
            tx_hash_val = hashlib.sha256(tx_data.encode('utf-8')).hexdigest()
            tx_hash = f"0x{tx_hash_val}"
            
            # Simulate brief delay (L1 submission)
            time.sleep(0.1)
        
        return AnchorReceipt(
            merkle_root=merkle_root,
            tx_hash=tx_hash,
            block_number=block_number,
            timestamp=time.time(),
            checkpoints_included=checkpoints_count,
            simulated=simulated
        )
    
    def verify_anchor(self, receipt: AnchorReceipt, checkpoint_data: List[Dict[str, Any]]) -> bool:
        """
        Verify that checkpoints match the anchored Merkle root.
        """
        recomputed_root = self.compute_merkle_root(checkpoint_data)
        return recomputed_root == receipt.merkle_root
    
    def format_receipt(self, receipt: AnchorReceipt) -> str:
        """Format anchor receipt for display."""
        status = "✓ REAL (Polygon)" if not receipt.simulated else "~ SIMULATED"
        return f"""
┌─────────────────────────────────────────────────────────────────────┐
│  L1 STATE ANCHOR RECEIPT                                             │
├─────────────────────────────────────────────────────────────────────┤
│  Merkle Root:  {receipt.merkle_root[:18]}...{receipt.merkle_root[-8:]}  │
│  Tx Hash:      {receipt.tx_hash[:18]}...{receipt.tx_hash[-8:]}  │
│  Block:        #{receipt.block_number:,}                               │
│  Status:       {status}                                   │
│  Checkpoints:  {receipt.checkpoints_included} states anchored                          │
└─────────────────────────────────────────────────────────────────────┘
"""


# Singleton instance for easy import
_anchor_instance: Optional[L1StateAnchor] = None

def get_anchor() -> L1StateAnchor:
    """Get the singleton L1StateAnchor instance."""
    global _anchor_instance
    if _anchor_instance is None:
        _anchor_instance = L1StateAnchor()
    return _anchor_instance
