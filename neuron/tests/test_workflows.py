"""
VAMS Neuron - Workflow Integration Tests
=========================================
Tests for the crash-proof workflow engine (Layer 3).
"""

import sys
import os
import pytest
import sqlite3
import tempfile
import shutil
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflows import (
    CheckpointStore,
    Checkpoint,
    WorkflowStatus,
    WorkflowResult,
    VamsWorkflow,
    DemoWorkflow,
    checkpoint,
    run_demo_workflow,
    LogicLayerMonitor
)


class TestCheckpointStore:
    """Tests for the CheckpointStore SQLite-based persistence."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_checkpoints.db")
        yield db_path
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def store(self, temp_db):
        """Create a checkpoint store with temp database."""
        return CheckpointStore(db_path=temp_db)
    
    def test_store_initialization(self, store):
        """Test that store initializes correctly."""
        assert store is not None
        assert os.path.exists(store.db_path)
    
    def test_save_checkpoint(self, store):
        """Test saving a checkpoint."""
        cp = Checkpoint(
            workflow_id="wf_test",
            step_name="step1",
            step_index=0,
            data={"key": "value"}
        )
        
        # Should not raise
        store.save_checkpoint(cp)
    
    def test_get_last_checkpoint(self, store):
        """Test retrieving the last checkpoint."""
        # Save two checkpoints
        cp1 = Checkpoint(
            workflow_id="wf_test",
            step_name="step1",
            step_index=0,
            data={"stage": "first"}
        )
        cp2 = Checkpoint(
            workflow_id="wf_test",
            step_name="step2",
            step_index=1,
            data={"stage": "second"}
        )
        
        store.save_checkpoint(cp1)
        store.save_checkpoint(cp2)
        
        last = store.get_last_checkpoint("wf_test")
        
        assert last is not None
        assert last.step_name == "step2"
        assert last.step_index == 1
        assert last.data["stage"] == "second"
    
    def test_get_last_checkpoint_nonexistent(self, store):
        """Test getting checkpoint for nonexistent workflow."""
        result = store.get_last_checkpoint("nonexistent")
        assert result is None
    
    def test_clear_checkpoints(self, store):
        """Test clearing checkpoints."""
        cp = Checkpoint(
            workflow_id="wf_test",
            step_name="step1",
            step_index=0,
            data={"key": "value"}
        )
        store.save_checkpoint(cp)
        
        store.clear_checkpoints("wf_test")
        
        result = store.get_last_checkpoint("wf_test")
        assert result is None


class TestCheckpoint:
    """Tests for the Checkpoint dataclass."""
    
    def test_to_dict(self):
        """Test Checkpoint.to_dict() method."""
        cp = Checkpoint(
            workflow_id="wf_123",
            step_name="test_step",
            step_index=5,
            data={"foo": "bar"},
            timestamp=1234567890.0
        )
        
        d = cp.to_dict()
        
        assert d["workflow_id"] == "wf_123"
        assert d["step_name"] == "test_step"
        assert d["step_index"] == 5
        assert d["data"] == {"foo": "bar"}
        assert d["timestamp"] == 1234567890.0


class TestDemoWorkflow:
    """Tests for the DemoWorkflow crash-proof execution."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "workflow_checkpoints.db")
        yield db_path, temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_workflow_without_crash(self):
        """Test workflow runs to completion without crash simulation."""
        workflow_id = f"test_{int(time.time() * 1000)}"
        wf = DemoWorkflow(workflow_id=workflow_id, simulate_crash=False)
        
        logs = []
        result = wf.run(log_fn=logs.append)
        
        assert result.status == WorkflowStatus.COMPLETED
        assert result.steps_completed == result.total_steps
        assert result.error is None
    
    def test_workflow_crash_simulation(self):
        """Test that crash simulation works."""
        workflow_id = f"crash_test_{int(time.time() * 1000)}"
        wf = DemoWorkflow(workflow_id=workflow_id, simulate_crash=True)
        
        logs = []
        result = wf.run(log_fn=logs.append)
        
        assert result.status == WorkflowStatus.FAILED
        assert "Simulated crash" in result.error
        assert result.steps_completed == 2  # Crashes after step 2
    
    def test_workflow_recovery(self):
        """Test workflow recovery after crash."""
        workflow_id = f"recovery_{int(time.time() * 1000)}"
        
        # First run - will crash
        wf1 = DemoWorkflow(workflow_id=workflow_id, simulate_crash=True)
        logs1 = []
        result1 = wf1.run(log_fn=logs1.append)
        
        assert result1.status == WorkflowStatus.FAILED
        
        # Second run - should recover
        wf2 = DemoWorkflow(workflow_id=workflow_id, simulate_crash=False)
        logs2 = []
        result2 = wf2.run(log_fn=logs2.append)
        
        assert result2.status == WorkflowStatus.COMPLETED
        assert result2.recovered is True
        assert result2.recovery_step is not None


class TestCrashRecovery:
    """Tests for crash-proof recovery behavior."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_recovery.db")
        yield db_path
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_checkpoint_persists_across_store_restart(self, temp_db):
        """Test that checkpoint data persists when store restarts."""
        # Create checkpoint with first store
        store1 = CheckpointStore(db_path=temp_db)
        cp = Checkpoint(
            workflow_id="persist_test",
            step_name="step1",
            step_index=0,
            data={"key": "value"}
        )
        store1.save_checkpoint(cp)
        
        # Create new store instance (simulates restart)
        store2 = CheckpointStore(db_path=temp_db)
        
        # Should be able to retrieve checkpoint
        last = store2.get_last_checkpoint("persist_test")
        
        assert last is not None
        assert last.workflow_id == "persist_test"
        assert last.data["key"] == "value"


class TestLogicLayerMonitor:
    """Tests for the LogicLayerMonitor."""
    
    def test_check_all_returns_dict(self):
        """Test that check_all returns a dictionary."""
        monitor = LogicLayerMonitor()
        result = monitor.check_all()
        
        assert isinstance(result, dict)
        assert len(result) > 0
    
    def test_expected_providers(self):
        """Test that expected providers are present."""
        monitor = LogicLayerMonitor()
        result = monitor.check_all()
        
        # Check for known logic providers
        expected = ["kwil", "weavedb", "glacier"]
        for name in expected:
            assert name in result, f"Missing provider: {name}"
    
    def test_provider_status_structure(self):
        """Test that provider status has expected structure."""
        monitor = LogicLayerMonitor()
        result = monitor.check_all()
        
        for name, info in result.items():
            assert "status" in info
            assert "latency_ms" in info
            assert "description" in info


class TestRunDemoWorkflow:
    """Tests for the run_demo_workflow function."""
    
    def test_demo_workflow_completes(self):
        """Test that demo workflow eventually completes."""
        logs = []
        result = run_demo_workflow(log_fn=logs.append)
        
        # Should complete (after recovery from simulated crash)
        assert result.status == WorkflowStatus.COMPLETED
        assert result.recovered is True
    
    def test_demo_workflow_logs(self):
        """Test that demo workflow produces logs."""
        logs = []
        run_demo_workflow(log_fn=logs.append)
        
        # Should have produced some log output
        assert len(logs) > 0
        
        # Should mention crash and recovery
        log_text = " ".join(logs)
        assert "crash" in log_text.lower() or "RECOVERY" in log_text


# Run with: python -m pytest tests/test_workflows.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
