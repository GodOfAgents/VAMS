"""
VAMS Neuron - MEV Protection Module
=====================================
Architecture Reference: ARCHITECTURE_v0-3-0.md Section 20.4.3

Multi-layered MEV protection:
1. Encrypted Mempool — Threshold encryption until block inclusion
2. Batch Auction Settlement — Uniform-price execution (no sandwiching)
3. Proposer-Builder Separation — Separate block building from proposing
4. Slashing Detection — Proven MEV extraction outside OFA = 25% slash

Note: This is a mock implementation for the Neuron client. Real threshold
encryption and proposer-builder separation require L3 consensus changes.
The mock allows the routing pipeline to work end-to-end.
"""

import hashlib
import time
import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum

logger = logging.getLogger("VAMS-MEV")

try:
    from neuron.config import MEV_BATCH_WINDOW_MS
except ImportError:
    try:
        from config import MEV_BATCH_WINDOW_MS
    except ImportError:
        MEV_BATCH_WINDOW_MS = 500


# =============================================================================
# DATA MODELS
# =============================================================================

class MEVThreatType(Enum):
    """Known MEV attack vectors."""
    FRONT_RUNNING = "front_running"
    SANDWICH = "sandwich"
    BACK_RUNNING = "back_running"
    JIT_LIQUIDITY = "jit_liquidity"
    TIME_BANDIT = "time_bandit"


class EncryptionStatus(Enum):
    """Transaction encryption lifecycle."""
    PLAINTEXT = "plaintext"
    ENCRYPTED = "encrypted"
    COMMITTED = "committed"        # In encrypted mempool
    DECRYPTED = "decrypted"        # Block included, now visible
    SETTLED = "settled"


@dataclass
class EncryptedTransaction:
    """A transaction protected by threshold encryption."""
    tx_id: str
    encrypted_payload: bytes       # Encrypted transaction data
    commitment_hash: str           # H(tx) for ordering proof
    target_block: int              # Decrypt at this block
    timestamp: float
    status: EncryptionStatus = EncryptionStatus.ENCRYPTED
    # Mock fields
    original_value_usd: float = 0.0
    submitter_id: str = ""


@dataclass
class BatchPayment:
    """A payment within a batch auction."""
    payment_id: str
    agent_id: str
    provider_id: str
    amount_vams: float
    service_hash: str              # H(delivered service)
    timestamp: float


@dataclass
class BatchResult:
    """Result of a batch auction settlement."""
    batch_id: str
    clearing_price: float          # Uniform price for all payments
    payments_settled: int
    total_volume_vams: float
    batch_window_ms: int
    timestamp: float
    mev_savings_estimate: float = 0.0  # Estimated MEV prevented


# =============================================================================
# ENCRYPTED MEMPOOL
# =============================================================================

