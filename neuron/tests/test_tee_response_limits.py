"""Bounded-body regressions for non-authoritative SGX/Nitro JSON claims.

The byte stream and transport are local fixtures. They do not model Requests'
internal buffering, a real HTTP server, provider behavior, or authentic claims.
"""

import json
import os
import unittest
from unittest.mock import patch

from neuron.runtime_safety import RuntimeConfigurationError
from neuron.sdk import phala_tee as P
from neuron.sdk.phala_tee import PhalaTEE


BODY_LIMIT = 65_536
READ_LIMIT = 8_192
PHALA_URL = "https://phala.example.invalid/pruntime"
MARLIN_URL = "https://marlin.example.invalid/attestation"
SENTINEL = "synthetic-provider-secret-marker"


class FixtureControlInterrupt(BaseException):
    """Controlled local cancellation; tests catch it without stopping the runner."""


def environment(mode="test"):
    return {
        "VAMS_ENV": mode,
        "PHALA_MOCK_MODE": "false",
        "PHALA_RPC_URL": PHALA_URL,
        "MARLIN_ATTESTATION_URL": MARLIN_URL,
        "PHALA_API_KEY": "synthetic-key-only",
        "VAMS_PHAT_PYTHON_RUNTIME": "synthetic-runtime",
    }


class RawBytes:
    def __init__(self, body, *, on_read=None, read_error=None, oversized_return=False):
        self.body = body
        self.offset = 0
        self.calls = []
        self.on_read = on_read
        self.read_error = read_error
        self.oversized_return = oversized_return

    def read(self, amount, *, decode_content=True):
        self.calls.append((amount, decode_content))
        if self.on_read is not None:
            self.on_read()
        if self.read_error is not None:
            raise self.read_error
        take = amount + 1 if self.oversized_return else amount
        chunk = self.body[self.offset : self.offset + take]
        self.offset += len(chunk)
        return chunk


class StreamResponse:
    def __init__(
        self,
        body=b'{"valid":false}',
        *,
        status=200,
        headers=None,
        on_read=None,
        on_close=None,
        read_error=None,
        close_error=None,
        raw=None,
    ):
        self.status_code = status
        self.headers = dict(headers or {})
        self.raw = raw if raw is not None else RawBytes(
            body, on_read=on_read, read_error=read_error
        )
        self.on_close = on_close
        self.close_error = close_error
        self.close_calls = 0

    def close(self):
        self.close_calls += 1
        if self.on_close is not None:
            self.on_close()
        if self.close_error is not None:
            raise self.close_error

    def json(self):
        raise AssertionError("diagnostic response must not call .json()")

    @property
    def content(self):
        raise AssertionError("diagnostic response must not read .content")

    @property
    def text(self):
        raise AssertionError("diagnostic response must not read .text")

    def iter_content(self, *args, **kwargs):
        raise AssertionError("diagnostic response must not use iter_content")


class RecordingTransport:
    def __init__(self, responses=(), *, on_post=None):
        self.responses = list(responses)
        self.calls = []
        self.on_post = on_post

    def post(self, url, **kwargs):
        self.calls.append((url, dict(kwargs)))
        response = self.responses.pop(0)
        if self.on_post is not None:
            self.on_post()
        return response


class AccessorResponse:
    """Supported custom-response seam; all bytes and callbacks stay in memory."""
    status_code = 200

    def __init__(self, phase, callback, *, close_error=None):
        self.phase, self.callback = phase, callback
        self.inner = StreamResponse(close_error=close_error)

    @property
    def headers(self):
        if self.phase == "headers":
            self.callback()
        return self.inner.headers

    @property
    def raw(self):
        if self.phase == "raw":
            self.callback()
        if self.phase == "reader":
            owner = self

            class ReaderAccessor:
                @property
                def read(self):
                    owner.callback()
                    return owner.inner.raw.read

            return ReaderAccessor()
        return self.inner.raw

    @property
    def close_calls(self):
        return self.inner.close_calls

    def close(self):
        self.inner.close()


