"""
VAMS DA Models
==============
Shared data models for the multi-DA performance audit layer.
"""

import time
import hashlib
import json
import math
import re
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List


SENSITIVE_KPI_KEY_FRAGMENTS = (
    "authorization",
    "cookie",
    "mnemonic",
    "password",
    "private",
    "prompt",
    "raw_",
    "request_body",
    "response_body",
    "secret",
    "token",
    "transcript",
    "world_state_trace",
)
MAX_PUBLIC_KPI_COUNT = 64
MAX_PUBLIC_KPI_KEY_LENGTH = 64
MAX_PUBLIC_KPI_ABS_VALUE = 1e18
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PUBLIC_CHALLENGE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
MAX_PUBLIC_IDENTIFIER_LENGTH = 256
MAX_PUBLIC_METRICS_SCORE = 10_000
MAX_PUBLIC_TIMESTAMP = 2**63 - 1
MAX_PUBLIC_DURATION_SECONDS = 86_400.0


def pseudonymize_public_identifier(value: Any, domain: str) -> str:
    """Return a domain-separated identifier without archiving caller input."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{domain} identifier must be a non-empty string")
    normalized = value.strip()
    if len(normalized) > MAX_PUBLIC_IDENTIFIER_LENGTH:
        raise ValueError(f"{domain} identifier exceeds the public telemetry limit")
    return hashlib.sha256(
        b"vams-public-audit-id-v1\x00"
        + domain.encode("ascii")
        + b"\x00"
        + normalized.encode("utf-8")
    ).hexdigest()


def normalize_public_identifier(value: Any, domain: str) -> str:
    """Preserve existing pseudonyms and pseudonymize every other identifier."""
    if isinstance(value, str) and HASH_PATTERN.fullmatch(value.lower()):
        return value.lower()
    return pseudonymize_public_identifier(value, domain)


def sanitize_public_challenge_type(value: Any) -> str:
    """Accept only bounded machine-readable challenge categories."""
    if not isinstance(value, str) or PUBLIC_CHALLENGE_PATTERN.fullmatch(value) is None:
        raise ValueError("challengeType must be a bounded lowercase machine identifier")
    return value


def _bounded_public_int(value: Any, label: str, maximum: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= maximum
    ):
        raise ValueError(f"{label} must be an integer between 0 and {maximum}")
    return value


def _bounded_public_duration(value: Any) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or not 0.0 <= float(value) <= MAX_PUBLIC_DURATION_SECONDS
    ):
        raise ValueError(
            "duration must be finite and between 0 and 86400 seconds"
        )
    return float(value)


def _public_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def sanitize_public_kpis(kpis: Any) -> Dict[str, Any]:
    """Return bounded scalar KPIs that are safe for public DA archival."""
    if not isinstance(kpis, dict):
        return {}

    sanitized: Dict[str, Any] = {}
    for raw_key in sorted(kpis, key=str):
        if len(sanitized) >= MAX_PUBLIC_KPI_COUNT:
            break

        key = str(raw_key)
        normalized_key = key.lower()
        if not key or len(key) > MAX_PUBLIC_KPI_KEY_LENGTH:
            continue
        if any(fragment in normalized_key for fragment in SENSITIVE_KPI_KEY_FRAGMENTS):
            continue

        value = kpis[raw_key]
        if isinstance(value, bool):
            sanitized[key] = value
        elif isinstance(value, int) and abs(value) <= MAX_PUBLIC_KPI_ABS_VALUE:
            sanitized[key] = value
        elif (
            isinstance(value, float)
            and math.isfinite(value)
            and abs(value) <= MAX_PUBLIC_KPI_ABS_VALUE
        ):
            sanitized[key] = value
    return sanitized


def _finite_number(value: Any, minimum: float, maximum: float) -> Optional[Any]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(float(value)) or not minimum <= float(value) <= maximum:
        return None
    return value


def sanitize_public_telemetry(report: Any) -> Dict[str, Any]:
    """Allowlist bounded telemetry fields; never archive arbitrary nested data."""
    if not isinstance(report, dict):
        return {}

    sanitized: Dict[str, Any] = {}
    fidelity = report.get("worldStateFidelity")
    if isinstance(fidelity, dict):
        clean_fidelity: Dict[str, Any] = {}
        for key in ("agent_state_hash", "verified_external_state_hash"):
            value = fidelity.get(key)
            if isinstance(value, str) and HASH_PATTERN.fullmatch(value.lower()):
                clean_fidelity[key] = value.lower()
        for key in (
            "state_fidelity_score",
            "staleness_score",
            "false_progress_score",
        ):
            value = _finite_number(fidelity.get(key), 0.0, 1.0)
            if value is not None:
                clean_fidelity[key] = value
        for key in ("first_state_divergence_step", "first_invalid_action_step"):
            value = fidelity.get(key)
            if value is None or (isinstance(value, int) and not isinstance(value, bool) and value >= 0):
                clean_fidelity[key] = value
        if fidelity.get("status") == "telemetry_only":
            clean_fidelity["status"] = "telemetry_only"
        if fidelity.get("rewardImpact") == "none":
            clean_fidelity["rewardImpact"] = "none"
        if fidelity.get("regionalBonusImpact") == "none":
            clean_fidelity["regionalBonusImpact"] = "none"
        if clean_fidelity:
            sanitized["worldStateFidelity"] = clean_fidelity

    gain = report.get("continualLearningGain")
    if isinstance(gain, dict):
        clean_gain: Dict[str, Any] = {}
        for key in ("statefulReward", "statelessReward", "gain"):
            value = _finite_number(gain.get(key), -1e18, 1e18)
            if value is not None:
                clean_gain[key] = value
        if isinstance(gain.get("operationalFailureCandidate"), bool):
            clean_gain["operationalFailureCandidate"] = gain["operationalFailureCandidate"]
        if gain.get("status") == "telemetry_only":
            clean_gain["status"] = "telemetry_only"
        if gain.get("rewardImpact") == "none":
            clean_gain["rewardImpact"] = "none"
        if gain.get("regionalBonusImpact") == "none":
            clean_gain["regionalBonusImpact"] = "none"
        if clean_gain:
            sanitized["continualLearningGain"] = clean_gain

    anomaly_score = _finite_number(report.get("activation_anomaly_score"), 0.0, 1e12)
    if anomaly_score is not None:
        sanitized["activation_anomaly_score"] = anomaly_score
    if isinstance(report.get("adversarial_flag"), bool):
        sanitized["adversarial_flag"] = report["adversarial_flag"]

    return sanitized


class DAProtocol(Enum):
    """Supported DA layer protocols matching the VAMS Foundation Layer."""
    CELESTIA = "celestia"
    EIGEN_DA = "eigenda"
    NEAR_DA = "near"
    POLYGON_DAC = "polygon"
    AVAIL = "avail"
    IAGON = "iagon"


@dataclass
class DAReceipt:
    """Receipt returned after successful DA blob submission."""
    protocol: DAProtocol
    blob_id: str
    height: int
    commitment: str
    timestamp: float = field(default_factory=time.time)
    verified: bool = False
    raw_response: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocol": self.protocol.value,
            "blob_id": self.blob_id,
            "height": self.height,
            "commitment": self.commitment,
            "timestamp": self.timestamp,
            "verified": self.verified,
        }


@dataclass
class AuditReport:
    """
    Structured serialization format for Sentinel challenge reports
    intended for DA archival.
    """
    node_id: str
    sentinel_id: str
    challenge_type: str
    metrics_score: int
    passed: bool
    kpis: Dict[str, Any]
    timestamp: int
    duration: float
    da_target: DAProtocol = DAProtocol.CELESTIA
    telemetry: Dict[str, Any] = field(default_factory=dict)

    def serialize(self) -> bytes:
        """Deterministic JSON serialization for hashing."""
        payload = {
            "nodeId": normalize_public_identifier(self.node_id, "node"),
            "sentinelId": normalize_public_identifier(self.sentinel_id, "sentinel"),
            "challengeType": sanitize_public_challenge_type(self.challenge_type),
            "metricsScore": _bounded_public_int(
                self.metrics_score, "metricsScore", MAX_PUBLIC_METRICS_SCORE
            ),
            "passed": _public_bool(self.passed, "passed"),
            "kpis": sanitize_public_kpis(self.kpis),
            "telemetry": sanitize_public_telemetry(self.telemetry),
            "timestamp": _bounded_public_int(
                self.timestamp, "timestamp", MAX_PUBLIC_TIMESTAMP
            ),
            "duration": round(_bounded_public_duration(self.duration), 6),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def compute_hash(self) -> str:
        """SHA-256 hash of the deterministic serialization."""
        return "0x" + hashlib.sha256(self.serialize()).hexdigest()

    @classmethod
    def from_sentinel_report(cls, report: Dict[str, Any], da_target: DAProtocol = DAProtocol.CELESTIA) -> "AuditReport":
        """Construct from a raw Sentinel report dict."""
        return cls(
            node_id=normalize_public_identifier(report["nodeId"], "node"),
            sentinel_id=normalize_public_identifier(report["sentinelId"], "sentinel"),
            challenge_type=sanitize_public_challenge_type(report["challengeType"]),
            metrics_score=_bounded_public_int(
                report["metricsScore"], "metricsScore", MAX_PUBLIC_METRICS_SCORE
            ),
            passed=_public_bool(report["passed"], "passed"),
            kpis=sanitize_public_kpis(report.get("kpis", {})),
            timestamp=_bounded_public_int(
                report["timestamp"], "timestamp", MAX_PUBLIC_TIMESTAMP
            ),
            duration=_bounded_public_duration(report.get("duration", 0.0)),
            da_target=da_target,
            telemetry=sanitize_public_telemetry(report),
        )