class EncryptedMempool:
    """
    Threshold-encrypted transaction pool.

    Architecture Section 20.4.3:
        Transactions encrypted until block inclusion.
        Prevents front-running by hiding tx content from validators.

    In production: Uses threshold encryption with DKG (Distributed Key
    Generation) among L3 validators. The decryption key is only
    reconstructable after the block is committed.

    Current: Mock encryption using SHA-256 commitment scheme.
    """

    def __init__(self):
        self._pool: Dict[str, EncryptedTransaction] = {}
        self._block_counter = 0
        self._stats = {
            "submitted": 0,
            "committed": 0,
            "decrypted": 0,
            "mev_prevented": 0,
        }

    def submit_transaction(
        self,
        tx_data: bytes,
        value_usd: float = 0.0,
        submitter_id: str = "",
    ) -> EncryptedTransaction:
        """
        Encrypt and submit a transaction to the mempool.
        The transaction content is hidden until block inclusion.
        """
        self._block_counter += 1
        target_block = self._block_counter + 1

        # Commitment hash: H(tx_data) — proves we committed without revealing
        commitment = hashlib.sha256(tx_data).hexdigest()

        # Robust Mock encryption: AES-256-GCM with key derived from target block
        # Production: threshold encryption with validator DKG
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        key_material = hashlib.sha256(f"threshold_key_{target_block}".encode()).digest()
        aesgcm = AESGCM(key_material)
        nonce = os.urandom(12)
        encrypted = nonce + aesgcm.encrypt(nonce, tx_data, None)

        tx_id = f"etx_{commitment[:12]}_{target_block}"
        enc_tx = EncryptedTransaction(
            tx_id=tx_id,
            encrypted_payload=encrypted,
            commitment_hash=commitment,
            target_block=target_block,
            timestamp=time.time(),
            status=EncryptionStatus.COMMITTED,
            original_value_usd=value_usd,
            submitter_id=submitter_id,
        )

        self._pool[tx_id] = enc_tx
        self._stats["submitted"] += 1
        self._stats["committed"] += 1

        # Estimate MEV prevented (rough: 0.5% of value for high-value txs)
        if value_usd > 1000:
            self._stats["mev_prevented"] += value_usd * 0.005

        logger.debug(
            f"Encrypted tx {tx_id}: commitment={commitment[:12]}..., "
            f"target_block={target_block}"
        )

        return enc_tx

    def decrypt_block(self, block_number: int) -> List[EncryptedTransaction]:
        """
        Decrypt all transactions targeted at this block.
        Called after block is committed (too late for MEV).
        """
        decrypted = []
        for tx_id, tx in self._pool.items():
            if tx.target_block == block_number and tx.status == EncryptionStatus.COMMITTED:
                tx.status = EncryptionStatus.DECRYPTED
                self._stats["decrypted"] += 1
                decrypted.append(tx)

        if decrypted:
            logger.debug(
                f"Decrypted {len(decrypted)} txs at block {block_number}"
            )

        return decrypted

    def get_stats(self) -> dict:
        return {**self._stats, "pool_size": len(self._pool)}


# =============================================================================
# BATCH AUCTION SETTLER
# =============================================================================

