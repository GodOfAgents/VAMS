from __future__ import annotations
import hashlib, json, subprocess, sys
from pathlib import Path

root = Path("/home/GodOfAgents/code/VAMS-testnet")
family = root / "docs/remediation/m3_f05_2a_r4_tx_families/seed_reference_and_datum_binding"
out = root / "docs/remediation/m3_f05_2a_r4_family_freeze_r1"
out.mkdir(parents=True, exist_ok=True)
sum_result = subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=family,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
(out / "CHECKSUMS.stdout").write_text(sum_result.stdout)
(out / "CHECKSUMS.stderr").write_text(sum_result.stderr)
(out / "CHECKSUMS.exit").write_text(f"{sum_result.returncode}\n")
if sum_result.returncode:
    raise SystemExit("family SHA256SUMS verification failed")
sum_lines = (family / "SHA256SUMS").read_text().splitlines()
files = {}
for line in sum_lines:
    digest, rel = line.split("  ", 1)
    path = family / rel
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != digest:
        raise SystemExit(f"digest mismatch: {rel}")
    files[rel] = {"sha256": actual, "size_bytes": path.stat().st_size}
checksums_path = family / "SHA256SUMS"
files["SHA256SUMS"] = {
    "sha256": hashlib.sha256(checksums_path.read_bytes()).hexdigest(),
    "size_bytes": checksums_path.stat().st_size,
}
manifest = json.loads((family / "FAMILY-MANIFEST.json").read_text())
if (manifest["status"] != "fixtures prepared; pending independent family review; no simulator execution"
        or manifest["executions"] != 0 or not manifest["all_cases_pending"]
        or manifest["family_fixture_count"] != 3):
    raise SystemExit("unexpected R4 family status/count")
case_rows = []
for case in manifest["cases"]:
    if case["status"] != "PENDING" or case["script_invoked"] or case["simulator_result"] != "not run pending coordinator freeze and independent review":
        raise SystemExit(f"case is not pending/no-execution: {case['id']}")
    for role, entry in case["files"].items():
        rel = entry["path"]
        if rel not in files or files[rel]["sha256"] != entry["sha256"]:
            raise SystemExit(f"case artifact mismatch: {case['id']} {role}")
    case_rows.append({"id": case["id"], "status": case["status"],
                      "transaction_body_hash_blake2b_256": case["transaction_body_hash_blake2b_256"],
                      "artifacts": case["files"]})
freeze = {
    "schema_version": "f05-2a-r4-coordinator-freeze-r1",
    "date": "2026-10-03",
    "status": "coordinator_frozen_pending_independent_family_approval",
    "family_id": manifest["family_id"],
    "family_manifest_sha256": hashlib.sha256((family / "FAMILY-MANIFEST.json").read_bytes()).hexdigest(),
    "sha256sums_file_sha256": files["SHA256SUMS"]["sha256"],
    "fixture_file_count": len(files) - 1,
    "family_fixture_count": manifest["family_fixture_count"],
    "executions": 0,
    "cases": case_rows,
    "files": files,
    "checksum_command": "sha256sum -c SHA256SUMS",
    "checksum_exit": sum_result.returncode,
    "coordinator_scope": "Freeze exact local fixture bytes for independent review only; no Aiken simulator invocation or case admission is authorized by this record.",
    "freeze_gate": "Independent family approval is still required before any Aiken simulator invocation."
}
(out / "FREEZE.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": freeze["status"], "family_id": freeze["family_id"],
                  "fixture_file_count": freeze["fixture_file_count"],
                  "case_ids": [x["id"] for x in case_rows],
                  "checksum_exit": sum_result.returncode,
                  "freeze_sha256": hashlib.sha256((out / "FREEZE.json").read_bytes()).hexdigest()},
                 sort_keys=True))
