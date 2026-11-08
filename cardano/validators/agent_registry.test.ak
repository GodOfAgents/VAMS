use aiken/primitive/bytearray
//// Regression fixtures for the deprecated registry-side identity mint path.
////
//// These fixtures exercise registry-side mint rejection and retained legacy burn
//// acceptance. The policy rejects registry-side identity creation; the legacy
//// burn branch remains available pending the separately designed migration.

use cardano/address
use cardano/assets
use cardano/transaction.{InlineDatum, Input, Output, OutputReference, Transaction}
use agent_nft
use agent_registry
use vams/types.{AgentDatumV1, AgentNftRedeemer, BurnIdentity, MintIdentity}

const bootstrap_ref: OutputReference =
  OutputReference {
    transaction_id: #"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    output_index: 7,
  }

const identity_policy_id: ByteArray =
  #"11111111111111111111111111111111111111111111111111111111"

const owner_vkh: ByteArray =
  #"22222222222222222222222222222222222222222222222222222222"

const operator_vkh: ByteArray =
  #"33333333333333333333333333333333333333333333333333333333"

const did: ByteArray =
  bytearray.from_string(@"did:vams:agent:00000000000000000")

const metadata_hash: ByteArray =
  #"4444444444444444444444444444444444444444444444444444444444444444"

const stake_lovelace: Int = 1_000_000_000

fn identity_asset_name() -> ByteArray {
  agent_nft.derive_identity_name(did, owner_vkh, bootstrap_ref)
}

fn identity_datum() -> AgentDatumV1 {
  AgentDatumV1 {
    schema_version: 1,
    identity_policy_id,
    identity_asset_name: identity_asset_name(),
    nonce: 0,
    did,
    owner: owner_vkh,
    operator: operator_vkh,
    stake_lovelace,
    reputation_bps: 5_000,
    metadata_hash,
    status: 0,
    action_epoch: 0,
    registered_at_ms: 0,
    authorized_slashers: [],
  }
}

fn bootstrap_input() -> Input {
  Input {
    output_reference: bootstrap_ref,
    output: Output {
      address: address.from_verification_key(owner_vkh),
      value: assets.from_lovelace(2_000_000),
      datum: transaction.NoDatum,
      reference_script: None,
    },
  }
}

fn identity_input() -> Input {
  Input {
    output_reference: OutputReference {
      transaction_id: #"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      output_index: 2,
    },
    output: Output {
      address: address.from_script(identity_policy_id),
      value: assets.merge(
        assets.from_lovelace(stake_lovelace),
        assets.from_asset(identity_policy_id, identity_asset_name(), 1),
      ),
      datum: InlineDatum(identity_datum()),
      reference_script: None,
    },
  }
}

fn mint_transaction() -> Transaction {
  Transaction {
    ..transaction.placeholder,
    inputs: [bootstrap_input()],
    outputs: [
      Output {
        address: address.from_script(identity_policy_id),
        value: assets.merge(
          assets.from_lovelace(stake_lovelace),
          assets.from_asset(identity_policy_id, identity_asset_name(), 1),
        ),
        datum: InlineDatum(identity_datum()),
        reference_script: None,
      },
    ],
    mint: assets.from_asset(identity_policy_id, identity_asset_name(), 1),
    extra_signatories: [owner_vkh],
  }
}

fn burn_transaction() -> Transaction {
  Transaction {
    ..transaction.placeholder,
    inputs: [identity_input()],
    outputs: [
      Output {
        address: address.from_verification_key(owner_vkh),
        value: assets.from_lovelace(stake_lovelace),
        datum: transaction.NoDatum,
        reference_script: None,
      },
    ],
    mint: assets.from_asset(identity_policy_id, identity_asset_name(), -1),
    extra_signatories: [owner_vkh],
  }
}

fn run_registry_mint(redeemer: AgentNftRedeemer, tx: Transaction) -> Bool {
  agent_registry.agent_registry.mint(
    bootstrap_ref,
    #"55555555555555555555555555555555555555555555555555555555",
    #"66666666666666666666666666666666666666666666666666666666",
    #"7777777777777777777777777777777777777777777777777777777777777777",
    2_000_000,
    owner_vkh,
    #"8888888888888888888888888888888888888888888888888888888888888888",
    redeemer,
    identity_policy_id,
    tx,
  )
}

test registry_mint_identity_must_reject() {
  run_registry_mint(MintIdentity { did, owner_vkh }, mint_transaction()) == False
}

test registry_legacy_burn_identity_remains_accepted() {
  run_registry_mint(
    BurnIdentity { identity_asset_name: identity_asset_name(), owner_vkh },
    burn_transaction(),
  ) == True
}
