#!/usr/bin/env python3
"""Capture F05 synthetic evaluator provenance without changing the public harness.

Run this script itself under bwrap with canonical source read-only, no network,
and only --evidence writable. No result from this script is ledger admission.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HARNESS = ROOT / "scripts/remediation/test_f05_2a_authority_bootstrap_public.py"
CARDANO = ROOT / "cardano"
PINNED_AIKEN = Path("/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/unpacked/aiken-x86_64-unknown-linux-musl/aiken")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def inventory() -> dict[str, str]:
    explicit = [
        HARNESS,
        Path(__file__).resolve(),
        ROOT / "docs/remediation/m3_f05_design_r2/CONTRACT.json",
        ROOT / "docs/remediation/m3_f05_2a/AMENDMENT-R1.md",
        ROOT / "docs/remediation/m3_f05_2a/AMENDMENT-R1.SHA256",
        ROOT / "docs/remediation/m3_f05_2a/AMENDMENT-R2.md",
        ROOT / "docs/remediation/m3_f05_2a/AMENDMENT-R2.SHA256",
        ROOT / "docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json",
    ]
    explicit += list((ROOT / "docs/remediation/m3_f05_2a/tx_sim_r1").rglob("*"))
    explicit += list((ROOT / "scripts/remediation").glob("test_f05_2a_*.py"))
    explicit += list(CARDANO.rglob("*"))
    files = sorted({p for p in explicit if p.is_file() and
                    (not p.is_relative_to(CARDANO) or "build" not in p.relative_to(CARDANO).parts)})
    return {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in files}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", type=Path, required=True)
    ap.add_argument("--aiken", type=Path, default=PINNED_AIKEN)
    args = ap.parse_args()
    evidence = args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "submitted").mkdir(exist_ok=True)
    if args.aiken.resolve() != PINNED_AIKEN.resolve():
        raise SystemExit("Aiken path differs from the pinned local binary")
    if not HARNESS.is_file() or not PINNED_AIKEN.is_file():
        raise SystemExit("missing canonical harness or pinned Aiken")
    version = subprocess.run([str(PINNED_AIKEN), "--version"], capture_output=True, text=True, check=True)
    if "1.1.21" not in version.stdout + version.stderr:
        raise SystemExit("pinned Aiken did not report 1.1.21")
    before = inventory()
    write_json(evidence / "PROTECTED_BEFORE.json", before)
    spec = importlib.util.spec_from_file_location("f05_public_capture_target", HARNESS)
    if spec is None or spec.loader is None:
        raise SystemExit("cannot import public harness")
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    commands: list[dict] = []
    compiles: list[dict] = []
    evaluations: list[dict] = []
    keys: list[object] = []
    workroots: list[Path] = []
    original_run = subprocess.run
    original_compile = h._compile
    original_evaluate = h._evaluate
    original_committee = h._ephemeral_committee
    original_mkdtemp = h.tempfile.mkdtemp
    outcome: dict = {}
    index = 0

    def capture_mkdtemp(*a, **kw):
        result = original_mkdtemp(*a, **kw)
        workroots.append(Path(result))
        return result

    def capture_committee():
        result = original_committee()
        keys.extend(result)
        return result

    def capture_run(command, *a, **kw):
        nonlocal index
        argv = [str(x) for x in command]
        tracked = bool(argv and Path(argv[0]).resolve() == PINNED_AIKEN.resolve())
        record = None
        if tracked:
            index += 1
            record = {"sequence": index, "argv": argv, "cwd": str(kw.get("cwd")),
                      "kind": argv[1:3], "submitted_program": None}
            if argv[1:4] == ["uplc", "eval", "-d"]:
                submitted = Path(argv[4]).read_bytes()
                rel = f"submitted/program-{index:04d}.uplc"
                target = evidence / rel
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(submitted)
                record["submitted_program"] = {
                    "path": rel, "sha256": digest(submitted), "bytes": len(submitted)
                }
        try:
            result = original_run(command, *a, **kw)
        except BaseException as exc:
            if record is not None:
                record["exception"] = type(exc).__name__
                commands.append(record)
            raise
        if record is not None:
            record["exit"] = result.returncode
            stdout = result.stdout if isinstance(result.stdout, bytes) else (result.stdout or "").encode()
            stderr = result.stderr if isinstance(result.stderr, bytes) else (result.stderr or "").encode()
            record["stdout_sha256"] = digest(stdout)
            if argv[1:3] == ["blueprint", "policy"]:
                # Public policy command output is retained verbatim for parser audit.
                record["stdout"] = stdout.decode("utf-8", "replace")
                record["stderr"] = stderr.decode("utf-8", "replace")
            record["stderr_sha256"] = digest(stderr)
            if argv[1:3] == ["uplc", "eval"]:
                record["accepted"] = result.returncode == 0 and b"(con unit ())" in stdout
                record["cpu"] = max([int(x) for x in re.findall(rb'"cpu"\s*:\s*(\d+)', stdout)], default=None)
                record["mem"] = max([int(x) for x in re.findall(rb'"mem"\s*:\s*(\d+)', stdout)], default=None)
                record["diagnostic_tail"] = (stderr + b"\n" + stdout).decode("utf-8", "replace").splitlines()[-8:]
                submitted_path = Path(argv[4])
                record["submitted_program_post_sha256"] = digest(submitted_path.read_bytes())
                record["submitted_program_path_matches_argv"] = str(submitted_path) == argv[4]
                if record["submitted_program_post_sha256"] != record["submitted_program"]["sha256"] or not record["submitted_program_path_matches_argv"]:
                    raise RuntimeError("submitted UPLC program changed across child evaluation")
            commands.append(record)
        return result

    def capture_compile(cardano_source, aiken, work, parameters, mutation=None):
        command_before = len(commands)
        record = {
            "sequence": len(compiles) + 1,
            "work": str(work),
            "mutation": mutation,
            "parameter_cbor": {
                k: h.cbor(parameters[k]).hex() for k in ("genesis_ref", "initial_keys")
            },
        }
        record["parameter_sha256"] = {
            k: digest(bytes.fromhex(v)) for k, v in record["parameter_cbor"].items()
        }
        compiles.append(record)
        try:
            result = original_compile(cardano_source, aiken, work, parameters, mutation)
            policy_commands = [c for c in commands[command_before:] if c["kind"] == ["blueprint", "policy"]]
            if len(policy_commands) != 1:
                raise RuntimeError("compile lacks exactly one captured policy command")
            policy_command = policy_commands[0]
            parsed_ids = re.findall(r"\b[0-9a-f]{56}\b", policy_command["stdout"] + policy_command["stderr"])
            if not parsed_ids or parsed_ids[-1] != result["policy_id"].hex():
                raise RuntimeError("captured policy output does not bind compiled policy ID")
            record["policy_command_sequence"] = policy_command["sequence"]
            record["policy_output_id"] = parsed_ids[-1]
            record.update({
                "compiled_script_sha256": digest(result["code"]),
                "compiled_script_cbor_hex": result["code"].hex(),
                "applied_policy_id": result["policy_id"].hex(),
                "state_credential": result["state_credential"].hex(),
                "expected_credential": result["expected_credential"].hex(),
            })
            # Retain exact disposable mutant source and applied blueprints,
            # which are public. Never retain the anonymous signing keys.
            for name, file in {
                "policy_source": work / "cardano/validators/f05_authority_policy.ak",
                "authority_source": work / "cardano/lib/vams/f05_authority.ak",
                "applied_blueprint": work / "applied-2.json",
            }.items():
                data = file.read_bytes()
                rel = f"submitted/compile-{record['sequence']:03d}-{name}{file.suffix}"
                (evidence / rel).write_bytes(data)
                record[name] = {"path": rel, "sha256": digest(data), "bytes": len(data)}
            return result
        except BaseException as exc:
            record["exception"] = type(exc).__name__
            raise

    def capture_evaluate(aiken, code, context, work, label):
        record = {
            "sequence": len(evaluations) + 1,
            "label": label,
            "compiled_script_sha256": digest(code),
            "compiled_script_cbor_hex": code.hex(),
            "context_cbor_hex": h.cbor(context).hex(),
            "context_sha256": digest(h.cbor(context)),
            "purpose_policy_id": context["fields"][2]["fields"][0]["bytes"],
        }
        record["context_bytes"] = len(bytes.fromhex(record["context_cbor_hex"]))
        evaluations.append(record)
        command_before = len(commands)
        try:
            result = original_evaluate(aiken, code, context, work, label)
            record["result"] = result
            eval_commands = [c for c in commands[command_before:] if c["kind"] == ["uplc", "eval"]]
            if len(eval_commands) != 1:
                raise RuntimeError(f"evaluation {label} did not invoke exactly one captured Aiken UPLC eval")
            record["eval_command_sequence"] = eval_commands[0]["sequence"]
            submitted = eval_commands[0]["submitted_program"]
            if submitted is None:
                raise RuntimeError("actual submitted UPLC program missing")
            record["submitted_program"] = submitted
            if eval_commands[0]["exit"] != result["exit"] or eval_commands[0]["accepted"] != result["accepted"]:
                raise RuntimeError("captured child verdict disagrees with harness result")
            return result
        except BaseException as exc:
            record["exception"] = type(exc).__name__
            raise

    # Patch only the imported harness and its subprocess reference for this run.
    h.tempfile.mkdtemp = capture_mkdtemp
    h._ephemeral_committee = capture_committee
    h._compile = capture_compile
    h._evaluate = capture_evaluate
    subprocess.run = capture_run
    try:
        outcome = h._run_suite(PINNED_AIKEN)
        status = "suite_returned"
    except BaseException as exc:
        status = "suite_exception"
        outcome = {"exception": type(exc).__name__, "message": str(exc),
                   "traceback": traceback.format_exc().splitlines()[-16:]}
    finally:
        subprocess.run = original_run
        h.tempfile.mkdtemp = original_mkdtemp
        after = inventory()
        write_json(evidence / "PROTECTED_AFTER.json", after)
        write_json(evidence / "COMMANDS.json", commands)
        write_json(evidence / "COMPILES.json", compiles)
        write_json(evidence / "EVALUATIONS.json", evaluations)
        cleanup = {
            "workroots": [{"path": str(p), "removed": not p.exists()} for p in workroots],
            "signing_key_count": len(keys),
            "all_signing_memfds_closed": all(getattr(k, "fd", None) == -1 for k in keys),
        }
        report = {
            "schema": "f05-public-synthetic-mutation-provenance-v1",
            "status": status,
            "outcome": outcome,
            "protected_file_count": len(before),
            "protected_unchanged": before == after,
            "cleanup": cleanup,
            "commands": len(commands),
            "compiles": len(compiles),
            "evaluations": len(evaluations),
            "aiken_version": (version.stdout + version.stderr).strip(),
            "aiken_executable_sha256": digest(PINNED_AIKEN.read_bytes()),
            "capture_script_sha256": before[str(Path(__file__).resolve().relative_to(ROOT))],
            "policy_identity_class": "synthetic ephemeral committee; not frozen original applied-script identity",
            "evidence_class": "synthetic-compiled-UPLC-only; no ledger admission or live-network evidence",
            "sensitivity": "Public scripts, synthetic contexts, ephemeral public keys and signatures retained; private key bytes are never written.",
        }
        write_json(evidence / "CAPTURE.json", report)
        print(json.dumps({k: report[k] for k in ("status", "protected_file_count", "protected_unchanged", "cleanup", "commands", "compiles", "evaluations")}, indent=2))
    if before != after or not cleanup["all_signing_memfds_closed"] or not all(x["removed"] for x in cleanup["workroots"]):
        return 3
    if any(e.get("result") and "submitted_program" not in e for e in evaluations):
        return 4
    if status == "suite_returned":
        fixture = json.loads(h.FIXTURES.read_text(encoding="utf-8"))
        expected_negatives = {case["id"] for case in fixture["negative_cases"]}
        actual_negatives = {case["id"] for case in outcome["results"]} - {"valid_bootstrap", "r2_wrong_state_validator_hash_constant"}
        expected_mutations = {
            "remove_seed_guard", "remove_target_output_cardinality_guard",
            "remove_exact_mint_guard", "remove_state_validator_credential_binding",
            "remove_no_stake_credential_guard", "remove_singleton_quantity_guard",
            "remove_exact_lovelace_guard", "remove_no_extra_asset_guard",
            "remove_inline_datum_guard", "remove_schema_version_guard",
            "remove_seed_hash_guard", "remove_seed_index_guard", "remove_epoch_guard",
            "remove_threshold_guard", "remove_status_guard",
            "remove_pending_canonicality_guard", "remove_key_uniqueness_order_guard",
            "remove_key_binding_guard", "remove_key_order_guard",
            "remove_bootstrap_proof_of_possession_verification", "unconditional_success",
        }
        actual_mutations = {m["mutation"] for m in outcome["compiled_mutations"]}
        unconditional = next(m for m in outcome["compiled_mutations"] if m["mutation"] == "unconditional_success")
        covered = (len(fixture["negative_cases"]) == 55 and
                   len(outcome["results"]) == 57 and len(outcome["compiled_mutations"]) == 21 and
                   expected_negatives == actual_negatives and expected_mutations == actual_mutations and
                   len(unconditional["subcases"]) == 55 and
                   {x["id"] for x in unconditional["subcases"]} == expected_negatives and
                   len(evaluations) == sum(1 for c in commands if c["kind"] == ["uplc", "eval"]))
        report["coverage_assertions_pass"] = covered
        write_json(evidence / "CAPTURE.json", report)
        if not covered:
            return 5
    return 0 if status == "suite_returned" and outcome.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
