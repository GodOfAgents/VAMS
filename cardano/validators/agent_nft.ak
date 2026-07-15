//// VAMS agent identity NFT policy.
////
//// Each applied policy is bound to one seed UTxO and destination registry.
//// The asset name is the Blake2b-256 commitment of that seed. Minting creates one exact
//// registry state; burning requires the corresponding owner-signed state input.

use aiken/builtin
use aiken/collection/dict
use aiken/collection/list
use aiken/crypto.{blake2b_256}
use aiken/interval.{Finite}
use aiken/primitive/bytearray
use cardano/address.{Address, Script}
use cardano/assets.{PolicyId, Value, lovelace_of, quantity_of, tokens}
use cardano/transaction.{
  InlineDatum, Input, NoDatum, Output, OutputReference, Transaction,
}
use vams/types.{AgentDatum, cardano_schema_version}
use vams/utils.{is_signed_by}

const min_agent_stake: Int = 1_000_000_000

const initial_reputation: Int = 5_000

validator agent_nft(seed: OutputReference, registry_script_hash: ByteArray) {
  mint(_redeemer: Data, policy_id: PolicyId, tx: Transaction) {
    let policy_tokens = tokens(tx.mint, policy_id)
    when dict.to_pairs(policy_tokens) is {
      [Pair(asset_name, amount)] ->
        if amount == 1 {
          expect asset_name == identity_asset_name(seed)
          expect
            list.any(tx.inputs, fn(input) { input.output_reference == seed })
          expect Finite(current_time) = tx.validity_range.lower_bound.bound_type
          let matching_outputs =
            list.filter(
              tx.outputs,
              fn(output) {
                is_valid_registration_output(
                  output,
                  registry_script_hash,
                  policy_id,
                  asset_name,
                  current_time,
                  tx,
                )
              },
            )
          list.length(matching_outputs) == 1
        } else if amount == -1 {
          let matching_inputs =
            list.filter(
              tx.inputs,
              fn(input) {
                is_owner_signed_registry_input(
                  input.output,
                  registry_script_hash,
                  policy_id,
                  asset_name,
                  tx,
                )
              },
            )
          list.length(matching_inputs) == 1
        } else {
          False
        }
      _ -> False
    }
  }

  else(_) {
    fail
  }
}

fn identity_asset_name(seed: OutputReference) -> ByteArray {
  blake2b_256(builtin.serialise_data(seed))
}

fn is_valid_registration_output(
  output: Output,
  registry_script_hash: ByteArray,
  policy_id: PolicyId,
  asset_name: ByteArray,
  current_time: Int,
  tx: Transaction,
) -> Bool {
  when output.address.payment_credential is {
    Script(hash) ->
      if hash != registry_script_hash || quantity_of(
        output.value,
        policy_id,
        asset_name,
      ) != 1 {
        False
      } else {
        when output.datum is {
          InlineDatum(raw_datum) -> {
            expect datum: AgentDatum = raw_datum
            valid_initial_agent(
              datum,
              output.value,
              policy_id,
              asset_name,
              current_time,
            ) && is_signed_by(tx.extra_signatories, datum.owner)
          }
          _ -> False
        }
      }
    _ -> False
  }
}

fn is_owner_signed_registry_input(
  output: Output,
  registry_script_hash: ByteArray,
  policy_id: PolicyId,
  asset_name: ByteArray,
  tx: Transaction,
) -> Bool {
  when output.address.payment_credential is {
    Script(hash) ->
      if hash != registry_script_hash || quantity_of(
        output.value,
        policy_id,
        asset_name,
      ) != 1 {
        False
      } else {
        when output.datum is {
          InlineDatum(raw_datum) -> {
            expect datum: AgentDatum = raw_datum
            datum.identity_policy_id == policy_id && datum.identity_asset_name == asset_name && is_signed_by(
              tx.extra_signatories,
              datum.owner,
            )
          }
          _ -> False
        }
      }
    _ -> False
  }
}

