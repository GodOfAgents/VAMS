#!/usr/bin/env python3
"""Governance v2 applied-identity rehearsal (synthetic, local, read-only).

What it does, in an isolated temporary copy of ``cardano/``:

1. Builds the blueprint and checks it matches the committed ``plutus.json``.
2. Applies the real validator parameters with ``aiken blueprint apply``:
   the bootstrap to ``governance_authority_v2``, then the resulting anchor to
   the governor, timelock and three policy validators. Computes every applied
   script hash.
3. Builds ledger-shaped ScriptContext values for each governance action with
   those hashes (``cardano/lib/vams/governance_v2_rehearsal.ak``) and evaluates
   every applied compiled validator on them with ``aiken uplc eval``.
4. Checks each accept case succeeds, each adversarial case fails, and records
   CPU/memory per script, per-transaction totals and applied script sizes.

Limits (also written into the output record): custodian keys, the seed UTxO,
the VAMS policy and amounts are synthetic; contexts are not ledger-validated
(no fees, min-UTxO, collateral, balance or signature checks); costs come from
the evaluator's built-in cost model, not live Pre-Prod parameters; the
protocol limits below are reference values to confirm against live Pre-Prod.
This is source-bound rehearsal evidence, not deployment evidence.

Usage: python3 governance_v2_applied_rehearsal.py --repo <repo> --out <json>
Requires ``aiken`` (pinned in cardano/aiken.toml) and ``script`` on PATH.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\]8;;[^\x1b]*\x1b\\")
SCRIPTS = {
    0: ("authority", "governance_authority_v2"),
    1: ("governor", "governor_v2"),
    2: ("timelock", "timelock_v2"),
    3: ("proposal", "proposal_policy_v2"),
    4: ("receipt", "receipt_policy_v2"),
    5: ("intent", "intent_policy_v2"),
}
HANDLER = {0: None, 1: "spend", 2: "spend", 3: "mint", 4: "mint", 5: "mint"}
# Reference values only; must be confirmed against live Pre-Prod parameters.
REFERENCE_LIMITS = {
    "max_tx_execution_memory": 14_000_000,
    "max_tx_execution_steps": 10_000_000_000,
    "max_tx_size_bytes": 16_384,
    "max_reference_script_bytes_per_tx": 204_800,
    "status": "REFERENCE_VALUES_NOT_CONFIRMED_AGAINST_LIVE_PREPROD",
}
SOURCES = [
    "cardano/aiken.toml",
    "cardano/aiken.lock",
    "cardano/plutus.json",
    "cardano/validators/governance_v2.ak",
    "cardano/lib/vams/governance.ak",
    "cardano/lib/vams/governance_v2.ak",
    "cardano/lib/vams/governance_v2_types.ak",
    "cardano/lib/vams/governance_v2_transitions.ak",
    "cardano/lib/vams/governance_v2_rehearsal.ak",
    "scripts/cardano/governance_v2_applied_rehearsal.py",
]


class RehearsalError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aiken(args: list[str], cwd: Path) -> str:
    """Run aiken under a pseudo-terminal (it reports nothing without one)."""
    command = ["script", "-qec", shlex.join(["aiken", *args]), "/dev/null"]
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    output = ANSI.sub("", result.stdout + result.stderr).replace("\r", "")
    if result.returncode != 0:
        raise RehearsalError(f"aiken {' '.join(args[:3])} failed:\n{output[-2000:]}")
    return output


def first_json(text: str) -> dict:
    start = text.index("{")
    value, _ = json.JSONDecoder().raw_decode(text[start:])
    return value


# ---- Plutus Data CBOR -> UPLC textual data ---------------------------------

def _head(data: bytes, pos: int) -> tuple[int, int | None, int]:
    initial = data[pos]
    major, info = initial >> 5, initial & 0x1F
    pos += 1
    if info < 24:
        return major, info, pos
    if info == 31:
        return major, None, pos
    size = {24: 1, 25: 2, 26: 4, 27: 8}[info]
    return major, int.from_bytes(data[pos:pos + size], "big"), pos + size


def _items(data: bytes, pos: int, count: int | None) -> tuple[list, int]:
    items = []
    while (data[pos] != 0xFF) if count is None else (len(items) < count):
        item, pos = decode(data, pos)
        items.append(item)
    return items, pos + 1 if count is None else pos


def decode(data: bytes, pos: int = 0):
    major, arg, pos = _head(data, pos)
    if major == 0:
        return ("I", arg), pos
    if major == 1:
        return ("I", -1 - arg), pos
    if major == 2:
        if arg is not None:
            return ("B", data[pos:pos + arg]), pos + arg
        chunks = b""
        while data[pos] != 0xFF:
            _, size, pos = _head(data, pos)
            chunks += data[pos:pos + size]
            pos += size
        return ("B", chunks), pos + 1
    if major == 4:
        items, pos = _items(data, pos, arg)
        return ("List", items), pos
    if major == 5:
        flat, pos = _items(data, pos, None if arg is None else 2 * arg)
        return ("Map", list(zip(flat[0::2], flat[1::2]))), pos
    if major == 6:
        if 121 <= arg <= 127 or 1280 <= arg <= 1400:
            fields, pos = decode(data, pos)
            index = arg - 121 if arg <= 127 else arg - 1280 + 7
            return ("Constr", index, fields[1]), pos
        if arg == 102:
            pair, pos = decode(data, pos)
            return ("Constr", pair[1][0][1], pair[1][1][1]), pos
        if arg in (2, 3):
            raw, pos = decode(data, pos)
            value = int.from_bytes(raw[1], "big")
            return ("I", value if arg == 2 else -1 - value), pos
    raise RehearsalError(f"unsupported CBOR major {major} arg {arg} at {pos}")


def to_text(node) -> str:
    kind = node[0]
    if kind == "I":
        return f"I {node[1]}"
    if kind == "B":
        return f"B #{node[1].hex()}"
    if kind == "List":
        return "List [" + ", ".join(to_text(item) for item in node[1]) + "]"
    if kind == "Map":
        return "Map [" + ", ".join(f"({to_text(k)}, {to_text(v)})" for k, v in node[1]) + "]"
    return f"Constr {node[1]} [" + ", ".join(to_text(field) for field in node[2]) + "]"


# ---- Evaluation ------------------------------------------------------------

def evaluate(code_hex: str, args: list[str], work: Path, name: str) -> dict:
    program = work / f"{name}.hex"
    program.write_text(code_hex)
    command = ["aiken", "uplc", "eval", "--cbor", str(program), *args]
    result = subprocess.run(command, cwd=work, capture_output=True, text=True, check=False)
    output = ANSI.sub("", result.stdout + result.stderr)
    if output.lstrip().startswith("{"):
        value = first_json(output)
        return {"ok": True, "result": value["result"], "cpu": value["cpu"], "mem": value["mem"]}
    cpu = re.search(r"cpu:\s*(\d+)", output)
    mem = re.search(r"memory:\s*(\d+)", output)
    if "Error" not in output or not cpu or not mem:
        raise RehearsalError(f"unrecognised evaluator output for {name}:\n{output[:2000]}")
    return {"ok": False, "cpu": int(cpu.group(1)), "mem": int(mem.group(1)), "output": output[:1500]}


def bytes_result(evaluation: dict) -> bytes:
    if not evaluation["ok"]:
        raise RehearsalError("helper evaluation failed:\n" + evaluation.get("output", ""))
    match = re.search(r"#([0-9a-f]*)", evaluation["result"].replace("\n", ""))
    if not match:
        raise RehearsalError(f"expected a bytestring result, got {evaluation['result'][:200]}")
    return bytes.fromhex(match.group(1))


def export(work: Path, name: str) -> str:
    args = ["export", "-m", "vams/governance_v2_rehearsal", "-n", name, "-f", "all"]
    return first_json(aiken(args, work))["compiledCode"]


def apply(work: Path, validator: str, param: bytes) -> tuple[str, dict]:
    out = f"applied-{validator}.json"
    aiken(["blueprint", "apply", "-m", "governance_v2", "-v", validator, "-o", out, param.hex()], work)
    blueprint = json.loads((work / out).read_text())
    codes = {v["title"].rsplit(".", 1)[1]: v for v in blueprint["validators"]
             if v["title"].startswith(f"governance_v2.{validator}.")}
    hashes = {v["hash"] for v in codes.values()}
    if len(hashes) != 1:
        raise RehearsalError(f"{validator}: handlers disagree on applied hash")
    return hashes.pop(), codes


def run(repo: Path) -> dict:
    sources = {name: sha256(repo / name) for name in SOURCES}
    with tempfile.TemporaryDirectory(prefix="vams-gov-v2-rehearsal-") as tmp:
        work = Path(tmp) / "cardano"
        shutil.copytree(repo / "cardano", work)
        committed = sha256(work / "plutus.json")
        version = aiken(["--version"], work).strip()
        aiken(["build"], work)
        rebuilt = sha256(work / "plutus.json")
        if rebuilt != committed:
            raise RehearsalError("rebuilt plutus.json differs from the committed blueprint")

        helpers = {name: export(work, name)
                   for name in ("bootstrap_cbor", "anchor_cbor", "case_cbor", "case_total")}
        bootstrap = bytes_result(evaluate(helpers["bootstrap_cbor"], [], work, "bootstrap"))
        authority, codes0 = apply(work, "governance_authority_v2", bootstrap)
        anchor = bytes_result(evaluate(helpers["anchor_cbor"], [f"(con data (B #{authority}))"], work, "anchor"))

        hashes = {"authority": authority}
        codes = {0: codes0}
        for index in range(1, 6):
            label, validator = SCRIPTS[index]
            hashes[label], codes[index] = apply(work, validator, anchor)
        if len(set(hashes.values())) != 6:
            raise RehearsalError("applied script hashes are not distinct")

        total = evaluate(helpers["case_total"], [], work, "case_total")
        count = int(re.search(r"integer\s+(\d+)", total["result"]).group(1))
        order = ["authority", "governor", "timelock", "proposal", "receipt", "intent"]
        hash_args = [f"(con data (B #{hashes[k]}))" for k in order]
        cases = []
        for index in range(count):
            raw = bytes_result(evaluate(helpers["case_cbor"], [*hash_args, f"(con data (I {index}))"],
                                        work, f"case_{index}"))
            decoded, end = decode(raw)
            if end != len(raw) or decoded[0] != "Constr":
                raise RehearsalError(f"case {index} did not decode as one Plutus constructor")
            cases.append(decoded)
        labels = [case[2][0][1] for case in cases]
        if len(set(labels)) != len(labels):
            raise RehearsalError("case labels are not unique")

        results, failures = [], []
        for case in cases:
            _, _, fields = case
            label = fields[0][1].decode()
            script = fields[1][1]
            expect_accept = fields[2][1] == 1
            context_text = to_text(fields[3])
            handler = HANDLER[script] or ("mint" if "mint" in label else "spend")
            entry = codes[script][handler]
            outcome = evaluate(entry["compiledCode"], [f"(con data ({context_text}))"], work,
                               re.sub(r"[^a-z0-9]+", "_", label))
            accepted = outcome["ok"] and "unit" in outcome.get("result", "")
            record = {
                "label": label, "script": SCRIPTS[script][0], "handler": handler,
                "expected": "accept" if expect_accept else "reject",
                "observed": "accept" if accepted else "reject",
                "cpu": outcome["cpu"], "mem": outcome["mem"],
                "context_text_sha256": hashlib.sha256(context_text.encode()).hexdigest(),
            }
            results.append(record)
            if accepted != expect_accept:
                failures.append(label)

        transactions: dict[str, dict] = {}
        for record in results:
            if record["expected"] != "accept":
                continue
            tx = record["label"].split("/")[0]
            total = transactions.setdefault(tx, {"scripts": 0, "cpu": 0, "mem": 0})
            total["scripts"] += 1
            total["cpu"] += record["cpu"]
            total["mem"] += record["mem"]
        for total in transactions.values():
            total["mem_share_of_reference_limit"] = round(total["mem"] / REFERENCE_LIMITS["max_tx_execution_memory"], 4)
            total["cpu_share_of_reference_limit"] = round(total["cpu"] / REFERENCE_LIMITS["max_tx_execution_steps"], 4)

        sizes = {}
        for index, (label, _) in SCRIPTS.items():
            code = next(iter(codes[index].values()))["compiledCode"]
            sizes[label] = len(code) // 2
        queue_reference_bytes = sum(sizes.values())

        checks = {
            "blueprint_rebuild_matches_committed": True,
            "applied_hashes_distinct": True,
            "all_cases_match_expectation": not failures,
            "every_tx_within_reference_execution_limits": all(
                t["mem"] <= REFERENCE_LIMITS["max_tx_execution_memory"]
                and t["cpu"] <= REFERENCE_LIMITS["max_tx_execution_steps"] for t in transactions.values()),
            "each_script_fits_one_reference_script_tx": all(
                size < REFERENCE_LIMITS["max_tx_size_bytes"] - 1_000 for size in sizes.values()),
            "queue_reference_scripts_within_per_tx_limit":
                queue_reference_bytes <= REFERENCE_LIMITS["max_reference_script_bytes_per_tx"],
        }
        return {
            "schema": "vams.governance_v2_applied_rehearsal/1",
            "status": "PASS" if all(checks.values()) else "FAIL",
            "evidence_class": "SOURCE_BOUND_SYNTHETIC_APPLIED_UPLC",
            "aiken_version": version,
            "sources_sha256": sources,
            "blueprint_sha256": committed,
            "parameters": {"bootstrap_cbor": bootstrap.hex(), "anchor_cbor": anchor.hex()},
            "applied_hashes": hashes,
            "applied_script_bytes": sizes,
            "reference_limits": REFERENCE_LIMITS,
            "checks": checks,
            "failures": failures,
            "transactions": transactions,
            "cases": results,
            "limits": [
                "Custodian key hashes, seed UTxO, VAMS policy and amounts are synthetic fixtures.",
                "Contexts are ledger-shaped but not ledger-validated: no fee, min-UTxO, collateral, balance or signature check.",
                "Costs use the evaluator's built-in cost model, not live Pre-Prod cost-model parameters.",
                "Reference limits are not confirmed against live Pre-Prod protocol parameters.",
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
    except RehearsalError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    args.out.write_text(json.dumps(record, indent=2) + "\n")
    print(f"{record['status']}: {sum(c['observed'] == c['expected'] for c in record['cases'])}"
          f"/{len(record['cases'])} cases as expected; failures={record['failures']}")
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
