"""Proposed public-CLI mutation harness for the F05.1-R4 fixture suite.

This is a scratch proposal only; it is not part of the repository checkout.
Copy/adapt into docs/remediation/m3_f05_design_r2/test_design.py after the
normative v4 VECTORS.json is frozen.
"""

from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

try:
    from .independent_oracle import action_id, authority_state_bytes, certificate_bytes, sync_bytes
except ImportError:
    from independent_oracle import action_id, authority_state_bytes, certificate_bytes, sync_bytes


# Literal test-side inventory; do not derive it from production validator output.
REQUIRED_MUTATION_IDS = frozenset(
    {
        "frozen_contract_certificate_field_order",
        "frozen_contract_certificate_domain_terminator",
        "frozen_contract_source_scale",
        "frozen_contract_decimal_precision",
        "certificate_threshold_below_quorum",
        "emergency_threshold_below_quorum",
        "boolean_action_code",
        "wrapped_credit_payload_schema",
        "wrapped_release_payload_schema",
        "slash_agent_payload_schema",
        "execute_intent_payload_schema",
        "wrong_source_chain_domain",
        "proof_payload_substitution",
        "source_action_cap_exceeded",
        "dust_amount",
        "wrapped_int64_overflow",
        "counter_u64_overflow",
        "counter_underflow",
        "cumulative_supply_overflow",
        "authority_epoch_overlap",
        "authority_epoch_non_plus_one",
        "replay_resurrection",
        "reserve_lovelace_substitution",
        "reserve_u64_overflow",
        "cross_action_rebinding",
        "unknown_vector_key",
        "duplicate_json_key",
        "wrong_receipt_effect_commitment_field_name",
        "wrong_derived_credit_wrapped_amount",
        "sync_prior_epoch",
        "sync_prior_state_hash",
        "sync_prior_key_set",
        "sync_post_keys_authorize_rotation",
        "sync_epoch_not_exact_plus_one",
        "rotation_with_cardano_outbox_pending",
        "rotation_with_polygon_outbox_pending",
        "freeze_allows_new_source",
        "drain_accepts_post_cutoff_event",
        "missing_cardano_ready_receipt",
        "missing_polygon_drained_receipt",
        "cardano_activation_before_delay",
        "polygon_install_before_rotation_ready",
        "pause_clears_barrier",
        "pause_allows_economic_effect",
        "pause_ack_after_destination_cutoff",
        "resume_changes_barrier_id",
        "resume_reopens_new_source",
        "resume_mutates_pending_record",
        "resume_changes_action_certificate",
        "repeated_pause_rewinds_cutoff",
        "rotation_interleaves_before_polygon_install",
        "activation_delay_not_exact_48_hours",
        "rotation_authorization_before_drained",
        "expired_freeze_certificate",
        "future_freeze_certificate",
        "expired_cardano_ready_receipt",
        "future_cardano_ready_receipt",
        "expired_polygon_drained_receipt",
        "future_polygon_drained_receipt",
        "expired_rotation_ready_receipt",
        "future_rotation_ready_receipt",
        "pause_between_prepare_and_freeze",
        "stale_freeze_cert_after_pause",
        "reauthorization_changes_barrier_target",
        "reauthorization_changes_cardano_snapshot",
        "repeat_freeze_rewinds_polygon_cutoff",
        "economic_action_before_bilateral_freeze",
        "target_epoch_not_current_plus_one",
        "missing_rotation_authorized_state",
        "substituted_rotation_authorized_state",
        "backdated_rotation_authorization",
        "freeze_target_epoch_hash_mismatch",
    }
)


def _load_json_strict(path: Path) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise AssertionError("duplicate JSON key in mutation fixture")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)


def _pointer_parent(document: Any, pointer: str) -> tuple[Any, str]:
    # Frozen mutation paths are the human-readable dotted contract form, e.g.
    # action_vectors[0].certificate.threshold (not JSON-Pointer syntax).
    parts = []
    for match in re.finditer(r"[^.\[\]]+|\[(\d+)\]", pointer):
        token = match.group(0)
        parts.append(int(token[1:-1]) if token.startswith("[") else token)
    canonical = "" if not parts else str(parts[0])
    for part in parts[1:]:
        canonical += f"[{part}]" if isinstance(part, int) else f".{part}"
    if not parts or canonical != pointer:
        raise AssertionError("mutation path is malformed")
    if not parts or any(part == "" for part in parts):
        raise AssertionError("empty JSON-pointer component")
    current = document
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current, parts[-1]


