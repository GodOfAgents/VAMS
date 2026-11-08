#!/usr/bin/env python3
"""Sanitized offline Gitleaks capture for the refs already present locally."""
import collections
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path("/home/GodOfAgents/code/VAMS-testnet")
EVIDENCE = ROOT / "docs/remediation/m7_t06_local_history_89_r1"
SCANNER = Path("/home/GodOfAgents/vams-evidence/toolchains/gitleaks-8.30.1/gitleaks")
CONFIG = ROOT / ".gitleaks.toml"
PROTECTED = (
    "1321f91586784d218ebc11126de588fbcf649ec6",
    "174dbaa0393897107b9eafd283224d23a47572aa",
    "0161faebfba436fd3140d94dd0b9dbc91744f1bb",
    "31929a24419a9b7b9d8954cbea2df9fe1cb77a68",
)
EXPECTED_SCANNER_SHA256 = "88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509"
EXPECTED_CONFIG_SHA256 = "40ddce18233e73c94668ddd47a5abe2a6afa0e9bc4602657dc34ec2b78606ecd"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    return sha(path.read_bytes())


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True).stdout


def snapshot():
    refs = [line.split(" ", 1) for line in
            git("for-each-ref", "--format=%(refname) %(objectname)").decode("ascii").splitlines()]
    return {
        "head": git("rev-parse", "HEAD").decode("ascii").strip(),
        "branch": git("symbolic-ref", "--quiet", "--short", "HEAD").decode("ascii").strip(),
        "refs": [{"name": name, "oid": oid} for name, oid in refs],
        "ref_count": len(refs),
        "reachable_commit_count": int(git("rev-list", "--all", "--count").strip()),
        "is_shallow": git("rev-parse", "--is-shallow-repository").strip() == b"true",
        "porcelain_v1_z_sha256": sha(git("status", "--porcelain=v1", "-z", "--untracked-files=all")),
    }


def run():
    if ROOT.is_symlink() or EVIDENCE.is_symlink() or CONFIG.is_symlink() or SCANNER.is_symlink():
        raise RuntimeError("symlinked source/config/tool/evidence path")
    if digest(SCANNER) != EXPECTED_SCANNER_SHA256 or digest(CONFIG) != EXPECTED_CONFIG_SHA256:
        raise RuntimeError("pinned scanner or config hash mismatch")
    version = subprocess.run([str(SCANNER), "version"], cwd=ROOT, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, check=True).stdout.decode("ascii").strip()
    if version != "8.30.1":
        raise RuntimeError("scanner version mismatch")
    before = snapshot()
    if before["ref_count"] != 9 or before["reachable_commit_count"] != 89 or before["is_shallow"]:
        raise RuntimeError("local history shape differs from reviewed scope")
    absent = {}
    for oid in PROTECTED:
        cp = subprocess.run(["git", "cat-file", "-e", oid + "^{commit}"], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        absent[oid] = cp.returncode != 0
    if not all(absent.values()):
        raise RuntimeError("a formerly absent protected commit is present; stop for separate review")
    with tempfile.TemporaryDirectory(prefix="vams-t06-history-") as tmp:
        report = Path(tmp) / "report.json"
        command = [str(SCANNER), "git", "--log-opts=--all -m", ".",
                   "--config", str(CONFIG), "--redact=100", "--report-format", "json",
                   "--report-path", str(report), "--exit-code", "1", "--no-banner"]
        cp = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
        if cp.returncode not in (0, 1) or not report.is_file():
            raise RuntimeError("scanner failed; raw output intentionally withheld")
        raw = report.read_bytes()
        entries = json.loads(raw)
        if not isinstance(entries, list):
            raise RuntimeError("scanner report shape unexpected")
        rules = collections.Counter()
        for item in entries:
            if not isinstance(item, dict) or not isinstance(item.get("RuleID"), str):
                raise RuntimeError("scanner report entry shape unexpected")
            rules[item["RuleID"]] += 1
        report_sha = sha(raw)
        count = len(entries)
        if (cp.returncode == 0) != (count == 0):
            raise RuntimeError("scanner exit and report count disagree")
        # tempfile cleanup removes the redacted report before any evidence is written.
    after = snapshot()
    if after != before:
        raise RuntimeError("Git state changed during local-history scan")
    result = {
        "schema_version": "m7-t06-local-history-89-r1",
        "scope": "Only locally available refs; no fetch, hosted-ref inspection, rewrite, or credential access",
        "command": "gitleaks git --log-opts=\"--all -m\" . --config .gitleaks.toml --redact=100 --report-format json --report-path /tmp/<private>/report.json --exit-code 1 --no-banner",
        "execution_boundary": "bwrap --unshare-net; source read-only; only evidence directory writable; private /tmp",
        "tool": {"version": version, "sha256": digest(SCANNER), "path": str(SCANNER)},
        "config_sha256": digest(CONFIG),
        "capture_script_sha256": digest(Path(__file__)),
        "git_before": before,
        "git_after": after,
        "protected_commit_present": {oid: not was_absent for oid, was_absent in absent.items()},
        "scanner_exit_code": cp.returncode,
        "report_sha256": report_sha,
        "report_entry_count": count,
        "rule_counts": dict(sorted(rules.items())),
        "raw_report_retained": False,
        "stdout_stderr_retained": False,
        "limits": "This local scan cannot close T06: protected commits are absent locally; hosted refs, credential/provider revocation and impact, and any coordinated history operation remain external.",
    }
    EVIDENCE.joinpath("RUN.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"scanner_exit_code": cp.returncode, "report_entry_count": count,
                      "report_sha256": report_sha, "local_refs": before["ref_count"],
                      "reachable_commits": before["reachable_commit_count"],
                      "protected_commits_absent": all(absent.values())}, sort_keys=True))


if __name__ == "__main__":
    run()
