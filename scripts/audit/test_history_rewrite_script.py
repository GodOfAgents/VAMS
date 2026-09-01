from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit" / "history_rewrite.sh"
EXPECTED_ORIGIN = "https://github.com/GodOfAgents/VAMS.git"
TEST_TIME = "2026-08-25T12:00:00Z"


def _rotation_evidence() -> dict[str, object]:
    fingerprints = ("1" * 64, "2" * 64)

    def identity(fingerprint: str, address_digit: str) -> dict[str, object]:
        role_result = {"clear": True, "evidence_sha256": "3" * 64}
        return {
            "fingerprint_sha256": fingerprint,
            "key_type": "secp256k1",
            "decommissioned_at": TEST_TIME,
            "decommission_disposition": "permanently-decommissioned-no-replacement",
            "public_evm_identifier": "0x" + address_digit * 40,
            "no_replacement": True,
            "role_impact_checks": {
                role: dict(role_result)
                for role in (
                    "deployment_signer",
                    "funded_account",
                    "node",
                    "provider",
                    "safe",
                    "timelock",
                    "validator",
                )
            },
            "polygon_amoy": {
                "zero_balance": True,
                "observed_at": TEST_TIME,
                "block_number": 1,
                "evidence_sha256": "4" * 64,
            },
            "cardano_preprod": {
                "applicability": "cryptographically-inapplicable",
                "observed_at": TEST_TIME,
                "reason": "The exposed identity is an EVM secp256k1 key.",
                "evidence_sha256": "5" * 64,
            },
            "decommission_evidence_sha256": "6" * 64,
        }

    return {
        "schema_version": "1.0.0",
        "incident_id": "VAMS-PEM-2026-001",
        "reviewer": "Fixture Architect",
        "review_mode": "architect-owner",
        "independent_review": False,
        "reviewed_at": TEST_TIME,
        "approved_for_local_rewrite": True,
        "remote_force_push_approved": False,
        "affected_occurrences": [
            {
                "path": "node_identity.pem",
                "commit_sha": "a" * 40,
                "fingerprint_sha256": fingerprints[0],
            },
            {
                "path": "neuron/node_identity.pem",
                "commit_sha": "b" * 40,
                "fingerprint_sha256": fingerprints[1],
            },
        ],
        "affected_identities": [
            identity(fingerprints[0], "1"),
            identity(fingerprints[1], "2"),
        ],
        "provider_credentials": [
            {
                "provider": "infura",
                "fingerprint_sha256": "7" * 64,
                "revocation_status": "revoked",
                "exact_revocation_time_unavailable": True,
                "revoked_before": TEST_TIME,
                "observed_at": TEST_TIME,
                "access_review_clear": True,
                "billing_review_clear": True,
                "evidence_sha256": "8" * 64,
            }
        ],
    }


def _maintenance_approval(main_sha: str) -> dict[str, object]:
    def ruleset(rule_id: int, target: str) -> dict[str, object]:
        return {
            "id": rule_id,
            "name": f"VAMS-PEM-2026-001 freeze {target}",
            "enforcement": "active",
            "bypass_actor_count": 0,
            "current_user_can_bypass": "never",
        }

    return {
        "schema_version": "1.0.0",
        "incident_id": "VAMS-PEM-2026-001",
        "repository": "GodOfAgents/VAMS",
        "frozen_main_sha": main_sha,
        "frozen_at": TEST_TIME,
        "branch_ruleset": ruleset(1, "branches"),
        "tag_ruleset": ruleset(2, "tags"),
        "actions_enabled": False,
        "inventory_counts": {
            "branches": 1,
            "tags": 0,
            "releases": 0,
            "deployments": 0,
            "open_pull_requests": 0,
        },
        "authoritative_refs": {"refs/heads/main": main_sha},
        "approved_by": "Fixture Maintainer",
        "approved_at": TEST_TIME,
        "local_rewrite_approved": True,
        "remote_force_push_approved": False,
    }


