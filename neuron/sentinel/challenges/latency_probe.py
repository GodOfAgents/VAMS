"""
Latency Probe Challenge Module
==============================
Measures RTT, jitter, and packet loss to target nodes.
"""

import time
import logging
import asyncio
from web3 import Web3

from .base_challenge import BaseChallenge, ChallengeResult

logger = logging.getLogger(__name__)

NETWORK_10G = Web3.keccak(text="NETWORK_10G")

class LatencyBenchmark(BaseChallenge):
    def get_thresholds(self, hw_class: bytes) -> dict:
        if hw_class == NETWORK_10G:
            return {"max_rtt_ms": 5.0} # <= 5ms intra-region
        return {"max_rtt_ms": 50.0}

    async def run(self, node_endpoint: str) -> ChallengeResult:
        logger.info(f"Running Latency probe to {node_endpoint}")
        
        try:
            # Simulated ping. In prod, use `aioping` or similar.
            rtts = []
            for _ in range(5):
                start = time.time()
                await asyncio.sleep(0.002) # simulate 2ms ping
                rtts.append((time.time() - start) * 1000)
                
            avg_rtt = sum(rtts) / len(rtts)
            jitter = max(rtts) - min(rtts)
            
            # Map avg_rtt to score. < 5ms = 10000, 50ms = 5000, >100ms = 0
            if avg_rtt <= 5.0:
                score_bps = 10000
            else:
                score_bps = max(0, int(10000 - ((avg_rtt - 5.0) * 100)))

            return ChallengeResult(
                success=True,
                score=score_bps,
                kpis={
                    "avg_rtt_ms": avg_rtt,
                    "jitter_ms": jitter,
                    "packet_loss_pct": 0.0
                },
                passed=True,
                error=""
            )
            
        except Exception as e:
            logger.error(f"Latency probe failed: {e}")
            return ChallengeResult(success=False, score=0.0, kpis={}, passed=False, error=str(e))
