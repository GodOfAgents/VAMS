"""
Network Latency & Reachability Probe
====================================
Tests network reachability of a provider node's endpoint.
Used strictly for SLA uptime monitoring.
"""

import time
import requests
import socket
import logging
from urllib.parse import urlparse
from typing import Dict, Any

logger = logging.getLogger(__name__)

def run_latency_challenge(target_endpoint: str, timeout: int = 5) -> Dict[str, Any]:
    """
    Executes a latency ping to a target endpoint. 
    It supports HTTP(S) and raw sockets (host:port).
    Returns a score inversely proportional to the latency.
    """
    logger.info(f"Running Latency probe on {target_endpoint}")

    if not target_endpoint:
        return {"success": False, "score": 0.0, "error": "target_endpoint is empty"}

    target_endpoint = target_endpoint.strip()
    
    start_time = time.time()
    try:
        is_success = False
        
        # Support full URLs for checking API uptime
        if target_endpoint.startswith("http://") or target_endpoint.startswith("https://"):
            res = requests.get(target_endpoint, timeout=timeout)
            is_success = 200 <= res.status_code < 500
        else:
            # Support raw TCP socket (host:port) for instances
            parts = target_endpoint.split(":")
            if len(parts) == 2:
                host, port = parts[0], int(parts[1])
                with socket.create_connection((host, port), timeout=timeout):
                    is_success = True
            else:
                return {"success": False, "score": 0.0, "error": "Invalid target format (use http:// or host:port)"}
                
        latency_ms = (time.time() - start_time) * 1000
        
        if is_success:
            # Score formula: inverse of latency to incentivize low-latency nodes.
            # Max score is 1000 (1ms or less).
            score = 1000.0 / max(1.0, latency_ms)
            return {
                "success": True,
                "score": score,
                "metric": "inv_latency_score",
                "latency_ms": latency_ms
            }
        else:
             return {
                "success": False,
                "score": 0.0,
                "metric": "inv_latency_score",
                "error": "Endpoint refused connection or returned 5xx",
                "latency_ms": timeout * 1000
            }
            
    except requests.RequestException as re:
        logger.error(f"Latency probe failed for {target_endpoint}: {re}")
        return {"success": False, "score": 0.0, "error": f"HTTP Request failed: {re}"}
    except socket.error as se:
        logger.error(f"Socket connection failed for {target_endpoint}: {se}")
        return {"success": False, "score": 0.0, "error": f"Socket failed: {se}"}
    except Exception as e:
        logger.error(f"Unexpected latency error for {target_endpoint}: {e}")
        return {"success": False, "score": 0.0, "error": f"Unexpected error: {e}"}
