"""
Tests for the VAMS Sentinel monitoring network.
"""
import pytest
import asyncio
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sentinel.challenges.cpu_benchmark import CPUBenchmark
from sentinel.challenges.gpu_benchmark import GPUBenchmark
from sentinel.challenges.storage_iops import StorageBenchmark
from sentinel.challenges.memory_bandwidth import MemoryBenchmark
from sentinel.challenges.latency_probe import LatencyBenchmark
from sentinel.da_publisher import DAPublisher
from sentinel.sentinel_node import VAMSSentinelNode
import time

@pytest.mark.asyncio
class TestSentinelChallenges:
    
    # ═══════════════════ CPU Benchmark Tests ═══════════════════
    async def test_cpu_challenge_success(self):
        challenge = CPUBenchmark()
        result = await challenge.run("mock")
        # In our implementation we run actual simple python tests
        assert result.success is True
        assert result.score > 0
        assert "multi_thread_score" in result.kpis

    @patch("multiprocessing.Pool")
    async def test_cpu_challenge_fail(self, mock_pool):
        mock_pool.side_effect = Exception("Multiprocessing crashed")
        challenge = CPUBenchmark()
        result = await challenge.run("mock")
        assert result.success is False
        assert result.score == 0.0
        assert "Multiprocessing crashed" in result.error

    # ═══════════════════ GPU Benchmark Tests ═══════════════════
    async def test_gpu_challenge_no_cuda(self):
        fake_torch = MagicMock()
        fake_torch.cuda.is_available.return_value = False
        with patch.dict("sys.modules", {"torch": fake_torch}):
            challenge = GPUBenchmark()
            result = await challenge.run("mock")
        assert result.success is False
        assert result.score == 0.0
        assert "CUDA not available" in result.error
        
    # ═══════════════════ Storage IOPS Tests ═══════════════════
    async def test_storage_challenge_success(self):
        challenge = StorageBenchmark()
        result = await challenge.run("mock")
        assert result.success is True
        assert result.score > 0
        assert "rand_read_iops" in result.kpis

    # ═══════════════════ Memory Benchmark Tests ═══════════════════
    async def test_memory_challenge_success(self):
        challenge = MemoryBenchmark()
        result = await challenge.run("mock")
        assert result.success is True
        assert result.score > 0
        assert "bandwidth_gbps" in result.kpis
        
    # ═══════════════════ Latency Probe Tests ═══════════════════
    async def test_latency_probe_success(self):
        challenge = LatencyBenchmark()
        result = await challenge.run("mock")
        assert result.success is True
        assert result.score > 0
        assert "avg_rtt_ms" in result.kpis

@pytest.mark.asyncio
class TestSentinelPublisher:
    
    async def test_publish_report(self):
        pub = DAPublisher()
        res = await pub.publish_report({"nodeId": "1234", "score": 9000})
        
        assert res["success"] is True
        assert res["daHeight"] > 0
        assert "daCommitment" in res
        assert "merkleRoot" in res

@pytest.mark.asyncio
class TestSentinelNode:

    async def test_weighted_challenge_selection_uses_system_random(self):
        node = VAMSSentinelNode(anomaly_detector=MagicMock())
        node_id_hex = "01" * 32
        node._node_skill_gaps[node_id_hex] = {"gpu": 0.8}
        node._secure_random = MagicMock()
        node._secure_random.choices.return_value = ["gpu"]

        with patch.object(node, "_compute_challenge_weights", return_value=[0.8, 0.2]):
            selected = node._select_challenge_type(["gpu", "cpu"], node_id_hex)

        assert selected == "gpu"
        node._secure_random.choices.assert_called_once_with(
            ["gpu", "cpu"], weights=[0.8, 0.2], k=1
        )

    async def test_scheduler_delay_never_becomes_negative(self):
        node = VAMSSentinelNode()
        node._secure_random = MagicMock()
        node._secure_random.uniform.return_value = -10.0

        assert node._scheduler_delay(5) == 0.0
    
    @patch("sentinel.da_publisher.DAPublisher.publish_report")
    @patch("sentinel.challenges.latency_probe.LatencyBenchmark.run")
    async def test_audit_node_success(self, mock_run, mock_publish):
        from sentinel.challenges.base_challenge import ChallengeResult
        mock_run.return_value = ChallengeResult(
            success=True, score=10000, kpis={"avg_rtt": 2.0}, passed=True
        )
        # Needs async mock since python 3.8 AsyncMock
        mock_publish.return_value = {"success": True, "daHeight": 1000, "daCommitment": "abc"}
        
        node = VAMSSentinelNode()
        res = await node.audit_node(b"1234"*8, "http://test", "latency", b"NETWORK_10G")
        assert res is True

    async def test_continual_learning_negative_gain_is_telemetry_only(self):
        from sentinel.challenges.base_challenge import ChallengeResult

        class MockGainChallenge:
            async def run(self, endpoint):
                return ChallengeResult(
                    success=True,
                    score=9500,
                    kpis={
                        "stateful_reward": 1.0,
                        "stateless_reward": 2.5,
                    },
                    passed=True,
                )

        node = VAMSSentinelNode()
        node.challenges["latency"] = MockGainChallenge()

        report = await node.execute_challenge(
            b"1234" * 8,
            "http://test",
            "latency",
            b"NETWORK_10G",
        )

        gain = report["continualLearningGain"]
        assert gain["gain"] == -1.5
        assert gain["status"] == "telemetry_only"
        assert gain["operationalFailureCandidate"] is True
        assert gain["rewardImpact"] == "none"
        assert gain["regionalBonusImpact"] == "none"

    async def test_world_state_fidelity_is_telemetry_only(self):
        from sentinel.challenges.base_challenge import ChallengeResult

        class MockWorldStateChallenge:
            async def run(self, endpoint):
                return ChallengeResult(
                    success=True,
                    score=9900,
                    kpis={
                        "world_state_trace": [
                            {
                                "step": 1,
                                "agent_state": {"escrow": "locked"},
                                "verified_external_state": {"escrow": "locked"},
                                "action_valid": True,
                            },
                            {
                                "step": 2,
                                "agent_state": {"escrow": "locked"},
                                "verified_external_state": {"escrow": "claimed"},
                                "action_valid": True,
                            },
                        ]
                    },
                    passed=True,
                )

        node = VAMSSentinelNode()
        node.challenges["latency"] = MockWorldStateChallenge()

        report = await node.execute_challenge(
            b"1234" * 8,
            "http://test",
            "latency",
            b"NETWORK_10G",
        )

        fidelity = report["worldStateFidelity"]
        assert report["passed"] is True
        assert fidelity["state_fidelity_score"] == 0.5
        assert fidelity["first_state_divergence_step"] == 2
        assert fidelity["status"] == "telemetry_only"
        assert fidelity["rewardImpact"] == "none"
        assert fidelity["regionalBonusImpact"] == "none"
