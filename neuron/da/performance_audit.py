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
import os
from typing import Dict, Any, List, Optional

from neuron.da.models import DAProtocol, DAReceipt, AuditReport
from neuron.da.adapters.base import DAAdapter
from neuron.da.adapters.celestia_adapter import CelestiaDAAdapter
from neuron.da.adapters.near_adapter import NearDAAdapter
from neuron.da.adapters.eigenda_adapter import EigenDAAdapter
from neuron.da.adapters.avail_adapter import AvailDAAdapter
from neuron.runtime_safety import require_not_live_mock

logger = logging.getLogger("VAMS-PerformanceAuditLog")

# Default DA routing for different challenge types
CHALLENGE_DA_ROUTING: Dict[str, DAProtocol] = {
    "gpu": DAProtocol.CELESTIA,       # GPU benchmarks: public audit trail
    "cpu": DAProtocol.CELESTIA,       # CPU benchmarks: public audit trail
    "storage": DAProtocol.CELESTIA,   # Storage IOPS: public audit trail
    "latency": DAProtocol.NEAR_DA,    # Latency probes: high-frequency
    "memory": DAProtocol.CELESTIA,    # Memory bandwidth: public audit trail
}

# Near remains blocked until it submits a signed transaction and supports exact
# retrieval. Avail and EigenDA remain structured stubs. This set describes
# operational live routing only; release evidence requires an external observer.
LIVE_CAPABLE_PROTOCOLS = {DAProtocol.CELESTIA}
ALL_CONFIGURED_PROTOCOLS = (
    DAProtocol.CELESTIA,
    DAProtocol.NEAR_DA,
    DAProtocol.EIGEN_DA,
    DAProtocol.AVAIL,
)


class DAConfigurationError(RuntimeError):
    """Raised when a requested DA route is disabled or unsupported."""


