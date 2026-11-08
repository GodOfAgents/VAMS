#!/usr/bin/env python3
"""Create sanitized M0.3b findings and reviewed decisions from a fresh scan."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m0_3b_adjudicator as m


def write_new(path, value):
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise m.AdjudicationError("output collision")
    descriptor, temporary = tempfile.mkstemp(
        prefix="." + path.name + ".",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(m.base.encoded(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run(repo, scanner, output):
    repo = Path(repo).resolve()
    scanner = Path(scanner).resolve()
    output = Path(output).resolve()
    if not output.is_dir():
        raise m.AdjudicationError("missing remediation directory")
    if m.base.digest(scanner.read_bytes()) != m.SCANNER_SHA256:
        raise m.AdjudicationError("scanner digest mismatch")
    version = subprocess.run(
        [str(scanner), "version"], capture_output=True, check=True
    ).stdout.decode().strip()
    if version != "8.30.1":
        raise m.AdjudicationError("scanner version mismatch")
    state = m.provenance(repo)
    if (
        state["head"] != "829ab544571f12efe50ecb5740f129c8acb3e16f"
        or state["submodule_commit"] != m.PIN
        or state["submodule_head"] != m.PIN
        or not state["submodule_clean"]
    ):
        raise m.AdjudicationError("unexpected repository state")
    manifest = m.base.source_manifest(repo)
    manifest_sha = m.base.digest(m.base.encoded(manifest))
    report, blobs, gitlinks, _, scanner_exit = m.scan_direct_tree(
        repo, scanner, state
    )
    if scanner_exit != 1:
        raise m.AdjudicationError("expected findings")
    identities = m.build_records(
        report,
        head=state["head"],
        commit=state["submodule_commit"],
        repo=repo,
        state=state,
        manifest_sha256=manifest_sha,
        owned_blobs=blobs,
    )
    review_path = "docs/remediation/m0_3b_r1/REVIEW.md"
    review_hash = m.base.digest((repo / review_path).read_bytes())
    decisions = []
    proof_counts = Counter()
    for identity in identities:
        proof, role = m.source_proof(
            repo,
            identity["relative_path"],
            identity["line_start"],
            identity["line_end"],
        )
        if proof not in m.PROOFS:
            raise m.AdjudicationError("finding lacks exact source proof")
        decision = dict(
            identity,
            source_review=proof,
            file_role=role,
            disposition="confirmed_noncredential_fixture",
            rationale=proof,
            reviewer_status="accepted",
            reviewer="codex_local_source_review",
            reachability={domain: "absent" for domain in sorted(m.DOMAINS)},
            evidence_refs=[{"path": review_path, "sha256": review_hash}],
        )
        m.validate_record(decision)
        relative = identity["relative_path"][len(m.PREFIX) + 1 :]
        if (
            relative not in blobs
            or m.pinned_blob(repo, state["submodule_commit"], relative)
            != (repo / identity["relative_path"]).read_bytes()
        ):
            raise m.AdjudicationError("finding source is not pinned direct blob")
        proof_counts[proof] += 1
        decisions.append(decision)
    expected = Counter(
        {
            "expected_custom_error_assertion": 83,
            "ecdsa_public_key_der": 75,
            "erc7201_storage_slot_constant": 2,
        }
    )
    if (
        len(identities) != 160
        or len({item["finding_id"] for item in identities}) != 160
        or len({item["relative_path"] for item in identities}) != 24
        or proof_counts != expected
        or m.NESTED_OPENZEPPELIN not in gitlinks
    ):
        raise m.AdjudicationError("unexpected direct tranche")
    findings_document = {
        "schema": "m0_3b_r1_findings",
        "records": identities,
    }
    decisions_document = {
        "schema": "m0_3b_r1_decisions",
        "records": sorted(decisions, key=lambda item: item["finding_id"]),
    }
    write_new(output / "findings.json", findings_document)
    write_new(output / "decisions.json", decisions_document)
    return {
        "schema": "m0_3b_r1_preparation",
        "scanner_exit": scanner_exit,
        "finding_count": len(identities),
        "path_count": len({item["relative_path"] for item in identities}),
        "proof_counts": dict(sorted(proof_counts.items())),
        "excluded_gitlink_count": len(gitlinks),
        "source_manifest_sha256": manifest_sha,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--scanner", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = run(args.repo, args.scanner, args.output)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "schema": "m0_3b_r1_preparation",
                    "status": "failure",
                    "type": type(exc).__name__,
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
