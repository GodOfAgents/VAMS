"""
VAMS Sentinel Node
==================
Local Sentinel challenge/publication orchestration. Live operation and on-chain
SLA submission remain unqualified; publication is not proof of a protected effect.

Phase 0 Migration:
  - Replaced mock `da_publisher.DAPublisher` with `neuron.da.PerformanceAuditLog`.
  - Reports are now routed to the optimal DA layer per challenge type.
"""

import time
import asyncio
import secrets
import logging
import os
from typing import Dict, Any, List, Optional, Mapping

from ..sdk.hardware_registry import HardwareRegistryClient
from neuron.da.performance_audit import PerformanceAuditLog
from neuron.da.models import DAProtocol
from neuron.runtime_safety import (
    ImmutableRuntimeConfiguration,
    LiveModeSafetyError,
    RuntimePolicy,
    RuntimeConfigurationError,
    load_runtime_policy,
    resolve_component_mock_mode,
)

# Challenges
from .challenges.gpu_benchmark import GPUBenchmark
from .challenges.cpu_benchmark import CPUBenchmark
from .challenges.storage_iops import StorageBenchmark
from .challenges.latency_probe import LatencyBenchmark
from .challenges.memory_bandwidth import MemoryBenchmark
from .world_state_fidelity import WorldStateFidelitySentinel

logger = logging.getLogger(__name__)

# DA target routing per challenge type
CHALLENGE_DA_MAP: Dict[str, DAProtocol] = {
    "gpu": DAProtocol.CELESTIA,       # Heavy benchmark — public audit trail
    "cpu": DAProtocol.CELESTIA,       # Heavy benchmark — public audit trail
    "storage": DAProtocol.CELESTIA,   # IOPS test — public audit trail
    "latency": DAProtocol.NEAR_DA,    # Lightweight ping — high-frequency cheap DA
    "memory": DAProtocol.CELESTIA,    # Bandwidth test — public audit trail
}


SENTINEL_MOCK_VARIABLE = "SENTINEL_MOCK_MODE"


