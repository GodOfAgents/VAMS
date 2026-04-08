"""
Base interface for all hardware benchmarking challenges.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class ChallengeResult:
    success: bool
    score: float
    kpis: Dict[str, float]
    passed: bool
    error: str = ""

class BaseChallenge(ABC):
    @abstractmethod
    async def run(self, node_endpoint: str) -> ChallengeResult:
        """Execute the challenge against a target node and return KPI results."""
        pass
    
    @abstractmethod
    def get_thresholds(self, hw_class: bytes) -> dict:
        """Return pass/fail thresholds for the hardware class (bytes32 id)."""
        pass
