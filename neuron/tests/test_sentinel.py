"""
Tests for the VAMS Sentinel monitoring network.
"""
import pytest
from unittest.mock import patch, MagicMock

from sentinel.challenges.cpu_benchmark import run_cpu_challenge
from sentinel.challenges.gpu_benchmark import run_gpu_challenge
from sentinel.challenges.storage_iops import run_storage_challenge
from sentinel.challenges.memory_bandwidth import run_memory_challenge
from sentinel.challenges.latency_probe import run_latency_challenge
from sentinel.da_publisher import DAPublisher
from sentinel.sentinel_node import VAMSSentinelNode
import time

class TestSentinelChallenges:
    
    # ═══════════════════ CPU Benchmark Tests ═══════════════════
    @patch("subprocess.run")
    def test_cpu_challenge_success(self, mock_run):
        mock_result = MagicMock()
        mock_result.stdout = "CPU speed:\n    events per second: 12500.55\n"
        mock_run.return_value = mock_result
        
        result = run_cpu_challenge(max_prime=5000)
        assert result["success"] is True
        assert result["score"] == 12500.55
        assert result["metric"] == "events_per_sec"
        
    @patch("subprocess.run")
    def test_cpu_challenge_fail(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.CalledProcessError(1, "sysbench", stderr="Crash")
        result = run_cpu_challenge()
        assert result["success"] is False
        assert result["score"] == 0.0
        assert "sysbench execution failed" in result["error"]

    # ═══════════════════ GPU Benchmark Tests ═══════════════════
    @patch("torch.cuda.is_available")
    def test_gpu_challenge_no_cuda(self, mock_cuda):
        mock_cuda.return_value = False
        result = run_gpu_challenge()
        assert result["success"] is False
        assert result["score"] == 0.0
        assert "CUDA not available" in result["error"]
        
    # We don't mock the entire torch runtime, but catching the absence of it is enough for CI.

    # ═══════════════════ Storage IOPS Tests ═══════════════════
    @patch("subprocess.run")
    def test_storage_challenge_success(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"jobs": [{"read": {"iops": 5000.5}, "write": {"iops": 2500.2}}]}'
        mock_run.return_value = mock_result
        
        result = run_storage_challenge(size="10m", runtime=1)
        assert result["success"] is True
        assert result["score"] == 7500.7
        assert result["read_iops"] == 5000.5
        assert result["write_iops"] == 2500.2
        
    @patch("subprocess.run")
    def test_storage_challenge_invalid_json(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'invalid json data'
        mock_run.return_value = mock_result
        
        result = run_storage_challenge()
        assert result["success"] is False
        assert "JSON decode error" in result["error"]

    # ═══════════════════ Memory Benchmark Tests ═══════════════════
    @patch("subprocess.run")
    def test_memory_challenge_success(self, mock_run):
        mock_result = MagicMock()
        mock_result.stdout = "10240.00 MiB transferred (2400.00 MiB/sec)"
        mock_run.return_value = mock_result
        
        result = run_memory_challenge()
        assert result["success"] is True
        assert result["score"] == 2400.0
        assert result["metric"] == "mib_ps"
        
    # ═══════════════════ Latency Probe Tests ═══════════════════
    @patch("requests.get")
    def test_latency_probe_http_success(self, mock_get):
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_get.return_value = mock_res
        
        result = run_latency_challenge("http://mock-endpoint.com")
        assert result["success"] is True
        assert result["score"] > 0
        
    @patch("requests.get")
    def test_latency_probe_http_fail(self, mock_get):
        mock_res = MagicMock()
        mock_res.status_code = 502
        mock_get.return_value = mock_res
        
        result = run_latency_challenge("http://mock-endpoint.com")
        assert result["success"] is False
        assert result["score"] == 0.0

    @patch("socket.create_connection")
    def test_latency_probe_socket_success(self, mock_sock):
        mock_sock.return_value = True
        result = run_latency_challenge("10.0.0.1:8080")
        assert result["success"] is True

    @patch("socket.create_connection")
    def test_latency_probe_socket_fail(self, mock_sock):
        import socket
        mock_sock.side_effect = socket.error("Connection Refused")
        result = run_latency_challenge("10.0.0.1:8080")
        assert result["success"] is False

class TestSentinelPublisher:
    
    @patch("sdk.celestia.CelestiaDA.submit_blob")
    def test_publish_report(self, mock_submit):
        mock_sub = MagicMock()
        mock_sub.height = 42000
        mock_sub.commitment = "mockethash"
        mock_sub.namespace = "vams"
        mock_sub.size_bytes = 100
        mock_submit.return_value = mock_sub
        
        pub = DAPublisher()
        res = pub.publish_report({"benchmark": "results"})
        
        assert res["success"] is True
        assert res["da_height"] == 42000
        assert res["da_commitment"] == "mockethash"

    @patch("sdk.celestia.CelestiaDA.submit_blob")
    def test_publish_report_fail(self, mock_submit):
        mock_submit.side_effect = Exception("Celestia down")
        pub = DAPublisher()
        res = pub.publish_report({"benchmark": "results"})
        assert res["success"] is False
        assert "Celestia down" in res["error"]

class TestSentinelNode:
    
    @patch("sentinel.da_publisher.DAPublisher.publish_report")
    @patch("sentinel.challenges.latency_probe.run_latency_challenge")
    def test_audit_node_success(self, mock_latency, mock_publish):
        mock_latency.return_value = {"success": True, "score": 500.0, "latency_ms": 2.0}
        mock_publish.return_value = {"success": True, "da_height": 1000, "da_commitment": "abc"}
        
        node = VAMSSentinelNode()
        # Uses standard test node ID
        res = node.audit_node(b"1234"*8, "http://test", "latency")
        assert res is True

    @patch("sentinel.da_publisher.DAPublisher.publish_report")
    @patch("sentinel.sentinel_node.run_cpu_challenge")
    def test_audit_node_cpu_sim(self, mock_cpu, mock_publish):
        mock_cpu.return_value = {"success": True, "score": 10000.0}
        mock_publish.return_value = {"success": True, "da_height": 1001, "da_commitment": "def"}
        
        node = VAMSSentinelNode()
        res = node.audit_node(b"1234"*8, "http://test", "cpu_simulated")
        assert res is True
