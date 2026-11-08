#!/usr/bin/env python3
"""Paired, rule-specific regression for the narrow Gitleaks exceptions.

External preparation: NOT RUN. This is not an execution/containment provider.
Only generated noncredential fixtures are scanned, never the repository tree.
A separately admitted invocation must bind tools, limits and complete cleanup.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".gitleaks.toml"
PINNED_CONFIG_SHA256 = "2a8e3b8313a84bae9abdda78bd6d44738b8c85d772bd5669d53f8aad04caed8e"
PINNED_GITLEAKS_SHA256 = "88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509"
SCAN_SECONDS = 10
REPORT_BYTES = 1_048_576
STREAM_BYTES = 16_384
ADDRESS_PATHS = (
    "neuron/config.py",
    "contracts/script/DeployX402.s.sol",
    "contracts/script/EmergencyLockdown.s.sol",
    "contracts/script/RegisterAgent.s.sol",
)
REDACTED = "REDACTED"
FINDING_KEYS = frozenset({
    "RuleID", "Description", "StartLine", "EndLine", "StartColumn", "EndColumn",
    "Match", "Secret", "File", "SymlinkFile", "Commit", "Entropy", "Author",
    "Email", "Date", "Message", "Tags", "Fingerprint",
})
OPTIONAL_FINDING_KEYS = frozenset({"Link"})


class InputError(RuntimeError):
    """Binding, scanner, capture or report failure; no backend detail is printed."""


class OracleError(RuntimeError):
    """Complete scan evidence contradicted a declared fixture expectation."""


@dataclass(frozen=True)
class Observation:
    path: str
    rule: str
    line: int
    redacted_match: str
    match_bytes: int
    start_column: int
    end_column: int


def expected_columns(line: int, offset: int, width: int) -> tuple[int, int]:
    # Pinned v8.30.1 detect/location.go uses the preceding LF byte as origin
    # after line one. This is a fixed source-derived profile, NOT calibrated
    # from returned findings. Native qualification must confirm the interface.
    first = offset + (1 if line == 1 else 2)
    return first, first + width - 1


@dataclass
class Fixtures:
    files: dict[str, list[str]]
    baseline: list[Observation]
    configured: list[Observation]

    def add(
        self, path: str, prefix: str, value: str, suffix: str,
        *, allowed: bool = False, rule: str = "generic-api-key",
    ) -> None:
        # The expected match comes from the fixture, not from scanner output.
        text = prefix + value + suffix
        if not text.isascii() or "\n" in text or "\r" in text:
            raise InputError("FIXTURE_ENCODING")
        lines = self.files.setdefault(path, [])
        lines.append(text)
        width = len(text.encode("ascii"))
        first, last = expected_columns(len(lines), 0, width)
        expected = Observation(
            path, rule, len(lines), prefix + REDACTED + suffix,
            width, first, last,
        )
        self.baseline.append(expected)
        if not allowed:
            self.configured.append(expected)

    def adjacent(self, path: str, address: str, credential: str) -> None:
        # Two candidates on the SAME allowlisted path and source line.
        public = 'api_key = "' + address + '"'
        protected = 'private_key = "' + credential + '"'
        lines = self.files.setdefault(path, [])
        lines.append(public + "; " + protected)
        public_start, public_end = expected_columns(len(lines), 0, len(public))
        private_start, private_end = expected_columns(
            len(lines), len(public) + 2, len(protected),
        )
        first = Observation(path, "generic-api-key", len(lines),
                            'api_key = "' + REDACTED + '"', len(public),
                            public_start, public_end)
        second = Observation(path, "generic-api-key", len(lines),
                             'private_key = "' + REDACTED + '"', len(protected),
                             private_start, private_end)
        self.baseline.extend((first, second))
        self.configured.append(second)


def fixture_cases() -> Fixtures:
    fixtures = Fixtures({}, [], [])
    # Public fixed seeds generate synthetic material; no live key is used.
    digest = hashlib.sha256(b"vams-address-exception-boundary-regression-v1").hexdigest()
    address = "0x" + digest[:40]
    long_value = "0x" + digest
    forms = (
        ('api_key = "', '"'),
        ("api_key = '", "'"),
        ("api_key = " + chr(96), chr(96)),
        ("api_key=", ";"),
    )
    for path in (*ADDRESS_PATHS, "outside/address-scope.txt"):
        in_scope = path in ADDRESS_PATHS
        for prefix, suffix in forms:
            fixtures.add(path, prefix, address, suffix, allowed=in_scope)
            fixtures.add(path, prefix, long_value, suffix)
        for value in (
            "0x" + digest[:39], "0x" + digest[:41],
            "0x" + digest + "a", "a" + address, address + "g",
            "0X" + digest[:40],
        ):
            fixtures.add(path, 'api_key = "', value, '"')
        fixtures.add(path, 'api_key = "', "0x" + digest[:40].upper(), '"',
                     allowed=in_scope)
        if in_scope:
            fixtures.adjacent(path, address, long_value)
            fixtures.add(path, 'api_key = "', address, '"', allowed=True)
            fixtures.add(path, 'private_key = "', long_value, '"')

    curve = "ec." + "SECP256K1"
    fixtures.add("neuron/secp256k1.py", "key.curve, ", curve, "", allowed=True)
    fixtures.add("outside/curve-scope.py", "key.curve, ", curve, "")
    fixtures.add("scripts/security/gitleaks_allowlist_regression.py",
                 "key.curve, ", curve, "\\n", allowed=True)

    private = hashlib.sha256(b"vams-private-key-negative-fixture").hexdigest()
    generic = base64.urlsafe_b64encode(
        hashlib.sha256(b"vams-generic-token-negative-fixture").digest()
    ).decode("ascii").rstrip("=")
    aws_suffix = base64.b32encode(
        hashlib.sha256(b"vams-aws-negative-fixture").digest()
    ).decode("ascii")[:16]
    fixtures.add("outside/private-key.txt", 'private_key = "', private, '"')
    fixtures.add("outside/generic-token.txt", 'api_key = "', generic, '"')
    # The AWS rule matches the token, not its assignment identifier.
    fixtures.add("outside/aws-token.txt", "", "AKIA" + aws_suffix, "",
                 rule="aws-access-token")
    return fixtures


def strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise InputError("DUPLICATE_REPORT_MEMBER")
        result[key] = value
    return result


def reject_constant(_value: str) -> object:
    raise InputError("NONFINITE_REPORT_NUMBER")


def config_pair() -> tuple[bytes, bytes]:
    configured = CONFIG.read_bytes()
    if hashlib.sha256(configured).hexdigest() != PINNED_CONFIG_SHA256:
        raise InputError("CONFIG_BINDING")
    text = configured.decode("utf-8")
    document = tomllib.loads(text)
    if set(document) != {"title", "extend", "allowlists"}:
        raise InputError("CONFIG_SCHEMA")
    if document["extend"] != {"useDefault": True}:
        raise InputError("DEFAULT_RULES_CHANGED")
    allowlists = document["allowlists"]
    if not isinstance(allowlists, list) or len(allowlists) != 3:
        raise InputError("EXCEPTION_SET")
    # Remove only CUSTOM exceptions; the default detector configuration remains.
    prefix, separator, _ = text.partition("[[allowlists]]")
    expected = {key: value for key, value in document.items() if key != "allowlists"}
    if not separator or tomllib.loads(prefix) != expected:
        raise InputError("COUNTERFACTUAL_CONFIG")
    return prefix.encode("utf-8"), configured


def scanner_binary() -> Path:
    value = os.environ.get("GITLEAKS_BIN") or shutil.which("gitleaks")
    if not value:
        raise InputError("SCANNER_UNAVAILABLE")
    binary = Path(value).resolve(strict=True)
    if not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest() != PINNED_GITLEAKS_SHA256:
        raise InputError("SCANNER_BINDING")
    return binary


def read_findings(report: Path, known_paths: set[str]) -> Counter[Observation]:
    if not report.is_file() or report.is_symlink() or report.stat().st_size > REPORT_BYTES:
        raise InputError("REPORT_UNAVAILABLE_OR_OVERSIZE")
    data = json.loads(report.read_bytes(), object_pairs_hook=strict_object,
                      parse_constant=reject_constant)
    if not isinstance(data, list):
        raise InputError("REPORT_SCHEMA")
    result: Counter[Observation] = Counter()
    for item in data:
        if not isinstance(item, dict):
            raise InputError("FINDING_SCHEMA")
        keys = set(item)
        if not FINDING_KEYS <= keys or not keys <= FINDING_KEYS | OPTIONAL_FINDING_KEYS:
            # Fragment, diagnostic and future fields are not admitted implicitly.
            raise InputError("FINDING_MEMBERS")
        for key in ("Description", "SymlinkFile", "Commit", "Author", "Email",
                    "Date", "Message", "Fingerprint"):
            if not isinstance(item[key], str):
                raise InputError("FINDING_METADATA")
        if (any(item[key] for key in ("SymlinkFile", "Commit", "Author", "Email",
                                     "Date", "Message")) or item.get("Link", "") != ""):
            raise InputError("UNEXPECTED_SOURCE_METADATA")
        if (type(item["Entropy"]) not in (int, float)
                or not 0 <= item["Entropy"] <= 8):
            raise InputError("FINDING_ENTROPY_TYPE")
        tags = item["Tags"]
        if tags is not None and (not isinstance(tags, list)
                                 or any(not isinstance(tag, str) for tag in tags)):
            raise InputError("FINDING_TAGS")
        path, rule = item.get("File"), item.get("RuleID")
        if not isinstance(path, str) or not isinstance(rule, str) or not rule:
            raise InputError("FINDING_IDENTITY")
        path = path.replace("\\", "/")
        if path not in known_paths or str(PurePosixPath(path)) != path:
            raise InputError("UNLISTED_FINDING_PATH")
        coordinates = [item.get(key) for key in (
            "StartLine", "EndLine", "StartColumn", "EndColumn",
        )]
        if any(type(value) is not int or value < 1 for value in coordinates):
            raise InputError("FINDING_COORDINATES")
        start, end, column, last = coordinates
        if start != end or last < column:
            raise InputError("FINDING_SPAN")
        match, secret = item.get("Match"), item.get("Secret")
        if not isinstance(match, str) or secret != REDACTED:
            raise InputError("FINDING_REDACTION")
        # Entire redacted match and original span expose partial captures.
        observation = Observation(path, rule, start, match, last - column + 1,
                                  column, last)
        result[observation] += 1
        if result[observation] != 1:
            raise InputError("DUPLICATE_FINDING")
    return result


def tree_hashes(tree: Path, fixtures: Fixtures) -> dict[str, str]:
    return {name: hashlib.sha256((tree / name).read_bytes()).hexdigest()
            for name in fixtures.files}


def scan(binary: Path, tree: Path, config: Path, report: Path) -> None:
    # Two direct scanner creations in the complete proposed campaign.
    # The caller/provider must enforce complete-tree limits and cleanup.
    # Direct-child timeout and post-capture size checks are not containment.
    result = subprocess.run(
        [str(binary), "dir", ".", "--config", str(config), "--redact=100",
         "--report-format", "json", "--report-path", str(report),
         "--exit-code", "1", "--no-banner", "--log-level", "error"],
        cwd=tree, check=False, capture_output=True, timeout=SCAN_SECONDS,
    )
    if len(result.stdout) > STREAM_BYTES or len(result.stderr) > STREAM_BYTES:
        raise InputError("CAPTURE_OVERSIZE")
    if result.stdout or result.stderr:
        raise InputError("SCANNER_DIAGNOSTIC")
    # Both scans contain blocked fixtures: zero is not accepted as a clean pass.
    if result.returncode != 1:
        raise InputError("SCANNER_EXIT")


def main() -> int:
    try:
        baseline, configured = config_pair()
        binary = scanner_binary()
        fixtures = fixture_cases()
        baseline_expected = Counter(fixtures.baseline)
        configured_expected = Counter(fixtures.configured)
        if any(count != 1 for count in baseline_expected.values()) or not configured_expected:
            raise InputError("FIXTURE_IDENTITY")
        with tempfile.TemporaryDirectory(prefix="vams-allowlist-regression-") as temp:
            root = Path(temp)
            tree = root / "tree"
            tree.mkdir(mode=0o700)
            for name, lines in fixtures.files.items():
                destination = tree / name
                destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
            original_hashes = tree_hashes(tree, fixtures)
            for label, content, expected in (
                ("baseline", baseline, baseline_expected),
                ("configured", configured, configured_expected),
            ):
                config = root / (label + ".toml")
                report = root / (label + ".json")
                config.write_bytes(content)
                if tree_hashes(tree, fixtures) != original_hashes:
                    raise InputError("FIXTURE_DRIFT")
                if hashlib.sha256(binary.read_bytes()).hexdigest() != PINNED_GITLEAKS_SHA256:
                    raise InputError("SCANNER_DRIFT")
                scan(binary, tree, config, report)
                observed = read_findings(report, set(fixtures.files))
                report.unlink()
                if tree_hashes(tree, fixtures) != original_hashes:
                    raise InputError("FIXTURE_DRIFT")
                if observed != expected:
                    raise OracleError("BASELINE_MISMATCH" if label == "baseline"
                                      else "CONFIGURED_MISMATCH")
        print("allowlist_regression=pass paired_rule_candidate_path_oracles=matched")
        return 0
    except OracleError as exc:
        print("allowlist_regression=fail reason=" + str(exc), file=sys.stderr)
        return 1
    except InputError as exc:
        print("allowlist_regression=unqualified reason=" + str(exc), file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print("allowlist_regression=unqualified reason=SCANNER_TIMEOUT", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("allowlist_regression=unqualified reason=INTERRUPTED", file=sys.stderr)
        return 130
    except (OSError, UnicodeError, ValueError):
        print("allowlist_regression=unqualified reason=INPUT_OR_REPORT_ERROR", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
