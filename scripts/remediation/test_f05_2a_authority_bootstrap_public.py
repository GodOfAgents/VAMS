#!/usr/bin/env python3
"""Compiled Plutus V3 conformance harness for F05.2a authority bootstrap.

Every positive, negative, and source-mutant case is evaluated from the applied
public mint entrypoint. No private helper or source-level assertion determines
whether a Cardano transaction is accepted.
"""
from __future__ import annotations

import argparse
import copy
import os
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CARDANO = ROOT / "cardano"
CONTRACT = ROOT / "docs/remediation/m3_f05_design_r2/CONTRACT.json"
AMENDMENT = ROOT / "docs/remediation/m3_f05_2a/AMENDMENT-R1.md"
AMENDMENT_DIGEST = ROOT / "docs/remediation/m3_f05_2a/AMENDMENT-R1.SHA256"
AMENDMENT_R2 = ROOT / "docs/remediation/m3_f05_2a/AMENDMENT-R2.md"
AMENDMENT_R2_DIGEST = ROOT / "docs/remediation/m3_f05_2a/AMENDMENT-R2.SHA256"
FIXTURES = ROOT / "docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json"
TX_SIM_FIXTURES = ROOT / "docs/remediation/m3_f05_2a/tx_sim_r1"
POLICY_SOURCE = "validators/f05_authority_policy.ak"
AUTHORITY_SOURCE = "lib/vams/f05_authority.ak"
POLICY_TITLE = "f05_authority_policy.f05_authority_policy.mint"
STATE_TITLE = "f05_authority_state.f05_authority_state.spend"
POLICY_NAME = "f05_authority_policy"
STATE_NAME = "f05_authority_state"
AUTHORITY_NFT_NAME = b"VAMS-F05-AUTH-V3"
LOVELACE = 10_000_000
R2_POP_DOMAIN = bytes.fromhex(
    "56414d532d4630352d415554484f524954592d47454e455349532d504f502d563100"
)
R2_FIXED_STATE_VALIDATOR_HASH = bytes.fromhex(
    "b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66"
)


