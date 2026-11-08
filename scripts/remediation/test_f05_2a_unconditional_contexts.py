"""Identity and fixture tests for the F05 unconditional-success mutation loop.

These checks use deterministic in-memory signers and a compile stub. They do not
claim a Plutus verdict or ledger admission.
"""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.remediation import test_f05_2a_authority_bootstrap_public as harness


class FakeSigner:
    def __init__(self, public_key: bytes) -> None:
        self.public_key = public_key

    def sign(self, message: bytes) -> bytes:
        return hashlib.sha512(self.public_key + message).digest()


@pytest.fixture
def material():
    keys = [bytes([index]) * 32 for index in range(1, 6)]
    signers = [FakeSigner(key) for key in keys]
    genesis_hash = bytes.fromhex("a1" * 32)
    genesis_index = 4
    state_credential = bytes.fromhex("b4" * 28)
    base_policy_id = bytes.fromhex("c1" * 28)
    mutant_policy_id = bytes.fromhex("d2" * 28)
    message = harness._canonical_pop_message(
        genesis_hash, genesis_index, state_credential, keys,
    )
    proofs = [signer.sign(message) for signer in signers]
    parameters = {
        "genesis_ref": harness._output_reference(genesis_hash, genesis_index),
        "initial_keys": harness.list_data([harness.byte_string(key) for key in keys]),
        "policy_id": base_policy_id.hex(),
        "state_credential": state_credential.hex(),
        "state_validator_hash": state_credential.hex(),
    }
    valid = harness._base_context(
        base_policy_id, state_credential, genesis_hash, genesis_index, keys, proofs,
    )
    return {
        "keys": keys, "signers": signers, "genesis_hash": genesis_hash,
        "genesis_index": genesis_index, "state_credential": state_credential,
        "base_policy_id": base_policy_id, "mutant_policy_id": mutant_policy_id,
        "proofs": proofs, "parameters": parameters, "valid": valid,
        "base_mutant": {"code": b"base-mutant-code", "policy_id": mutant_policy_id},
    }


def _datum_keys(context):
    state = context["fields"][0]["fields"][2]["list"][0]["fields"][2]["fields"][0]
    return [bytes.fromhex(item["bytes"]) for item in state["fields"][4]["list"]]


def _proofs(context):
    return [
        bytes.fromhex(item["bytes"])
        for item in context["fields"][1]["fields"][0]["list"]
    ]


def _mint_policy_ids(context):
    return [
        bytes.fromhex(entry["k"]["bytes"])
        for entry in context["fields"][0]["fields"][4]["map"]
    ]


def _output_policy_ids(context):
    result = []
    for output in context["fields"][0]["fields"][2]["list"]:
        result.extend(
            bytes.fromhex(entry["k"]["bytes"])
            for entry in output["fields"][1]["map"]
        )
    return result


def _purpose_policy_id(context):
    return bytes.fromhex(context["fields"][2]["fields"][0]["bytes"])


APPLIED_CASES = [
    "applied_genesis_parameter",
    "applied_keys_parameter",
    "applied_keys_bad_count",
    "applied_keys_bad_length",
    "applied_keys_duplicate",
    "applied_keys_unsorted",
]
ALL_NEGATIVE_CASES = [
    item["id"] for item in json.loads(harness.FIXTURES.read_text(encoding="utf-8"))[
        "negative_cases"
    ]
]
assert len(ALL_NEGATIVE_CASES) == len(set(ALL_NEGATIVE_CASES)) == 55
assert set(APPLIED_CASES) == {
    case_id for case_id in ALL_NEGATIVE_CASES if case_id.startswith("applied_")
}


