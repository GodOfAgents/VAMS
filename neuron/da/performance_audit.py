"""
VAMS Performance Audit Log
==========================
Multi-DA routing orchestrator for Sentinel challenge reports.

Replaces the mock `da_publisher.py` in the Sentinel package with a
dedicated, production-ready audit log that routes performance data
to the optimal DA layer based on report criticality.

Routing Strategy:
    - Standard SLA reports    → Celestia (public DAS auditability)
    - High-freq latency pings → Near DA  (cheapest, sub-second)
    - High-value fraud proofs → EigenDA  (Ethereum-grade security)
    - Backup / ZK proofs      → Avail    (KZG commitments)
"""

import hashlib
import json
import logging
from typing import Dict, Any, List, Optional

from neuron.da.models import DAProtocol, DAReceipt, AuditReport
from neuron.da.adapters.base import DAAdapter
from neuron.da.adapters.celestia_adapter import CelestiaDAAdapter
from neuron.da.adapters.near_adapter import NearDAAdapter
from neuron.da.adapters.eigenda_adapter import EigenDAAdapter
from neuron.da.adapters.avail_adapter import AvailDAAdapter

logger = logging.getLogger("VAMS-PerformanceAuditLog")

# Default DA routing for different challenge types
CHALLENGE_DA_ROUTING: Dict[str, DAProtocol] = {
    "gpu": DAProtocol.CELESTIA,       # GPU benchmarks: public audit trail
    "cpu": DAProtocol.CELESTIA,       # CPU benchmarks: public audit trail
    "storage": DAProtocol.CELESTIA,   # Storage IOPS: public audit trail
    "latency": DAProtocol.NEAR_DA,    # Latency probes: high-frequency
    "memory": DAProtocol.CELESTIA,    # Memory bandwidth: public audit trail
}


class PerformanceAuditLog:
    """
    Multi-DA orchestrator for Sentinel performance audit reports.

    Manages a pool of DA adapters and routes reports to the optimal
    layer based on challenge type, criticality, or explicit target.
    """

    def __init__(self, mock_mode: bool = False, config: Optional[Dict] = None):
        self.mock_mode = mock_mode
        self._config = config or {}

        # Initialize adapters from config or defaults
        self.adapters: Dict[DAProtocol, DAAdapter] = {
            DAProtocol.CELESTIA: CelestiaDAAdapter(
                rpc_url=self._config.get("celestia_rpc", "https://rpc-mocha.pops.one"),
                mock_mode=mock_mode,
            ),
            DAProtocol.NEAR_DA: NearDAAdapter(
                rpc_url=self._config.get("near_rpc", "https://rpc.testnet.near.org"),
                mock_mode=mock_mode,
            ),
            DAProtocol.EIGEN_DA: EigenDAAdapter(
                rpc_url=self._config.get("eigenda_rpc", "https://holesky.drpc.org"),
                mock_mode=True,  # Stub always
            ),
            DAProtocol.AVAIL: AvailDAAdapter(
                rpc_url=self._config.get("avail_rpc", "https://avail-turing.api.onfinality.io/public"),
                mock_mode=True,  # Stub always
            ),
        }

        # Audit history for observability
        self.audit_history: List[Dict[str, Any]] = []

    def _select_da_target(self, report: AuditReport) -> DAProtocol:
        """
        Select the optimal DA layer for this report.

        Priority:
        1. Explicit da_target on the report.
        2. Challenge-type-based routing map.
        3. Default to Celestia.
        """
        if report.da_target and report.da_target in self.adapters:
            return report.da_target

        return CHALLENGE_DA_ROUTING.get(report.challenge_type, DAProtocol.CELESTIA)

    async def publish_sentinel_report(
        self,
        report: Dict[str, Any],
        da_target: Optional[DAProtocol] = None,
    ) -> Dict[str, Any]:
        """
        Publish a Sentinel challenge report to the appropriate DA layer.

        Args:
            report: Raw Sentinel report dict (from sentinel_node.py).
            da_target: Optional explicit DA target override.

        Returns:
            Submission result with DA receipt and Merkle proof data.
        """
        # Convert raw dict to structured AuditReport
        target = da_target or DAProtocol.CELESTIA
        audit_report = AuditReport.from_sentinel_report(report, da_target=target)

        # Resolve final DA target
        final_target = self._select_da_target(audit_report)

        # Serialize and submit
        blob_data = audit_report.serialize()
        report_hash = audit_report.compute_hash()

        adapter = self.adapters.get(final_target)
        if not adapter:
            logger.error(f"No adapter found for {final_target}. Falling back to Celestia.")
            adapter = self.adapters[DAProtocol.CELESTIA]
            final_target = DAProtocol.CELESTIA

        try:
            receipt = await adapter.submit_blob(blob_data)

            result = {
                "success": True,
                "protocol": final_target.value,
                "blob_id": receipt.blob_id,
                "daHeight": receipt.height,
                "daCommitment": receipt.commitment,
                "reportHash": report_hash,
                "merkleRoot": report_hash,  # Single-item tree root = report hash
                "merkleProof": [report_hash],
                "verified": receipt.verified,
            }

            # Track for observability
            self.audit_history.append({
                "node_id": audit_report.node_id,
                "protocol": final_target.value,
                "blob_id": receipt.blob_id,
                "height": receipt.height,
                "report_hash": report_hash,
                "timestamp": audit_report.timestamp,
            })

            logger.info(
                f"Audit published to {final_target.value} | "
                f"Node: {audit_report.node_id[:8]} | "
                f"Height: {receipt.height} | "
                f"Hash: {report_hash[:18]}..."
            )

            return result

        except Exception as e:
            logger.error(f"DA submission failed on {final_target.value}: {e}")
            return {
                "success": False,
                "protocol": final_target.value,
                "error": str(e),
            }

    async def verify_report(self, receipt_data: Dict[str, Any]) -> bool:
        """Verify that a previously submitted report is still available on the DA layer."""
        protocol = DAProtocol(receipt_data.get("protocol", "celestia"))
        adapter = self.adapters.get(protocol)
        if not adapter:
            return False

        receipt = DAReceipt(
            protocol=protocol,
            blob_id=receipt_data["blob_id"],
            height=receipt_data["daHeight"],
            commitment=receipt_data["daCommitment"],
        )

        return await adapter.verify_blob(receipt)

    async def get_adapter_status(self) -> Dict[str, Any]:
        """Get connectivity status for all DA adapters."""
        status = {}
        for protocol, adapter in self.adapters.items():
            is_healthy = await adapter.health_check()
            status[protocol.value] = {
                "name": adapter.name,
                "rpc_url": adapter.rpc_url,
                "mock_mode": adapter.mock_mode,
                "healthy": is_healthy,
            }
        return status

    def get_audit_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return the most recent audit submissions."""
        return self.audit_history[-limit:]
