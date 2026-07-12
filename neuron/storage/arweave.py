import os
import requests
import json
import logging
from typing import Optional, Dict, Any

from neuron.runtime_safety import require_not_live_mock

logger = logging.getLogger("VAMSArweave")

class ArweaveStorage:
    """
    Permanent Memory Interface (Pillar 5).
    Uses Arweave (via Irys bundler or direct gateway) for immutable agent logs.
    """
    
    GATEWAY_URL = "https://arweave.net"
    IRYS_NODE = "https://node2.irys.xyz"
    
    def __init__(self, key: Optional[str] = None):
        self.key = key or os.getenv("VAMS_IRYS_KEY")
        self.mock_mode = True
        require_not_live_mock("ArweaveStorage upload", self.mock_mode)
        logger.info(
            "Arweave/Irys upload is unavailable; local execution remains mock-only."
        )

    def store_memory(self, agent_id: str, data: Dict[str, Any], tags: Optional[Dict[str, str]] = None) -> str:
        """
        Store data permanently.
        Returns: Arweave Transaction ID (TXID).
        """
        if self.mock_mode:
            # Simulate upload
            import hashlib
            payload = json.dumps(data).encode()
            mock_tx = hashlib.sha256(payload).hexdigest()[:43] # Arweave IDs are 43 chars usually
            logger.info(f"[MOCK] Stored memory to Arweave: {mock_tx}")
            return mock_tx
            
        raise RuntimeError("Arweave/Irys live upload is not implemented")

    def retrieve_memory(self, tx_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve data from Arweave gateway.
        This works for ANY valid Arweave TX, not just mock ones.
        """
        if tx_id.startswith("mock_tx") or len(tx_id) != 43:
            logger.info(f"Skipping retrieval for mock TX: {tx_id}")
            return None
            
        try:
            url = f"{self.GATEWAY_URL}/{tx_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {"raw_content": response.text}
            else:
                logger.warning(f"Arweave fetch failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving from Arweave: {e}")
            return None

if __name__ == "__main__":
    # Test read
    # Example TX: VAMS whitepaper or random transaction
    storage = ArweaveStorage()
    # Using a known Arweave TX for testing (Hello World or similar)
    # This is a random meaningful TX from Arweave (e.g. initial block or similar) just for read test
    # But let's just instantiate.
    print(f"Arweave Storage initialized. Mock: {storage.mock_mode}")
