#!/usr/bin/env python3
"""M3.2b-R1 public-entrypoint and frozen-matrix sanity harness."""
from __future__ import annotations
import hashlib, json, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs/remediation/m3_2a_r7"
BLUEPRINT = ROOT / "cardano/plutus.json"
def main() -> int:
    matrix = json.loads((SPEC / "ACCEPTANCE_MATRIX.json").read_text())
    vectors = json.loads((SPEC / "ASSET_VECTORS.json").read_text())
    blueprint = json.loads(BLUEPRINT.read_text())
    rows = matrix["rows"]
    if len(rows) != 81 or len({row["id"] for row in rows}) != 81:
        raise AssertionError("frozen acceptance matrix is not the expected 81-row set")
    titles = {item["title"] for item in blueprint["validators"]}
    handlers = {row["handler"] for row in rows if row["handler"] not in {"public_handler", "all_policies", "policy"}}
    policy_handlers = {"authority_policy", "proposal_policy", "receipt_policy", "intent_policy"}
    missing = sorted(h for h in handlers if not any(f".{h}." in t for t in titles))
    missing += sorted(h for h in policy_handlers if not any(f".{h}." in t for t in titles))
    if missing:
        raise AssertionError(f"missing compiled public handler entrypoints: {missing}")
    prefixes = {
        "authority": bytes.fromhex("56414d532f617574686f726974792f763100"),
        "proposal": bytes.fromhex("56414d532f70726f706f73616c2f763100"),
        "receipt": bytes.fromhex("56414d532f726563656970742f763100"),
        "intent": bytes.fromhex("56414d532f696e74656e742f763100"),
    }
    for vector in vectors["vectors"]:
        preimage = prefixes[vector["kind"]] + b"".join(
            bytes.fromhex(field) for field in vector["fields_hex"]
        )
        if preimage.hex() != vector["preimage_hex"]:
            raise AssertionError(f"frozen preimage changed: {vector['id']}")
        if hashlib.blake2b(preimage, digest_size=32).hexdigest() != vector["digest_hex"]:
            raise AssertionError(f"frozen digest changed: {vector['id']}")
    with tempfile.NamedTemporaryFile(prefix="m3-2b-r3-results-", suffix=".json") as result:
        run = subprocess.run([
            sys.executable,
            str(Path(__file__).with_name("test_m3_2b_compiled_rows.py")),
            "--aiken",
            "/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken",
            "--output",
            result.name,
        ], capture_output=True, text=True)
        if run.returncode != 0:
            raise AssertionError("compiled public-handler evaluator failed")
        compiled = json.loads(Path(result.name).read_text())
    if compiled.get("executed") != 36 or compiled.get("pending") != 0 or compiled.get("failed"):
        raise AssertionError("compiled public-handler coverage is incomplete")
    print(json.dumps({
        "matrix_rows": len(rows),
        "compiled_named_handlers": sorted(handlers),
        "public_handler_rows_pending_evaluator": 0,
        "public_handler_rows_executed": compiled["executed"],
        "asset_vectors": len(vectors["vectors"]),
        "status": "compiled-pass",
    }, sort_keys=True))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