@pytest.mark.parametrize("case_id", APPLIED_CASES)
def test_applied_context_uses_variant_policy_keys_and_proofs(case_id, material):
    m = material
    _, params = harness._mutate(
        case_id, m["valid"], m["parameters"], m["signers"],
    )
    variant_policy_id = bytes.fromhex("e3" * 28)
    context = harness._applied_case_context(
        case_id, params, variant_policy_id, m["state_credential"],
        m["genesis_hash"], m["genesis_index"], m["keys"],
        m["proofs"], m["signers"],
    )
    assert _purpose_policy_id(context) == variant_policy_id
    assert _mint_policy_ids(context) == [variant_policy_id]
    assert variant_policy_id in _output_policy_ids(context)

    expected_keys = (
        [bytes.fromhex(value) for value in harness.fixture_keys(params)]
        if case_id.startswith("applied_keys_bad_")
        or case_id in {"applied_keys_duplicate", "applied_keys_unsorted"}
        else m["keys"]
    )
    assert _datum_keys(context) == expected_keys
    if case_id in {"applied_keys_duplicate", "applied_keys_unsorted"}:
        expected_message = harness._canonical_pop_message(
            m["genesis_hash"], m["genesis_index"], m["state_credential"],
            expected_keys, require_canonical_keys=False,
        )
        expected_proofs = [
            next(signer for signer in m["signers"] if signer.public_key == key).sign(
                expected_message
            )
            for key in expected_keys
        ]
        assert _proofs(context) == expected_proofs
        assert _proofs(context) != m["proofs"]
    else:
        assert _proofs(context) == m["proofs"]


@pytest.mark.parametrize("case_id", ALL_NEGATIVE_CASES)
def test_unconditional_target_aligns_identity_for_every_negative_case(
    case_id, material, monkeypatch, tmp_path,
):
    m = material
    before_valid = copy.deepcopy(m["valid"])
    before_parameters = copy.deepcopy(m["parameters"])
    compile_calls = []

    def fake_compile(source, aiken, work, parameters, mutation=None):
        assert mutation == "unconditional_success"
        assert work == tmp_path / f"mutant-all-param-{case_id}"
        compile_calls.append(copy.deepcopy(parameters))
        digest = hashlib.sha256(harness.cbor(parameters["genesis_ref"])
                                + harness.cbor(parameters["initial_keys"])).digest()
        return {"code": b"variant-" + digest, "policy_id": digest[:28]}

    monkeypatch.setattr(harness, "_compile", fake_compile)
    code, policy_id, context = harness._unconditional_case_target(
        case_id, m["valid"], m["parameters"], m["base_policy_id"],
        m["base_mutant"], Path("/unused/aiken"), tmp_path, m["signers"],
        m["keys"], m["proofs"], m["genesis_hash"], m["genesis_index"],
        m["state_credential"],
    )
    assert m["valid"] == before_valid
    assert m["parameters"] == before_parameters
    harness._assert_unconditional_context_binding(
        case_id, context, m["base_policy_id"], policy_id,
    )
    assert _purpose_policy_id(context) == policy_id
    assert policy_id in _output_policy_ids(context) or case_id == "authority_output_missing"

    if case_id in APPLIED_CASES:
        assert len(compile_calls) == 1
        assert code.startswith(b"variant-")
        assert policy_id != m["mutant_policy_id"]
        assert compile_calls[0] != m["parameters"]
        expected_keys = (
            [bytes.fromhex(value) for value in harness.fixture_keys(compile_calls[0])]
            if case_id in {"applied_keys_bad_count", "applied_keys_bad_length",
                           "applied_keys_duplicate", "applied_keys_unsorted"}
            else m["keys"]
        )
        assert _datum_keys(context) == expected_keys
        assert _mint_policy_ids(context) == [policy_id]
    else:
        assert compile_calls == []
        assert (code, policy_id) == (
            m["base_mutant"]["code"], m["mutant_policy_id"],
        )
        if case_id == "mint_wrong_policy":
            # This malformed mint must remain wrong after rebinding; the
            # output value and script purpose still follow the mutant ID.
            assert _mint_policy_ids(context) == [bytes.fromhex("ee" * 28)]
            assert m["mutant_policy_id"] not in _mint_policy_ids(context)
        else:
            assert _mint_policy_ids(context) == [policy_id]


