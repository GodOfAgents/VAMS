#!/usr/bin/env python3
"""Fail-closed validator for the frozen F05.1-R4 design contract.

This file validates documentation artifacts only; it does not verify a live
bridge, certificate, ledger proof, committee key, or deployed chain state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


class DesignError(ValueError):
    """Controlled rejection of a design artifact that is not the frozen form."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DesignError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise DesignError("non-standard JSON numeric constant")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_reject_constant)
    except DesignError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DesignError(f"invalid design JSON: {path.name}") from exc


def exact_keys(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise DesignError(f"{label} has missing, extra, or non-object fields")


def _type_matches(value: Any, expected: type) -> bool:
    if expected is int:
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, expected)


def _schema(value: Any, schema: Any, label: str) -> None:
    if isinstance(schema, dict):
        exact_keys(value, set(schema), label)
        for key, child_schema in schema.items():
            _schema(value[key], child_schema, f"{label}.{key}")
    elif isinstance(schema, list):
        if not isinstance(value, list):
            raise DesignError(f"{label} is not an array")
        if len(schema) == 1:
            for index, (item, child_schema) in enumerate(zip(value, schema)):
                # A one-item schema denotes a homogeneous array. Fixed tuples
                # use two or more explicit entries (e.g. [field, byte_width]).
                _schema(item, schema[0], f"{label}[{index}]")
        elif schema:
            if len(value) != len(schema):
                raise DesignError(f"{label} has wrong tuple length")
            for index, (item, child_schema) in enumerate(zip(value, schema)):
                _schema(item, child_schema, f"{label}[{index}]")
    elif not _type_matches(value, schema):
        raise DesignError(f"{label} has wrong scalar type")


# Every key and container shape is frozen here; the contract's own schema
# declarations are checked against this trusted validator definition.
CONTRACT_SCHEMA: dict[str, Any] = {
    "schema_version": int, "specification_id": str, "status": str,
    "protocol_domain": str, "source_commit": str,
    "domain_bytes": {"certificate": {"label": str, "domain_hex": str},
                     "action_id": {"label": str, "domain_hex": str},
                     "authority_state": {"label": str, "domain_hex": str},
                     "replay_state": {"label": str, "domain_hex": str},
                     "authority_sync": {"label": str, "domain_hex": str},
                     "destination_effect": {"label": str, "domain_hex": str},
                     "executor_call": {"label": str, "domain_hex": str},
                     "payloads": [{"action": str, "domain_hex": str}],
                     "encoding_rule": str},
    "networks": {"polygon_amoy": {"chain_code": int, "chain_id": int, "network_magic": int, "address_network_id": int},
                 "cardano_preprod": {"chain_code": int, "chain_id": int, "network_magic": int, "address_network_id": int}},
    "asset": {"source_symbol": str, "source_decimals": int, "source_max_supply_base": int,
              "wrapped_symbol": str, "wrapped_decimals": int, "source_units_per_wrapped_unit": int,
              "wrapped_asset_name_hex": str, "wrapped_asset_name_bytes": int, "wrapped_policy_id": str,
              "max_wrapped_supply": int, "cardano_multiasset_max_quantity": int,
              "cardano_mint_burn_max_abs_quantity": int, "max_action_source_base": int,
              "counter_max": int, "counter_width_bits": int, "counter_fields": [str],
              "counter_equations": [str], "checked_arithmetic": bool,
              "insurance_lovelace_conversion": str, "insurance_fund_deposit": str,
              "source_balance_width_bits": int, "source_balance_cap": int,
              "pending_amount_width_bits": int, "pending_amount_cap": int,
              "pending_policy": str, "backing_equation": str,
              "settled_conservation_equation": str, "escrow_liability_rule": str,
              "source_flow": str, "reverse_flow": str},
    "authority": {"state_type": str, "state_policy": str, "state_asset_name_ascii": str,
                  "version": int, "initial_epoch": int, "key_algorithm": str, "key_bytes": int,
                  "signature_bytes": int, "ordered_unique_keys": int, "threshold": int,
                  "certificate_signatures_exact": int, "status_values": [str],
                  "pending_transition_values": [str], "rotation_signatures": int,
                  "rotation_epoch_delta": int, "rotation_delay_ms": int, "pause_signatures": int,
                  "pause_effect": str, "unpause_signatures": int, "unpause_delay_ms": int,
                  "unpause_effect": str, "committee_trust": str, "honesty_assumption": str,
                  "actual_testnet_public_keys": str},
    "authority_preimages": {"encoding": str, "bootstrap_domain_hex": str,
        "state_domain_hex": str, "pending_domain_hex": str,
        "rotation_authorization_domain_hex": str, "unpause_authorization_domain_hex": str,
        "pause_authorization_domain_hex": str, "bootstrap_fields": [[str, int]],
        "state_fields": [[str, int]], "pending_fields": [[str, int]],
        "pause_fields": [[str, int]],
        "canonical_fields_bytes": {"bootstrap": int, "state": int, "pending": int, "pause": int},
        "preimage_lengths": {"bootstrap": int, "state": int, "pending": int, "pause": int},
        "key_order_rule": str, "pending_transition_rule": str, "pause_rule": str,
        "pending_hash_rule": str, "none_pending_encoding": str,
        "status_encoding": {"ACTIVE": int, "PAUSED": int},
        "pending_kind_encoding": {"NONE": int, "ROTATE": int, "UNPAUSE": int}},
    "polygon_authority_mirror": {"state_type": str, "state_policy": str, "canonical_source": str,
        "mirror_state_fields": [[str, int]], "state_hash_rule": str, "sync_certificate_domain_hex": str,
        "sync_certificate_version": int, "sync_message_fields": [[str, int]], "sync_message_bytes": int,
        "sync_signatures": {"count": int, "committee_keys": int, "order": str, "algorithm": str, "prehash": bool},
        "initialization_rule": str, "sync_nonce_rule": str, "checkpoint_rule": str, "epoch_rule": str,
        "committee_rule": str, "freshness_max_ms": int, "action_gate": str, "pause_effect": str, "recovery_rule": str},
    "rotation_barrier": {"version": int, "state_type": str, "domain_hex": str,
        "outbox_commitment_domain_hex": str,
        "freeze_domain_hex": str, "cardano_ready_domain_hex": str, "polygon_drained_domain_hex": str,
        "rotation_ready_domain_hex": str, "rotation_authorization_domain_hex": str,
        "rotation_authorized_state_domain_hex": str, "phase_values": [str],
        "fixed_source_streams": [str], "cardano_source_streams": [str], "polygon_source_streams": [str],
        "stream_watermark_fields": [str], "stream_watermark_encoding": str, "cutoff_fields": [str],
        "cardano_state_fields": [str], "polygon_state_fields": [str],
        "freeze_message_fields": [[str, int]], "cardano_ready_message_fields": [[str, int]],
        "polygon_drained_message_fields": [[str, int]], "rotation_ready_message_fields": [[str, int]],
        "rotation_authorization_message_fields": [[str, int]],
        "resumed_action_domain_hex": str, "resumed_action_message_fields": [[str, int]],
        "signature_rule": str, "finality_assumption": str, "outbox_commitment_rule": str, "freeze_rule": str, "drain_rule": str,
        "ready_order_rule": str, "rotation_guard": str, "pause_rule": str, "resume_rule": str,
        "resumed_action_rule": str, "ack_rule": str, "rollback_rule": str, "retry_rule": str,
        "max_streams": int, "rotation_authorized_state_fields": [[str, int]],
        "rotation_required_mutation_categories": [str]},
    "settlement_ack": {"domain_hex": str, "version": int, "message_fields": [[str, int]],
        "message_bytes": int, "signature_count": int, "receipt_finality_rule": str, "source_ack_rule": str,
        "idempotency_rule": str, "failure_rule": str, "pending_open_rule": str,
        "pending_clear_rule": str,
        "atomic_stage_rules": {"source": str, "destination": str, "ack": str, "cross_chain": str},
        "message_expiry_ms": int},
    "destination_effect_commitment": {"fields": [[str, (int, str)]], "hash_rule": str,
        "encoding_rule": str, "version": int},
    "certificate": {"version": int, "message_domain_hex": str, "message_bytes": int,
                    "signature_algorithm": str, "prehash": bool, "integer_encoding": str,
                    "hash_algorithm": str, "issued_at_unit": str, "max_lifetime_ms": int,
                    "cardano_time_rule": str, "evm_time_rule": str, "evm_time_conversion": str,
                    "destination_time_context_rule": str,
                    "message_fields": [[str, int]],
                    "signatures": {"count": int, "order": str, "caller_selected_keys": bool, "entry_encoding": str},
                    "hashes": {"payload": str, "action_id": str, "authority_state": str}},
    "checkpoint_and_replay": {"state_type": str, "state_policy": str,
                              "per_source_domain_cursor": bool, "source_stream_key_fields": [str],
                              "source_endpoint_encoding": str,
                              "source_streams": [{"name": str, "chain": str, "identifier_source": str, "endpoint_bytes": int}],
                              "source_stream_set": str, "source_cursor_fields": [[str, (int, str)]],
                              "shared_chain_checkpoint_state": {"state_type": str, "scope": str, "fields": [[str, int]],
                                  "genesis": {"checkpoint_number": int, "checkpoint_hash_hex": str, "previous_checkpoint_hash_hex": str},
                                  "transition_rule": str, "cross_stream_equivocation_rule": str, "atomicity": str},
                              "destination_replay_tombstone": {"fields": [str], "max_records": int,
                                  "max_records_per_fixed_source_stream": int, "replacement_rule": str},
                              "genesis_cursor": {"source_nonce": int, "checkpoint_number": int,
                                  "checkpoint_hash_hex": str, "previous_checkpoint_hash_hex": str},
                              "first_checkpoint_rule": str,
                              "pending_record_schema": {"fields": [str], "field_encoding": [[str, (int, str)]],
                                  "action_kinds": [str], "statuses": [str], "status_encoding": {"PENDING_CREDIT": int,
                                      "PENDING_RELEASE": int, "PENDING_SLASH": int, "PENDING_EXECUTE_INTENT": int,
                                      "DESTINATION_FINALIZED": int},
                                  "amount_semantics": {"WRAPPED_CREDIT": str, "WRAPPED_RELEASE": str,
                                      "SLASH_AGENT": str, "EXECUTE_INTENT": str}, "backing_status_rule": str,
                                  "max_open_per_source_stream": int, "max_records_per_stream": int,
                                  "open_rule": str, "clear_rule": str, "retry_rule": str},
                              "checkpoint_rule": str,
                              "source_event_rule": str, "source_nonce_rule": str,
                              "action_id_epoch_independent": bool, "cardano_destination_atomicity": str,
                              "evm_destination_atomicity": str, "source_atomicity": str,
                              "cross_chain_atomicity": str, "rollback_rule": str,
                              "retry_rule": str, "no_manual_skip": bool,
                              "event_index": {"polygon": str, "cardano": str}},
    "actions": [{"name": str, "code": int, "source": str, "destination": str,
                 "destination_gate": str, "expected_result": {"accepted": bool, "result_code": str},
                 "payload_domain_hex": str, "payload_fields": [[str, str]], "effect_fields": [[str, str]]}],
    "transaction_topology": {"common": {"authority": str, "replay": str, "reserve": str,
                                          "collateral": str, "rollback": str},
                              "WRAPPED_CREDIT": {"source_polygon": str,
                                  "destination_cardano_regular_inputs": [str],
                                  "destination_cardano_reference_inputs": [str],
                                  "destination_cardano_outputs": [str],
                                  "destination_cardano_mint": str, "ack": str, "effects": str},
                              "WRAPPED_RELEASE": {"source_cardano_regular_inputs": [str],
                                  "source_cardano_reference_inputs": [str], "source_cardano_mint": str,
                                  "source_cardano_outputs": [str], "destination_polygon": str, "ack": str, "effects": str},
                              "SLASH_AGENT": {"source_polygon": str,
                                  "destination_cardano_regular_inputs": [str],
                                  "destination_cardano_reference_inputs": [str],
                                  "destination_cardano_outputs": [str], "destination_cardano_mint": str,
                                  "ack": str, "effects": str},
                              "EXECUTE_INTENT": {"source_cardano_regular_inputs": [str],
                                  "source_cardano_reference_inputs": [str],
                                  "source_cardano_outputs": [str], "destination_polygon": str,
                                  "ack": str, "effects": str}},
    "vector_transactions": {
        action: {stage: {"chain": str, "regular_inputs": [str], "reference_inputs": [str],
            "collateral_inputs": [str], "outputs": [str], "mint": (int, str), "burn": (int, str),
            "reserve_delta": (int, str), "replay_input": str, "replay_output": str}
            for stage in ("source", "destination", "ack")}
        for action in ("WRAPPED_CREDIT", "WRAPPED_RELEASE", "SLASH_AGENT", "EXECUTE_INTENT")
    },
    "slash_reserve": {"state_type": str, "state_policy": str, "state_asset_name_ascii": str,
        "policy_id": str, "insurance_fund_datum_allowed": bool, "minimum_slash_lovelace": int,
        "balance_width_bits": int, "balance_cap": int, "overflow_rule": str, "rotation_rule": str,
        "agent_stake_minimum_lovelace": int, "seed_rule": str, "continuation_rule": str,
        "authorization_rule": str, "identity_rule": str},
    "cardano_transaction_rules": {"script_transaction_collateral_count": int, "collateral_input": str,
        "collateral_required_ada": str, "collateral_success": str, "collateral_phase2_failure": str,
        "cardano_reference_authority_count": int, "state_continuation_count": str, "evm_collateral_count": int,
        "fee_funding_rule": str, "state_ada_rule": str, "funding_failure_rule": str},
    "executor_registry": {"status": str, "registry_type": str, "entry_fields": [str],
        "resolution_rule": str, "calldata_rule": str, "update_rule": str,
        "test_only_mapping": {"classification": str, "destination_chain_code": int,
            "destination_chain_id": int, "destination_network_magic": int, "target_domain_hex": str,
            "executor_target_hex": str, "executor_selector_hex": str, "action_code": int,
            "calldata_schema_id": str},
        "effect_hash_rule": str, "live_activation_gate": str},
    "action_id_serialization": {"domain_hex": str, "hash_algorithm": str,
        "fields": [[str, (int, str)]], "source_endpoint_rule": str,
        "preimage_length_bytes": {"evm_source_endpoint": int, "cardano_source_endpoint": int}},
    "closed_schemas": [{"path": str, "fields": [str]}],
    "vector_schema": {"schema_version": int, "specification_id": str,
                      "root_fields": [str], "action_count": int,
                      "action_required_mutation_categories": [str],
                      "action_vector_fields": [str], "certificate_fields": [str],
                      "certificate_message_fields": [str], "identity_fields": [str],
                      "authority_fields": [str], "transaction_fields": [str],
                      "chain_transaction_fields": [str],
                      "state_fields": [str], "pending_record_fields": [str], "counter_change_fields": [str],
                      "authority_state_fields": [str], "polygon_mirror_fields": [str], "prior_mirror_fields": [str],
        "sync_certificate_fields": [str], "sync_message_fields": [str],
                      "rotation_case_fields": [str], "rotation_expected_fields": [str],
                      "rotation_required_mutation_categories": [str],
                      "rotation_barrier_case_count": int, "rotation_barrier_case_fields": [str], "rotation_barrier_phases": [str],
                      "rotation_barrier_state_fields": [str], "rotation_barrier_stream_fields": [str],
                      "rotation_barrier_expected_fields": [str], "rotation_barrier_required_mutation_categories": [str],
                      "barrier_certificate_fields": [str], "freeze_message_fields": [str],
                      "cardano_ready_message_fields": [str], "polygon_drained_message_fields": [str],
                      "rotation_ready_message_fields": [str], "rotation_authorization_message_fields": [str], "resumed_action_message_fields": [str],
                      "settlement_ack_message_fields": [str],
                      "destination_event_fields": [str],
                      "ack_transaction_fields": [str], "ack_receipt_fields": [str],
                      "action_effect_fields": [str],
                      "global_state_fields": [str], "stream_state_fields": [str],
                      "checkpoint_state_fields": [str], "outbox_state_fields": [str],
                      "destination_replay_fields": [str],
                      "expected_fields": [str], "mutation_fields": [str],
                      "arithmetic_fields": [str], "mutation_operations": [str]},
    "boundaries": {"uint64_max": int, "int64_max": int, "cardano_asset_name_max_bytes": int,
                   "cardano_policy_id_bytes": int, "cardano_tx_validity_interval_max_ms": int,
                   "source_action_nonce_min": int, "source_amount_min": int,
                   "cardano_address_max_bytes": int, "payload_max_bytes": int,
                   "certificate_message_max_bytes": int, "certificate_signature_set_bytes": int,
                   "certificate_envelope_max_bytes": int, "proof_max_bytes": int,
                   "signer_count_min": int, "signer_count_max": int, "unsupported_actions": [str]},
}

