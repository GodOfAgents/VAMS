import os
import time
import json
import base64
import requests
from typing import Optional, Dict, Any, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

class IagonStorageError(Exception):
    pass

class IagonStorageSDK:
    """
    VAMS SDK Client for Iagon (Cardano-Native) eUTXO Storage.

    This SDK fulfills the Pillar 5 (Permanent Memory) and Pillar 1 (Durable Execution)
    requirements by dispersing AES-GCM encrypted tensors and checkpoint states across
    Iagon's distributed node network.
    
    Operations:
    - Encrypt payload locally
    - Submit blob to Iagon REST endpoint
    - Instantiate Identity & Authentication
    """

    def __init__(self, api_key: str = None, encryption_key: bytes = None, timeout: int = 15):
        self.api_url = os.getenv("IAGON_API_URL", "https://api.iagon.com/v1")
        self.api_key = api_key or os.getenv("IAGON_API_KEY", "")
        self.timeout = timeout
        self.mock_mode = os.getenv("IAGON_MOCK_MODE", "true").lower() == "true"
        
        # Identity-derived symmetric encryption key (AES-256)
        # In a real node, this is derived from the ECDSA private key using HKDF
        self.encryption_key = encryption_key or os.urandom(32)
        
        if not self.api_key and not self.mock_mode:
            raise IagonStorageError("IAGON_API_KEY must be provided or mock mode enabled")

    def _encrypt(self, payload: str) -> Tuple[bytes, bytes]:
        """Encrypt payload using AES-GCM (256-bit). Returns (nonce, ciphertext_with_tag)."""
        aesgcm = AESGCM(self.encryption_key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, payload.encode('utf-8'), None)
        return nonce, ciphertext

    def _decrypt(self, nonce: bytes, ciphertext: bytes) -> str:
        """Decrypt payload using AES-GCM."""
        aesgcm = AESGCM(self.encryption_key)
        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext.decode('utf-8')
        except InvalidTag:
            raise IagonStorageError("Decryption failed: Invalid tag (data tampered or wrong key)")

    def store_checkpoint(self, checkpoint_id: str, data: Dict[str, Any]) -> str:
        """
        Encrypt and store a DBOS checkpoint on Iagon.
        Returns the Iagon Resource Identifier (IRI).
        """
        payload = json.dumps(data)
        nonce, ciphertext = self._encrypt(payload)

        # Prepare HTTP body representation
        encoded_nonce = base64.b64encode(nonce).decode('utf-8')
        encoded_cipher = base64.b64encode(ciphertext).decode('utf-8')

        blob_payload = {
            "checkpoint_id": checkpoint_id,
            "nonce": encoded_nonce,
            "data": encoded_cipher
        }

        if self.mock_mode:
            # Simulate network latency and return mock IRI
            time.sleep(0.4)
            hash_suffix = base64.b64encode(os.urandom(8)).decode('utf-8').replace('=', '')[:8]
            return f"iagon://cardano-mainnet/{checkpoint_id}_{hash_suffix}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                f"{self.api_url}/storage/upload",
                json=blob_payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            return result.get("iri")
        except requests.exceptions.RequestException as e:
            raise IagonStorageError(f"Failed to upload to Iagon: {str(e)}")

    def retrieve_checkpoint(self, iri: str) -> Dict[str, Any]:
        """Retrieve and decrypt a checkpoint by IRI."""
        if self.mock_mode:
            raise IagonStorageError("Mock mode: cannot retrieve dynamic IRIs unless mocked locally")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            response = requests.get(
                f"{self.api_url}/storage/download/{iri}",
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            nonce = base64.b64decode(data['nonce'])
            ciphertext = base64.b64decode(data['data'])

            plaintext = self._decrypt(nonce, ciphertext)
            return json.loads(plaintext)
            
        except requests.exceptions.RequestException as e:
            raise IagonStorageError(f"Failed to retrieve from Iagon: {str(e)}")
        except KeyError:
             raise IagonStorageError("Malformed response from Iagon API")

if __name__ == "__main__":
    # Internal execution test
    os.environ["IAGON_MOCK_MODE"] = "true"
    sdk = IagonStorageSDK(encryption_key=os.urandom(32))
    
    test_data = {"agent_id": "nexus-9", "hp": 100, "status": "active"}
    iri = sdk.store_checkpoint("chk_123", test_data)
    print(f"Stored mock checkpoint at IRI: {iri}")
