#!/usr/bin/env python3
"""Insurance fund applied-identity rehearsal (synthetic, local, read-only).

In an isolated temporary copy of ``cardano/`` this:

1. builds the blueprint and checks it matches the committed ``plutus.json``;
2. applies the six real parameters of ``insurance_fund`` (genesis reference,
   state asset name, guardians, threshold, policy epoch, payout cap) with
   ``aiken blueprint apply`` and computes the applied hash, which is also the
   state-token policy ID;
3. builds ledger-shaped ScriptContext values with that hash
   (``cardano/lib/vams/insurance_rehearsal.ak``) and evaluates the applied
   compiled validator on each with ``aiken uplc eval``;
4. checks accept/reject expectations, records CPU/memory per case, the fund
   datum size each transaction creates (cap 896 bytes) and the script size.

Same limits as the governance rehearsal: synthetic keys, seed and amounts;
not ledger-validated; evaluator cost model; reference protocol limits not
confirmed against live Pre-Prod. Not deployment evidence.

Usage: python3 insurance_applied_rehearsal.py --repo <repo> --out <json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import governance_v2_applied_rehearsal as common  # noqa: E402

SOURCES = [
    "cardano/aiken.toml",
    "cardano/aiken.lock",
    "cardano/plutus.json",
    "cardano/validators/insurance_fund.ak",
    "cardano/lib/vams/types.ak",
    "cardano/lib/vams/utils.ak",
    "cardano/lib/vams/insurance_rehearsal.ak",
    "scripts/cardano/insurance_applied_rehearsal.py",
    "scripts/cardano/governance_v2_applied_rehearsal.py",
]
DATUM_LIMIT = 896
MODULE = "vams/insurance_rehearsal"


def export(work: Path, name: str) -> str:
    args = ["export", "-m", MODULE, "-n", name, "-f", "all"]
    return common.first_json(common.aiken(args, work))["compiledCode"]


def run(repo: Path) -> dict:
    sources = {name: common.sha256(repo / name) for name in SOURCES}
    with tempfile.TemporaryDirectory(prefix="vams-insurance-rehearsal-") as tmp:
        work = Path(tmp) / "cardano"
        shutil.copytree(repo / "cardano", work)
        committed = common.sha256(work / "plutus.json")
        version = common.aiken(["--version"], work).strip()
        common.aiken(["build"], work)
        if common.sha256(work / "plutus.json") != committed:
            raise common.RehearsalError("rebuilt plutus.json differs from the committed blueprint")

        helpers = {name: export(work, name) for name in ("param_cbor", "case_cbor", "case_total")}
        params = []
        blueprint = "plutus.json"
        for index in range(6):
            raw = common.bytes_result(common.evaluate(
                helpers["param_cbor"], [f"(con data (I {index}))"], work, f"param_{index}"))
            params.append(raw.hex())
            out = f"applied-insurance-{index}.json"
            common.aiken(["blueprint", "apply", "-i", blueprint, "-m", "insurance_fund",
                          "-v", "insurance_fund", "-o", out, raw.hex()], work)
            blueprint = out
        applied = json.loads((work / blueprint).read_text())
        codes = {v["title"].rsplit(".", 1)[1]: v for v in applied["validators"]
                 if v["title"].startswith("insurance_fund.insurance_fund.")}
        hashes = {v["hash"] for v in codes.values()}
        if len(hashes) != 1:
            raise common.RehearsalError("insurance handlers disagree on applied hash")
        policy = hashes.pop()
        pending = [title for title, v in codes.items() if v.get("parameters")]
        if pending:
            raise common.RehearsalError(f"parameters left unapplied: {pending}")

        total = common.evaluate(helpers["case_total"], [], work, "case_total")
        count = int(re.search(r"integer\s+(\d+)", total["result"]).group(1))
        results, failures = [], []
        for index in range(count):
            raw = common.bytes_result(common.evaluate(
                helpers["case_cbor"], [f"(con data (B #{policy}))", f"(con data (I {index}))"],
                work, f"case_{index}"))
            decoded, end = common.decode(raw)
            if end != len(raw) or decoded[0] != "Constr":
                raise common.RehearsalError(f"case {index} did not decode")
            fields = decoded[2]
            label = fields[0][1].decode()
            handler = "mint" if fields[1][1] == 0 else "spend"
            expect_accept = fields[2][1] == 1
            datum_bytes = fields[3][1]
            context_text = common.to_text(fields[4])
            outcome = common.evaluate(codes[handler]["compiledCode"], [f"(con data ({context_text}))"],
                                      work, re.sub(r"[^a-z0-9]+", "_", label))
            accepted = outcome["ok"] and "unit" in outcome.get("result", "")
            results.append({
                "label": label, "handler": handler,
                "expected": "accept" if expect_accept else "reject",
                "observed": "accept" if accepted else "reject",
                "cpu": outcome["cpu"], "mem": outcome["mem"], "created_datum_bytes": datum_bytes,
                "context_text_sha256": hashlib.sha256(context_text.encode()).hexdigest(),
            })
            if accepted != expect_accept:
                failures.append(label)

        limits = common.REFERENCE_LIMITS
        accepted_cases = [r for r in results if r["expected"] == "accept"]
        script_bytes = len(codes["spend"]["compiledCode"]) // 2
        checks = {
            "blueprint_rebuild_matches_committed": True,
            "all_cases_match_expectation": not failures,
            "every_tx_within_reference_execution_limits": all(
                r["mem"] <= limits["max_tx_execution_memory"] and r["cpu"] <= limits["max_tx_execution_steps"]
                for r in accepted_cases),
            "accepted_states_within_datum_limit": all(
                r["created_datum_bytes"] <= DATUM_LIMIT for r in accepted_cases),
            "script_fits_one_reference_script_tx": script_bytes < limits["max_tx_size_bytes"] - 1_000,
        }
        for record in results:
            record["mem_share_of_reference_limit"] = round(record["mem"] / limits["max_tx_execution_memory"], 4)
            record["cpu_share_of_reference_limit"] = round(record["cpu"] / limits["max_tx_execution_steps"], 4)
        return {
            "schema": "vams.insurance_applied_rehearsal/1",
            "status": "PASS" if all(checks.values()) else "FAIL",
            "evidence_class": "SOURCE_BOUND_SYNTHETIC_APPLIED_UPLC",
            "aiken_version": version,
            "sources_sha256": sources,
            "blueprint_sha256": committed,
            "parameters_cbor": params,
            "applied_hash": policy,
            "applied_script_bytes": script_bytes,
            "datum_limit_bytes": DATUM_LIMIT,
            "reference_limits": limits,
            "checks": checks,
            "failures": failures,
            "cases": results,
            "limits": [
                "Guardian and claimant keys, seed UTxO and amounts are synthetic fixtures.",
                "Contexts are ledger-shaped but not ledger-validated: no fee, min-UTxO, collateral, balance or signature check.",
                "Costs use the evaluator's built-in cost model, not live Pre-Prod cost-model parameters.",
                "Reference limits are not confirmed against live Pre-Prod protocol parameters.",
                "Deposit stays disabled (F05); no bridge path is exercised.",
                "Not independent review, custody, or deployment evidence.",
            ],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        record = run(args.repo.resolve())
    except common.RehearsalError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    args.out.write_text(json.dumps(record, indent=2) + "\n")
    print(f"{record['status']}: {sum(c['observed'] == c['expected'] for c in record['cases'])}"
          f"/{len(record['cases'])} cases as expected; failures={record['failures']}")
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
