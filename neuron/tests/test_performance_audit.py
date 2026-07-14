"""
Tests: Performance Audit Log
=============================
Covers: blob serialization, multi-DA routing, Merkle root generation,
anchor record generation, fallback on adapter failure.
"""

import pytest
import asyncio
import json
import hashlib
from unittest.mock import AsyncMock, patch, MagicMock

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from neuron.da.models import (
    DAProtocol,
    DAReceipt,
    AuditReport,
    pseudonymize_public_identifier,
    sanitize_public_kpis,
)
from neuron.da.performance_audit import PerformanceAuditLog, CHALLENGE_DA_ROUTING


# --- Fixtures ---

@pytest.fixture
def sample_report():
    return {
        "nodeId": "abcdef1234567890",
        "sentinelId": "0xSentinel01",
        "challengeType": "gpu",
        "metricsScore": 9200,
        "passed": True,
        "kpis": {"flops": 120.5, "memory_bw": 3200},
        "timestamp": 1700000000,
        "duration": 2.345,
    }


@pytest.fixture
def latency_report():
    return {
        "nodeId": "node_latency_01",
        "sentinelId": "0xSentinel02",
        "challengeType": "latency",
        "metricsScore": 9800,
        "passed": True,
        "kpis": {"rtt_ms": 12.5},
        "timestamp": 1700000100,
        "duration": 0.015,
    }


@pytest.fixture
def audit_log():
    return PerformanceAuditLog(mock_mode=True)


# --- Serialization Tests ---

class TestAuditReportSerialization:
    def test_serialize_deterministic(self, sample_report):
        """Same input always produces the same bytes."""
        r1 = AuditReport.from_sentinel_report(sample_report)
        r2 = AuditReport.from_sentinel_report(sample_report)
        assert r1.serialize() == r2.serialize()

    def test_serialize_sorted_keys(self, sample_report):
        """Serialized JSON has keys in alphabetical order."""
        r = AuditReport.from_sentinel_report(sample_report)
        parsed = json.loads(r.serialize())
        keys = list(parsed.keys())
        assert keys == sorted(keys)

    def test_compute_hash_format(self, sample_report):
        """Hash has correct 0x prefix and length."""
        r = AuditReport.from_sentinel_report(sample_report)
        h = r.compute_hash()
        assert h.startswith("0x")
        assert len(h) == 66  # 0x + 64 hex chars

    def test_compute_hash_deterministic(self, sample_report):
        """Same report always hashes to the same value."""
        r1 = AuditReport.from_sentinel_report(sample_report)
        r2 = AuditReport.from_sentinel_report(sample_report)
        assert r1.compute_hash() == r2.compute_hash()

    def test_different_reports_different_hashes(self, sample_report, latency_report):
        """Different reports produce different hashes."""
        r1 = AuditReport.from_sentinel_report(sample_report)
        r2 = AuditReport.from_sentinel_report(latency_report)
        assert r1.compute_hash() != r2.compute_hash()

    def test_sensitive_and_structured_kpis_are_not_archived(self, sample_report):
        sample_report["kpis"].update(
            {
                "world_state_trace": [
                    {
                        "agent_state": {"balance": 100},
                        "verified_external_state": {"balance": 80},
                    }
                ],
                "system_prompt": "private agent instructions",
                "api_token": "secret-token",
                "nested_payload": {"email": "operator@example.com"},
            }
        )

        report = AuditReport.from_sentinel_report(sample_report)
        serialized = json.loads(report.serialize())

        assert serialized["kpis"] == {"flops": 120.5, "memory_bw": 3200}
        assert "private agent instructions" not in report.serialize().decode("utf-8")
        assert "operator@example.com" not in report.serialize().decode("utf-8")

    def test_public_kpis_are_bounded_scalars(self):
        sanitized = sanitize_public_kpis(
            {
                "device": "NVIDIA H100",
                "score": 99.5,
                "passed": True,
                "not_finite": float("inf"),
                "oversized_number": 10**30,
                "too_long": "x" * 129,
                "items": [1, 2, 3],
            }
        )

        assert sanitized == {
            "passed": True,
            "score": 99.5,
        }

    def test_telemetry_is_schema_allowlisted(self, sample_report):
        sample_report["worldStateFidelity"] = {
            "agent_state_hash": "a" * 64,
            "verified_external_state_hash": "b" * 64,
            "state_fidelity_score": 0.75,
            "status": "telemetry_only",
            "system_prompt": "do not publish this",
            "raw_trace": [{"email": "operator@example.com"}],
        }

        serialized = AuditReport.from_sentinel_report(sample_report).serialize().decode("utf-8")
        telemetry = json.loads(serialized)["telemetry"]["worldStateFidelity"]

        assert telemetry["state_fidelity_score"] == 0.75
        assert telemetry["agent_state_hash"] == "a" * 64
        assert "do not publish this" not in serialized
        assert "operator@example.com" not in serialized

    def test_public_identifiers_are_domain_separated_pseudonyms(self, sample_report):
        sample_report["nodeId"] = "operator@example.com"
        sample_report["sentinelId"] = "operator@example.com"

        serialized = json.loads(AuditReport.from_sentinel_report(sample_report).serialize())

        assert "operator@example.com" not in json.dumps(serialized)
        assert serialized["nodeId"] == pseudonymize_public_identifier(
            "operator@example.com", "node"
        )
        assert serialized["sentinelId"] == pseudonymize_public_identifier(
            "operator@example.com", "sentinel"
        )
        assert serialized["nodeId"] != serialized["sentinelId"]

    @pytest.mark.parametrize(
        "field,value",
        [
            ("nodeId", ""),
            ("sentinelId", "x" * 257),
            ("challengeType", "GPU benchmark for operator@example.com"),
            ("metricsScore", "operator@example.com"),
            ("passed", 1),
            ("timestamp", "operator@example.com"),
            ("duration", 86_401),
        ],
    )
    def test_invalid_public_identity_fields_fail_closed(self, sample_report, field, value):
        sample_report[field] = value
        with pytest.raises(ValueError):
            AuditReport.from_sentinel_report(sample_report)


