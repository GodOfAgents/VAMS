"""
Data Availability Publisher for Sentinel Reports
===============================================
Publishes the signed Sentinel hardware benchmark reports to Celestia DA.
"""

import json
import logging
from typing import Dict, Any

from sdk.celestia import CelestiaDA, CelestiaNetwork

logger = logging.getLogger(__name__)

class DAPublisher:
    """
    Handles publishing Sentinel reports to the Celestia Data Availability network.
    The reports act as an immutable audit trail for programmatic slashing.
    """
    def __init__(self, rpc_url: str = "https://rpc-mocha.pops.one"):
        self.da = CelestiaDA(rpc_url=rpc_url, network=CelestiaNetwork.MOCHA)
        
    def publish_report(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes a Sentinel report dictionary, serializes it, and publishes it
        as a blob to the VAMS namespace on Celestia Mocha testnet.
        """
        try:
            # Serialize payload deterministically
            payload_bytes = json.dumps(report, sort_keys=True).encode("utf-8")
            
            logger.info(f"Publishing Sentinel Report to DA [Size: {len(payload_bytes)} bytes]")
            
            submission = self.da.submit_blob(payload_bytes)
            
            return {
                "success": True,
                "da_height": submission.height,
                "da_commitment": submission.commitment,
                "da_namespace": submission.namespace,
                "size": submission.size_bytes
            }
        except Exception as e:
            logger.error(f"Failed to publish Sentinel report to DA: {e}")
            return {
                "success": False,
                "error": str(e)
            }
