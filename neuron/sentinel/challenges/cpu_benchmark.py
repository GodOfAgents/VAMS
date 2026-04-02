"""
CPU Benchmark Challenge Module
==============================
Executes subprocess challenges to determine compute capacity.
Requires `sysbench` installed on target node.
"""

import subprocess
import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def run_cpu_challenge(max_prime: int = 20000, threads: int = 1) -> Dict[str, Any]:
    """
    Executes sysbench CPU test. Returns a payload with benchmark score.
    The benchmark score is defined as 'events per second'.
    """
    logger.info(f"Running CPU sysbench challenge (max_prime={max_prime}, threads={threads})")
    
    start_time = time.time()
    try:
        cmd = ["sysbench", "cpu", f"--cpu-max-prime={max_prime}", f"--threads={threads}", "run"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Parse output for 'events per second:'
        events_per_sec = 0.0
        for line in result.stdout.split('\n'):
            if "events per second:" in line:
                val = line.split("events per second:")[1].strip()
                events_per_sec = float(val)
                break
                
        latency_ms = (time.time() - start_time) * 1000
        
        return {
            "success": True,
            "score": events_per_sec, 
            "metric": "events_per_sec",
            "latency_ms": latency_ms,
            "raw_output": result.stdout[:200] # just leading chars
        }
        
    except subprocess.CalledProcessError as e:
        logger.error(f"CPU benchmark failed: {e.stderr}")
        return {
            "success": False,
            "score": 0.0,
            "error": "sysbench execution failed",
            "stderr": str(e.stderr)
        }
    except FileNotFoundError:
        logger.error("sysbench not found on system.")
        return {
            "success": False,
            "score": 0.0,
            "error": "sysbench not installed"
        }