def _read_pointer(document: Any, pointer: str) -> Any:
    parent, leaf = _pointer_parent(document, pointer)
    return parent[int(leaf)] if isinstance(parent, list) else parent[leaf]


def _same_json_value(left: Any, right: Any) -> bool:
    # JSON booleans must not compare equal to integer test controls.
    return type(left) is type(right) and left == right


def _apply_json_mutation(document: Any, case: dict[str, Any]) -> Any:
    parent, leaf = _pointer_parent(document, case["path"])
    is_list = isinstance(parent, list)
    key: Any = int(leaf) if is_list else leaf
    operation = case["operation"]
    if operation == "add":
        if is_list:
            parent.insert(key, case["new_value"])
        else:
            if key in parent:
                raise AssertionError("add mutation target already exists")
            parent[key] = case["new_value"]
    elif operation == "remove":
        actual = parent[key]
        if "old_value" in case and not _same_json_value(actual, case["old_value"]):
            raise AssertionError("remove old_value does not match frozen fixture")
        if is_list:
            del parent[key]
        else:
            del parent[key]
    elif operation in {"replace", "set"}:
        actual = parent[key]
        if "old_value" in case and not _same_json_value(actual, case["old_value"]):
            raise AssertionError("mutation old_value does not match frozen fixture")
        parent[key] = case["new_value"]
    elif operation == "rename":
        if is_list or key not in parent or not isinstance(case.get("new_value"), str):
            raise AssertionError("rename mutation requires an existing object key and string destination")
        if case.get("old_value") is not None and not _same_json_value(parent[key], case["old_value"]):
            raise AssertionError("rename old_value does not match frozen fixture")
        new_key = case["new_value"]
        if new_key in parent:
            raise AssertionError("rename destination key already exists")
        parent[new_key] = parent.pop(key)
    elif operation == "reorder":
        actual = parent[key]
        if not isinstance(actual, list) or not isinstance(case["new_value"], list):
            raise AssertionError("reorder mutation requires list old/new values")
        if not _same_json_value(actual, case["old_value"]):
            raise AssertionError("reorder old_value does not match frozen fixture")
        parent[key] = case["new_value"]
    elif operation == "duplicate_key_raw":
        raise AssertionError("duplicate_key_raw must be applied to the original JSON text")
    else:
        raise AssertionError(f"unsupported mutation operation: {operation}")
    return document


_SYNTHETIC_TEST_SEEDS = {
    "6e7a1cdd29b0b78fd13af4c5598feff4ef2a97166e3ca6f2e4fbfccd80505bf1": 5,
    "8139770ea87d175f56a35466c34c7ecccb8d8a91b4ee37a25df60f5b8fc9b394": 2,
    "8a88e3dd7409f195fd52db2d3cba5d72ca6709bf1d94121bf3748801b40f6f5c": 1,
    "ca93ac1705187071d67b83c7ff0efe8108e8ec4530575d7726879333dbdabe7c": 4,
    "ed4928c628d1c2c6eae90338905995612959273a5c63f93636c14614ac8737d1": 3,
}


def _resign_freeze_for_target_hash(
    vectors: dict[str, Any], contract: dict[str, Any], barrier_index: int, target_hash: str
) -> None:
    """Re-encode and re-sign a freeze cert with a valid but semantically wrong target hash."""
    case = vectors["rotation_barrier_cases"][barrier_index]
    cert = case["polygon_freeze"]["freeze_certificate"]
    cert["message_fields"]["target_authority_state_hash_hex"] = target_hash
    spec = contract["rotation_barrier"]
    _resign_certificate(cert, spec["freeze_message_fields"], spec["freeze_domain_hex"])


