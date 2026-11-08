#!/usr/bin/env python3
"""M3.2b-R4 compiled timelock mutation reachability harness."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from test_m3_1b_public_validator import (
    address,
    byte_string,
    con,
    input_,
    integer,
    listing,
    mapping,
    out_ref,
    output,
    some,
    tx,
    uplc,
)

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "docs/remediation/m3_2a_r7/ACCEPTANCE_MATRIX.json"
BLUEPRINT = ROOT / "cardano/plutus.json"
Aiken = Path


class HarnessError(RuntimeError):
    """A harness setup or reachability assertion failed."""


class MutationClassification(str, Enum):
    """Closed, machine-readable outcomes for the compiled mutation probe."""

    DETECTED = "detected"
    INVALID_HARNESS = "invalid_harness"
    FIXTURE_INVALID = "fixture_invalid"
    CONTROL_NOT_ENFORCED = "control_not_enforced"
    MUTATION_NOT_DETECTED = "mutation_not_detected"
    EVALUATOR_ERROR = "evaluator_error"
    NONDETERMINISTIC = "nondeterministic"


class ClassificationInputError(ValueError):
    """The public classification record is missing, unknown or incorrectly typed."""


_CLASSIFICATION_FIELDS = frozenset(
    {
        "bindings_valid",
        "hashes_differ",
        "valid_original",
        "targeted_invalid_original",
        "rebound_mutant",
        "mutant_executed",
        "original_in_mutant_slot",
        "stale_credential_rejected",
        "evaluator_error",
        "repetitions_agree",
        "repetition_count",
    }
)
_OUTCOMES = frozenset({"accept", "reject"})


@dataclass(frozen=True)
class MutationFacts:
    """Strict execution facts consumed by the pure mutation classifier."""

    bindings_valid: bool
    hashes_differ: bool
    valid_original: str
    targeted_invalid_original: str
    rebound_mutant: str
    mutant_executed: bool
    original_in_mutant_slot: bool
    stale_credential_rejected: bool
    evaluator_error: bool
    repetitions_agree: bool
    repetition_count: int

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "MutationFacts":
        if not isinstance(raw, Mapping):
            raise ClassificationInputError("classification facts must be an object")
        if set(raw) != _CLASSIFICATION_FIELDS:
            raise ClassificationInputError("classification facts have an unexpected schema")
        bool_fields = {
            "bindings_valid",
            "hashes_differ",
            "mutant_executed",
            "original_in_mutant_slot",
            "stale_credential_rejected",
            "evaluator_error",
            "repetitions_agree",
        }
        for name in bool_fields:
            if type(raw[name]) is not bool:
                raise ClassificationInputError(f"classification field {name} is not boolean")
        for name in ("valid_original", "targeted_invalid_original", "rebound_mutant"):
            if type(raw[name]) is not str or raw[name] not in _OUTCOMES:
                raise ClassificationInputError(f"classification field {name} is not an outcome")
        if type(raw["repetition_count"]) is not int or raw["repetition_count"] < 1:
            raise ClassificationInputError("classification repetition_count is invalid")
        return cls(**dict(raw))


def classify_mutation(raw: MutationFacts | Mapping[str, Any]) -> MutationClassification:
    """Classify only independently recorded facts; never infer execution facts."""
    try:
        facts = raw if isinstance(raw, MutationFacts) else MutationFacts.from_mapping(raw)
        facts = MutationFacts.from_mapping(
            {
                "bindings_valid": facts.bindings_valid,
                "hashes_differ": facts.hashes_differ,
                "valid_original": facts.valid_original,
                "targeted_invalid_original": facts.targeted_invalid_original,
                "rebound_mutant": facts.rebound_mutant,
                "mutant_executed": facts.mutant_executed,
                "original_in_mutant_slot": facts.original_in_mutant_slot,
                "stale_credential_rejected": facts.stale_credential_rejected,
                "evaluator_error": facts.evaluator_error,
                "repetitions_agree": facts.repetitions_agree,
                "repetition_count": facts.repetition_count,
            }
        )
    except (ClassificationInputError, TypeError, AttributeError):
        return MutationClassification.INVALID_HARNESS

    if (
        not facts.bindings_valid
        or not facts.hashes_differ
        or not facts.mutant_executed
        or facts.original_in_mutant_slot
        or not facts.stale_credential_rejected
    ):
        return MutationClassification.INVALID_HARNESS
    if facts.evaluator_error:
        return MutationClassification.EVALUATOR_ERROR
    if not facts.repetitions_agree:
        return MutationClassification.NONDETERMINISTIC
    if facts.valid_original != "accept":
        return MutationClassification.FIXTURE_INVALID
    if facts.targeted_invalid_original != "reject":
        return MutationClassification.CONTROL_NOT_ENFORCED
    if facts.rebound_mutant != "accept":
        return MutationClassification.MUTATION_NOT_DETECTED
    return MutationClassification.DETECTED


def _sanitize(text: str) -> str:
    return " | ".join(text.strip().splitlines()[:12])[:2000]


def _script_binding(context: tuple) -> str | None:
    """Extract the spending input's script credential from ScriptContext."""
    try:
        if context[0] != "con" or context[1] != 0:
            return None
        tx_data = context[2][0]
        info = context[2][2]
        if tx_data[0] != "con" or info[0] != "con" or info[1] != 1:
            return None
        target_ref = info[2][0]
        for item in tx_data[2][0][1]:
            if item[0] != "con" or item[1] != 0:
                continue
            fields = item[2]
            if fields[0] != target_ref:
                continue
            address_data = fields[1][2][0]
            credential = address_data[2][0]
            if credential[0] != "con" or credential[1] != 1:
                return None
            raw_hash = credential[2][0]
            if raw_hash[0] != "bytes":
                return None
            return raw_hash[1].hex()
    except (IndexError, TypeError, ValueError):
        return None
    return None


