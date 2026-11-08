"""Bounded error-detail regressions for the AgentOS interrupt SDK path.

These stdlib tests exercise actual SDK methods with synthetic collaborators.
They do not enable live mode, contact providers, or test external log sinks.
"""
import logging
import time
import unittest

from neuron.sdk.interrupt_handler import (
    InterruptRequest,
    InterruptResult,
    InterruptSignal,
    InterruptStatus,
    InterruptVectorTable,
)
from neuron.sdk.x402_recovery import (
    EscrowRecord,
    EscrowState,
    X402InterruptHandler,
)


SENSITIVE_MARKER = "Bearer TEST_SENTINEL signature=0xDEADBEEF payload=TOP-SECRET"


class UnsafeDiagnostic(Exception):
    def __init__(self):
        self.str_calls = 0
        self.repr_calls = 0

    def __str__(self):
        self.str_calls += 1
        return SENSITIVE_MARKER

    def __repr__(self):
        self.repr_calls += 1
        return SENSITIVE_MARKER


class FakeMMU:
    def __init__(self):
        self.checkpoints = []
        self.stored = []

    def restore_interrupt_state(self, interrupt_id):
        return None

    def checkpoint_interrupt_state(self, interrupt_id, escrow, payload):
        self.checkpoints.append((interrupt_id, escrow, payload))

    def store(self, address, value, tier=None):
        self.stored.append((address, value, tier))


class FakeNonces:
    def __init__(self):
        self.calls = []

    def next_nonce(self, provider):
        self.calls.append(provider)
        return len(self.calls)


def make_request(payload=None):
    return InterruptRequest(
        interrupt_id="irq_privacy_regression",
        signal=InterruptSignal.SIG_TOOL_INVOKE,
        source="test-agent",
        target_provider="fixture-provider",
        payload={} if payload is None else payload,
        max_cost_vams=1.0,
        timeout_ms=10_000,
    )


def make_x402(*, max_retries=1, grace_period_seconds=5.0):
    # Bypass constructor policy wiring only to isolate the actual handler method;
    # no live mode or external implementation is enabled by this test.
    handler = X402InterruptHandler.__new__(X402InterruptHandler)
    handler.agent_id = "test-agent"
    handler.mmu = FakeMMU()
    handler.nonce_manager = FakeNonces()
    handler.max_retries = max_retries
    handler.grace_period_seconds = grace_period_seconds
    handler.recovery_attempts = 0
    return handler


def fixed_escrow(request, nonce, *, expires_in=60.0):
    return EscrowRecord(
        escrow_id=b"fixture-escrow",
        state=EscrowState.LOCKED,
        amount_wei=10**18,
        expires_at=time.time() + expires_in,
        provider=request.target_provider,
        nonce=nonce,
    )