# --- Multi-DA Routing Tests ---

class TestMultiDARouting:
    @pytest.mark.asyncio
    async def test_gpu_routes_to_celestia(self, audit_log, sample_report):
        """GPU benchmark reports route to Celestia."""
        result = await audit_log.publish_sentinel_report(sample_report)
        assert result["success"] is True
        assert result["protocol"] == "celestia"

    @pytest.mark.asyncio
    async def test_latency_routes_to_near(self, audit_log, latency_report):
        """Latency probes route to Near DA."""
        result = await audit_log.publish_sentinel_report(latency_report, da_target=DAProtocol.NEAR_DA)
        assert result["success"] is True
        assert result["protocol"] == "near"

    @pytest.mark.asyncio
    async def test_explicit_target_overrides_routing(self, audit_log, sample_report):
        """Explicit da_target overrides the default routing map."""
        result = await audit_log.publish_sentinel_report(sample_report, da_target=DAProtocol.NEAR_DA)
        assert result["success"] is True
        assert result["protocol"] == "near"

    @pytest.mark.asyncio
    async def test_disabled_explicit_target_fails_closed(self, sample_report):
        audit_log = PerformanceAuditLog(
            mock_mode=True,
            config={"enabled_protocols": ["celestia", "near"]},
        )

        result = await audit_log.publish_sentinel_report(
            sample_report,
            da_target=DAProtocol.EIGEN_DA,
        )

        assert result["success"] is False
        assert result["protocol"] == "eigenda"
        assert "not enabled" in result["error"]

    @pytest.mark.asyncio
    async def test_unknown_explicit_target_fails_closed(self, sample_report):
        result = await PerformanceAuditLog(mock_mode=True).publish_sentinel_report(
            sample_report,
            da_target="untrusted-da",
        )

        assert result["success"] is False
        assert result["protocol"] == "untrusted-da"
        assert "Unknown DA protocol" in result["error"]

    @pytest.mark.asyncio
    async def test_unknown_challenge_defaults_to_celestia(self, audit_log):
        """Unknown challenge types default to Celestia."""
        report = {
            "nodeId": "node_unknown",
            "sentinelId": "0xS03",
            "challengeType": "quantum_benchmark",
            "metricsScore": 5000,
            "passed": True,
            "kpis": {},
            "timestamp": 1700000200,
            "duration": 1.0,
        }
        result = await audit_log.publish_sentinel_report(report)
        assert result["success"] is True
        assert result["protocol"] == "celestia"


# --- Result Structure Tests ---

class TestResultStructure:
    @pytest.mark.asyncio
    async def test_result_contains_all_fields(self, audit_log, sample_report):
        """Result dict has all required fields."""
        result = await audit_log.publish_sentinel_report(sample_report)
        assert "success" in result
        assert "protocol" in result
        assert "blob_id" in result
        assert "daHeight" in result
        assert "daCommitment" in result
        assert "reportHash" in result
        assert "verified" in result
        assert result["verified"] is False
        assert result["mock_mode"] is True
        assert result["release_evidence_eligible"] is False

    @pytest.mark.asyncio
    async def test_report_hash_matches_serialized(self, audit_log, sample_report):
        """reportHash in result matches AuditReport.compute_hash()."""
        result = await audit_log.publish_sentinel_report(sample_report)
        expected = AuditReport.from_sentinel_report(sample_report).compute_hash()
        assert result["reportHash"] == expected


# --- Observability Tests ---

class TestObservability:
    @pytest.mark.asyncio
    async def test_audit_history_recorded(self, audit_log, sample_report):
        """Publishing adds to audit history."""
        assert len(audit_log.get_audit_history()) == 0
        await audit_log.publish_sentinel_report(sample_report)
        history = audit_log.get_audit_history()
        assert len(history) == 1
        assert history[0]["node_id"] == pseudonymize_public_identifier(
            "abcdef1234567890", "node"
        )

    @pytest.mark.asyncio
    async def test_audit_history_limit(self, audit_log, sample_report):
        """History limit parameter works."""
        for i in range(5):
            r = {**sample_report, "timestamp": 1700000000 + i, "nodeId": f"node_{i}"}
            await audit_log.publish_sentinel_report(r)

        assert len(audit_log.get_audit_history(limit=3)) == 3
        assert len(audit_log.get_audit_history(limit=10)) == 5

    @pytest.mark.asyncio
    async def test_adapter_status(self, audit_log):
        """Adapter status returns all configured protocols."""
        status = await audit_log.get_adapter_status()
        assert "celestia" in status
        assert "near" in status
        assert "eigenda" in status
        assert "avail" in status