class TeeResponseLimitTests(unittest.TestCase):
    def make_client(self, transport, mode="test"):
        values = environment(mode)
        active = patch.dict(os.environ, values, clear=True)
        active.start()
        self.addCleanup(active.stop)
        return PhalaTEE(environ=values, transport=transport)

    @staticmethod
    def call(client, provider):
        if provider == "phala":
            return client.verify_sgx_quote(b"synthetic-sgx-quote")
        return client.verify_nitro_quote(b"synthetic-nitro-attestation")

    @staticmethod
    def valid_false_json(length=None):
        body = b'{"valid":false}'
        if length is not None:
            if length < len(body):
                raise ValueError("fixture length is too short")
            body += b" " * (length - len(body))
        return body

    def test_exact_budget_is_accepted_for_both_diagnostic_providers(self):
        for provider in ("phala", "marlin"):
            with self.subTest(provider=provider):
                body = self.valid_false_json(BODY_LIMIT)
                response_headers = {"Content-Length": str(BODY_LIMIT)}
                if provider == "phala":
                    response_headers["Content-Encoding"] = "identity"
                response = StreamResponse(body, headers=response_headers)
                transport = RecordingTransport([response])
                client = self.make_client(transport)

                report = self.call(client, provider)

                self.assertFalse(report.is_valid)
                self.assertIs(report.provider_claim_valid, False)
                self.assertEqual(response.raw.offset, BODY_LIMIT)
                self.assertTrue(response.raw.calls)
                self.assertTrue(all(0 < amount <= READ_LIMIT for amount, _ in response.raw.calls))
                self.assertTrue(all(decode is False for _, decode in response.raw.calls))
                self.assertEqual(response.close_calls, 1)
                url, kwargs = transport.calls[0]
                self.assertEqual(kwargs.get("stream"), True)
                self.assertIs(kwargs.get("allow_redirects"), False)
                self.assertEqual(kwargs.get("headers", {}).get("Accept-Encoding"), "identity")
                if provider == "phala":
                    self.assertIn("VerifyAttestation", url)
                    self.assertEqual(
                        kwargs["headers"].get("Authorization"),
                        "Bearer synthetic-key-only",
                    )
                else:
                    self.assertTrue(url.endswith("/verify"))
                    self.assertNotIn("Authorization", kwargs["headers"])

    def test_budget_plus_one_rejects_and_false_small_length_is_ignored(self):
        body = self.valid_false_json(BODY_LIMIT + 1)
        for provider in ("phala", "marlin"):
            with self.subTest(provider=provider):
                response = StreamResponse(body, headers={"Content-Length": "1"})
                transport = RecordingTransport([response])
                client = self.make_client(transport)

                report = self.call(client, provider)

                self.assertEqual(report.error, "provider_response_too_large")
                self.assertIsNone(report.provider_claim_valid)
                self.assertEqual(response.close_calls, 1)
                self.assertEqual(response.raw.offset, BODY_LIMIT + 1)
                self.assertEqual(response.raw.calls[-1][0], 1)
                self.assertLessEqual(max(amount for amount, _ in response.raw.calls), READ_LIMIT)

    def test_false_large_content_length_does_not_reject_bounded_body(self):
        response = StreamResponse(
            b'{"valid":false}', headers={"Content-Length": "999999999"}
        )
        client = self.make_client(RecordingTransport([response]))

        report = client.verify_sgx_quote(b"synthetic-quote")

        self.assertEqual(report.error, "provider_claim_false")
        self.assertIs(report.provider_claim_valid, False)
        self.assertEqual(response.close_calls, 1)

    def test_non_identity_encoding_is_rejected_before_body_read(self):
        for encoding in ("", "gzip", "br", "identity, gzip"):
            with self.subTest(encoding=encoding):
                response = StreamResponse(
                    b'{"valid":false}', headers={"Content-Encoding": encoding}
                )
                client = self.make_client(RecordingTransport([response]))

                report = client.verify_nitro_quote(b"synthetic-attestation")

                self.assertEqual(report.error, "unsupported_content_encoding")
                self.assertEqual(response.raw.calls, [])
                self.assertEqual(response.close_calls, 1)

    def test_invalid_utf8_or_json_fails_closed_after_close(self):
        for body in (b"\xff", b"not-json"):
            with self.subTest(body=body):
                response = StreamResponse(body)
                client = self.make_client(RecordingTransport([response]))

                report = client.verify_sgx_quote(b"synthetic-quote")

                self.assertEqual(report.error, "malformed_response")
                self.assertIsNone(report.provider_claim_valid)
                self.assertEqual(response.close_calls, 1)

    def test_redirect_statuses_close_without_read_or_follow_up(self):
        for provider in ("phala", "marlin"):
            for status in (301, 302, 307, 308):
                with self.subTest(provider=provider, status=status):
                    response = StreamResponse(b"redirect-body-must-not-be-read", status=status)
                    transport = RecordingTransport([response])
                    client = self.make_client(transport)

                    report = self.call(client, provider)

                    self.assertEqual(report.error, "provider_status")
                    self.assertEqual(len(transport.calls), 1)
                    self.assertIs(transport.calls[0][1].get("allow_redirects"), False)
                    self.assertEqual(response.raw.calls, [])
                    self.assertEqual(response.close_calls, 1)

    def test_raw_interface_and_read_failures_are_bounded_and_closed(self):
        missing_raw = StreamResponse()
        missing_raw.raw = None
        malformed_headers = StreamResponse()
        malformed_headers.headers = None
        for response, expected in (
            (StreamResponse(read_error=RuntimeError(SENTINEL)), "provider_error"),
            (missing_raw, "provider_error"),
            (malformed_headers, "provider_error"),
            (StreamResponse(raw=RawBytes("not bytes")), "provider_error"),
            (
                StreamResponse(
                    raw=RawBytes(b"x" * (READ_LIMIT + 2), oversized_return=True)
                ),
                "provider_error",
            ),
        ):
            with self.subTest(expected=expected, read_error=response.raw):
                client = self.make_client(RecordingTransport([response]))

                report = client.verify_nitro_quote(b"synthetic-attestation")

                self.assertEqual(report.error, expected)
                self.assertNotIn(SENTINEL, report.error or "")
                self.assertEqual(response.close_calls, 1)

    def test_close_failure_prevents_claim_adoption_and_hides_details(self):
        response = StreamResponse(
            b'{"valid":false}', close_error=RuntimeError(SENTINEL)
        )
        client = self.make_client(RecordingTransport([response]))

        report = client.verify_sgx_quote(b"synthetic-quote")

        self.assertEqual(report.error, "provider_error")
        self.assertIsNone(report.provider_claim_valid)
        self.assertNotIn(SENTINEL, report.error or "")
        self.assertEqual(response.close_calls, 1)

    def test_runtime_drift_after_read_closes_once_and_precedes_close_failure(self):
        response = StreamResponse(
            b'{"valid":false}',
            on_read=lambda: os.environ.update(VAMS_ENV="production"),
            close_error=RuntimeError(SENTINEL),
        )
        transport = RecordingTransport([response])
        client = self.make_client(transport)

        with self.assertRaises(RuntimeConfigurationError):
            client.verify_sgx_quote(b"synthetic-quote")

        self.assertEqual(len(response.raw.calls), 1)
        self.assertEqual(response.close_calls, 1)

    def test_runtime_drift_during_close_is_checked_before_claim_adoption(self):
        response = StreamResponse(
            b'{"valid":false}',
            on_close=lambda: os.environ.update(VAMS_ENV="production"),
        )
        client = self.make_client(RecordingTransport([response]))

        with self.assertRaises(RuntimeConfigurationError):
            client.verify_nitro_quote(b"synthetic-attestation")

        self.assertEqual(response.close_calls, 1)

    def test_runtime_drift_immediately_after_post_still_closes_response(self):
        response = StreamResponse(b'{"valid":false}')
        transport = RecordingTransport(
            [response], on_post=lambda: os.environ.update(VAMS_ENV="production")
        )
        client = self.make_client(transport)

        with self.assertRaises(RuntimeConfigurationError):
            client.verify_sgx_quote(b"synthetic-quote")

        self.assertEqual(response.raw.calls, [])
        self.assertEqual(response.close_calls, 1)

    def test_local_control_interrupt_during_read_still_closes_and_propagates(self):
        response = StreamResponse(
            read_error=FixtureControlInterrupt("synthetic-local-cancel"),
            close_error=RuntimeError(SENTINEL),
        )
        client = self.make_client(RecordingTransport([response]))
        with self.assertRaises(FixtureControlInterrupt):
            client.verify_sgx_quote(b"synthetic-quote")
        self.assertEqual(response.close_calls, 1)

    def test_cleanup_control_interrupt_cannot_replace_private_runtime_drift(self):
        response = StreamResponse(
            on_read=lambda: os.environ.update(VAMS_ENV="production"),
            close_error=FixtureControlInterrupt("synthetic-cleanup-cancel"),
        )
        client = self.make_client(RecordingTransport([response]))
        with self.assertRaises(BaseException) as raised:
            client.verify_nitro_quote(b"synthetic-attestation")
        self.assertIsInstance(raised.exception, RuntimeConfigurationError)
        self.assertNotIn(SENTINEL, str(raised.exception))
        self.assertEqual(response.close_calls, 1)

    def test_accessor_private_denial_survives_restoration_and_cleanup(self):
        for provider in ("phala", "marlin"):
            for phase in ("headers", "raw", "reader"):
                for cleanup_control in (False, True):
                    with self.subTest(provider=provider, phase=phase, cleanup_control=cleanup_control):
                        def deny():
                            original = os.environ["VAMS_ENV"]
                            os.environ["VAMS_ENV"] = "production"
                            try:
                                client._assert_current_runtime()
                            finally:
                                os.environ["VAMS_ENV"] = original

                        response = AccessorResponse(phase, deny,
                            close_error=FixtureControlInterrupt() if cleanup_control else None)
                        transport = RecordingTransport([response])
                        client = self.make_client(transport)
                        error = None
                        try:
                            self.call(client, provider)
                        except BaseException as exc:
                            error = exc
                        self.assertEqual(type(error).__name__, "_PhalaRuntimeDriftError")
                        self.assertEqual(response.close_calls, 1)
                        self.assertEqual(len(transport.calls), 1)
                        self.assertEqual(response.inner.raw.calls, [])

    def test_accessor_private_denial_stops_multi_provider_dispatch(self):
        for phase in ("headers", "raw", "reader"):
            with self.subTest(phase=phase):
                def deny():
                    original = os.environ["VAMS_ENV"]
                    os.environ["VAMS_ENV"] = "production"
                    try:
                        client._assert_current_runtime()
                    finally:
                        os.environ["VAMS_ENV"] = original

                first = AccessorResponse(phase, deny)
                second = StreamResponse()
                transport = RecordingTransport([first, second])
                client = self.make_client(transport)
                error = None
                try:
                    client.verify_multi_tee({P.TEEProvider.PHALA: b"fixture-first",
                                             P.TEEProvider.MARLIN: b"fixture-second"})
                except BaseException as exc:
                    error = exc
                self.assertEqual(type(error).__name__, "_PhalaRuntimeDriftError")
                self.assertEqual(len(transport.calls), 1)
                self.assertEqual(first.close_calls, 1)
                self.assertEqual(second.close_calls, 0)
                self.assertEqual(len(transport.responses), 1)

    def test_ordinary_accessor_errors_remain_bounded_non_authoritative_failures(self):
        for provider in ("phala", "marlin"):
            for phase in ("headers", "raw", "reader"):
                with self.subTest(provider=provider, phase=phase):
                    def fail():
                        raise RuntimeError(SENTINEL)

                    response = AccessorResponse(phase, fail)
                    transport = RecordingTransport([response])
                    client = self.make_client(transport)
                    report = self.call(client, provider)
                    self.assertEqual(report.error, "provider_error")
                    self.assertFalse(report.is_valid)
                    self.assertFalse(report.usable_as_live_evidence)
                    self.assertIsNone(report.provider_claim_valid)
                    self.assertNotIn(SENTINEL, str(report))
                    self.assertEqual(response.close_calls, 1)
                    self.assertEqual(len(transport.calls), 1)

    def test_buffer_observer_confirms_no_over_limit_or_post_drift_append(self):
        buffers = []
        appends = []

        class ObservedBuffer(bytearray):
            def __init__(self):
                super().__init__()
                buffers.append(self)

            def extend(self, chunk):
                appends.append((len(self), len(chunk)))
                super().extend(chunk)

        response = StreamResponse(self.valid_false_json(BODY_LIMIT + 1))
        client = self.make_client(RecordingTransport([response]))
        with patch.object(P, "bytearray", ObservedBuffer, create=True):
            report = client.verify_sgx_quote(b"synthetic-quote")
        self.assertEqual(report.error, "provider_response_too_large")
        self.assertEqual(len(buffers), 1)
        self.assertEqual(len(buffers[0]), BODY_LIMIT)
        self.assertTrue(all(before + added <= BODY_LIMIT for before, added in appends))

        buffers.clear()
        appends.clear()
        response = StreamResponse(on_read=lambda: os.environ.update(VAMS_ENV="production"))
        client = self.make_client(RecordingTransport([response]))
        with patch.object(P, "bytearray", ObservedBuffer, create=True):
            with self.assertRaises(RuntimeConfigurationError):
                client.verify_nitro_quote(b"synthetic-attestation")
        self.assertEqual(len(buffers), 1)
        self.assertEqual(len(buffers[0]), 0)
        self.assertEqual(appends, [])
        self.assertEqual(response.close_calls, 1)


if __name__ == "__main__":
    unittest.main()
