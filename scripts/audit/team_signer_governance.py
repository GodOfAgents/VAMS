#!/usr/bin/env python3
"""Fail-closed checks for team-controlled bootstrap signer evidence.

Owner decision 12 (docs/remediation/OWNER_DECISIONS_20261108.md) fixes the
restricted-testnet signer layout: four routine seats, two offline recovery
seats in 2-of-3 split custody, and the authorities in ``AUTHORITIES``.

``validate_document`` checks a filled ``team-signer-governance.json`` against
that layout (stdlib only; the JSON Schema in
``docs/audit/schemas/team-signer-governance.schema.json`` describes the same
shape for other tools). ``source_errors`` checks that the thresholds the
layout assumes are the ones the deploy script and Cardano validator enforce.

Usage:
  python scripts/audit/team_signer_governance.py            # source check only
  python scripts/audit/team_signer_governance.py FILE.json  # plus evidence check
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "2.0.0"
GOVERNANCE_MODE = "team-controlled-bootstrap"

ROUTINE = ("ARCHITECT", "SIGNER_A", "SIGNER_B", "SIGNER_C")
RECOVERY = ("GOVERNANCE_RECOVERY", "TREASURY_RECOVERY")
CUSTODIANS = ("SIGNER_A", "SIGNER_B", "SIGNER_C")

# id -> (threshold, members, scope, identity kind)
AUTHORITIES = {
    "amoy-governance": (3, {*ROUTINE, "GOVERNANCE_RECOVERY"}, "governance", "evm"),
    "amoy-treasury": (3, {*ROUTINE, "TREASURY_RECOVERY"}, "faucet-only-treasury", "evm"),
    "amoy-emergency": (2, {"ARCHITECT", "SIGNER_A", "SIGNER_B"}, "pause-only", "evm"),
    "cardano-governance": (3, {*ROUTINE, "GOVERNANCE_RECOVERY"}, "governance", "cardano"),
}

SCENARIOS = (
    "amoy-governance-3-of-5",
    "amoy-treasury-3-of-5",
    "amoy-emergency-2-of-3",
    "cardano-governance-3-of-5",
    "unavailable-signer",
    "rejected-transaction",
    "lost-key-replacement",
    "recovery-split-custody",
    "human-readable-transaction-review",
)

CONSENT_FLAGS = (
    "consented",
    "understands_authority",
    "independent_key_custody_confirmed",
    "emergency_channel_recorded",
    "compromise_reporting_accepted",
    "amoy_rehearsal_completed",
)

EVM = re.compile(r"^0x[0-9a-fA-F]{40}$")
CARDANO_HASH = re.compile(r"^[0-9a-f]{56}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
ZERO_EVM = "0x" + "0" * 40


def _safe_path(value: object) -> bool:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value:
        return False
    return ".." not in value.split("/")


def _exact_keys(obj: object, keys: set[str], where: str, errors: list[str]) -> bool:
    if not isinstance(obj, dict):
        errors.append(f"{where} must be an object")
        return False
    missing, extra = keys - obj.keys(), obj.keys() - keys
    if missing:
        errors.append(f"{where} missing {sorted(missing)}")
    if extra:
        errors.append(f"{where} has unexpected {sorted(extra)}")
    return not missing


def _evidence(obj: dict, where: str, errors: list[str]) -> None:
    if not _safe_path(obj.get("evidence_path")):
        errors.append(f"{where} evidence_path must be a relative path inside the bundle")
    if not isinstance(obj.get("evidence_sha256"), str) or not SHA256.match(obj["evidence_sha256"]):
        errors.append(f"{where} evidence_sha256 must be 64 lowercase hex")


def _seat_keys(seat: dict, where: str, errors: list[str]) -> None:
    address = seat.get("evm_address")
    if not isinstance(address, str) or not EVM.match(address) or address.lower() == ZERO_EVM:
        errors.append(f"{where} evm_address must be a non-zero 0x address")
    key_hash = seat.get("cardano_key_hash")
    if not isinstance(key_hash, str) or not CARDANO_HASH.match(key_hash):
        errors.append(f"{where} cardano_key_hash must be 56 lowercase hex")
    if seat.get("historical_pem_relationship") is not False:
        errors.append(f"{where} must have no relationship to the historical PEM identities")


def validate_document(doc: object) -> list[str]:
    errors: list[str] = []
    top = {
        "schema_version", "commit_sha", "governance_mode", "decentralized_governance_claimed",
        "independent_review_claimed", "externally_audited_claimed", "signers",
        "offline_recovery_seats", "authorities", "consent_records", "rehearsals",
        "emergency_response_target_seconds", "limitations", "blocking_findings_open",
    }
    if not _exact_keys(doc, top, "document", errors):
        return errors
    assert isinstance(doc, dict)
    if doc["schema_version"] != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not isinstance(doc["commit_sha"], str) or not COMMIT.match(doc["commit_sha"]):
        errors.append("commit_sha must be a 40-hex commit")
    if doc["governance_mode"] != GOVERNANCE_MODE:
        errors.append(f"governance_mode must be {GOVERNANCE_MODE}")
    for claim in ("decentralized_governance_claimed", "independent_review_claimed",
                  "externally_audited_claimed"):
        if doc[claim] is not False:
            errors.append(f"{claim} must be false for a team-controlled bootstrap")

    seats: list[dict] = []
    signers = doc["signers"]
    if not isinstance(signers, list) or sorted(s.get("role") for s in signers if isinstance(s, dict)) != sorted(ROUTINE) or len(signers) != 4:
        errors.append(f"signers must be exactly {list(ROUTINE)}")
    else:
        for seat in signers:
            where = f"signer {seat.get('role')}"
            if _exact_keys(seat, {"role", "evm_address", "cardano_key_hash",
                                  "historical_pem_relationship", "independent_key_custody"}, where, errors):
                _seat_keys(seat, where, errors)
                if seat["independent_key_custody"] is not True:
                    errors.append(f"{where} must hold its own key independently")
                seats.append(seat)

    recovery = doc["offline_recovery_seats"]
    if not isinstance(recovery, list) or sorted(s.get("role") for s in recovery if isinstance(s, dict)) != sorted(RECOVERY) or len(recovery) != 2:
        errors.append(f"offline_recovery_seats must be exactly {list(RECOVERY)}")
    else:
        for seat in recovery:
            where = f"recovery seat {seat.get('role')}"
            if _exact_keys(seat, {"role", "evm_address", "cardano_key_hash", "historical_pem_relationship",
                                  "custody_mode", "custodians", "custody_threshold", "routine_use",
                                  "rotate_after_use"}, where, errors):
                _seat_keys(seat, where, errors)
                if seat["custody_mode"] != "2-of-3-split-custody":
                    errors.append(f"{where} custody_mode must be 2-of-3-split-custody")
                if not isinstance(seat["custodians"], list) or sorted(seat["custodians"]) != sorted(CUSTODIANS):
                    errors.append(f"{where} custodians must be exactly {list(CUSTODIANS)}")
                if seat["custody_threshold"] != 2:
                    errors.append(f"{where} custody_threshold must be 2")
                if seat["routine_use"] is not False:
                    errors.append(f"{where} must never be used for routine approvals")
                if seat["rotate_after_use"] is not True:
                    errors.append(f"{where} must be rotated after any use")
                seats.append(seat)

    if len(seats) == 6:
        if len({s["evm_address"].lower() for s in seats}) != 6:
            errors.append("all six seats need distinct EVM addresses")
        if len({s["cardano_key_hash"] for s in seats}) != 6:
            errors.append("all six seats need distinct Cardano key hashes")

    authorities = doc["authorities"]
    if not isinstance(authorities, list) or sorted(a.get("id") for a in authorities if isinstance(a, dict)) != sorted(AUTHORITIES) or len(authorities) != len(AUTHORITIES):
        errors.append(f"authorities must be exactly {sorted(AUTHORITIES)}")
    else:
        identities = []
        for authority in authorities:
            where = f"authority {authority['id']}"
            if not _exact_keys(authority, {"id", "threshold", "members", "scope", "identity"}, where, errors):
                continue
            threshold, members, scope, kind = AUTHORITIES[authority["id"]]
            if authority["threshold"] != threshold:
                errors.append(f"{where} threshold must be {threshold}")
            got = authority["members"]
            if not isinstance(got, list) or len(got) != len(set(got)) or set(got) != members:
                errors.append(f"{where} members must be exactly {sorted(members)}")
            if authority["scope"] != scope:
                errors.append(f"{where} scope must be {scope}")
            identity = authority["identity"]
            pattern = EVM if kind == "evm" else CARDANO_HASH
            if not isinstance(identity, str) or not pattern.match(identity) or identity.lower() == ZERO_EVM:
                errors.append(f"{where} identity must be a real {'Safe address' if kind == 'evm' else 'script hash'}")
            else:
                identities.append(identity.lower())
        if len(identities) != len(set(identities)):
            errors.append("authority identities must be distinct")

    consents = doc["consent_records"]
    if not isinstance(consents, list) or sorted(c.get("role") for c in consents if isinstance(c, dict)) != sorted(ROUTINE) or len(consents) != 4:
        errors.append(f"consent_records must cover exactly {list(ROUTINE)}")
    else:
        for record in consents:
            where = f"consent {record['role']}"
            if _exact_keys(record, {"role", *CONSENT_FLAGS, "evidence_path", "evidence_sha256"}, where, errors):
                for flag in CONSENT_FLAGS:
                    if record[flag] is not True:
                        errors.append(f"{where} {flag} must be true")
                _evidence(record, where, errors)

    rehearsals = doc["rehearsals"]
    if not isinstance(rehearsals, list) or sorted(r.get("scenario") for r in rehearsals if isinstance(r, dict)) != sorted(SCENARIOS) or len(rehearsals) != len(SCENARIOS):
        errors.append(f"rehearsals must cover exactly {list(SCENARIOS)}")
    else:
        for record in rehearsals:
            where = f"rehearsal {record['scenario']}"
            if _exact_keys(record, {"scenario", "passed", "evidence_path", "evidence_sha256"}, where, errors):
                if record["passed"] is not True:
                    errors.append(f"{where} must have passed")
                _evidence(record, where, errors)

    target = doc["emergency_response_target_seconds"]
    if isinstance(target, bool) or not isinstance(target, int) or target < 1:
        errors.append("emergency_response_target_seconds must be a positive integer")
    limitations = doc["limitations"]
    if not isinstance(limitations, list) or not limitations or not all(isinstance(x, str) and x.strip() for x in limitations):
        errors.append("limitations must list at least one non-empty statement")
    elif not any("overlap" in x.lower() for x in limitations):
        errors.append("limitations must disclose the signer overlap")
    if doc["blocking_findings_open"] != 0:
        errors.append("blocking_findings_open must be 0")
    return errors


def source_errors(root: Path = ROOT) -> list[str]:
    """The layout's thresholds must equal what the source enforces."""
    errors: list[str] = []
    deploy = (root / "contracts/script/DeployTestnet.s.sol").read_text(encoding="utf-8")
    for authority, owners, threshold in (("governanceAuthority", 5, 3), ("treasuryAuthority", 5, 3),
                                         ("emergencyAuthority", 3, 2)):
        if not re.search(rf"_requireSafe\(\s*{authority}\s*,\s*{owners}\s*,\s*{threshold}\s*,", deploy):
            errors.append(f"DeployTestnet no longer requires {authority} {threshold}-of-{owners}")
    for name, (threshold, members, _, kind) in AUTHORITIES.items():
        if kind == "evm":
            expected = {"amoy-governance": (5, 3), "amoy-treasury": (5, 3), "amoy-emergency": (3, 2)}[name]
            if (len(members), threshold) != expected:
                errors.append(f"{name} layout {threshold}-of-{len(members)} differs from DeployTestnet")
    governance = (root / "cardano/lib/vams/governance_v2.ak").read_text(encoding="utf-8")
    if "list.length(c.members) == 5" not in governance or "c.threshold == 3" not in governance:
        errors.append("governance_v2 no longer fixes five members with threshold 3")
    threshold, members, _, _ = AUTHORITIES["cardano-governance"]
    if (len(members), threshold) != (5, 3):
        errors.append("cardano-governance layout differs from governance_v2")
    return errors


def main(argv: list[str]) -> int:
    errors = source_errors()
    for path in argv:
        errors += [f"{path}: {e}" for e in validate_document(json.loads(Path(path).read_text(encoding="utf-8")))]
    if errors:
        print("Team signer governance check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Team signer governance check passed" + (f" for {len(argv)} document(s)." if argv else " (source only)."))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