def _write_valid_inputs(root: Path, mirror: Path) -> tuple[Path, Path]:
    rotation = root / "rotation.json"
    approval = root / "approval.json"
    main_sha = _git("rev-parse", "refs/heads/main", cwd=mirror)
    rotation.write_text(json.dumps(_rotation_evidence()), encoding="utf-8")
    approval.write_text(
        json.dumps(_maintenance_approval(main_sha)), encoding="utf-8"
    )
    return rotation, approval


def _bash() -> str:
    candidates: list[str | None] = []
    if os.name == "nt":
        candidates.extend(
            [
                r"C:\Program Files\Git\bin\bash.exe",
                r"C:\Program Files\Git\usr\bin\bash.exe",
            ]
        )
    candidates.append(shutil.which("bash"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise unittest.SkipTest("Bash is unavailable")


def _run(
    *args: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def _git(*args: str, cwd: Path | None = None) -> str:
    result = _run("git", *args, cwd=cwd)
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout.strip()


class HistoryRewriteScriptTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path]:
        source = root / "source"
        mirror = root / "mirror.git"
        source.mkdir()
        _git("init", "--initial-branch=main", cwd=source)
        _git("config", "user.name", "VAMS Test", cwd=source)
        _git("config", "user.email", "test@invalid.example", cwd=source)
        (source / "README.md").write_text("safe fixture\n", encoding="utf-8")
        _git("add", "README.md", cwd=source)
        _git("commit", "-m", "test fixture", cwd=source)
        _git("clone", "--mirror", str(source), str(mirror), cwd=root)
        _git("remote", "set-url", "origin", EXPECTED_ORIGIN, cwd=mirror)
        return source, mirror

    def test_inventory_accepts_only_mirror_and_does_not_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, mirror = self._fixture(root)
            evidence = root / "evidence"
            before = _git("rev-parse", "refs/heads/main", cwd=mirror)

            result = _run(
                _bash(),
                SCRIPT.as_posix(),
                "--mirror",
                mirror.as_posix(),
                "--evidence-dir",
                evidence.as_posix(),
                cwd=ROOT,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("No history was changed", result.stdout)
            self.assertEqual(before, _git("rev-parse", "refs/heads/main", cwd=mirror))
            self.assertTrue((evidence / "pre-refs.tsv").is_file())
            self.assertTrue((evidence / "pre-target-paths.tsv").is_file())
            self.assertTrue((evidence / "evidence-sha256.txt").is_file())
            self.assertFalse((evidence / "post-refs.tsv").exists())

    def test_rejects_working_clone(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, _ = self._fixture(root)
            result = _run(
                _bash(),
                SCRIPT.as_posix(),
                "--mirror",
                source.as_posix(),
                "--evidence-dir",
                (root / "evidence").as_posix(),
                cwd=ROOT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("bare mirror clone", result.stderr)

    def test_rejects_wrong_origin(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, mirror = self._fixture(root)
            _git("remote", "set-url", "origin", "https://example.invalid/not-vams.git", cwd=mirror)
            result = _run(
                _bash(),
                SCRIPT.as_posix(),
                "--mirror",
                mirror.as_posix(),
                "--evidence-dir",
                (root / "evidence").as_posix(),
                cwd=ROOT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("origin does not match", result.stderr)

    def test_rejects_evidence_inside_source_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, mirror = self._fixture(root)
            evidence = Path(tempfile.mkdtemp(prefix=".history-evidence-", dir=ROOT))
            try:
                result = _run(
                    _bash(),
                    SCRIPT.as_posix(),
                    "--mirror",
                    mirror.as_posix(),
                    "--evidence-dir",
                    evidence.as_posix(),
                    cwd=ROOT,
                )
            finally:
                shutil.rmtree(evidence, ignore_errors=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("outside the source checkout", result.stderr)

    def test_execute_requires_external_rotation_and_approval_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, mirror = self._fixture(root)
            before = _git("rev-parse", "refs/heads/main", cwd=mirror)
            result = _run(
                _bash(),
                SCRIPT.as_posix(),
                "--mirror",
                mirror.as_posix(),
                "--evidence-dir",
                (root / "evidence").as_posix(),
                "--execute",
                "--confirm-incident",
                "VAMS-PEM-2026-001",
                cwd=ROOT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("sanitized rotation evidence is required", result.stderr)
            self.assertEqual(before, _git("rev-parse", "refs/heads/main", cwd=mirror))

    def test_execute_requires_external_replacement_map(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, mirror = self._fixture(root)
            rotation, approval = _write_valid_inputs(root, mirror)
            result = _run(
                _bash(),
                SCRIPT.as_posix(),
                "--mirror",
                mirror.as_posix(),
                "--evidence-dir",
                (root / "evidence").as_posix(),
                "--execute",
                "--confirm-incident",
                "VAMS-PEM-2026-001",
                "--rotation-evidence",
                rotation.as_posix(),
                "--maintenance-approval",
                approval.as_posix(),
                cwd=ROOT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("non-empty --replace-text", result.stderr)

    def test_execute_rejects_empty_replacement_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, mirror = self._fixture(root)
            rotation, approval = _write_valid_inputs(root, mirror)
            replacement = root / "replacements.txt"
            replacement.write_text(
                "literal:fixture-source==>\n", encoding="utf-8"
            )
            result = _run(
                _bash(),
                SCRIPT.as_posix(),
                "--mirror",
                mirror.as_posix(),
                "--evidence-dir",
                (root / "evidence").as_posix(),
                "--execute",
                "--confirm-incident",
                "VAMS-PEM-2026-001",
                "--rotation-evidence",
                rotation.as_posix(),
                "--maintenance-approval",
                approval.as_posix(),
                "--replace-text",
                replacement.as_posix(),
                cwd=ROOT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "non-empty source and replacement values", result.stderr
            )

    def test_rejects_execution_inputs_inside_source_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, mirror = self._fixture(root)
            result = _run(
                _bash(),
                SCRIPT.as_posix(),
                "--mirror",
                mirror.as_posix(),
                "--evidence-dir",
                (root / "evidence").as_posix(),
                "--rotation-evidence",
                SCRIPT.as_posix(),
                cwd=ROOT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("outside the source checkout", result.stderr)

    def test_execute_rejects_placeholder_approvals_without_rewriting(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, mirror = self._fixture(root)
            before = _git("rev-parse", "refs/heads/main", cwd=mirror)
            rotation = root / "rotation.json"
            approval = root / "approval.json"
            replacement = root / "replacements.txt"
            rotation.write_text('{"status":"decommissioned"}', encoding="utf-8")
            approval.write_text('{"approved":true}', encoding="utf-8")
            replacement.write_text(
                "literal:fixture-source==>fixture-target\n", encoding="utf-8"
            )
            env = os.environ.copy()
            env["PYTHON_BIN"] = sys.executable

            result = _run(
                _bash(),
                SCRIPT.as_posix(),
                "--mirror",
                mirror.as_posix(),
                "--evidence-dir",
                (root / "evidence").as_posix(),
                "--execute",
                "--confirm-incident",
                "VAMS-PEM-2026-001",
                "--rotation-evidence",
                rotation.as_posix(),
                "--maintenance-approval",
                approval.as_posix(),
                "--replace-text",
                replacement.as_posix(),
                cwd=ROOT,
                env=env,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("incident evidence validation failed", result.stderr)
            self.assertEqual(before, _git("rev-parse", "refs/heads/main", cwd=mirror))

    def test_rejects_replacement_map_inside_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, mirror = self._fixture(root)
            evidence = root / "evidence"
            evidence.mkdir()
            replacement = evidence / "replacements.txt"
            replacement.write_text(
                "literal:fixture-source==>fixture-target\n", encoding="utf-8"
            )
            result = _run(
                _bash(),
                SCRIPT.as_posix(),
                "--mirror",
                mirror.as_posix(),
                "--evidence-dir",
                evidence.as_posix(),
                "--replace-text",
                replacement.as_posix(),
                cwd=ROOT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("outside the evidence directory", result.stderr)

    def test_script_has_no_remote_or_destructive_checkout_commands(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("git push", text)
        self.assertNotIn("git reset --hard", text)
        self.assertNotIn("git clean -fdx", text)
        self.assertNotIn("--force", text)
        self.assertIn("--sensitive-data-removal", text)
        self.assertIn("remote.origin.mirror", text)
        self.assertIn("+refs/*:refs/*", text)
        self.assertIn("--replace-text", text)
        self.assertIn("replacement_map_sha256", text)
        self.assertIn("NO REMOTE PUSH WAS PERFORMED", text)
        self.assertIn("GIT_CONFIG_KEY_${config_index}=core.protectNTFS", text)
        self.assertIn("GIT_CONFIG_VALUE_${config_index}=false", text)

    def test_execute_rewrites_targets_and_rehearses_only_local_mirror_push(self) -> None:
        if _run(sys.executable, "-m", "git_filter_repo", "-h", cwd=ROOT).returncode != 0:
            self.skipTest("git-filter-repo is unavailable")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, _ = self._fixture(root)
            mirror = root / "rewrite-mirror.git"
            (source / ".foundry").mkdir()
            (source / ".foundry" / "fixture.txt").write_text(
                "vendored fixture\n", encoding="utf-8"
            )
            (source / "node_identity.pem").write_text(
                "fixture identity marker\n", encoding="utf-8"
            )
            (source / "scripts").mkdir()
            (source / "scripts" / "simulate-request.mjs").write_text(
                "fixture legacy helper marker\n", encoding="utf-8"
            )
            old_uri = (
                "https://" + "fixture-user" + ":" + "fixture-pass" + "@example.invalid"
            )
            (source / "uri.txt").write_text(old_uri + "\n", encoding="utf-8")
            _git("add", ".", cwd=source)
            _git("commit", "-m", "add rewrite targets", cwd=source)
            _git("clone", "--mirror", str(source), str(mirror), cwd=root)
            _git("remote", "set-url", "origin", EXPECTED_ORIGIN, cwd=mirror)

            rotation, approval = _write_valid_inputs(root, mirror)
            replacement = root / "replacements.txt"
            evidence = root / "evidence"
            replacement.write_text(
                f"literal:{old_uri}==>https://example.invalid\n", encoding="utf-8"
            )
            env = os.environ.copy()
            env["PYTHON_BIN"] = sys.executable
            result = _run(
                _bash(),
                SCRIPT.as_posix(),
                "--mirror",
                mirror.as_posix(),
                "--evidence-dir",
                evidence.as_posix(),
                "--execute",
                "--confirm-incident",
                "VAMS-PEM-2026-001",
                "--rotation-evidence",
                rotation.as_posix(),
                "--maintenance-approval",
                approval.as_posix(),
                "--replace-text",
                replacement.as_posix(),
                cwd=ROOT,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(_git("log", "--all", "--format=%H", "--", ".foundry", cwd=mirror), "")
            self.assertEqual(
                _git("log", "--all", "--format=%H", "--", "node_identity.pem", cwd=mirror),
                "",
            )
            self.assertEqual(
                _git(
                    "log",
                    "--all",
                    "--format=%H",
                    "--",
                    "scripts/simulate-request.mjs",
                    cwd=mirror,
                ),
                "",
            )
            combined_evidence = "\n".join(
                path.read_text(encoding="utf-8", errors="ignore")
                for path in evidence.iterdir()
                if path.is_file()
            )
            self.assertNotIn(old_uri, combined_evidence)
            self.assertIn("replacement_map_sha256=", combined_evidence)
            self.assertTrue((evidence / "git-fsck.txt").is_file())

            local_remote = root / "local-rehearsal.git"
            _git("init", "--bare", str(local_remote), cwd=root)
            _git("push", "--mirror", str(local_remote), cwd=mirror)
            self.assertEqual(
                _git("for-each-ref", "--format=%(refname) %(objectname)", cwd=mirror),
                _git(
                    "for-each-ref",
                    "--format=%(refname) %(objectname)",
                    cwd=local_remote,
                ),
            )


if __name__ == "__main__":
    unittest.main()