class PerformanceAuditLog:
    """
    Multi-DA orchestrator for Sentinel performance audit reports.

    Manages a pool of DA adapters and routes reports to the optimal
    layer based on challenge type, criticality, or explicit target.
    """

    def __init__(self, mock_mode: bool = False, config: Optional[Dict] = None):
        require_not_live_mock("PerformanceAuditLog", mock_mode)
        self.mock_mode = mock_mode
        self._config = config or {}

        enabled_protocols = self._enabled_protocols()
        self.adapters: Dict[DAProtocol, DAAdapter] = {}
        if DAProtocol.CELESTIA in enabled_protocols:
            self.adapters[DAProtocol.CELESTIA] = CelestiaDAAdapter(
                rpc_url=self._config.get("celestia_rpc", "https://rpc-mocha.pops.one"),
                mock_mode=mock_mode,
            )
        if DAProtocol.NEAR_DA in enabled_protocols:
            self.adapters[DAProtocol.NEAR_DA] = NearDAAdapter(
                rpc_url=self._config.get("near_rpc", "https://rpc.testnet.near.org"),
                mock_mode=mock_mode,
            )
        if DAProtocol.EIGEN_DA in enabled_protocols:
            self.adapters[DAProtocol.EIGEN_DA] = EigenDAAdapter(
                rpc_url=self._config.get("eigenda_rpc", "https://holesky.drpc.org"),
                mock_mode=True,
            )
        if DAProtocol.AVAIL in enabled_protocols:
            self.adapters[DAProtocol.AVAIL] = AvailDAAdapter(
                rpc_url=self._config.get("avail_rpc", "https://avail-turing.api.onfinality.io/public"),
                mock_mode=True,
            )

        if DAProtocol.CELESTIA not in self.adapters:
            raise DAConfigurationError("Celestia must remain enabled as the audit fallback")

        # Audit history for observability
        self.audit_history: List[Dict[str, Any]] = []

    def _enabled_protocols(self) -> set[DAProtocol]:
        configured = self._config.get("enabled_protocols")
        if configured is None:
            configured = os.getenv("VAMS_DA_ENABLED_PROTOCOLS")

        if configured is None:
            return set(ALL_CONFIGURED_PROTOCOLS if self.mock_mode else LIVE_CAPABLE_PROTOCOLS)
        if isinstance(configured, str):
            configured = [item.strip() for item in configured.split(",") if item.strip()]
        if not isinstance(configured, (list, tuple, set)):
            raise DAConfigurationError("enabled_protocols must be a list or comma-separated string")

        try:
            enabled = {
                item if isinstance(item, DAProtocol) else DAProtocol(str(item).strip().lower())
                for item in configured
            }
        except ValueError as exc:
            raise DAConfigurationError(f"Unknown DA protocol in enabled_protocols: {exc}") from exc
        unsupported_live = enabled - LIVE_CAPABLE_PROTOCOLS
        if not self.mock_mode and unsupported_live:
            for protocol in sorted(unsupported_live, key=lambda item: item.value):
                require_not_live_mock(f"{protocol.value} DA adapter", True)
            names = ", ".join(sorted(protocol.value for protocol in unsupported_live))
            raise DAConfigurationError(
                f"DA protocols are not live-capable and remain disabled: {names}"
            )
        return enabled

    def _select_da_target(
        self,
        report: AuditReport,
        explicit_target: Optional[DAProtocol | str],
    ) -> DAProtocol:
        """
        Select the optimal DA layer for this report.

        Priority:
        1. Explicit da_target on the report.
        2. Challenge-type-based routing map.
        3. Default to Celestia.
        """
        try:
            target = (
                explicit_target
                if isinstance(explicit_target, DAProtocol)
                else DAProtocol(str(explicit_target).strip().lower())
                if explicit_target is not None
                else CHALLENGE_DA_ROUTING.get(report.challenge_type, DAProtocol.CELESTIA)
            )
        except ValueError as exc:
            raise DAConfigurationError(f"Unknown DA protocol: {explicit_target}") from exc
        target = target or CHALLENGE_DA_ROUTING.get(
            report.challenge_type, DAProtocol.CELESTIA
        )
        if target not in self.adapters:
            raise DAConfigurationError(f"DA protocol {target.value} is not enabled")
        return target

    async def publish_sentinel_report(
        self,
        report: Dict[str, Any],
        da_target: Optional[DAProtocol | str] = None,
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
        try:
            provisional_report = AuditReport.from_sentinel_report(report)
            target = self._select_da_target(provisional_report, da_target)
            audit_report = AuditReport.from_sentinel_report(report, da_target=target)
            final_target = self._select_da_target(audit_report, da_target)
        except (DAConfigurationError, KeyError, TypeError, ValueError) as exc:
            logger.error(str(exc))
            return {
                "success": False,
                "protocol": da_target.value if isinstance(da_target, DAProtocol) else str(da_target or "unknown"),
                "error": str(exc),
            }

        # Serialize and submit
        blob_data = audit_report.serialize()
        report_hash = audit_report.compute_hash()

        adapter = self.adapters[final_target]

        try:
            receipt = await adapter.submit_blob(blob_data)
            retrieval_verified = False
            if not self.mock_mode:
                retrieval_verified = await adapter.verify_blob(receipt)
                if retrieval_verified is not True:
                    raise DAConfigurationError(
                        f"DA protocol {final_target.value} did not return the exact submitted blob"
                    )

            result = {
                "success": True,
                "protocol": final_target.value,
                "blob_id": receipt.blob_id,
                "daHeight": receipt.height,
                "daCommitment": receipt.commitment,
                "reportHash": report_hash,
                "merkleRoot": report_hash,  # Single-item tree root = report hash
                "merkleProof": [report_hash],
                "verified": retrieval_verified,
                "mock_mode": self.mock_mode,
                # This publisher cannot establish independent release evidence.
                "release_evidence_eligible": False,
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
                "supports_live_submission": adapter.supports_live_submission,
                "supports_exact_retrieval": adapter.supports_exact_retrieval,
                "release_evidence_eligible": adapter.release_evidence_eligible,
            }
        return status

    def get_audit_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return the most recent audit submissions."""
        return self.audit_history[-limit:]
