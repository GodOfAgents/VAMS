#!/usr/bin/env python3
"""Focused F04 interface/blueprint migration checks.

The assertions are derived from the accepted frozen design artifacts and inspect
the public Cardano source/blueprint contract; they do not call production
validator helpers to manufacture expected values.
"""
from __future__ import annotations
import hashlib
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CARDANO = REPO / "cardano"
DESIGN = REPO / "docs/remediation/m3_f04_design_r1"
IDENTITY = json.loads((DESIGN / "IDENTITY_SPEC.json").read_text())
MATRIX = json.loads((DESIGN / "ACCEPTANCE_MATRIX.json").read_text())
BLUEPRINT = json.loads((CARDANO / "plutus.json").read_text())
REGISTRY = (CARDANO / "validators/agent_registry.ak").read_text()
NFT = (CARDANO / "validators/agent_nft.ak").read_text()
TYPE_SOURCE = (CARDANO / "lib/vams/types.ak").read_text()

DATUM_FIELDS = [field[0] for field in IDENTITY["datum"]["fields"]]
EXPECTED_REDEEMERS = set(IDENTITY["redeemers"])
DOMAIN = bytes.fromhex(IDENTITY["identity"]["domain_hex"])


def blueprint_entry(title: str) -> dict:
    return next((entry for entry in BLUEPRINT["validators"] if entry["title"] == title), {})


def derive_identity(row: dict) -> str:
    did = bytes.fromhex(row["did"])
    owner = bytes.fromhex(row["owner_vkh"])
    seed = bytes.fromhex(row["seed_tx_id"])
    preimage = DOMAIN + len(did).to_bytes(2, "big") + did + owner + seed + row["seed_index"].to_bytes(4, "big")
    return hashlib.blake2b(preimage, digest_size=32).hexdigest()


def contract_ok(registry: str, nft: str, blueprint: dict) -> bool:
    required_registry = (
        "AgentDatumV1", "RegistryRedeemerV1", "expected_nonce == datum.nonce",
        "expected_action_epoch == datum.action_epoch",
        "expect unique_authority_reference(",
        "assets.quantity_of(tx.mint", "SlashAgent { .. } -> False",
        "conserved_full_value(own_input.output.value, next_output.value)",
        "valid_did(did)", "asset_name == derive_identity_name", "list.has(tx.extra_signatories, owner_vkh)", "mint_output_is_bound(tx.outputs, policy_id, asset_name, did, owner_vkh, bootstrap_ref)",
        "valid_burn_input(input, policy_id, asset_name, owner_vkh, bootstrap_ref, tx)",
    )
    required_legacy = (
        "validator agent_nft(bootstrap_ref: OutputReference)",
        "mint(_redeemer: AgentNftRedeemer, _policy_id: PolicyId, _tx: Transaction) {\n    expect _unused_bootstrap_ref = bootstrap_ref\n    False\n  }",
    )
    if not all(token in registry for token in required_registry):
        return False
    if not all(token in nft for token in required_legacy):
        return False
    reg = blueprint_entry_from(blueprint, "agent_registry.agent_registry.spend")
    mint = blueprint_entry_from(blueprint, "agent_registry.agent_registry.mint")
    return (
        reg.get("datum", {}).get("schema", {}).get("$ref", "").endswith("AgentDatumV1")
        and reg.get("redeemer", {}).get("schema", {}).get("$ref", "").endswith("RegistryRedeemerV1")
        and mint.get("redeemer", {}).get("schema", {}).get("$ref", "").endswith("AgentNftRedeemer")
        and [p.get("title") for p in mint.get("parameters", [])] == ["bootstrap_ref", "trusted_authority_script_hash", "trusted_authority_policy_id", "trusted_authority_asset_name", "trusted_authority_state_lovelace", "trusted_reserve_credential", "trusted_authority_datum_commitment"]
        and [p.get("title") for p in reg.get("parameters", [])] == ["bootstrap_ref", "trusted_authority_script_hash", "trusted_authority_policy_id", "trusted_authority_asset_name", "trusted_authority_state_lovelace", "trusted_reserve_credential", "trusted_authority_datum_commitment"]
    )


def blueprint_entry_from(blueprint: dict, title: str) -> dict:
    return next((entry for entry in blueprint.get("validators", []) if entry.get("title") == title), {})