fn valid_initial_agent(
  datum: AgentDatum,
  value: Value,
  policy_id: PolicyId,
  asset_name: ByteArray,
  current_time: Int,
) -> Bool {
  and {
    datum.schema_version == cardano_schema_version,
    datum.identity_policy_id == policy_id,
    datum.identity_asset_name == asset_name,
    bytearray.length(datum.did) >= 32,
    bytearray.length(datum.owner) == 28,
    datum.reputation_score == initial_reputation,
    datum.registered_at == current_time,
    bytearray.length(datum.metadata_hash) == 32,
    datum.is_active,
    datum.staked_amount == lovelace_of(value),
    datum.staked_amount >= min_agent_stake,
    list.is_empty(datum.authorized_slashers),
  }
}

test identity_asset_name_is_seed_bound() {
  let first =
    OutputReference {
      transaction_id: #"0000000000000000000000000000000000000000000000000000000000000000",
      output_index: 0,
    }
  let second = OutputReference { ..first, output_index: 1 }
  identity_asset_name(first) != identity_asset_name(second)
}

const fixture_seed: OutputReference =
  OutputReference {
    transaction_id: #"0101010101010101010101010101010101010101010101010101010101010101",
    output_index: 0,
  }

const fixture_registry_hash: ByteArray =
  #"02020202020202020202020202020202020202020202020202020202"

const fixture_policy_id: PolicyId =
  #"03030303030303030303030303030303030303030303030303030303"

const fixture_owner: ByteArray =
  #"04040404040404040404040404040404040404040404040404040404"

fn fixture_seed_input() -> Input {
  Input {
    output_reference: fixture_seed,
    output: Output {
      address: Address {
        payment_credential: Script(fixture_registry_hash),
        stake_credential: None,
      },
      value: assets.from_lovelace(2_000_000),
      datum: NoDatum,
      reference_script: None,
    },
  }
}

fn fixture_registration_output(asset_name: ByteArray) -> Output {
  let value =
    assets.from_lovelace(min_agent_stake)
      |> assets.add(fixture_policy_id, asset_name, 1)
  let datum =
    AgentDatum {
      schema_version: cardano_schema_version,
      identity_policy_id: fixture_policy_id,
      identity_asset_name: asset_name,
      did: #"0505050505050505050505050505050505050505050505050505050505050505",
      owner: fixture_owner,
      reputation_score: initial_reputation,
      registered_at: 100,
      metadata_hash: #"0606060606060606060606060606060606060606060606060606060606060606",
      is_active: True,
      staked_amount: min_agent_stake,
      authorized_slashers: [],
    }
  Output {
    address: Address {
      payment_credential: Script(fixture_registry_hash),
      stake_credential: None,
    },
    value,
    datum: InlineDatum(datum),
    reference_script: None,
  }
}

test mint_creates_one_exact_registered_identity() {
  let asset_name = identity_asset_name(fixture_seed)
  agent_nft.mint(
    fixture_seed,
    fixture_registry_hash,
    builtin.i_data(0),
    fixture_policy_id,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_seed_input()],
      outputs: [fixture_registration_output(asset_name)],
      mint: assets.from_asset(fixture_policy_id, asset_name, 1),
      validity_range: interval.between(100, 200),
      extra_signatories: [fixture_owner],
    },
  )
}

test mint_rejects_duplicate_identity_outputs() fail {
  let asset_name = identity_asset_name(fixture_seed)
  let output = fixture_registration_output(asset_name)
  agent_nft.mint(
    fixture_seed,
    fixture_registry_hash,
    builtin.i_data(0),
    fixture_policy_id,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_seed_input()],
      outputs: [output, output],
      mint: assets.from_asset(fixture_policy_id, asset_name, 1),
      validity_range: interval.between(100, 200),
      extra_signatories: [fixture_owner],
    },
  )
}
