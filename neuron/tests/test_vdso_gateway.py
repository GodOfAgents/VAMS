import hashlib
import json
import os
import sqlite3
import tempfile
import time
import unittest
from base64 import b64encode
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ.setdefault("GATEWAY_ADMIN_PASSWORD", "SecureVDSOTestPassword123!")
os.environ["VAMS_ENV"] = "test"

from gateway import vdso as vdso_gateway
from gateway.request_auth import AUTH_ALGORITHM, AUTH_VERSION, GatewayAuthEnvelope
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


class VDSOGatewayTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.signing_key = generate_private_key()
        self.public_key = public_key_bytes(self.signing_key)
        self.audience = "vams.gateway.vdso-test"
        self.replay_path = os.path.join(
            self.temporary_directory.name, "replay.sqlite3"
        )
        self.environment = patch.dict(
            os.environ,
            {
                "VAMS_ENV": "local",
                "GATEWAY_ADMIN_PASSWORD": "SecureVDSOTestPassword123!",
                "GATEWAY_ADMIN_DID": "did:key:" + self.public_key.hex(),
                "GATEWAY_AUTH_AUDIENCE": self.audience,
                "GATEWAY_AUTH_REPLAY_DB": self.replay_path,
            },
            clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        vdso_gateway.service = VDSOCanaryService(
            mode=VDSOMode.SHADOW,
            height_provider=lambda _binding: 1_000,
        )
        self.client = TestClient(app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self._nonce = 0

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

    def _headers(
        self,
        path,
        body_bytes=b"",
        *,
        timestamp=None,
        method="POST",
        nonce=None,
    ):
        now = int(time.time())
        self._nonce += 1
        nonce_value = nonce if nonce is not None else self._nonce
        envelope = GatewayAuthEnvelope(
            AUTH_VERSION,
            AUTH_ALGORITHM,
            method.encode(),
            path.encode(),
            b"",
            hashlib.sha256(body_bytes).digest(),
            self.audience,
            "did:key:" + self.public_key.hex(),
            nonce_value.to_bytes(16, "big"),
            now,
            now + 120,
        )
        headers = {
            "Content-Type": "application/json",
            "X-VAMS-Auth-Version": AUTH_VERSION,
            "X-VAMS-Auth-Algorithm": AUTH_ALGORITHM,
            "X-VAMS-Auth-Audience": self.audience,
            "X-VAMS-Auth-Signer": envelope.signer,
            "X-VAMS-Auth-Nonce": envelope.nonce.hex(),
            "X-VAMS-Auth-Issued-At": str(envelope.issued_at),
            "X-VAMS-Auth-Expires-At": str(envelope.expires_at),
            "X-VAMS-Auth-Signature": sign_message(
                self.signing_key, envelope.canonical_bytes()
            ).hex(),
        }
        if method == "GET":
            headers.pop("Content-Type")
        if timestamp is not None:
            headers["X-VAMS-Auth-Issued-At"] = timestamp
        return headers

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
        response = self.client.post(path, content=body + b" ", headers=headers)
        self.assertEqual(response.status_code, 401)
        self.assertIn("invalid_signature", response.json()["detail"])

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
                self.assertIn("malformed_issued_at", response.json()["detail"])

    def test_signature_alias_cannot_bypass_atomic_replay_claim(self):
        path = "/v1/vdso/intents/simulate"
        body = self._encoded(self._simulation_body())
        first_headers = self._headers(path, body, nonce=99)
        second_headers = self._headers(path, body, nonce=99)
        self.assertNotEqual(
            first_headers["X-VAMS-Auth-Signature"],
            second_headers["X-VAMS-Auth-Signature"],
        )
        first = self.client.post(path, content=body, headers=first_headers)
        second = self.client.post(path, content=body, headers=second_headers)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 401, second.text)
        self.assertIn("duplicate_nonce", second.json()["detail"])

    def test_legacy_vdso_auth_scheme_cannot_bypass_m2(self):
        path = "/v1/vdso/intents/simulate"
        body = self._encoded(self._simulation_body())
        response = self.client.post(
            path,
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-VAMS-DID": "did:key:" + self.public_key.hex(),
                "X-VAMS-Signature": "00" * 64,
                "X-VAMS-Timestamp": str(int(time.time())),
            },
        )
        self.assertEqual(response.status_code, 401, response.text)
        self.assertIn("conflicting_legacy_auth_header", response.json()["detail"])

    def test_vdso_uses_root_durable_m2_replay_store(self):
        path = "/v1/vdso/intents/simulate"
        body = self._encoded(self._simulation_body())
        response = self.client.post(
            path, content=body, headers=self._headers(path, body)
        )
        self.assertEqual(response.status_code, 200, response.text)
        with sqlite3.connect(self.replay_path) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM replay_reservations"
                ).fetchone()[0],
                1,
            )

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
        read_path = f"{path}/{payload['content_hash']}"
        read = self.client.get(
            read_path,
            headers=self._headers(read_path, method="GET"),
        )
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
