import os
import time
import json
import base64
import requests
from typing import Optional, Dict, Any, Tuple, Mapping
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

from neuron.runtime_safety import (
    ImmutableRuntimeConfiguration,
    LiveModeSafetyError,
    RuntimePolicy,
    load_runtime_policy,
    resolve_component_mock_mode,
)

class IagonStorageError(Exception):
    pass

IAGON_MOCK_VARIABLE = "IAGON_MOCK_MODE"


class IagonStorageSDK(ImmutableRuntimeConfiguration):
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

    _immutable_runtime_fields = frozenset(
        {"api_url", "api_key", "timeout", "mock_mode", "runtime_policy", "encryption_key"}
    )

    def __init__(self, api_key: str = None, encryption_key: bytes = None, timeout: int = 15, mock_mode: Optional[bool] = None, *, environ: Optional[Mapping[str, str]] = None, policy: Optional[RuntimePolicy] = None):
        source = os.environ if environ is None else environ
        self.runtime_policy = policy or load_runtime_policy(source)
        self.mock_mode = resolve_component_mock_mode(
            "IagonStorageSDK",
            IAGON_MOCK_VARIABLE,
            mock_mode,
            policy=self.runtime_policy,
            environ=source,
        )
        self.api_url = source.get("IAGON_API_URL", "")
        self.api_key = api_key if api_key is not None else source.get("IAGON_API_KEY", "")
        self.timeout = timeout
        if self.runtime_policy.is_live:
            raise LiveModeSafetyError(
                "IagonStorageSDK live execution is disabled until checkpoint identity, "
                "durability, and exact authenticated read-back are implemented"
            )
        
        # Identity-derived symmetric encryption key (AES-256)
        # In a real node, this is derived from the ECDSA private key using HKDF
        self.encryption_key = encryption_key or os.urandom(32)
        
        if not self.mock_mode and not self.api_key:
            raise IagonStorageError("IAGON_API_KEY must be provided outside mock mode")
        if not self.mock_mode and not self.api_url:
            raise IagonStorageError("IAGON_API_URL must be provided outside mock mode")
        self._freeze_runtime_configuration()

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
            return f"simulated:iagon:{checkpoint_id}_{hash_suffix}"

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
            iri = result.get("iri") if isinstance(result, dict) else None
            if not isinstance(iri, str) or not iri:
                raise IagonStorageError("Iagon upload returned a malformed resource identifier")
            return iri
        except requests.exceptions.RequestException as exc:
            raise IagonStorageError("Iagon upload provider request failed") from exc

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
            
        except requests.exceptions.RequestException as exc:
            raise IagonStorageError("Iagon retrieval provider request failed") from exc
        except KeyError:
             raise IagonStorageError("Malformed response from Iagon API")

if __name__ == "__main__":
    policy = load_runtime_policy()
    if not policy.is_demo:
        raise LiveModeSafetyError("Iagon demo requires explicit VAMS_ENV=demo")
    sdk = IagonStorageSDK(
        encryption_key=os.urandom(32),
        mock_mode=True,
        policy=policy,
    )
    
    test_data = {"agent_id": "nexus-9", "hp": 100, "status": "active"}
    iri = sdk.store_checkpoint("chk_123", test_data)
    print(f"Stored mock checkpoint at IRI: {iri}")
