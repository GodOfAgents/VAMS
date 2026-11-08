#!/usr/bin/env python3
"""Strict dependency-free validator for the F04 design artifacts."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DOMAIN = bytes.fromhex("56414d532f6167656e742f763100")
DID_MIN = 32
DID_MAX = 256
BOUNDARY_IDS = {
    "did_len_31_rejected": (31, False, "DID_LENGTH_BELOW_MIN"),
    "did_len_32_accepted": (32, True, "DID_LENGTH_MINIMUM_INCLUSIVE"),
    "did_len_256_accepted": (256, True, "DID_LENGTH_MAXIMUM_INCLUSIVE"),
    "did_len_257_rejected": (257, False, "DID_LENGTH_ABOVE_MAX"),
    "did_invalid_utf8_rejected": (32, False, "DID_UTF8_INVALID"),
}


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


def load(name: str, base: Path = ROOT) -> Any:
    raw = (base / name).read_bytes()
    if not raw.startswith(b"{"):
        raise ValueError(name + ": object required")
    return json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON")),
    )


def exact(obj: Any, keys: tuple[str, ...] | set[str], label: str) -> None:
    if type(obj) is not dict or set(obj) != set(keys):
        raise ValueError(label + ": closed keys")


def integer(value: Any, label: str, minimum: int | None = None, maximum: int | None = None) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise ValueError(label + ": strict integer")
    if minimum is not None and value < minimum:
        raise ValueError(label + ": minimum")
    if maximum is not None and value > maximum:
        raise ValueError(label + ": maximum")
    return value


def boolean(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise ValueError(label + ": strict boolean")
    return value


def text(value: Any, label: str) -> str:
    if type(value) is not str:
        raise ValueError(label + ": string required")
    return value


def hex_value(value: Any, label: str, size: int | None = None) -> bytes:
    text_value = text(value, label)
    if len(text_value) % 2 or text_value.startswith("0x") or any(c not in "0123456789abcdef" for c in text_value):
        raise ValueError(label + ": lowercase hex")
    raw = bytes.fromhex(text_value)
    if size is not None and len(raw) != size:
        raise ValueError(label + ": byte length")
    return raw


def did_value(value: Any, label: str = "did") -> bytes:
    raw = hex_value(value, label)
    if not DID_MIN <= len(raw) <= DID_MAX:
        raise ValueError(label + ": DID length")
    try:
        decoded = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise ValueError(label + ": invalid UTF-8") from exc
    if decoded.encode("utf-8") != raw:
        raise ValueError(label + ": non-canonical UTF-8")
    return raw


def derive(row: dict[str, Any]) -> tuple[str, str]:
    did = did_value(row["did"])
    owner = hex_value(row["owner_vkh"], "owner", 28)
    seed = hex_value(row["seed_tx_id"], "seed", 32)
    index = integer(row["seed_index"], "index", 0, 0xFFFFFFFF)
    preimage = DOMAIN + len(did).to_bytes(2, "big") + did + owner + seed + index.to_bytes(4, "big")
    return preimage.hex(), hashlib.blake2b(preimage, digest_size=32).hexdigest()


def _validate_identity(spec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    exact(spec, ("schema_version", "status", "identity", "datum", "authority", "redeemers", "limits", "lifecycle", "r5_contract", "entrypoints"), "identity spec")
    if spec["schema_version"] != "m3-f04-r1-identity-v1" or spec["status"] != "design-frozen-not-implemented":
        raise ValueError("identity spec version/status")
    identity = spec["identity"]
    exact(identity, ("policy", "bootstrap", "domain_hex", "formula", "token_name_bytes", "policy_id_bytes", "mint_quantity", "retain_quantity", "burn_quantity", "did_rules", "hex_rules", "json_rules", "integer_rule"), "identity")
    for key in ("policy", "bootstrap", "formula", "integer_rule"):
        text(identity[key], "identity " + key)
    if hex_value(identity["domain_hex"], "identity domain", len(DOMAIN)) != DOMAIN:
        raise ValueError("identity domain")
    integer(identity["token_name_bytes"], "token bytes", 1)
    integer(identity["policy_id_bytes"], "policy bytes", 1)
    integer(identity["mint_quantity"], "mint quantity")
    integer(identity["retain_quantity"], "retain quantity")
    integer(identity["burn_quantity"], "burn quantity")
    if (identity["token_name_bytes"], identity["policy_id_bytes"], identity["mint_quantity"], identity["retain_quantity"], identity["burn_quantity"]) != (32, 28, 1, 1, -1):
        raise ValueError("identity dimensions/quantities")
    did_rules = identity["did_rules"]
    exact(did_rules, ("representation", "encoding", "canonical_utf8", "min_bytes", "max_bytes", "boundary_lengths", "invalid_utf8_rejected"), "DID rules")
    if text(did_rules["representation"], "DID representation") != "lowercase-hex" or text(did_rules["encoding"], "DID encoding") != "utf-8":
        raise ValueError("DID representation/encoding")
    if boolean(did_rules["canonical_utf8"], "DID canonical") is not True or boolean(did_rules["invalid_utf8_rejected"], "DID UTF-8") is not True:
        raise ValueError("DID UTF-8 rules")
    if integer(did_rules["min_bytes"], "DID minimum", 1) != DID_MIN or integer(did_rules["max_bytes"], "DID maximum", DID_MIN) != DID_MAX:
        raise ValueError("DID bounds")
    if did_rules["boundary_lengths"] != [31, 32, 256, 257]:
        raise ValueError("DID boundary lengths")
    hex_rules = did_rules = identity["hex_rules"]
    exact(hex_rules, ("alphabet", "lowercase", "even_length", "prefix"), "hex rules")
    if text(hex_rules["alphabet"], "hex alphabet") != "0123456789abcdef" or boolean(hex_rules["lowercase"], "hex lowercase") is not True or boolean(hex_rules["even_length"], "hex even") is not True or text(hex_rules["prefix"], "hex prefix") != "forbidden":
        raise ValueError("hex rules")
    json_rules = identity["json_rules"]
    exact(json_rules, ("closed_objects", "duplicate_keys", "unknown_keys", "missing_keys", "non_finite_numbers"), "JSON rules")
    if boolean(json_rules["closed_objects"], "closed objects") is not True or any(text(json_rules[key], key) != "reject" for key in ("duplicate_keys", "unknown_keys", "missing_keys", "non_finite_numbers")):
        raise ValueError("JSON strict rules")
    datum = spec["datum"]
    exact(datum, ("name", "constructor", "closed", "fields"), "datum")
    if text(datum["name"], "datum name") != "AgentDatumV1" or integer(datum["constructor"], "datum constructor", 0) != 0 or boolean(datum["closed"], "datum closed") is not True or type(datum["fields"]) is not list or len(datum["fields"]) != 14:
        raise ValueError("datum schema")
    names = []
    for index, field in enumerate(datum["fields"]):
        if type(field) is not list or len(field) != 3 or any(type(item) not in (str, int) or isinstance(item, bool) for item in field):
            raise ValueError("datum field " + str(index))
        names.append(field[0])
    if len(set(names)) != 14 or names[:4] != ["schema_version", "identity_policy_id", "identity_asset_name", "nonce"]:
        raise ValueError("datum field order")
    authority = spec["authority"]
    exact(authority, ("name", "closed", "fields"), "authority")
    if text(authority["name"], "authority name") != "RegistryAuthorityV1" or boolean(authority["closed"], "authority closed") is not True or type(authority["fields"]) is not list:
        raise ValueError("authority schema")
    for field in authority["fields"]:
        text(field, "authority field")
    if authority["fields"] != ["schema_version:u16=1", "identity_policy_id:bytes28", "bootstrap_ref:OutputReference", "action_epoch:u64", "slash_enabled:bool=false_pre_f05", "authority_script_hash:bytes28", "authority_policy_id:bytes28", "authority_asset_name:bytes32", "authority_quantity:u64=1", "authority_state_lovelace:u64", "reserve_credential:bytes28", "authority_address:script_hash", "datum_hash:bytes32"]:
        raise ValueError("authority binding fields")
    redeemers = spec["redeemers"]
    if type(redeemers) is not dict or set(redeemers) != {"RegisterAgent", "UpdateAgent", "DeregisterAgent", "SlashAgent"}:
        raise ValueError("redeemer schema")
    for key, values in redeemers.items():
        if type(values) is not list or not values or integer(values[0], key + " constructor", 0) < 0 or any(type(item) is not str for item in values[1:]):
            raise ValueError("redeemer " + key)
    limits = spec["limits"]
    exact(limits, ("min_stake_lovelace", "max_slash_bps", "initial_reputation_bps", "max_reputation_bps", "max_authorized_slashers", "max_inputs", "max_outputs", "max_assets_per_value", "max_datum_bytes"), "limits")
    for key in limits:
        integer(limits[key], "limit " + key, 0)
    if limits["min_stake_lovelace"] != 1000000000 or limits["max_slash_bps"] != 1000 or limits["initial_reputation_bps"] != 5000:
        raise ValueError("limit values")
    lifecycle = spec["lifecycle"]
    exact(lifecycle, ("slash_pre_f05", "register", "update", "deregister"), "lifecycle")
    for key in lifecycle:
        text(lifecycle[key], "lifecycle " + key)
    if lifecycle["slash_pre_f05"] != "reject_unconditionally":
        raise ValueError("slash pre-F05 policy")
    expected_r5 = {
        "authority_reference": {"count": 1, "kind": "reference_input", "datum": "RegistryAuthorityV1", "credential": "authority_script_hash", "address": "exact script address from authority_script_hash", "policy_id": "authority_policy_id exact", "token_name": "authority_asset_name exact", "quantity": 1, "value": "exactly authority_state_lovelace plus one authority_policy_id.authority_asset_name", "datum_hash": "hash of the exact RegistryAuthorityV1 datum", "match": ["identity_policy_id", "bootstrap_ref", "action_epoch", "authority_script_hash", "authority_policy_id", "authority_asset_name", "reserve_credential"], "registry_stake_excluded": True, "missing_duplicate_stale": "reject"},
        "action_authorization": {"input_count": 1, "input_kind": "regular_input", "datum": "RegistryActionV1", "policy_id": "action_policy_id exact", "token_name": "action_asset_name exact", "quantity": 1, "burn_quantity": -1, "consumed_once": True, "success_rule": "one unique action token is burned on success", "authority_substitution": "reject", "registry_stake_substitution": "reject"},
        "replay": {"identity": "identity_policy_id || identity_asset_name || nonce || action_epoch", "expected_nonce": "redeemer.expected_nonce == input_datum.nonce", "output_nonce": "output_datum.nonce == input_datum.nonce + 1", "same_nonce": "reject across concurrent or restarted evaluation", "duplicate_signer": "reject"},
        "f05_interface": {"authority_gate": "reference.authority.slash_enabled == true", "evidence_type": "EvidenceAttestationV1", "evidence_fields": ["schema_version", "identity_policy_id", "identity_asset_name", "action_epoch", "nonce", "evidence_hash", "authorized_slasher", "valid_until", "status", "verifier_id"], "status": "verified", "expiry": "tx_upper_bound <= valid_until", "binding": "identity_policy_id, identity_asset_name, action_epoch, nonce, slasher and evidence_hash exact", "pre_f05": "reject_unconditionally"},
        "inv10": {"bridge_proof": "opaque proof input; never payload_hash", "payload_hash": "separate bytes32 action-payload digest", "alias_or_substitution": "reject", "registry_effect": "no slash effect until F05 evidence verifier is enabled"},
    }
    if spec["r5_contract"] != expected_r5:
        raise ValueError("R5 contract mismatch")
    entrypoints = spec["entrypoints"]
    exact(entrypoints, ("registry_spend", "registry_else", "identity_mint", "context"), "entrypoints")
    for key in entrypoints:
        text(entrypoints[key], "entrypoint " + key)
    if entrypoints["registry_spend"] != "agent_registry.agent_registry.spend" or entrypoints["identity_mint"] != "agent_nft.agent_nft.mint":
        raise ValueError("entrypoint boundary")
    return datum, limits


def _validate_boundary_rows(rows: Any, label: str) -> None:
    if type(rows) is not list or {(row.get("id", "").removeprefix("datum_") if label == "datum" else row.get("id")) for row in rows if type(row) is dict} != set(BOUNDARY_IDS):
        raise ValueError(label + ": boundary coverage")
    for row in rows:
        exact(row, ("id", "did", "accepted", "reason"), label + " boundary row")
        lookup_id = row["id"].removeprefix("datum_") if label == "datum" else row["id"]
        expected_length, expected_accept, expected_reason = BOUNDARY_IDS[lookup_id]
        raw = hex_value(row["did"], label + " DID")
        if len(raw) != expected_length or boolean(row["accepted"], label + " accepted") is not expected_accept or text(row["reason"], label + " reason") != expected_reason:
            raise ValueError(label + ": boundary expectation")
        if expected_accept:
            did_value(row["did"], label + " DID")
        else:
            try:
                did_value(row["did"], label + " DID")
            except ValueError:
                pass
            else:
                raise ValueError(label + ": rejected DID accepted")


def _validate_asset_vectors(base: Path) -> int:
    vectors = load("ASSET_VECTORS.json", base)
    exact(vectors, ("schema_version", "status", "vectors", "boundary_vectors"), "asset vectors")
    if text(vectors["schema_version"], "asset version") != "m3-f04-r1-assets-v1" or text(vectors["status"], "asset status") != "design-only" or type(vectors["vectors"]) is not list or len(vectors["vectors"]) != 2:
        raise ValueError("asset vectors identity")
    ids: set[str] = set()
    for row in vectors["vectors"]:
        exact(row, ("id", "seed_tx_id", "seed_index", "owner_vkh", "did", "preimage_hex", "token_name", "accepted"), "asset row")
        row_id = text(row["id"], "asset id")
        if row_id in ids or boolean(row["accepted"], "asset accepted") is not True:
            raise ValueError("asset row identity")
        ids.add(row_id)
        preimage, token = derive(row)
        if row["preimage_hex"] != preimage or row["token_name"] != token:
            raise ValueError("asset derivation " + row_id)
        hex_value(row["preimage_hex"], "preimage")
        hex_value(row["token_name"], "token name", 32)
    _validate_boundary_rows(vectors["boundary_vectors"], "asset")
    return len(vectors["vectors"])


def _validate_datum_fields(fields: Any, datum_fields: list[list[Any]], limits: dict[str, Any]) -> None:
    required = {field[0] for field in datum_fields}
    if type(fields) is not dict or set(fields) != required:
        raise ValueError("datum vector fields")
    integer(fields["schema_version"], "schema version", 1, 1)
    integer(fields["nonce"], "nonce", 0)
    integer(fields["stake_lovelace"], "stake", limits["min_stake_lovelace"])
    integer(fields["reputation_bps"], "reputation", 0, 10000)
    integer(fields["action_epoch"], "action epoch", 0)
    integer(fields["registered_at_ms"], "registered at", 0)
    did_value(fields["did"], "datum DID")
    hex_value(fields["identity_policy_id"], "datum policy", 28)
    hex_value(fields["identity_asset_name"], "datum asset", 32)
    hex_value(fields["owner"], "datum owner", 28)
    hex_value(fields["operator"], "datum operator", 28)
    hex_value(fields["metadata_hash"], "metadata", 32)
    if text(fields["status"], "datum status") not in {"active", "suspended"}:
        raise ValueError("datum status")
    if type(fields["authorized_slashers"]) is not list or len(fields["authorized_slashers"]) > limits["max_authorized_slashers"]:
        raise ValueError("slasher list")
    for signer in fields["authorized_slashers"]:
        hex_value(signer, "slasher", 28)


def _validate_datum_vectors(base: Path, datum_fields: list[list[Any]], limits: dict[str, Any]) -> int:
    vectors = load("DATUM_VECTORS.json", base)
    exact(vectors, ("schema_version", "status", "vectors", "boundary_vectors"), "datum vectors")
    if text(vectors["schema_version"], "datum version") != "m3-f04-r1-datum-vectors-v1" or text(vectors["status"], "datum status") != "design-only" or type(vectors["vectors"]) is not list or len(vectors["vectors"]) != 2:
        raise ValueError("datum vector identity")
    ids: set[str] = set()
    for row in vectors["vectors"]:
        exact(row, ("id", "accepted", "fields"), "datum vector row")
        row_id = text(row["id"], "datum id")
        if row_id in ids or boolean(row["accepted"], "datum accepted") is not True:
            raise ValueError("datum vector identity")
        ids.add(row_id)
        _validate_datum_fields(row["fields"], datum_fields, limits)
    _validate_boundary_rows(vectors["boundary_vectors"], "datum")
    return len(vectors["vectors"])


def validate(base: Path = ROOT) -> dict[str, int | bool]:
    spec = load("IDENTITY_SPEC.json", base)
    datum, limits = _validate_identity(spec)
    asset_count = _validate_asset_vectors(base)
    datum_count = _validate_datum_vectors(base, datum["fields"], limits)

    topology = load("TRANSITION_TOPOLOGY.json", base)
    exact(topology, ("schema_version", "status", "transitions"), "topology")
    seen: set[str] = set()
    expected_topology = {
        "register": ({"state": 0, "bootstrap": 1, "authority_reference": 1, "collateral": 1}, {"agent_state": 1, "owner_release": 0, "reserve": 0, "change_max": 1}, 1, 0),
        "update": ({"state": 1, "bootstrap": 0, "authority_reference": 1, "collateral": 1}, {"agent_state": 1, "owner_release": 0, "reserve": 0, "change_max": 1}, 0, 0),
        "slash": ({"state": 1, "bootstrap": 0, "authority_reference": 1, "action_authorization": 1, "evidence_reference": 1, "collateral": 1}, {"agent_state": 1, "owner_release": 0, "reserve": 1, "change_max": 1}, 0, 0),
        "deregister": ({"state": 1, "bootstrap": 0, "authority_reference": 1, "collateral": 1}, {"agent_state": 0, "owner_release": 1, "reserve": 0, "change_max": 1}, 0, -1),
    }
    topology_required = {"id", "redeemer", "inputs", "outputs", "identity_mint", "identity_burn", "pre_f05"}
    topology_optional = {"authority_reference", "action_authorization", "continuation", "operator", "evidence_reference", "reserve", "owner_release"}
    for row in topology["transitions"]:
        if type(row) is not dict or not topology_required.issubset(row) or not set(row).issubset(topology_required | topology_optional):
            raise ValueError("topology row: closed keys")
        row_id = text(row["id"], "topology id")
        if row_id in seen or row_id not in expected_topology:
            raise ValueError("topology id")
        seen.add(row_id)
        expected_inputs, expected_outputs, expected_mint, expected_burn = expected_topology[row_id]
        if row["inputs"] != expected_inputs or row["outputs"] != expected_outputs or row["identity_mint"] != expected_mint or row["identity_burn"] != expected_burn:
            raise ValueError("topology equation")
        for group in (row["inputs"], row["outputs"]):
            if type(group) is not dict:
                raise ValueError("topology map")
            for value in group.values():
                integer(value, "topology count", 0)
        integer(row["identity_mint"], "mint", 0)
        if type(row["identity_burn"]) is not int or isinstance(row["identity_burn"], bool):
            raise ValueError("burn integer")
        if row_id == "slash" and text(row["pre_f05"], "slash topology") != "reject_unconditionally":
            raise ValueError("slash topology")
        if row_id == "slash":
            if text(row["reserve"], "slash reserve") != "one unique output to the fixed reserve credential from the authority reference; registry stake cannot substitute":
                raise ValueError("slash reserve destination")
            if text(row["action_authorization"], "slash action") != "one consumed regular RegistryActionV1 input with exact action policy/token/quantity; burn exactly one unique action token on success":
                raise ValueError("slash action authorization")
    if seen != set(expected_topology):
        raise ValueError("topology coverage")

    rules = load("VALUE_RULES.json", base)
    exact(rules, ("schema_version", "status", "rules", "operator_rules", "post_f05_slash_interface", "integer_rules"), "value rules")
    if rules["integer_rules"]["json_integer"] != "type(value) is int and not bool":
        raise ValueError("integer rule")
    for key in ("register", "update", "slash_post_f05", "deregister", "replay", "reserve", "inv10", "all"):
        if not rules["rules"].get(key):
            raise ValueError("missing value rule " + key)
    if rules["rules"]["replay"] != ["replay_key == identity_policy_id || identity_asset_name || nonce || action_epoch", "expected_nonce == input_datum.nonce", "output_nonce == input_datum.nonce + 1", "same replay key rejects across concurrent or restarted evaluation"]:
        raise ValueError("replay value rule")
    if rules["rules"]["reserve"] != ["post_f05 reserve credential == authority_reference.reserve_credential", "reserve_delta == slash_amount", "reserve output cardinality == 1", "reserve routing mutation rejects", "pre_f05 reserve output == 0", "registry stake is not authority value and cannot satisfy authority binding"]:
        raise ValueError("reserve value rule")
    if rules["rules"]["inv10"] != ["bridge_proof is distinct opaque proof input", "payload_hash is distinct bytes32 action digest", "bridge_proof cannot populate payload_hash", "proof/payload alias or substitution rejects"]:
        raise ValueError("INV-10 value rule")
    if rules["post_f05_slash_interface"] != {"authority": "RegistryAuthorityV1.slash_enabled == true with exact policy/token/quantity/value/datum/address binding", "action": "one consumed regular RegistryActionV1 input with exact action policy/token/quantity and one unique action token burned on success", "evidence": "EvidenceAttestationV1(status=verified, identity/policy/token/epoch/nonce/slasher/evidence_hash exact, valid_until >= tx_upper_bound)", "destination": "fixed reserve credential from authority reference", "replay": "same identity/nonce/epoch evidence cannot be consumed twice", "substitution": "authority/action values cannot substitute registry stake"}:
        raise ValueError("R5 slash interface")

    matrix = load("ACCEPTANCE_MATRIX.json", base)
    exact(matrix, ("schema_version", "status", "evidence_status_default", "rows"), "acceptance matrix")
    if len(matrix["rows"]) != 49 or matrix["evidence_status_default"] != "pending":
        raise ValueError("matrix size/status")
    seen_matrix: set[str] = set()
    for row in matrix["rows"]:
        exact(row, ("id", "transition", "expectation", "reason", "mutation"), "matrix row")
        row_id = text(row["id"], "matrix id")
        if row_id in seen_matrix or row["expectation"] not in {"accept", "reject"}:
            raise ValueError("matrix row")
        seen_matrix.add(row_id)
    required = {"register_valid", "update_valid", "slash_valid_pre_f05", "deregister_valid", "register_declared_stake_only", "update_identity_rebind", "slash_wrong_remainder", "deregister_missing_burn", "schema_boolean_integer", "update_replayed_nonce", "update_parallel_nonce", "update_stale_epoch_r5", "slash_reserve_redirect", "slash_evidence_identity_mismatch", "slash_evidence_expired", "slash_proof_payload_alias", "slash_payload_substitution"}
    if not required.issubset(seen_matrix):
        raise ValueError("matrix coverage")
    return {"ok": True, "asset_vectors": asset_count, "datum_vectors": datum_count, "topology_rows": len(seen), "matrix_rows": len(matrix["rows"])}


if __name__ == "__main__":
    try:
        print(json.dumps(validate(), sort_keys=True))
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        raise SystemExit(1)
