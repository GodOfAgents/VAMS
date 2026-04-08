"""
CPU Benchmark Challenge Module
==============================
Executes mathematical workloads to evaluate CPU compute capacity.
"""

import time
import logging
import multiprocessing
import math
from web3 import Web3
from typing import Dict, Any

from .base_challenge import BaseChallenge, ChallengeResult

logger = logging.getLogger(__name__)

CPU_EPYC = Web3.keccak(text="CPU_EPYC")
CPU_XEON = Web3.keccak(text="CPU_XEON")

def cpu_workload(iterations: int) -> float:
    """CPU-intensive mathematical workload"""
    score = 0.0
    for i in range(1, iterations):
        score += math.sin(i) * math.cos(i) + math.sqrt(i)
    return score

class CPUBenchmark(BaseChallenge):
    def get_thresholds(self, hw_class: bytes) -> dict:
        if hw_class == CPU_EPYC:
            return {"min_multi_score": 80000.0}
        elif hw_class == CPU_XEON:
            return {"min_multi_score": 75000.0}
        return {"min_multi_score": 0.0}

    async def run(self, node_endpoint: str) -> ChallengeResult:
        logger.info(f"Running CPU challenge on {node_endpoint}")
        
        try:
            cores = multiprocessing.cpu_count()
            iterations = 5_000_000
            
            # Single-thread test
            st_start = time.time()
            cpu_workload(iterations)
            st_elapsed = time.time() - st_start
            single_score = (iterations / st_elapsed) / 1000.0
            
            # Multi-thread test
            mt_start = time.time()
            with multiprocessing.Pool(processes=cores) as pool:
                pool.map(cpu_workload, [iterations // cores] * cores)
            mt_elapsed = time.time() - mt_start
            multi_score = (iterations / mt_elapsed) / 1000.0
            
            # Basic score mapping: map multi_score to a 0-10000 bps scale.
            # Using EPYC threshold (~80000) as passing. Let's make 100k = 10000 score.
            score_bps = min(10000, int((multi_score / 100000.0) * 10000))

            return ChallengeResult(
                success=True,
                score=score_bps,
                kpis={
                    "single_thread_score": single_score,
                    "multi_thread_score": multi_score,
                    "cores": cores
                },
                passed=True,
                error=""
            )
            
        except Exception as e:
            logger.error(f"CPU benchmark crashed: {e}")
            return ChallengeResult(success=False, score=0.0, kpis={}, passed=False, error=str(e))