class F04InterfaceMigrationTests(unittest.TestCase):
    def test_frozen_fourteen_field_datum(self):
        self.assertEqual(DATUM_FIELDS, [
            "schema_version", "identity_policy_id", "identity_asset_name", "nonce",
            "did", "owner", "operator", "stake_lovelace", "reputation_bps",
            "metadata_hash", "status", "action_epoch", "registered_at_ms",
            "authorized_slashers",
        ])
        self.assertRegex(TYPE_SOURCE, r"pub type AgentDatumV1 \{[\s\S]*?authorized_slashers: List<ByteArray>,\n\}")
        self.assertNotRegex(TYPE_SOURCE, r"pub type AgentDatum \{")
        self.assertNotRegex(REGISTRY, r"AgentDatum[>,)](?!V1)")

    def test_versioned_redeemers_are_closed(self):
        self.assertEqual(set(IDENTITY["redeemers"]), EXPECTED_REDEEMERS)
        for name in EXPECTED_REDEEMERS:
            self.assertIn(name, REGISTRY)
        self.assertIn("pub type RegistryRedeemerV1", TYPE_SOURCE)
        self.assertNotIn("pub type RegistryRedeemer {", TYPE_SOURCE)

    def test_identity_vectors_match_frozen_contract(self):
        vectors = json.loads((DESIGN / "ASSET_VECTORS.json").read_text())["vectors"]
        self.assertEqual(len(vectors), 2)
        for row in vectors:
            self.assertEqual(derive_identity(row), row["token_name"])
            self.assertEqual(len(bytes.fromhex(row["token_name"])), 32)

    def test_all_forty_nine_rows_remain_present(self):
        rows = MATRIX["rows"]
        self.assertEqual(len(rows), 49)
        self.assertEqual(len({row["id"] for row in rows}), 49)
        self.assertTrue(all(row["evidence_status"] == "pending" for row in rows) if "evidence_status" in rows[0] else True)

    def test_blueprint_uses_migrated_public_schemas(self):
        self.assertTrue(contract_ok(REGISTRY, NFT, BLUEPRINT))

    def test_pre_f05_slash_is_unconditionally_rejected(self):
        self.assertIn("SlashAgent { .. } -> False", REGISTRY)
        self.assertNotIn("slash_enabled == True", REGISTRY)

    def test_mutation_wrong_identity_binding_rejects(self):
        mutated = REGISTRY.replace("asset_name == derive_identity_name", "asset_name == #\"00\"", 1)
        self.assertFalse(contract_ok(mutated, NFT, BLUEPRINT))

    def test_mutation_unlinked_burn_rejects(self):
        mutated = REGISTRY.replace("valid_burn_input(input, policy_id, asset_name, owner_vkh, bootstrap_ref, tx)", "True", 1)
        self.assertFalse(contract_ok(mutated, NFT, BLUEPRINT))

    def test_mutation_nonce_binding_rejects(self):
        mutated = REGISTRY.replace("expected_nonce == datum.nonce", "True")
        self.assertFalse(contract_ok(mutated, NFT, BLUEPRINT))

    def test_mutation_authority_reference_rejects(self):
        mutated = REGISTRY.replace("expect unique_authority_reference(", "True", 1)
        self.assertFalse(contract_ok(mutated, NFT, BLUEPRINT))

    def test_mutation_pre_f05_slash_enablement_rejects(self):
        mutated = REGISTRY.replace("SlashAgent { .. } -> False", "SlashAgent { .. } -> True", 1)
        self.assertFalse(contract_ok(mutated, NFT, BLUEPRINT))

    def test_mutation_legacy_blueprint_rejects(self):
        mutated = json.loads(json.dumps(BLUEPRINT))
        entry = blueprint_entry_from(mutated, "agent_registry.agent_registry.spend")
        entry["datum"]["schema"]["$ref"] = "#/definitions/vams~1types~1AgentDatum"
        self.assertFalse(contract_ok(REGISTRY, NFT, mutated))

    def test_mutation_nft_parameter_rejects(self):
        mutated = json.loads(json.dumps(BLUEPRINT))
        entry = blueprint_entry_from(mutated, "agent_registry.agent_registry.mint")
        entry["parameters"][0]["title"] = "utxo_ref"
        self.assertFalse(contract_ok(REGISTRY, NFT, mutated))

    def test_r2_value_authority_and_did_guards_present(self):
        for token in (
            "next_output.address == own_input.output.address",
            "assets.lovelace_of(next_output.value) == next.stake_lovelace",
            "assets.lovelace_of(payout.value) == assets.lovelace_of(own_input.output.value)",
            "exact_authority_value",
            "blake2b_256(cbor.serialise(RegistryAuthorityPayloadV1",
            "authority.reserve_credential",
            "valid_did(did)",
            "bytearray.from_string(bytearray.to_string(did)) == did",
        ):
            self.assertIn(token, REGISTRY)

        # Option B preserves the exact raw UTF-8 bytes supplied by the caller.
        # The superseded R1 lowercase-hex canonicalization helpers must not be
        # part of the production identity path.
        self.assertNotIn("canonical_did(", REGISTRY)
        self.assertNotIn("canonical_hex_byte", REGISTRY)

    def test_register_value_and_deregister_burn_guards_present(self):
        self.assertIn("next.stake_lovelace >= min_agent_stake", REGISTRY)
        self.assertIn("assets.quantity_of(tx.mint, datum.identity_policy_id, datum.identity_asset_name) == -1", REGISTRY)
        self.assertIn("conserved_full_value", REGISTRY)
        self.assertIn("payout.value", REGISTRY)


if __name__ == "__main__":
    unittest.main(verbosity=2)
