#!/usr/bin/env python3
"""M0.3a-R1: unsuppressed scan, sanitized decisions, exact content gate.

Acceptance is local source adjudication, never independent release approval.
No scanner match, value, snippet, or value-derived digest enters evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
import time

PREFIX = "contracts/lib/openzeppelin-contracts"
PIN = "239795bea728c8dca4deb6c66856dd58a6991112"
SCANNER_SHA256 = "88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509"
ALLOWED = {"confirmed_noncredential_fixture", "potential_credential", "unresolved"}
DOMAINS = {"production_compilation", "deployment", "runtime", "gateway", "frontend", "credential_loading", "ci_execution"}
PROOFS = {"expected_custom_error_assertion", "ecdsa_public_key_der"}
RATIONALES = PROOFS | {"missing_or_stale_evidence", "credential_or_ambiguous_datum", "review_incomplete"}
IDENTITY = {"finding_id", "head", "submodule", "submodule_commit", "submodule_head", "submodule_clean", "relative_path", "rule_id", "line_start", "line_end", "file_sha256"}
DECISION_FIELDS = IDENTITY | {"file_role", "source_review", "reachability", "reviewer_status", "reviewer", "rationale", "evidence_refs", "disposition", "source_manifest_sha256"}
FORBIDDEN = {"secret", "match", "fingerprint", "entropy", "raw", "rawmatch", "sourceline", "snippet", "value", "password", "token", "privatekey", "credential"}
HASH_FIELDS = {"finding_id", "head", "submodule_commit", "submodule_head", "file_sha256", "source_manifest_sha256", "sha256"}


class AdjudicationError(RuntimeError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def stable_id(head, commit, path, rule, start, end):
    return digest("|".join((head, commit, path, rule, str(start), str(end))).encode())


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AdjudicationError("duplicate JSON key")
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_pairs)


def safe_path(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_./-]{1,220}", value):
        raise AdjudicationError("unsafe path")
    p = PurePosixPath(value)
    if p.is_absolute() or any(x in {"", ".", ".."} for x in value.split("/")):
        raise AdjudicationError("noncanonical path")
    return value


def sanitized(value, field=""):
    """Defense in depth; schemas below further constrain all free text."""
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or re.sub(r"[^a-z]", "", key.lower()) in FORBIDDEN:
                raise AdjudicationError("forbidden evidence field")
            sanitized(child, key)
    elif isinstance(value, list):
        for child in value:
            sanitized(child, field)
    elif isinstance(value, str):
        if field in HASH_FIELDS:
            if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value):
                raise AdjudicationError("invalid digest")
        elif field in {"relative_path", "path", "submodule"}:
            safe_path(value)
            if re.search(r"[0-9a-fA-F]{32}|[A-Za-z0-9]{64}", value):
                raise AdjudicationError("unsafe long path value")
        elif field == "rule_id":
            if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", value) or re.search(r"[a-z0-9]{24}", value):
                raise AdjudicationError("invalid rule")
        elif len(value) > 96 or not re.fullmatch(r"[a-z][a-z0-9_]{0,95}", value):
            raise AdjudicationError("unsafe evidence text")
    elif value is not None and type(value) not in {bool, int}:
        raise AdjudicationError("unsafe evidence type")


def validate_record(r):
    sanitized(r)
    if set(r) != DECISION_FIELDS:
        raise AdjudicationError("record schema mismatch")
    if r["disposition"] not in ALLOWED or r["rationale"] not in RATIONALES:
        raise AdjudicationError("invalid disposition or rationale")
    if r["submodule"] != PREFIX or not r["relative_path"].startswith(PREFIX + "/"):
        raise AdjudicationError("outside tranche")
    if any(not re.fullmatch(r"[0-9a-f]{40}", r[k]) for k in ("head", "submodule_commit", "submodule_head")):
        raise AdjudicationError("invalid commit")
    for k in ("finding_id", "file_sha256", "source_manifest_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", r[k]):
            raise AdjudicationError("invalid sha256")
    if type(r["submodule_clean"]) is not bool:
        raise AdjudicationError("invalid clean state")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", r["rule_id"]):
        raise AdjudicationError("invalid rule")
    if any(type(r[k]) is not int for k in ("line_start", "line_end")) or not 1 <= r["line_start"] <= r["line_end"]:
        raise AdjudicationError("invalid line range")
    if r["finding_id"] != stable_id(r["head"], r["submodule_commit"], r["relative_path"], r["rule_id"], r["line_start"], r["line_end"]):
        raise AdjudicationError("identity mismatch")
    if r["file_role"] not in {"upstream_js_test", "upstream_public_vector", "unreviewed"}:
        raise AdjudicationError("invalid role")
    if r["source_review"] not in PROOFS | {"not_proven", "credential_or_ambiguous_datum"}:
        raise AdjudicationError("invalid source proof")
    if r["reviewer_status"] not in {"accepted", "pending_review", "rejected"} or r["reviewer"] not in {"codex_local_source_review", "pending"}:
        raise AdjudicationError("invalid reviewer")
    reach = r["reachability"]
    if not isinstance(reach, dict) or set(reach) != DOMAINS or any(v not in {"absent", "reachable", "not_assessed"} for v in reach.values()):
        raise AdjudicationError("invalid reachability")
    refs = r["evidence_refs"]
    if not isinstance(refs, list):
        raise AdjudicationError("invalid references")
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {"path", "sha256"} or len(ref["sha256"]) != 64:
            raise AdjudicationError("invalid reference")
    if r["disposition"] == "confirmed_noncredential_fixture":
        expected_role = "upstream_js_test" if r["source_review"] == "expected_custom_error_assertion" else "upstream_public_vector"
        if (r["source_review"] not in PROOFS or r["rationale"] != r["source_review"]
                or r["file_role"] != expected_role or r["reviewer_status"] != "accepted"
                or r["reviewer"] == "pending" or not refs or not r["submodule_clean"]
                or r["submodule_head"] != r["submodule_commit"] or set(reach.values()) != {"absent"}):
            raise AdjudicationError("confirmed finding lacks accepted proof")
    if r["disposition"] == "potential_credential" and (
            r["rationale"] != "credential_or_ambiguous_datum"
            or r["source_review"] != "credential_or_ambiguous_datum" or not refs):
        raise AdjudicationError("potential finding lacks blocker rationale")
    return r


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True).stdout


def provenance(repo):
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    entry = git(repo, "ls-tree", "HEAD", "--", PREFIX).decode().split()
    index = git(repo, "ls-files", "--stage", "--", PREFIX).decode().split()
    if len(entry) != 4 or entry[:2] != ["160000", "commit"] or len(index) != 4 or index[0] != "160000":
        raise AdjudicationError("missing gitlink")
    commit = entry[2]
    sub = repo / PREFIX
    subhead = git(sub, "rev-parse", "HEAD").decode().strip()
    clean = not git(sub, "status", "--porcelain", "--untracked-files=all", "--ignored")
    return {"head": head, "submodule": PREFIX, "submodule_commit": commit,
            "submodule_head": subhead, "submodule_clean": clean and index[1] == commit}


def file_bytes(repo, path):
    safe_path(path)
    target = repo / path
    if target.resolve() != target or not target.is_file():
        raise AdjudicationError("nonregular source")
    return target.read_bytes()


def source_manifest(repo):
    """First-party execution/configuration snapshot; never traverse gitlinks.

    Documentation is evidence, not an execution root. Any first-party source,
    script, workflow, manifest or unignored new file outside docs invalidates
    reachability review. Vendor contents are bound by the clean gitlink.
    """
    names = git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard").decode().split("\0")
    result = {}
    for name in sorted(set(names) - {""}):
        if name.startswith(("docs/", "codex-skills/", ".codex/", "contracts/lib/")) or name.endswith(".md"):
            continue
        path = repo / name
        if path.is_dir():  # gitlinks only; inspect no other submodule
            continue
        result[name] = digest(file_bytes(repo, name))
    return result


def source_proof(repo, path, start, end):
    """Recheck the exact two reviewed syntactic forms, not a vendor allowlist."""
    data = file_bytes(repo, path)
    lines = data.decode("utf-8").splitlines()
    if start != end or not 1 <= start <= len(lines):
        return "not_proven", "unreviewed"
    line = lines[start - 1]
    if path.startswith(PREFIX + "/test/") and path.endswith((".test.js", ".behavior.js")):
        if re.fullmatch(r"\s*\.to\.be\.revertedWithCustomError\(this\.[A-Za-z][A-Za-z0-9]*, (['`])(ERC[0-9]+[A-Za-z]+)\1\)\s*", line):
            return "expected_custom_error_assertion", "upstream_js_test"
    if path.startswith(PREFIX + "/test/") and path.endswith(".json"):
        match = re.fullmatch(r'\s*"keyDer"\s*:\s*"([0-9a-f]+)",?\s*', line)
        if match:
            doc = json.loads(data)
            groups = doc.get("testGroups", [])
            matching = [g for g in groups if g.get("keyDer") == match[1]]
            if (doc.get("algorithm") == "ECDSA" and matching
                    and all(g.get("key", {}).get("type") == "EcPublicKey" and g.get("type") == "EcdsaP1363Verify" for g in matching)):
                # Input/output stay in memory; persist only the public-form result.
                proc = subprocess.run(["openssl", "pkey", "-pubin", "-inform", "DER", "-noout"],
                                      input=bytes.fromhex(match[1]), capture_output=True)
                if proc.returncode == 0:
                    return "ecdsa_public_key_der", "upstream_public_vector"
    return "not_proven", "unreviewed"


def references_valid(repo, refs):
    return bool(refs) and all(digest(file_bytes(repo, r["path"])) == r["sha256"] for r in refs)


def build_records(report, *, head, commit, prefix=PREFIX, decisions=None, repo=None, state=None, manifest_sha256=None):
    if prefix != PREFIX:
        raise AdjudicationError("wrong tranche")
    decisions = [] if decisions is None else decisions
    if not isinstance(decisions, list):
        raise AdjudicationError("decisions must be a list keyed by finding_id")
    by_id = {}
    for d in decisions:
        sanitized(d)
        if not isinstance(d, dict) or "finding_id" not in d or d["finding_id"] in by_id:
            raise AdjudicationError("invalid or duplicate decision")
        if set(d) - DECISION_FIELDS:
            raise AdjudicationError("unknown decision fields")
        by_id[d["finding_id"]] = d
    state = state or {"head": head, "submodule": prefix, "submodule_commit": commit, "submodule_head": commit, "submodule_clean": False}
    records, seen = [], set()
    for item in report:
        path = item.get("File")
        if not isinstance(path, str):
            raise AdjudicationError("missing path")
        if path.startswith("./"):
            path = path[2:]
        safe_path(path)
        if not path.startswith(prefix + "/"):
            path = prefix + "/" + path
        rule, start, end = item.get("RuleID"), item.get("StartLine"), item.get("EndLine")
        if not isinstance(rule, str) or type(start) is not int or type(end) is not int:
            raise AdjudicationError("missing finding identity")
        identifier = stable_id(head, commit, path, rule, start, end)
        if identifier in seen:
            raise AdjudicationError("duplicate finding id")
        seen.add(identifier)
        sha = digest(file_bytes(repo, path)) if repo else "0" * 64
        r = dict(state, finding_id=identifier, relative_path=path, rule_id=rule, line_start=start, line_end=end,
                 file_sha256=sha, source_manifest_sha256=manifest_sha256 or "0" * 64,
                 file_role="unreviewed", source_review="not_proven", disposition="unresolved",
                 rationale="missing_or_stale_evidence", evidence_refs=[],
                 reachability={k: "not_assessed" for k in sorted(DOMAINS)}, reviewer_status="pending_review", reviewer="pending")
        d = by_id.get(identifier)
        if d is not None:
            complete = set(d) == DECISION_FIELDS
            bound = complete and all(d[k] == r[k] for k in IDENTITY | {"source_manifest_sha256"})
            if bound:
                try:
                    # A credential concern cannot be downgraded by a conflicting
                    # submitted label or a pending reviewer. Missing bindings
                    # still take the unresolved fallback above.
                    if d["source_review"] == "credential_or_ambiguous_datum":
                        d = dict(d, disposition="potential_credential", rationale="credential_or_ambiguous_datum")
                    validate_record(d)
                    refs_ok = repo is not None and references_valid(repo, d["evidence_refs"])
                    proof, role = source_proof(repo, path, start, end) if repo else ("not_proven", "unreviewed")
                    pinned = (repo is not None and state["submodule_clean"] and state["submodule_head"] == commit
                              and git(repo / prefix, "show", f"{commit}:{path[len(prefix)+1:]}") == file_bytes(repo, path))
                    if d["disposition"] == "potential_credential" and refs_ok and pinned:
                        r = d.copy()
                    elif refs_ok and pinned and proof == d["source_review"] and role == d["file_role"] and rule == "generic-api-key":
                        r = d.copy()
                except (AdjudicationError, OSError, subprocess.CalledProcessError, ValueError):
                    pass  # Missing, rejected, or stale evidence cannot confirm.
        records.append(validate_record(r))
    if set(by_id) - seen:
        raise AdjudicationError("unknown decision id")
    return sorted(records, key=lambda x: x["finding_id"])


def approved_gate(records, approved):
    """Exact approved-set reconciliation; removals require a separate review."""
    for r in records:
        validate_record(r)
    return (bool(records) and len({r["finding_id"] for r in records}) == len(records)
            and all(r["disposition"] == "confirmed_noncredential_fixture" for r in records)
            and encoded(records) == encoded(approved))


def publish(output, records, metadata, decisions, manifest):
    """Atomically publish sanitized blockers before the caller returns nonzero."""
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise AdjudicationError("output collision")
    for record in records:
        validate_record(record)
    safe_decisions = []
    for decision in decisions:
        try:
            validate_record(decision)
            if decision in records:
                safe_decisions.append(decision)
        except AdjudicationError:
            continue  # Never copy invalid user-supplied text into durable evidence.
    stage = Path(tempfile.mkdtemp(prefix=".m03-publish-", dir=output.parent))
    try:
        totals = {d: sum(r["disposition"] == d for r in records) for d in sorted(ALLOWED)}
        artifacts = {"adjudication-ledger.json": {"schema": "m0_3a_r1", "records": records},
                     "adjudication-summary.json": {"disposition_totals": totals, "observed_count": len(records), "path_count": len({r["relative_path"] for r in records})},
                     "record.json": metadata, "adjudication-decisions.json": safe_decisions, "source-manifest.json": manifest}
        for name, value in artifacts.items():
            (stage / name).write_bytes(encoded(value))
        (stage / "source-checksums.sha256").write_text("".join(f"{digest((stage / n).read_bytes())}  {n}\n" for n in sorted(artifacts)))
        os.rename(stage, output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def run_adjudication(repo, scanner, output, decisions_path=None, approved_sha256=None):
    repo, scanner, output = Path(repo).resolve(), Path(scanner).resolve(), Path(output).absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise AdjudicationError("invalid output destination")
    before = provenance(repo)
    if before["submodule_commit"] != PIN:
        raise AdjudicationError("unexpected gitlink")
    if digest(scanner.read_bytes()) != SCANNER_SHA256:
        raise AdjudicationError("scanner digest mismatch")
    version = subprocess.run([str(scanner), "version"], capture_output=True, check=True).stdout.decode().strip()
    if version != "8.30.1":
        raise AdjudicationError("scanner version mismatch")
    manifest = source_manifest(repo)
    manifest_sha = digest(encoded(manifest))
    decision_bytes = Path(decisions_path).read_bytes() if decisions_path else b"[]"
    decisions = json.loads(decision_bytes, object_pairs_hook=_pairs)
    if not isinstance(decisions, list):
        raise AdjudicationError("invalid decisions document")
    # Validate the entire input, including unknown IDs, before any publication.
    sanitized(decisions)
    if any(not isinstance(d, dict) or "finding_id" not in d or set(d) - DECISION_FIELDS for d in decisions):
        raise AdjudicationError("invalid decision fields")
    if len({d["finding_id"] for d in decisions}) != len(decisions):
        raise AdjudicationError("duplicate decision")
    started, tick = datetime.now(timezone.utc).isoformat(), time.monotonic()
    # POSIX mkdtemp mode 0700, raw scan never stored in the checkout.
    with tempfile.TemporaryDirectory(prefix="m03-raw-") as temp:
        os.chmod(temp, 0o700)
        raw = Path(temp) / "report.json"
        cmd = [str(scanner), "dir", ".", "--config", str(repo / ".gitleaks.toml"), "--redact=100",
               "--report-format", "json", "--report-path", str(raw), "--exit-code", "1", "--no-banner"]
        proc = subprocess.run(cmd, cwd=repo / PREFIX, capture_output=True)
        if proc.returncode not in {0, 1}:
            raise AdjudicationError("scanner failure")
        report = read_json(raw)
        if not isinstance(report, list) or bool(report) != (proc.returncode == 1):
            raise AdjudicationError("scanner result inconsistency")
        current = provenance(repo)
        if before != current or manifest != source_manifest(repo):
            current["submodule_clean"] = False
        identities = build_records(report, head=current["head"], commit=current["submodule_commit"], repo=repo,
                                   state=current, manifest_sha256=manifest_sha)
        known = {r["finding_id"] for r in identities}
        selected = [d for d in decisions if d.get("finding_id") in known]
        records = build_records(report, head=current["head"], commit=current["submodule_commit"], repo=repo,
                                state=current, decisions=selected, manifest_sha256=manifest_sha)
        after = provenance(repo)
        if after != current or manifest != source_manifest(repo):
            after["submodule_clean"] = False
            current = after
            records = build_records(report, head=current["head"], commit=current["submodule_commit"], repo=repo,
                                    state=current, manifest_sha256=manifest_sha)
        del report
    passed = False
    if approved_sha256 and decisions_path and digest(decision_bytes) == approved_sha256:
        passed = approved_gate(records, decisions)
    metadata = {"schema": "m0_3a_r1_run", **current, "started_utc": started,
                "finished_utc": datetime.now(timezone.utc).isoformat(), "duration_seconds": round(time.monotonic() - tick, 6),
                "command": cmd, "scanner_version": version, "scanner_sha256": SCANNER_SHA256,
                "scanner_exit": proc.returncode, "adjudication_exit": 0 if passed else 1,
                "source_manifest_sha256": manifest_sha, "raw_removed": True,
                "approved_decisions_sha256": approved_sha256, "independent_review": False,
                "input_decisions_sha256": digest(decision_bytes),
                "unknown_decision_count": len(decisions) - len(selected),
                "promotion_gates": "open"}
    publish(output, records, metadata, decisions, manifest)
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("repo", "scanner", "output"):
        parser.add_argument("--" + arg, required=True)
    parser.add_argument("--decisions")
    parser.add_argument("--approved-sha256")
    args = parser.parse_args()
    try:
        return run_adjudication(args.repo, args.scanner, args.output, args.decisions, args.approved_sha256)
    except Exception as exc:
        # Never echo untrusted fields, exception details, scanner output, or values.
        print("adjudication=failure type=" + type(exc).__name__, file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