class BatchAuctionSettler:
    """
    Uniform-price batch settlement for x402 payments.

    Architecture Section 20.4.3:
        All payments in batch execute at same price (no sandwiching).
        Clearing price = median of submitted bids.

    This prevents:
        - Sandwich attacks (no ordering advantage)
        - Front-running (uniform price removes information advantage)
        - JIT liquidity manipulation
    """

    def __init__(self, batch_window_ms: int = None):
        self.batch_window_ms = batch_window_ms or MEV_BATCH_WINDOW_MS
        self._current_batch: List[BatchPayment] = []
        self._batch_counter = 0
        self._stats = {
            "batches_settled": 0,
            "total_payments": 0,
            "total_volume_vams": 0.0,
            "total_mev_savings": 0.0,
        }

    def add_payment(self, payment: BatchPayment):
        """Add a payment to the current batch window."""
        self._current_batch.append(payment)

    def settle_batch(self) -> Optional[BatchResult]:
        """
        Settle all payments in the current batch at uniform price.
        Called at end of each batch window.
        """
        if not self._current_batch:
            return None

        self._batch_counter += 1
        batch = self._current_batch
        self._current_batch = []

        # Calculate uniform clearing price (median of amounts)
        amounts = sorted(p.amount_vams for p in batch)
        n = len(amounts)
        if n % 2 == 0:
            clearing_price = (amounts[n // 2 - 1] + amounts[n // 2]) / 2
        else:
            clearing_price = amounts[n // 2]

        total_volume = sum(p.amount_vams for p in batch)

        # Estimate MEV savings: difference between max and uniform price
        # represents the value that would have been extractable
        max_price = max(amounts)
        min_price = min(amounts)
        spread = max_price - min_price
        mev_savings = spread * len(batch) * 0.1  # 10% of spread per tx

        batch_id = f"batch_{self._batch_counter}_{int(time.time())}"

        result = BatchResult(
            batch_id=batch_id,
            clearing_price=clearing_price,
            payments_settled=len(batch),
            total_volume_vams=total_volume,
            batch_window_ms=self.batch_window_ms,
            timestamp=time.time(),
            mev_savings_estimate=mev_savings,
        )

        self._stats["batches_settled"] += 1
        self._stats["total_payments"] += len(batch)
        self._stats["total_volume_vams"] += total_volume
        self._stats["total_mev_savings"] += mev_savings

        logger.info(
            f"Batch {batch_id}: {len(batch)} payments at "
            f"{clearing_price:.4f} VAMS (saved ~{mev_savings:.4f} MEV)"
        )

        return result

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "pending_payments": len(self._current_batch),
            "batch_window_ms": self.batch_window_ms,
        }


# =============================================================================
# MEV PROTECTION ORCHESTRATOR
# =============================================================================

class MEVProtection:
    """
    Multi-layered MEV protection orchestrator.

    Architecture Section 20.4.3:
        1. Encrypted Mempool — Prevents front-running
        2. Batch Auctions — Prevents sandwiching
        3. Proposer-Builder Separation — Reduces validator MEV
        4. Slashing for MEV — 25% slash for proven extraction

    Mechanisms:
        | Mechanism              | Effectiveness       |
        |------------------------|---------------------|
        | Encrypted Mempool      | Prevents front-run  |
        | MEV-Share Auctions     | Eliminates Oracle   |
        | Proposer-Builder Sep   | Reduces validator   |
        | Slashing for MEV       | Economic punishment |
    """

    def __init__(self, batch_window_ms: int = None):
        self.mempool = EncryptedMempool()
        self.settler = BatchAuctionSettler(batch_window_ms)
        self._slashing_log: List[dict] = []

    async def submit_protected_transaction(
        self,
        tx_data: bytes,
        value_usd: float = 0.0,
        agent_id: str = "",
    ) -> EncryptedTransaction:
        """Submit a transaction with full MEV protection."""
        return self.mempool.submit_transaction(tx_data, value_usd, agent_id)

    def submit_protected_transaction_sync(
        self,
        tx_data: bytes,
        value_usd: float = 0.0,
        agent_id: str = "",
    ) -> EncryptedTransaction:
        """Synchronous version for non-async contexts."""
        return self.mempool.submit_transaction(tx_data, value_usd, agent_id)

    async def settle_x402_batch(
        self,
        payments: List[BatchPayment]
    ) -> Optional[BatchResult]:
        """Settle x402 payments as a batch at uniform price."""
        for p in payments:
            self.settler.add_payment(p)
        return self.settler.settle_batch()

    def settle_x402_batch_sync(
        self,
        payments: List[BatchPayment]
    ) -> Optional[BatchResult]:
        """Synchronous batch settlement."""
        for p in payments:
            self.settler.add_payment(p)
        return self.settler.settle_batch()

    def report_mev_extraction(
        self,
        tx_hash: str,
        extractor_id: str,
        evidence: str,
        estimated_profit: float,
    ) -> dict:
        """
        Report detected MEV extraction for slashing.
        Architecture: 25% slash for proven extraction outside OFA.
        """
        report = {
            "tx_hash": tx_hash,
            "extractor_id": extractor_id,
            "evidence": evidence,
            "estimated_profit": estimated_profit,
            "slash_amount": estimated_profit * 0.25,  # 25% slash
            "timestamp": time.time(),
            "status": "pending_review",
        }
        self._slashing_log.append(report)

        logger.warning(
            f"MEV extraction reported: {extractor_id} "
            f"profit={estimated_profit:.4f}, slash={report['slash_amount']:.4f}"
        )

        return report

    def get_stats(self) -> dict:
        """Combined MEV protection statistics."""
        return {
            "mempool": self.mempool.get_stats(),
            "settler": self.settler.get_stats(),
            "slashing_reports": len(self._slashing_log),
        }
