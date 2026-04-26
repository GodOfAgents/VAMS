"""
VAMS Neuron - L1 State Anchoring (Layer 3: Logic)
==================================================
Simulates the "Merkle root on Ethereum" concept
for the Immortal Agent guarantee.

Pillar 2 of Immortal Agents: L1 STATE ANCHORING
- Every workflow state is hashed into a Merkle root
- Root is "submitted" to L1 (simulated in PoC+)
- This ensures state survives even VAMS L3 death
"""

import hashlib
import logging
import time
import json
import threading
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


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

    In production: Submits Merkle root to Ethereum/Polygon CDK.
    In PoC+: Generates hash and logs "anchor transaction"
    with fake tx hash.

    The Five Pillars of Immortal Agents:
    1. DURABLE EXECUTION (DBOS) - Checkpointing
    2. L1 STATE ANCHORING - This module
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

    def compute_merkle_root(
        self, checkpoint_data: List[Dict[str, Any]]
    ) -> str:
        """
        Compute proper Merkle root from checkpoint data.
        Uses SHA256 for tree construction.
        """
        if not checkpoint_data:
            return "0x" + "0" * 64

        # 1. Create leaf hashes
        leaves = []
        for cp in checkpoint_data:
            leaf_data = json.dumps(
                cp, sort_keys=True
            ).encode('utf-8')
            # SHA256 for now; switch to keccak256
            # for ETH compatibility in production.
            leaf_hash = hashlib.sha256(leaf_data).digest()
            leaves.append(leaf_hash)

        # 2. Build tree
        while len(leaves) > 1:
            next_level = []
            for i in range(0, len(leaves), 2):
                if i + 1 < len(leaves):
                    # Combine pair: H(a + b)
                    combined = leaves[i] + leaves[i + 1]
                else:
                    # Duplicate odd leaf (OpenZeppelin standard)
                    combined = leaves[i] + leaves[i]

                next_level.append(
                    hashlib.sha256(combined).digest()
                )
            leaves = next_level

        return f"0x{leaves[0].hex()}"

    def submit_anchor(
        self,
        merkle_root: str,
        checkpoints_count: int = 0
    ) -> AnchorReceipt:
        """
        Submit state anchor to L1.

        If Web3 client is configured, sends real transaction.
        Otherwise falls back to simulation.
        """
        self._anchor_count += 1

        tx_hash = ""
        block_number = self._last_block + 1
        simulated = True

        # Try real Web3 submission
        try:
            from neuron.eth_client.registration import (
                AgentRegistryClient,
            )
            client = AgentRegistryClient()
            if client.contract:
                root_bytes = bytes.fromhex(merkle_root[2:])
                agent_id = hashlib.sha256(b"agent").digest()

                tx_hash_str = client.submit_checkpoint(
                    root_bytes, agent_id
                )
                tx_hash = tx_hash_str
                block_number = client.w3.eth.block_number
                simulated = False
        except ImportError:
            pass  # Module not found or dependency missing
        except (ConnectionError, TimeoutError) as e:
            logger.warning(
                "Web3 submission failed (network): %s. "
                "Falling back to simulation.", e
            )
        except ValueError as e:
            logger.error(
                "Web3 submission failed (bad data): %s. "
                "Falling back to simulation.", e
            )
        except Exception:
            logger.exception(
                "Web3 submission failed unexpectedly. "
                "Falling back to simulation."
            )

        # Update internal block tracker
        if simulated:
            self._last_block += 1
            block_number = self._last_block

            # Generate simulated tx hash
            tx_data = (
                f"{merkle_root}:{self._anchor_count}"
                f":{time.time()}"
            )
            tx_hash_val = hashlib.sha256(
                tx_data.encode('utf-8')
            ).hexdigest()
            tx_hash = f"0x{tx_hash_val}"

            # Simulate brief delay (L1 submission)
            time.sleep(0.1)
        else:
            self._last_block = block_number

        return AnchorReceipt(
            merkle_root=merkle_root,
            tx_hash=tx_hash,
            block_number=block_number,
            timestamp=time.time(),
            checkpoints_included=checkpoints_count,
            simulated=simulated
        )

    def verify_anchor(
        self,
        receipt: AnchorReceipt,
        checkpoint_data: List[Dict[str, Any]]
    ) -> bool:
        """
        Verify that checkpoints match the anchored
        Merkle root.
        """
        recomputed_root = self.compute_merkle_root(
            checkpoint_data
        )
        return recomputed_root == receipt.merkle_root

    def format_receipt(self, receipt: AnchorReceipt) -> str:
        """Format anchor receipt for display."""
        status = (
            "✓ REAL (Polygon)"
            if not receipt.simulated
            else "~ SIMULATED"
        )
        root_short = (
            f"{receipt.merkle_root[:18]}"
            f"...{receipt.merkle_root[-8:]}"
        )
        tx_short = (
            f"{receipt.tx_hash[:18]}"
            f"...{receipt.tx_hash[-8:]}"
        )
        return (
            "\n"
            "┌──────────────────────────────────"
            "───────────────────────────────────┐\n"
            "│  L1 STATE ANCHOR RECEIPT"
            "                                     │\n"
            "├──────────────────────────────────"
            "───────────────────────────────────┤\n"
            f"│  Merkle Root:  {root_short}  │\n"
            f"│  Tx Hash:      {tx_short}  │\n"
            f"│  Block:        #{receipt.block_number:,}"
            "                               │\n"
            f"│  Status:       {status}"
            "                                   │\n"
            f"│  Checkpoints:  "
            f"{receipt.checkpoints_included}"
            " states anchored"
            "                          │\n"
            "└──────────────────────────────────"
            "───────────────────────────────────┘\n"
        )


# Thread-safe singleton
_anchor_instance: Optional[L1StateAnchor] = None
_anchor_lock = threading.Lock()


def get_anchor() -> L1StateAnchor:
    """Get the singleton L1StateAnchor instance (thread-safe)."""
    global _anchor_instance
    if _anchor_instance is None:
        # NOTE: GIL-dependent double-check pattern
        # Safe in CPython, but requires review if porting to PyPy or Cython
        with _anchor_lock:
            if _anchor_instance is None:
                _anchor_instance = L1StateAnchor()
    return _anchor_instance
