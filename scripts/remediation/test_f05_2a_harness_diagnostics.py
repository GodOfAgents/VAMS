from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("test_f05_2a_authority_bootstrap_public.py")
SPEC = importlib.util.spec_from_file_location("f05_2a_public_harness", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_missing_plutus_builtin_is_reported_as_evaluator_capability_failure():
    observed = {
        "accepted": False,
        "exit": 101,
        "diagnostic": "Error: Default Function not found - verifySignature",
    }
    with pytest.raises(RuntimeError, match="UPLC evaluation aborted before an accept/reject verdict"):
        MODULE._require_positive_acceptance(observed)


def test_compiled_positive_fixture_rejection_remains_a_validator_failure():
    observed = {
        "accepted": False,
        "exit": 1,
        "diagnostic": "script evaluation failed",
    }
    with pytest.raises(AssertionError, match="fixture rejected by compiled Plutus V3"):
        MODULE._require_positive_acceptance(observed)


def test_accepted_positive_control_passes():
    assert MODULE._require_positive_acceptance({"accepted": True}) is None