class VAMSSentinelNode(ImmutableRuntimeConfiguration):
    _immutable_runtime_fields = frozenset({"mock_mode", "runtime_policy", "_runtime_environ"})

    def __init__(self, private_key: str = None, registry_addr: str = None, rpc_url: str = None, mock_mode: Optional[bool] = None,
                 anomaly_detector=None, world_state_fidelity_sentinel=None, *, environ: Optional[Mapping[str, str]] = None, policy: Optional[RuntimePolicy] = None):
        source = os.environ if environ is None else environ
        self._runtime_environ = source
        self.runtime_policy = policy or load_runtime_policy(source)
        self.mock_mode = resolve_component_mock_mode(
            "VAMSSentinelNode",
            SENTINEL_MOCK_VARIABLE,
            mock_mode,
            policy=self.runtime_policy,
            environ=source,
        )
        if self.runtime_policy.is_live:
            raise LiveModeSafetyError(
                "VAMSSentinelNode live execution is disabled until challenge identity, "
                "on-chain anchoring, and publication confirmation are complete"
            )
        self.registry = HardwareRegistryClient(registry_addr, rpc_url, private_key)
        self.private_key = private_key
        if private_key:
            account_address = self.registry.account_address
            is_address = (
                isinstance(account_address, str)
                and len(account_address) == 42
                and account_address[:2].lower() == "0x"
                and all(char in "0123456789abcdefABCDEF" for char in account_address[2:])
                and any(char != "0" for char in account_address[2:])
            )
            if not is_address:
                raise RuntimeConfigurationError(
                    "Sentinel selected operator identity is unavailable"
                )
            self.operator_address = account_address
        else:
            self.operator_address = "0x0000000000000000000000000000000000000000"
        self.da = PerformanceAuditLog(
            mock_mode=self.mock_mode,
            runtime_policy=self.runtime_policy,
            environ=source,
        )

        self.sla_enforcer_address = os.getenv("SLA_ENFORCER_ADDRESS")

        # AUTOSKILL Phase 3a: Optional activation-space anomaly detector
        # When provided, audit reports are enriched with activation_anomaly_score
        # and adversarial_flag based on PCA-projected Mahalanobis distance.
        self.anomaly_detector = anomaly_detector
        self.world_state_fidelity_sentinel = (
            world_state_fidelity_sentinel or WorldStateFidelitySentinel()
        )

        # AUTOSKILL Phase 5: Per-node skill gap tracking for informed challenge selection
        self._node_skill_gaps: Dict[str, Dict[str, float]] = {}
        self._secure_random = secrets.SystemRandom()

        self.challenges = {
            "gpu": GPUBenchmark(),
            "cpu": CPUBenchmark(),
            "storage": StorageBenchmark(),
            "latency": LatencyBenchmark(),
            "memory": MemoryBenchmark()
        }
        self._freeze_runtime_configuration()

    def _require_local_runtime(self) -> None:
        """Revalidate the same configuration source bound at construction."""
        if type(self.runtime_policy) is not RuntimePolicy:
            raise RuntimeConfigurationError("Sentinel requires its bound runtime policy")
        current = load_runtime_policy(self._runtime_environ)
        if current != self.runtime_policy or current.is_live:
            raise RuntimeConfigurationError("Sentinel runtime changed or is unqualified for live operation")
        resolve_component_mock_mode(
            "VAMSSentinelNode", SENTINEL_MOCK_VARIABLE, self.mock_mode,
            policy=self.runtime_policy, environ=self._runtime_environ,
        )

    def _select_challenge_type(self, challenge_types: List[str], node_id_hex: str) -> str:
        if self.anomaly_detector and self._node_skill_gaps.get(node_id_hex):
            weights = self._compute_challenge_weights(node_id_hex)
            return self._secure_random.choices(challenge_types, weights=weights, k=1)[0]
        return self._secure_random.choice(challenge_types)

    def _scheduler_delay(self, interval_seconds: int) -> float:
        return max(0.0, interval_seconds + self._secure_random.uniform(-10.0, 10.0))

    @staticmethod
    def _build_continual_learning_gain(kpis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Build telemetry-only stateful-vs-stateless gain evidence.

        Gain must remain observational until calibrated benchmarks and reward
        policy thresholds exist.
        """
        if not isinstance(kpis, dict):
            return None

        if "stateful_reward" not in kpis or "stateless_reward" not in kpis:
            return None

        try:
            stateful_reward = float(kpis["stateful_reward"])
            stateless_reward = float(kpis["stateless_reward"])
        except (TypeError, ValueError):
            return None

        gain = stateful_reward - stateless_reward
        return {
            "statefulReward": stateful_reward,
            "statelessReward": stateless_reward,
            "gain": round(gain, 6),
            "status": "telemetry_only",
            "operationalFailureCandidate": gain < 0.0,
            "rewardImpact": "none",
            "regionalBonusImpact": "none",
        }

    async def execute_challenge(self, node_id: bytes, endpoint: str, challenge_type: str, hw_class: bytes) -> Dict[str, Any]:
        self._require_local_runtime()
        logger.info(f"Sentinel [{self.operator_address[:8]}] dispatching '{challenge_type}' to Node {node_id.hex()[:8]}")
        
        challenge = self.challenges.get(challenge_type)
        if not challenge:
            raise ValueError(f"Unknown challenge: {challenge_type}")

        start_time = time.time()
        
        # Run challenge
        result = await challenge.run(endpoint)
        self._require_local_runtime()
        
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

        gain_telemetry = self._build_continual_learning_gain(result.kpis)
        if gain_telemetry is not None:
            report["continualLearningGain"] = gain_telemetry

        world_state_trace = result.kpis.get("world_state_trace")
        if world_state_trace is not None:
            fidelity = self.world_state_fidelity_sentinel.evaluate_trace(world_state_trace)
            report["worldStateFidelity"] = fidelity.to_dict()
        
        return report

    async def audit_node(self, node_id: bytes, endpoint: str, challenge_type: str, hw_class: bytes) -> bool:
        """Local publication status only. Requested SLA submission is unavailable."""
        node_label = node_id.hex()[:8] if type(node_id) is bytes else "invalid"
        try:
            self._require_local_runtime()
            report = await self.execute_challenge(node_id, endpoint, challenge_type, hw_class)
            
            if not report.get("passed", False):
                logger.warning(f"Probe failed for Node {node_id.hex()[:8]}")

            # AUTOSKILL Phase 3a: Activation-space anomaly detection
            # Enriches the audit report with latent-space analysis when
            # an anomaly detector is configured and activation data is available.
            if self.anomaly_detector and report.get("activation_vector") is not None:
                try:
                    import numpy as np
                    activation = np.asarray(report["activation_vector"], dtype=np.float32)
                    anomaly_score = self.anomaly_detector.score_anomaly(activation)
                    is_adv = self.anomaly_detector.is_adversarial(activation)
                    report["activation_anomaly_score"] = round(anomaly_score, 6)
                    report["adversarial_flag"] = is_adv
                    if is_adv:
                        logger.warning(
                            f"AUTOSKILL: Adversarial activation detected for Node {node_id.hex()[:8]} "
                            f"(anomaly_score={anomaly_score:.4f})"
                        )
                except Exception as e:
                    logger.debug(f"AUTOSKILL anomaly detection skipped: {e}")

            # Route to optimal DA layer based on challenge type
            da_target = CHALLENGE_DA_MAP.get(challenge_type, DAProtocol.CELESTIA)
            
            # Publish to multi-DA performance audit log
            self._require_local_runtime()
            da_response = await self.da.publish_sentinel_report(report, da_target=da_target)
            self._require_local_runtime()
            
            if da_response["success"] is True:
                logger.info(
                    f"Local audit publication via {da_response['protocol']} | "
                    f"Height: {da_response['daHeight']} | "
                    f"Commitment: {da_response['daCommitment']}"
                )
                
                # OFC07: Web3 SLAEnforcer submission
                if self.sla_enforcer_address or self.private_key:
                    await self._submit_sla_report(report, da_response)
                else:
                    logger.info("No SLA submission requested; status describes local publication only.")
                return True
            else:
                logger.error("Local audit publication did not return explicit success.")
                return False
                
        except Exception as e:
            logger.error("Audit sequence failed for %s (%s)", node_label, type(e).__name__)
            return False
    async def _submit_sla_report(self, report: Dict[str, Any], da_response: Dict[str, Any]):
        """No qualified transaction producer/receipt verifier exists for this path."""
        raise LiveModeSafetyError("Sentinel SLA submission is unavailable; no transaction was built or sent")

    def _compute_challenge_weights(self, node_id_hex: str) -> List[float]:
        """
        AUTOSKILL Phase 5: Compute informed challenge selection weights.

        Nodes with known skill gaps in certain dimensions get weighted
        more heavily toward challenges that probe those weaknesses.
        Falls back to uniform weights if no gap data is available.
        """
        challenge_types = list(self.challenges.keys())
        n = len(challenge_types)
        uniform = [1.0 / n] * n

        gaps = self._node_skill_gaps.get(node_id_hex)
        if not gaps:
            return uniform

        # Boost weight for challenge types where the node has higher gap scores
        weights = []
        for ct in challenge_types:
            gap_score = gaps.get(ct, 0.0)
            weights.append(1.0 + gap_score)  # Baseline 1.0 + gap bonus

        total = sum(weights)
        if total < 1e-8:
            return uniform

        return [w / total for w in weights]

    async def run_scheduler(self, interval_seconds: int = 300):
        """Local randomized scheduling; not a verified randomness function."""
        self._require_local_runtime()
        logger.info(f"Starting Sentinel Scheduler. Interval: {interval_seconds}s")
        while True:
            self._require_local_runtime()
            try:
                # 1. Fetch available nodes from registry
                # For Phase 2, mock a node ID and endpoint for testing
                node_id = b"test_node_01" + b"\x00"*20
                hw_class = b"GPU_H100" + b"\x00"*24
                endpoint = "http://localhost:8080"
                
                # 2. Pick challenge type
                challenge_types = list(self.challenges.keys())

                # AUTOSKILL Phase 5: Informed challenge selection
                # When skill gap data is available, weight challenges toward
                # areas where the target node shows historical weakness.
                node_id_hex = node_id.hex()
                if self.anomaly_detector and self._node_skill_gaps.get(node_id_hex):
                    challenge_type = self._select_challenge_type(challenge_types, node_id_hex)
                    logger.debug(f"AUTOSKILL: Informed challenge selection for {node_id_hex[:8]}: {challenge_type}")
                else:
                    challenge_type = self._select_challenge_type(challenge_types, node_id_hex)
                
                # 3. Audit
                self._require_local_runtime()
                asyncio.create_task(self.audit_node(node_id, endpoint, challenge_type, hw_class))
                
            except LiveModeSafetyError:
                raise
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                
            # Random jitter to prevent timing attacks
            await asyncio.sleep(self._scheduler_delay(interval_seconds))