EXPECTED_CONTRACT_CANONICAL_SHA256 = "d9ec898f7a2b9b24e8e124ff548d45ba20280658c0660dc0e308537e52d4f8c5"
EXPECTED_ACTIONS = [
    ("WRAPPED_CREDIT", 1, "polygon_amoy", "cardano_preprod", "56414d532d4630352d5041594c4f41442d57432d563300"),
    ("WRAPPED_RELEASE", 2, "cardano_preprod", "polygon_amoy", "56414d532d4630352d5041594c4f41442d57522d563300"),
    ("SLASH_AGENT", 3, "polygon_amoy", "cardano_preprod", "56414d532d4630352d5041594c4f41442d53412d563300"),
    ("EXECUTE_INTENT", 4, "cardano_preprod", "polygon_amoy", "56414d532d4630352d5041594c4f41442d45492d563300"),
]
EXPECTED_ACTION_MUTATION_CATEGORIES = [
    "certificate_threshold_below_quorum", "emergency_threshold_below_quorum",
    "frozen_contract_certificate_field_order", "frozen_contract_certificate_domain_terminator",
    "boolean_action_code",
    "wrapped_credit_payload_schema", "wrapped_release_payload_schema", "slash_agent_payload_schema",
    "execute_intent_payload_schema", "wrong_source_chain_domain", "proof_payload_substitution",
    "frozen_contract_source_scale", "frozen_contract_decimal_precision", "source_action_cap_exceeded", "dust_amount",
    "wrapped_int64_overflow", "counter_u64_overflow", "counter_underflow", "cumulative_supply_overflow",
    "authority_epoch_overlap", "authority_epoch_non_plus_one", "replay_resurrection",
    "reserve_lovelace_substitution", "reserve_u64_overflow", "cross_action_rebinding",
    "unknown_vector_key", "duplicate_json_key", "wrong_receipt_effect_commitment_field_name",
    "wrong_derived_credit_wrapped_amount",
]
CERTIFICATE_FIELDS = [
    ("source_chain_code", 1), ("source_chain_id", 8), ("source_network_magic", 4),
    ("destination_chain_code", 1), ("destination_chain_id", 8), ("destination_network_magic", 4),
    ("destination_address_network_id", 1), ("action_code", 1), ("authority_epoch", 8),
    ("authority_state_hash", 32),
    ("source_action_nonce", 8), ("source_event_block_number", 8), ("source_event_block_hash", 32),
    ("finalized_checkpoint_number", 8), ("finalized_checkpoint_hash", 32),
    ("previous_certified_checkpoint_hash", 32), ("event_transaction_hash", 32), ("event_index", 4),
    ("payload_hash", 32), ("action_id", 32), ("issued_at_ms", 8), ("expires_at_ms", 8),
]
ACTION_ID_FIELDS = [
    ("source_chain_code", 1), ("source_chain_id", 8), ("source_network_magic", 4),
    ("destination_chain_code", 1), ("destination_chain_id", 8), ("destination_network_magic", 4),
    ("source_endpoint_length", 1), ("source_endpoint_bytes", "20_or_28"),
    ("event_transaction_hash", 32), ("event_index", 4), ("action_code", 1),
    ("source_action_nonce", 8), ("payload_hash", 32),
]


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def uint(value: Any, bits: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 1 << bits:
        raise DesignError(f"{label} is outside uint{bits}")
    return value


def _hex(value: Any, byte_length: int, label: str) -> bytes:
    if not isinstance(value, str) or len(value) != byte_length * 2 or not re.fullmatch(r"[0-9a-f]*", value):
        raise DesignError(f"{label} has malformed hex")
    return bytes.fromhex(value)


def _prefix(domain_hex: str, label: str) -> bytes:
    raw = _hex(domain_hex, len(domain_hex) // 2, label)
    if not raw or raw[-1] != 0:
        raise DesignError(f"{label} must include its explicit terminal NUL byte")
    return raw


def validate_contract(contract: dict[str, Any], vectors: dict[str, Any] | None = None) -> dict[str, int]:
    _schema(contract, CONTRACT_SCHEMA, "contract")
    if _canonical_digest(contract) != EXPECTED_CONTRACT_CANONICAL_SHA256:
        raise DesignError("contract differs from the frozen F05.1-R4 values or schema")
    if (contract["schema_version"] != 4 or contract["specification_id"] != "F05.1-R4"
            or contract["status"] != "DESIGN_FREEZE_TESTNET_ONLY"
            or contract["protocol_domain"] != "VAMS-F05-R4-V4"):
        raise DesignError("unsupported contract version or protocol domain")
    if contract["vector_schema"]["schema_version"] != 4 or contract["vector_schema"]["specification_id"] != "F05.1-R4":
        raise DesignError("vector schema version differs from the frozen v4 contract")
    if contract["vector_schema"]["action_required_mutation_categories"] != EXPECTED_ACTION_MUTATION_CATEGORIES:
        raise DesignError("action mutation inventory differs from the frozen acceptance set")
    executor = contract["executor_registry"]
    fixture = executor["test_only_mapping"]
    if (executor["status"] != "UNPOPULATED_DEPLOYMENT_PREREQUISITE; EXECUTE_INTENT_LIVE_USE_DISABLED"
            or executor["registry_type"] != "IMMUTABLE_DEPLOYMENT_BOUND_ALLOWLIST_OR_SEPARATELY_VERSIONED_DELAYED_GOVERNED_REGISTRY"
            or executor["entry_fields"] != ["destination_chain_code","destination_chain_id","destination_network_magic","target_domain_hex","executor_target_hex","executor_selector_hex","action_code","calldata_schema_id"]
            or "NO_WILDCARD" not in executor["resolution_rule"]
            or "NO_CALLER_SELECTED_TARGET_SELECTOR_OR_CALLDATA" not in executor["resolution_rule"]
            or "NO_ADDRESS_INFERENCE_FROM_TARGET_DOMAIN" not in executor["resolution_rule"]
            or "MISSING_OR_DUPLICATE_MATCH_REJECTS" not in executor["resolution_rule"]
            or "CALLER_SUPPLIED_CALLDATA_IS_FORBIDDEN" not in executor["calldata_rule"]
            or "NO_LIVE_EXECUTE_INTENT" not in executor["live_activation_gate"]):
        raise DesignError("executor allowlist, call binding, or live activation gate is not closed")
    if (fixture["classification"] != "SYNTHETIC_TEST_ONLY_NOT_A_DEPLOYMENT_OR_PRODUCTION_ADDRESS"
            or (fixture["destination_chain_code"], fixture["destination_chain_id"], fixture["destination_network_magic"], fixture["action_code"])
               != (1, 80002, 0, 4)
            or fixture["calldata_schema_id"] != "F05_R4_TEST_INTENT_V1"):
        raise DesignError("synthetic executor fixture is not the exact non-production test mapping")
    _hex(fixture["target_domain_hex"], len(fixture["target_domain_hex"]) // 2, "fixture target domain")
    _hex(fixture["executor_target_hex"], 20, "fixture executor target")
    _hex(fixture["executor_selector_hex"], 4, "fixture executor selector")
    if domains_hex := contract["domain_bytes"]["executor_call"]["domain_hex"]:
        if domains_hex != "56414d532d4630352d4558454355544f522d43414c4c2d563300":
            raise DesignError("executor-call hash domain differs from frozen v3 value")
    for item, expected in zip(contract["actions"], EXPECTED_ACTIONS):
        if (item["name"], item["code"], item["source"], item["destination"], item["payload_domain_hex"]) != expected:
            raise DesignError("action enum, routing, or domain differs from the frozen contract")
        uint(item["code"], 8, "action code")
        _prefix(item["payload_domain_hex"], "action payload domain")
    if contract["certificate"]["message_fields"] != [list(row) for row in CERTIFICATE_FIELDS]:
        raise DesignError("certificate ordered field layout differs from frozen contract")
    if sum(width for _, width in CERTIFICATE_FIELDS) + len(_prefix(contract["certificate"]["message_domain_hex"], "certificate domain")) != contract["certificate"]["message_bytes"]:
        raise DesignError("certificate message size equation does not hold")
    cert_signatures = contract["certificate"]["signatures"]
    if (cert_signatures["count"] != 3 or cert_signatures["caller_selected_keys"] is not False
            or cert_signatures["entry_encoding"] != "signer_id_u8||ed25519_signature_64; EXACTLY_THREE_ENTRIES; PUBLIC_KEYS_RESOLVED_FROM_CURRENT_AUTHORITY_STATE_NOT_REPEATED"
            or contract["boundaries"]["certificate_message_max_bytes"] != contract["certificate"]["message_bytes"]
            or contract["boundaries"]["certificate_signature_set_bytes"] != 3 * (1 + 64)
            or contract["boundaries"]["certificate_envelope_max_bytes"] != contract["boundaries"]["certificate_message_max_bytes"] + contract["boundaries"]["certificate_signature_set_bytes"]):
        raise DesignError("certificate message/envelope size boundaries do not match v3 wire encoding")
    domains = contract["domain_bytes"]
    for name in ("action_id", "authority_state", "replay_state", "authority_sync", "destination_effect", "executor_call"):
        _prefix(domains[name]["domain_hex"], f"{name} domain")
    if contract["certificate"]["message_domain_hex"] != domains["certificate"]["domain_hex"]:
        raise DesignError("certificate domain records disagree")
    if contract["authority_preimages"]["state_domain_hex"] != domains["authority_state"]["domain_hex"]:
        raise DesignError("authority state domain records disagree")
    if contract["destination_effect_commitment"]["version"] != 3:
        raise DesignError("destination effect commitment version differs from v3")
    preimages = contract["authority_preimages"]
    preimage_domains = {
        "bootstrap": "bootstrap_domain_hex", "state": "state_domain_hex",
        "pending": "pending_domain_hex", "pause": "pause_authorization_domain_hex",
    }
    for key in ("rotation_authorization_domain_hex", "unpause_authorization_domain_hex"):
        _prefix(preimages[key], f"authority {key} domain")
    preimage_fields = {"bootstrap": "bootstrap_fields", "state": "state_fields",
                       "pending": "pending_fields", "pause": "pause_fields"}
    for label, domain_key in preimage_domains.items():
        prefix = _prefix(preimages[domain_key], f"authority {label} domain")
        fields = preimages[preimage_fields[label]]
        field_bytes = 0
        seen: set[str] = set()
        for field_name, width in fields:
            if not isinstance(field_name, str) or field_name in seen:
                raise DesignError(f"authority {label} field names are not unique")
            seen.add(field_name)
            field_bytes += uint(width, 16, f"authority {label} field width")
        if preimages["canonical_fields_bytes"][label] != field_bytes:
            raise DesignError(f"authority {label} canonical field length mismatch")
        if preimages["preimage_lengths"][label] != len(prefix) + field_bytes:
            raise DesignError(f"authority {label} hash preimage length mismatch")
    if preimages["canonical_fields_bytes"] != {"bootstrap":239,"state":239,"pending":194,"pause":48}:
        raise DesignError("authority canonical field widths differ from frozen v3 layouts")
    if preimages["status_encoding"] != {"ACTIVE":1,"PAUSED":2} or preimages["pending_kind_encoding"] != {"NONE":0,"ROTATE":1,"UNPAUSE":2}:
        raise DesignError("authority enum encoding differs from frozen v3 layout")
    if preimages["none_pending_encoding"] != "kind=0; from_epoch=to_epoch=authorized_at_ms=activation_at_ms=0; next_key_count=0; ordered_next_keys=160_zero_bytes; pending_hash=32_zero_bytes":
        raise DesignError("canonical no-pending authority encoding differs")
    mirror = contract["polygon_authority_mirror"]
    if (mirror["sync_certificate_version"] != 3 or mirror["freshness_max_ms"] != 300000
            or mirror["sync_message_bytes"] != 389
            or sum(width for _, width in mirror["sync_message_fields"])
               + len(_prefix(mirror["sync_certificate_domain_hex"], "authority sync domain")) != 389
            or mirror["sync_certificate_domain_hex"] != domains["authority_sync"]["domain_hex"]
            or "DEPLOYMENT_INITIALIZED_FROM_THE_PINNED_CARDANO_GENESIS_AUTHORITY_STATE" not in mirror["initialization_rule"]
            or "NO_FIRST_SYNC_SELF_AUTHENTICATION" not in mirror["initialization_rule"]
            or "CURRENT_PRE_UPDATE_POLYGON_MIRROR_KEY_SET_K_E" not in mirror["committee_rule"]
            or "POST_STATE_K_E_PLUS_1" not in mirror["committee_rule"]):
        raise DesignError("Polygon authority-sync version, domain, length, or freshness differs")
    barrier = contract["rotation_barrier"]
    expected_barrier_categories = [
        "rotation_with_cardano_outbox_pending", "rotation_with_polygon_outbox_pending",
        "freeze_allows_new_source", "drain_accepts_post_cutoff_event",
        "missing_cardano_ready_receipt", "missing_polygon_drained_receipt",
        "cardano_activation_before_delay", "polygon_install_before_rotation_ready",
        "pause_clears_barrier", "pause_allows_economic_effect",
        "pause_ack_after_destination_cutoff", "resume_changes_barrier_id",
        "resume_reopens_new_source", "resume_mutates_pending_record",
        "resume_changes_action_certificate", "repeated_pause_rewinds_cutoff",
        "rotation_interleaves_before_polygon_install", "activation_delay_not_exact_48_hours",
        "rotation_authorization_before_drained", "expired_freeze_certificate", "future_freeze_certificate",
        "expired_cardano_ready_receipt", "future_cardano_ready_receipt", "expired_polygon_drained_receipt",
        "future_polygon_drained_receipt", "expired_rotation_ready_receipt", "future_rotation_ready_receipt",
        "pause_between_prepare_and_freeze", "stale_freeze_cert_after_pause",
        "reauthorization_changes_barrier_target", "reauthorization_changes_cardano_snapshot",
        "repeat_freeze_rewinds_polygon_cutoff", "economic_action_before_bilateral_freeze",
        "target_epoch_not_current_plus_one", "missing_rotation_authorized_state",
        "substituted_rotation_authorized_state", "backdated_rotation_authorization",
        "freeze_target_epoch_hash_mismatch",
    ]
    if (barrier["version"] != 4 or barrier["state_type"] != "RotationBarrierV4"
            or contract["vector_schema"]["rotation_barrier_case_count"] != 3
            or contract["vector_schema"]["rotation_barrier_case_fields"] != [
                "case_id", "barrier_id_hex", "cardano_prepare", "polygon_freeze", "drain_steps", "cardano_ready",
                "polygon_drained", "cardano_authorization", "cardano_activation", "polygon_install", "pause_resume", "pre_freeze_pause_resume", "expected"]
            or barrier["domain_hex"] != "56414d532d4630352d524f544154494f4e2d424152524945522d563400"
            or barrier["outbox_commitment_domain_hex"] != "56414d532d4630352d524f544154494f4e2d4f5554424f582d563400"
            or barrier["freeze_domain_hex"] != "56414d532d4630352d524f544154494f4e2d465245455a452d563400"
            or barrier["cardano_ready_domain_hex"] != "56414d532d4630352d524f544154494f4e2d43415244414e4f2d52454144592d563400"
            or barrier["polygon_drained_domain_hex"] != "56414d532d4630352d524f544154494f4e2d504f4c59474f4e2d445241494e45442d563400"
            or barrier["rotation_ready_domain_hex"] != "56414d532d4630352d524f544154494f4e2d524f544154494f4e2d52454144592d563400"
            or barrier["rotation_authorization_domain_hex"] != "56414d532d4630352d524f544154494f4e2d415554484f52495a4154494f4e2d563400"
            or barrier["resumed_action_domain_hex"] != "56414d532d4630352d524553554d45442d414354494f4e2d563400"
            or barrier["max_streams"] != 4
            or barrier["fixed_source_streams"] != [item["name"] for item in contract["checkpoint_and_replay"]["source_streams"]]
            or barrier["cardano_source_streams"] != [item["name"] for item in contract["checkpoint_and_replay"]["source_streams"] if item["chain"] == "cardano_preprod"]
            or barrier["polygon_source_streams"] != [item["name"] for item in contract["checkpoint_and_replay"]["source_streams"] if item["chain"] == "polygon_amoy"]
            or set(barrier["cardano_source_streams"]).intersection(barrier["polygon_source_streams"])
            or set(barrier["cardano_source_streams"] + barrier["polygon_source_streams"]) != set(barrier["fixed_source_streams"])
            or barrier["rotation_required_mutation_categories"] != expected_barrier_categories
            or contract["vector_schema"]["rotation_barrier_required_mutation_categories"] != expected_barrier_categories):
        raise DesignError("rotation barrier v4 domains, bounded streams, or required mutation inventory differ")
    if ("CENTRALIZED_TESTNET_FINALITY_TRUST" not in barrier["finality_assumption"]
            or "NO_ACTION_CAN_INTERLEAVE" not in barrier["ready_order_rule"]
            or "ONLY_NON_ECONOMIC_ACK" not in barrier["pause_rule"]
            or "IMMUTABLE" not in barrier["resumed_action_rule"]
            or "NO_CROSS_CHAIN_ROLLBACK" not in barrier["rollback_rule"]
            or "INITIAL_TARGET_EPOCH_AND_TARGET_STATE_HASH_ARE_BOUND_TO_THE_SAME_INITIAL_TARGET_STATE" not in barrier["freeze_rule"]
            or "REAUTHORIZED_TARGET_EPOCH_IS_CURRENT_AUTHORITY_EPOCH_PLUS_ONE" not in barrier["freeze_rule"]
            or "TARGET_EPOCH_CURRENT_AUTHORITY_EPOCH_PLUS_ONE" not in barrier["resume_rule"]
            or "AUTHORIZED_AT_MS_EQUALS_AUTHORIZATION_TX_CARDANO_VALIDITY_UPPER_BOUND" not in barrier["rotation_guard"]
            or "ACTIVATION_CONSUMES_THAT_EXACT_FINALIZED_SINGLETON" not in barrier["rotation_guard"]
            or "WITHOUT_A_NEW_AUTHORIZATION_CERTIFICATE" not in barrier["rotation_guard"]
            or "THE_LATER_CARDANO_ACTIVATION_TRANSACTION_HAS_ITS_OWN_VALIDITY_INTERVAL" not in barrier["rotation_guard"]
            or "LOWER_BOUND_AT_OR_AFTER_ACTIVATION_AT_MS" not in barrier["rotation_guard"]):
        raise DesignError("rotation barrier omits required finality, pause, immutability, or rollback rule")
    for label in ("domain_hex", "outbox_commitment_domain_hex", "freeze_domain_hex", "cardano_ready_domain_hex",
                  "polygon_drained_domain_hex", "rotation_ready_domain_hex", "rotation_authorization_domain_hex", "resumed_action_domain_hex"):
        _prefix(barrier[label], f"rotation barrier {label}")
    for key in ("freeze_message_fields", "cardano_ready_message_fields", "polygon_drained_message_fields", "rotation_ready_message_fields", "rotation_authorization_message_fields", "resumed_action_message_fields"):
        fields = barrier[key]
        if not fields or len({row[0] for row in fields}) != len(fields):
            raise DesignError(f"rotation barrier {key} must be a nonempty unique ordered schema")
        for field_name, width in fields:
            uint(width, 16, f"rotation barrier {key} field width")
            if not field_name or width < 1:
                raise DesignError(f"rotation barrier {key} contains an invalid field")
    auth_state_rows = barrier["rotation_authorized_state_fields"]
    if (barrier["rotation_authorized_state_domain_hex"] != "56414d532d4630352d524f544154494f4e2d415554484f52495a45442d53544154452d563400"
            or [name for name, _ in auth_state_rows] != ["version", "barrier_id", "authority_epoch", "authority_state_hash",
                "target_epoch", "target_authority_state_hash", "target_ordered_keys_hash", "polygon_drained_receipt_hash",
                "authorization_certificate_hash", "authorized_at_ms", "authorization_tx_hash", "authorization_event_index",
                "finalized_checkpoint_number", "finalized_checkpoint_hash", "previous_checkpoint_hash"]
            or sum(width for _, width in auth_state_rows) != 326):
        raise DesignError("ROTATION_AUTHORIZED singleton domain or fixed-width field order differs")
    ack = contract["settlement_ack"]
    if (ack["version"] != 3 or ack["message_bytes"] != 351 or ack["message_expiry_ms"] != 300000
            or sum(width for _, width in ack["message_fields"])
               + len(_prefix(ack["domain_hex"], "settlement ACK domain")) != 351
            or ack["signature_count"] != 3):
        raise DesignError("settlement receipt version, domain, size, expiry, or threshold differs")
    if ack["atomic_stage_rules"]["cross_chain"].find("NO_CROSS_CHAIN_ATOMICITY_CLAIM") != 0:
        raise DesignError("cross-chain rollback semantics are not explicitly fail-closed")
    if ("ONLY_AFTER_DESTINATION_EFFECT_TRANSACTION_IS_INCLUDED_IN_A_FINALIZED_DESTINATION_CHECKPOINT" not in ack["receipt_finality_rule"]
            or "NEVER_CREATED_OR_COMMITTED_BY_THE_DESTINATION_EFFECT_TRANSACTION" not in ack["receipt_finality_rule"]
            or "DO_NOT_CREATE_OR_COMMIT_ITS_FINALITY_RECEIPT" not in ack["atomic_stage_rules"]["destination"]
            or "ADVANCES_SOURCE_LEDGER_REMOTE_DESTINATION_CHECKPOINT" not in ack["atomic_stage_rules"]["ack"]):
        raise DesignError("finality receipt must be issued after destination transaction finality and consumed by a later source ACK")
    if contract["certificate"]["cardano_time_rule"] != "issued_at_ms<=validity_lower_posix_ms<validity_upper_posix_ms<expires_at_ms" or contract["certificate"]["evm_time_rule"] != "issued_at_ms<=block_timestamp_seconds*1000<expires_at_ms":
        raise DesignError("destination time-bound contract differs from frozen strict inequalities")
    if contract["action_id_serialization"]["fields"] != [list(row) for row in ACTION_ID_FIELDS]:
        raise DesignError("action-ID endpoint length/type binding layout differs")
    if contract["action_id_serialization"]["domain_hex"] != domains["action_id"]["domain_hex"]:
        raise DesignError("action-ID domain records disagree")
    if contract["action_id_serialization"]["preimage_length_bytes"] != {"evm_source_endpoint":21,"cardano_source_endpoint":29}:
        raise DesignError("action-ID endpoint preimage lengths differ")
    streams = contract["checkpoint_and_replay"]["source_streams"]
    expected_streams = [("wrapped_escrow","polygon_amoy",20),("wrapped_burn_policy","cardano_preprod",28),
                        ("polygon_slash_event","polygon_amoy",20),("cardano_timelock_intent","cardano_preprod",28)]
    if [(s["name"],s["chain"],s["endpoint_bytes"]) for s in streams] != expected_streams:
        raise DesignError("source cursor stream set differs from the four deployment-bound endpoints")
    replay = contract["checkpoint_and_replay"]
    if (replay["genesis_cursor"]["source_nonce"] != 0 or replay["genesis_cursor"]["checkpoint_number"] != 0
            or set(replay["genesis_cursor"]["checkpoint_hash_hex"]) != {"0"}
            or set(replay["genesis_cursor"]["previous_checkpoint_hash_hex"]) != {"0"}
            or replay["pending_record_schema"]["max_open_per_source_stream"] != 1
            or replay["pending_record_schema"]["max_records_per_stream"] != 1):
        raise DesignError("source genesis, bounded pending lifecycle, or replay scope differs")
    checkpoint = replay["shared_chain_checkpoint_state"]
    if (checkpoint["fields"] != [["chain_code",1],["chain_id",8],["network_magic",4],
                                   ["checkpoint_number",8],["checkpoint_hash",32],["previous_checkpoint_hash",32]]
            or "PER_RECEIVING_LEDGER" not in checkpoint["scope"]
            or "NO_LEDGER_STORES_A_FINALITY_CURSOR_FOR_ITS_OWN_UNINCLUDED_BLOCK" not in checkpoint["scope"]
            or replay["destination_replay_tombstone"]["max_records"] != 4
            or replay["destination_replay_tombstone"]["max_records_per_fixed_source_stream"] != 1):
        raise DesignError("shared chain checkpoint or bounded destination tombstone differs")
    for action_name in ("WRAPPED_CREDIT", "WRAPPED_RELEASE", "SLASH_AGENT", "EXECUTE_INTENT"):
        tx = contract["vector_transactions"][action_name]
        source_roles = (tx["source"]["regular_inputs"] + tx["source"]["reference_inputs"]
                       + tx["source"]["collateral_inputs"] + tx["source"]["outputs"])
        destination_roles = (tx["destination"]["regular_inputs"] + tx["destination"]["reference_inputs"]
                             + tx["destination"]["collateral_inputs"] + tx["destination"]["outputs"])
        ack_roles = (tx["ack"]["regular_inputs"] + tx["ack"]["reference_inputs"]
                     + tx["ack"]["collateral_inputs"] + tx["ack"]["outputs"])
        if any("chain_checkpoint" in role for role in source_roles):
            raise DesignError(f"{action_name} source action transaction may not write a finality cursor")
        if ("source_chain_checkpoint_singleton" not in tx["destination"]["regular_inputs"]
                or "source_chain_checkpoint_continuation" not in tx["destination"]["outputs"]
                or any("destination_chain_checkpoint" in role for role in destination_roles)):
            raise DesignError(f"{action_name} destination must update only its remote-source cursor")
        if ("destination_chain_checkpoint_singleton" not in tx["ack"]["regular_inputs"]
                or "destination_chain_checkpoint_continuation" not in tx["ack"]["outputs"]
                or any("source_chain_checkpoint" in role for role in ack_roles)):
            raise DesignError(f"{action_name} source ACK must update only its remote-destination cursor")
    if replay["pending_record_schema"]["status_encoding"] != {
        "PENDING_CREDIT":1,"PENDING_RELEASE":2,"PENDING_SLASH":3,
        "PENDING_EXECUTE_INTENT":4,"DESTINATION_FINALIZED":5}:
        raise DesignError("pending lifecycle status encoding differs")
    asset = contract["asset"]
    if (asset["source_balance_width_bits"] != 128 or asset["pending_amount_width_bits"] != 128
            or asset["source_balance_cap"] != asset["source_max_supply_base"]
            or asset["pending_amount_cap"] != asset["source_max_supply_base"]):
        raise DesignError("source or pending balance representation is not bounded by u128 and supply")
    if contract["slash_reserve"]["minimum_slash_lovelace"] != 1 or contract["slash_reserve"]["agent_stake_minimum_lovelace"] != 1_000_000_000 or contract["slash_reserve"]["insurance_fund_datum_allowed"] is not False:
        raise DesignError("slash reserve minimums or insurance separation differ")
    if contract["slash_reserve"]["balance_width_bits"] != 64 or contract["slash_reserve"]["balance_cap"] != (1 << 64) - 1:
        raise DesignError("slash reserve is not checked u64")
    if contract["cardano_transaction_rules"]["script_transaction_collateral_count"] != 1 or contract["cardano_transaction_rules"]["evm_collateral_count"] != 0:
        raise DesignError("Cardano/EVM collateral cardinality differs")
    if contract["asset"]["source_units_per_wrapped_unit"] != 10 ** (contract["asset"]["source_decimals"] - contract["asset"]["wrapped_decimals"]):
        raise DesignError("asset scale equation does not hold")
    asset = contract["asset"]
    if asset["max_wrapped_supply"] != asset["source_max_supply_base"] // asset["source_units_per_wrapped_unit"]:
        raise DesignError("wrapped supply equation does not hold")
    if asset["max_wrapped_supply"] > asset["counter_max"] or asset["counter_max"] >= 1 << asset["counter_width_bits"]:
        raise DesignError("cumulative counter cap is not representable")
    if asset["max_action_source_base"] != asset["cardano_mint_burn_max_abs_quantity"] * asset["source_units_per_wrapped_unit"]:
        raise DesignError("per-action signed-int64 source bound is inconsistent")
    if asset["cardano_mint_burn_max_abs_quantity"] != (1 << 63) - 1:
        raise DesignError("per-action quantity must be signed-int64 bounded")
    if len(contract["actions"]) != 4 or len({item["code"] for item in contract["actions"]}) != 4:
        raise DesignError("action enum is not a four-member unique set")
    if vectors is not None:
        validate_vectors(vectors, contract)
    return {"actions": len(contract["actions"]), "certificate_fields": len(CERTIFICATE_FIELDS)}


def convert_source_amount(amount: Any, contract: dict[str, Any]) -> int:
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
        raise DesignError("source amount is not a nonnegative integer")
    asset = contract["asset"]
    if amount > asset["source_max_supply_base"]:
        raise DesignError("SOURCE_CAP_EXCEEDED")
    scale = asset["source_units_per_wrapped_unit"]
    if amount % scale:
        raise DesignError("NOT_EXACTLY_DIVISIBLE")
    wrapped = amount // scale
    if wrapped > asset["cardano_multiasset_max_quantity"]:
        raise DesignError("MULTIASSET_UINT64_CAP")
    if wrapped > asset["cardano_mint_burn_max_abs_quantity"]:
        raise DesignError("MINT_BURN_INT64_CAP")
    return wrapped


def action_quantity_allowed(wrapped: Any, contract: dict[str, Any]) -> bool:
    if isinstance(wrapped, bool) or not isinstance(wrapped, int):
        return False
    cap = contract["asset"]["cardano_mint_burn_max_abs_quantity"]
    return 0 < wrapped <= cap


def counter_transition(minted: Any, burned: Any, delta: Any, direction: str,
                       contract: dict[str, Any]) -> tuple[int, int, int]:
    asset = contract["asset"]
    maximum = asset["counter_max"]
    for value, label in ((minted, "minted"), (burned, "burned"), (delta, "quantity")):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise DesignError(f"{label} must be a nonnegative integer")
    if minted > maximum or burned > maximum or burned > minted or direction not in {"mint", "burn"}:
        raise DesignError("invalid cumulative counter state")
    next_minted = minted + delta if direction == "mint" else minted
    next_burned = burned + delta if direction == "burn" else burned
    if next_minted > maximum or next_burned > maximum or next_burned > next_minted:
        raise DesignError("cumulative counter overflow or underflow")
    outstanding = next_minted - next_burned
    if outstanding < 0 or outstanding > maximum:
        raise DesignError("outstanding counter outside bound")
    return next_minted, next_burned, outstanding


def _u(value: Any, size: int, label: str) -> bytes:
    uint(value, size * 8, label)
    return value.to_bytes(size, "big")


def credit_payload(source_escrow: bytes, nonce: Any, amount: Any, address: bytes,
                   domain_hex: str = "56414d532d4630352d5041594c4f41442d57432d563300") -> bytes:
    if len(source_escrow) != 20 or not 1 <= len(address) <= 128:
        raise DesignError("WRAPPED_CREDIT field length invalid")
    uint(nonce, 64, "source action nonce")
    uint(amount, 128, "source amount")
    if nonce == 0 or amount == 0:
        raise DesignError("WRAPPED_CREDIT quantity and nonce must be positive")
    return (_prefix(domain_hex, "WRAPPED_CREDIT domain") + source_escrow + _u(nonce, 8, "nonce")
            + _u(amount, 16, "amount") + _u(len(address), 2, "address length") + address)


def payload_hash(payload: bytes) -> bytes:
    return hashlib.sha256(payload).digest()


def action_id(fields: dict[str, Any], payload_digest: bytes,
              domain_hex: str = "56414d532d4630352d414354494f4e2d563300") -> bytes:
    if len(payload_digest) != 32:
        raise DesignError("payload hash must be 32 bytes")
    source_code = uint(fields["source_chain_code"], 8, "source chain code")
    destination_code = uint(fields["destination_chain_code"], 8, "destination chain code")
    code = uint(fields["action_code"], 8, "action code")
    endpoint_size = {1: 20, 2: 28}.get(source_code)
    if endpoint_size is None:
        raise DesignError("unsupported source chain code")
    endpoint = _hex(fields["source_endpoint_hex"], endpoint_size, "source endpoint")
    event_hash = _hex(fields["event_transaction_hash_hex"], 32, "event transaction hash")
    return hashlib.sha256(
        _prefix(domain_hex, "action-id domain") + bytes([source_code])
        + _u(fields["source_chain_id"], 8, "source chain id")
        + _u(fields["source_network_magic"], 4, "source network magic")
        + bytes([destination_code]) + _u(fields["destination_chain_id"], 8, "destination chain id")
        + _u(fields["destination_network_magic"], 4, "destination network magic")
        + bytes([len(endpoint)]) + endpoint + event_hash + _u(fields["event_index"], 4, "event index")
        + bytes([code]) + _u(fields["source_action_nonce"], 8, "source action nonce")
        + payload_digest).digest()


def certificate_message(fields: dict[str, Any],
                        domain_hex: str = "56414d532d4630352d434552542d563300") -> bytes:
    exact_keys(fields, {name + "_hex" if name.endswith("hash") or name == "action_id" else name for name, _ in CERTIFICATE_FIELDS}, "certificate fields")
    result = bytearray(_prefix(domain_hex, "certificate domain"))
    for name, width in CERTIFICATE_FIELDS:
        value = fields[name + "_hex"] if name.endswith("hash") or name == "action_id" else fields[name]
        if name.endswith("hash") or name == "action_id":
            result.extend(_hex(value, width, name))
        elif name.endswith("_code") or name in {"action_code", "destination_address_network_id"}:
            uint(value, width * 8, name)
            result.extend(bytes([value]))
        else:
            result.extend(_u(value, width, name))
    if len(result) != 321:
        raise DesignError("certificate serialization length is not 321 bytes")
    return bytes(result)


def _field_hex_key(name: str) -> str:
    return name if name.endswith("_hex") else name + "_hex"


def _encode_typed_fields(values: dict[str, Any], fields: list[list[Any]], label: str) -> bytes:
    """Encode a frozen ordered `[field,width-or-type]` vector without JSON normalization."""
    result = bytearray()
    for name, encoding in fields:
        if not isinstance(name, str):
            raise DesignError(f"{label} has a malformed field declaration")
        key = name
        if key not in values and _field_hex_key(name) in values:
            key = _field_hex_key(name)
        if key not in values:
            raise DesignError(f"{label} is missing {name}")
        value = values[key]
        if isinstance(encoding, int):
            if name.endswith("hash") or name in {"barrier_id", "action_id", "source_stream_key_hash",
                    "destination_effect_commitment", "cardano_outbox_commitment", "polygon_outbox_commitment",
                    "cardano_ready_receipt", "polygon_drained_receipt", "action_certificate_hash",
                    "ordered_keys", "ordered_next_keys"}:
                result.extend(_hex(value, encoding, f"{label}.{name}"))
            elif name == "status" and isinstance(value, str):
                status_values = {"ACTIVE": 1, "PAUSED": 2}
                if value not in status_values:
                    raise DesignError(f"{label}.{name} has an unknown status")
                result.extend(_u(status_values[value], encoding, f"{label}.{name}"))
            else:
                result.extend(_u(value, encoding, f"{label}.{name}"))
            continue
        if encoding in {"uint64", "uint128"}:
            result.extend(_u(value, int(encoding[4:]) // 8, f"{label}.{name}"))
            continue
        if encoding in {"bytes20", "bytes28", "bytes32", "bytes4"}:
            result.extend(_hex(value, int(encoding[5:]), f"{label}.{name}"))
        elif encoding == "bytes_1_to_32_length_prefixed_u8" or encoding == "bytes_1_to_128_length_prefixed_u16":
            raw = _hex(value, len(value) // 2, f"{label}.{name}")
            max_len = 32 if "32" in encoding else 128
            if not 1 <= len(raw) <= max_len:
                raise DesignError(f"{label}.{name} length is outside its declared bounds")
            prefix_bytes = 1 if encoding.endswith("u8") else 2
            result.extend(_u(len(raw), prefix_bytes, f"{label}.{name} length"))
            result.extend(raw)
        elif encoding == "enum1_QUEUED_EXECUTED":
            enum = {"QUEUED": 1, "EXECUTED": 2}
            if value not in enum:
                raise DesignError(f"{label}.{name} has an unknown enum value")
            result.append(enum[value])
        else:
            raise DesignError(f"{label}.{name} has an unsupported frozen encoding")
    return bytes(result)


def _encode_sync_message(fields: dict[str, Any], contract: dict[str, Any]) -> bytes:
    rows = contract["polygon_authority_mirror"]["sync_message_fields"]
    expected = {name + "_hex" if name.endswith("hash") or name == "ordered_keys" else name for name, _ in rows}
    exact_keys(fields, expected, "authority sync message fields")
    result = bytearray(_prefix(contract["polygon_authority_mirror"]["sync_certificate_domain_hex"], "authority sync domain"))
    result.extend(_encode_typed_fields(fields, rows, "authority sync message"))
    if len(result) != contract["polygon_authority_mirror"]["sync_message_bytes"]:
        raise DesignError("authority sync message length mismatch")
    return bytes(result)


def _committee_list_from_ordered_hex(value: str, label: str) -> list[str]:
    raw = _hex(value, 160, label)
    keys = [raw[offset:offset + 32] for offset in range(0, 160, 32)]
    if keys != sorted(keys) or len(set(keys)) != 5:
        raise DesignError(f"{label} must contain five distinct sorted keys")
    return [key.hex() for key in keys]


def _validate_prior_mirror(prior: dict[str, Any], spec: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    exact_keys(prior, set(spec["prior_mirror_fields"]), "prior Polygon authority mirror")
    exact_keys(prior["canonical_state"], set(spec["authority_state_fields"]), "prior canonical authority state")
    state_bytes = _encode_authority_state(prior["canonical_state"], contract)
    digest = hashlib.sha256(state_bytes).hexdigest()
    canonical = prior["canonical_state"]
    prior_keys = _committee_list_from_ordered_hex(prior["ordered_keys_hex"], "prior mirror ordered keys")
    if (prior["authority_state_hash_hex"] != digest
            or prior["authority_epoch"] != canonical["epoch"]
            or prior["status"] != canonical["status"]
            or prior["ordered_keys_hex"] != canonical["ordered_keys_hex"]
            or prior["threshold"] != canonical["threshold"]
            or prior["committee_epoch"] != canonical["epoch"]
            or canonical["schema_version"] != 3
            or canonical["threshold"] != 3):
        raise DesignError("prior Polygon mirror does not match its canonical trusted authority state")
    uint(prior["sync_nonce"], 64, "prior mirror sync nonce")
    uint(prior["source_checkpoint_number"], 64, "prior mirror source checkpoint")
    _hex(prior["source_checkpoint_hash_hex"], 32, "prior mirror source checkpoint hash")
    _hex(prior["previous_sync_checkpoint_hash_hex"], 32, "prior mirror previous sync checkpoint")
    return prior_keys


def _validate_rotation_cases(cases: Any, spec: dict[str, Any], contract: dict[str, Any]) -> None:
    if not isinstance(cases, list) or len(cases) != 1:
        raise DesignError("exactly one synthetic prior-committee rotation/settlement case is required")
    for index, case in enumerate(cases):
        exact_keys(case, set(spec["rotation_case_fields"]), f"rotation_cases[{index}]")
        if not isinstance(case["case_id"], str) or not case["case_id"]:
            raise DesignError("rotation case ID must be a non-empty string")
        prior = case["prior_mirror"]
        prior_keys = _validate_prior_mirror(prior, spec, contract)
        if prior["authority_epoch"] != 0 or prior["status"] != "ACTIVE":
            raise DesignError("synthetic rotation case must start from the deployment-pinned active genesis mirror")
        next_state = case["next_authority_state"]
        exact_keys(next_state, set(spec["authority_state_fields"]), "next authority state")
        next_bytes = _encode_authority_state(next_state, contract)
        next_hash = hashlib.sha256(next_bytes).hexdigest()
        if (uint(next_state["epoch"], 64, "next authority epoch") != prior["authority_epoch"] + 1
                or next_state["schema_version"] != 3 or next_state["threshold"] != 3
                or next_state["status"] != "ACTIVE"):
            raise DesignError("rotation case must advance exactly one epoch to active v3 authority")
        next_keys = _committee_list_from_ordered_hex(next_state["ordered_keys_hex"], "next authority keys")
        if next_keys == prior_keys:
            raise DesignError("rotation case must demonstrate the post-rotation key set")
        sync = case["sync_certificate"]
        exact_keys(sync, set(spec["sync_certificate_fields"]), "rotation sync certificate")
        exact_keys(sync["message_fields"], set(spec["sync_message_fields"]), "rotation sync message")
        sync_message = _encode_sync_message(sync["message_fields"], contract)
        if (sync["message_bytes_hex"] != sync_message.hex()
                or sync["message_sha256"] != hashlib.sha256(sync_message).hexdigest()
                or not verify_signatures(sync["committee_public_keys_hex"], sync_message, _committee_signature_records(sync))
                or sync["committee_public_keys_hex"] != prior_keys):
            raise DesignError("rotation sync must be signed by the trusted pre-update committee")
        smsg = sync["message_fields"]
        cardano = contract["networks"]["cardano_preprod"]
        if (smsg["previous_authority_epoch"] != prior["authority_epoch"]
                or smsg["previous_authority_state_hash_hex"] != prior["authority_state_hash_hex"]
                or smsg["authority_epoch"] != next_state["epoch"] or smsg["authority_state_hash_hex"] != next_hash
                or smsg["ordered_keys_hex"] != next_state["ordered_keys_hex"]
                or smsg["status"] != 1 or smsg["threshold"] != 3
                or smsg["committee_epoch"] != next_state["epoch"]
                or smsg["sync_nonce"] != prior["sync_nonce"] + 1
                or (smsg["source_chain_code"], smsg["source_chain_id"], smsg["source_network_magic"])
                   != (cardano["chain_code"], cardano["chain_id"], cardano["network_magic"])):
            raise DesignError("rotation sync does not bind prior trusted state to the exact finalized next state")
        if (smsg["expires_at_ms"] <= smsg["issued_at_ms"]
                or smsg["expires_at_ms"] - smsg["issued_at_ms"] > contract["polygon_authority_mirror"]["freshness_max_ms"]):
            raise DesignError("rotation sync time window is invalid")
        pending = case["pending_record"]
        exact_keys(pending, set(spec["pending_record_fields"]), "pending source action snapshot")
        _hex(pending["action_id_hex"], 32, "pending action ID")
        stream_raw = _hex(pending["source_stream_key_hex"], len(pending["source_stream_key_hex"]) // 2, "pending source stream")
        if len(stream_raw) not in (34, 42) or stream_raw[13] not in (20, 28) or len(stream_raw) != 14 + stream_raw[13]:
            raise DesignError("rotation pending action has an ambiguous source stream key")
        uint(pending["source_action_nonce"], 64, "pending action nonce")
        _hex(pending["source_transaction_id_hex"], 32, "pending source transaction")
        _hex(pending["effect_commitment_hex"], 32, "pending destination effect")
        uint(pending["source_amount_base"], 128, "pending source amount")
        uint(pending["wrapped_amount"], 64, "pending wrapped amount")
        uint(pending["authority_epoch"], 64, "pending authority epoch")
        pending_keys = _committee_list_from_ordered_hex(pending["committee_public_keys_hex"], "pending committee snapshot")
        _hex(pending["authority_state_hash_hex"], 32, "pending authority snapshot hash")
        if (pending["authority_epoch"] != prior["authority_epoch"]
                or pending["authority_state_hash_hex"] != prior["authority_state_hash_hex"]
                or pending_keys != prior_keys
                or pending["status"] != "DESTINATION_FINALIZED"
                or pending["effect_commitment_hex"] == "00" * 32
                or pending["action_kind"] not in contract["checkpoint_and_replay"]["pending_record_schema"]["action_kinds"]):
            raise DesignError("pending action does not retain its exact bounded source-time authority snapshot")
        receipt = case["receipt"]
        exact_keys(receipt, set(spec["ack_receipt_fields"]), "post-rotation settlement receipt")
        exact_keys(receipt["message_fields"], set(spec["settlement_ack_message_fields"]), "post-rotation receipt message")
        receipt_message = _encode_settlement_receipt(receipt["message_fields"], contract)
        if (receipt["message_bytes_hex"] != receipt_message.hex()
                or receipt["message_sha256"] != hashlib.sha256(receipt_message).hexdigest()
                or receipt["committee_public_keys_hex"] != pending_keys
                or not verify_signatures(receipt["committee_public_keys_hex"], receipt_message, _committee_signature_records(receipt))):
            raise DesignError("pending action receipt must verify only against its bounded source-time key snapshot")
        rmsg = receipt["message_fields"]
        stream_hash = hashlib.sha256(bytes.fromhex(pending["source_stream_key_hex"])).hexdigest()
        action = next(item for item in contract["actions"] if item["name"] == pending["action_kind"])
        destination_network = contract["networks"][action["destination"]]
        if (rmsg["action_id_hex"] != pending["action_id_hex"]
                or rmsg["action_code"] != action["code"]
                or rmsg["source_stream_key_hash_hex"] != stream_hash
                or rmsg["source_action_nonce"] != pending["source_action_nonce"]
                or (rmsg["destination_chain_code"], rmsg["destination_chain_id"], rmsg["destination_network_magic"])
                   != (destination_network["chain_code"], destination_network["chain_id"], destination_network["network_magic"])
                or rmsg["destination_effect_commitment_hex"] != pending["effect_commitment_hex"]
                or rmsg["authority_epoch"] != pending["authority_epoch"]
                or rmsg["authority_state_hash_hex"] != pending["authority_state_hash_hex"]
                or rmsg["expires_at_ms"] <= rmsg["issued_at_ms"]
                or rmsg["expires_at_ms"] - rmsg["issued_at_ms"] > contract["settlement_ack"]["message_expiry_ms"]):
            raise DesignError("post-rotation receipt is not bound to pending action and source-time authority")
        if case["expected"] != {"accepted": True, "result_code": "ACCEPT"}:
            raise DesignError("rotation positive case must have exact ACCEPT outcome")


def _barrier_message(values: dict[str, Any], rows: list[list[Any]], domain_hex: str, label: str) -> bytes:
    expected = {_field_hex_key(name) if (name.endswith("hash") or name in {
        "barrier_id", "action_id", "cardano_outbox_commitment", "polygon_outbox_commitment",
        "cardano_ready_receipt", "polygon_drained_receipt", "action_certificate_hash"}) else name
        for name, _ in rows}
    exact_keys(values, expected, f"{label} fields")
    return _prefix(domain_hex, f"{label} domain") + _encode_typed_fields(values, rows, label)


def _verify_barrier_certificate(certificate: dict[str, Any], rows: list[list[Any]],
                                message_field_schema: list[str], domain_hex: str,
                                expected_keys: list[str], label: str, consume_now_ms: int,
                                max_lifetime_ms: int) -> tuple[str, dict[str, Any]]:
    exact_keys(certificate, {"version", "committee_public_keys_hex", "signer_ids", "message_fields",
                             "message_bytes_hex", "message_sha256", "signatures_hex"}, label)
    if uint(certificate["version"], 16, f"{label} version") != 4:
        raise DesignError(f"{label} version is not v4")
    if certificate["committee_public_keys_hex"] != expected_keys:
        raise DesignError(f"{label} is not signed by its exact trusted committee")
    fields = certificate["message_fields"]
    exact_keys(fields, set(message_field_schema), f"{label} message")
    issued = uint(fields["issued_at_ms"], 64, f"{label} issue time")
    expires = uint(fields["expires_at_ms"], 64, f"{label} expiry time")
    consume_now = uint(consume_now_ms, 64, f"{label} consuming time")
    if expires <= issued or expires - issued > max_lifetime_ms or not issued <= consume_now <= expires:
        raise DesignError(f"{label} is expired, future-issued, or outside the bounded freshness window")
    encoded = _barrier_message(fields, rows, domain_hex, label)
    if (certificate["message_bytes_hex"] != encoded.hex()
            or certificate["message_sha256"] != hashlib.sha256(encoded).hexdigest()
            or not verify_signatures(expected_keys, encoded, _committee_signature_records(certificate))):
        raise DesignError(f"{label} bytes, digest, or Ed25519 threshold is invalid")
    return hashlib.sha256(encoded).hexdigest(), fields


def _destination_consume_time_ms(certificate: dict[str, Any], destination_chain_code: int, label: str) -> int:
    context = certificate.get("destination_time_context")
    exact_keys(context, {"cardano_validity_lower_posix_ms", "cardano_validity_upper_posix_ms",
                         "evm_block_timestamp_seconds"}, f"{label} destination time context")
    lower = uint(context["cardano_validity_lower_posix_ms"], 64, f"{label} Cardano lower bound")
    upper = uint(context["cardano_validity_upper_posix_ms"], 64, f"{label} Cardano upper bound")
    seconds = uint(context["evm_block_timestamp_seconds"], 64, f"{label} EVM block time")
    if destination_chain_code == 2:
        if seconds != 0 or not lower < upper:
            raise DesignError(f"{label} Cardano destination time interval is invalid")
        # Use the conservative latest possible inclusion time in the bounded interval.
        return upper
    if lower != 0 or upper != 0 or seconds > (2**64 - 1) // 1000:
        raise DesignError(f"{label} EVM destination time is invalid or overflows milliseconds")
    return seconds * 1000


def _watermark_commitment(records: Any, stream_names: list[str], contract: dict[str, Any], label: str) -> tuple[str, list[dict[str, Any]]]:
    barrier = contract["rotation_barrier"]
    if not isinstance(records, list) or len(records) != len(stream_names):
        raise DesignError(f"{label} must contain exactly its two fixed source streams")
    configured = {item["name"]: item for item in contract["checkpoint_and_replay"]["source_streams"]}
    encoded = bytearray()
    normalized: list[dict[str, Any]] = []
    for name, record in zip(stream_names, records):
        exact_keys(record, set(barrier["stream_watermark_fields"]), f"{label}[{name}]")
        raw_key = _hex(record["source_stream_key_hex"], len(record["source_stream_key_hex"]) // 2,
                       f"{label} source stream key")
        if len(raw_key) not in (34, 42) or raw_key[13] not in (20, 28) or len(raw_key) != 14 + raw_key[13]:
            raise DesignError(f"{label} source stream key has ambiguous endpoint encoding")
        config = configured[name]
        network = contract["networks"][config["chain"]]
        expected_endpoint_length = config["endpoint_bytes"]
        if (raw_key[0] != network["chain_code"]
                or int.from_bytes(raw_key[1:9], "big") != network["chain_id"]
                or int.from_bytes(raw_key[9:13], "big") != network["network_magic"]
                or raw_key[13] != expected_endpoint_length):
            raise DesignError(f"{label} source stream is attributed to the wrong fixed chain or endpoint type")
        nonce = uint(record["source_action_nonce"], 64, f"{label} source nonce")
        if not isinstance(record["pending"], bool):
            raise DesignError(f"{label} pending flag must be boolean")
        action_id_raw = _hex(record["pending_action_id_hex"], 32, f"{label} pending action ID")
        payload_raw = _hex(record["payload_hash_hex"], 32, f"{label} pending payload hash")
        effect_raw = _hex(record["effect_commitment_hex"], 32, f"{label} pending effect commitment")
        tx_raw = _hex(record["source_transaction_hash_hex"], 32, f"{label} source transaction")
        event_index = uint(record["source_event_index"], 32, f"{label} source event index")
        event_number = uint(record["source_event_block_number"], 64, f"{label} source event block")
        event_hash = _hex(record["source_event_block_hash_hex"], 32, f"{label} source event block hash")
        if record["pending"]:
            if nonce == 0 or not any(action_id_raw) or not any(payload_raw) or not any(tx_raw) or not any(event_hash) or event_number == 0:
                raise DesignError(f"{label} pending watermark lacks exact action identity/source event")
        elif any(action_id_raw + payload_raw + effect_raw + tx_raw + event_hash) or event_index != 0 or event_number != 0:
            raise DesignError(f"{label} empty watermark must use canonical zero pending fields")
        encoded.extend(raw_key)
        encoded.extend(_u(nonce, 8, f"{label} source nonce"))
        encoded.append(1 if record["pending"] else 0)
        encoded.extend(action_id_raw + payload_raw + effect_raw + tx_raw)
        encoded.extend(_u(event_index, 4, f"{label} event index"))
        encoded.extend(_u(event_number, 8, f"{label} event number"))
        encoded.extend(event_hash)
        normalized.append(record)
    digest = hashlib.sha256(_prefix(barrier["outbox_commitment_domain_hex"], "rotation outbox domain") + encoded).hexdigest()
    return digest, normalized


def _validate_barrier_cutoff(cutoff: Any, chain_name: str, contract: dict[str, Any], label: str) -> dict[str, Any]:
    exact_keys(cutoff, set(contract["rotation_barrier"]["cutoff_fields"]), label)
    network = contract["networks"][chain_name]
    if (uint(cutoff["chain_code"], 8, f"{label} chain code") != network["chain_code"]
            or uint(cutoff["chain_id"], 64, f"{label} chain ID") != network["chain_id"]
            or uint(cutoff["network_magic"], 32, f"{label} network magic") != network["network_magic"]):
        raise DesignError(f"{label} is bound to the wrong chain/network")
    uint(cutoff["checkpoint_number"], 64, f"{label} checkpoint number")
    _hex(cutoff["checkpoint_hash_hex"], 32, f"{label} checkpoint hash")
    _hex(cutoff["previous_checkpoint_hash_hex"], 32, f"{label} previous checkpoint hash")
    return cutoff


def _validate_rotation_barrier_cases(cases: Any, spec: dict[str, Any], contract: dict[str, Any],
                                     rotation_cases: list[dict[str, Any]],
                                     action_vectors: list[dict[str, Any]]) -> None:
    if not isinstance(cases, list) or len(cases) != contract["vector_schema"]["rotation_barrier_case_count"]:
        raise DesignError("v4 requires the exact nominal, post-freeze pause, and pre-freeze pause/resume vectors")
    barrier = contract["rotation_barrier"]
    names = ["wrapped_escrow", "polygon_slash_event"]
    cardano_names = ["wrapped_burn_policy", "cardano_timelock_intent"]
    base_rotation = rotation_cases[0]
    prior_keys = _committee_list_from_ordered_hex(base_rotation["prior_mirror"]["ordered_keys_hex"], "barrier prior keys")
    base_next_state = base_rotation["next_authority_state"]
    expected_ids = ["rotation_barrier_nominal", "rotation_barrier_pause_resume", "rotation_barrier_pre_freeze_pause_resume"]
    action_vectors_by_id = {item.get("case_id"): item for item in action_vectors if isinstance(item, dict)}
    for case_index, case in enumerate(cases):
        exact_keys(case, set(spec["rotation_barrier_case_fields"]), f"rotation_barrier_cases[{case_index}]")
        if case["case_id"] != expected_ids[case_index]:
            raise DesignError("rotation barrier cases must be ordered nominal, post-freeze pause, pre-freeze pause")
        next_state = case["cardano_activation"]["next_authority_state"]
        _encode_authority_state(next_state, contract)
        next_keys = _committee_list_from_ordered_hex(next_state["ordered_keys_hex"], "barrier next keys")
        if next_state["ordered_keys_hex"] != base_next_state["ordered_keys_hex"]:
            raise DesignError("pause recovery cannot change the already-authorized target committee")
        if case_index == 0:
            resumed_epoch = base_rotation["prior_mirror"]["authority_epoch"]
        elif case_index == 1:
            resumed_epoch = uint(case["pause_resume"]["current_authority_epoch"], 64, "post-pause current authority epoch")
        else:
            resumed_epoch = uint(case["pre_freeze_pause_resume"]["resumed_authority_epoch"], 64, "pre-freeze resumed authority epoch")
        if next_state["epoch"] != resumed_epoch + 1:
            raise DesignError("rotation target epoch must be exactly current post-resume authority epoch plus one")
        barrier_id = _hex(case["barrier_id_hex"], 32, "rotation barrier ID")
        if not any(barrier_id):
            raise DesignError("rotation barrier ID must be nonzero")
        prepare = case["cardano_prepare"]
        exact_keys(prepare, {"phase", "authority_epoch", "authority_state_hash_hex", "target_epoch",
                             "target_authority_state_hash_hex", "target_ordered_keys_hex", "cardano_source_cutoff", "cardano_destination_cutoff",
                             "cardano_stream_watermarks", "outbox_commitment_hex", "freeze_certificate", "now_ms"}, "Cardano rotation prepare")
        if (prepare["phase"] != "CARDANO_DRAINING"
                or uint(prepare["authority_epoch"], 64, "Cardano prepare epoch") != base_rotation["prior_mirror"]["authority_epoch"]
                or prepare["authority_state_hash_hex"] != base_rotation["prior_mirror"]["authority_state_hash_hex"]
                or uint(prepare["target_epoch"], 64, "Cardano target epoch") != base_next_state["epoch"]
                or prepare["target_authority_state_hash_hex"] != hashlib.sha256(_encode_authority_state(base_next_state, contract)).hexdigest()
                or prepare["target_ordered_keys_hex"] != next_state["ordered_keys_hex"]):
            raise DesignError("Cardano prepare is not bound to exact current and proposed authority states")
        c_source = _validate_barrier_cutoff(prepare["cardano_source_cutoff"], "cardano_preprod", contract, "Cardano source cutoff")
        c_dest = _validate_barrier_cutoff(prepare["cardano_destination_cutoff"], "cardano_preprod", contract, "Cardano destination cutoff")
        c_commit, c_initial = _watermark_commitment(prepare["cardano_stream_watermarks"], cardano_names, contract, "Cardano prepare watermarks")
        if prepare["outbox_commitment_hex"] != c_commit:
            raise DesignError("Cardano prepare outbox commitment mismatch")
        polygon = case["polygon_freeze"]
        pre_freeze = case["pre_freeze_pause_resume"]
        if case_index == 2:
            stale_freeze_hash, stale_freeze_msg = _verify_barrier_certificate(prepare["freeze_certificate"],
                barrier["freeze_message_fields"], spec["freeze_message_fields"], barrier["freeze_domain_hex"], prior_keys,
                "pre-pause Cardano freeze certificate", prepare["now_ms"], contract["polygon_authority_mirror"]["freshness_max_ms"])
            exact_keys(pre_freeze, {"present", "barrier_id_before_hex", "barrier_id_after_hex",
                "cardano_source_cutoff_before", "cardano_source_cutoff_after", "cardano_destination_cutoff_before",
                "cardano_destination_cutoff_after", "cardano_stream_watermarks_before", "cardano_stream_watermarks_after",
                "outbox_commitment_before_hex", "outbox_commitment_after_hex", "polygon_cutoff_before", "polygon_cutoff_after",
                "stale_freeze_certificate_hash_hex",
                "stale_freeze_rejected", "resumed_authority_epoch", "resumed_authority_state_hash_hex",
                "current_committee_keys_hex", "target_ordered_keys_hex", "reauthorized_target_epoch",
                "reauthorized_target_authority_state_hash_hex", "now_ms"}, "pre-freeze pause/resume")
            if (pre_freeze["present"] is not True or pre_freeze["barrier_id_before_hex"] != case["barrier_id_hex"]
                    or pre_freeze["barrier_id_after_hex"] != case["barrier_id_hex"]
                    or pre_freeze["cardano_source_cutoff_before"] != prepare["cardano_source_cutoff"]
                    or pre_freeze["cardano_source_cutoff_after"] != prepare["cardano_source_cutoff"]
                    or pre_freeze["cardano_destination_cutoff_before"] != prepare["cardano_destination_cutoff"]
                    or pre_freeze["cardano_destination_cutoff_after"] != prepare["cardano_destination_cutoff"]
                    or pre_freeze["cardano_stream_watermarks_before"] != prepare["cardano_stream_watermarks"]
                    or pre_freeze["cardano_stream_watermarks_after"] != prepare["cardano_stream_watermarks"]
                    or pre_freeze["outbox_commitment_before_hex"] != prepare["outbox_commitment_hex"]
                    or pre_freeze["outbox_commitment_after_hex"] != prepare["outbox_commitment_hex"]
                    or pre_freeze["polygon_cutoff_before"] is not None
                    or pre_freeze["polygon_cutoff_after"] != polygon["polygon_source_cutoff"]
                    or pre_freeze["stale_freeze_certificate_hash_hex"] != stale_freeze_hash
                    or pre_freeze["stale_freeze_rejected"] is not True
                    or pre_freeze["current_committee_keys_hex"] != base_rotation["prior_mirror"]["ordered_keys_hex"]
                    or pre_freeze["target_ordered_keys_hex"] != prepare["target_ordered_keys_hex"]
                    or uint(pre_freeze["resumed_authority_epoch"], 64, "resumed freeze authority epoch") != prepare["authority_epoch"] + 2
                    or pre_freeze["resumed_authority_state_hash_hex"] == prepare["authority_state_hash_hex"]
                    or uint(pre_freeze["reauthorized_target_epoch"], 64, "pre-freeze reauthorized target epoch") != pre_freeze["resumed_authority_epoch"] + 1
                    or pre_freeze["reauthorized_target_epoch"] != next_state["epoch"]
                    or pre_freeze["reauthorized_target_authority_state_hash_hex"] != hashlib.sha256(_encode_authority_state(next_state, contract)).hexdigest()
                    or stale_freeze_msg["target_epoch"] != prepare["target_epoch"]
                    or stale_freeze_msg["target_authority_state_hash_hex"] != prepare["target_authority_state_hash_hex"]):
                raise DesignError("pre-freeze pause recovery changes or rewinds the durable Cardano barrier snapshot")
            current_keys = _committee_list_from_ordered_hex(pre_freeze["current_committee_keys_hex"], "resumed freeze current keys")
            freeze_hash, freeze_msg = _verify_barrier_certificate(polygon["freeze_certificate"],
                barrier["freeze_message_fields"], spec["freeze_message_fields"], barrier["freeze_domain_hex"], current_keys,
                "resumed Polygon freeze certificate", polygon["now_ms"], contract["polygon_authority_mirror"]["freshness_max_ms"])
        else:
            if pre_freeze is not None:
                raise DesignError("pre-freeze pause vector must be absent outside its designated case")
            freeze_hash, freeze_msg = _verify_barrier_certificate(prepare["freeze_certificate"],
            barrier["freeze_message_fields"], spec["freeze_message_fields"], barrier["freeze_domain_hex"], prior_keys,
            "Cardano freeze certificate", polygon["now_ms"], contract["polygon_authority_mirror"]["freshness_max_ms"])
        if (freeze_msg["barrier_id_hex"] != case["barrier_id_hex"]
                or freeze_msg["authority_epoch"] != (pre_freeze["resumed_authority_epoch"] if case_index == 2 else prepare["authority_epoch"])
                or freeze_msg["authority_state_hash_hex"] != (pre_freeze["resumed_authority_state_hash_hex"] if case_index == 2 else prepare["authority_state_hash_hex"])
                or freeze_msg["target_epoch"] != (pre_freeze["reauthorized_target_epoch"] if case_index == 2 else prepare["target_epoch"])
                or freeze_msg["target_authority_state_hash_hex"] != (pre_freeze["reauthorized_target_authority_state_hash_hex"]
                    if case_index == 2 else prepare["target_authority_state_hash_hex"])
                or freeze_msg["cardano_source_cutoff_number"] != c_source["checkpoint_number"]
                or freeze_msg["cardano_source_cutoff_hash_hex"] != c_source["checkpoint_hash_hex"]
                or freeze_msg["cardano_destination_cutoff_number"] != c_dest["checkpoint_number"]
                or freeze_msg["cardano_destination_cutoff_hash_hex"] != c_dest["checkpoint_hash_hex"]
                or freeze_msg["cardano_outbox_commitment_hex"] != c_commit
                or freeze_msg["expires_at_ms"] <= freeze_msg["issued_at_ms"]
                or freeze_msg["expires_at_ms"] - freeze_msg["issued_at_ms"] > contract["polygon_authority_mirror"]["freshness_max_ms"]):
            raise DesignError("Cardano freeze certificate does not bind the exact barrier, target, cutoff, and outbox")

        exact_keys(polygon, {"phase", "authority_epoch", "authority_state_hash_hex", "cardano_source_cutoff",
            "cardano_stream_watermarks", "polygon_source_cutoff", "polygon_destination_cutoff",
            "polygon_stream_watermarks", "outbox_commitment_hex", "freeze_certificate", "now_ms",
            "stale_freeze_certificate_hash_hex", "stale_freeze_rejected"}, "Polygon rotation freeze")
        if (polygon["phase"] != "POLYGON_DRAINING"
                or polygon["authority_epoch"] != (pre_freeze["resumed_authority_epoch"] if case_index == 2 else prepare["authority_epoch"])
                or polygon["authority_state_hash_hex"] != (pre_freeze["resumed_authority_state_hash_hex"] if case_index == 2 else prepare["authority_state_hash_hex"])
                or polygon["cardano_source_cutoff"] != prepare["cardano_source_cutoff"]
                or polygon["cardano_stream_watermarks"] != prepare["cardano_stream_watermarks"]
                or (case_index != 2 and (polygon["stale_freeze_rejected"] is not False
                    or polygon["stale_freeze_certificate_hash_hex"] is not None
                    or polygon["freeze_certificate"] != prepare["freeze_certificate"]))
                or (case_index == 2 and (polygon["stale_freeze_rejected"] is not True
                    or polygon["stale_freeze_certificate_hash_hex"] != pre_freeze["stale_freeze_certificate_hash_hex"]))):
            raise DesignError("Polygon freeze is not the atomic continuation of the finalized Cardano freeze request")
        p_source = _validate_barrier_cutoff(polygon["polygon_source_cutoff"], "polygon_amoy", contract, "Polygon source cutoff")
        p_dest = _validate_barrier_cutoff(polygon["polygon_destination_cutoff"], "polygon_amoy", contract, "Polygon destination cutoff")
        p_commit, p_initial = _watermark_commitment(polygon["polygon_stream_watermarks"], names, contract, "Polygon freeze watermarks")
        if polygon["outbox_commitment_hex"] != p_commit:
            raise DesignError("Polygon freeze outbox commitment mismatch")
        pending_initial = {
            item["source_stream_key_hex"]: item for item in c_initial + p_initial if item["pending"]
        }
        stream_by_key = {item["source_stream_key_hex"]: name
                         for names_for_ledger, records_for_ledger in ((cardano_names, c_initial), (names, p_initial))
                         for name, item in zip(names_for_ledger, records_for_ledger)}
        steps = case["drain_steps"]
        if not isinstance(steps, list) or len(steps) != len(pending_initial):
            raise DesignError("drain steps must settle exactly every frozen pending action and no other action")
        seen: set[str] = set()
        for step_index, step in enumerate(steps):
            exact_keys(step, {"ledger", "action_vector_case_id", "action_id_hex", "source_stream_key_hex", "source_action_nonce",
                "source_event_block_number", "source_cutoff_checkpoint_number", "source_cutoff_checkpoint_hash_hex",
                "payload_hash_hex", "effect_commitment_hex", "authority_epoch", "authority_state_hash_hex",
                "destination_effect_committed", "ack_committed", "action_certificate", "resumed_action_certificate"},
                f"rotation drain step {step_index}")
            stream_hex = step["source_stream_key_hex"]
            initial = pending_initial.get(stream_hex)
            if initial is None or stream_hex in seen:
                raise DesignError("drain step is not a unique exact pending barrier watermark")
            seen.add(stream_hex)
            source_event_block_number = uint(step["source_event_block_number"], 64, "drain source event block number")
            source_cutoff_checkpoint_number = uint(step["source_cutoff_checkpoint_number"], 64, "drain source cutoff checkpoint number")
            if source_event_block_number > source_cutoff_checkpoint_number:
                raise DesignError("drain source event exceeds frozen cutoff")
            stream_name = stream_by_key.get(stream_hex)
            action_by_stream = {"wrapped_escrow": "WRAPPED_CREDIT", "wrapped_burn_policy": "WRAPPED_RELEASE",
                                "polygon_slash_event": "SLASH_AGENT", "cardano_timelock_intent": "EXECUTE_INTENT"}
            action = next((item for item in contract["actions"] if item["name"] == action_by_stream.get(stream_name)), None)
            if action is None:
                raise DesignError("drain step source stream is not one of the four fixed action streams")
            expected_source = contract["networks"][action["source"]]
            expected_destination = contract["networks"][action["destination"]]
            if step["ledger"] != action["source"]:
                raise DesignError("drain step is assigned to the wrong source ledger")
            linked_vector = action_vectors_by_id.get(step["action_vector_case_id"])
            if linked_vector is None or linked_vector["action_name"] != action["name"]:
                raise DesignError("drain step must link to one exact positive action vector of the matching action type")
            linked_identity = linked_vector["identity_fields"]
            linked_stream_key = _source_stream_key(linked_identity).hex()
            linked_message = linked_vector["certificate"]["message_fields"]
            if (linked_stream_key != stream_hex
                    or linked_vector["action_id_hex"] != initial["pending_action_id_hex"]
                    or linked_vector["payload_sha256"] != initial["payload_hash_hex"]
                    or linked_message["source_action_nonce"] != initial["source_action_nonce"]
                    or linked_message["source_event_block_number"] != initial["source_event_block_number"]
                    or linked_message["source_event_block_hash_hex"] != initial["source_event_block_hash_hex"]
                    or linked_message["event_transaction_hash_hex"] != initial["source_transaction_hash_hex"]
                    or linked_message["event_index"] != initial["source_event_index"]
                    or linked_vector["action_effects"]["commitment_hex"] != step["effect_commitment_hex"]):
                raise DesignError("drain step differs from its independently validated positive action vector")
            _hex(step["action_id_hex"], 32, "drain action ID")
            if (step["action_id_hex"] != initial["pending_action_id_hex"]
                    or step["source_action_nonce"] != initial["source_action_nonce"]
                    or step["payload_hash_hex"] != initial["payload_hash_hex"]
                    or step["source_event_block_number"] != initial["source_event_block_number"]
                    or source_event_block_number > source_cutoff_checkpoint_number
                    or step["source_cutoff_checkpoint_number"] != (c_source if step["ledger"] == "cardano_preprod" else p_source)["checkpoint_number"]
                    or step["source_cutoff_checkpoint_hash_hex"] != (c_source if step["ledger"] == "cardano_preprod" else p_source)["checkpoint_hash_hex"]
                    or step["destination_effect_committed"] is not True or step["ack_committed"] is not True):
                raise DesignError("drain step changes or exceeds exact frozen source action identity/cutoff")
            action_cert = step["action_certificate"]
            exact_keys(action_cert, set(spec["certificate_fields"]), "drain action certificate")
            cert_msg = action_cert["message_fields"]
            encoded_action = certificate_message(cert_msg)
            resume_state = case["pause_resume"] if case["pause_resume"] is not None else pre_freeze
            execution_keys = (resume_state["current_committee_keys_hex"] if resume_state is not None else prior_keys)
            execution_epoch = (resume_state.get("current_authority_epoch", resume_state.get("resumed_authority_epoch"))
                               if resume_state is not None else prepare["authority_epoch"])
            execution_state_hash = (resume_state.get("current_authority_state_hash_hex", resume_state.get("resumed_authority_state_hash_hex"))
                                    if resume_state is not None else prepare["authority_state_hash_hex"])
            if (action_cert["committee_public_keys_hex"] != execution_keys
                    or uint(action_cert["version"], 16, "drain action certificate version") != contract["certificate"]["version"]
                    or uint(action_cert["threshold"], 8, "drain threshold") != 3
                    or uint(action_cert["emergency_threshold"], 8, "drain emergency threshold") != 4
                    or uint(action_cert["epoch"], 64, "drain certificate epoch") != execution_epoch):
                raise DesignError("drain action certificate uses keys outside the currently trusted frozen committee")
            if (action_cert["message_bytes_hex"] != encoded_action.hex()
                    or action_cert["message_sha256"] != hashlib.sha256(encoded_action).hexdigest()
                    or not verify_signatures(action_cert["committee_public_keys_hex"], encoded_action,
                                             _committee_signature_records(action_cert))
                    or cert_msg["action_id_hex"] != initial["pending_action_id_hex"]
                    or cert_msg["payload_hash_hex"] != initial["payload_hash_hex"]
                    or cert_msg["action_code"] != action["code"]
                    or (cert_msg["source_chain_code"], cert_msg["source_chain_id"], cert_msg["source_network_magic"])
                       != (expected_source["chain_code"], expected_source["chain_id"], expected_source["network_magic"])
                    or (cert_msg["destination_chain_code"], cert_msg["destination_chain_id"], cert_msg["destination_network_magic"])
                       != (expected_destination["chain_code"], expected_destination["chain_id"], expected_destination["network_magic"])
                    or cert_msg["source_action_nonce"] != initial["source_action_nonce"]
                    or cert_msg["source_event_block_number"] != initial["source_event_block_number"]
                    or cert_msg["authority_epoch"] != step["authority_epoch"]
                    or cert_msg["authority_state_hash_hex"] != step["authority_state_hash_hex"]
                    or step["authority_epoch"] != execution_epoch
                    or step["authority_state_hash_hex"] != execution_state_hash
                    or cert_msg["source_event_block_hash_hex"] != initial["source_event_block_hash_hex"]
                    or cert_msg["event_transaction_hash_hex"] != initial["source_transaction_hash_hex"]
                    or cert_msg["event_index"] != initial["source_event_index"]
                    or cert_msg["finalized_checkpoint_number"] < step["source_event_block_number"]
                    or cert_msg["finalized_checkpoint_number"] != step["source_cutoff_checkpoint_number"]
                    or cert_msg["finalized_checkpoint_hash_hex"] != step["source_cutoff_checkpoint_hash_hex"]
                    or cert_msg["expires_at_ms"] <= cert_msg["issued_at_ms"]
                    or cert_msg["expires_at_ms"] - cert_msg["issued_at_ms"] > contract["certificate"]["max_lifetime_ms"]
                    or action_cert["checkpoint_hash"] != cert_msg["finalized_checkpoint_hash_hex"]):
                raise DesignError("drain action certificate is not bound to the frozen pending event/current authority revision")
            time_context = action_cert["destination_time_context"]
            exact_keys(time_context, {"cardano_validity_lower_posix_ms", "cardano_validity_upper_posix_ms",
                                     "evm_block_timestamp_seconds"}, "drain destination time context")
            lower = uint(time_context["cardano_validity_lower_posix_ms"], 64, "drain Cardano validity lower bound")
            upper = uint(time_context["cardano_validity_upper_posix_ms"], 64, "drain Cardano validity upper bound")
            seconds = uint(time_context["evm_block_timestamp_seconds"], 64, "drain EVM block time")
            if expected_destination["chain_code"] == 2:
                if seconds != 0 or not cert_msg["issued_at_ms"] <= lower < upper < cert_msg["expires_at_ms"] or upper - lower > contract["boundaries"]["cardano_tx_validity_interval_max_ms"]:
                    raise DesignError("drain Cardano destination is outside strict signed time bounds")
            elif lower != 0 or upper != 0 or not cert_msg["issued_at_ms"] <= seconds * 1000 < cert_msg["expires_at_ms"]:
                raise DesignError("drain EVM destination is outside strict signed time bounds")
            if initial["effect_commitment_hex"] != "00" * 32:
                if step["effect_commitment_hex"] != initial["effect_commitment_hex"]:
                    raise DesignError("already-finalized effect commitment changed during drain")
            elif not _hex(step["effect_commitment_hex"], 32, "drained destination effect commitment") or step["effect_commitment_hex"] == "00" * 32:
                raise DesignError("destination commit must derive one nonzero effect commitment")
            if step["resumed_action_certificate"] is not None:
                if resume_state is None or initial["effect_commitment_hex"] != "00" * 32:
                    raise DesignError("only an unexecuted pre-barrier action may carry a resumed-action certificate")
                resumed = step["resumed_action_certificate"]
                resume_keys = resume_state["current_committee_keys_hex"]
                resumed_hash, resumed_msg = _verify_barrier_certificate(resumed,
                    barrier["resumed_action_message_fields"], spec["resumed_action_message_fields"],
                    barrier["resumed_action_domain_hex"], resume_keys, "resumed action certificate",
                    _destination_consume_time_ms(action_cert, expected_destination["chain_code"], "drain action certificate"),
                    contract["polygon_authority_mirror"]["freshness_max_ms"])
                if (resumed_msg["barrier_id_hex"] != case["barrier_id_hex"]
                        or resumed_msg["action_id_hex"] != initial["pending_action_id_hex"]
                        or resumed_msg["source_action_nonce"] != initial["source_action_nonce"]
                        or resumed_msg["payload_hash_hex"] != initial["payload_hash_hex"]
                        or resumed_msg["source_transaction_hash_hex"] != initial["source_transaction_hash_hex"]
                        or resumed_msg["source_event_index"] != initial["source_event_index"]
                        or resumed_msg["source_event_block_number"] != initial["source_event_block_number"]
                        or resumed_msg["source_cutoff_checkpoint_number"] != step["source_cutoff_checkpoint_number"]
                        or resumed_msg["source_cutoff_checkpoint_hash_hex"] != step["source_cutoff_checkpoint_hash_hex"]
                        or resumed_msg["action_certificate_hash_hex"] != action_cert["message_sha256"]
                        or resumed_msg["execution_authority_epoch"] != step["authority_epoch"]
                        or resumed_msg["execution_authority_state_hash_hex"] != step["authority_state_hash_hex"]):
                    raise DesignError("resumed action certificate changes pending identity or escapes cutoff")
            elif resume_state is not None and initial["effect_commitment_hex"] == "00" * 32:
                raise DesignError("unexecuted pending action after pause requires a v4 resumed-action certificate")
        if seen != set(pending_initial):
            raise DesignError("one or more frozen pending actions were omitted from drain")

        ready = case["cardano_ready"]
        drained = case["polygon_drained"]
        exact_keys(ready, {"phase", "cardano_outbox_empty", "cardano_stream_watermarks", "outbox_commitment_hex", "receipt", "now_ms"}, "Cardano drained-ready proof")
        c_final, c_empty = _watermark_commitment(ready["cardano_stream_watermarks"], cardano_names, contract, "Cardano ready watermarks")
        if ready["phase"] != "CARDANO_READY" or ready["cardano_outbox_empty"] is not True or any(item["pending"] for item in c_empty) or c_final != ready["outbox_commitment_hex"]:
            raise DesignError("Cardano ready proof does not commit its exact empty fixed outbox set")
        c_ready_hash, c_ready_msg = _verify_barrier_certificate(ready["receipt"], barrier["cardano_ready_message_fields"],
            spec["cardano_ready_message_fields"], barrier["cardano_ready_domain_hex"], prior_keys, "Cardano ready receipt",
            drained["now_ms"], contract["polygon_authority_mirror"]["freshness_max_ms"])
        if (c_ready_msg["barrier_id_hex"] != case["barrier_id_hex"]
                or c_ready_msg["authority_epoch"] != polygon["authority_epoch"]
                or c_ready_msg["authority_state_hash_hex"] != polygon["authority_state_hash_hex"]
                or c_ready_msg["cardano_source_cutoff_number"] != c_source["checkpoint_number"]
                or c_ready_msg["cardano_source_cutoff_hash_hex"] != c_source["checkpoint_hash_hex"]
                or c_ready_msg["cardano_outbox_commitment_hex"] != c_final):
            raise DesignError("Cardano ready receipt is not bound to barrier and empty source outboxes")

        activation = case["cardano_activation"]
        exact_keys(drained, {"phase", "polygon_outbox_empty", "polygon_stream_watermarks", "cardano_ready_receipt_hash_hex", "outbox_commitment_hex", "receipt", "now_ms"}, "Polygon drained proof")
        p_final, p_empty = _watermark_commitment(drained["polygon_stream_watermarks"], names, contract, "Polygon drained watermarks")
        if (drained["phase"] != "POLYGON_DRAINED" or drained["polygon_outbox_empty"] is not True
                or any(item["pending"] for item in p_empty) or p_final != drained["outbox_commitment_hex"]
                or drained["cardano_ready_receipt_hash_hex"] != c_ready_hash):
            raise DesignError("Polygon drained proof lacks bilateral empty outboxes or Cardano ready receipt")
        authorization = case["cardano_authorization"]
        exact_keys(authorization, {"phase", "authorization_tx_hash_hex", "authorization_event_index",
            "cardano_validity_lower_ms", "cardano_validity_upper_ms", "finalized_checkpoint_number",
            "finalized_checkpoint_hash_hex", "previous_checkpoint_hash_hex", "authorization_certificate", "state"},
            "Cardano ROTATION_AUTHORIZED transition")
        authorized_at = uint(authorization["cardano_validity_upper_ms"], 64, "authorization transaction upper bound")
        authorization_lower = uint(authorization["cardano_validity_lower_ms"], 64, "authorization transaction lower bound")
        uint(authorization["authorization_event_index"], 32, "authorization event index")
        if (authorization["phase"] != "ROTATION_AUTHORIZED" or authorization_lower >= authorized_at
                or authorized_at - authorization_lower > contract["boundaries"]["cardano_tx_validity_interval_max_ms"]):
            raise DesignError("Cardano rotation authorization transition has an invalid bounded finalized transaction")
        auth_hash, auth_msg = _verify_barrier_certificate(authorization["authorization_certificate"],
            barrier["rotation_authorization_message_fields"], spec["rotation_authorization_message_fields"],
            barrier["rotation_authorization_domain_hex"], prior_keys, "rotation authorization certificate",
            authorized_at, contract["polygon_authority_mirror"]["freshness_max_ms"])
        p_drained_hash, p_drained_msg = _verify_barrier_certificate(drained["receipt"], barrier["polygon_drained_message_fields"],
            spec["polygon_drained_message_fields"], barrier["polygon_drained_domain_hex"], prior_keys, "Polygon drained receipt",
            authorized_at, contract["polygon_authority_mirror"]["freshness_max_ms"])
        if (p_drained_msg["barrier_id_hex"] != case["barrier_id_hex"]
                or p_drained_msg["authority_epoch"] != polygon["authority_epoch"]
                or p_drained_msg["authority_state_hash_hex"] != polygon["authority_state_hash_hex"]
                or p_drained_msg["cardano_ready_receipt_hash_hex"] != c_ready_hash
                or p_drained_msg["polygon_source_cutoff_number"] != p_source["checkpoint_number"]
                or p_drained_msg["polygon_source_cutoff_hash_hex"] != p_source["checkpoint_hash_hex"]
                or p_drained_msg["polygon_outbox_commitment_hex"] != p_final):
            raise DesignError("Polygon drained receipt is not bound to the frozen bilateral barrier state")

        exact_keys(activation, {"phase", "cardano_outbox_empty", "polygon_drained_receipt_hash_hex",
            "authorization_state_hash_hex", "authorization_tx_hash_hex", "authorized_at_ms", "activation_at_ms", "activation_validity_lower_ms",
            "activation_validity_upper_ms", "now_ms", "next_authority_state", "rotation_ready_receipt"},
            "Cardano rotation activation")
        if (authorization["authorization_tx_hash_hex"] != _hex(authorization["authorization_tx_hash_hex"], 32, "authorization transaction hash").hex()
                or authorization["finalized_checkpoint_hash_hex"] != _hex(authorization["finalized_checkpoint_hash_hex"], 32, "authorization finalized checkpoint hash").hex()
                or authorization["previous_checkpoint_hash_hex"] != _hex(authorization["previous_checkpoint_hash_hex"], 32, "authorization previous checkpoint hash").hex()):
            raise DesignError("rotation authorization finalized transaction provenance is malformed")
        authorization_state = authorization["state"]
        authorization_state_hash = _rotation_authorized_state_hash(authorization_state, contract)
        if (authorization_state["state_hash_hex"] != authorization_state_hash
                or authorization_state["version"] != 2
                or authorization_state["barrier_id_hex"] != case["barrier_id_hex"]
                or authorization_state["authority_epoch"] != auth_msg["authority_epoch"]
                or authorization_state["authority_state_hash_hex"] != auth_msg["authority_state_hash_hex"]
                or authorization_state["target_epoch"] != auth_msg["target_epoch"]
                or authorization_state["target_authority_state_hash_hex"] != auth_msg["target_authority_state_hash_hex"]
                or authorization_state["target_ordered_keys_hash_hex"] != auth_msg["target_ordered_keys_hash_hex"]
                or authorization_state["polygon_drained_receipt_hash_hex"] != p_drained_hash
                or authorization_state["authorization_certificate_hash_hex"] != auth_hash
                or authorization_state["authorized_at_ms"] != authorized_at
                or authorization_state["authorization_tx_hash_hex"] != authorization["authorization_tx_hash_hex"]
                or authorization_state["authorization_event_index"] != authorization["authorization_event_index"]
                or authorization_state["finalized_checkpoint_number"] != authorization["finalized_checkpoint_number"]
                or authorization_state["finalized_checkpoint_hash_hex"] != authorization["finalized_checkpoint_hash_hex"]
                or authorization_state["previous_checkpoint_hash_hex"] != authorization["previous_checkpoint_hash_hex"]
                or not uint(authorization_state["finalized_checkpoint_number"], 64, "authorization finalized checkpoint number")):
            raise DesignError("ROTATION_AUTHORIZED singleton does not commit the exact certificate, barrier, target, transaction, and finalized checkpoint")
        if (auth_msg["barrier_id_hex"] != case["barrier_id_hex"]
                or auth_msg["authority_epoch"] != resumed_epoch
                or auth_msg["target_epoch"] != resumed_epoch + 1
                or auth_msg["polygon_drained_receipt_hash_hex"] != p_drained_hash
                or auth_msg["cardano_validity_lower_ms"] != authorization_lower
                or auth_msg["cardano_validity_upper_ms"] != authorized_at
                or not auth_msg["issued_at_ms"] <= authorization_lower < authorized_at < auth_msg["expires_at_ms"]
                or auth_msg["authorized_at_ms"] != authorized_at):
            raise DesignError("ROTATION_AUTHORIZED certificate is not fresh and bound to exact current authority and drained receipt")
        activation_at = uint(activation["activation_at_ms"], 64, "rotation activation time")
        now_ms = uint(activation["now_ms"], 64, "rotation activation current time")
        authorized_at_activation = uint(activation["authorized_at_ms"], 64, "rotation authorization time")
        valid_lower = uint(activation["activation_validity_lower_ms"], 64, "rotation activation validity lower")
        valid_upper = uint(activation["activation_validity_upper_ms"], 64, "rotation activation validity upper")
        if (valid_lower >= valid_upper or valid_upper - valid_lower > contract["boundaries"]["cardano_tx_validity_interval_max_ms"]
                or valid_lower < activation_at or now_ms < valid_lower or now_ms > valid_upper
                or activation["authorization_state_hash_hex"] != authorization_state_hash
                or activation["authorization_tx_hash_hex"] != authorization["authorization_tx_hash_hex"]
                or authorized_at_activation != authorized_at):
            raise DesignError("Cardano activation is outside its bounded transaction validity interval")
        target_keys_raw = _hex(next_state["ordered_keys_hex"], 160, "rotation target ordered keys")
        if (activation["phase"] != "CARDANO_ROTATED" or activation["cardano_outbox_empty"] is not True
                or activation["polygon_drained_receipt_hash_hex"] != p_drained_hash
                or auth_msg["authority_state_hash_hex"] != (case["pause_resume"]["current_authority_state_hash_hex"] if case_index == 1 else polygon["authority_state_hash_hex"])
                or auth_msg["target_epoch"] != next_state["epoch"]
                or auth_msg["target_authority_state_hash_hex"] != hashlib.sha256(_encode_authority_state(next_state, contract)).hexdigest()
                or auth_msg["target_ordered_keys_hash_hex"] != hashlib.sha256(target_keys_raw).hexdigest()
                or auth_msg["polygon_drained_receipt_issued_at_ms"] != p_drained_msg["issued_at_ms"]
                or authorized_at < p_drained_msg["issued_at_ms"]
                or authorized_at > (2**64 - 1) - contract["authority"]["rotation_delay_ms"]
                or activation_at != authorized_at + contract["authority"]["rotation_delay_ms"]
                or auth_msg["activation_at_ms"] != activation_at
                or now_ms < activation_at):
            raise DesignError("Cardano rotation activated before bilateral drain or full delay")
        activation_state = activation["next_authority_state"]
        if activation_state != next_state:
            raise DesignError("Cardano activation installs a different target authority state")
        rotation_ready_hash, rotation_ready_msg = _verify_barrier_certificate(activation["rotation_ready_receipt"],
            barrier["rotation_ready_message_fields"], spec["rotation_ready_message_fields"],
            barrier["rotation_ready_domain_hex"], next_keys, "Cardano rotation-ready receipt", activation["now_ms"],
            contract["polygon_authority_mirror"]["freshness_max_ms"])
        if (rotation_ready_msg["barrier_id_hex"] != case["barrier_id_hex"]
                or rotation_ready_msg["authority_epoch"] != next_state["epoch"]
                or rotation_ready_msg["authority_state_hash_hex"] != hashlib.sha256(_encode_authority_state(next_state, contract)).hexdigest()
                or rotation_ready_msg["polygon_drained_receipt_hash_hex"] != p_drained_hash
                or rotation_ready_msg["rotation_authorization_hash_hex"] != authorization_state_hash
                or rotation_ready_msg["authorized_at_ms"] != authorized_at
                or rotation_ready_msg["activation_at_ms"] != activation_at):
            raise DesignError("rotation-ready receipt is not finalized under exact new authority state")
        installed = case["polygon_install"]
        exact_keys(installed, {"phase", "cardano_rotation_ready_receipt_hash_hex", "prior_mirror_frozen", "next_authority_state_hash_hex", "installed_keys_hex", "mirror_frozen_after_install", "now_ms"}, "Polygon new authority installation")
        _verify_barrier_certificate(activation["rotation_ready_receipt"], barrier["rotation_ready_message_fields"],
            spec["rotation_ready_message_fields"], barrier["rotation_ready_domain_hex"], next_keys,
            "Polygon-consumed rotation-ready receipt", installed["now_ms"],
            contract["polygon_authority_mirror"]["freshness_max_ms"])
        if (installed["phase"] != "MIRROR_SYNCED" or installed["cardano_rotation_ready_receipt_hash_hex"] != rotation_ready_hash
                or installed["prior_mirror_frozen"] is not True or installed["mirror_frozen_after_install"] is not False
                or installed["next_authority_state_hash_hex"] != rotation_ready_msg["authority_state_hash_hex"]
                or _committee_list_from_ordered_hex(installed["installed_keys_hex"], "installed Polygon mirror keys") != next_keys):
            raise DesignError("Polygon mirror released freeze without exact finalized new authority")

        pause = case["pause_resume"]
        if case_index in (0, 2):
            if pause is not None:
                raise DesignError("nominal and pre-freeze pause cases must not include post-freeze pause/resume")
        else:
            if pause is None:
                raise DesignError("second rotation barrier case must exercise pause/resume")
            exact_keys(pause, {"present", "pause_epoch", "resume_count", "barrier_id_before_hex", "barrier_id_after_hex",
                "cutoffs_before", "cutoffs_after", "watermarks_before", "watermarks_after", "economic_effect_during_pause",
                "ack_effect_checkpoint_number", "destination_cutoff_checkpoint_number", "current_authority_epoch",
                "current_authority_state_hash_hex", "current_committee_keys_hex", "reauthorized_target_keys_hex",
                "reauthorized_target_epoch", "reauthorized_target_authority_state_hash_hex",
                "rotation_authorized_at_ms", "activation_at_ms", "mirror_frozen_after_resume", "pending_record_before",
                "pending_record_after"}, "pause/resume barrier case")
            if (pause["present"] is not True or uint(pause["resume_count"], 32, "barrier resume count") < 1
                    or pause["barrier_id_before_hex"] != case["barrier_id_hex"]
                    or pause["barrier_id_after_hex"] != case["barrier_id_hex"]
                    or pause["cutoffs_before"] != pause["cutoffs_after"]
                    or pause["watermarks_before"] != pause["watermarks_after"]
                    or pause["economic_effect_during_pause"] is not False
                    or uint(pause["ack_effect_checkpoint_number"], 64, "pause ACK checkpoint") > uint(pause["destination_cutoff_checkpoint_number"], 64, "pause destination cutoff")
                    or pause["pending_record_before"] != pause["pending_record_after"]
                    or pause["current_committee_keys_hex"] != prior_keys
                    or pause["reauthorized_target_keys_hex"] != next_state["ordered_keys_hex"]
                    or uint(pause["reauthorized_target_epoch"], 64, "post-freeze reauthorized target epoch") != resumed_epoch + 1
                    or pause["reauthorized_target_epoch"] != next_state["epoch"]
                    or pause["reauthorized_target_authority_state_hash_hex"] != hashlib.sha256(_encode_authority_state(next_state, contract)).hexdigest()
                    or pause["mirror_frozen_after_resume"] is not True
                    or uint(pause["activation_at_ms"], 64, "resumed activation time") - uint(pause["rotation_authorized_at_ms"], 64, "resumed rotation authorization time") < contract["authority"]["rotation_delay_ms"]):
                raise DesignError("pause/resume clears or mutates barrier, pending action, key set, cutoff, or full delay")
            expected_cutoffs = {
                "cardano_source_cutoff": prepare["cardano_source_cutoff"],
                "cardano_destination_cutoff": prepare["cardano_destination_cutoff"],
                "polygon_source_cutoff": polygon["polygon_source_cutoff"],
                "polygon_destination_cutoff": polygon["polygon_destination_cutoff"],
            }
            expected_watermarks = {
                "cardano": prepare["cardano_stream_watermarks"],
                "polygon": polygon["polygon_stream_watermarks"],
            }
            if pause["cutoffs_before"] != expected_cutoffs or pause["watermarks_before"] != expected_watermarks:
                raise DesignError("pause/resume snapshot does not equal the committed bilateral barrier state")
            if uint(pause["current_authority_epoch"], 64, "post-pause current authority epoch") != prepare["authority_epoch"] + 2:
                raise DesignError("one pause/unpause cycle must advance authority epoch exactly twice")
            pending_record = pause["pending_record_before"]
            exact_keys(pending_record, {"action_id_hex", "source_stream_key_hex", "source_action_nonce", "payload_hash_hex",
                "effect_commitment_hex", "authority_epoch", "authority_state_hash_hex", "committee_public_keys_hex"}, "immutable pending record")
            if pending_record["committee_public_keys_hex"] != prior_keys:
                raise DesignError("pending source-time ACK snapshot changed during pause/resume")
            matching_pending = [item for item in c_initial + p_initial if item["pending"]
                               and item["pending_action_id_hex"] == pending_record["action_id_hex"]]
            if len(matching_pending) != 1:
                raise DesignError("pause/resume pending snapshot must bind exactly one frozen source outbox")
            frozen_pending = matching_pending[0]
            frozen_stream_name = stream_by_key[pending_record["source_stream_key_hex"]]
            stream_to_action = {"wrapped_escrow": "WRAPPED_CREDIT", "wrapped_burn_policy": "WRAPPED_RELEASE",
                                "polygon_slash_event": "SLASH_AGENT", "cardano_timelock_intent": "EXECUTE_INTENT"}
            pending_action = next(item for item in contract["actions"] if item["name"] == stream_to_action[frozen_stream_name])
            destination_cutoff = (prepare["cardano_destination_cutoff"] if pending_action["destination"] == "cardano_preprod"
                                  else polygon["polygon_destination_cutoff"])
            expected_destination_cutoff = destination_cutoff["checkpoint_number"]
            ack_checkpoint = uint(pause["ack_effect_checkpoint_number"], 64, "pause ACK effect checkpoint")
            supplied_destination_cutoff = uint(pause["destination_cutoff_checkpoint_number"], 64, "pause destination cutoff")
            if any([
                    pending_record["source_stream_key_hex"] != frozen_pending["source_stream_key_hex"],
                    pending_record["source_action_nonce"] != frozen_pending["source_action_nonce"],
                    pending_record["payload_hash_hex"] != frozen_pending["payload_hash_hex"],
                    pending_record["effect_commitment_hex"] != frozen_pending["effect_commitment_hex"],
                    pending_record["authority_epoch"] != prepare["authority_epoch"],
                    pending_record["authority_state_hash_hex"] != prepare["authority_state_hash_hex"],
                    supplied_destination_cutoff != expected_destination_cutoff,
                    frozen_pending["effect_commitment_hex"] != "00" * 32 and
                    (ack_checkpoint == 0 or ack_checkpoint > expected_destination_cutoff),
                    frozen_pending["effect_commitment_hex"] == "00" * 32 and ack_checkpoint != 0]):
                raise DesignError("pause/resume pending record differs from immutable source-time watermark")
            _hex(pause["current_authority_state_hash_hex"], 32, "resumed authority state hash")
            if (uint(pause["activation_at_ms"], 64, "resumed activation time")
                    != uint(pause["rotation_authorized_at_ms"], 64, "resumed rotation authorization time")
                    + contract["authority"]["rotation_delay_ms"]):
                raise DesignError("resumed authority transition must restart the exact full delay")
            if not any(step["resumed_action_certificate"] is not None for step in steps):
                raise DesignError("pause/resume fixture must contain a current-state resumed-action certificate")
        if case["expected"] != {"accepted": True, "result_code": "ACCEPT", "final_phase": "MIRROR_SYNCED"}:
            raise DesignError("rotation barrier vector must have exact MIRROR_SYNCED acceptance")


def _encode_settlement_receipt(fields: dict[str, Any], contract: dict[str, Any]) -> bytes:
    rows = contract["settlement_ack"]["message_fields"]
    expected = {name + "_hex" if name.endswith("hash") or name in {"action_id", "destination_effect_commitment"} else name for name, _ in rows}
    exact_keys(fields, expected, "settlement receipt fields")
    result = bytearray(_prefix(contract["settlement_ack"]["domain_hex"], "settlement receipt domain"))
    result.extend(_encode_typed_fields(fields, rows, "settlement receipt"))
    if len(result) != contract["settlement_ack"]["message_bytes"]:
        raise DesignError("settlement receipt length mismatch")
    return bytes(result)


def _encode_authority_state(state: dict[str, Any], contract: dict[str, Any]) -> bytes:
    rows = contract["authority_preimages"]["state_fields"]
    exact_keys(state, set(contract["vector_schema"]["authority_state_fields"]), "canonical authority state")
    encoded = bytearray(_prefix(contract["authority_preimages"]["state_domain_hex"], "authority state domain"))
    normalized = dict(state)
    normalized["key_count"] = len(state["ordered_keys_hex"]) // 64
    normalized["status"] = {"ACTIVE": 1, "PAUSED": 2}.get(state["status"], 0)
    encoded.extend(_encode_typed_fields(normalized, rows, "canonical authority state"))
    if len(encoded) != contract["authority_preimages"]["preimage_lengths"]["state"]:
        raise DesignError("canonical authority-state preimage length mismatch")
    return bytes(encoded)


def _rotation_authorized_state_hash(state: dict[str, Any], contract: dict[str, Any]) -> str:
    """Hash the canonical persisted ROTATION_AUTHORIZED singleton, excluding display metadata."""
    barrier = contract["rotation_barrier"]
    display_fields = {"phase", "state_hash_hex"}
    exact_keys(state, set(_field_hex_key(name) if name.endswith("hash") or name in {
        "barrier_id", "target_ordered_keys_hash"} else name
        for name, _ in barrier["rotation_authorized_state_fields"]) | display_fields,
        "ROTATION_AUTHORIZED singleton")
    if state["phase"] != "ROTATION_AUTHORIZED":
        raise DesignError("rotation authorization singleton has the wrong phase")
    values = {key: value for key, value in state.items() if key not in display_fields}
    preimage = (_prefix(barrier["rotation_authorized_state_domain_hex"], "rotation authorized state domain")
                + _encode_typed_fields(values, barrier["rotation_authorized_state_fields"],
                                       "ROTATION_AUTHORIZED singleton"))
    if len(preimage) != 364:
        raise DesignError("ROTATION_AUTHORIZED singleton preimage length differs")
    return hashlib.sha256(preimage).hexdigest()


def _signature_entries(keys: list[str], signers: list[str], signatures: list[str]) -> list[dict[str, str]]:
    if not isinstance(keys, list) or len(keys) != 5 or not isinstance(signers, list) or len(signers) != 3:
        raise DesignError("certificate committee/signers have wrong cardinality")
    if not isinstance(signatures, list) or len(signatures) != 3:
        raise DesignError("certificate signature count is not three")
    return [{"public_key_hex": signer, "signature_hex": signature}
            for signer, signature in zip(signers, signatures)]


def _source_stream_key(identity: dict[str, Any]) -> bytes:
    endpoint_size = {1: 20, 2: 28}.get(identity["source_chain_code"])
    if endpoint_size is None:
        raise DesignError("unsupported source endpoint domain")
    endpoint = _hex(identity["source_endpoint_hex"], endpoint_size, "source endpoint")
    return (bytes([uint(identity["source_chain_code"], 8, "source chain code")])
            + _u(identity["source_chain_id"], 8, "source chain id")
            + _u(identity["source_network_magic"], 4, "source network magic")
            + bytes([len(endpoint)]) + endpoint)


def _encode_action_effect(action: dict[str, Any], effect: dict[str, Any]) -> bytes:
    fields = action["effect_fields"]
    expected = {name + "_hex" if encoding.startswith("bytes") and not name.endswith("_hex") else name
                for name, encoding in fields}
    exact_keys(effect, expected, f"{action['name']} action effect")
    return _encode_typed_fields(effect, fields, f"{action['name']} action effect")


def _action_effect_commitment(record: dict[str, Any], action: dict[str, Any], contract: dict[str, Any]) -> bytes:
    effects = record["action_effects"]
    exact_keys(effects, set(contract["vector_schema"]["action_effect_fields"]), "action_effects")
    before = _encode_action_effect(action, effects["before"])
    after = _encode_action_effect(action, effects["after"])
    preimage = (_prefix(contract["domain_bytes"]["destination_effect"]["domain_hex"], "destination effect domain")
                + _hex(record["action_id_hex"], 32, "action ID")
                + bytes([uint(action["code"], 8, "action code")])
                + _hex(record["payload_sha256"], 32, "payload digest")
                + _u(len(before), 4, "effect-before length") + before
                + _u(len(after), 4, "effect-after length") + after)
    return hashlib.sha256(preimage).digest()


def _validate_action_effect_semantics(record: dict[str, Any], action: dict[str, Any], contract: dict[str, Any]) -> None:
    effect = record["action_effects"]
    before, after = effect["before"], effect["after"]
    payload = record["payload"]
    scale = contract["asset"]["source_units_per_wrapped_unit"]
    if action["name"] == "WRAPPED_CREDIT":
        amount = uint(payload["source_amount_base"], 128, "credit source amount")
        quantity = convert_source_amount(amount, contract)
        for state in (before, after):
            if uint(state["source_amount_base"], 128, "effect source amount") != amount or uint(state["wrapped_amount"], 64, "effect wrapped amount") != quantity:
                raise DesignError("credit action effect amount differs from signed payload")
            if state["recipient_address_hex"] != payload["destination_cardano_address_hex"]:
                raise DesignError("credit recipient differs from signed payload")
        if (uint(after["recipient_wrapped_balance"], 64, "recipient balance after")
                != uint(before["recipient_wrapped_balance"], 64, "recipient balance before") + quantity):
            raise DesignError("credit recipient balance does not increase by exact wrapped quantity")
        if (uint(after["source_liability_base"], 128, "liability after")
                != uint(before["source_liability_base"], 128, "liability before")):
            raise DesignError("credit destination stage may not apply source liability twice")
        if (uint(after["actual_escrow_balance_base"], 128, "actual escrow after")
                != uint(before["actual_escrow_balance_base"], 128, "actual escrow before")):
            raise DesignError("credit destination stage may not repeat the source escrow transfer")
        if after["actual_escrow_balance_base"] < after["source_liability_base"]:
            raise DesignError("credit leaves escrow under-backed")
    elif action["name"] == "WRAPPED_RELEASE":
        quantity = uint(payload["wrapped_amount"], 64, "release wrapped amount")
        amount = quantity * scale
        for state in (before, after):
            if (uint(state["wrapped_amount"], 64, "effect wrapped amount") != quantity
                    or uint(state["source_amount_base"], 128, "effect source amount") != amount
                    or state["credit_action_id_hex"] != payload["credit_action_id_hex"]
                    or state["destination_address_hex"] != payload["destination_polygon_address_hex"]):
                raise DesignError("release effect differs from signed burn/recipient payload")
        if (uint(after["escrow_liability_base"], 128, "release liability after")
                != uint(before["escrow_liability_base"], 128, "release liability before") - amount):
            raise DesignError("release liability does not decrease by exact source amount")
        if (uint(after["actual_escrow_balance_base"], 128, "release actual balance after")
                != uint(before["actual_escrow_balance_base"], 128, "release actual balance before") - amount):
            raise DesignError("release transfer does not decrease actual escrow by exact amount")
        if (uint(after["recipient_vams_balance_base"], 128, "recipient VAMS after")
                != uint(before["recipient_vams_balance_base"], 128, "recipient VAMS before") + amount):
            raise DesignError("release recipient does not receive exact source amount")
        if after["actual_escrow_balance_base"] < after["escrow_liability_base"]:
            raise DesignError("release leaves escrow under-backed")
    elif action["name"] == "SLASH_AGENT":
        amount = uint(payload["slash_amount_lovelace"], 64, "slash amount")
        for state in (before, after):
            if (state["identity_policy_id_hex"] != payload["identity_policy_id_hex"]
                    or state["identity_asset_name_hex"] != payload["identity_asset_name_hex"]
                    or state["authorized_slasher_hex"] == "00" * 28):
                raise DesignError("slash effect identity or authorized slasher is invalid")
        if (uint(after["agent_nonce"], 64, "agent nonce after")
                != uint(before["agent_nonce"], 64, "agent nonce before") + 1
                or uint(before["agent_nonce"], 64, "agent nonce before") != payload["expected_agent_nonce"]):
            raise DesignError("slash identity nonce does not advance exactly once")
        if (uint(after["stake_lovelace"], 64, "stake after")
                != uint(before["stake_lovelace"], 64, "stake before") - amount
                or after["stake_lovelace"] < contract["slash_reserve"]["agent_stake_minimum_lovelace"]):
            raise DesignError("slash does not preserve the exact minimum-stake transition")
        if (uint(after["slash_reserve_lovelace"], 64, "slash reserve after")
                != uint(before["slash_reserve_lovelace"], 64, "slash reserve before") + amount
                or after["slash_reserve_lovelace"] > contract["slash_reserve"]["balance_cap"]):
            raise DesignError("slash reserve does not receive the exact capped amount")
    elif action["name"] == "EXECUTE_INTENT":
        fixture = contract["executor_registry"]["test_only_mapping"]
        mapping_target_domain = bytes.fromhex(fixture["target_domain_hex"])
        supplied_target_domain = bytes.fromhex(payload["target_domain_hex"])
        identity = record["identity_fields"]
        if ((identity["destination_chain_code"], identity["destination_chain_id"], identity["destination_network_magic"])
                != (fixture["destination_chain_code"], fixture["destination_chain_id"], fixture["destination_network_magic"])):
            raise DesignError("intent executor has no exact destination-chain registry entry")
        if supplied_target_domain != mapping_target_domain or action["code"] != fixture["action_code"]:
            raise DesignError("intent target domain or action has no exact registry entry")
        for state in (before, after):
            for effect_key, payload_key in (("intent_id_hex", "intent_id_hex"), ("action_hash_hex", "action_hash_hex"),
                                             ("payload_hash_hex", "payload_hash_hex")):
                if state[effect_key] != payload[payload_key]:
                    raise DesignError("intent effect is not bound to signed intent/payload")
            if uint(state["policy_epoch"], 64, "intent effect epoch") != payload["policy_epoch"]:
                raise DesignError("intent effect policy epoch differs from signed payload")
            if (state["executor_target_hex"] != fixture["executor_target_hex"]
                    or state["executor_selector_hex"] != fixture["executor_selector_hex"]):
                raise DesignError("intent target or selector differs from the exact registry entry")
        if before["intent_status"] != "QUEUED" or after["intent_status"] != "EXECUTED":
            raise DesignError("intent is not terminally consumed by the successful destination stage")
        executor_preimage = (
            _prefix(contract["domain_bytes"]["executor_call"]["domain_hex"], "executor call domain")
            + bytes([fixture["destination_chain_code"]])
            + _u(fixture["destination_chain_id"], 8, "executor chain ID")
            + _u(fixture["destination_network_magic"], 4, "executor network magic")
            + bytes([len(supplied_target_domain)]) + supplied_target_domain
            + bytes.fromhex(fixture["executor_target_hex"])
            + bytes.fromhex(fixture["executor_selector_hex"])
            + bytes([action["code"]])
            + bytes.fromhex(payload["intent_id_hex"])
            + bytes.fromhex(payload["action_hash_hex"])
            + bytes.fromhex(payload["payload_hash_hex"])
            + _u(payload["policy_epoch"], 8, "intent policy epoch")
            + _u(payload["intent_nonce"], 8, "intent nonce")
        )
        if after["executor_effect_hash_hex"] != hashlib.sha256(executor_preimage).hexdigest():
            raise DesignError("intent executor effect hash does not match the canonical registry-bound call")
    else:
        raise DesignError("unsupported action effect schema")


def cursor_accepts(cursor: dict[str, Any], cert: dict[str, Any]) -> bool:
    try:
        for obj, field in ((cursor, "checkpoint_number"), (cert, "source_event_block_number"),
                           (cert, "finalized_checkpoint_number"), (cert, "source_action_nonce"),
                           (cursor, "source_action_nonce")):
            uint(obj[field], 64, field)
        if cert["source_event_block_number"] > cert["finalized_checkpoint_number"]:
            return False
        height = cert["finalized_checkpoint_number"]
        if height < cursor["checkpoint_number"]:
            return False
        if height == cursor["checkpoint_number"]:
            if (cert["finalized_checkpoint_hash_hex"] != cursor["checkpoint_hash_hex"]
                    or cert["previous_certified_checkpoint_hash_hex"] != cursor["previous_checkpoint_hash_hex"]):
                return False
        elif cert["previous_certified_checkpoint_hash_hex"] != cursor["checkpoint_hash_hex"]:
            return False
        if cursor["source_action_nonce"] == (1 << 64) - 1:
            return False
        return cert["source_action_nonce"] == cursor["source_action_nonce"] + 1
    except (DesignError, KeyError, TypeError):
        return False


def verify_signatures(keys_hex: list[str], message: bytes,
                      signatures: list[dict[str, str]]) -> bool:
    """Verify exactly three sorted distinct current committee signatures."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        if not isinstance(keys_hex, list) or not isinstance(signatures, list):
            return False
        keys = [_hex(item, 32, "committee public key") for item in keys_hex]
        if len(keys) != 5 or len(set(keys)) != 5 or keys != sorted(keys):
            return False
        if len(signatures) != 3:
            return False
        signers: list[bytes] = []
        decoded: list[bytes] = []
        for item in signatures:
            exact_keys(item, {"public_key_hex", "signature_hex"}, "signature entry")
            signers.append(_hex(item["public_key_hex"], 32, "signer key"))
            decoded.append(_hex(item["signature_hex"], 64, "signature"))
        if len(set(signers)) != 3 or signers != sorted(signers) or any(key not in keys for key in signers):
            return False
        for key, signature in zip(signers, decoded):
            Ed25519PublicKey.from_public_bytes(key).verify(signature, message)
        return True
    except (ValueError, KeyError, TypeError, DesignError, InvalidSignature):
        return False


def _committee_signature_records(certificate: dict[str, Any]) -> list[dict[str, str]]:
    keys = certificate["committee_public_keys_hex"]
    signers = certificate["signer_ids"]
    signatures = certificate["signatures_hex"]
    if (not isinstance(keys, list) or len(keys) != 5 or not isinstance(signers, list)
            or len(signers) != 3 or not isinstance(signatures, list) or len(signatures) != 3):
        raise DesignError("committee certificate requires five keys and three signer signatures")
    raw_keys = [_hex(key, 32, "committee key") for key in keys]
    if raw_keys != sorted(raw_keys) or len(set(raw_keys)) != 5:
        raise DesignError("committee keys must be five distinct sorted raw keys")
    if any(isinstance(signer, bool) or not isinstance(signer, int) or not 0 <= signer < 5 for signer in signers):
        raise DesignError("signer IDs must be committee indexes in 0..4")
    if signers != sorted(set(signers)):
        raise DesignError("signer IDs must be unique and sorted")
    return [{"public_key_hex": keys[signer], "signature_hex": signature}
            for signer, signature in zip(signers, signatures)]


def _validate_v3_state(state: dict[str, Any], contract: dict[str, Any]) -> None:
    spec = contract["vector_schema"]
    exact_keys(state, set(spec["state_fields"]), "state snapshot")
    exact_keys(state["global"], set(spec["global_state_fields"]), "global state")
    exact_keys(state["source_stream"], set(spec["stream_state_fields"]), "source stream")
    exact_keys(state["source_chain_checkpoint"], set(spec["checkpoint_state_fields"]), "source checkpoint")
    exact_keys(state["destination_chain_checkpoint"], set(spec["checkpoint_state_fields"]), "destination checkpoint")
    exact_keys(state["source_outbox"], set(spec["outbox_state_fields"]), "source outbox")
    exact_keys(state["destination_replay"], set(spec["destination_replay_fields"]), "destination replay")
    global_state = state["global"]
    for key in ("current_locked_source_balance_base", "actual_escrow_token_balance_base", "pending_credit_base", "pending_release_base"):
        uint(global_state[key], 128, key)
    for key in ("minted", "burned", "outstanding", "slash_reserve_lovelace"):
        uint(global_state[key], 64, key)
    if global_state["burned"] > global_state["minted"] or global_state["outstanding"] != global_state["minted"] - global_state["burned"]:
        raise DesignError("global wrapped counters violate minted/burned equation")
    if global_state["current_locked_source_balance_base"] > contract["asset"]["source_balance_cap"]:
        raise DesignError("global tracked source liability exceeds cap")
    if global_state["actual_escrow_token_balance_base"] < global_state["current_locked_source_balance_base"]:
        raise DesignError("actual source escrow is below protocol-accounted liability")
    if global_state["slash_reserve_lovelace"] > contract["slash_reserve"]["balance_cap"]:
        raise DesignError("slash reserve exceeds checked cap")
    stream = state["source_stream"]
    for key, bits in (("chain_code", 8), ("chain_id", 64), ("network_magic", 32), ("nonce", 64)):
        uint(stream[key], bits, f"source stream {key}")
    endpoint_size = {1:20, 2:28}.get(stream["chain_code"])
    if endpoint_size is None:
        raise DesignError("source stream has an unsupported chain domain")
    _hex(stream["endpoint_hex"], endpoint_size, "source endpoint")
    expected_network = next((n for n in contract["networks"].values() if n["chain_code"] == stream["chain_code"]), None)
    if expected_network is None or (stream["chain_id"], stream["network_magic"]) != (expected_network["chain_id"], expected_network["network_magic"]):
        raise DesignError("source stream is not a configured chain domain")
    for name in ("source_chain_checkpoint", "destination_chain_checkpoint"):
        checkpoint = state[name]
        for key, bits in (("chain_code", 8), ("chain_id", 64), ("network_magic", 32), ("checkpoint_number", 64)):
            uint(checkpoint[key], bits, f"{name}.{key}")
        _hex(checkpoint["checkpoint_hash_hex"], 32, f"{name}.checkpoint_hash")
        _hex(checkpoint["previous_checkpoint_hash_hex"], 32, f"{name}.previous_checkpoint_hash")
        configured = next((n for n in contract["networks"].values() if n["chain_code"] == checkpoint["chain_code"]), None)
        if configured is None or (checkpoint["chain_id"], checkpoint["network_magic"]) != (configured["chain_id"], configured["network_magic"]):
            raise DesignError(f"{name} is not a configured chain domain")
    outbox = state["source_outbox"]
    pending = outbox["pending_records"]
    if not isinstance(pending, list) or len(pending) > 4:
        raise DesignError("source outbox exceeds the four deployment-bound streams")
    if not isinstance(outbox["last_settled_by_source_stream"], list) or len(outbox["last_settled_by_source_stream"]) > 4:
        raise DesignError("last-settled tombstones exceed the four deployment-bound streams")
    settled_streams: set[str] = set()
    for settled in outbox["last_settled_by_source_stream"]:
        exact_keys(settled, {"source_stream_key_hex", "last_settled_action_id_hex"}, "last-settled stream record")
        _hex(settled["source_stream_key_hex"], len(settled["source_stream_key_hex"]) // 2, "last-settled source stream")
        _hex(settled["last_settled_action_id_hex"], 32, "last-settled action ID")
        if settled["source_stream_key_hex"] in settled_streams:
            raise DesignError("duplicate last-settled record for a source stream")
        settled_streams.add(settled["source_stream_key_hex"])
    if [item["source_stream_key_hex"] for item in outbox["last_settled_by_source_stream"]] != sorted(settled_streams):
        raise DesignError("last-settled records must be sorted by source stream key")
    replay = state["destination_replay"]["latest_by_source_stream"]
    if not isinstance(replay, list) or len(replay) > 4:
        raise DesignError("destination replay tombstone exceeds the four fixed streams")
    replay_streams: set[str] = set()
    for entry in replay:
        exact_keys(entry, {"source_stream_key_hex", "source_action_nonce", "action_id_hex", "effect_commitment_hex"}, "destination tombstone")
        _hex(entry["source_stream_key_hex"], len(entry["source_stream_key_hex"]) // 2, "tombstone source stream")
        uint(entry["source_action_nonce"], 64, "tombstone nonce")
        _hex(entry["action_id_hex"], 32, "tombstone action ID")
        _hex(entry["effect_commitment_hex"], 32, "tombstone effect commitment")
        if entry["source_stream_key_hex"] in replay_streams:
            raise DesignError("duplicate destination tombstone for a source stream")
        replay_streams.add(entry["source_stream_key_hex"])
    pending_streams: set[str] = set()
    pending_credit = pending_release = 0
    for entry in pending:
        exact_keys(entry, set(spec["pending_record_fields"]), "pending outbox record")
        _hex(entry["action_id_hex"], 32, "pending action ID")
        _hex(entry["source_stream_key_hex"], len(entry["source_stream_key_hex"]) // 2, "pending source stream")
        _hex(entry["source_transaction_id_hex"], 32, "pending source transaction")
        _hex(entry["effect_commitment_hex"], 32, "pending effect commitment")
        uint(entry["source_action_nonce"], 64, "pending nonce")
        uint(entry["source_amount_base"], 128, "pending source amount")
        uint(entry["wrapped_amount"], 64, "pending wrapped amount")
        uint(entry["authority_epoch"], 64, "pending authority epoch")
        _hex(entry["authority_state_hash_hex"], 32, "pending authority state hash")
        committee_bytes = _hex(entry["committee_public_keys_hex"], 160, "pending authority committee keys")
        pending_keys = [committee_bytes[i:i + 32] for i in range(0, 160, 32)]
        if pending_keys != sorted(pending_keys) or len(set(pending_keys)) != 5:
            raise DesignError("pending authority keys must be five distinct sorted keys")
        if entry["action_kind"] not in contract["checkpoint_and_replay"]["pending_record_schema"]["action_kinds"] or entry["status"] not in contract["checkpoint_and_replay"]["pending_record_schema"]["statuses"]:
            raise DesignError("pending record has an unknown kind or status")
        raw_stream = bytes.fromhex(entry["source_stream_key_hex"])
        if len(raw_stream) not in (34, 42) or raw_stream[13] not in (20, 28) or len(raw_stream) != 14 + raw_stream[13]:
            raise DesignError("pending record has an ambiguous source stream key")
        if entry["source_stream_key_hex"] in pending_streams:
            raise DesignError("more than one pending record exists for a source stream")
        pending_streams.add(entry["source_stream_key_hex"])
        expected_status = {"WRAPPED_CREDIT":"PENDING_CREDIT","WRAPPED_RELEASE":"PENDING_RELEASE","SLASH_AGENT":"PENDING_SLASH","EXECUTE_INTENT":"PENDING_EXECUTE_INTENT"}[entry["action_kind"]]
        if entry["status"] not in {expected_status,"DESTINATION_FINALIZED"}:
            raise DesignError("pending action kind and status disagree")
        if entry["status"] == expected_status and entry["effect_commitment_hex"] != "00" * 32:
            raise DesignError("source-chain pending record cannot claim a destination effect")
        if entry["status"] == "DESTINATION_FINALIZED":
            matching = [t for t in replay if t["source_stream_key_hex"] == entry["source_stream_key_hex"]
                        and t["source_action_nonce"] == entry["source_action_nonce"]
                        and t["action_id_hex"] == entry["action_id_hex"]
                        and t["effect_commitment_hex"] == entry["effect_commitment_hex"]]
            if len(matching) != 1:
                raise DesignError("finalized projection lacks an exact matching destination tombstone")
        elif any(t["source_stream_key_hex"] == entry["source_stream_key_hex"]
                 and t["source_action_nonce"] == entry["source_action_nonce"]
                 and t["action_id_hex"] == entry["action_id_hex"] for t in replay):
            raise DesignError("pending projection already has a matching destination tombstone")
        if entry["action_kind"] == "WRAPPED_CREDIT":
            if entry["source_amount_base"] == 0 or entry["source_amount_base"] % contract["asset"]["source_units_per_wrapped_unit"] or entry["wrapped_amount"] != entry["source_amount_base"] // contract["asset"]["source_units_per_wrapped_unit"]:
                raise DesignError("pending credit record has invalid amount/status")
            if entry["status"] == "PENDING_CREDIT": pending_credit += entry["source_amount_base"]
        elif entry["action_kind"] == "WRAPPED_RELEASE":
            if entry["wrapped_amount"] == 0 or entry["source_amount_base"] != entry["wrapped_amount"] * contract["asset"]["source_units_per_wrapped_unit"]:
                raise DesignError("pending release record has invalid amount/status")
            if entry["status"] == "PENDING_RELEASE": pending_release += entry["source_amount_base"]
        elif entry["source_amount_base"] != 0 or entry["wrapped_amount"] != 0:
            raise DesignError("slash/intent pending records cannot enter wrapped backing")
    if [item["source_stream_key_hex"] for item in pending] != sorted(pending_streams):
        raise DesignError("pending records must be sorted by source stream key")
    if (pending_credit, pending_release) != (global_state["pending_credit_base"],global_state["pending_release_base"]):
        raise DesignError("global pending backing totals do not match all four source outboxes")
    scale = contract["asset"]["source_units_per_wrapped_unit"]
    expected_liability = (global_state["minted"] - global_state["burned"]) * scale + pending_credit + pending_release
    if global_state["current_locked_source_balance_base"] != expected_liability:
        raise DesignError("global source-liability backing equation fails")


def _validate_stage_progression(record: dict[str, Any], action: dict[str, Any], contract: dict[str, Any], effect_hash: str) -> None:
    snapshots = [record[name] for name in ("state_before", "state_after_source", "state_after_destination", "state_after")]
    for snapshot in snapshots:
        _validate_v3_state(snapshot, contract)
    before, source, destination, final = snapshots
    stream_key = (bytes([record["identity_fields"]["source_chain_code"]])
                  + _u(record["identity_fields"]["source_chain_id"], 8, "source chain id")
                  + _u(record["identity_fields"]["source_network_magic"], 4, "source network magic")
                  + bytes([len(bytes.fromhex(record["identity_fields"]["source_endpoint_hex"]))])
                  + bytes.fromhex(record["identity_fields"]["source_endpoint_hex"])).hex()
    nonce = uint(record["certificate"]["message_fields"]["source_action_nonce"], 64, "action nonce")
    for snapshot in snapshots:
        stream = snapshot["source_stream"]
        if ((stream["chain_code"],stream["chain_id"],stream["network_magic"],stream["endpoint_hex"])
                != (record["identity_fields"]["source_chain_code"],record["identity_fields"]["source_chain_id"],record["identity_fields"]["source_network_magic"],record["identity_fields"]["source_endpoint_hex"])):
            raise DesignError("snapshot source cursor is not the exact action stream")
        expected_source_chain = contract["networks"][action["source"]]
        expected_destination_chain = contract["networks"][action["destination"]]
        for key, expected in (("source_chain_checkpoint", expected_source_chain),
                              ("destination_chain_checkpoint", expected_destination_chain)):
            checkpoint = snapshot[key]
            if (checkpoint["chain_code"],checkpoint["chain_id"],checkpoint["network_magic"]) != (expected["chain_code"],expected["chain_id"],expected["network_magic"]):
                raise DesignError(f"{key} is assigned to the wrong configured chain")
    if before["source_stream"]["nonce"] + 1 != nonce or source["source_stream"]["nonce"] != nonce:
        raise DesignError("source stage must commit exactly the next stream nonce")
    if destination["source_stream"] != source["source_stream"] or final["source_stream"] != source["source_stream"]:
        raise DesignError("destination and ACK stages may not alter the source nonce")
    payload = record["payload"]
    scale = contract["asset"]["source_units_per_wrapped_unit"]
    if action["name"] == "WRAPPED_CREDIT":
        pending_source_amount = uint(payload["source_amount_base"], 128, "credit source amount")
        pending_wrapped_amount = convert_source_amount(pending_source_amount, contract)
    elif action["name"] == "WRAPPED_RELEASE":
        pending_wrapped_amount = uint(payload["wrapped_amount"], 64, "release wrapped amount")
        pending_source_amount = pending_wrapped_amount * scale
        uint(pending_source_amount, 128, "release source liability")
    else:
        pending_source_amount = 0
        pending_wrapped_amount = 0
    expected_pending = {"action_id_hex":record["action_id_hex"], "source_stream_key_hex":stream_key,
        "source_action_nonce":nonce, "action_kind":action["name"],
        "source_amount_base":pending_source_amount,
        "wrapped_amount":pending_wrapped_amount,
        "source_transaction_id_hex":record["identity_fields"]["event_transaction_hash_hex"],
        "effect_commitment_hex":"00" * 32,
        "status":{"WRAPPED_CREDIT":"PENDING_CREDIT","WRAPPED_RELEASE":"PENDING_RELEASE","SLASH_AGENT":"PENDING_SLASH","EXECUTE_INTENT":"PENDING_EXECUTE_INTENT"}[action["name"]],
        "authority_epoch":record["certificate"]["epoch"],
        "authority_state_hash_hex":record["certificate"]["message_fields"]["authority_state_hash_hex"],
        "committee_public_keys_hex":"".join(record["certificate"]["committee_public_keys_hex"])}
    prior_pending = before["source_outbox"]["pending_records"]
    if any(entry["source_stream_key_hex"] == stream_key for entry in prior_pending):
        raise DesignError("source stream already has an outstanding action")
    expected_source_pending = sorted(prior_pending + [expected_pending], key=lambda item: item["source_stream_key_hex"])
    if source["source_outbox"]["pending_records"] != expected_source_pending:
        raise DesignError("source action must add one exact outbox record while preserving other streams")
    expected_projected = [dict(item) for item in expected_source_pending]
    target_record = next(item for item in expected_projected if item["source_stream_key_hex"] == stream_key)
    target_record["status"] = "DESTINATION_FINALIZED"
    target_record["effect_commitment_hex"] = effect_hash
    if destination["source_outbox"]["pending_records"] != expected_projected:
        raise DesignError("destination finality must change only the derived projection status")
    if final["source_outbox"]["pending_records"] != [entry for entry in expected_source_pending if entry["source_stream_key_hex"] != stream_key]:
        raise DesignError("ACK stage must clear only the exact stream's pending action")
    prior_settled = before["source_outbox"]["last_settled_by_source_stream"]
    source_settled = source["source_outbox"]["last_settled_by_source_stream"]
    if source_settled != prior_settled or destination["source_outbox"]["last_settled_by_source_stream"] != prior_settled:
        raise DesignError("source and destination stages may not change settled tombstones")
    expected_settled = sorted([entry for entry in prior_settled if entry["source_stream_key_hex"] != stream_key]
                              + [{"source_stream_key_hex":stream_key,"last_settled_action_id_hex":record["action_id_hex"]}],
                              key=lambda item: item["source_stream_key_hex"])
    if final["source_outbox"]["last_settled_by_source_stream"] != expected_settled:
        raise DesignError("ACK must advance the exact stream's bounded last-settled action tombstone")
    if before["destination_replay"] != source["destination_replay"] or destination["destination_replay"] == source["destination_replay"]:
        raise DesignError("only destination stage may advance destination replay")
    cert_message = record["certificate"]["message_fields"]
    source_checkpoint_before = before["source_chain_checkpoint"]
    source_checkpoint_after = destination["source_chain_checkpoint"]
    source_height = uint(cert_message["finalized_checkpoint_number"], 64, "source finalized checkpoint")
    if source_height < source_checkpoint_before["checkpoint_number"]:
        raise DesignError("source certified checkpoint regresses")
    if source_height == source_checkpoint_before["checkpoint_number"]:
        source_link_ok = (cert_message["finalized_checkpoint_hash_hex"] == source_checkpoint_before["checkpoint_hash_hex"]
                          and cert_message["previous_certified_checkpoint_hash_hex"] == source_checkpoint_before["previous_checkpoint_hash_hex"])
    else:
        source_link_ok = cert_message["previous_certified_checkpoint_hash_hex"] == source_checkpoint_before["checkpoint_hash_hex"]
    if (not source_link_ok
            or source_checkpoint_after["checkpoint_number"] != cert_message["finalized_checkpoint_number"]
            or source_checkpoint_after["checkpoint_hash_hex"] != cert_message["finalized_checkpoint_hash_hex"]
            or source_checkpoint_after["previous_checkpoint_hash_hex"] != cert_message["previous_certified_checkpoint_hash_hex"]):
        raise DesignError("destination ledger remote-source checkpoint does not advance from the certified predecessor")
    if (source["source_chain_checkpoint"] != before["source_chain_checkpoint"]
            or source["destination_chain_checkpoint"] != before["destination_chain_checkpoint"]):
        raise DesignError("source action transaction may not advance a finality cursor")
    if destination["destination_chain_checkpoint"] != source["destination_chain_checkpoint"]:
        raise DesignError("destination effect transaction may not advance its own-chain finality cursor")
    if final["source_chain_checkpoint"] != destination["source_chain_checkpoint"]:
        raise DesignError("source ACK may not rewrite the destination ledger remote-source cursor")
    destination_checkpoint_before = before["destination_chain_checkpoint"]
    destination_checkpoint_after = final["destination_chain_checkpoint"]
    receipt_message = record["transaction"]["ack"]["receipt"]["message_fields"]
    receipt_height = uint(receipt_message["destination_checkpoint_number"], 64, "destination finalized checkpoint")
    if receipt_height < destination_checkpoint_before["checkpoint_number"]:
        raise DesignError("destination finalized checkpoint regresses")
    if receipt_height == destination_checkpoint_before["checkpoint_number"]:
        destination_link_ok = (receipt_message["destination_checkpoint_hash_hex"] == destination_checkpoint_before["checkpoint_hash_hex"]
                               and receipt_message["previous_destination_checkpoint_hash_hex"] == destination_checkpoint_before["previous_checkpoint_hash_hex"])
    else:
        destination_link_ok = receipt_message["previous_destination_checkpoint_hash_hex"] == destination_checkpoint_before["checkpoint_hash_hex"]
    if (not destination_link_ok
            or destination_checkpoint_after["checkpoint_number"] != receipt_message["destination_checkpoint_number"]
            or destination_checkpoint_after["checkpoint_hash_hex"] != receipt_message["destination_checkpoint_hash_hex"]
            or destination_checkpoint_after["previous_checkpoint_hash_hex"] != receipt_message["previous_destination_checkpoint_hash_hex"]):
        raise DesignError("source ACK remote-destination checkpoint does not advance from its shared predecessor")
    dest_tombstones = destination["destination_replay"]["latest_by_source_stream"]
    expected_tombstone = {"source_stream_key_hex":stream_key,"source_action_nonce":nonce,
                          "action_id_hex":record["action_id_hex"],"effect_commitment_hex":effect_hash}
    if expected_tombstone not in dest_tombstones or final["destination_replay"] != destination["destination_replay"]:
        raise DesignError("destination tombstone must bind exact stream, nonce, action and effect through ACK")
    prior_tombstones = before["destination_replay"]["latest_by_source_stream"]
    expected_prior = [entry for entry in prior_tombstones if entry["source_stream_key_hex"] != stream_key]
    if dest_tombstones != sorted(expected_prior + [expected_tombstone], key=lambda item: item["source_stream_key_hex"]):
        raise DesignError("destination must replace only this stream tombstone and preserve other streams")
    if final["global"] != destination["global"]:
        raise DesignError("ACK stage may not modify destination economic state")
    if final["source_stream"] != destination["source_stream"]:
        raise DesignError("ACK may not alter stream nonce")
    final_source_cp, dest_source_cp = final["source_chain_checkpoint"], destination["source_chain_checkpoint"]
    final_source_height = final_source_cp["checkpoint_number"]
    if final_source_height < dest_source_cp["checkpoint_number"]:
        raise DesignError("ACK source checkpoint regresses")
    if final_source_height == dest_source_cp["checkpoint_number"]:
        if final_source_cp != dest_source_cp:
            raise DesignError("same-height ACK checkpoint must be identical")
    elif final_source_cp["previous_checkpoint_hash_hex"] != dest_source_cp["checkpoint_hash_hex"]:
        raise DesignError("ACK checkpoint must link to the prior shared source checkpoint")
    b, s, d, f = (snapshot["global"] for snapshot in snapshots)
    amount = record["payload"].get("source_amount_base", 0)
    quantity = record["payload"].get("wrapped_amount", 0)
    if action["name"] == "WRAPPED_CREDIT":
        quantity = convert_source_amount(amount, contract)
        if (s["current_locked_source_balance_base"] != b["current_locked_source_balance_base"] + amount
                or s["actual_escrow_token_balance_base"] != b["actual_escrow_token_balance_base"] + amount
                or (s["minted"],s["burned"],s["outstanding"],s["slash_reserve_lovelace"]) != (b["minted"],b["burned"],b["outstanding"],b["slash_reserve_lovelace"])):
            raise DesignError("credit source stage must lock exact source amount and liability")
        if (d["minted"] != s["minted"] + quantity or d["outstanding"] != s["outstanding"] + quantity
                or d["burned"] != s["burned"] or d["current_locked_source_balance_base"] != s["current_locked_source_balance_base"]
                or d["actual_escrow_token_balance_base"] != s["actual_escrow_token_balance_base"]
                or d["slash_reserve_lovelace"] != s["slash_reserve_lovelace"]):
            raise DesignError("credit destination stage must mint exact wrapped amount without changing source escrow")
        if (s["pending_credit_base"] != b["pending_credit_base"] + amount
                or d["pending_credit_base"] != s["pending_credit_base"] - amount
                or d["pending_release_base"] != s["pending_release_base"]):
            raise DesignError("credit pending backing must open at source and clear only at destination mint")
    elif action["name"] == "WRAPPED_RELEASE":
        amount = quantity * contract["asset"]["source_units_per_wrapped_unit"]
        if (s["burned"] != b["burned"] + quantity or s["outstanding"] != b["outstanding"] - quantity
                or s["minted"] != b["minted"] or s["current_locked_source_balance_base"] != b["current_locked_source_balance_base"]
                or s["actual_escrow_token_balance_base"] != b["actual_escrow_token_balance_base"]
                or s["slash_reserve_lovelace"] != b["slash_reserve_lovelace"]):
            raise DesignError("release source stage must burn exact wrapped amount without changing source escrow")
        if (d["current_locked_source_balance_base"] != s["current_locked_source_balance_base"] - amount
                or d["actual_escrow_token_balance_base"] != s["actual_escrow_token_balance_base"] - amount
                or (d["minted"],d["burned"],d["outstanding"],d["slash_reserve_lovelace"]) != (s["minted"],s["burned"],s["outstanding"],s["slash_reserve_lovelace"])):
            raise DesignError("release destination stage must transfer exact source amount and reduce tracked liability")
        if (s["pending_release_base"] != b["pending_release_base"] + amount
                or d["pending_release_base"] != s["pending_release_base"] - amount
                or d["pending_credit_base"] != s["pending_credit_base"]):
            raise DesignError("release pending entitlement must open at source burn and clear only at destination transfer")
    elif action["name"] == "SLASH_AGENT":
        slash = record["payload"]["slash_amount_lovelace"]
        if b != s or (d["current_locked_source_balance_base"],d["actual_escrow_token_balance_base"],d["minted"],d["burned"],d["outstanding"]) != (s["current_locked_source_balance_base"],s["actual_escrow_token_balance_base"],s["minted"],s["burned"],s["outstanding"]) or d["slash_reserve_lovelace"] != s["slash_reserve_lovelace"] + slash:
            raise DesignError("slash must change only destination slash reserve by the exact amount")
    elif action["name"] == "EXECUTE_INTENT":
        if b != s or s != d:
            raise DesignError("intent source/destination stages may not change global economic accounting")
    if f != d:
        raise DesignError("ACK stage must be non-economic")
    counter_changes = record["counter_changes"]
    exact_keys(counter_changes, set(contract["vector_schema"]["counter_change_fields"]), "counter changes")
    for key in ("minted", "burned", "outstanding"):
        delta = d[key] - b[key]
        if isinstance(counter_changes[key], bool) or not isinstance(counter_changes[key], int) or counter_changes[key] != delta:
            raise DesignError("counter change does not equal cross-stage global transition")
    if counter_changes["outstanding"] != counter_changes["minted"] - counter_changes["burned"]:
        raise DesignError("counter change equation fails")
    for stage_name, snapshot, checkpoint_name, chain_name in (
            ("destination effect", destination, "source_chain_checkpoint", action["source"]),
            ("source ACK", final, "destination_chain_checkpoint", action["destination"])):
        chain_checkpoint = snapshot[checkpoint_name]
        expected_chain = contract["networks"][chain_name]
        if (chain_checkpoint["chain_code"],chain_checkpoint["chain_id"],chain_checkpoint["network_magic"]) != (expected_chain["chain_code"],expected_chain["chain_id"],expected_chain["network_magic"]):
            raise DesignError(f"{stage_name} remote checkpoint is not for its action chain")
    receipt_fields = record["transaction"]["ack"]["receipt"]["message_fields"]
    dest_checkpoint = final["destination_chain_checkpoint"]
    if (receipt_fields["destination_checkpoint_number"] != dest_checkpoint["checkpoint_number"]
            or receipt_fields["destination_checkpoint_hash_hex"] != dest_checkpoint["checkpoint_hash_hex"]
            or receipt_fields["previous_destination_checkpoint_hash_hex"] != dest_checkpoint["previous_checkpoint_hash_hex"]):
        raise DesignError("settlement receipt checkpoint differs from source ACK remote-destination cursor")


def validate_vectors(vectors: dict[str, Any], contract: dict[str, Any]) -> None:
    """Validate v4 canonical vectors, authority, and the bilateral rotation barrier."""
    spec = contract["vector_schema"]
    exact_keys(vectors, set(spec["root_fields"]), "vectors")
    if uint(vectors["schema_version"], 32, "vector schema version") != 4 or vectors["specification_id"] != "F05.1-R4":
        raise DesignError("vectors target the wrong specification")
    records = vectors["action_vectors"]
    if not isinstance(records, list) or len(records) != 4:
        raise DesignError("v4 vectors require exactly four positive action fixtures")
    _validate_rotation_cases(vectors["rotation_cases"], spec, contract)
    payload_keys = [
        ["source_escrow_address_hex","source_action_nonce","source_amount_base","destination_cardano_address_hex"],
        ["burn_transaction_hash_hex","burn_event_index","source_action_nonce","wrapped_amount","credit_action_id_hex","destination_polygon_address_hex"],
        ["identity_policy_id_hex","identity_asset_name_hex","evidence_hash_hex","slash_amount_lovelace","expected_agent_nonce","expected_action_epoch"],
        ["intent_transaction_hash_hex","intent_output_index","intent_id_hex","action_hash_hex","payload_hash_hex","target_domain_hex","policy_epoch","intent_nonce","queue_time_ms","execute_after_ms","lifetime_ms","proposer_vkh_hex"]]
    seen: set[str] = set()
    for index, (record, action) in enumerate(zip(records, contract["actions"])):
        exact_keys(record, set(spec["action_vector_fields"]), f"action_vectors[{index}]")
        if (record["action_name"], uint(record["action_code"], 8, "action code")) != (action["name"], action["code"]):
            raise DesignError("positive vectors must use exact frozen action order and codes")
        if not isinstance(record["case_id"], str) or not record["case_id"] or record["case_id"] in seen:
            raise DesignError("action vector IDs must be unique non-empty strings")
        seen.add(record["case_id"])
        exact_keys(record["payload"], set(payload_keys[index]), f"{action['name']} payload")
        _validate_action_payload(action["name"], record["payload"], contract)
        payload_bytes = _encode_action_payload(action, record["payload"])
        if record["payload_bytes_hex"] != payload_bytes.hex() or record["payload_sha256"] != hashlib.sha256(payload_bytes).hexdigest():
            raise DesignError("canonical payload bytes/hash mismatch")
        _validate_identity_and_action_id(record)
        cert = record["certificate"]
        exact_keys(cert, set(spec["certificate_fields"]), "certificate")
        exact_keys(cert["message_fields"], set(spec["certificate_message_fields"]), "certificate message")
        if uint(cert["version"], 16, "certificate version") != contract["certificate"]["version"] or uint(cert["epoch"], 64, "certificate epoch") < 0:
            raise DesignError("certificate version or epoch invalid")
        keys = cert["committee_public_keys_hex"]
        if uint(cert["threshold"], 8, "certificate threshold") != 3 or uint(cert["emergency_threshold"], 8, "emergency threshold") != 4:
            raise DesignError("certificate committee threshold mismatch")
        msg = cert["message_fields"]
        encoded_cert = certificate_message(msg)
        if cert["message_bytes_hex"] != encoded_cert.hex() or cert["message_sha256"] != hashlib.sha256(encoded_cert).hexdigest():
            raise DesignError("certificate canonical message/hash mismatch")
        if not verify_signatures(keys, encoded_cert, _committee_signature_records(cert)):
            raise DesignError("action certificate Ed25519 threshold verification failed")
        if cert["checkpoint_hash"] != msg["finalized_checkpoint_hash_hex"]:
            raise DesignError("certificate checkpoint summary differs from signed message")
        source, destination = contract["networks"][action["source"]], contract["networks"][action["destination"]]
        if (msg["source_chain_code"],msg["source_chain_id"],msg["source_network_magic"],msg["destination_chain_code"],msg["destination_chain_id"],msg["destination_network_magic"],msg["destination_address_network_id"]) != (source["chain_code"],source["chain_id"],source["network_magic"],destination["chain_code"],destination["chain_id"],destination["network_magic"],destination["address_network_id"]):
            raise DesignError("certificate is bound to the wrong chain domains")
        if msg["action_id_hex"] != record["action_id_hex"] or msg["payload_hash_hex"] != record["payload_sha256"] or msg["action_code"] != action["code"] or msg["source_action_nonce"] != record["identity_fields"]["source_action_nonce"]:
            raise DesignError("certificate does not bind exact action identity and payload")
        if "source_action_nonce" in record["payload"] and record["payload"]["source_action_nonce"] != msg["source_action_nonce"]:
            raise DesignError("payload stream nonce differs from certificate")
        if msg["source_event_block_number"] > msg["finalized_checkpoint_number"] or msg["expires_at_ms"] <= msg["issued_at_ms"] or msg["expires_at_ms"] - msg["issued_at_ms"] > contract["certificate"]["max_lifetime_ms"]:
            raise DesignError("certificate finality or lifetime bounds invalid")
        time = cert["destination_time_context"]
        exact_keys(time, {"cardano_validity_lower_posix_ms","cardano_validity_upper_posix_ms","evm_block_timestamp_seconds"}, "destination time context")
        lower, upper, seconds = (uint(time[k], 64, k) for k in ("cardano_validity_lower_posix_ms","cardano_validity_upper_posix_ms","evm_block_timestamp_seconds"))
        if destination["chain_code"] == 2:
            if seconds != 0 or not msg["issued_at_ms"] <= lower < upper < msg["expires_at_ms"] or upper-lower > contract["boundaries"]["cardano_tx_validity_interval_max_ms"]:
                raise DesignError("Cardano validity interval is outside strict certificate bounds")
        elif lower != 0 or upper != 0 or not msg["issued_at_ms"] <= seconds*1000 < msg["expires_at_ms"]:
            raise DesignError("EVM destination block time is outside strict certificate bounds")
        authority = record["authority"]
        exact_keys(authority, set(spec["authority_fields"]), "authority")
        exact_keys(authority["canonical_state"], set(spec["authority_state_fields"]), "canonical authority state")
        state_bytes = _encode_authority_state(authority["canonical_state"], contract)
        state_digest = hashlib.sha256(state_bytes).hexdigest()
        if authority["state_hash_hex"] != state_digest or msg["authority_state_hash_hex"] != state_digest:
            raise DesignError("certificate authority hash does not match canonical state preimage")
        canonical = authority["canonical_state"]
        ordered_key_bytes = _hex(canonical["ordered_keys_hex"], 160, "ordered authority keys")
        key_bytes = [ordered_key_bytes[index:index + 32] for index in range(0, 160, 32)]
        if (canonical["schema_version"] != 3 or len(key_bytes) != 5 or key_bytes != sorted(key_bytes)
                or len(set(key_bytes)) != 5 or canonical["threshold"] != 3 or canonical["status"] != "ACTIVE"):
            raise DesignError("canonical authority state violates committee schema")
        if (authority["epoch"] != canonical["epoch"] or authority["status"] != canonical["status"]
                or authority["committee_epoch"] != canonical["epoch"]
                or authority["state_hash_hex"] != state_digest or cert["epoch"] != canonical["epoch"]
                or msg["authority_epoch"] != canonical["epoch"]):
            raise DesignError("authority summary and certificate epoch/status do not match canonical state")
        mirror = authority["polygon_mirror"]
        exact_keys(mirror, set(spec["polygon_mirror_fields"]), "Polygon authority mirror")
        prior_mirror = mirror["prior_mirror"]
        prior_keys = _validate_prior_mirror(prior_mirror, spec, contract)
        if (mirror["version"] != 3 or mirror["authority_epoch"] != canonical["epoch"] or mirror["authority_state_hash_hex"] != state_digest
                or mirror["status"] != canonical["status"] or mirror["ordered_keys_hex"] != canonical["ordered_keys_hex"]
                or mirror["threshold"] != canonical["threshold"] or mirror["committee_epoch"] != canonical["epoch"]):
            raise DesignError("Polygon mirror does not equal canonical Cardano authority state")
        prior_epoch = uint(prior_mirror["authority_epoch"], 64, "prior mirror authority epoch")
        if canonical["epoch"] not in (prior_epoch, prior_epoch + 1):
            raise DesignError("Polygon mirror sync may retain an identical epoch or advance exactly one epoch")
        if canonical["epoch"] == prior_epoch and (state_digest != prior_mirror["authority_state_hash_hex"]
                or canonical["ordered_keys_hex"] != prior_mirror["ordered_keys_hex"]
                or canonical["status"] != prior_mirror["status"]):
            raise DesignError("same-epoch mirror sync must preserve the exact trusted authority state")
        sync = mirror["sync_certificate"]
        exact_keys(sync, set(spec["sync_certificate_fields"]), "authority sync certificate")
        exact_keys(sync["message_fields"], set(spec["sync_message_fields"]), "authority sync message")
        if uint(sync["version"], 16, "sync certificate version") != contract["polygon_authority_mirror"]["sync_certificate_version"]:
            raise DesignError("authority sync certificate version is not v3")
        sync_message = _encode_sync_message(sync["message_fields"], contract)
        if sync["message_bytes_hex"] != sync_message.hex() or sync["message_sha256"] != hashlib.sha256(sync_message).hexdigest() or not verify_signatures(sync["committee_public_keys_hex"], sync_message, _committee_signature_records(sync)):
            raise DesignError("authority sync certificate bytes/signatures invalid")
        sync_msg = sync["message_fields"]
        cardano_source = contract["networks"]["cardano_preprod"]
        if (sync_msg["previous_authority_state_hash_hex"] != prior_mirror["authority_state_hash_hex"]
                or sync_msg["previous_authority_epoch"] != prior_epoch
                or sync_msg["authority_state_hash_hex"] != state_digest or sync_msg["authority_epoch"] != canonical["epoch"]
                or (sync_msg["source_chain_code"],sync_msg["source_chain_id"],sync_msg["source_network_magic"])
                   != (cardano_source["chain_code"],cardano_source["chain_id"],cardano_source["network_magic"])
                or sync_msg["status"] != 1 or sync_msg["ordered_keys_hex"] != canonical["ordered_keys_hex"]
                or sync_msg["threshold"] != 3 or sync_msg["committee_epoch"] != mirror["committee_epoch"]
                or sync_msg["sync_nonce"] != mirror["sync_nonce"]
                or sync_msg["sync_nonce"] != prior_mirror["sync_nonce"] + 1
                or sync_msg["source_checkpoint_number"] != mirror["source_checkpoint_number"]
                or sync_msg["source_checkpoint_hash_hex"] != mirror["source_checkpoint_hash_hex"]
                or sync_msg["previous_sync_checkpoint_hash_hex"] != mirror["previous_sync_checkpoint_hash_hex"]):
            raise DesignError("authority sync message is not bound to exact mirror state")
        sync_checkpoint = uint(sync_msg["source_checkpoint_number"], 64, "sync source checkpoint")
        if (sync_checkpoint < prior_mirror["source_checkpoint_number"]
                or (sync_checkpoint == prior_mirror["source_checkpoint_number"]
                    and sync_msg["source_checkpoint_hash_hex"] != prior_mirror["source_checkpoint_hash_hex"])
                or (sync_checkpoint > prior_mirror["source_checkpoint_number"]
                    and sync_msg["previous_sync_checkpoint_hash_hex"] != prior_mirror["source_checkpoint_hash_hex"])):
            raise DesignError("authority sync checkpoint regresses or is not linked to the trusted prior mirror")
        if (sync_msg["expires_at_ms"] <= sync_msg["issued_at_ms"]
                or sync_msg["expires_at_ms"] - sync_msg["issued_at_ms"] > contract["polygon_authority_mirror"]["freshness_max_ms"]):
            raise DesignError("authority sync certificate time bounds invalid")
        if sync["committee_public_keys_hex"] != prior_keys:
            raise DesignError("authority sync must be authorized by the pre-update trusted mirror keys")
        if cert["committee_public_keys_hex"] != _committee_list_from_ordered_hex(canonical["ordered_keys_hex"], "post-sync authority keys"):
            raise DesignError("action certificate must use the installed current authority key set")
        if destination["chain_code"] == 1:
            now = uint(time["evm_block_timestamp_seconds"], 64, "EVM destination time") * 1000
            if uint(mirror["synced_at_ms"], 64, "mirror sync time") > now or now-mirror["synced_at_ms"] > contract["polygon_authority_mirror"]["freshness_max_ms"]:
                raise DesignError("Polygon authority mirror is stale")
        record["action_effects"]
        exact_keys(record["action_effects"], set(spec["action_effect_fields"]), "action effects")
        _validate_action_effect_semantics(record, action, contract)
        commitment = _action_effect_commitment(record, action, contract).hex()
        if record["action_effects"]["commitment_hex"] != commitment:
            raise DesignError("action effect commitment mismatch")
        effect_before, effect_after = record["action_effects"]["before"], record["action_effects"]["after"]
        if action["name"] == "WRAPPED_CREDIT":
            projected = record["state_after_source"]["global"]
            if (effect_before["source_liability_base"] != projected["current_locked_source_balance_base"]
                    or effect_after["source_liability_base"] != projected["current_locked_source_balance_base"]
                    or effect_before["actual_escrow_balance_base"] != projected["actual_escrow_token_balance_base"]
                    or effect_after["actual_escrow_balance_base"] != projected["actual_escrow_token_balance_base"]):
                raise DesignError("credit destination effect does not bind the already-committed source lock")
        elif action["name"] == "WRAPPED_RELEASE":
            pre, post = record["state_after_source"]["global"], record["state_after_destination"]["global"]
            if (effect_before["escrow_liability_base"] != pre["current_locked_source_balance_base"]
                    or effect_before["actual_escrow_balance_base"] != pre["actual_escrow_token_balance_base"]
                    or effect_after["escrow_liability_base"] != post["current_locked_source_balance_base"]
                    or effect_after["actual_escrow_balance_base"] != post["actual_escrow_token_balance_base"]):
                raise DesignError("release destination effect does not bind exact source liability reduction")
        elif action["name"] == "SLASH_AGENT":
            pre, post = record["state_after_source"]["global"], record["state_after_destination"]["global"]
            if (effect_before["slash_reserve_lovelace"] != pre["slash_reserve_lovelace"]
                    or effect_after["slash_reserve_lovelace"] != post["slash_reserve_lovelace"]):
                raise DesignError("slash destination effect does not bind reserve singleton transition")
        event = record["destination_event"]
        exact_keys(event, set(spec["destination_event_fields"]), "destination event")
        _hex(event["transaction_hash_hex"], 32, "destination event tx")
        _hex(event["block_hash_hex"], 32, "destination event block")
        uint(event["event_index"], 32, "destination event index"); uint(event["block_number"], 64, "destination event block")
        transaction = record["transaction"]
        exact_keys(transaction, set(spec["transaction_fields"]), "transaction stages")
        if set(transaction) != {"source","destination","ack"}:
            raise DesignError("transaction must have exactly source/destination/ack stages")
        for stage in ("source","destination"):
            exact_keys(transaction[stage], set(spec["chain_transaction_fields"]), f"transaction.{stage}")
        exact_keys(transaction["ack"], set(spec["ack_transaction_fields"]), "transaction.ack")
        for stage in ("source","destination","ack"):
            tx = transaction[stage]
            expected_tx = contract["vector_transactions"][action["name"]][stage]
            for field in ("chain","regular_inputs","reference_inputs","collateral_inputs","outputs","replay_input","replay_output"):
                if tx[field] != expected_tx[field]:
                    raise DesignError(f"{stage} transaction topology differs from frozen role contract")
            for field in ("mint","burn","reserve_delta"):
                if isinstance(tx[field], bool) or not isinstance(tx[field], int):
                    raise DesignError(f"{stage} transaction {field} must be a non-boolean integer")
        stx, dtx, atx = (transaction[stage] for stage in ("source","destination","ack"))
        for field in ("mint","burn","reserve_delta"):
            if atx[field] != 0:
                raise DesignError("ACK transaction must have zero economic deltas")
        if action["name"] == "WRAPPED_CREDIT":
            wrapped = convert_source_amount(record["payload"]["source_amount_base"], contract)
            if (stx["mint"],stx["burn"],dtx["mint"],dtx["burn"],dtx["reserve_delta"]) != (0,0,wrapped,0,wrapped):
                raise DesignError("credit transaction deltas must mint and reserve the exact wrapped amount")
        elif action["name"] == "WRAPPED_RELEASE":
            wrapped = record["payload"]["wrapped_amount"]
            source_amount = wrapped * contract["asset"]["source_units_per_wrapped_unit"]
            if (stx["mint"],stx["burn"],stx["reserve_delta"],dtx["mint"],dtx["burn"],dtx["reserve_delta"]) != (0,wrapped,-wrapped,0,0,-source_amount):
                raise DesignError("release transaction deltas must burn wrapped value then release exact source liability")
        elif action["name"] == "SLASH_AGENT":
            if (stx["mint"],stx["burn"],dtx["mint"],dtx["burn"],dtx["reserve_delta"]) != (0,0,0,0,record["payload"]["slash_amount_lovelace"]):
                raise DesignError("slash transaction deltas differ from the exact slash reserve credit")
        elif (stx["mint"],stx["burn"],dtx["mint"],dtx["burn"],dtx["reserve_delta"]) != (0,0,0,0,0):
            raise DesignError("intent transaction may not alter wrapped or slash-reserve accounting")
        ack_tx = transaction["ack"]
        if ack_tx["cleared_action_id_hex"] != record["action_id_hex"] or ack_tx["last_settled_action_id_hex"] != record["action_id_hex"]:
            raise DesignError("ACK transaction does not settle the exact action")
        receipt = ack_tx["receipt"]
        exact_keys(receipt, set(spec["ack_receipt_fields"]), "settlement receipt")
        exact_keys(receipt["message_fields"], set(spec["settlement_ack_message_fields"]), "settlement receipt message")
        if uint(receipt["version"], 16, "settlement receipt version") != contract["settlement_ack"]["version"]:
            raise DesignError("settlement receipt version is not v3")
        receipt_message = _encode_settlement_receipt(receipt["message_fields"], contract)
        if receipt["message_bytes_hex"] != receipt_message.hex() or receipt["message_sha256"] != hashlib.sha256(receipt_message).hexdigest() or not verify_signatures(receipt["committee_public_keys_hex"], receipt_message, _committee_signature_records(receipt)):
            raise DesignError("settlement receipt bytes/signatures invalid")
        rmsg = receipt["message_fields"]
        source_stream_key_hash = hashlib.sha256(_source_stream_key(record["identity_fields"])).hexdigest()
        source_pending = next((item for item in record["state_after_source"]["source_outbox"]["pending_records"]
                               if item["action_id_hex"] == record["action_id_hex"]), None)
        if source_pending is None:
            raise DesignError("source transaction did not persist the authority snapshot with its pending action")
        pending_committee = _committee_list_from_ordered_hex(source_pending["committee_public_keys_hex"], "pending receipt authority keys")
        if (rmsg["action_id_hex"] != record["action_id_hex"] or rmsg["action_code"] != action["code"]
                or rmsg["source_stream_key_hash_hex"] != source_stream_key_hash
                or rmsg["source_action_nonce"] != msg["source_action_nonce"]
                or (rmsg["destination_chain_code"],rmsg["destination_chain_id"],rmsg["destination_network_magic"])
                   != (destination["chain_code"],destination["chain_id"],destination["network_magic"])
                or rmsg["destination_transaction_hash_hex"] != event["transaction_hash_hex"]
                or rmsg["destination_event_index"] != event["event_index"]
                or rmsg["destination_event_block_number"] != event["block_number"]
                or rmsg["destination_event_block_hash_hex"] != event["block_hash_hex"]
                or rmsg["destination_effect_commitment_hex"] != commitment
                or rmsg["authority_state_hash_hex"] != source_pending["authority_state_hash_hex"]
                or rmsg["authority_epoch"] != source_pending["authority_epoch"]
                or rmsg["expires_at_ms"] <= rmsg["issued_at_ms"]
                or rmsg["expires_at_ms"] - rmsg["issued_at_ms"] > contract["settlement_ack"]["message_expiry_ms"]
                or receipt["committee_public_keys_hex"] != pending_committee):
            raise DesignError("settlement receipt does not bind exact destination effect and authority")
        _validate_stage_progression(record, action, contract, commitment)
        if record["expected"] != {"accepted":True,"result_code":"ACCEPT"}:
            raise DesignError("positive action vector must have exact ACCEPT result")
    _validate_cases(vectors["mutation_cases"], spec, "mutation")
    _validate_cases(vectors["arithmetic_cases"], spec, "arithmetic")
    _validate_rotation_barrier_cases(vectors["rotation_barrier_cases"], spec, contract,
                                     vectors["rotation_cases"], records)


def _validate_action_payload(name: str, payload: dict[str, Any], contract: dict[str, Any]) -> None:
    widths = {"source_escrow_address_hex": 20, "burn_transaction_hash_hex": 32,
              "credit_action_id_hex": 32, "destination_polygon_address_hex": 20,
              "identity_policy_id_hex": 28, "evidence_hash_hex": 32,
              "intent_transaction_hash_hex": 32, "intent_id_hex": 32,
              "action_hash_hex": 32, "payload_hash_hex": 32, "proposer_vkh_hex": 28}
    for key, length in widths.items():
        if key in payload:
            _hex(payload[key], length, key)
    variable = {"destination_cardano_address_hex":128,"identity_asset_name_hex":32,"target_domain_hex":32}
    for key, maximum in variable.items():
        if key in payload:
            value = payload[key]
            if not isinstance(value, str) or not re.fullmatch(r"(?:[0-9a-f]{2})+", value):
                raise DesignError(f"{key} must be even-length lowercase hex")
            _hex(value, len(value) // 2, key)
            if not 2 <= len(value) <= maximum * 2:
                raise DesignError(f"{key} must contain 1..{maximum} bytes")
    for key, value in payload.items():
        if key.endswith("_hex"):
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            raise DesignError(f"payload {key} must be a non-boolean integer")
        uint(value, 128 if key == "source_amount_base" else 64, key)
    for key in ("source_action_nonce", "source_amount_base", "wrapped_amount", "slash_amount_lovelace", "intent_nonce"):
        if key in payload and payload[key] == 0:
            raise DesignError(f"payload {key} must be positive")
    if "wrapped_amount" in payload and payload["wrapped_amount"] > contract["asset"]["cardano_mint_burn_max_abs_quantity"]:
        raise DesignError("wrapped amount exceeds signed-int64 cap")


def _encode_action_payload(action: dict[str, Any], payload: dict[str, Any]) -> bytes:
    types = dict(action["payload_fields"])
    output = bytearray(bytes.fromhex(action["payload_domain_hex"]))
    hex_keys = {"source_escrow_address":"source_escrow_address_hex", "destination_cardano_address":"destination_cardano_address_hex",
                "burn_transaction_hash":"burn_transaction_hash_hex", "credit_action_id":"credit_action_id_hex",
                "destination_polygon_address":"destination_polygon_address_hex", "identity_policy_id":"identity_policy_id_hex",
                "identity_asset_name":"identity_asset_name_hex", "evidence_hash":"evidence_hash_hex",
                "intent_transaction_hash":"intent_transaction_hash_hex", "intent_id":"intent_id_hex",
                "action_hash":"action_hash_hex", "payload_hash":"payload_hash_hex",
                "target_domain":"target_domain_hex", "proposer_vkh":"proposer_vkh_hex"}
    for field, kind in action["payload_fields"]:
        key = hex_keys.get(field, field)
        value = payload[key]
        if "length_prefixed" in kind:
            raw = bytes.fromhex(value)
            size = 2 if "u16" in kind else 1
            output.extend(len(raw).to_bytes(size, "big")); output.extend(raw)
        elif kind.startswith("bytes"):
            output.extend(bytes.fromhex(value))
        else:
            size = 4 if kind == "uint32_zero" else 2 if kind == "uint16" else 16 if "uint128" in kind else 8
            output.extend(_u(value, size, field))
    return bytes(output)


def _validate_identity_and_action_id(record: dict[str, Any]) -> None:
    fields = record["identity_fields"]
    exact_keys(fields, {"source_chain_code","source_chain_id","source_network_magic","destination_chain_code",
                        "destination_chain_id","destination_network_magic","source_endpoint_hex",
                        "event_transaction_hash_hex","event_index","action_code","source_action_nonce"},
               "identity_fields")
    endpoint_size = {1: 20, 2: 28}.get(fields["source_chain_code"])
    if endpoint_size is None:
        raise DesignError("unsupported source chain code")
    for key, size in (("source_endpoint_hex",endpoint_size),("event_transaction_hash_hex",32)):
        _hex(fields[key], size, key)
    digest = bytes.fromhex(record["payload_sha256"])
    actual = action_id(fields, digest)
    if record["action_id_hex"] != actual.hex():
        raise DesignError("canonical action ID mismatch")
    cert_fields = record["certificate"]["message_fields"]
    for key in ("source_chain_code","source_chain_id","source_network_magic","destination_chain_code",
                "destination_chain_id","destination_network_magic","action_code","source_action_nonce","event_index"):
        if fields[key] != cert_fields[key]:
            raise DesignError("identity fields disagree with certificate fields")
    if fields["event_transaction_hash_hex"] != cert_fields["event_transaction_hash_hex"]:
        raise DesignError("event transaction differs from certificate")


def _validate_counter_state(state: dict[str, Any], contract: dict[str, Any]) -> None:
    numeric = {"current_locked_source_balance_base":128,"minted":64,"burned":64,
               "outstanding":64,"pending_credit_base":128,"pending_release_base":128,
               "source_nonce":64,"checkpoint_number":64}
    for key, bits in numeric.items():
        uint(state[key], bits, key)
    chain_code = uint(state["source_chain_code"], 8, "source chain code")
    chain_id = uint(state["source_chain_id"], 64, "source chain id")
    network_magic = uint(state["source_network_magic"], 32, "source network magic")
    endpoint_size = {1: 20, 2: 28}.get(chain_code)
    if endpoint_size is None:
        raise DesignError("unsupported state source chain")
    endpoint = _hex(state["source_endpoint_hex"], endpoint_size, "state source endpoint")
    network = next((item for item in contract["networks"].values() if item["chain_code"] == chain_code), None)
    if network is None or (chain_id, network_magic) != (network["chain_id"], network["network_magic"]):
        raise DesignError("state source network is not a frozen deployment domain")
    for key in ("checkpoint_hash_hex","previous_checkpoint_hash_hex"):
        _hex(state[key], 32, key)
    asset = contract["asset"]
    if state["current_locked_source_balance_base"] > asset["source_balance_cap"]:
        raise DesignError("source balance exceeds uint128/supply cap")
    if max(state["pending_credit_base"], state["pending_release_base"]) > asset["pending_amount_cap"]:
        raise DesignError("pending amount exceeds uint128/supply cap")
    if not isinstance(state["consumed_action_ids"], list):
        raise DesignError("consumed_action_ids must be an array")
    for value in state["consumed_action_ids"]:
        _hex(value, 32, "consumed action id")
    if len(set(state["consumed_action_ids"])) != len(state["consumed_action_ids"]):
        raise DesignError("consumed action IDs must be unique")
    maximum = contract["asset"]["counter_max"]
    if max(state["minted"],state["burned"],state["outstanding"]) > maximum or state["burned"] > state["minted"]:
        raise DesignError("counter state outside cap")
    if state["outstanding"] != state["minted"] - state["burned"]:
        raise DesignError("outstanding != minted - burned")
    scale = asset["source_units_per_wrapped_unit"]
    records = state["pending_records"]
    if not isinstance(records, list) or len(records) > 1:
        raise DesignError("at most one pending action is allowed per source stream")
    pending_credit = pending_release = 0
    pending_ids: set[str] = set()
    for record in records:
        exact_keys(record, set(contract["vector_schema"]["pending_record_fields"]), "pending record")
        action_id_hex = record["action_id_hex"]
        _hex(action_id_hex, 32, "pending action id")
        if action_id_hex in pending_ids:
            raise DesignError("duplicate pending action id")
        pending_ids.add(action_id_hex)
        stream = record["source_stream_key_hex"]
        if not isinstance(stream, str) or not re.fullmatch(r"(?:[0-9a-f]{2})+", stream):
            raise DesignError("pending source stream key is malformed")
        raw_stream = bytes.fromhex(stream)
        if len(raw_stream) not in (34, 42):
            raise DesignError("pending source stream endpoint length is invalid")
        chain_code = raw_stream[0]
        expected_length = {1:20, 2:28}.get(chain_code)
        if expected_length is None or raw_stream[13] != expected_length or len(raw_stream) != 14 + expected_length:
            raise DesignError("pending source stream key does not match chain endpoint width")
        expected_stream = (bytes([chain_code]) + chain_id.to_bytes(8, "big")
                           + network_magic.to_bytes(4, "big") + bytes([endpoint_size]) + endpoint)
        if raw_stream != expected_stream:
            raise DesignError("pending record stream differs from state source identity")
        amount = uint(record["source_amount_base"], 128, "pending source amount")
        wrapped = uint(record["wrapped_amount"], 64, "pending wrapped amount")
        _hex(record["source_transaction_id_hex"], 32, "pending source transaction id")
        if record["action_kind"] == "WRAPPED_CREDIT" and record["status"] == "PENDING_CREDIT":
            if amount == 0 or amount % scale or amount // scale != wrapped:
                raise DesignError("pending credit amount conversion is inconsistent")
            pending_credit += amount
        elif record["action_kind"] == "WRAPPED_RELEASE" and record["status"] == "PENDING_RELEASE":
            if wrapped == 0 or amount != wrapped * scale:
                raise DesignError("pending release amount conversion is inconsistent")
            pending_release += amount
        else:
            raise DesignError("pending action kind and status disagree")
    if pending_credit != state["pending_credit_base"] or pending_release != state["pending_release_base"]:
        raise DesignError("pending aggregates disagree with pending records")
    rhs = (state["minted"] - state["burned"]) * scale + state["pending_credit_base"] + state["pending_release_base"]
    if state["current_locked_source_balance_base"] != rhs:
        raise DesignError("in-flight source/wrapped conservation mismatch")


def _validate_cases(cases: Any, schema: dict[str, Any], label: str) -> None:
    if not isinstance(cases, list) or not cases:
        raise DesignError(f"{label} cases must be a non-empty array")
    seen: set[str] = set()
    categories: set[str] = set()
    for index, case in enumerate(cases):
        fields = schema["mutation_fields"] if label == "mutation" else schema["arithmetic_fields"]
        exact_keys(case, set(fields), f"{label}[{index}]")
        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise DesignError(f"{label} IDs must be unique strings")
        seen.add(case_id)
        if label == "mutation":
            if case["operation"] not in schema["mutation_operations"] or not isinstance(case["expected_error"], str):
                raise DesignError("mutation operation/error invalid")
            categories.add(case["category"])
        elif not isinstance(case["operands"], dict) or ((case["expected_result"] is None) == (case["expected_error"] is None)):
            raise DesignError("arithmetic case requires exactly one expected result or error")
    if label == "mutation" and not (
            set(schema["action_required_mutation_categories"])
            |
            set(schema["rotation_required_mutation_categories"])
            | set(schema["rotation_barrier_required_mutation_categories"])
    ).issubset(categories):
        raise DesignError("mutation inventory omits required action, authority, or rotation-barrier cases")
    if label == "mutation":
        expected_paths = {
            "sync_prior_epoch": ("VECTORS.json", "rotation_cases[0].sync_certificate.message_fields.previous_authority_epoch", "replace"),
            "sync_prior_state_hash": ("VECTORS.json", "rotation_cases[0].sync_certificate.message_fields.previous_authority_state_hash_hex", "replace"),
            "sync_prior_key_set": ("VECTORS.json", "rotation_cases[0].sync_certificate.committee_public_keys_hex", "replace"),
            "sync_post_keys_authorize_rotation": ("VECTORS.json", "rotation_cases[0].sync_certificate.committee_public_keys_hex", "replace"),
            "sync_epoch_not_exact_plus_one": ("VECTORS.json", "rotation_cases[0].sync_certificate.message_fields.authority_epoch", "replace"),
            "certificate_threshold_below_quorum": ("VECTORS.json", "action_vectors[0].certificate.threshold", "replace"),
            "emergency_threshold_below_quorum": ("VECTORS.json", "action_vectors[0].certificate.emergency_threshold", "replace"),
            "frozen_contract_certificate_field_order": ("CONTRACT.json", "certificate.message_fields", "reorder"),
            "frozen_contract_certificate_domain_terminator": ("CONTRACT.json", "domain_bytes.certificate.domain_hex", "replace"),
            "boolean_action_code": ("VECTORS.json", "action_vectors[0].action_code", "replace"),
            "wrapped_credit_payload_schema": ("VECTORS.json", "action_vectors[0].payload.destination_cardano_address_hex", "remove"),
            "wrapped_release_payload_schema": ("VECTORS.json", "action_vectors[1].payload.credit_action_id_hex", "remove"),
            "slash_agent_payload_schema": ("VECTORS.json", "action_vectors[2].payload.identity_asset_name_hex", "remove"),
            "execute_intent_payload_schema": ("VECTORS.json", "action_vectors[3].payload.intent_id_hex", "remove"),
            "wrong_source_chain_domain": ("VECTORS.json", "action_vectors[0].certificate.message_fields.source_chain_id", "replace"),
            "proof_payload_substitution": ("VECTORS.json", "action_vectors[0].certificate.message_fields.payload_hash_hex", "replace"),
            "frozen_contract_source_scale": ("CONTRACT.json", "asset.source_units_per_wrapped_unit", "replace"),
            "frozen_contract_decimal_precision": ("CONTRACT.json", "asset.wrapped_decimals", "replace"),
            "source_action_cap_exceeded": ("VECTORS.json", "action_vectors[0].payload.source_amount_base", "replace"),
            "dust_amount": ("VECTORS.json", "action_vectors[0].payload.source_amount_base", "replace"),
            "wrapped_int64_overflow": ("VECTORS.json", "action_vectors[1].payload.wrapped_amount", "replace"),
            "counter_u64_overflow": ("VECTORS.json", "action_vectors[0].state_after.global.minted", "replace"),
            "counter_underflow": ("VECTORS.json", "action_vectors[0].state_after.global.burned", "replace"),
            "cumulative_supply_overflow": ("VECTORS.json", "action_vectors[0].state_after.global.minted", "replace"),
            "authority_epoch_overlap": ("VECTORS.json", "rotation_cases[0].sync_certificate.message_fields.authority_epoch", "replace"),
            "authority_epoch_non_plus_one": ("VECTORS.json", "rotation_cases[0].sync_certificate.message_fields.authority_epoch", "replace"),
            "replay_resurrection": ("VECTORS.json", "action_vectors[0].state_after.destination_replay.latest_by_source_stream[0].source_action_nonce", "replace"),
            "reserve_lovelace_substitution": ("VECTORS.json", "action_vectors[2].transaction.destination.reserve_delta", "replace"),
            "reserve_u64_overflow": ("VECTORS.json", "action_vectors[2].state_after.global.slash_reserve_lovelace", "replace"),
            "cross_action_rebinding": ("VECTORS.json", "action_vectors[0].action_code", "replace"),
            "unknown_vector_key": ("VECTORS.json", "action_vectors[0].unexpected_security_field", "add"),
            "duplicate_json_key": ("VECTORS.json", "action_vectors[0].payload", "duplicate_key_raw"),
            "wrong_receipt_effect_commitment_field_name": ("VECTORS.json", "action_vectors[0].transaction.ack.receipt.message_fields.destination_effect_commitment", "add"),
            "wrong_derived_credit_wrapped_amount": ("VECTORS.json", "action_vectors[0].state_after_source.source_outbox.pending_records[0].wrapped_amount", "replace"),
            "rotation_with_cardano_outbox_pending": ("VECTORS.json", "rotation_barrier_cases[0].cardano_activation.cardano_outbox_empty", "replace"),
            "rotation_with_polygon_outbox_pending": ("VECTORS.json", "rotation_barrier_cases[0].polygon_drained.polygon_outbox_empty", "replace"),
            "freeze_allows_new_source": ("VECTORS.json", "rotation_barrier_cases[0].polygon_freeze.phase", "replace"),
            "drain_accepts_post_cutoff_event": ("VECTORS.json", "rotation_barrier_cases[1].drain_steps[0].source_event_block_number", "replace"),
            "missing_cardano_ready_receipt": ("VECTORS.json", "rotation_barrier_cases[0].cardano_ready.receipt", "remove"),
            "missing_polygon_drained_receipt": ("VECTORS.json", "rotation_barrier_cases[0].polygon_drained.receipt", "remove"),
            "cardano_activation_before_delay": ("VECTORS.json", "rotation_barrier_cases[0].cardano_activation.now_ms", "replace"),
            "polygon_install_before_rotation_ready": ("VECTORS.json", "rotation_barrier_cases[0].polygon_install.cardano_rotation_ready_receipt_hash_hex", "replace"),
            "pause_clears_barrier": ("VECTORS.json", "rotation_barrier_cases[1].pause_resume.barrier_id_after_hex", "replace"),
            "pause_allows_economic_effect": ("VECTORS.json", "rotation_barrier_cases[1].pause_resume.economic_effect_during_pause", "replace"),
            "pause_ack_after_destination_cutoff": ("VECTORS.json", "rotation_barrier_cases[1].pause_resume.ack_effect_checkpoint_number", "replace"),
            "resume_changes_barrier_id": ("VECTORS.json", "rotation_barrier_cases[1].pause_resume.barrier_id_after_hex", "replace"),
            "resume_reopens_new_source": ("VECTORS.json", "rotation_barrier_cases[1].pause_resume.watermarks_after", "replace"),
            "resume_mutates_pending_record": ("VECTORS.json", "rotation_barrier_cases[1].pause_resume.pending_record_after", "replace"),
            "resume_changes_action_certificate": ("VECTORS.json", "rotation_barrier_cases[1].drain_steps[0].resumed_action_certificate.message_fields.action_certificate_hash_hex", "replace"),
            "repeated_pause_rewinds_cutoff": ("VECTORS.json", "rotation_barrier_cases[1].pause_resume.cutoffs_after.cardano_source_cutoff.checkpoint_number", "replace"),
            "rotation_interleaves_before_polygon_install": ("VECTORS.json", "rotation_barrier_cases[0].polygon_install.prior_mirror_frozen", "replace"),
            "activation_delay_not_exact_48_hours": ("VECTORS.json", "rotation_barrier_cases[0].cardano_activation.activation_at_ms", "replace"),
            "rotation_authorization_before_drained": ("VECTORS.json", "rotation_barrier_cases[0].cardano_authorization.authorization_certificate.message_fields.polygon_drained_receipt_hash_hex", "replace"),
            "expired_freeze_certificate": ("VECTORS.json", "rotation_barrier_cases[0].polygon_freeze.now_ms", "replace"),
            "future_freeze_certificate": ("VECTORS.json", "rotation_barrier_cases[0].polygon_freeze.now_ms", "replace"),
            "expired_cardano_ready_receipt": ("VECTORS.json", "rotation_barrier_cases[0].polygon_drained.now_ms", "replace"),
            "future_cardano_ready_receipt": ("VECTORS.json", "rotation_barrier_cases[0].polygon_drained.now_ms", "replace"),
            "expired_polygon_drained_receipt": ("VECTORS.json", "rotation_barrier_cases[0].cardano_authorization.cardano_validity_upper_ms", "replace"),
            "future_polygon_drained_receipt": ("VECTORS.json", "rotation_barrier_cases[0].cardano_authorization.cardano_validity_upper_ms", "replace"),
            "expired_rotation_ready_receipt": ("VECTORS.json", "rotation_barrier_cases[0].polygon_install.now_ms", "replace"),
            "future_rotation_ready_receipt": ("VECTORS.json", "rotation_barrier_cases[0].polygon_install.now_ms", "replace"),
            "pause_between_prepare_and_freeze": ("VECTORS.json", "rotation_barrier_cases[2].pre_freeze_pause_resume.present", "replace"),
            "stale_freeze_cert_after_pause": ("VECTORS.json", "rotation_barrier_cases[2].polygon_freeze.freeze_certificate", "replace"),
            "reauthorization_changes_barrier_target": ("VECTORS.json", "rotation_barrier_cases[2].polygon_freeze.freeze_certificate.message_fields.target_epoch", "replace"),
            "reauthorization_changes_cardano_snapshot": ("VECTORS.json", "rotation_barrier_cases[2].polygon_freeze.cardano_source_cutoff", "replace"),
            "repeat_freeze_rewinds_polygon_cutoff": ("VECTORS.json", "rotation_barrier_cases[2].pre_freeze_pause_resume.polygon_cutoff_before", "replace"),
            "economic_action_before_bilateral_freeze": ("VECTORS.json", "rotation_barrier_cases[2].polygon_freeze.phase", "replace"),
            "target_epoch_not_current_plus_one": ("VECTORS.json", "rotation_barrier_cases[1].cardano_activation.next_authority_state.epoch", "replace"),
            "missing_rotation_authorized_state": ("VECTORS.json", "rotation_barrier_cases[0].cardano_authorization", "remove"),
            "substituted_rotation_authorized_state": ("VECTORS.json", "rotation_barrier_cases[0].cardano_activation.authorization_state_hash_hex", "replace"),
            "backdated_rotation_authorization": ("VECTORS.json", "rotation_barrier_cases[0].cardano_authorization.state.authorized_at_ms", "replace"),
            "freeze_target_epoch_hash_mismatch": ("VECTORS.json", "rotation_barrier_cases[1].polygon_freeze.freeze_certificate.message_fields.target_authority_state_hash_hex", "replace"),
        }
        for category, path in expected_paths.items():
            matches = [case for case in cases if case["category"] == category]
            expected_artifact, expected_path, expected_operation = path
            if (len(matches) != 1 or matches[0]["artifact"] != expected_artifact
                    or matches[0]["path"] != expected_path or matches[0]["operation"] != expected_operation):
                raise DesignError(f"{category} mutation must target its exact closed rotation/barrier-vector field")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="validate the frozen F05.1-R4 design package")
    parser.add_argument("--dir", type=Path, default=Path(__file__).resolve().parent,
                        help="isolated normative-artifact directory")
    parser.add_argument("--contract", type=Path, help="explicit contract JSON path")
    parser.add_argument("--vectors", type=Path, help="explicit vectors JSON path")
    parser.add_argument("--contract-only", action="store_true",
                        help="validate the exact frozen contract without loading vectors")
    args = parser.parse_args(argv)
    contract_path = args.contract or args.dir / "CONTRACT.json"
    vectors_path = args.vectors or args.dir / "VECTORS.json"
    try:
        contract = load_json(contract_path)
        vectors = None if args.contract_only else load_json(vectors_path)
        print(json.dumps({"result": "PASS", **validate_contract(contract, vectors)}, sort_keys=True))
        return 0
    except (DesignError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"result": "FAIL", "reason": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
