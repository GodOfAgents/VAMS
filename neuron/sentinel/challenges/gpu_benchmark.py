"""
GPU Benchmark Challenge Module
==============================
Executes PyTorch matrix multiplications to estimate TFLOPS compute capacity.
Requires PyTorch with CUDA installed on target node.
"""

import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def run_gpu_challenge(matrix_size: int = 8192, iterations: int = 10) -> Dict[str, Any]:
    """
    Executes PyTorch multi-pass matrix multiplications to derive TFLOPS.
    """
    logger.info(f"Running GPU challenge (matrix_size={matrix_size}, runs={iterations})")
    
    try:
        import torch
    except ImportError:
        logger.error("PyTorch not installed, returning 0 score.")
        return {"success": False, "score": 0.0, "error": "PyTorch not installed"}
        
    if not torch.cuda.is_available():
        logger.error("CUDA not available, returning 0 score.")
        return {"success": False, "score": 0.0, "error": "CUDA not available"}

    try:
        device = torch.device('cuda')
        device_name = torch.cuda.get_device_name(0)
        
        # Warm-up pass to let GPU reach boost clock
        tmp_size = min(1024, matrix_size)
        a_warm = torch.randn(tmp_size, tmp_size, device=device)
        b_warm = torch.randn(tmp_size, tmp_size, device=device)
        for _ in range(3):
            _ = torch.matmul(a_warm, b_warm)
        torch.cuda.synchronize()

        # Main benchmark pass
        a = torch.randn(matrix_size, matrix_size, device=device)
        b = torch.randn(matrix_size, matrix_size, device=device)
        
        start_time = time.time()
        for _ in range(iterations):
            _ = torch.matmul(a, b)
        torch.cuda.synchronize()
        end_time = time.time()

        elapsed = end_time - start_time
        
        # Operations: 2 * N^3 per matmul
        total_flops = 2.0 * (matrix_size ** 3) * iterations
        tflops = (total_flops / elapsed) / 1e12

        return {
            "success": True,
            "score": tflops,
            "metric": "tflops",
            "latency_ms": elapsed * 1000,
            "device": device_name
        }
        
    except Exception as e:
        logger.error(f"GPU benchmark crashed: {e}")
        return {
            "success": False, 
            "score": 0.0, 
            "error": str(e)
        }
