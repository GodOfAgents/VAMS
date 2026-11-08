"""Synthetic regressions for Phala credential request scoping.

The recording transport below models merged session/request headers. It is not
the Requests implementation and proves no remote server behavior.
"""

import os
import json
import unittest
from unittest.mock import patch

from neuron.runtime_safety import LiveModeSafetyError
from neuron.sdk.phala_tee import PhalaTEE


PHALA_URL = "https://phala.example.invalid/pruntime"
MARLIN_URL = "https://marlin.example.invalid/attestation"
KEY_A = "synthetic-credential-a"
KEY_B = "synthetic-credential-b"


def environment(mode="test", *, mock=False, key=KEY_A):
    values = {
        "VAMS_ENV": mode,
        "PHALA_MOCK_MODE": "true" if mock else "false",
        "PHALA_RPC_URL": PHALA_URL,
        "MARLIN_ATTESTATION_URL": MARLIN_URL,
        "VAMS_PHAT_PYTHON_RUNTIME": "synthetic-runtime",
    }
    if key is not None:
        values["PHALA_API_KEY"] = key
    return values


class _FixtureRaw:
    """Local JSON-byte fixture; not an HTTP/urllib3 implementation."""
    def __init__(self, response):
        self.response = response
        self.data = None
        self.offset = 0
        self.requests = []

    def read(self, amount, *, decode_content=False):
        self.requests.append((amount, decode_content))
        if type(amount) is not int or amount <= 0 or decode_content is not False:
            raise AssertionError("Expected a bounded undecoded byte read")
        if self.data is None:
            payload = self.response.payload
            if isinstance(payload, Exception): raise payload
            self.data = json.dumps(payload).encode("utf-8")
        chunk = self.data[self.offset:self.offset + amount]
        self.offset += len(chunk)
        return chunk


class Response:
    def __init__(self, payload=None, status=200):
        self.payload = payload if payload is not None else {"valid": False}
        self.status_code = status
        self.headers = {}
        self.raw = _FixtureRaw(self)
        self.close_calls = 0

    def close(self):
        self.close_calls += 1

    def json(self):
        return self.payload


class RecordingTransport:
    """Small requests-like fixture that records merged headers, without I/O."""

    def __init__(self, responses=()):
        self.headers = {}
        self.calls = []
        self.responses = list(responses)

    def _response(self):
        if self.responses:
            return self.responses.pop(0)
        return Response()

    def _record(self, method, url, kwargs):
        merged = dict(self.headers)
        merged.update(kwargs.get("headers") or {})
        self.calls.append(
            {
                "method": method,
                "url": url,
                "kwargs": dict(kwargs),
                "merged_headers": merged,
            }
        )
        return self._response()

    def post(self, url, **kwargs):
        return self._record("post", url, kwargs)

    def get(self, url, **kwargs):
        return self._record("get", url, kwargs)


