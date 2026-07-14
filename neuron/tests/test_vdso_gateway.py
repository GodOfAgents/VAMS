import hashlib
import json
import os
import time
import unittest
from base64 import b64encode
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ.setdefault("GATEWAY_ADMIN_PASSWORD", "SecureVDSOTestPassword123!")

from gateway import vdso as vdso_gateway
from gateway.server import app
from neuron.secp256k1 import (
    generate_private_key,
    public_key_bytes,
    sign_digest,
    sign_message,
)
from neuron.vdso.keccak import domain_hash
from neuron.vdso.service import VDSOCanaryService, VDSOMode
from neuron.vdso.sidecar import RecipientEnvelope, sidecar_content_hash


def hex32(value: bytes) -> str:
    return "0x" + value.hex()


class _SharedReplayStore(vdso_gateway.InMemoryReplayStore):
    """Atomic test double for an externally shared replay implementation."""

    shared = True


class VDSOGatewayTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"VAMS_ENV": "local"}, clear=False)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        vdso_gateway.service = VDSOCanaryService(
            mode=VDSOMode.SHADOW,
            height_provider=lambda _binding: 1_000,
        )
        vdso_gateway.replay_store = None
        vdso_gateway._local_replay_store.clear()
        self.client = TestClient(app)
        self.signing_key = generate_private_key()
        self.public_key = public_key_bytes(self.signing_key)

    def _intent_body(
        self,
        *,
        tier=0,
        hybrid=False,
        valid_until_height=2_000,
        program_byte=2,
    ):
        actor_root = domain_hash(b"VAMS:ACTOR:v1", (self.public_key,))
        return {
            "schema_version": 1,
            "actor_root": hex32(actor_root),
            "binding": {
                "state_domain": hex32(bytes.fromhex("08" * 32)),
                "host_authority": "polygon-amoy",
                "authority_epoch": 3,
            },
            "nonce": 1,
            "valid_until_height": valid_until_height,
            "program_id": hex32(bytes([program_byte]) * 32),
            "workflow_definition_hash": hex32(bytes.fromhex("03" * 32)),
            "input_commitment": hex32(bytes.fromhex("04" * 32)),
            "expected_output_commitment": hex32(bytes.fromhex("05" * 32)),
            "evidence_root": hex32(bytes.fromhex("06" * 32)),
            "sidecar_root": hex32(bytes.fromhex("07" * 32)),
            "signature_suite": (
                "secp256k1+ml-dsa-65" if hybrid else "secp256k1"
            ),
            "execution_tier": tier,
            "max_execution_units": 100_000,
            "max_settlement_cost": 5_000 if tier == 2 else 0,
            "accesses": [
                {
                    "object_id": hex32(bytes.fromhex("09" * 32)),
                    "mode": "read",
                    "expected_version": 1,
                }
            ],
        }

    def _simulation_body(self, **intent_kwargs):
        return {
            "intent": self._intent_body(**intent_kwargs),
            "current_height": 1_000,
        }

    @staticmethod
    def _encoded(body):
        return json.dumps(body, separators=(",", ":")).encode()

    def _headers(self, path, body_bytes, *, timestamp=None):
        timestamp_value = timestamp if timestamp is not None else str(int(time.time()))
        digest = hashlib.sha256(body_bytes).hexdigest()
        message = (
            f"VAMS_VDSO_AUTH:POST:{path}:{timestamp_value}:{digest}"
        ).encode()
        signature = sign_message(self.signing_key, message).hex()
        return {
            "Content-Type": "application/json",
            "X-VAMS-DID": "did:key:" + self.public_key.hex(),
            "X-VAMS-Signature": signature,
            "X-VAMS-Timestamp": timestamp_value,
            "X-VAMS-Content-SHA256": digest,
        }

    def _signed_intent_payload(self, intent_payload):
        intent = vdso_gateway.UnsignedIntentRequest.model_validate(
            intent_payload
        ).to_domain()
        classic_signature = sign_digest(self.signing_key, intent.intent_id).hex()
        return {
            "intent": intent_payload,
            "authorization": {
                "suite": intent_payload["signature_suite"],
                "secp256k1_public_key": "0x" + self.public_key.hex(),
                "secp256k1_signature": "0x" + classic_signature,
                "ml_dsa_65_public_key_b64": (
                    "cHEta2V5" if intent_payload["execution_tier"] == 2 else None
                ),
                "ml_dsa_65_signature_b64": (
                    "cHEtc2lnbmF0dXJl"
                    if intent_payload["execution_tier"] == 2
                    else None
                ),
            },
        }

    @staticmethod
    def _sidecar_payload():
        nonce = b"n" * 24
        ciphertext = b"ciphertext-only"
        envelopes = (RecipientEnvelope(bytes.fromhex("04" * 32), b"enc", b"wrapped"),)
        content_hash = sidecar_content_hash(
            schema_version=1,
            nonce=nonce,
            ciphertext=ciphertext,
            plaintext_root=bytes.fromhex("01" * 32),
            policy_hash=bytes.fromhex("03" * 32),
            recipient_envelopes=envelopes,
        )
        return {
            "schema_version": 1,
            "nonce_b64": b64encode(nonce).decode(),
            "ciphertext_b64": b64encode(ciphertext).decode(),
            "plaintext_root": hex32(bytes.fromhex("01" * 32)),
            "content_hash": hex32(content_hash),
            "policy_hash": hex32(bytes.fromhex("03" * 32)),
            "recipient_envelopes": [
                {
                    "recipient_id": hex32(envelopes[0].recipient_id),
                    "encapsulated_key_b64": b64encode(
                        envelopes[0].encapsulated_key
                    ).decode(),
                    "wrapped_key_b64": b64encode(envelopes[0].wrapped_key).decode(),
                }
            ],
        }

    def test_simulation_requires_body_bound_did_and_performs_no_write(self):
        path = "/v1/vdso/intents/simulate"
        body = self._encoded(self._simulation_body())
        response = self.client.post(path, content=body, headers=self._headers(path, body))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "simulated")
        self.assertEqual(response.json()["external_writes"], 0)

    def test_body_digest_mismatch_is_rejected(self):
        path = "/v1/vdso/intents/simulate"
        body = self._encoded(self._simulation_body())
        headers = self._headers(path, body)
        headers["X-VAMS-Content-SHA256"] = "00" * 32
        response = self.client.post(path, content=body, headers=headers)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "request body digest mismatch")

    def test_timestamp_must_be_canonical_integer_epoch_seconds(self):
        path = "/v1/vdso/intents/simulate"
        body = self._encoded(self._simulation_body())
        for value in ("NaN", "Inf", "1.5", "+1", "01", "9" * 100):
            with self.subTest(value=value):
                response = self.client.post(
                    path,
                    content=body,
                    headers=self._headers(path, body, timestamp=value),
                )
                self.assertEqual(response.status_code, 401, response.text)
                self.assertIn("canonical integer", response.json()["detail"])

    def test_signature_alias_cannot_bypass_atomic_replay_claim(self):
        path = "/v1/vdso/intents/simulate"
        body = self._encoded(self._simulation_body())
        timestamp = str(int(time.time()))
        first_headers = self._headers(path, body, timestamp=timestamp)
        second_headers = self._headers(path, body, timestamp=timestamp)
        self.assertNotEqual(
            first_headers["X-VAMS-Signature"], second_headers["X-VAMS-Signature"]
        )
        first = self.client.post(path, content=body, headers=first_headers)
        second = self.client.post(path, content=body, headers=second_headers)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 401, second.text)
        self.assertEqual(second.json()["detail"], "replayed VDSO request")

    def test_local_replay_claim_is_atomic_under_race(self):
        store = vdso_gateway.InMemoryReplayStore()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = tuple(
                pool.map(
                    lambda _index: store.check_and_record("same-key", 1_000, 2_000),
                    range(16),
                )
            )
        self.assertEqual(sum(results), 1)

    def test_live_auth_fails_closed_without_shared_replay_store(self):
        path = "/v1/vdso/intents/simulate"
        body = self._encoded(self._simulation_body())
        with patch.dict(os.environ, {"VAMS_ENV": "testnet"}, clear=False):
            response = self.client.post(
                path, content=body, headers=self._headers(path, body)
            )
        self.assertEqual(response.status_code, 503, response.text)
        self.assertIn("shared atomic replay", response.json()["detail"])

    def test_live_auth_uses_injected_shared_atomic_replay_store(self):
        path = "/v1/vdso/intents/simulate"
        body = self._encoded(self._simulation_body())
        vdso_gateway.replay_store = _SharedReplayStore()
        with patch.dict(os.environ, {"VAMS_ENV": "testnet"}, clear=False):
            response = self.client.post(
                path, content=body, headers=self._headers(path, body)
            )
        self.assertEqual(response.status_code, 200, response.text)

    def test_valid_until_height_uses_trusted_chain_height_not_wall_clock(self):
        path = "/v1/vdso/intents/simulate"
        valid_body = self._encoded(
            self._simulation_body(valid_until_height=1_000)
        )
        valid = self.client.post(
            path, content=valid_body, headers=self._headers(path, valid_body)
        )
        self.assertEqual(valid.status_code, 200, valid.text)

        expired_body = self._encoded(
            self._simulation_body(valid_until_height=999)
        )
        expired = self.client.post(
            path, content=expired_body, headers=self._headers(path, expired_body)
        )
        self.assertEqual(expired.status_code, 422, expired.text)
        self.assertEqual(expired.json()["detail"], "intent is expired")

    def test_client_height_must_match_trusted_host_source(self):
        path = "/v1/vdso/intents/simulate"
        payload = self._simulation_body()
        payload["current_height"] = 999
        body = self._encoded(payload)
        response = self.client.post(path, content=body, headers=self._headers(path, body))
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("trusted host height", response.json()["detail"])

    def test_gateway_rejects_cardano_consume_before_service_execution(self):
        path = "/v1/vdso/intents/simulate"
        payload = self._simulation_body(tier=2, hybrid=True)
        payload["intent"]["binding"]["host_authority"] = "cardano-pre-prod"
        payload["intent"]["accesses"][0]["mode"] = "consume"
        body = self._encoded(payload)
        response = self.client.post(path, content=body, headers=self._headers(path, body))
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("Cardano authority", response.json()["detail"])

    def test_gateway_rejects_polygon_reserve_tier_downgrade(self):
        path = "/v1/vdso/intents/simulate"
        payload = self._simulation_body()
        payload["intent"]["accesses"][0].update(
            {"mode": "reserve", "fencing_token": 11}
        )
        body = self._encoded(payload)
        response = self.client.post(path, content=body, headers=self._headers(path, body))
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("Tier 2 hybrid", response.json()["detail"])

    def test_gateway_rejects_read_tier_one_nonzero_settlement_cost(self):
        path = "/v1/vdso/intents/simulate"
        zero_cost_body = self._encoded(self._simulation_body(tier=1))
        accepted = self.client.post(
            path,
            content=zero_cost_body,
            headers=self._headers(path, zero_cost_body),
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)

        nonzero_cost_payload = self._simulation_body(tier=1)
        nonzero_cost_payload["intent"]["max_settlement_cost"] = 1
        nonzero_cost_body = self._encoded(nonzero_cost_payload)
        rejected = self.client.post(
            path,
            content=nonzero_cost_body,
            headers=self._headers(path, nonzero_cost_body),
        )
        self.assertEqual(rejected.status_code, 422, rejected.text)
        self.assertIn("max_settlement_cost", rejected.json()["detail"])

    def test_tier_two_fails_closed_without_ml_dsa_verifier(self):
        request_payload = self._signed_intent_payload(
            self._intent_body(tier=2, hybrid=True)
        )
        path = "/v1/vdso/intents"
        body = self._encoded(request_payload)
        response = self.client.post(path, content=body, headers=self._headers(path, body))
        self.assertEqual(response.status_code, 403, response.text)
        self.assertIn("ML-DSA-65 verifier is not configured", response.json()["detail"])

    def test_nonce_alias_is_rejected_end_to_end(self):
        path = "/v1/vdso/intents"
        first_payload = self._signed_intent_payload(self._intent_body(program_byte=2))
        first_body = self._encoded(first_payload)
        first = self.client.post(
            path, content=first_body, headers=self._headers(path, first_body)
        )
        self.assertEqual(first.status_code, 200, first.text)

        alias_payload = self._signed_intent_payload(self._intent_body(program_byte=10))
        alias_body = self._encoded(alias_payload)
        alias = self.client.post(
            path, content=alias_body, headers=self._headers(path, alias_body)
        )
        self.assertEqual(alias.status_code, 422, alias.text)
        self.assertIn("nonce reuse", alias.json()["detail"])

    def test_complete_encrypted_sidecar_is_stored_and_public_read_is_commitment_only(self):
        path = "/v1/vdso/sidecars"
        payload = self._sidecar_payload()
        body = self._encoded(payload)
        response = self.client.post(path, content=body, headers=self._headers(path, body))
        self.assertEqual(response.status_code, 200, response.text)
        read = self.client.get(f"{path}/{payload['content_hash']}")
        self.assertEqual(read.status_code, 200, read.text)
        self.assertEqual(read.json()["content_hash"], payload["content_hash"])
        self.assertEqual(
            set(read.json()),
            {"content_hash", "plaintext_root", "policy_hash"},
        )

    def test_sidecar_schema_rejects_plaintext_and_metadata_tamper(self):
        path = "/v1/vdso/sidecars"
        plaintext_payload = {**self._sidecar_payload(), "plaintext": "never accepted"}
        plaintext_body = self._encoded(plaintext_payload)
        rejected_plaintext = self.client.post(
            path,
            content=plaintext_body,
            headers=self._headers(path, plaintext_body),
        )
        self.assertEqual(rejected_plaintext.status_code, 422)

        tampered_payload = self._sidecar_payload()
        tampered_payload["nonce_b64"] = b64encode(b"m" * 24).decode()
        tampered_body = self._encoded(tampered_payload)
        rejected_tamper = self.client.post(
            path,
            content=tampered_body,
            headers=self._headers(path, tampered_body),
        )
        self.assertEqual(rejected_tamper.status_code, 422)
        self.assertIn("content_hash", rejected_tamper.json()["detail"])


if __name__ == "__main__":
    unittest.main()
