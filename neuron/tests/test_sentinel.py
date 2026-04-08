"""
Tests for the VAMS Sentinel monitoring network.
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock

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
    @patch("torch.cuda.is_available")
    async def test_gpu_challenge_no_cuda(self, mock_cuda):
        mock_cuda.return_value = False
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
