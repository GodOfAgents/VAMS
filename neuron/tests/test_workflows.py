"""
VAMS Neuron - Workflow Tests (DBOS)
=====================================
Tests for the DBOS-native durable workflow engine (Layer 3).

Test strategy
-------------
- Unit-test each @DBOS.step() individually — fast, no Postgres needed
  when using DBOS TestClient which provides an in-memory Postgres via
  pytest-dbos / dbos.testing.
- Integration-test the full @DBOS.workflow() pipeline end-to-end.
- Verify idempotency via SetWorkflowID.
- Verify LogicLayerMonitor HTTP health checks (unchanged component).

Run with:
    cd neuron
    pip install dbos psycopg2-binary pytest pytest-asyncio
    python -m pytest tests/test_workflows.py -v
"""

import sys
import os
import time
import pytest
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── DBOS test harness ────────────────────────────────────────────────────────
import os
import sqlalchemy as sa
from dbos import DBOS

# Clean up any leftover database file
DB_FILE = "dbos_test_workflows.db"
if os.path.exists(DB_FILE):
    try:
        os.remove(DB_FILE)
    except OSError:
        pass

from workflows import (
    step_gather_data,
    step_run_inference,
    step_execute_action,
    step_report_result,
    vams_data_pipeline,
    run_demo_workflow,
    LogicLayerMonitor,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def dbos_client():
    """
    Session-scoped DBOS test client.
    Initialises file-based SQLite database with NullPool to run workflow tests.
    """
    DBOS.destroy()
    DBOS(config={
        "name": "vams-test-app",
        "system_database_url": f"sqlite:///{DB_FILE}",
        "db_engine_kwargs": {
            "poolclass": sa.NullPool
        }
    })
    DBOS.reset_system_database()
    DBOS.launch()
    
    yield None
    
    DBOS.destroy()
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
        except OSError:
            pass


# ─── Step unit tests ──────────────────────────────────────────────────────────

class TestSteps:
    """Unit tests for individual @DBOS.step() functions."""

    def test_gather_data_returns_required_keys(self, dbos_client):
        """step_gather_data() must return source, block, and timestamp."""
        result = asyncio.run(step_gather_data())
        assert isinstance(result, dict)
        assert "source" in result
        assert "block" in result
        assert "timestamp" in result

    def test_gather_data_source_is_celestia(self, dbos_client):
        """Default data source should be celestia (placeholder)."""
        result = asyncio.run(step_gather_data())
        assert result["source"] == "celestia"

    def test_run_inference_returns_prediction(self, dbos_client):
        """step_run_inference() must return prediction and confidence."""
        data = {"source": "celestia", "block": 1234, "timestamp": 0.0}
        result = asyncio.run(step_run_inference(data))
        assert "prediction" in result
        assert "confidence" in result
        assert isinstance(result["confidence"], float)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_run_inference_has_model_field(self, dbos_client):
        """Inference result must identify which model was used."""
        data = {"source": "celestia", "block": 1234, "timestamp": 0.0}
        result = asyncio.run(step_run_inference(data))
        assert "model" in result
        assert len(result["model"]) > 0

    def test_execute_action_returns_success(self, dbos_client):
        """step_execute_action() must report a status and tx_hash."""
        inference = {"prediction": "bullish", "confidence": 0.9, "model": "sn1"}
        result = asyncio.run(step_execute_action(inference))
        assert "status" in result
        assert result["status"] == "success"
        assert "tx_hash" in result

    def test_report_result_returns_string(self, dbos_client):
        """step_report_result() must return a non-empty string."""
        action = {"action": "log_prediction", "status": "success", "tx_hash": "0x"}
        result = asyncio.run(step_report_result(action))
        assert isinstance(result, str)
        assert len(result) > 0
        assert "success" in result


# ─── Full pipeline integration tests ─────────────────────────────────────────

class TestVamsDataPipeline:
    """Integration tests for the full @DBOS.workflow() pipeline."""

    def test_pipeline_completes_and_returns_string(self, dbos_client):
        """Full pipeline should run all 4 steps and return a result string."""
        result = asyncio.run(vams_data_pipeline())
        assert isinstance(result, str)
        assert "complete" in result.lower() or "success" in result.lower()

    def test_pipeline_result_contains_status(self, dbos_client):
        """Pipeline result string should include the action status."""
        result = asyncio.run(vams_data_pipeline())
        assert "success" in result

    def test_run_demo_workflow_public_api(self, dbos_client):
        """run_demo_workflow() public entry-point returns a result string."""
        logs = []
        result = run_demo_workflow(log_fn=logs.append)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_run_demo_workflow_emits_logs(self, dbos_client):
        """run_demo_workflow() should emit at least a start and complete log."""
        logs = []
        run_demo_workflow(log_fn=logs.append)
        assert len(logs) >= 2
        log_text = " ".join(logs)
        assert "WORKFLOW" in log_text
        assert "Complete" in log_text or "complete" in log_text


# ─── Idempotency tests ────────────────────────────────────────────────────────

class TestWorkflowIdempotency:
    """Verify DBOS workflow ID idempotency guarantees."""

    def test_same_workflow_id_executes_once(self, dbos_client):
        """
        Calling vams_data_pipeline() twice with the same SetWorkflowID
        should return identical results (the second call is a no-op).
        """
        from dbos import SetWorkflowID

        async def run_both():
            wf_id = f"idempotent-test-{int(time.time() * 1000)}"
            with SetWorkflowID(wf_id):
                r1 = await vams_data_pipeline()
            with SetWorkflowID(wf_id):
                r2 = await vams_data_pipeline()
            return r1, r2

        r1, r2 = asyncio.run(run_both())
        # Both calls should produce the same result string
        assert r1 == r2

    def test_different_workflow_ids_are_independent(self, dbos_client):
        """Two different workflow IDs are independent executions."""
        from dbos import SetWorkflowID

        async def run_both():
            ts = int(time.time() * 1000)
            with SetWorkflowID(f"wf-a-{ts}"):
                r1 = await vams_data_pipeline()
            with SetWorkflowID(f"wf-b-{ts}"):
                r2 = await vams_data_pipeline()
            return r1, r2

        r1, r2 = asyncio.run(run_both())
        # Both succeed independently
        assert r1 is not None
        assert r2 is not None


# ─── LogicLayerMonitor tests (unchanged component) ───────────────────────────

class TestLogicLayerMonitor:
    """
    Tests for LogicLayerMonitor — pure HTTP health checks, no DBOS dependency.
    These tests do NOT require dbos_client.
    """

    def test_check_all_returns_dict(self):
        monitor = LogicLayerMonitor()
        result = monitor.check_all()
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_expected_providers_present(self):
        monitor = LogicLayerMonitor()
        result = monitor.check_all()
        for provider in ("kwil", "weavedb", "glacier"):
            assert provider in result, f"Missing provider: {provider}"

    def test_provider_status_structure(self):
        monitor = LogicLayerMonitor()
        result = monitor.check_all()
        for name, info in result.items():
            assert "status" in info, f"{name}: missing 'status'"
            assert "latency_ms" in info, f"{name}: missing 'latency_ms'"
            assert "description" in info, f"{name}: missing 'description'"
            assert info["status"] in ("healthy", "degraded", "offline"), (
                f"{name}: unexpected status '{info['status']}'"
            )


# Run directly: python tests/test_workflows.py
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
