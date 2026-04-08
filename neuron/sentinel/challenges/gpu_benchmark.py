"""
GPU Benchmark Challenge Module
==============================
Executes PyTorch matrix multiplications to estimate TFLOPS compute capacity.
Requires PyTorch with CUDA installed on target node.
"""

import time
import logging
import asyncio
from typing import Dict, Any
from web3 import Web3

from .base_challenge import BaseChallenge, ChallengeResult

logger = logging.getLogger(__name__)

# Constants matching HardwareClasses.sol
GPU_H100 = Web3.keccak(text="GPU_H100")
GPU_A100 = Web3.keccak(text="GPU_A100")
GPU_L40S = Web3.keccak(text="GPU_L40S")
GPU_RTX_4090 = Web3.keccak(text="GPU_RTX_4090")

class GPUBenchmark(BaseChallenge):
    def get_thresholds(self, hw_class: bytes) -> dict:
        if hw_class == GPU_H100:
            return {"min_fp16_tflops": 1500.0}
        elif hw_class == GPU_A100:
            return {"min_fp16_tflops": 250.0}
        elif hw_class == GPU_L40S:
            return {"min_fp16_tflops": 150.0}
        elif hw_class == GPU_RTX_4090:
            return {"min_fp16_tflops": 80.0}
        return {"min_fp16_tflops": 0.0}

    async def run(self, node_endpoint: str) -> ChallengeResult:
        logger.info(f"Running GPU challenge on {node_endpoint}")
        
        try:
            import torch
        except ImportError:
            return ChallengeResult(success=False, score=0.0, kpis={}, passed=False, error="PyTorch not installed")
            
        if not torch.cuda.is_available():
            return ChallengeResult(success=False, score=0.0, kpis={}, passed=False, error="CUDA not available")

        try:
            device = torch.device('cuda')
            device_name = torch.cuda.get_device_name(0)
            
            # Use smaller default sizes for routine checks
            matrix_size = 8192
            iterations = 10
            
            # FP16 benchmark
            a_fp16 = torch.randn(matrix_size, matrix_size, dtype=torch.float16, device=device)
            b_fp16 = torch.randn(matrix_size, matrix_size, dtype=torch.float16, device=device)
            
            # Warm-up pass
            for _ in range(3):
                _ = torch.matmul(a_fp16, b_fp16)
            torch.cuda.synchronize()

            # Main benchmark pass
            start_time = time.time()
            for _ in range(iterations):
                _ = torch.matmul(a_fp16, b_fp16)
            torch.cuda.synchronize()
            elapsed = time.time() - start_time

            # Operations: 2 * N^3 per matmul
            total_flops = 2.0 * (matrix_size ** 3) * iterations
            fp16_tflops = (total_flops / elapsed) / 1e12

            # Basic score mapping: map tflops to a 0-10000 bps scale.
            # Using H100 as the top tier (1500 tflops = 10000 score)
            score_bps = min(10000, int((fp16_tflops / 1500.0) * 10000))

            return ChallengeResult(
                success=True,
                score=score_bps,
                kpis={
                    "fp16_tflops": fp16_tflops,
                    "latency_ms": elapsed * 1000,
                    "device": device_name
                },
                passed=True, # Evaluated up-stack based on get_thresholds
                error=""
            )
            
        except Exception as e:
            logger.error(f"GPU benchmark crashed: {e}")
            return ChallengeResult(success=False, score=0.0, kpis={}, passed=False, error=str(e))
