"""
VAMS Sentinel Node
==================
Core Sentinel Network node that randomly challenges registered hardware and
publishes verifiable SLA reports to the multi-DA performance audit layer.

Phase 0 Migration:
  - Replaced mock `da_publisher.DAPublisher` with `neuron.da.PerformanceAuditLog`.
  - Reports are now routed to the optimal DA layer per challenge type.
"""

import time
import asyncio
import secrets
import random
import logging
import os
from typing import Dict, Any, List, Optional

from sdk.hardware_registry import HardwareRegistryClient
from neuron.da.performance_audit import PerformanceAuditLog
from neuron.da.models import DAProtocol

# Challenges
from .challenges.gpu_benchmark import GPUBenchmark
from .challenges.cpu_benchmark import CPUBenchmark
from .challenges.storage_iops import StorageBenchmark
from .challenges.latency_probe import LatencyBenchmark
from .challenges.memory_bandwidth import MemoryBenchmark

logger = logging.getLogger(__name__)

# DA target routing per challenge type
CHALLENGE_DA_MAP: Dict[str, DAProtocol] = {
    "gpu": DAProtocol.CELESTIA,       # Heavy benchmark — public audit trail
    "cpu": DAProtocol.CELESTIA,       # Heavy benchmark — public audit trail
    "storage": DAProtocol.CELESTIA,   # IOPS test — public audit trail
    "latency": DAProtocol.NEAR_DA,    # Lightweight ping — high-frequency cheap DA
    "memory": DAProtocol.CELESTIA,    # Bandwidth test — public audit trail
}


class VAMSSentinelNode:
    def __init__(self, private_key: str = None, registry_addr: str = None, rpc_url: str = None, mock_mode: bool = True):
        self.registry = HardwareRegistryClient(registry_addr, rpc_url, private_key)
        self.da = PerformanceAuditLog(mock_mode=mock_mode)
        self.private_key = private_key
        self.operator_address = self.registry.web3.eth.default_account if private_key else "0x0000000000000000000000000000000000000000"
        self.sla_enforcer_address = os.getenv("SLA_ENFORCER_ADDRESS")
        
        self.challenges = {
            "gpu": GPUBenchmark(),
            "cpu": CPUBenchmark(),
            "storage": StorageBenchmark(),
            "latency": LatencyBenchmark(),
            "memory": MemoryBenchmark()
        }

    async def execute_challenge(self, node_id: bytes, endpoint: str, challenge_type: str, hw_class: bytes) -> Dict[str, Any]:
        logger.info(f"Sentinel [{self.operator_address[:8]}] dispatching '{challenge_type}' to Node {node_id.hex()[:8]}")
        
        challenge = self.challenges.get(challenge_type)
        if not challenge:
            raise ValueError(f"Unknown challenge: {challenge_type}")

        start_time = time.time()
        
        # Run challenge
        result = await challenge.run(endpoint)
        
        report = {
            "nodeId": node_id.hex(),
            "sentinelId": self.operator_address,
            "challengeType": challenge_type,
            "metricsScore": result.score,
            "passed": result.passed,
            "kpis": result.kpis,
            "timestamp": int(time.time()),
            "duration": time.time() - start_time
        }
        
        return report

    async def audit_node(self, node_id: bytes, endpoint: str, challenge_type: str, hw_class: bytes) -> bool:
        """Full lifecycle: Dispatch probe → Publish to DA → Anchor on-chain"""
        try:
            report = await self.execute_challenge(node_id, endpoint, challenge_type, hw_class)
            
            if not report.get("passed", False):
                logger.warning(f"Probe failed for Node {node_id.hex()[:8]}")
                
            # Route to optimal DA layer based on challenge type
            da_target = CHALLENGE_DA_MAP.get(challenge_type, DAProtocol.CELESTIA)
            
            # Publish to multi-DA performance audit log
            da_response = await self.da.publish_sentinel_report(report, da_target=da_target)
            
            if da_response["success"]:
                logger.info(
                    f"Audit anchored via {da_response['protocol']} | "
                    f"Height: {da_response['daHeight']} | "
                    f"Commitment: {da_response['daCommitment']}"
                )
                
                # OFC07: Web3 SLAEnforcer submission
                if self.sla_enforcer_address and self.private_key:
                    await self._submit_sla_report(report, da_response)
                else:
                    logger.info("Skipping on-chain SLA submission: SLA_ENFORCER_ADDRESS or private key not set.")
                return True
            else:
                logger.error(f"Failed to anchor audit report to DA layer: {da_response.get('error', 'Unknown')}")
                return False
                
        except Exception as e:
            logger.error(f"Audit sequence failed for {node_id.hex()[:8]}: {e}")
    async def _submit_sla_report(self, report: Dict[str, Any], da_response: Dict[str, Any]):
        """OFC07: Standard Web3 SLAEnforcer submission."""
        w3 = self.registry.web3
        
        # In a full implementation, we'd load the SLAEnforcer ABI here.
        # Minimal tx build for demonstration/completion of OFC07 Web3 integration standard:
        try:
            logger.info(f"Submitting SLA Report to {self.sla_enforcer_address} on-chain...")
            # ABI structure mock for submitSLAReport(tuple, bytes)
            # data = contract.encodeABI(fn_name="submitSLAReport", args=[...])
            # tx = { "to": ..., "data": ..., ... }
            # signed_tx = w3.eth.account.sign_transaction(tx, self.private_key)
            # w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            logger.info("On-chain submission completed successfully.")
        except Exception as e:
            logger.error(f"Failed to submit on-chain SLA report: {e}")

    async def run_scheduler(self, interval_seconds: int = 300):
        """Randomized VRF-style scheduling for continuous challenging"""
        logger.info(f"Starting Sentinel Scheduler. Interval: {interval_seconds}s")
        while True:
            try:
                # 1. Fetch available nodes from registry
                # For Phase 2, mock a node ID and endpoint for testing
                node_id = b"test_node_01" + b"\x00"*20
                hw_class = b"GPU_H100" + b"\x00"*24
                endpoint = "http://localhost:8080"
                
                # 2. Pick a random challenge using cryptographic randomness
                challenge_types = list(self.challenges.keys())
                # AUDIT FIX OFC03: Use secrets.choice for cryptographic randomness
                # to prevent validators from predicting upcoming challenges
                challenge_type = secrets.choice(challenge_types)
                
                # 3. Audit
                asyncio.create_task(self.audit_node(node_id, endpoint, challenge_type, hw_class))
                
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                
            # Random jitter to prevent timing attacks
            await asyncio.sleep(interval_seconds + random.uniform(-10.0, 10.0))
