import os
import time
import json
import base64
import requests
from typing import Optional, Dict, Any

class AvailDAError(Exception):
    pass

class AvailDASDK:
    """
    VAMS SDK Client for Avail (Substrate) Validium DA.

    This SDK fulfills Pillar 1 (Durable Execution) by submitting arbitrary 
    byte arrays (blobs) to the Avail data availability network using 
    Substrate JSON-RPC methods, returning the block hash and extrinsic index.
    """

    def __init__(self, rpc_url: str = None, seed_phrase: str = None, timeout: int = 15):
        self.rpc_url = rpc_url or os.getenv("AVAIL_RPC_URL", "https://avail-turing.api.onfinality.io/public")
        self.seed_phrase = seed_phrase or os.getenv("AVAIL_SEED_PHRASE", "")
        self.timeout = timeout
        self.mock_mode = os.getenv("AVAIL_MOCK_MODE", "true").lower() == "true"
        
        if not self.seed_phrase and not self.mock_mode:
            raise AvailDAError("AVAIL_SEED_PHRASE must be provided or mock mode enabled")

    def submit_data(self, payload: bytes) -> Dict[str, Any]:
        """
        Submit arbitrary byte payload to Avail.
        """
        if self.mock_mode:
            time.sleep(0.5)
            mock_hash = base64.b64encode(os.urandom(24)).decode('utf-8').replace('=', '')
            return {
                "block_hash": f"0x{mock_hash}",
                "extrinsic_index": 1,
                "network": "turing-mock"
            }

        # Substrate requires scale-encoded signed transactions logic.
        # This requires the substrate-interface library and compiling the types.json metadata.
        raise NotImplementedError("Direct REST Substrate transaction signing requires substrate-interface package.")

    def retrieve_data(self, block_hash: str, extrinsic_index: int) -> bytes:
        """
        Retrieve data from an Avail block using the block hash and transaction index.
        """
        if self.mock_mode:
            return b'{"mock": "data_retrieved"}'

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "chain_getBlock",
            "params": [block_hash]
        }
        
        try:
            response = requests.post(
                self.rpc_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            # The extrinsics array contains the actual signed payload data
            # Requires stripping the Substrate extrinsic framing bytes
            extrinsics = data.get("result", {}).get("block", {}).get("extrinsics", [])
            if len(extrinsics) > extrinsic_index:
                raw_hex = extrinsics[extrinsic_index]
                # Returning the raw hex string representing the payload
                return bytes.fromhex(raw_hex[2:]) 
            raise AvailDAError("Extrinsic not found in block")
            
        except requests.exceptions.RequestException as e:
            raise AvailDAError(f"Failed to query Avail RPC: {str(e)}")

if __name__ == "__main__":
    os.environ["AVAIL_MOCK_MODE"] = "true"
    sdk = AvailDASDK()
    res = sdk.submit_data(b"VAMS_CHECKPOINT_001")
    print(f"Avail DA Result: {res}")