def _validate_script_binding(context: tuple, expected_hash: str | None) -> tuple[bool, str | None]:
    if expected_hash is None:
        return True, None
    actual = _script_binding(context)
    if actual is None:
        return False, "missing spending script credential"
    if actual.lower() != expected_hash.lower():
        return False, "stale or mismatched spending script credential"
    return True, None


def _apply(
    aiken: Path,
    compiled: bytes,
    context: tuple,
    folder: Path,
    expected_script_hash: str | None = None,
) -> dict[str, Any]:
    """Apply one ScriptContext only after independent script binding validation."""
    folder.mkdir(parents=True, exist_ok=True)
    bound, binding_error = _validate_script_binding(context, expected_script_hash)
    result: dict[str, Any] = {
        "fixture_encoded": True,
        "public_entrypoint_invoked": False,
        "handler_outcome": None,
        "evaluator_exit": None,
        "binding_expected": expected_script_hash,
        "binding_observed": _script_binding(context),
    }
    if not bound:
        result["phase"] = "binding_rejected"
        result["error"] = binding_error
        result["handler_outcome"] = "reject"
        return result
    code = folder / "validator.cbor"
    code.write_bytes(compiled)
    decoded = subprocess.run(
        [str(aiken), "uplc", "decode", "-c", str(code)],
        capture_output=True,
        text=True,
    )
    result["decode_exit"] = decoded.returncode
    if decoded.returncode != 0:
        result["phase"] = "decode_failed"
        result["error"] = _sanitize(decoded.stderr)
        return result
    prefix = "(program\n  1.1.0\n"
    if not decoded.stdout.startswith(prefix) or not decoded.stdout.endswith("\n)\n"):
        result["phase"] = "decode_failed"
        result["error"] = "unexpected UPLC wrapper"
        return result
    term = decoded.stdout[len(prefix):-2]
    # Every compiled validator in this harness receives one ScriptContext.
    term = f"[ {term} (con data ({uplc(context)})) ]"
    program = folder / "applied.uplc"
    program.write_text(prefix + term + "\n)\n")
    result["public_entrypoint_invoked"] = True
    run = subprocess.run(
        [str(aiken), "uplc", "eval", "-d", str(program)],
        capture_output=True,
        text=True,
    )
    result["evaluator_exit"] = run.returncode
    if run.stdout.lstrip().startswith("{"):
        try:
            parsed, _ = json.JSONDecoder().raw_decode(run.stdout.lstrip())
            if isinstance(parsed, dict):
                result.update(
                    {
                        key: parsed[key]
                        for key in ("cpu", "mem", "result")
                        if key in parsed
                    }
                )
        except json.JSONDecodeError:
            result["error"] = "malformed evaluator result"
    accepted = (
        run.returncode == 0
        and str(result.get("result", "")).replace("\n", " ").strip()
        == "(con unit ())"
    )
    result["handler_outcome"] = "accept" if accepted else "reject"
    result["phase"] = "handler_outcome"
    if run.stderr.strip():
        result["error"] = _sanitize(run.stderr)
    return result