def _resign_certificate(certificate: dict[str, Any], rows: list[list[Any]], domain_hex: str) -> None:
    message = certificate_bytes(certificate["message_fields"], rows, domain_hex)
    keys = certificate["committee_public_keys_hex"]
    seeds = [_SYNTHETIC_TEST_SEEDS[key] for key in keys[:3]]
    certificate["signatures_hex"] = _synthetic_signatures(message, seeds)
    certificate["message_bytes_hex"] = message.hex()
    certificate["message_sha256"] = __import__("hashlib").sha256(message).hexdigest()


def _resign_sync_certificate(certificate: dict[str, Any], contract: dict[str, Any]) -> None:
    message = sync_bytes(certificate["message_fields"], contract)
    keys = certificate["committee_public_keys_hex"]
    seeds = [_SYNTHETIC_TEST_SEEDS[key] for key in keys[:3]]
    _set_synthetic_signatures(certificate, message, seeds)


def _set_synthetic_signatures(certificate: dict[str, Any], message: bytes, seeds: list[int]) -> None:
    certificate["signatures_hex"] = _synthetic_signatures(message, seeds)
    certificate["message_bytes_hex"] = message.hex()
    certificate["message_sha256"] = __import__("hashlib").sha256(message).hexdigest()


def _synthetic_signatures(message: bytes, seeds: list[int]) -> list[str]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    return [Ed25519PrivateKey.from_private_bytes(bytes([seed]) * 32).sign(message).hex()
            for seed in seeds]


def _resign_semantic_mutation(vectors: dict[str, Any], contract: dict[str, Any], category: str) -> None:
    if category.startswith("sync_") or category.startswith("authority_epoch_"):
        _resign_sync_certificate(vectors["rotation_cases"][0]["sync_certificate"], contract)
    elif category in {"wrong_source_chain_domain", "proof_payload_substitution"}:
        record = vectors["action_vectors"][0]
        cert = record["certificate"]
        if category == "wrong_source_chain_domain":
            identity = record["identity_fields"]
            identity["source_chain_id"] = cert["message_fields"]["source_chain_id"]
            rebound_action_id = action_id(identity, record["payload_sha256"],
                                          contract["action_id_serialization"]["domain_hex"]).hex()
            record["action_id_hex"] = rebound_action_id
            cert["message_fields"]["action_id_hex"] = rebound_action_id
        _resign_certificate(cert, contract["certificate"]["message_fields"],
                            contract["certificate"]["message_domain_hex"])
    elif category == "rotation_authorization_before_drained":
        cert = vectors["rotation_barrier_cases"][0]["cardano_authorization"]["authorization_certificate"]
        spec = contract["rotation_barrier"]
        _resign_certificate(cert, spec["rotation_authorization_message_fields"],
                            spec["rotation_authorization_domain_hex"])
    elif category == "resume_changes_action_certificate":
        cert = vectors["rotation_barrier_cases"][1]["drain_steps"][0]["resumed_action_certificate"]
        spec = contract["rotation_barrier"]
        _resign_certificate(cert, spec["resumed_action_message_fields"],
                            spec["resumed_action_domain_hex"])


def _semantic_mutation_certificate(vectors: dict[str, Any], category: str) -> dict[str, Any]:
    if category.startswith("sync_") or category.startswith("authority_epoch_"):
        return vectors["rotation_cases"][0]["sync_certificate"]
    if category in {"wrong_source_chain_domain", "proof_payload_substitution"}:
        return vectors["action_vectors"][0]["certificate"]
    if category == "rotation_authorization_before_drained":
        return vectors["rotation_barrier_cases"][0]["cardano_authorization"]["authorization_certificate"]
    if category == "resume_changes_action_certificate":
        return vectors["rotation_barrier_cases"][1]["drain_steps"][0]["resumed_action_certificate"]
    raise AssertionError(f"no signed certificate for {category}")


def _resign_case2_freeze_for_target_epoch(vectors: dict[str, Any], contract: dict[str, Any], epoch: int) -> None:
    """Keep a target-epoch mutation cryptographically valid with synthetic keys."""
    case = vectors["rotation_barrier_cases"][2]
    target_state = json.loads(json.dumps(case["cardano_activation"]["next_authority_state"]))
    target_state["epoch"] = epoch
    target_hash = __import__("hashlib").sha256(authority_state_bytes(target_state, contract)).hexdigest()
    _resign_freeze_for_target_hash(vectors, contract, 2, target_hash)


