"""Source-anchor regression tests for the disposable F05 inline-datum mutant."""

from pathlib import Path

import pytest

from scripts.remediation.test_f05_2a_authority_bootstrap_public import (
    AUTHORITY_SOURCE,
    CARDANO,
    POLICY_SOURCE,
    _mutant_source,
)

IMPORT_ANCHOR = "InlineDatum, Input, Output, OutputReference, Transaction"
IMPORT_MUTANT = "Datum, InlineDatum, Input, Output, OutputReference, Transaction"
GUARD_ANCHOR = "expect InlineDatum(raw_datum) = authority_output.datum"
GUARD_MUTANT = (
    "expect InlineDatum(raw_datum) = sponsor_datum(tx.outputs, state_validator_script_hash)"
)
HELPER_ANCHOR = "fn count_seed_input(inputs: List<Input>, seed_ref: OutputReference) -> Int {"
HELPER = """fn sponsor_datum(outputs: List<Output>, state_validator_script_hash: ByteArray) -> Datum {
  expect Some(output) = list.find(outputs, fn(output) {
    output.address.payment_credential != Script(state_validator_script_hash)
  })
  output.datum
}

"""


def _disposable_source(tmp_path: Path) -> tuple[Path, Path, str]:
    policy = tmp_path / POLICY_SOURCE
    authority = tmp_path / AUTHORITY_SOURCE
    policy.parent.mkdir(parents=True)
    authority.parent.mkdir(parents=True)
    original = (CARDANO / POLICY_SOURCE).read_text(encoding="utf-8")
    policy.write_text(original, encoding="utf-8")
    authority.write_bytes((CARDANO / AUTHORITY_SOURCE).read_bytes())
    return policy, authority, original


def test_inline_datum_mutant_changes_only_expected_policy_anchors(tmp_path: Path) -> None:
    policy, authority, original = _disposable_source(tmp_path)
    authority_before = authority.read_bytes()
    assert original.count(IMPORT_ANCHOR) == 1
    assert original.count(GUARD_ANCHOR) == 1
    assert original.count(HELPER_ANCHOR) == 1
    assert "fn sponsor_datum(" not in original

    _mutant_source(tmp_path, "remove_inline_datum_guard")

    expected = original.replace(GUARD_ANCHOR, GUARD_MUTANT, 1)
    expected = expected.replace(HELPER_ANCHOR, HELPER + HELPER_ANCHOR, 1)
    expected = expected.replace(IMPORT_ANCHOR, IMPORT_MUTANT, 1)
    mutated = policy.read_text(encoding="utf-8")
    assert mutated == expected
    assert mutated.count(IMPORT_MUTANT) == 1
    assert mutated.count("fn sponsor_datum(") == 1
    assert mutated.count(GUARD_MUTANT) == 1
    assert mutated.count(GUARD_ANCHOR) == 0
    assert authority.read_bytes() == authority_before
    assert (CARDANO / POLICY_SOURCE).read_text(encoding="utf-8") == original


@pytest.mark.parametrize(
    ("anchor", "replacement"),
    [
        (IMPORT_ANCHOR, "InlineDatum, Input, OutputReference, Output, Transaction"),
        (HELPER_ANCHOR, "fn renamed_seed_input(inputs: List<Input>, seed_ref: OutputReference) -> Int {"),
        (GUARD_ANCHOR, "expect InlineDatum(raw_datum) = other_output.datum"),
    ],
)
def test_mutant_fails_closed_on_drifted_anchor(
    tmp_path: Path, anchor: str, replacement: str
) -> None:
    policy, _, original = _disposable_source(tmp_path)
    assert original.count(anchor) == 1
    policy.write_text(original.replace(anchor, replacement, 1), encoding="utf-8")
    with pytest.raises(RuntimeError, match="mutation guard anchor must occur exactly once"):
        _mutant_source(tmp_path, "remove_inline_datum_guard")


@pytest.mark.parametrize("anchor", [IMPORT_ANCHOR, HELPER_ANCHOR, GUARD_ANCHOR])
def test_mutant_fails_closed_on_duplicate_anchor(tmp_path: Path, anchor: str) -> None:
    policy, _, original = _disposable_source(tmp_path)
    assert original.count(anchor) == 1
    policy.write_text(original + "\n" + anchor + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="mutation guard anchor must occur exactly once"):
        _mutant_source(tmp_path, "remove_inline_datum_guard")