class TeeCredentialScopeTests(unittest.TestCase):
    def make_client(self, transport, *, mode="test", mock=False, key=KEY_A):
        values = environment(mode, mock=mock, key=key)
        ambient = patch.dict(os.environ, values, clear=True)
        ambient.start()
        self.addCleanup(ambient.stop)
        return PhalaTEE(environ=values, transport=transport)

    @staticmethod
    def authorization(call):
        return call["merged_headers"].get("Authorization")

    def test_constructor_does_not_put_credential_in_shared_defaults(self):
        transport = RecordingTransport()
        self.make_client(transport, key=KEY_A)

        self.assertEqual(transport.headers, {})
        self.assertEqual(transport.calls, [])

    def test_constructor_preserves_caller_owned_transport_headers(self):
        transport = RecordingTransport()
        transport.headers.update(
            {"Authorization": "Bearer caller-owned", "X-Caller-Header": "keep"}
        )
        before = dict(transport.headers)

        self.make_client(transport, key=KEY_A)

        self.assertEqual(transport.headers, before)
        self.assertEqual(transport.calls, [])

    def test_sdk_owned_session_keeps_only_non_secret_defaults(self):
        transport = RecordingTransport()
        values = environment()
        with patch.dict(os.environ, values, clear=True), patch(
            "neuron.sdk.phala_tee.requests.Session", return_value=transport
        ):
            client = PhalaTEE()
            client.verify_sgx_quote(b"synthetic-default-session-quote")
        self.assertEqual(transport.headers, {
            "Content-Type": "application/json", "Accept": "application/json"
        })
        self.assertEqual(self.authorization(transport.calls[0]), f"Bearer {KEY_A}")
        self.assertIs(transport.calls[0]["kwargs"].get("allow_redirects"), False)

    def test_sgx_gets_request_local_phala_bearer_and_redirects_are_disabled(self):
        transport = RecordingTransport([Response({"valid": False})])
        client = self.make_client(transport, key=KEY_A)

        report = client.verify_sgx_quote(b"synthetic-sgx-quote")

        self.assertFalse(report.is_valid)
        self.assertEqual(len(transport.calls), 1)
        call = transport.calls[0]
        self.assertIn("/prpc/PhactoryAPI.VerifyAttestation", call["url"])
        self.assertEqual(self.authorization(call), f"Bearer {KEY_A}")
        self.assertEqual(call["kwargs"].get("allow_redirects"), False)
        self.assertNotIn("Authorization", transport.headers)

    def test_nitro_is_credential_free_before_and_after_phala_request(self):
        transport = RecordingTransport(
            [Response({"valid": False}), Response({"valid": False})]
        )
        client = self.make_client(transport, key=KEY_A)

        client.verify_nitro_quote(b"synthetic-nitro-before")
        client.verify_sgx_quote(b"synthetic-sgx")
        client.verify_nitro_quote(b"synthetic-nitro-after")

        nitro_calls = [call for call in transport.calls if "/verify" in call["url"]]
        phala_calls = [
            call for call in transport.calls
            if "VerifyAttestation" in call["url"]
        ]
        self.assertEqual(len(nitro_calls), 2)
        self.assertEqual(len(phala_calls), 1)
        self.assertTrue(all(self.authorization(call) is None for call in nitro_calls))
        self.assertEqual(self.authorization(phala_calls[0]), f"Bearer {KEY_A}")

    def test_public_gets_do_not_receive_phala_bearer(self):
        transport = RecordingTransport(
            [Response({"contract": "fixture"}), Response({}, status=200),
             Response({"valid": False}), Response({"contract": "fixture"}),
             Response({}, status=200)]
        )
        client = self.make_client(transport, key=KEY_A)

        self.assertEqual(client.get_phat_contract_info("fixture-contract"), {"contract": "fixture"})
        self.assertEqual(client.check_health()["status"], "healthy")
        client.verify_sgx_quote(b"synthetic-between-public-gets")
        self.assertEqual(client.get_phat_contract_info("fixture-contract"), {"contract": "fixture"})
        self.assertEqual(client.check_health()["status"], "healthy")

        self.assertEqual(len(transport.calls), 5)
        gets = [call for call in transport.calls if call["method"] == "get"]
        self.assertEqual(len(gets), 4)
        self.assertTrue(all(self.authorization(call) is None for call in gets))
        self.assertEqual(self.authorization(transport.calls[2]), f"Bearer {KEY_A}")

    def test_nonlive_phat_post_gets_key_and_does_not_follow_redirect(self):
        transport = RecordingTransport(
            [Response({"output": {"fixture": True}, "gas_used": 1}),
             Response({"redirect": "must-not-be-followed"}, status=302)]
        )
        client = self.make_client(transport, mode="test", mock=False, key=KEY_A)

        successful = client.call_phat_contract("fixture-address", "read_fixture", [])
        redirected = client.call_phat_contract("fixture-address", "read_fixture", [])

        self.assertTrue(successful.success)
        self.assertEqual(redirected.error, "provider_status")
        self.assertEqual(len(transport.calls), 2)
        for call in transport.calls:
            self.assertIn("PinkRuntime.ContractQuery", call["url"])
            self.assertEqual(self.authorization(call), f"Bearer {KEY_A}")
            self.assertIs(call["kwargs"].get("allow_redirects"), False)
        self.assertNotIn("Authorization", transport.headers)

    def test_keyless_calls_remain_credential_free(self):
        transport = RecordingTransport(
            [Response({"valid": False}), Response({"valid": False})]
        )
        client = self.make_client(transport, key=None)

        client.verify_sgx_quote(b"synthetic-sgx")
        client.verify_nitro_quote(b"synthetic-nitro")

        self.assertNotIn("Authorization", transport.headers)
        self.assertTrue(all(self.authorization(call) is None for call in transport.calls))

    def test_shared_transport_keeps_two_clients_credentials_isolated(self):
        transport = RecordingTransport(
            [Response({"valid": False}) for _ in range(4)]
        )
        values_a = environment("test", key=KEY_A)
        values_b = environment("test", key=KEY_B)
        with patch.dict(os.environ, values_a, clear=True):
            client_a = PhalaTEE(environ=values_a, transport=transport)
        with patch.dict(os.environ, values_b, clear=True):
            client_b = PhalaTEE(environ=values_b, transport=transport)

        with patch.dict(os.environ, values_a, clear=True):
            client_a.verify_sgx_quote(b"client-a-sgx")
            client_a.verify_nitro_quote(b"client-a-nitro")
        with patch.dict(os.environ, values_b, clear=True):
            client_b.verify_sgx_quote(b"client-b-sgx")
            client_b.verify_nitro_quote(b"client-b-nitro")

        self.assertEqual(self.authorization(transport.calls[0]), f"Bearer {KEY_A}")
        self.assertIsNone(self.authorization(transport.calls[1]))
        self.assertEqual(self.authorization(transport.calls[2]), f"Bearer {KEY_B}")
        self.assertIsNone(self.authorization(transport.calls[3]))
        self.assertNotIn("Authorization", transport.headers)

    def test_live_and_mock_direct_calls_reject_before_transport_or_header_injection(self):
        for mode, mock in (("production", False), ("test", True)):
            with self.subTest(mode=mode, mock=mock):
                transport = RecordingTransport()
                client = self.make_client(
                    transport, mode=mode, mock=mock, key=KEY_A
                )
                with self.assertRaises(LiveModeSafetyError):
                    client.call_phat_contract("fixture-address", "method", [])
                self.assertEqual(transport.calls, [])
                self.assertNotIn("Authorization", transport.headers)

    def test_redirect_statuses_are_not_followed_for_credential_bearing_posts(self):
        for status in (301, 302, 307, 308):
            with self.subTest(status=status):
                transport = RecordingTransport([Response({}, status=status)])
                client = self.make_client(transport, key=KEY_A)

                report = client.verify_sgx_quote(b"synthetic-redirect-case")

                self.assertEqual(report.error, "provider_status")
                self.assertEqual(len(transport.calls), 1)
                self.assertIs(
                    transport.calls[0]["kwargs"].get("allow_redirects"), False
                )

        for status in (301, 302, 307, 308):
            with self.subTest(phat_status=status):
                transport = RecordingTransport([Response({}, status=status)])
                client = self.make_client(transport, key=KEY_A)

                result = client.call_phat_contract("fixture-address", "method", [])

                self.assertFalse(result.success)
                self.assertEqual(result.error, "provider_status")
                self.assertEqual(len(transport.calls), 1)
                self.assertIs(
                    transport.calls[0]["kwargs"].get("allow_redirects"), False
                )
        # A synthetic transport can assert the request option only; it does not
        # prove Requests or an actual upstream server's redirect behavior.


if __name__ == "__main__":
    unittest.main()