def _verify_synthetic_certificate_signatures(certificate: dict[str, Any]) -> list[bool]:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    message = bytes.fromhex(certificate["message_bytes_hex"])
    verified: list[bool] = []
    for public_hex, signature_hex in zip(
        certificate["committee_public_keys_hex"][:3], certificate["signatures_hex"]
    ):
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex)).verify(
                bytes.fromhex(signature_hex), message
            )
            verified.append(True)
        except InvalidSignature:
            verified.append(False)
    return verified


def _assert_mutation_inventory(vectors: dict[str, Any]) -> None:
    cases = vectors["mutation_cases"]
    ids = [case["id"] for case in cases]
    categories = [case["category"] for case in cases]
    if len(ids) != len(set(ids)):
        raise AssertionError("mutation IDs are not unique")
    if len(categories) != len(set(categories)) or set(categories) != REQUIRED_MUTATION_IDS:
        raise AssertionError("mutation registry omits or adds a required category")
    if set(ids) != REQUIRED_MUTATION_IDS:
        raise AssertionError("mutation IDs omit or add a required category")


def _invoke_public_validator(validator: Path, artifact_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(validator), "--dir", str(artifact_dir)],
        cwd=artifact_dir,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


class PublicMutationHarnessTests(unittest.TestCase):
    here = Path(__file__).resolve().parent
    validator = Path(os.environ.get("F05_R4_VALIDATOR", here / "validate_design.py"))

    def test_mutation_inventory_has_one_case_per_required_category(self) -> None:
        vectors = _load_json_strict(self.here / "VECTORS.json")
        _assert_mutation_inventory(vectors)

    def test_frozen_72_category_inventory_is_literal_and_removal_sensitive(self) -> None:
        # This list is a test-side contract, not loaded from the validator.
        cases = [{"id": category, "category": category} for category in sorted(REQUIRED_MUTATION_IDS)]
        _assert_mutation_inventory({"mutation_cases": cases})
        for removed in sorted(REQUIRED_MUTATION_IDS):
            mutated = [case for case in cases if case["id"] != removed]
            with self.subTest(removed=removed):
                with self.assertRaisesRegex(AssertionError, "mutation registry"):
                    _assert_mutation_inventory({"mutation_cases": mutated})

    def test_contract_dotted_path_parser_selects_nested_object_and_array_fields(self) -> None:
        document = {"action_vectors": [{"payload": {"value": 1}}],
                    "rotation_barrier_cases": [{"phase": "OLD"}]}
        parent, leaf = _pointer_parent(document, "action_vectors[0].payload.value")
        self.assertEqual((parent, leaf), ({"value": 1}, "value"))
        parent[leaf] = 2
        self.assertEqual(document["action_vectors"][0]["payload"]["value"], 2)
        self.assertRaises(AssertionError, _pointer_parent, document, "action_vectors..payload")
        self.assertFalse(_same_json_value(True, 1))
        self.assertFalse(_same_json_value(False, 0))

    def test_rename_mutation_replaces_exact_receipt_field_name(self) -> None:
        document = {"message_fields": {"destination_effect_commitment_hex": "ab" * 32}}
        result = _apply_json_mutation(document, {
            "path": "message_fields.destination_effect_commitment_hex",
            "operation": "rename",
            "old_value": "ab" * 32,
            "new_value": "destination_effect_commitment",
        })
        self.assertEqual(result, {"message_fields": {"destination_effect_commitment": "ab" * 32}})

    def test_stale_freeze_mutation_replaces_actual_certificate_from_prepare(self) -> None:
        # The stale-cert mutation must substitute the signed old certificate, not
        # merely toggle stale_freeze_rejected metadata.
        old_certificate = {"version": 4, "message_bytes_hex": "0102",
                          "message_sha256": "old", "signatures_hex": ["aa", "bb", "cc"]}
        fresh_certificate = {"version": 4, "message_bytes_hex": "0304",
                             "message_sha256": "fresh", "signatures_hex": ["dd", "ee", "ff"]}
        document = {
            "rotation_barrier_cases": [{}, {}, {
                "cardano_prepare": {"freeze_certificate": old_certificate},
                "polygon_freeze": {"freeze_certificate": fresh_certificate},
            }]
        }
        result = _apply_json_mutation(document, {
            "path": "rotation_barrier_cases[2].polygon_freeze.freeze_certificate",
            "operation": "replace",
            "old_value": fresh_certificate,
            "new_value": old_certificate,
        })
        self.assertEqual(
            result["rotation_barrier_cases"][2]["polygon_freeze"]["freeze_certificate"],
            old_certificate,
        )

    def test_reauthorization_wrong_target_is_resigned_and_rejected_semantically(self) -> None:
        vectors_path = self.here / "VECTORS.json"
        contract_path = self.here / "CONTRACT.json"
        source = _load_json_strict(vectors_path)
        case = next(x for x in source["mutation_cases"]
                    if x["category"] == "reauthorization_changes_barrier_target")
        with tempfile.TemporaryDirectory(prefix="f05-r4-resigned-target-") as name:
            work = Path(name)
            shutil.copyfile(contract_path, work / "CONTRACT.json")
            shutil.copyfile(vectors_path, work / "VECTORS.json")
            control = _invoke_public_validator(self.validator, work)
            self.assertEqual(control.returncode, 0, control.stdout[:500])
            self.assertEqual(json.loads(control.stdout)["result"], "PASS")
            mutated = _load_json_strict(work / "VECTORS.json")
            _apply_json_mutation(mutated, case)
            contract = _load_json_strict(work / "CONTRACT.json")
            _resign_case2_freeze_for_target_epoch(mutated, contract, 4)
            certificate = mutated["rotation_barrier_cases"][2]["polygon_freeze"]["freeze_certificate"]
            self.assertEqual(certificate["message_fields"]["target_epoch"], 4)
            state = json.loads(json.dumps(mutated["rotation_barrier_cases"][2]["cardano_activation"]["next_authority_state"]))
            state["epoch"] = 4
            expected_state_hash = hashlib.sha256(authority_state_bytes(state, contract)).hexdigest()
            self.assertEqual(certificate["message_fields"]["target_authority_state_hash_hex"], expected_state_hash)
            expected_message = certificate_bytes(certificate["message_fields"],
                contract["rotation_barrier"]["freeze_message_fields"],
                contract["rotation_barrier"]["freeze_domain_hex"])
            self.assertEqual(certificate["message_bytes_hex"], expected_message.hex())
            self.assertEqual(certificate["message_sha256"], hashlib.sha256(expected_message).hexdigest())
            (work / "VECTORS.json").write_text(
                json.dumps(mutated, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            result = _invoke_public_validator(self.validator, work)
            response = json.loads(result.stdout)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.stdout, "validator returned no sanitized response")
            self.assertEqual(result.stderr, "", "validator emitted unexpected stderr")
            self.assertEqual(response.get("result"), "FAIL")
            self.assertEqual(response.get("reason"), case["expected_error"])
            self.assertNotIn("signature", response.get("reason", "").lower())
        self.assertFalse(work.exists(), "resigned target mutation temporary copy was not cleaned")

    def test_freeze_target_hash_mismatch_is_resigned_and_rejected_semantically(self) -> None:
        vectors_path = self.here / "VECTORS.json"
        contract_path = self.here / "CONTRACT.json"
        source = _load_json_strict(vectors_path)
        mutation = next(x for x in source["mutation_cases"]
                        if x["category"] == "freeze_target_epoch_hash_mismatch")
        with tempfile.TemporaryDirectory(prefix="f05-r4-resigned-freeze-hash-") as name:
            work = Path(name)
            shutil.copyfile(contract_path, work / "CONTRACT.json")
            shutil.copyfile(vectors_path, work / "VECTORS.json")
            control = _invoke_public_validator(self.validator, work)
            self.assertEqual(control.returncode, 0, control.stdout[:500])
            self.assertTrue(control.stdout, "validator returned no sanitized response")
            self.assertEqual(control.stderr, "", "validator emitted unexpected stderr")
            self.assertEqual(json.loads(control.stdout)["result"], "PASS")

            mutated = _load_json_strict(work / "VECTORS.json")
            _apply_json_mutation(mutated, mutation)
            contract = _load_json_strict(work / "CONTRACT.json")
            target_state = json.loads(json.dumps(
                mutated["rotation_barrier_cases"][1]["cardano_activation"]["next_authority_state"]
            ))
            target_state["epoch"] = 2
            alternate_hash = hashlib.sha256(authority_state_bytes(target_state, contract)).hexdigest()
            self.assertEqual(alternate_hash, mutation["new_value"])
            _resign_freeze_for_target_hash(mutated, contract, 1, alternate_hash)

            certificate = mutated["rotation_barrier_cases"][1]["polygon_freeze"]["freeze_certificate"]
            self.assertEqual(certificate["message_fields"]["target_epoch"], 1)
            self.assertEqual(certificate["message_fields"]["target_authority_state_hash_hex"], alternate_hash)
            expected_message = certificate_bytes(
                certificate["message_fields"],
                contract["rotation_barrier"]["freeze_message_fields"],
                contract["rotation_barrier"]["freeze_domain_hex"],
            )
            self.assertEqual(certificate["message_bytes_hex"], expected_message.hex())
            self.assertEqual(certificate["message_sha256"], hashlib.sha256(expected_message).hexdigest())
            self.assertEqual(_verify_synthetic_certificate_signatures(certificate), [True, True, True])
            (work / "VECTORS.json").write_text(
                json.dumps(mutated, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            result = _invoke_public_validator(self.validator, work)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.stdout, "validator returned no sanitized response")
            self.assertEqual(result.stderr, "", "validator emitted unexpected stderr")
            response = json.loads(result.stdout)
            self.assertEqual(response.get("result"), "FAIL")
            self.assertEqual(response.get("reason"), mutation["expected_error"])
            self.assertNotIn("signature", response.get("reason", "").lower())
        self.assertFalse(work.exists(), "resigned freeze-hash mutation temporary copy was not cleaned")

    def test_remaining_signed_semantic_mutations_reencode_and_reject(self) -> None:
        vectors_path = self.here / "VECTORS.json"
        contract_path = self.here / "CONTRACT.json"
        source = _load_json_strict(vectors_path)
        categories = {
            "sync_prior_epoch", "sync_prior_state_hash", "sync_epoch_not_exact_plus_one",
            "authority_epoch_non_plus_one", "authority_epoch_overlap",
            "rotation_authorization_before_drained", "resume_changes_action_certificate",
            "wrong_source_chain_domain", "proof_payload_substitution",
        }
        cases = [case for case in source["mutation_cases"] if case["category"] in categories]
        self.assertEqual({case["category"] for case in cases}, categories)
        control_seen = False
        with tempfile.TemporaryDirectory(prefix="f05-r4-signed-semantics-control-") as name:
            control_work = Path(name)
            shutil.copyfile(contract_path, control_work / "CONTRACT.json")
            shutil.copyfile(vectors_path, control_work / "VECTORS.json")
            control = _invoke_public_validator(self.validator, control_work)
            control_seen = True
            self.assertEqual(control.returncode, 0, control.stdout[:500])
            self.assertTrue(control.stdout, "validator returned no sanitized response")
            self.assertEqual(control.stderr, "", "validator emitted unexpected stderr")
            self.assertEqual(json.loads(control.stdout)["result"], "PASS")
        self.assertTrue(control_seen)
        self.assertFalse(control_work.exists(), "signed semantic baseline temporary copy was not cleaned")

        contract = _load_json_strict(contract_path)
        for case in cases:
            with self.subTest(category=case["category"]):
                with tempfile.TemporaryDirectory(prefix="f05-r4-signed-semantic-") as name:
                    work = Path(name)
                    shutil.copyfile(contract_path, work / "CONTRACT.json")
                    shutil.copyfile(vectors_path, work / "VECTORS.json")
                    mutated = _load_json_strict(work / "VECTORS.json")
                    _apply_json_mutation(mutated, case)
                    _resign_semantic_mutation(mutated, contract, case["category"])
                    cert = _semantic_mutation_certificate(mutated, case["category"])
                    if case["category"] == "wrong_source_chain_domain":
                        record = mutated["action_vectors"][0]
                        self.assertEqual(record["identity_fields"]["source_chain_id"],
                                         cert["message_fields"]["source_chain_id"])
                        independently_rebound_id = action_id(
                            record["identity_fields"], record["payload_sha256"],
                            contract["action_id_serialization"]["domain_hex"]
                        ).hex()
                        self.assertEqual(record["action_id_hex"], independently_rebound_id)
                        self.assertEqual(cert["message_fields"]["action_id_hex"], independently_rebound_id)
                    if case["category"].startswith("sync_") or case["category"].startswith("authority_epoch_"):
                        expected_message = sync_bytes(cert["message_fields"], contract)
                    elif case["category"] in {"wrong_source_chain_domain", "proof_payload_substitution"}:
                        expected_message = certificate_bytes(cert["message_fields"],
                            contract["certificate"]["message_fields"],
                            contract["certificate"]["message_domain_hex"])
                    else:
                        spec = contract["rotation_barrier"]
                        if case["category"] == "rotation_authorization_before_drained":
                            rows, domain = spec["rotation_authorization_message_fields"], spec["rotation_authorization_domain_hex"]
                        else:
                            rows, domain = spec["resumed_action_message_fields"], spec["resumed_action_domain_hex"]
                        expected_message = certificate_bytes(cert["message_fields"], rows, domain)
                    self.assertEqual(cert["message_bytes_hex"], expected_message.hex())
                    self.assertEqual(cert["message_sha256"], hashlib.sha256(expected_message).hexdigest())
                    self.assertEqual(_verify_synthetic_certificate_signatures(cert), [True, True, True])
                    (work / "VECTORS.json").write_text(
                        json.dumps(mutated, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
                    result = _invoke_public_validator(self.validator, work)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertTrue(result.stdout, "validator returned no sanitized response")
                    self.assertEqual(result.stderr, "", "validator emitted unexpected stderr")
                    response = json.loads(result.stdout)
                    self.assertEqual(response.get("result"), "FAIL")
                    self.assertEqual(response.get("reason"), case["expected_error"])
                self.assertFalse(work.exists(), f"{case['category']} temporary copy was not cleaned")

    def test_inventory_rejects_duplicate_or_unknown_id_and_category(self) -> None:
        cases = [{"id": category, "category": category} for category in sorted(REQUIRED_MUTATION_IDS)]
        duplicate_id = [*cases, {"id": cases[0]["id"], "category": "extra-category"}]
        duplicate_category = [*cases, {"id": "extra-id", "category": cases[0]["category"]}]
        unknown = [*cases, {"id": "extra-category", "category": "extra-category"}]
        for mutated in (duplicate_id, duplicate_category, unknown):
            with self.assertRaises(AssertionError):
                _assert_mutation_inventory({"mutation_cases": mutated})

    def test_every_registered_mutation_is_rejected_by_public_cli(self) -> None:
        vectors_path = self.here / "VECTORS.json"
        contract_path = self.here / "CONTRACT.json"
        vectors = _load_json_strict(vectors_path)
        _assert_mutation_inventory(vectors)

        # The immutable clean baseline has already been proven once; do not pay
        # its full signature-validation cost before every independent mutation.
        control_calls = 0
        with tempfile.TemporaryDirectory(prefix="f05-r4-control-") as name:
            control_work = Path(name)
            shutil.copyfile(contract_path, control_work / "CONTRACT.json")
            shutil.copyfile(vectors_path, control_work / "VECTORS.json")
            control = _invoke_public_validator(self.validator, control_work)
            control_calls += 1
            self.assertEqual(control.returncode, 0, control.stdout[:500])
            self.assertEqual(json.loads(control.stdout)["result"], "PASS")
        self.assertFalse(control_work.exists(), "baseline control temporary copy was not cleaned")

        mutation_calls = 0
        for case in vectors["mutation_cases"]:
            with self.subTest(mutation_id=case["id"]):
                with tempfile.TemporaryDirectory(prefix="f05-r4-mutation-") as name:
                    work = Path(name)
                    shutil.copyfile(contract_path, work / "CONTRACT.json")
                    shutil.copyfile(vectors_path, work / "VECTORS.json")

                    artifact_name = case["artifact"]
                    artifact_path = work / artifact_name
                    if case["operation"] == "duplicate_key_raw":
                        raw = artifact_path.read_text(encoding="utf-8")
                        duplicate = case["new_value"]
                        self.assertIsInstance(duplicate, dict)
                        key = duplicate["key"]
                        old_token = json.dumps(case["old_value"], separators=(",", ":"))
                        new_token = json.dumps(duplicate["value"], separators=(",", ":"))
                        needle = re.compile(
                            r'(' + re.escape(json.dumps(key)) + r'\s*:\s*)' + re.escape(old_token)
                        )
                        raw, count = needle.subn(
                            lambda match: match.group(1) + old_token + ", "
                            + match.group(1) + new_token,
                            raw,
                            count=1,
                        )
                        self.assertEqual(count, 1, "duplicate-key target was not found exactly once")
                        artifact_path.write_text(raw, encoding="utf-8")
                    else:
                        artifact = _load_json_strict(artifact_path)
                        mutated = _apply_json_mutation(artifact, case)
                        if case["category"] == "reauthorization_changes_barrier_target":
                            contract = _load_json_strict(work / "CONTRACT.json")
                            _resign_case2_freeze_for_target_epoch(mutated, contract, case["new_value"])
                        elif case["category"] == "freeze_target_epoch_hash_mismatch":
                            contract = _load_json_strict(work / "CONTRACT.json")
                            target_state = json.loads(json.dumps(
                                mutated["rotation_barrier_cases"][1]["cardano_activation"]["next_authority_state"]
                            ))
                            target_state["epoch"] = 2
                            alternate_hash = hashlib.sha256(authority_state_bytes(target_state, contract)).hexdigest()
                            self.assertEqual(alternate_hash, case["new_value"])
                            _resign_freeze_for_target_hash(mutated, contract, 1, alternate_hash)
                        elif case["category"] in {
                            "sync_prior_epoch", "sync_prior_state_hash", "sync_epoch_not_exact_plus_one",
                            "authority_epoch_non_plus_one", "authority_epoch_overlap",
                            "rotation_authorization_before_drained", "resume_changes_action_certificate",
                            "wrong_source_chain_domain", "proof_payload_substitution",
                        }:
                            contract = _load_json_strict(work / "CONTRACT.json")
                            _resign_semantic_mutation(mutated, contract, case["category"])
                        artifact_path.write_text(
                            json.dumps(mutated, sort_keys=True, separators=(",", ":")) + "\n",
                            encoding="utf-8",
                        )

                    result = _invoke_public_validator(self.validator, work)
                    mutation_calls += 1
                    self.assertNotEqual(result.returncode, 0, case["id"])
                    self.assertTrue(result.stdout, "validator returned no sanitized response")
                    self.assertEqual(result.stderr, "", "validator emitted unexpected stderr")
                    response = json.loads(result.stdout)
                    self.assertEqual(response.get("result"), "FAIL")
                    self.assertLessEqual(len(result.stdout), 4096)
                    self.assertNotIn("Traceback", result.stdout)
                    self.assertNotIn(str(work), result.stdout)
                    if case["expected_error"]:
                        self.assertIn(case["expected_error"], response.get("reason", ""))

                self.assertFalse(work.exists(), "temporary mutation copy was not cleaned")
        self.assertEqual(control_calls, 1, "the suite must run exactly one clean baseline control")
        self.assertEqual(mutation_calls, 72, "the suite must invoke exactly 72 public mutations")

    def test_mutation_removal_meta_check_fails_closed(self) -> None:
        vectors = _load_json_strict(self.here / "VECTORS.json")
        cases = vectors["mutation_cases"]
        for removed in cases:
            with self.subTest(removed=removed["id"]):
                mutated = json.loads(json.dumps(vectors))
                mutated["mutation_cases"] = [case for case in mutated["mutation_cases"] if case["id"] != removed["id"]]
                with self.assertRaisesRegex(AssertionError, "mutation registry"):
                    _assert_mutation_inventory(mutated)


if __name__ == "__main__":
    unittest.main()