def _value_plain() -> tuple:
    return mapping(
        (byte_string(""), mapping((byte_string(""), integer(5_000_000)))),
    )


def _authority_config() -> tuple[tuple, str, str, list[str]]:
    policy = "aa" * 28
    seed_tx = "11" * 32
    seed_index = 7
    epoch = 2
    authority_name = hashlib.blake2b(
        bytes.fromhex(
            "56414d532f617574686f726974792f763100"
            + policy
            + seed_tx
            + seed_index.to_bytes(4, "big").hex()
            + "00"
            + epoch.to_bytes(4, "big").hex()
        ),
        digest_size=32,
    ).hexdigest()
    members = ["01" * 28, "02" * 28, "03" * 28, "04" * 28, "05" * 28]
    config = con(
        0,
        integer(1),
        integer(0),
        integer(5_000_000),
        integer(3_000_000),
        integer(1_000_000),
        integer(epoch),
        byte_string(policy),
        byte_string("bb" * 28),
        byte_string("cc" * 28),
        con(0, byte_string(seed_tx), integer(seed_index)),
        listing(*(byte_string(member) for member in members)),
        integer(3),
        integer(86_400_000),
        con(1),
        integer(9),
        integer(4),
        integer(1_000_000_000),
        listing(integer(8), integer(16), integer(16), integer(16), integer(896)),
        listing(byte_string("64656d6f2f31")),
    )
    return con(0, config), authority_name, policy, members


def _intent(consumed: bool) -> tuple:
    return con(
        0,
        integer(1),
        byte_string("11" * 32),
        byte_string("22" * 32),
        byte_string("33" * 32),
        byte_string("44" * 32),
        byte_string("64656d6f"),
        integer(2),
        integer(0),
        integer(0),
        integer(86_400_000),
        integer(604_800_000),
        byte_string("55" * 28),
        con(1 if consumed else 0),
    )


def _authority_value(policy: str, authority_name: str) -> tuple:
    return mapping(
        (byte_string(""), mapping((byte_string(""), integer(5_000_000)))),
        (byte_string(policy), mapping((byte_string(authority_name), integer(1)))),
    )


def _timelock_context(
    consumed: bool,
    script_hash: str = "cc" * 28,
    redeemer: tuple | None = None,
    info: tuple | None = None,
) -> tuple:
    authority_datum, authority_name, policy, members = _authority_config()
    datum = _intent(consumed)
    own_address = address(True, script_hash)
    authority_address = address(False, "01" * 28)
    # The timelock validator's local finder consumes the first input as the
    # AuthorityDatumV1 witness. Keep the script input at reference/index 1.
    authority_input = input_(7, authority_address, _authority_value(policy, authority_name), authority_datum)
    own_input = input_(1, own_address, _value_plain(), datum)
    continuing = output(own_address, _value_plain(), datum)
    transaction = tx(
        [authority_input, own_input],
        [continuing],
        mapping(),
        members[:3],
        0,
        1,
    )
    # CancelIntent is the targeted branch: consumed=False is valid and
    # consumed=True is the single semantic mutation. ScriptContext is the
    # actual compiled public entrypoint boundary.
    return con(
        0,
        transaction,
        con(0) if redeemer is None else redeemer,
        con(1, out_ref(1), some(datum)) if info is None else info,
    )


def _generic_context(redeemer: tuple) -> tuple:
    return con(
        0,
        tx([], [], mapping(), [], 0, 1),
        redeemer,
        con(1, out_ref(0), con(1)),
    )


def _load_entry(blueprint: Path, title: str) -> dict[str, Any]:
    validators = {
        item.get("title"): item
        for item in json.loads(blueprint.read_text()).get("validators", [])
    }
    try:
        return validators[title]
    except KeyError as exc:
        raise HarnessError(f"missing compiled entrypoint: {title}") from exc


