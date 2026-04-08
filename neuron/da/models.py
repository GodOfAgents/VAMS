"""
VAMS DA Models
==============
Shared data models for the multi-DA performance audit layer.
"""

import time
import hashlib
import json
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List


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

    def serialize(self) -> bytes:
        """Deterministic JSON serialization for hashing."""
        payload = {
            "nodeId": self.node_id,
            "sentinelId": self.sentinel_id,
            "challengeType": self.challenge_type,
            "metricsScore": self.metrics_score,
            "passed": self.passed,
            "kpis": self.kpis,
            "timestamp": self.timestamp,
            "duration": round(self.duration, 6),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def compute_hash(self) -> str:
        """SHA-256 hash of the deterministic serialization."""
        return "0x" + hashlib.sha256(self.serialize()).hexdigest()

    @classmethod
    def from_sentinel_report(cls, report: Dict[str, Any], da_target: DAProtocol = DAProtocol.CELESTIA) -> "AuditReport":
        """Construct from a raw Sentinel report dict."""
        return cls(
            node_id=report["nodeId"],
            sentinel_id=report["sentinelId"],
            challenge_type=report["challengeType"],
            metrics_score=report["metricsScore"],
            passed=report["passed"],
            kpis=report.get("kpis", {}),
            timestamp=report["timestamp"],
            duration=report.get("duration", 0.0),
            da_target=da_target,
        )