@pytest.mark.parametrize("defect", ["purpose", "mint", "output"])
def test_unconditional_binding_rejects_stale_policy_material(defect, material):
    m = material
    context = copy.deepcopy(m["valid"])
    harness._rebind_policy_id(context, m["base_policy_id"], m["mutant_policy_id"])
    if defect == "purpose":
        context["fields"][2]["fields"][0] = harness.byte_string(m["base_policy_id"])
    elif defect == "mint":
        context["fields"][0]["fields"][4]["map"][0]["k"] = harness.byte_string(
            m["base_policy_id"]
        )
    else:
        policies = context["fields"][0]["fields"][2]["list"][0]["fields"][1]["map"]
        next(pair for pair in policies if pair["k"]["bytes"] == m["mutant_policy_id"].hex())[
            "k"
        ] = harness.byte_string(m["base_policy_id"])
    with pytest.raises(AssertionError):
        harness._assert_unconditional_context_binding(
            "seed_missing", context, m["base_policy_id"], m["mutant_policy_id"],
        )


def test_unconditional_suite_retains_control_and_all_subcase_provenance(
    material, monkeypatch,
):
    m = material
    # Deterministic fake signers and compiler/evaluator: no keys, builds, or
    # Plutus execution. This tests orchestration/provenance, never acceptance.
    for signer in m["signers"]:
        signer.close = lambda: None
    monkeypatch.setattr(harness, "_ephemeral_committee", lambda: m["signers"])
    calls = []

    def fake_compile(source, aiken, work, parameters, mutation=None):
        code = (mutation or "base").encode() + harness.cbor(parameters["genesis_ref"])
        code += harness.cbor(parameters["initial_keys"])
        return {
            "code": code, "policy_id": hashlib.sha256(code).digest()[:28],
            "state_credential": harness.R2_FIXED_STATE_VALIDATOR_HASH,
            "expected_credential": (
                bytes.fromhex("cd" * 28) if mutation == "wrong_state_validator_hash_constant"
                else harness.R2_FIXED_STATE_VALIDATOR_HASH
            ),
        }

    def fake_evaluate(aiken, code, context, work, label):
        calls.append(label)
        accepted = label == "valid-bootstrap" or label.startswith("mutant")
        return {"accepted": accepted, "exit": 0 if accepted else 1}

    monkeypatch.setattr(harness, "_compile", fake_compile)
    monkeypatch.setattr(harness, "_evaluate", fake_evaluate)
    result = harness._run_suite(Path("/unused/aiken"))
    mutation = next(row for row in result["compiled_mutations"]
                    if row["mutation"] == "unconditional_success")
    assert mutation["positive_control"]["accepted"] is True
    assert calls.index("mutant-control-unconditional_success") < calls.index(
        "mutant-all-seed_missing"
    )
    assert [row["id"] for row in mutation["subcases"]] == ALL_NEGATIVE_CASES
    assert len({row["id"] for row in mutation["subcases"]}) == 55
    by_id = {row["id"]: row for row in mutation["subcases"]}
    for row in mutation["subcases"]:
        assert row["accepted"] is True
        for key in ("script_sha256", "context_sha256", "genesis_ref_cbor_sha256",
                    "initial_keys_cbor_sha256"):
            assert len(row[key]) == 64
    assert by_id["applied_genesis_parameter"]["genesis_ref_cbor_sha256"] != (
        by_id["seed_missing"]["genesis_ref_cbor_sha256"]
    )
    assert by_id["applied_keys_unsorted"]["initial_keys_cbor_sha256"] != (
        by_id["seed_missing"]["initial_keys_cbor_sha256"]
    )
    assert "no_transaction_witness_or_ledger_credit" in mutation["evidence_scope"]