class _EphemeralEd25519Key:
    """Test-only Ed25519 key held in anonymous memory; never serialize secrets."""

    def __init__(self) -> None:
        if os.name != "posix" or not hasattr(os, "memfd_create"):
            raise RuntimeError("F05.2a R2 fixtures require Linux memfd support")
        self.fd = os.memfd_create("vams-f05-r2-test-key", flags=0)
        generated = subprocess.run(
            ["openssl", "genpkey", "-algorithm", "ED25519", "-outform", "DER",
             "-out", f"/proc/self/fd/{self.fd}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, pass_fds=(self.fd,),
            check=False,
        )
        if generated.returncode != 0:
            os.close(self.fd)
            self.fd = -1
            raise RuntimeError("ephemeral Ed25519 key generation unavailable")
        os.lseek(self.fd, 0, os.SEEK_SET)
        public = subprocess.run(
            ["openssl", "pkey", "-inform", "DER", "-pubout", "-outform", "DER",
             "-in", f"/proc/self/fd/{self.fd}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, pass_fds=(self.fd,), check=False,
        )
        if public.returncode != 0 or len(public.stdout) != 44 or \
                public.stdout[:12] != bytes.fromhex("302a300506032b6570032100"):
            os.close(self.fd)
            self.fd = -1
            raise RuntimeError("ephemeral Ed25519 public-key extraction failed")
        self.public_key = public.stdout[12:]

    def sign(self, message: bytes) -> bytes:
        if self.fd < 0:
            raise RuntimeError("ephemeral Ed25519 key already released")
        if len(message) != 279:
            raise ValueError("F05.2a R2 PoP message must be exactly 279 bytes")
        message_fd = os.memfd_create("vams-f05-r2-test-message", flags=0)
        try:
            written = os.write(message_fd, message)
            if written != len(message):
                raise RuntimeError("ephemeral PoP message write was incomplete")
            os.lseek(self.fd, 0, os.SEEK_SET)
            os.lseek(message_fd, 0, os.SEEK_SET)
            signed = subprocess.run(
                ["openssl", "pkeyutl", "-sign", "-rawin", "-inkey",
                 f"/proc/self/fd/{self.fd}", "-keyform", "DER", "-in",
                 f"/proc/self/fd/{message_fd}"],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                pass_fds=(self.fd, message_fd), check=False,
            )
            if signed.returncode != 0 or len(signed.stdout) != 64:
                # Never include OpenSSL output in errors; it may contain input details.
                raise RuntimeError("ephemeral Ed25519 signing failed")
            return signed.stdout
        finally:
            os.close(message_fd)

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1


def _canonical_pop_message(seed_hash: bytes, seed_index: int, state_hash: bytes,
                           keys: list[bytes], *, chain_code: int = 2,
                           chain_id: int = 0, network_magic: int = 1,
                           address_network_id: int = 0, epoch: int = 0,
                           require_canonical_keys: bool = True) -> bytes:
    """Independent fixed-width R2 oracle; deliberately no production imports."""
    if len(seed_hash) != 32 or len(state_hash) != 28:
        raise ValueError("bad R2 seed or validator hash width")
    if not 0 <= seed_index <= 65_535 or len(keys) != 5 or any(len(k) != 32 for k in keys):
        raise ValueError("bad R2 seed index or committee-key dimensions")
    if require_canonical_keys and (keys != sorted(keys) or len(set(keys)) != 5):
        raise ValueError("R2 keys must be five distinct raw-byte-sorted values")
    message = b"".join((
        R2_POP_DOMAIN,
        struct.pack(">BQIB", chain_code, chain_id, network_magic, address_network_id),
        seed_hash,
        struct.pack(">H", seed_index),
        state_hash,
        b"\x05",
        b"".join(keys),
        struct.pack(">Q", epoch),
    ))
    if len(R2_POP_DOMAIN) != 34 or len(message) != 279:
        raise AssertionError("R2 PoP message must be exactly 279 bytes")
    return message


def _ephemeral_committee() -> list[_EphemeralEd25519Key]:
    keys: list[_EphemeralEd25519Key] = []
    try:
        for _ in range(5):
            keys.append(_EphemeralEd25519Key())
        keys.sort(key=lambda item: item.public_key)
        if len({item.public_key for item in keys}) != 5:
            raise RuntimeError("ephemeral test-key collision")
        return keys
    except Exception:
        for item in keys:
            item.close()
        raise


def _signers_for_keys(keys: list[bytes], signers: list[_EphemeralEd25519Key]
                      ) -> list[_EphemeralEd25519Key]:
    by_public_key = {item.public_key: item for item in signers}
    try:
        return [by_public_key[key] for key in keys]
    except KeyError as exc:
        raise ValueError("fixture key vector does not map to ephemeral committee") from exc


def _head(major: int, value: int) -> bytes:
    if value < 24:
        return bytes([(major << 5) | value])
    if value < 256:
        return bytes([(major << 5) | 24, value])
    if value < 65_536:
        return bytes([(major << 5) | 25]) + value.to_bytes(2, "big")
    if value < 2**32:
        return bytes([(major << 5) | 26]) + value.to_bytes(4, "big")
    if value < 2**64:
        return bytes([(major << 5) | 27]) + value.to_bytes(8, "big")
    raise ValueError("CBOR integer outside supported fixture range")


def cbor(data: dict[str, Any]) -> bytes:
    """Encode the small Plutus Data subset used by this fixture suite."""
    if set(data) == {"int"}:
        value = data["int"]
        return _head(0, value) if value >= 0 else _head(1, -1 - value)
    if set(data) == {"bytes"}:
        value = bytes.fromhex(data["bytes"])
        return _head(2, len(value)) + value
    if set(data) == {"list"}:
        values = [cbor(item) for item in data["list"]]
        return b"\x9f" + b"".join(values) + b"\xff"
    if set(data) == {"map"}:
        pairs = sorted((cbor(pair["k"]), cbor(pair["v"])) for pair in data["map"])
        return b"\xbf" + b"".join(key + value for key, value in pairs) + b"\xff"
    if set(data) == {"constructor", "fields"}:
        fields = b"\x9f" + b"".join(cbor(item) for item in data["fields"]) + b"\xff"
        index = data["constructor"]
        return _head(6, 121 + index) + fields if index < 7 else _head(6, 1280 + index - 7) + fields
    raise ValueError("invalid Plutus Data fixture shape")


def uplc(data: dict[str, Any]) -> str:
    if set(data) == {"int"}:
        return f"I {data['int']}"
    if set(data) == {"bytes"}:
        return f"B #{data['bytes']}"
    if set(data) == {"list"}:
        return "List [" + ", ".join(uplc(item) for item in data["list"]) + "]"
    if set(data) == {"map"}:
        return "Map [" + ", ".join(
            f"({uplc(pair['k'])}, {uplc(pair['v'])})" for pair in data["map"]
        ) + "]"
    return f"Constr {data['constructor']} [" + ", ".join(
        uplc(item) for item in data["fields"]
    ) + "]"


def integer(value: int) -> dict[str, Any]:
    return {"int": value}


def byte_string(value: bytes) -> dict[str, Any]:
    return {"bytes": value.hex()}


def list_data(values: list[dict[str, Any]]) -> dict[str, Any]:
    return {"list": values}


def constr(index: int, *fields: dict[str, Any]) -> dict[str, Any]:
    return {"constructor": index, "fields": list(fields)}


def map_data(pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    return {"map": [{"k": key, "v": value} for key, value in pairs]}


def _output_reference(tx_hash: bytes, index: int) -> dict[str, Any]:
    # Frozen blueprint defines OutputReference as constructor 0 with the
    # transaction-id ByteArray and output-index Int fields directly.
    return constr(0, byte_string(tx_hash), integer(index))


def _value(lovelace: int = 0,
           native_assets: list[tuple[bytes, bytes, int]] | None = None) -> dict[str, Any]:
    # Cardano Value always separates ADA (empty policy/name) from native assets.
    entries: dict[bytes, dict[bytes, int]] = {b"": {b"": lovelace}}
    for policy_id, asset_name, amount in native_assets or []:
        entries.setdefault(policy_id, {})[asset_name] = amount
    return map_data([
        (byte_string(policy_id), map_data([
            (byte_string(asset_name), integer(amount))
            for asset_name, amount in sorted(tokens.items())
        ]))
        for policy_id, tokens in sorted(entries.items())
    ])


def _address(credential_hash: bytes, *, script: bool, stake: bytes | None = None) -> dict[str, Any]:
    credential = constr(1 if script else 0, byte_string(credential_hash))
    stake_credential = constr(1) if stake is None else constr(0, constr(0, byte_string(stake)))
    return constr(0, credential, stake_credential)


def _output(address: dict[str, Any], value: dict[str, Any], datum: dict[str, Any]) -> dict[str, Any]:
    return constr(0, address, value, datum, constr(1))  # no reference script


def _input(reference: dict[str, Any], address: dict[str, Any], ada: int) -> dict[str, Any]:
    return constr(0, reference, _output(address, _value(lovelace=ada), constr(0)))


def _pending_none() -> dict[str, Any]:
    return constr(0, constr(0), integer(0), integer(0), integer(0), integer(0),
                  integer(0), byte_string(bytes(160)))


def _authority_state(genesis_hash: bytes, genesis_index: int,
                     keys: list[bytes], *, schema: int = 3, epoch: int = 0,
                     threshold: int = 3, status: int = 0,
                     pending: dict[str, Any] | None = None) -> dict[str, Any]:
    return constr(0, integer(schema), byte_string(genesis_hash), integer(genesis_index),
                  integer(epoch), list_data([byte_string(key) for key in keys]),
                  integer(threshold), constr(status), pending or _pending_none())


def _script_datum(value: dict[str, Any] | None) -> dict[str, Any]:
    return constr(0) if value is None else constr(2, value)  # None or InlineDatum


def _base_context(policy_id: bytes, state_credential: bytes, genesis_hash: bytes,
                  genesis_index: int, keys: list[bytes],
                  proofs: list[bytes]) -> dict[str, Any]:
    seed_ref = _output_reference(genesis_hash, genesis_index)
    key_addr = _address(bytes.fromhex("61" * 28), script=False)
    sponsor_addr = _address(bytes.fromhex("62" * 28), script=False)
    state_addr = _address(state_credential, script=True)
    state = _authority_state(genesis_hash, genesis_index, keys)
    state_value = _value(LOVELACE, [(policy_id, AUTHORITY_NFT_NAME, 1)])
    outputs = [
        _output(state_addr, state_value, _script_datum(state)),
        # A valid datum-bearing non-state change output lets the inline-datum
        # guard mutation prove that it is specifically the state output datum
        # that is required.
        _output(sponsor_addr, _value(lovelace=6_000_000), _script_datum(state)),
    ]
    inputs = [
        _input(seed_ref, key_addr, 2_000_000),
        _input(_output_reference(bytes.fromhex("bb" * 32), 3), key_addr, 15_000_000),
    ]
    minted = map_data([(byte_string(policy_id), map_data([
        (byte_string(AUTHORITY_NFT_NAME), integer(1))
    ]))])
    finite = lambda ms: constr(0, constr(1, integer(ms)), constr(1))
    tx_info = constr(0,
        list_data(inputs), list_data([]), list_data(outputs), integer(1_000_000), minted,
        list_data([]), map_data([]), constr(0, finite(1_700_000_000_000), finite(1_700_000_030_000)),
        list_data([byte_string(bytes.fromhex("63" * 28))]), map_data([]), map_data([]),
        byte_string(bytes.fromhex("cc" * 32)), map_data([]), list_data([]), constr(1), constr(1))
    redeemer = constr(0, list_data([byte_string(proof) for proof in proofs]))
    purpose = constr(0, byte_string(policy_id))  # Minting policy
    return constr(0, tx_info, redeemer, purpose)


def _set_output_value(context: dict[str, Any], output_index: int,
                      value: dict[str, Any]) -> None:
    context["fields"][0]["fields"][2]["list"][output_index]["fields"][1] = value


def _set_state(context: dict[str, Any], state: dict[str, Any] | None,
               *, datum_kind: str = "inline") -> None:
    outputs = context["fields"][0]["fields"][2]["list"]
    if datum_kind == "none":
        outputs[0]["fields"][2] = constr(0)
    elif datum_kind == "hash":
        outputs[0]["fields"][2] = constr(1, byte_string(bytes.fromhex("dd" * 32)))
    else:
        outputs[0]["fields"][2] = _script_datum(state)


def _set_proofs(context: dict[str, Any], proofs: list[bytes]) -> None:
    context["fields"][1] = constr(0, list_data([byte_string(proof) for proof in proofs]))


def _map_mint(context: dict[str, Any], policy_id: bytes,
              assets: list[tuple[bytes, int]]) -> None:
    context["fields"][0]["fields"][4] = map_data([
        (byte_string(policy_id), map_data([
            (byte_string(name), integer(quantity)) for name, quantity in assets
        ]))
    ])


def _rebind_policy_id(context: dict[str, Any], old_id: bytes, new_id: bytes) -> None:
    """Keep the synthetic transaction's mint/value/purpose aligned to a mutant."""
    tx_fields = context["fields"][0]["fields"]
    mint = tx_fields[4]
    for policy in mint["map"]:
        if bytes.fromhex(policy["k"]["bytes"]) == old_id:
            policy["k"] = byte_string(new_id)
    mint["map"].sort(key=lambda pair: bytes.fromhex(pair["k"]["bytes"]))
    for output in tx_fields[2]["list"]:
        value = output["fields"][1]
        for policy in value["map"]:
            if bytes.fromhex(policy["k"]["bytes"]) == old_id:
                policy["k"] = byte_string(new_id)
        # Aiken's dict lookup assumes ascending policy keys after rebinding.
        value["map"].sort(key=lambda pair: bytes.fromhex(pair["k"]["bytes"]))
    context["fields"][2]["fields"][0] = byte_string(new_id)


def _assert_unconditional_context_binding(
    case_id: str, context: dict[str, Any], old_id: bytes, target_id: bytes,
) -> None:
    """Check synthetic context identity while preserving the wrong-mint case.

    This is a ScriptContext check only; it does not attest a transaction's V3
    witness, funding signatures, ledger admission, or a Plutus verdict.
    """
    tx = context["fields"][0]["fields"]
    purpose_id = bytes.fromhex(context["fields"][2]["fields"][0]["bytes"])
    if purpose_id != target_id:
        raise AssertionError(f"unconditional-success purpose ID mismatch: {case_id}")
    mint_ids = [bytes.fromhex(pair["k"]["bytes"]) for pair in tx[4]["map"]]
    expected_mint = bytes.fromhex("ee" * 28) if case_id == "mint_wrong_policy" else target_id
    if mint_ids != [expected_mint]:
        raise AssertionError(f"unconditional-success mint ID mismatch: {case_id}")
    for output in tx[2]["list"]:
        policy_ids = [bytes.fromhex(pair["k"]["bytes"]) for pair in output["fields"][1]["map"]]
        if old_id != target_id and old_id in policy_ids:
            raise AssertionError(f"unconditional-success stale output ID: {case_id}")


def _replace_applied_keys(parameters: dict[str, Any], keys: list[bytes]) -> None:
    parameters["initial_keys"] = list_data([byte_string(key) for key in keys])


def _mutate(case_id: str, context: dict[str, Any], parameters: dict[str, Any],
            signers: list[_EphemeralEd25519Key]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply one case mutation; return context and possible param overrides."""
    ctx = copy.deepcopy(context)
    params = copy.deepcopy(parameters)
    tx = ctx["fields"][0]["fields"]
    outputs = tx[2]["list"]
    seed_fields = params["genesis_ref"]["fields"]
    canonical_seed_hash = bytes.fromhex(seed_fields[0]["bytes"])
    canonical_seed_index = seed_fields[1]["int"]
    canonical_keys = [bytes.fromhex(value) for value in fixture_keys(params)]
    state = _authority_state(canonical_seed_hash, canonical_seed_index, canonical_keys)
    if case_id == "seed_missing":
        tx[0]["list"] = tx[0]["list"][1:]
    elif case_id == "seed_duplicate":
        tx[0]["list"].append(copy.deepcopy(tx[0]["list"][0]))
    elif case_id in {"seed_datum_hash", "datum_seed_hash"}:
        state["fields"][1] = byte_string(bytes.fromhex("ab" * 32)); _set_state(ctx, state)
    elif case_id in {"seed_datum_index", "datum_seed_index"}:
        state["fields"][2] = integer(8); _set_state(ctx, state)
    elif case_id == "applied_genesis_parameter":
        params["genesis_ref"] = _output_reference(bytes.fromhex("ab" * 32), 7)
    elif case_id == "applied_keys_parameter":
        changed = [bytes.fromhex(value) for value in fixture_keys(parameters)]
        changed[0] = bytes(32)
        _replace_applied_keys(params, changed)
    elif case_id in {"applied_keys_bad_count", "applied_keys_bad_length", "applied_keys_duplicate", "applied_keys_unsorted"}:
        changed = [bytes.fromhex(value) for value in fixture_keys(parameters)]
        if case_id == "applied_keys_bad_count":
            changed.append(bytes.fromhex("06" * 32))
        elif case_id == "applied_keys_bad_length":
            changed[0] = bytes.fromhex("01" * 31)
        elif case_id == "applied_keys_duplicate":
            changed[1] = changed[0]
        else:
            changed[1], changed[2] = changed[2], changed[1]
        _replace_applied_keys(params, changed)
    elif case_id == "mint_wrong_policy":
        wrong = bytes.fromhex("ee" * 28); _map_mint(ctx, wrong, [(AUTHORITY_NFT_NAME, 1)])
    elif case_id == "mint_wrong_name":
        _map_mint(ctx, bytes.fromhex(parameters["policy_id"]), [(b"wrong", 1)])
    elif case_id == "mint_quantity_two":
        _map_mint(ctx, bytes.fromhex(parameters["policy_id"]), [(AUTHORITY_NFT_NAME, 2)])
    elif case_id == "mint_extra_name":
        _map_mint(ctx, bytes.fromhex(parameters["policy_id"]), [(AUTHORITY_NFT_NAME, 1), (b"extra", 1)])
    elif case_id == "output_wrong_payment_credential":
        outputs[0]["fields"][0] = _address(bytes.fromhex("65" * 28), script=True)
        outputs.append(_output(
            _address(bytes.fromhex(parameters["state_credential"]), script=True),
            _value(lovelace=2_000_000), constr(0),
        ))
    elif case_id == "output_stake_credential":
        outputs[0]["fields"][0] = _address(bytes.fromhex(parameters["state_credential"]), script=True, stake=bytes.fromhex("66" * 28))
    elif case_id == "datum_missing":
        _set_state(ctx, None, datum_kind="none")
    elif case_id == "datum_hash_only":
        _set_state(ctx, None, datum_kind="hash")
    elif case_id == "datum_unknown_constructor":
        _set_state(ctx, constr(7));
    elif case_id == "datum_schema_version":
        state["fields"][0] = integer(2); _set_state(ctx, state)
    elif case_id == "datum_epoch":
        state["fields"][3] = integer(1); _set_state(ctx, state)
    elif case_id == "datum_key_count":
        state["fields"][4]["list"].append(byte_string(bytes.fromhex("06" * 32))); _set_state(ctx, state)
    elif case_id == "datum_key_length":
        state["fields"][4]["list"][0] = byte_string(bytes.fromhex("01" * 31)); _set_state(ctx, state)
    elif case_id == "datum_duplicate_key":
        state["fields"][4]["list"][1] = copy.deepcopy(state["fields"][4]["list"][0]); _set_state(ctx, state)
    elif case_id == "datum_key_order":
        state["fields"][4]["list"][1], state["fields"][4]["list"][2] = state["fields"][4]["list"][2], state["fields"][4]["list"][1]; _set_state(ctx, state)
    elif case_id == "datum_key_binding":
        state["fields"][4]["list"][0] = byte_string(bytes(32)); _set_state(ctx, state)
    elif case_id == "datum_threshold":
        state["fields"][5] = integer(4); _set_state(ctx, state)
    elif case_id == "datum_status":
        state["fields"][6] = constr(1); _set_state(ctx, state)
    elif case_id == "datum_pending_kind":
        pending = state["fields"][7]; pending["fields"][0] = constr(1); pending["fields"][1] = integer(0); pending["fields"][2] = integer(1); pending["fields"][5] = integer(5); pending["fields"][6] = byte_string(bytes.fromhex("01" * 32) + bytes(128)); _set_state(ctx, state)
    elif case_id == "datum_pending_noncanonical":
        state["fields"][7]["fields"][6] = byte_string(bytes.fromhex("01" + "00" * 159)); _set_state(ctx, state)
    elif case_id in {"authority_value_minus_one", "fee_diversion"}:
        _set_output_value(ctx, 0, _value(LOVELACE - 1, [(bytes.fromhex(parameters["policy_id"]), AUTHORITY_NFT_NAME, 1)]))
        if case_id == "fee_diversion":
            tx[3] = integer(1_000_001)
    elif case_id == "authority_value_plus_one":
        _set_output_value(ctx, 0, _value(LOVELACE + 1, [(bytes.fromhex(parameters["policy_id"]), AUTHORITY_NFT_NAME, 1)]))
    elif case_id == "authority_extra_native_asset":
        _set_output_value(ctx, 0, _value(LOVELACE, [(bytes.fromhex(parameters["policy_id"]), AUTHORITY_NFT_NAME, 1), (bytes.fromhex("ef" * 28), b"x", 1)]))
    elif case_id == "authority_output_duplicate_nft":
        duplicate = copy.deepcopy(outputs[0])
        duplicate["fields"][0] = _address(bytes.fromhex("65" * 28), script=True)
        outputs.append(duplicate)
    elif case_id == "authority_output_extra_target":
        outputs.append(_output(_address(bytes.fromhex(parameters["state_credential"]), script=True), _value(lovelace=2_000_000), constr(0)))
    elif case_id == "authority_output_quantity_two":
        _set_output_value(ctx, 0, _value(LOVELACE, [(bytes.fromhex(parameters["policy_id"]), AUTHORITY_NFT_NAME, 2)]))
    elif case_id == "authority_output_missing":
        del outputs[0]
    elif case_id in {"r2_proof_missing", "r2_proof_extra"}:
        current = [bytes.fromhex(item["bytes"]) for item in ctx["fields"][1]["fields"][0]["list"]]
        _set_proofs(ctx, current[:-1] if case_id == "r2_proof_missing" else current + [current[-1]])
    elif case_id.startswith("r2_invalid_proof_"):
        position = int(case_id.rsplit("_", 1)[1])
        current = [bytes.fromhex(item["bytes"]) for item in ctx["fields"][1]["fields"][0]["list"]]
        changed = bytearray(current[position])
        changed[0] ^= 1
        current[position] = bytes(changed)
        _set_proofs(ctx, current)
    elif case_id == "r2_wrong_key_pairing":
        current = [bytes.fromhex(item["bytes"]) for item in ctx["fields"][1]["fields"][0]["list"]]
        _set_proofs(ctx, list(reversed(current)))
    elif case_id.startswith("r2_signature_for_"):
        base_hash = bytes.fromhex(params["state_validator_hash"])
        kwargs: dict[str, int] = {}
        seed_hash = canonical_seed_hash
        seed_index = canonical_seed_index
        if case_id == "r2_signature_for_other_seed":
            seed_hash = bytes.fromhex("ad" * 32)
        elif case_id == "r2_signature_for_other_network":
            kwargs["network_magic"] = 0
        elif case_id == "r2_signature_for_other_validator_hash":
            base_hash = bytes.fromhex("cd" * 28)
        elif case_id == "r2_signature_for_other_epoch":
            kwargs["epoch"] = 1
        else:
            raise ValueError(f"unknown R2 signed-message case {case_id}")
        signed_message = _canonical_pop_message(
            seed_hash, seed_index, base_hash, canonical_keys, **kwargs,
        )
        _set_proofs(ctx, [key.sign(signed_message) for key in signers])
    elif case_id == "r2_swapped_datum_keys":
        state["fields"][4]["list"][0], state["fields"][4]["list"][1] = state["fields"][4]["list"][1], state["fields"][4]["list"][0]
        _set_state(ctx, state)
    elif case_id == "r2_duplicate_datum_key":
        state["fields"][4]["list"][1] = copy.deepcopy(state["fields"][4]["list"][0])
        _set_state(ctx, state)
    elif case_id == "r2_wrong_state_address":
        outputs[0]["fields"][0] = _address(bytes.fromhex("65" * 28), script=True)
        # Keep target-output cardinality satisfied independently of the
        # payment-credential-equality guard, so its removal is testable.
        outputs.append(_output(
            _address(bytes.fromhex(params["state_validator_hash"]), script=True),
            _value(lovelace=2_000_000), constr(0),
        ))
    else:
        raise ValueError(f"unknown fixture case {case_id}")
    return ctx, params


def _applied_case_context(
    case_id: str, params: dict[str, Any], policy_id: bytes,
    state_credential: bytes, genesis_hash: bytes, genesis_index: int,
    keys: list[bytes], proofs: list[bytes], signers: list[_EphemeralEd25519Key],
) -> dict[str, Any]:
    datum_keys = keys
    if case_id in {"applied_keys_bad_count", "applied_keys_bad_length",
                   "applied_keys_duplicate", "applied_keys_unsorted"}:
        datum_keys = [bytes.fromhex(value) for value in fixture_keys(params)]
    if case_id in {"applied_keys_duplicate", "applied_keys_unsorted"}:
        proof_signers = _signers_for_keys(datum_keys, signers)
        variant_message = _canonical_pop_message(
            genesis_hash, genesis_index, state_credential, datum_keys,
            require_canonical_keys=False,
        )
        variant_proofs = [key.sign(variant_message) for key in proof_signers]
    else:
        variant_proofs = proofs
    return _base_context(policy_id, state_credential, genesis_hash,
                         genesis_index, datum_keys, variant_proofs)


def _unconditional_case_target(
    case_id: str, valid: dict[str, Any], base_parameters: dict[str, Any],
    base_policy_id: bytes, base_mutant: dict[str, Any], aiken: Path,
    workroot: Path, signers: list[_EphemeralEd25519Key], keys: list[bytes],
    proofs: list[bytes], genesis_hash: bytes, genesis_index: int,
    state_credential: bytes,
) -> tuple[bytes, bytes, dict[str, Any]]:
    invalid, params = _mutate(case_id, valid, base_parameters, signers)
    if case_id.startswith("applied_"):
        variant = _compile(
            CARDANO, aiken, workroot / f"mutant-all-param-{case_id}",
            params, "unconditional_success",
        )
        invalid = _applied_case_context(
            case_id, params, variant["policy_id"], state_credential,
            genesis_hash, genesis_index, keys, proofs, signers,
        )
        return variant["code"], variant["policy_id"], invalid
    _rebind_policy_id(invalid, base_policy_id, base_mutant["policy_id"])
    return base_mutant["code"], base_mutant["policy_id"], invalid


def _validate_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    fixture = json.loads(FIXTURES.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    amendment_hash = hashlib.sha256(AMENDMENT.read_bytes()).hexdigest()
    recorded_hash = AMENDMENT_DIGEST.read_text(encoding="utf-8").split()[0].lower()
    assert amendment_hash == recorded_hash == fixture["value_amendment"]["sha256"]
    amendment_r2_hash = hashlib.sha256(AMENDMENT_R2.read_bytes()).hexdigest()
    r2_recorded_hash = AMENDMENT_R2_DIGEST.read_text(encoding="utf-8").split()[0].lower()
    assert amendment_r2_hash == r2_recorded_hash == fixture["bootstrap_amendment_r2"]["sha256"]
    assert contract["authority"]["state_type"] == "AuthorityStateV3"
    assert contract["authority"]["version"] == 3
    assert contract["authority"]["initial_epoch"] == 0
    assert contract["authority"]["threshold"] == 3
    assert contract["authority"]["ordered_unique_keys"] == 5
    assert contract["authority_preimages"]["status_encoding"]["ACTIVE"] == 1
    assert contract["authority_preimages"]["none_pending_encoding"].startswith("kind=0;")
    assert fixture["value_amendment"]["authority_output_lovelace"] == LOVELACE
    assert fixture["bootstrap_amendment_r2"]["expected_state_validator_script_hash"] == R2_FIXED_STATE_VALIDATOR_HASH.hex()
    assert fixture["bootstrap_amendment_r2"]["proof_message_total_bytes"] == 279
    return fixture, contract


def _run_tx_sim_canaries(aiken: Path) -> dict[str, Any]:
    manifest_path = TX_SIM_FIXTURES / "CANARY-MANIFEST.json"
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != "91c7bc46476a391c3ea3e3012b2f9174a1b87f6e0253ce6167b4c7b96e47f95d":
        raise SystemExit("transaction canary manifest digest mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_cases = [
        ("valid", "valid.tx.cbor", 0, ["Parsing script context", "Evaluating Mint[0]"]),
        ("invalid_signature", "invalid_signature.tx.cbor", 1,
         ["Parsing script context", "Evaluating Mint[0]", "failed script execution"]),
        ("wrong_credential", "wrong_credential.tx.cbor", 1,
         ["Parsing script context", "Evaluating Mint[0]", "failed script execution"]),
    ]
    actual_cases = [(c.get("id"), c.get("transaction"), c.get("expected_exit"), c.get("required_output"))
                    for c in manifest.get("canaries", [])]
    if actual_cases != expected_cases:
        raise SystemExit("transaction canary case set/order/expectations mismatch")
    if manifest.get("schema_version") != "f05-2a-typed-tx-sim-canaries-r1" or \
            manifest.get("status") != "transaction-canaries-only; registry-not-run":
        raise SystemExit("transaction canary manifest contract mismatch")
    version = _run([str(aiken), "--version"], ROOT).stdout.strip()
    binary_hash = hashlib.sha256(aiken.read_bytes()).hexdigest()
    runtime = next((entry for entry in manifest["runtimes"].values()
                    if entry["version"] == version and entry["sha256"] == binary_hash), None)
    if runtime is None:
        raise SystemExit("Aiken runtime is not one of the checksum-pinned canary runtimes")
    expected = {
        "applied-policy.cbor": "fc8726cff89172d4944e257a2eb2659d35363c8e5a4d423ed8a2112eb5af7e59",
        "raw_inputs.cbor": "4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe",
        "raw_outputs.cbor": "9cdf345a785f51763bdb43f1b1ba0c20b5545051f03051e6a7bf726ea128c56a",
    }
    for name, digest in expected.items():
        if hashlib.sha256((TX_SIM_FIXTURES / name).read_bytes()).hexdigest() != digest:
            raise SystemExit(f"transaction canary artifact digest mismatch: {name}")
    results = []
    for case in manifest["canaries"]:
        tx_path = TX_SIM_FIXTURES / case["transaction"]
        if hashlib.sha256(tx_path.read_bytes()).hexdigest() != case["sha256"]:
            raise SystemExit(f"transaction canary digest mismatch: {case['id']}")
        completed = subprocess.run(
            [str(aiken), "tx", "simulate", "--cbor", str(tx_path),
             str(TX_SIM_FIXTURES / "raw_inputs.cbor"),
             str(TX_SIM_FIXTURES / "raw_outputs.cbor")],
            cwd=ROOT, capture_output=True, text=True, timeout=90, check=False,
        )
        output = completed.stdout + completed.stderr
        required = case["required_output"]
        ok = completed.returncode == case["expected_exit"] and all(token in output for token in required)
        if not ok:
            raise AssertionError(f"tx-sim canary failed: {case['id']} (exit {completed.returncode})")
        results.append({"id": case["id"], "exit": completed.returncode,
                        "target_invoked": "Evaluating Mint[0]" in output, "result": "pass"})
    return {"status": "pass", "mode": "transaction_canaries_only",
            "runtime": version, "runtime_sha256": binary_hash, "canaries": results,
            "registry": "not_run_pending_independent_reachability_review"}

def _run_tx_sim_r3_canaries(aiken: Path) -> dict[str, Any]:
    """Run one frozen positive and one negative through the sealed R3 runner."""
    manifest_path = TX_SIM_FIXTURES / "CANARY-MANIFEST.json"
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != "91c7bc46476a391c3ea3e3012b2f9174a1b87f6e0253ce6167b4c7b96e47f95d":
        raise SystemExit("transaction canary manifest digest mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    policy_id = manifest.get("target", {}).get("applied_policy_id")
    expected_cases = [
        ("valid", "valid.tx.cbor", 0, "script_accepted"),
        ("invalid_signature", "invalid_signature.tx.cbor", 1, "compiled_evaluation"),
    ]
    actual_cases = [(case.get("id"), case.get("transaction"), case.get("expected_exit"))
                    for case in manifest.get("canaries", [])]
    if actual_cases != [(row[0], row[1], row[2]) for row in expected_cases] + [
            ("wrong_credential", "wrong_credential.tx.cbor", 1)]:
        raise SystemExit("transaction canary case set/order/expectations mismatch")
    if manifest.get("schema_version") != "f05-2a-typed-tx-sim-canaries-r1" or \
            manifest.get("status") != "transaction-canaries-only; registry-not-run":
        raise SystemExit("transaction canary manifest contract mismatch")
    version = _run([str(aiken), "--version"], ROOT).stdout.strip()
    binary_hash = hashlib.sha256(aiken.read_bytes()).hexdigest()
    runtime = next((entry for entry in manifest["runtimes"].values()
                    if entry["version"] == version and entry["sha256"] == binary_hash), None)
    if runtime is None:
        raise SystemExit("Aiken runtime is not one of the checksum-pinned canary runtimes")
    if policy_id != "9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731":
        raise SystemExit("transaction canary applied-policy ID mismatch")
    expected_artifacts = {
        "applied-policy.cbor": manifest["target"]["applied_policy_cbor"]["sha256"],
        "raw_inputs.cbor": manifest["shared_vectors"]["raw_inputs.cbor"],
        "raw_outputs.cbor": manifest["shared_vectors"]["raw_outputs.cbor"],
    }
    for name, digest in expected_artifacts.items():
        if hashlib.sha256((TX_SIM_FIXTURES / name).read_bytes()).hexdigest() != digest:
            raise SystemExit(f"transaction canary artifact digest mismatch: {name}")
    runner = ROOT / "scripts/remediation/f05_2a_tx_sim_runner_r3.py"
    results = []
    for case, expected in zip(manifest["canaries"][:2], expected_cases, strict=True):
        case_id, tx_name, child_exit, stage = expected
        tx_path = TX_SIM_FIXTURES / tx_name
        tx_digest = hashlib.sha256(tx_path.read_bytes()).hexdigest()
        if case.get("id") != case_id or case.get("transaction") != tx_name or \
                case.get("expected_exit") != child_exit or case.get("sha256") != tx_digest:
            raise SystemExit(f"transaction canary digest/contract mismatch: {case_id}")
        command = [
            sys.executable, str(runner), "--aiken", str(aiken), "--tx", str(tx_path),
            "--raw-inputs", str(TX_SIM_FIXTURES / "raw_inputs.cbor"),
            "--raw-outputs", str(TX_SIM_FIXTURES / "raw_outputs.cbor"),
            "--policy-id", policy_id,
        ]
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                   timeout=100, check=False)
        if completed.returncode != 0:
            raise AssertionError(f"snapshot transaction canary wrapper failed: {case_id}")
        try:
            observed = json.loads(completed.stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            raise AssertionError(f"snapshot transaction canary result invalid: {case_id}") from exc
        expected_hashes = {
            "transaction": tx_digest,
            "raw_inputs": manifest["shared_vectors"]["raw_inputs.cbor"],
            "raw_outputs": manifest["shared_vectors"]["raw_outputs.cbor"],
        }
        binding = observed.get("target_mint_binding", {})
        cleanup = observed.get("cleanup", {})
        simulator_result = observed.get("simulator_result", {})
        if (observed.get("schema_version") != "f05-2a-tx-sim-run-result-r3" or
                observed.get("wrapper_exit_code") != 0 or
                observed.get("simulator_child_exit") != child_exit or
                simulator_result != {"stage": stage, "target_script_invoked": True} or
                observed.get("submitted_sha256") != expected_hashes or
                binding != {"expected_policy_id": policy_id, "policy_ids": [policy_id],
                            "compiled_script_hash": policy_id} or
                cleanup != {"child_reaped": True, "process_group_empty": True,
                            "snapshot_descriptors_closed": True, "status": "clean"}):
            raise AssertionError(f"snapshot transaction canary classification/binding failed: {case_id}")
        results.append({
            "id": case_id, "wrapper_exit": completed.returncode,
            "simulator_child_exit": child_exit, "result": stage,
            "target_invoked": True, "policy_id": policy_id,
            "submitted_sha256": expected_hashes, "cleanup": "clean",
        })
    return {"status": "pass", "mode": "snapshot_bound_transaction_canaries_only",
            "runtime": version, "runtime_sha256": binary_hash, "canaries": results,
            "registry": "not_run", "evidence_class": "synthetic_local_transaction_simulator"}


def fixture_keys(parameters: dict[str, Any]) -> list[str]:
    return [item["bytes"] for item in parameters["initial_keys"]["list"]]


def _run(command: list[str], cwd: Path, *, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        tail = (result.stderr + "\n" + result.stdout).strip().splitlines()[-12:]
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command[:4])}: {' | '.join(tail)}")
    return result


def _replace_once(source: Path, old: str, new: str) -> None:
    content = source.read_text(encoding="utf-8")
    if content.count(old) != 1:
        raise RuntimeError(f"mutation guard anchor must occur exactly once: {old[:80]!r}")
    source.write_text(content.replace(old, new, 1), encoding="utf-8")


def _mutant_source(cardano_root: Path, mutation: str) -> None:
    policy = cardano_root / POLICY_SOURCE
    authority = cardano_root / AUTHORITY_SOURCE
    policy_changes: dict[str, tuple[str, str]] = {
        "remove_seed_guard": ("expect count_seed_input(tx.inputs, genesis_ref) == 1", "expect True"),
        "remove_target_output_cardinality_guard": ("expect count_state_credential_outputs(tx.outputs, state_validator_script_hash) == 1", "expect True"),
        "remove_exact_mint_guard": ("""expect
    dict.to_pairs(assets.tokens(tx.mint, policy_id)) == [
      Pair(authority_asset_name, 1),
    ]""", "expect True"),
        "remove_state_validator_credential_binding": ("expect authority_output.address.payment_credential == Script(state_validator_script_hash)", "expect True"),
        "remove_no_stake_credential_guard": ("expect authority_output.address.stake_credential == None", "expect True"),
        "remove_singleton_quantity_guard": ("expect assets.quantity_of(authority_output.value, policy_id, authority_asset_name) == 1", "expect True"),
        "remove_exact_lovelace_guard": ("expect assets.lovelace_of(authority_output.value) == authority_initial_lovelace", "expect True"),
        "remove_no_extra_asset_guard": ("expect only_authority_nft(authority_output.value, policy_id)", "expect True"),
        "remove_inline_datum_guard": ("expect InlineDatum(raw_datum) = authority_output.datum", "expect InlineDatum(raw_datum) = sponsor_datum(tx.outputs, state_validator_script_hash)"),
    }
    if mutation == "unconditional_success":
        old = """    let BootstrapAuthority { proofs } = redeemer
    validate_bootstrap(genesis_ref, initial_keys, proofs, policy_id, tx)"""
        _replace_once(
            policy,
            old,
            "    let BootstrapAuthority { proofs: _ } = redeemer\n    True",
        )
        return
    if mutation == "wrong_state_validator_hash_constant":
        _replace_once(
            policy,
            'const state_validator_script_hash: ByteArray = #"b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66"',
            'const state_validator_script_hash: ByteArray = #"00000000000000000000000000000000000000000000000000000000"',
        )
        return
    if mutation == "remove_bootstrap_proof_of_possession_verification":
        _replace_once(
            policy,
            "valid_bootstrap_proofs(initial_keys, proofs, bootstrap_message)",
            "True",
        )
        return
    if mutation in policy_changes:
        old, new = policy_changes[mutation]
        _replace_once(policy, old, new)
        if mutation == "remove_inline_datum_guard":
            helper = """fn count_seed_input(inputs: List<Input>, seed_ref: OutputReference) -> Int {"""
            insertion = """fn sponsor_datum(outputs: List<Output>, state_validator_script_hash: ByteArray) -> Datum {
  expect Some(output) = list.find(outputs, fn(output) {
    output.address.payment_credential != Script(state_validator_script_hash)
  })
  output.datum
}

"""
            _replace_once(policy, helper, insertion + helper)
            # Import Datum only in the disposable mutant.
            _replace_once(policy, "InlineDatum, Input, Output, OutputReference, Transaction", "Datum, InlineDatum, Input, Output, OutputReference, Transaction")
        return
    field_changes = {
        "remove_schema_version_guard": ("state.schema_version == authority_schema_version", "True"),
        "remove_seed_hash_guard": ("state.bootstrap_tx_hash == genesis_ref.transaction_id", "True"),
        "remove_seed_index_guard": ("state.bootstrap_output_index == genesis_ref.output_index", "True"),
        "remove_epoch_guard": ("state.epoch == 0", "True"),
        "remove_threshold_guard": ("state.threshold == authority_threshold", "True"),
        "remove_status_guard": ("state.status == AuthorityActive", "True"),
        "remove_key_binding_guard": ("state.ordered_keys == initial_keys", "True"),
        "remove_key_order_guard": ("bytearray.to_int_big_endian(second) < bytearray.to_int_big_endian(third)", "True"),
        "remove_key_size_guard": ("bytearray.length(first) == authority_key_bytes", "True"),
        "remove_key_uniqueness_order_guard": ("bytearray.to_int_big_endian(first) < bytearray.to_int_big_endian(second)", "True"),
        "remove_pending_canonicality_guard": ("canonical_none(state.pending)", "True"),
    }
    if mutation == "remove_pending_hash_guard":
        _replace_once(authority, "pending_hash(state.pending) == zero_bytes(authority_hash_bytes)", "True")
        return
    if mutation == "remove_key_count_guard":
        old = """fn valid_ordered_keys(keys: List<ByteArray>) -> Bool {
  when keys is [first, second, third, fourth, fifth] {"""
        new = """fn valid_ordered_keys(keys: List<ByteArray>) -> Bool {
  when keys is [first, second, third, fourth, fifth, _] {"""
        _replace_once(authority, old, new)
        return
    if mutation in field_changes:
        old, new = field_changes[mutation]
        _replace_once(authority, old, new)
        return
    raise ValueError(f"unknown source mutation {mutation}")


def _compile(cardano_source: Path, aiken: Path, work: Path,
             parameters: dict[str, Any], mutation: str | None = None) -> dict[str, Any]:
    work.mkdir(parents=True, exist_ok=True)
    cardano = work / "cardano"
    shutil.copytree(cardano_source, cardano)
    # The read-only dossier snapshot flattens canonical `cardano/lib/vams/**`
    # to `cardano/vams/**`. Normalize only this disposable compile copy back
    # to Aiken's project module layout; never alter the source snapshot.
    flattened_vams = cardano / "vams"
    canonical_vams = cardano / "lib" / "vams"
    if flattened_vams.exists():
        if canonical_vams.exists():
            raise RuntimeError("ambiguous flattened and canonical vams module trees")
        canonical_vams.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(flattened_vams), str(canonical_vams))
    elif not canonical_vams.is_dir():
        raise RuntimeError("candidate authority modules missing from staged Aiken project")
    if mutation:
        _mutant_source(cardano, mutation)
    _run([str(aiken), "build"], cardano)
    blueprint_path = cardano / "plutus.json"
    blueprint = json.loads(blueprint_path.read_text(encoding="utf-8"))
    validators = {item["title"]: item for item in blueprint["validators"]}
    if POLICY_TITLE not in validators or STATE_TITLE not in validators:
        raise RuntimeError("public F05.2a mint/state entrypoint missing from generated blueprint")
    state_credential = bytes.fromhex(validators[STATE_TITLE]["hash"])
    policy_source = (cardano / POLICY_SOURCE).read_text(encoding="utf-8")
    constant = re.search(
        r'const state_validator_script_hash: ByteArray = #"([0-9a-f]{56})"',
        policy_source,
    )
    if constant is None:
        raise RuntimeError("compiled policy lacks its generated state-validator hash constant")
    expected_credential = bytes.fromhex(constant.group(1))
    if mutation != "wrong_state_validator_hash_constant" and expected_credential != state_credential:
        raise RuntimeError("generated state-validator hash constant does not match compiled validator")
    params = [parameters["genesis_ref"], parameters["initial_keys"]]
    previous = blueprint_path
    for index, value in enumerate(params, 1):
        output = work / f"applied-{index}.json"
        _run([
            str(aiken), "blueprint", "apply", "-i", str(previous), "-o", str(output),
            "-m", POLICY_NAME, "-v", POLICY_NAME, cbor(value).hex(),
        ], cardano)
        previous = output
    applied = json.loads(previous.read_text(encoding="utf-8"))
    applied_validators = {item["title"]: item for item in applied["validators"]}
    code = bytes.fromhex(applied_validators[POLICY_TITLE]["compiledCode"])
    policy_result = _run([
        str(aiken), "blueprint", "policy", "-i", str(previous), "-m", POLICY_NAME,
        "-v", POLICY_NAME, str(cardano),
    ], cardano)
    matches = re.findall(r"\b[0-9a-f]{56}\b", policy_result.stdout + policy_result.stderr)
    if not matches:
        raise RuntimeError("compiled applied authority policy id unavailable")
    return {"code": code, "policy_id": bytes.fromhex(matches[-1]),
            "state_credential": state_credential,
            "expected_credential": expected_credential}



def _normalize_verify_signature_builtin(decoded: str, label: str) -> tuple[str, int]:
    # Aiken prints the legacy Ed25519 builtin alias but its text parser accepts
    # the canonical name. Verify the re-encoded script before evaluation.
    normalized, count = re.subn(
        r"(\(builtin\s+)verifySignature(\s*\))",
        r"\1verifyEd25519Signature\2",
        decoded,
    )
    named_tokens = re.findall(r"(?<![A-Za-z0-9_])verifySignature(?![A-Za-z0-9_])", decoded)
    if len(named_tokens) != count:
        raise ValueError("unscoped Ed25519 builtin alias in decoded UPLC")
    if count not in (0, 5) or (label == "valid-bootstrap" and count != 5):
        raise ValueError(f"unexpected Ed25519 builtin alias count: {count}")
    return normalized, count


def _evaluate(aiken: Path, code: bytes, context: dict[str, Any], work: Path, label: str) -> dict[str, Any]:
    code_path = work / f"{label}.cbor"
    code_path.write_bytes(code)
    decoded = _run([str(aiken), "uplc", "decode", "-c", str(code_path)], work).stdout
    prefix = "(program\n  1.1.0\n"
    if not decoded.startswith(prefix):
        raise RuntimeError("compiled mint program did not decode as Plutus 1.1")
    normalized, alias_count = _normalize_verify_signature_builtin(decoded, label)
    normalized_path = work / f"{label}-normalized.uplc"
    normalized_path.write_text(normalized, encoding="utf-8")
    encoded = subprocess.run(
        [str(aiken), "uplc", "encode", "-c", str(normalized_path)],
        cwd=work, capture_output=True, timeout=45,
    )
    if encoded.returncode != 0 or encoded.stdout != code:
        raise RuntimeError("normalized UPLC text does not round-trip to original compiled script bytes")
    program = work / f"{label}.uplc"
    program.write_text(prefix + f"[ {normalized[len(prefix):-2]} (con data ({uplc(context)})) ]\n)\n", encoding="utf-8")
    result = subprocess.run([str(aiken), "uplc", "eval", "-d", str(program)], cwd=work,
                            capture_output=True, text=True, timeout=45)
    accepted = result.returncode == 0 and "(con unit ())" in result.stdout
    cpu = [int(x) for x in re.findall(r'"cpu"\s*:\s*(\d+)', result.stdout)]
    mem = [int(x) for x in re.findall(r'"mem"\s*:\s*(\d+)', result.stdout)]
    return {"accepted": accepted, "exit": result.returncode,
            "cpu": max(cpu, default=None), "mem": max(mem, default=None),
            "context_cbor_bytes": len(cbor(context)),
            "verify_signature_alias_count": alias_count,
            "diagnostic": " | ".join((result.stderr + "\n" + result.stdout).strip().splitlines()[-8:])}


def _require_positive_acceptance(observed: dict[str, Any]) -> None:
    if observed.get("accepted") is True:
        return
    diagnostic = observed.get("diagnostic")
    if isinstance(diagnostic, str):
        missing_builtin = re.search(
            r"Default Function not found - ([A-Za-z][A-Za-z0-9_]*)",
            diagnostic,
        )
        if missing_builtin:
            raise RuntimeError(
                "configured Aiken UPLC evaluator lacks required Plutus builtin "
                f"{missing_builtin.group(1)}; UPLC evaluation aborted before an accept/reject verdict"
            )
    raise AssertionError(
        "canonical F05.2a bootstrap fixture rejected by compiled Plutus V3"
    )


def _run_suite(aiken: Path) -> dict[str, Any]:
    fixture, contract = _validate_inputs()
    signers = _ephemeral_committee()
    keys = [item.public_key for item in signers]
    genesis_hash = bytes.fromhex(fixture["synthetic_fixture_only"]["genesis_tx_hash"])
    genesis_index = fixture["synthetic_fixture_only"]["genesis_output_index"]
    base_parameters = {
        "genesis_ref": _output_reference(genesis_hash, genesis_index),
        "initial_keys": list_data([byte_string(key) for key in keys]),
    }
    workroot = Path(tempfile.mkdtemp(prefix="f05-2a-public-v3-"))
    try:
        base = _compile(CARDANO, aiken, workroot / "base", base_parameters)
        base_parameters.update({"policy_id": base["policy_id"].hex(),
                                "state_credential": base["state_credential"].hex(),
                                "state_validator_hash": base["expected_credential"].hex()})
        if base["state_credential"] != R2_FIXED_STATE_VALIDATOR_HASH:
            raise RuntimeError("pinned state-validator hash differs from R2 fixture contract")
        message = _canonical_pop_message(genesis_hash, genesis_index, base["state_credential"], keys)
        proofs = [key.sign(message) for key in signers]
        valid = _base_context(base["policy_id"], base["state_credential"],
                              genesis_hash, genesis_index, keys, proofs)
        cases: list[dict[str, Any]] = []
        observed = _evaluate(aiken, base["code"], valid, workroot, "valid-bootstrap")
        cases.append({"id": "valid_bootstrap", "expected": "accept", "actual": "accept" if observed["accepted"] else "reject", **observed})
        _require_positive_acceptance(observed)
        for item in fixture["negative_cases"]:
            case_id = item["id"]
            context, params = _mutate(case_id, valid, base_parameters, signers)
            if case_id.startswith("applied_"):
                variant = _compile(CARDANO, aiken, workroot / f"param-{case_id}", params)
                context = _applied_case_context(
                    case_id, params, variant["policy_id"], base["state_credential"],
                    genesis_hash, genesis_index, keys, proofs, signers,
                )
                observed = _evaluate(aiken, variant["code"], context, workroot, case_id)
            else:
                observed = _evaluate(aiken, base["code"], context, workroot, case_id)
            cases.append({"id": case_id, "expected": "reject", "actual": "reject" if not observed["accepted"] else "accept", **observed})

        wrong_hash_build = _compile(
            CARDANO, aiken, workroot / "wrong-state-hash",
            {"genesis_ref": base_parameters["genesis_ref"],
             "initial_keys": base_parameters["initial_keys"]},
            "wrong_state_validator_hash_constant",
        )
        wrong_hash_message = _canonical_pop_message(
            genesis_hash, genesis_index, wrong_hash_build["expected_credential"], keys,
        )
        wrong_hash_proofs = [key.sign(wrong_hash_message) for key in signers]
        wrong_hash_context = _base_context(
            wrong_hash_build["policy_id"], base["state_credential"], genesis_hash,
            genesis_index, keys, wrong_hash_proofs,
        )
        wrong_hash_context["fields"][0]["fields"][2]["list"].append(_output(
            _address(wrong_hash_build["expected_credential"], script=True),
            _value(lovelace=2_000_000), constr(0),
        ))
        observed = _evaluate(aiken, wrong_hash_build["code"], wrong_hash_context,
                             workroot, "wrong-state-hash-binding")
        cases.append({"id": "r2_wrong_state_validator_hash_constant",
                      "expected": "reject", "actual": "reject" if not observed["accepted"] else "accept", **observed})

        mutations = []
        mutation_pairs = {
            "remove_seed_guard": "seed_missing",
            "remove_target_output_cardinality_guard": "authority_output_extra_target",
            "remove_exact_mint_guard": "mint_extra_name",
            "remove_state_validator_credential_binding": "r2_wrong_state_address",
            "remove_no_stake_credential_guard": "output_stake_credential",
            "remove_singleton_quantity_guard": "authority_output_quantity_two",
            "remove_exact_lovelace_guard": "authority_value_minus_one",
            "remove_no_extra_asset_guard": "authority_extra_native_asset",
            "remove_inline_datum_guard": "datum_missing",
            "remove_schema_version_guard": "datum_schema_version",
            "remove_seed_hash_guard": "seed_datum_hash",
            "remove_seed_index_guard": "seed_datum_index",
            "remove_epoch_guard": "datum_epoch",
            "remove_threshold_guard": "datum_threshold",
            "remove_status_guard": "datum_status",
            "remove_pending_canonicality_guard": "datum_pending_noncanonical",
            "remove_key_uniqueness_order_guard": "applied_keys_duplicate",
            "remove_key_binding_guard": "datum_key_binding",
            "remove_key_order_guard": "applied_keys_unsorted",
            "remove_bootstrap_proof_of_possession_verification": "r2_invalid_proof_0",
            "unconditional_success": "seed_missing",
        }
        for index, (mutation, case_id) in enumerate(mutation_pairs.items()):
            context, mutant_parameters = _mutate(case_id, valid, base_parameters, signers)
            mutant = _compile(CARDANO, aiken, workroot / f"mutant-{index}", mutant_parameters, mutation)
            if mutation in {"remove_state_validator_credential_binding",
                            "remove_bootstrap_proof_of_possession_verification",
                            "unconditional_success"}:
                valid_control = copy.deepcopy(valid)
                _rebind_policy_id(valid_control, base["policy_id"], mutant["policy_id"])
                control = _evaluate(aiken, mutant["code"], valid_control, workroot,
                                    f"mutant-control-{mutation}")
                if not control["accepted"]:
                    raise AssertionError(f"mutant rejected canonical control: {mutation}")
            if mutation == "remove_state_validator_credential_binding":
                _set_proofs(context, proofs)
            if case_id.startswith("applied_keys_"):
                mutant_keys = [bytes.fromhex(value) for value in fixture_keys(mutant_parameters)]
                proof_signers = signers
                canonical_message = case_id not in {"applied_keys_duplicate", "applied_keys_unsorted"}
                if not canonical_message:
                    proof_signers = _signers_for_keys(mutant_keys, signers)
                mutant_message = _canonical_pop_message(
                    genesis_hash, genesis_index, base["state_credential"], mutant_keys,
                    require_canonical_keys=canonical_message,
                )
                mutant_proofs = [key.sign(mutant_message) for key in proof_signers]
                context = _base_context(mutant["policy_id"], base["state_credential"],
                                        genesis_hash, genesis_index, mutant_keys, mutant_proofs)
            else:
                _rebind_policy_id(context, base["policy_id"], mutant["policy_id"])
            if mutation == "unconditional_success":
                subcases = []
                for negative in fixture["negative_cases"]:
                    negative_id = negative["id"]
                    target_code, target_id, invalid = _unconditional_case_target(
                        negative_id, valid, base_parameters, base["policy_id"],
                        mutant, aiken, workroot, signers, keys, proofs,
                        genesis_hash, genesis_index, base["state_credential"],
                    )
                    _assert_unconditional_context_binding(
                        negative_id, invalid, base["policy_id"], target_id,
                    )
                    _, target_parameters = _mutate(
                        negative_id, valid, base_parameters, signers,
                    )
                    result = _evaluate(
                        aiken, target_code, invalid, workroot,
                        f"mutant-all-{negative_id}",
                    )
                    subcases.append({
                        "id": negative_id, "policy_id": target_id.hex(),
                        "script_sha256": hashlib.sha256(target_code).hexdigest(),
                        "context_sha256": hashlib.sha256(cbor(invalid)).hexdigest(),
                        "genesis_ref_cbor_sha256": hashlib.sha256(
                            cbor(target_parameters["genesis_ref"])
                        ).hexdigest(),
                        "initial_keys_cbor_sha256": hashlib.sha256(
                            cbor(target_parameters["initial_keys"])
                        ).hexdigest(),
                        "exit": result["exit"], "accepted": result["accepted"],
                    })
                    if not result["accepted"]:
                        raise AssertionError(f"unconditional-success mutation not detected by {negative_id}")
            else:
                result = _evaluate(aiken, mutant["code"], context, workroot, f"mutant-{mutation}")
                if not result["accepted"]:
                    raise AssertionError(f"compiled guard-removal mutant survived: {mutation} / {case_id}")
            mutation_record = {"mutation": mutation, "negative_fixture": case_id, "detected": True}
            if mutation == "unconditional_success":
                mutation_record["subcases"] = subcases
                mutation_record["positive_control"] = {
                    "policy_id": mutant["policy_id"].hex(),
                    "script_sha256": hashlib.sha256(mutant["code"]).hexdigest(),
                    "context_sha256": hashlib.sha256(cbor(valid_control)).hexdigest(),
                    "exit": control["exit"], "accepted": control["accepted"],
                }
                mutation_record["evidence_scope"] = (
                    "synthetic_direct_uplc_context_only; no_transaction_witness_or_ledger_credit"
                )
            mutations.append(mutation_record)
        failures = [item["id"] for item in cases if item["expected"] != item["actual"]]
        return {"status": "pass" if not failures else "fail", "entrypoint": POLICY_TITLE,
                "ledger": "Plutus V3", "positive_and_negative_cases": len(cases),
                "compiled_mutations": mutations, "failures": failures, "results": cases,
                "contract_id": contract["specification_id"]}
    finally:
        shutil.rmtree(workroot, ignore_errors=True)
        for key in signers:
            key.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aiken", type=Path, required=True,
                        help="path to the already-pinned Aiken 1.1.21 binary")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--tx-sim-canaries", action="store_true",
                        help="run only the checksum-pinned transaction canaries")
    parser.add_argument("--tx-sim-r3-canaries", action="store_true",
                        help="run the frozen positive and invalid-signature fixtures through the R3 snapshot runner")
    args = parser.parse_args()
    if args.tx_sim_r3_canaries:
        result = _run_tx_sim_r3_canaries(args.aiken.resolve())
        text = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        print(text, end="")
        return 0
    if args.tx_sim_canaries:
        result = _run_tx_sim_canaries(args.aiken.resolve())
        text = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        print(text, end="")
        return 0
    version = _run([str(args.aiken), "--version"], ROOT)
    if "1.1.21" not in version.stdout + version.stderr:
        raise SystemExit("expected pinned Aiken 1.1.21")
    result = _run_suite(args.aiken.resolve())
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
