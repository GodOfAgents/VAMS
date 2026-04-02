"""
Memory Bandwidth Challenge Module
=================================
Executes `sysbench memory` to test RAM write speeds.
Requires `sysbench` on target node.
"""

import subprocess
import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def run_memory_challenge(block_size: str = "4K", total_size: str = "10G") -> Dict[str, Any]:
    """
    Executes sysbench memory benchmark. 
    Returns score as MiB/sec.
    """
    logger.info(f"Running Memory bandwidth challenge (bs={block_size}, total={total_size})")

    cmd = [
        "sysbench",
        "memory",
        f"--memory-block-size={block_size}",
        f"--memory-total-size={total_size}",
        "--memory-oper=write", # Memory write bandwidth is a standard SLA metric
        "run"
    ]
    
    start_time = time.time()
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        mib_sec = 0.0
        for line in res.stdout.split('\n'):
            # Looking for: "10240.00 MiB transferred (3200.50 MiB/sec)"
            if "transferred" in line and "MiB/sec" in line:
                try:
                    mib_sec_str = line.split("(")[1].split("MiB/sec")[0].strip()
                    mib_sec = float(mib_sec_str)
                except (IndexError, ValueError) as ve:
                    logger.warning(f"Failed to parse memory score from line: {line} -> {ve}")
                break
                
        latency_ms = (time.time() - start_time) * 1000
        
        return {
            "success": True,
            "score": mib_sec,
            "metric": "mib_ps",
            "latency_ms": latency_ms
        }
        
    except FileNotFoundError:
        logger.error("sysbench not found on system.")
        return {"success": False, "score": 0.0, "error": "sysbench not installed"}
    except subprocess.CalledProcessError as e:
        logger.error(f"Memory benchmark failed: {e.stderr}")
        return {"success": False, "score": 0.0, "error": f"sysbench failed: {e.stderr}"}
    except Exception as e:
        logger.error(f"Unexpected error in memory benchmark: {e}")
        return {"success": False, "score": 0.0, "error": str(e)}