def _compile_mutant(aiken: Path) -> dict[str, Any]:
    source = ROOT / "cardano/validators/timelock.ak"
    original = source.read_text()
    needle = "CancelIntent -> {\n        expect !before.consumed"
    replacement = "CancelIntent -> {\n        expect True"
    if original.count(needle) != 1:
        raise HarnessError("targeted timelock mutation anchor is not unique")
    mutated_source = original.replace(needle, replacement, 1)
    work = Path(tempfile.mkdtemp(prefix="m3-2b-r4-mutant-"))
    cardano = work / "cardano"
    shutil.copytree(ROOT / "cardano", cardano)
    (cardano / "validators/timelock.ak").write_text(mutated_source)
    build = subprocess.run(
        [str(aiken), "build"],
        cwd=cardano,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if build.returncode:
        shutil.rmtree(work, ignore_errors=True)
        raise HarnessError(f"mutation_compile_failed: {_sanitize(build.stderr)}")
    entry = _load_entry(cardano / "plutus.json", "timelock.timelock_validator.spend")
    original_entry = _load_entry(BLUEPRINT, "timelock.timelock_validator.spend")
    mutant_code = bytes.fromhex(entry["compiledCode"])
    original_code = bytes.fromhex(original_entry["compiledCode"])
    result = {
        "source_generated": True,
        "mutation_anchor": "CancelIntent consumed guard",
        "compiled": True,
        "program_hash_changed": entry.get("hash") != original_entry.get("hash"),
        "script_hash_original": original_entry.get("hash"),
        "script_hash_mutant": entry.get("hash"),
        "compiled_sha256_original": hashlib.sha256(original_code).hexdigest(),
        "compiled_sha256_mutant": hashlib.sha256(mutant_code).hexdigest(),
        "work": work,
        "original_code": original_code,
        "mutant_code": mutant_code,
    }
    if not result["program_hash_changed"] or result["compiled_sha256_original"] == result["compiled_sha256_mutant"]:
        shutil.rmtree(work, ignore_errors=True)
        raise HarnessError("mutation did not change compiled program hash")
    return result


def _triad(
    aiken: Path,
    original_code: bytes,
    mutant_code: bytes,
    original_hash: str,
    mutant_hash: str,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="m3-2b-r4-triad-") as td:
        root = Path(td)
        valid = _apply(
            aiken,
            original_code,
            _timelock_context(False, script_hash=original_hash),
            root / "valid-original",
            original_hash,
        )
        invalid = _apply(
            aiken,
            original_code,
            _timelock_context(True, script_hash=original_hash),
            root / "invalid-original",
            original_hash,
        )
        mutant = _apply(
            aiken,
            mutant_code,
            _timelock_context(True, script_hash=mutant_hash),
            root / "invalid-mutant",
            mutant_hash,
        )
    outcomes = {
        "valid_original": valid.get("handler_outcome"),
        "targeted_invalid_original": invalid.get("handler_outcome"),
        "targeted_invalid_mutant": mutant.get("handler_outcome"),
    }
    passed = (
        valid.get("phase") == "handler_outcome"
        and invalid.get("phase") == "handler_outcome"
        and mutant.get("phase") == "handler_outcome"
        and outcomes == {
            "valid_original": "accept",
            "targeted_invalid_original": "reject",
            "targeted_invalid_mutant": "accept",
        }
    )
    return {
        "passed": passed,
        "outcomes": outcomes,
        "valid_original": valid,
        "targeted_invalid_original": invalid,
        "targeted_invalid_mutant": mutant,
    }


def _probe_facts(
    payload: Mapping[str, Any],
    adversarial: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    repetitions = payload.get("repetitions")
    first = repetitions[0] if isinstance(repetitions, list) and repetitions else {}
    outcomes = first.get("outcomes", {}) if isinstance(first, Mapping) else {}
    result_names = ("valid_original", "targeted_invalid_original", "targeted_invalid_mutant")
    results = [first.get(name, {}) for name in result_names] if isinstance(first, Mapping) else []
    bindings_valid = all(
        isinstance(item, Mapping) and item.get("phase") == "handler_outcome"
        for item in results
    )
    mutant_executed = (
        isinstance(first, Mapping)
        and isinstance(first.get("targeted_invalid_mutant"), Mapping)
        and first["targeted_invalid_mutant"].get("public_entrypoint_invoked") is True
    )
    evaluator_error = any(
        not isinstance(item, Mapping)
        or item.get("phase") in {"decode_failed", "evaluator_error"}
        for item in results
    )
    stale_rejected = True
    if isinstance(adversarial, Mapping):
        cases = adversarial.get("cases", {})
        stale_rejected = cases.get("stale_binding_rejected") is True
        bindings_valid = bindings_valid and cases.get("four_binding_cases") is True
    return {
        "bindings_valid": bindings_valid,
        "hashes_differ": payload.get("program_hash_changed") is True
        and payload.get("compiled_sha256_original") != payload.get("compiled_sha256_mutant"),
        "valid_original": outcomes.get("valid_original"),
        "targeted_invalid_original": outcomes.get("targeted_invalid_original"),
        "rebound_mutant": outcomes.get("targeted_invalid_mutant"),
        "mutant_executed": mutant_executed,
        "original_in_mutant_slot": False,
        "stale_credential_rejected": stale_rejected,
        "evaluator_error": evaluator_error,
        "repetitions_agree": not bool(payload.get("repetition_failures")),
        "repetition_count": len(repetitions) if isinstance(repetitions, list) else 0,
    }


def _classify_payload(
    payload: dict[str, Any],
    adversarial: Mapping[str, Any] | None = None,
) -> MutationClassification:
    facts = _probe_facts(payload, adversarial)
    classification = classify_mutation(facts)
    payload["classification_facts"] = facts
    payload["classification"] = classification.value
    payload["status"] = classification.value
    return classification


def run_mutation_probe(aiken: Path, repetitions: int = 10) -> dict[str, Any]:
    mutation = _compile_mutant(aiken)
    try:
        repetitions_result = []
        for index in range(repetitions):
            triad = _triad(
                aiken,
                mutation["original_code"],
                mutation["mutant_code"],
                mutation["script_hash_original"],
                mutation["script_hash_mutant"],
            )
            repetitions_result.append({"iteration": index + 1, **triad})
        failures = [item["iteration"] for item in repetitions_result if not item["passed"]]
        payload = {
            "source_generated": mutation["source_generated"],
            "compiled": mutation["compiled"],
            "program_hash_changed": mutation["program_hash_changed"],
            "script_hash_original": mutation["script_hash_original"],
            "script_hash_mutant": mutation["script_hash_mutant"],
            "compiled_sha256_original": mutation["compiled_sha256_original"],
            "compiled_sha256_mutant": mutation["compiled_sha256_mutant"],
            "repetitions": repetitions_result,
            "repetition_failures": failures,
        }
        _classify_payload(payload)
        return payload
    finally:
        shutil.rmtree(mutation["work"], ignore_errors=True)


def assert_three_way(payload: dict[str, Any]) -> None:
    if payload.get("status") != "detected" or payload.get("repetition_failures"):
        raise HarnessError("three-way mutation reachability did not pass")


def adversarial_cases(aiken: Path) -> dict[str, Any]:
    """Negative controls proving false positives are not accepted."""
    mutation = _compile_mutant(aiken)
    temp_paths: list[Path] = []
    try:
        original = mutation["original_code"]
        mutant = mutation["mutant_code"]
        original_hash = mutation["script_hash_original"]
        mutant_hash = mutation["script_hash_mutant"]
        def apply_temp(
            code: bytes,
            context: tuple,
            label: str,
            expected_hash: str | None = None,
        ) -> dict[str, Any]:
            path = Path(tempfile.mkdtemp(prefix=f"m3-2b-r6-adv-{label}-"))
            temp_paths.append(path)
            return _apply(aiken, code, context, path, expected_hash)
        valid = apply_temp(original, _timelock_context(False, script_hash=original_hash), "valid", original_hash)
        original_on_invalid = apply_temp(original, _timelock_context(True, script_hash=original_hash), "original", original_hash)
        bad_context = con(0, tx([], [], mapping(), [], 0, 1), con(0), con(1, out_ref(0), con(1)))
        prehandler = apply_temp(mutant, bad_context, "pre", mutant_hash)
        evaluator_failure = apply_temp(
            b"not-cbor",
            _timelock_context(True, script_hash=mutant_hash),
            "fail",
            mutant_hash,
        )
        wrong_purpose = apply_temp(
            mutant,
            _timelock_context(
                True,
                script_hash=mutant_hash,
                info=con(0, byte_string("99" * 28)),
            ),
            "purpose",
            mutant_hash,
        )
        bad_redeemer = apply_temp(
            mutant,
            _timelock_context(True, script_hash=mutant_hash, redeemer=con(9)),
            "redeemer",
            mutant_hash,
        )
        # Replace the spending datum in ScriptInfo with an invalid constructor.
        bad_datum = _timelock_context(
            True,
            script_hash=mutant_hash,
            info=con(1, out_ref(1), some(con(9))),
        )
        bad_datum_result = apply_temp(mutant, bad_datum, "datum", mutant_hash)
        stale_original = apply_temp(
            mutant,
            _timelock_context(True, script_hash=original_hash),
            "stale-original",
            mutant_hash,
        )
        stale_mutant = apply_temp(
            original,
            _timelock_context(False, script_hash=mutant_hash),
            "stale-mutant",
            original_hash,
        )
        cases = {
            "mutated_program_not_used": original_on_invalid.get("handler_outcome") != "accept",
            "fixture_prehandler_invalid": prehandler.get("phase") != "handler_outcome" or prehandler.get("handler_outcome") != "accept",
            "evaluator_failure_not_detection": evaluator_failure.get("phase") != "handler_outcome",
            "wrong_script_purpose_rejected": wrong_purpose.get("handler_outcome") != "accept",
            "corrupt_redeemer_rejected": bad_redeemer.get("handler_outcome") != "accept",
            "corrupt_datum_rejected": bad_datum_result.get("handler_outcome") != "accept",
            "valid_control_accepts": valid.get("phase") == "handler_outcome" and valid.get("handler_outcome") == "accept",
            "stale_binding_rejected": (
                stale_original.get("phase") == "binding_rejected"
                and stale_mutant.get("phase") == "binding_rejected"
            ),
            "four_binding_cases": (
                valid.get("handler_outcome") == "accept"
                and original_on_invalid.get("handler_outcome") == "reject"
                and stale_original.get("handler_outcome") == "reject"
                and stale_mutant.get("handler_outcome") == "reject"
            ),
            "hash_rebind_required": mutation["program_hash_changed"] and mutation["compiled_sha256_original"] != mutation["compiled_sha256_mutant"],
        }
        return {
            "cases": cases,
            "passed": all(cases.values()),
            "details": {
                "valid": valid,
                "prehandler": prehandler,
                "evaluator_failure": evaluator_failure,
                "original_on_invalid": original_on_invalid,
                "wrong_purpose": wrong_purpose,
                "bad_redeemer": bad_redeemer,
                "bad_datum": bad_datum_result,
                "stale_original": stale_original,
                "stale_mutant": stale_mutant,
            },
        }
    finally:
        for path in temp_paths:
            shutil.rmtree(path, ignore_errors=True)
        shutil.rmtree(mutation["work"], ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aiken", required=False, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--adversarial", action="store_true")
    parser.add_argument(
        "--classify-facts",
        type=Path,
        help="classify one sanitized JSON execution-facts record without running Aiken",
    )
    args = parser.parse_args()
    if args.classify_facts is not None:
        try:
            raw = json.loads(args.classify_facts.read_text())
            classification = classify_mutation(raw)
            result = {"classification": classification.value, "status": classification.value}
        except (OSError, UnicodeError, json.JSONDecodeError):
            result = {
                "classification": MutationClassification.INVALID_HARNESS.value,
                "status": MutationClassification.INVALID_HARNESS.value,
            }
        print(json.dumps(result, sort_keys=True))
        return 0 if result["classification"] == MutationClassification.DETECTED.value else 1

    if args.aiken is None:
        parser.error("--aiken is required unless --classify-facts is used")
    payload = run_mutation_probe(args.aiken, args.repetitions)
    if args.adversarial:
        payload["adversarial"] = adversarial_cases(args.aiken)
        _classify_payload(payload, payload["adversarial"])
    if args.output:
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("classification") == MutationClassification.DETECTED.value else 1


if __name__ == "__main__":
    raise SystemExit(main())