class InterruptErrorPrivacyTest(unittest.TestCase):
    def test_x402_exception_is_not_stringified_logged_or_returned_and_retries_unchanged(self):
        handler = make_x402(max_retries=1)
        error = UnsafeDiagnostic()
        attempts = []

        def fail_lock(request, nonce):
            attempts.append((request, nonce))
            raise error

        handler._lock_escrow = fail_lock
        request = make_request({"tool": "lookup", "input": SENSITIVE_MARKER})
        with self.assertLogs("vams.x402_recovery", level="ERROR") as captured:
            result = handler.handle_tool_invoke(request)

        self.assertEqual(len(attempts), 2)
        self.assertEqual(handler.nonce_manager.calls, ["global", "global"])
        self.assertEqual(result.status, InterruptStatus.FAILED)
        self.assertEqual(
            result.error,
            "All attempts exhausted. Last error: Provider execution failed",
        )
        self.assertNotIn(SENSITIVE_MARKER, result.error)
        self.assertNotIn(SENSITIVE_MARKER, "\n".join(captured.output))
        self.assertEqual((error.str_calls, error.repr_calls), (0, 0))

    def test_untrusted_failed_result_error_is_mapped_to_fixed_code(self):
        handler = make_x402(max_retries=1)
        handler._lock_escrow = lambda request, nonce: fixed_escrow(request, nonce)
        supplied = "Provider rejected call: " + SENSITIVE_MARKER

        def failed_delivery(escrow, request):
            return InterruptResult(
                interrupt_id=request.interrupt_id,
                signal=request.signal,
                status=InterruptStatus.FAILED,
                error=supplied,
                provider=escrow.provider,
                cost_vams=0.25,
            )

        handler._await_delivery = failed_delivery
        result = handler.handle_tool_invoke(make_request())

        self.assertEqual(handler.nonce_manager.calls, ["global", "global"])
        self.assertEqual(result.status, InterruptStatus.FAILED)
        self.assertEqual(
            result.error,
            "All attempts exhausted. Last error: Provider execution failed",
        )
        self.assertNotIn(SENSITIVE_MARKER, result.error)

    def test_expiry_and_dispute_failures_keep_safe_metadata_and_known_messages(self):
        # The actual local expiry branch retains its fixed message/status/provider.
        handler = make_x402(max_retries=0, grace_period_seconds=5.0)
        handler._lock_escrow = lambda request, nonce: fixed_escrow(
            request, nonce, expires_in=1.0
        )
        expired = handler.handle_tool_invoke(make_request())
        self.assertEqual(expired.status, InterruptStatus.FAILED)
        self.assertEqual(expired.provider, "fixture-provider")
        self.assertEqual(
            expired.error,
            "All attempts exhausted. Last error: Escrow expired or too close to expiry",
        )

        # The established local dispute text is allowlisted by exact value, while
        # arbitrary provider error text is discarded by the preceding regression.
        handler = make_x402(max_retries=0)
        handler._lock_escrow = lambda request, nonce: fixed_escrow(request, nonce)
        handler._await_delivery = X402InterruptHandler._await_delivery.__get__(handler)
        disputed = handler.handle_tool_invoke(
            make_request({"tool": "lookup", "simulate_invalid_preimage": True})
        )
        self.assertEqual(disputed.status, InterruptStatus.FAILED)
        self.assertEqual(disputed.provider, "fixture-provider")
        self.assertIn("Disputed: HTLC preimage mismatch", disputed.error)
        self.assertNotIn(SENSITIVE_MARKER, disputed.error)

    def test_verified_result_and_proof_metadata_are_unchanged(self):
        handler = make_x402(max_retries=0)
        handler._lock_escrow = lambda request, nonce: fixed_escrow(request, nonce)
        expected = InterruptResult(
            interrupt_id="irq_success",
            signal=InterruptSignal.SIG_TOOL_INVOKE,
            status=InterruptStatus.VERIFIED,
            result={"tool_output": "ok", "business_value": 9},
            proof={"type": "fixture-proof", "hash": "abc123"},
            provider="fixture-provider",
            cost_vams=0.75,
        )
        handler._await_delivery = lambda escrow, request: expected

        actual = handler.handle_tool_invoke(make_request())
        self.assertIs(actual, expected)
        self.assertEqual(actual.status, InterruptStatus.VERIFIED)
        self.assertEqual(actual.result, {"tool_output": "ok", "business_value": 9})
        self.assertEqual(actual.proof, {"type": "fixture-proof", "hash": "abc123"})
        self.assertEqual(actual.provider, "fixture-provider")
        self.assertEqual(actual.cost_vams, 0.75)
        self.assertEqual(len(handler.mmu.stored), 1)

    def test_ivt_custom_handler_exception_returns_safe_error_and_preserves_status(self):
        ivt = InterruptVectorTable(
            agent_id="test-agent",
            mock_mode=True,
            environ={"VAMS_ENV": "test"},
        )
        error = UnsafeDiagnostic()

        def fail_handler(request):
            raise error

        ivt.register_handler(InterruptSignal.SIG_TOOL_INVOKE, fail_handler)
        with self.assertLogs("vams.interrupt_handler", level="ERROR") as captured:
            result = ivt.raise_interrupt(
                InterruptSignal.SIG_TOOL_INVOKE,
                {"tool": "lookup", "payload": SENSITIVE_MARKER},
                target_provider="fixture-provider",
            )

        self.assertEqual(result.status, InterruptStatus.FAILED)
        self.assertEqual(result.error, "interrupt_handler_failed")
        self.assertEqual(result.interrupt_id, "irq_1_tool_invoke")
        self.assertNotIn(SENSITIVE_MARKER, result.error)
        self.assertNotIn(SENSITIVE_MARKER, "\n".join(captured.output))
        self.assertEqual((error.str_calls, error.repr_calls), (0, 0))
        self.assertIs(ivt._history[-1], result)
        self.assertEqual(ivt.get_stats()["failed"], 1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    unittest.main()
