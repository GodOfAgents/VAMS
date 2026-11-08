"""Independent F05.1-R4 canonical byte oracles; no validator imports."""
from __future__ import annotations

import hashlib
from typing import Any


def sha(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _raw_hex(value: str, size: int | None = None) -> bytes:
    if not isinstance(value, str) or len(value) % 2 or value.lower() != value:
        raise ValueError("expected lowercase even-length hex")
    result = bytes.fromhex(value)
    if size is not None and len(result) != size:
        raise ValueError("hex width mismatch")
    return result


def _uint(value: Any, width: int) -> bytes:
    if type(value) is not int or value < 0 or value >= 1 << (width * 8):
        raise ValueError("unsigned integer outside exact width")
    return value.to_bytes(width, "big")


def _key(name: str, value_map: dict[str, Any]) -> str:
    if name in value_map:
        return name
    candidate = name + "_hex"
    if candidate in value_map:
        return candidate
    if name.endswith("hash") or name in {
        "action_id", "source_stream_key_hash", "destination_effect_commitment",
        "ordered_keys", "ordered_next_keys", "barrier_id", "cardano_outbox_commitment",
        "polygon_outbox_commitment", "cardano_ready_receipt", "polygon_drained_receipt",
        "action_certificate_hash",
    }:
        if candidate in value_map:
            return candidate
    return name


def encode_fields(rows: list[list[Any]], values: dict[str, Any], *, enums: dict[str, dict[str, int]] | None = None) -> bytes:
    """Encode the frozen ordered field table; validates widths independently."""
    enums = enums or {}
    out = bytearray()
    for name, enc in rows:
        k = _key(name, values)
        if k not in values:
            raise ValueError(f"missing field {name}")
        value = values[k]
        if isinstance(enc, int):
            if name in enums:
                value = enums[name][value] if isinstance(value, str) else value
                out.extend(_uint(value, enc))
            elif name.endswith("hash") or name in {
                "action_id", "source_stream_key_hash", "destination_effect_commitment",
                "barrier_id", "cardano_outbox_commitment", "polygon_outbox_commitment",
                "cardano_ready_receipt", "polygon_drained_receipt", "action_certificate_hash",
                "ordered_keys", "ordered_next_keys",
            }:
                out.extend(_raw_hex(value, enc))
            else:
                out.extend(_uint(value, enc))
        elif enc in ("uint64", "uint128"):
            out.extend(_uint(value, int(enc[4:]) // 8))
        elif enc.startswith("bytes") and "length_prefixed" not in enc:
            out.extend(_raw_hex(value, int(enc[5:])))
        elif enc in ("bytes_1_to_32_length_prefixed_u8", "bytes_1_to_128_length_prefixed_u16"):
            raw = _raw_hex(value)
            cap, pfx = (32, 1) if enc.endswith("u8") else (128, 2)
            if not 1 <= len(raw) <= cap:
                raise ValueError("length-prefixed bytes outside contract limits")
            out.extend(_uint(len(raw), pfx)); out.extend(raw)
        elif enc == "enum1_QUEUED_EXECUTED":
            out.extend(_uint({"QUEUED": 1, "EXECUTED": 2}[value], 1))
        else:
            raise ValueError(f"unsupported encoding {enc!r}")
    return bytes(out)


def payload_bytes(action: dict[str, Any], payload: dict[str, Any], domain_hex: str) -> bytes:
    aliases = {
        "source_escrow_address": "source_escrow_address_hex",
        "destination_cardano_address": "destination_cardano_address_hex",
        "burn_transaction_hash": "burn_transaction_hash_hex",
        "credit_action_id": "credit_action_id_hex",
        "destination_polygon_address": "destination_polygon_address_hex",
        "identity_policy_id": "identity_policy_id_hex",
        "identity_asset_name": "identity_asset_name_hex",
        "evidence_hash": "evidence_hash_hex",
        "intent_transaction_hash": "intent_transaction_hash_hex",
        "intent_id": "intent_id_hex", "action_hash": "action_hash_hex",
        "payload_hash": "payload_hash_hex", "target_domain": "target_domain_hex",
        "proposer_vkh": "proposer_vkh_hex",
    }
    out = bytearray(_raw_hex(domain_hex))
    for field, enc in action["payload_fields"]:
        value = payload[aliases.get(field, field)]
        if enc.startswith("bytes_"):
            raw = _raw_hex(value)
            n = 1 if enc.endswith("u8") else 2
            cap = 32 if n == 1 else 128
            if not 1 <= len(raw) <= cap:
                raise ValueError("payload bytes bound")
            out.extend(_uint(len(raw), n)); out.extend(raw)
        elif enc.startswith("bytes"):
            out.extend(_raw_hex(value, int(enc[5:])))
        else:
            width = 4 if enc == "uint32_zero" else 2 if enc == "uint16" else 16 if "uint128" in enc else 8
            out.extend(_uint(value, width))
    return bytes(out)


def action_id(identity: dict[str, Any], payload_hash_hex: str, domain_hex: str) -> bytes:
    endpoint = _raw_hex(identity["source_endpoint_hex"])
    if len(endpoint) not in (20, 28):
        raise ValueError("wrong source endpoint size")
    preimage = (
        bytes.fromhex(domain_hex)
        + _uint(identity["source_chain_code"], 1)
        + _uint(identity["source_chain_id"], 8)
        + _uint(identity["source_network_magic"], 4)
        + _uint(identity["destination_chain_code"], 1)
        + _uint(identity["destination_chain_id"], 8)
        + _uint(identity["destination_network_magic"], 4)
        + _uint(len(endpoint), 1) + endpoint
        + _raw_hex(identity["event_transaction_hash_hex"], 32)
        + _uint(identity["event_index"], 4)
        + _uint(identity["action_code"], 1)
        + _uint(identity["source_action_nonce"], 8)
        + _raw_hex(payload_hash_hex, 32)
    )
    return sha(preimage)


def certificate_bytes(fields: dict[str, Any], rows: list[list[Any]], domain_hex: str) -> bytes:
    return bytes.fromhex(domain_hex) + encode_fields(rows, fields)


def authority_state_bytes(state: dict[str, Any], contract: dict[str, Any]) -> bytes:
    values = dict(state)
    values["key_count"] = len(_raw_hex(state["ordered_keys_hex"])) // 32
    values["status"] = {"ACTIVE": 1, "PAUSED": 2}[state["status"]]
    return bytes.fromhex(contract["authority_preimages"]["state_domain_hex"]) + encode_fields(
        contract["authority_preimages"]["state_fields"], values
    )


def sync_bytes(fields: dict[str, Any], contract: dict[str, Any]) -> bytes:
    return bytes.fromhex(contract["polygon_authority_mirror"]["sync_certificate_domain_hex"]) + encode_fields(
        contract["polygon_authority_mirror"]["sync_message_fields"], fields,
        enums={"status": {"ACTIVE": 1, "PAUSED": 2}},
    )


def effect_bytes(effect: dict[str, Any], rows: list[list[Any]]) -> bytes:
    return encode_fields(rows, effect, enums={"intent_status": {"QUEUED": 1, "EXECUTED": 2}})


def effect_commitment(record: dict[str, Any], action: dict[str, Any], contract: dict[str, Any]) -> bytes:
    before = effect_bytes(record["action_effects"]["before"], action["effect_fields"])
    after = effect_bytes(record["action_effects"]["after"], action["effect_fields"])
    preimage = (
        bytes.fromhex(contract["domain_bytes"]["destination_effect"]["domain_hex"])
        + _raw_hex(record["action_id_hex"], 32)
        + _uint(action["code"], 1)
        + _raw_hex(record["payload_sha256"], 32)
        + _uint(len(before), 4) + before
        + _uint(len(after), 4) + after
    )
    return sha(preimage)


def executor_call_hash(payload: dict[str, Any], fixture: dict[str, Any], action_code: int,
                       domain_hex: str) -> bytes:
    """Encode the registry-bound executor call with independently fixed widths/order."""
    target_domain = _raw_hex(payload["target_domain_hex"])
    if not 1 <= len(target_domain) <= 32:
        raise ValueError("executor target-domain width")
    preimage = (
        _raw_hex(domain_hex)
        + _uint(fixture["destination_chain_code"], 1)
        + _uint(fixture["destination_chain_id"], 8)
        + _uint(fixture["destination_network_magic"], 4)
        + _uint(len(target_domain), 1) + target_domain
        + _raw_hex(fixture["executor_target_hex"], 20)
        + _raw_hex(fixture["executor_selector_hex"], 4)
        + _uint(action_code, 1)
        + _raw_hex(payload["intent_id_hex"], 32)
        + _raw_hex(payload["action_hash_hex"], 32)
        + _raw_hex(payload["payload_hash_hex"], 32)
        + _uint(payload["policy_epoch"], 8)
        + _uint(payload["intent_nonce"], 8)
    )
    return sha(preimage)


def ack_bytes(fields: dict[str, Any], contract: dict[str, Any]) -> bytes:
    return bytes.fromhex(contract["settlement_ack"]["domain_hex"]) + encode_fields(
        contract["settlement_ack"]["message_fields"], fields
    )
