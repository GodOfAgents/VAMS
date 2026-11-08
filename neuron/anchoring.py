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
import os
import time
import json
from dataclasses import dataclass
from typing import List, Dict, Any, Mapping, Optional

from neuron.runtime_safety import (
    ImmutableRuntimeConfiguration,
    LiveModeSafetyError,
    RuntimePolicy,
    load_runtime_policy,
    resolve_component_mock_mode,
)


ANCHOR_MOCK_VARIABLE = "ANCHOR_MOCK_MODE"


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


class L1StateAnchor(ImmutableRuntimeConfiguration):
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

    _immutable_runtime_fields = frozenset({"mock_mode", "runtime_policy"})

    def __init__(
        self,
        mock_mode: Optional[bool] = None,
        *,
        environ: Optional[Mapping[str, str]] = None,
        policy: Optional[RuntimePolicy] = None,
    ):
        source = os.environ if environ is None else environ
        self.runtime_policy = policy or load_runtime_policy(source)
        self.mock_mode = resolve_component_mock_mode(
            "L1StateAnchor",
            ANCHOR_MOCK_VARIABLE,
            mock_mode,
            policy=self.runtime_policy,
            environ=source,
        )
        if self.runtime_policy.is_live:
            raise LiveModeSafetyError(
                "L1StateAnchor live execution is disabled until transaction "
                "confirmation and exact on-chain read-back are implemented"
            )
        if not self.mock_mode:
            raise LiveModeSafetyError(
                "L1StateAnchor has no authoritative non-simulated implementation"
            )
        self._anchor_count = 0
        self._last_block = self.BASE_BLOCK_NUMBER
        self._freeze_runtime_configuration()

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

        Produce an explicitly requested non-authoritative demo receipt.
        """
        self._anchor_count += 1

        self._last_block += 1
        block_number = self._last_block
        tx_data = f"{merkle_root}:{self._anchor_count}:{time.time()}"
        tx_hash_val = hashlib.sha256(tx_data.encode("utf-8")).hexdigest()
        tx_hash = f"simulated:sha256:{tx_hash_val}"
        time.sleep(0.1)

        return AnchorReceipt(
            merkle_root=merkle_root,
            tx_hash=tx_hash,
            block_number=block_number,
            timestamp=time.time(),
            checkpoints_included=checkpoints_count,
            simulated=True
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


def get_anchor(
    mock_mode: Optional[bool] = None,
    *,
    environ: Optional[Mapping[str, str]] = None,
    policy: Optional[RuntimePolicy] = None,
) -> L1StateAnchor:
    """Construct an anchor under the caller's immutable runtime policy."""

    return L1StateAnchor(mock_mode=mock_mode, environ=environ, policy=policy)
