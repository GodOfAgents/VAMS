"""
Storage IOPS Challenge Module
=============================
Executes `fio` storage benchmark to ensure disks meet SLA standards.
Requires `fio` on target node.
"""

import subprocess
import time
import json
import logging
import tempfile
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)

def run_storage_challenge(size: str = "250m", runtime: int = 10) -> Dict[str, Any]:
    """
    Executes flexible I/O tester (fio) for random read/write benchmark.
    Returns composite IOPS score.
    """
    logger.info(f"Running Storage IOPS challenge (size={size}, runtime={runtime}s)")

    # Execute in temporary directory to avoid clutter
    test_dir = tempfile.mkdtemp(prefix="vams_fio_")
    
    cmd = [
        "fio",
        "--name=vams_iops_test",
        f"--directory={test_dir}",
        "--ioengine=sync", # More compatible across environments than libaio
        "--iodepth=16",
        "--rw=randrw",
        "--rwmixread=75", # Standard mixed workload
        "--bs=4k",
        f"--size={size}",
        "--numjobs=1",
        f"--runtime={runtime}",
        "--time_based=1",
        "--group_reporting",
        "--output-format=json"
    ]
    
    start_time = time.time()
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        if res.returncode != 0:
            logger.error(f"fio failed: {res.stderr}")
            return {"success": False, "score": 0.0, "error": res.stderr[:500]}
            
        data = json.loads(res.stdout)
        
        jobs = data.get("jobs", [{}])[0]
        read_iops = float(jobs.get("read", {}).get("iops", 0.0))
        write_iops = float(jobs.get("write", {}).get("iops", 0.0))
        total_iops = read_iops + write_iops
        
        latency_ms = (time.time() - start_time) * 1000
        
        return {
            "success": True,
            "score": total_iops,
            "metric": "iops",
            "read_iops": read_iops,
            "write_iops": write_iops,
            "latency_ms": latency_ms
        }
        
    except FileNotFoundError:
        logger.error("fio not found on system.")
        return {"success": False, "score": 0.0, "error": "fio not installed"}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse fio JSON output: {e}")
        return {"success": False, "score": 0.0, "error": f"JSON decode error: {e}"}
    except Exception as e:
        return {"success": False, "score": 0.0, "error": str(e)}
    finally:
        # Cleanup temporary files
        try:
            for f in os.listdir(test_dir):
                os.remove(os.path.join(test_dir, f))
            os.rmdir(test_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup {test_dir}: {e}")
