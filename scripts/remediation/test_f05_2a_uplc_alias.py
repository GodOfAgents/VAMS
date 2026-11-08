"""Tests for the F05 UPLC verifier alias boundary."""

import pytest

from scripts.remediation.test_f05_2a_authority_bootstrap_public import (
    _normalize_verify_signature_builtin,
)

LEGACY = "(builtin verifySignature)"
CANONICAL = "(builtin verifyEd25519Signature)"


def test_positive_bootstrap_rewrites_only_exact_five_tokens():
    original = (
        "(program 1.1.0 " + " ".join([LEGACY] * 5)
        + " (builtin verifySignatureExtra) " + CANONICAL + ")"
    )
    normalized, count = _normalize_verify_signature_builtin(original, "valid-bootstrap")
    assert count == 5
    assert normalized == original.replace(LEGACY, CANONICAL)
    assert normalized.count(CANONICAL) == 6
    assert "(builtin verifySignatureExtra)" in normalized


@pytest.mark.parametrize("label", ["mutation-no-verifier", "mutation-removes-calls"])
def test_zero_legacy_calls_in_mutation_preserves_program(label):
    original = "(program 1.1.0 (builtin verifyEd25519Signature) (builtin verifySignatureExtra))"
    normalized, count = _normalize_verify_signature_builtin(original, label)
    assert (normalized, count) == (original, 0)


def test_five_legacy_calls_in_mutation_are_normalized():
    original = " ".join([LEGACY] * 5)
    normalized, count = _normalize_verify_signature_builtin(original, "mutation-retains-calls")
    assert (normalized, count) == (" ".join([CANONICAL] * 5), 5)


@pytest.mark.parametrize("count", [1, 2, 4, 6])
@pytest.mark.parametrize("label", ["valid-bootstrap", "mutation-partial-calls"])
def test_unexpected_call_counts_fail_closed(count, label):
    with pytest.raises(ValueError):
        _normalize_verify_signature_builtin(" ".join([LEGACY] * count), label)


def test_positive_bootstrap_with_no_legacy_calls_fails_closed():
    with pytest.raises(ValueError):
        _normalize_verify_signature_builtin(CANONICAL, "valid-bootstrap")


MULTILINE = "(builtin\n  verifySignature\n)"
MULTILINE_CANONICAL = "(builtin\n  verifyEd25519Signature\n)"


def test_pretty_printed_multiline_bootstrap_rewrites_five_aliases():
    original = "(program\n  1.1.0\n  " + "\n  ".join([MULTILINE] * 5) + "\n)"
    normalized, count = _normalize_verify_signature_builtin(original, "valid-bootstrap")
    assert count == 5
    assert normalized == original.replace(MULTILINE, MULTILINE_CANONICAL)


def test_mixed_one_line_and_multiline_forms_count_together():
    original = " ".join([LEGACY, MULTILINE, LEGACY, MULTILINE, LEGACY])
    normalized, count = _normalize_verify_signature_builtin(original, "mutation-mixed")
    assert count == 5
    assert normalized == " ".join(
        [CANONICAL, MULTILINE_CANONICAL, CANONICAL, MULTILINE_CANONICAL, CANONICAL]
    )


@pytest.mark.parametrize("count", [1, 4, 6])
def test_partial_or_excess_multiline_aliases_fail_closed(count):
    with pytest.raises(ValueError):
        _normalize_verify_signature_builtin("\n".join([MULTILINE] * count), "mutation-multiline")


@pytest.mark.parametrize("stray", ["verifySignature", "(con string verifySignature)", "(builtinOther verifySignature)"])
def test_unscoped_legacy_name_fails_closed_even_with_five_valid_builtins(stray):
    program = " ".join([LEGACY] * 5) + " " + stray
    with pytest.raises(ValueError):
        _normalize_verify_signature_builtin(program, "valid-bootstrap")
