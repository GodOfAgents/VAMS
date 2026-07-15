//// VAMS governance proposal authentication policy.
////
//// The fixed policy derives each proposal asset name from a consumed seed
//// UTxO. The asset follows the proposal into the timelock and is burned only
//// by an authorized governor cancellation or timelock terminal transition.

use aiken/builtin
use aiken/collection/dict
use aiken/collection/list
use aiken/crypto.{blake2b_256}
use aiken/interval.{Finite}
use aiken/primitive/bytearray
use cardano/address.{Address, Script}
use cardano/assets.{PolicyId, lovelace_of, quantity_of, tokens}
use cardano/transaction.{
  InlineDatum, Input, NoDatum, Output, OutputReference, Transaction,
}
use vams/types.{IntentDatum, Pending, ProposalDatum, cardano_schema_version}
use vams/utils.{is_signed_by}

validator proposal_nft(
  seed: OutputReference,
  governor_script_hash: ByteArray,
  timelock_script_hash: ByteArray,
  allowed_target_scripts: List<ByteArray>,
  min_proposal_stake: Int,
  min_voting_period_ms: Int,
  default_quorum: Int,
) {
  mint(_redeemer: Data, policy_id: PolicyId, tx: Transaction) {
    when dict.to_pairs(tokens(tx.mint, policy_id)) is {
      [Pair(asset_name, amount)] ->
        if amount == 1 {
          expect asset_name == proposal_asset_name(seed)
          expect
            list.any(tx.inputs, fn(input) { input.output_reference == seed })
          expect Finite(current_time) = tx.validity_range.lower_bound.bound_type
          let outputs =
            list.filter(
              tx.outputs,
              fn(output) {
                is_valid_proposal_output(
                  output,
                  governor_script_hash,
                  policy_id,
                  asset_name,
                  current_time,
                  allowed_target_scripts,
                  min_proposal_stake,
                  min_voting_period_ms,
                  default_quorum,
                  tx,
                )
              },
            )
          list.length(outputs) == 1
        } else if amount == -1 {
          let inputs =
            list.filter(
              tx.inputs,
              fn(input) {
                is_authenticated_terminal_input(
                  input.output,
                  governor_script_hash,
                  timelock_script_hash,
                  policy_id,
                  asset_name,
                )
              },
            )
          list.length(inputs) == 1
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

fn is_authenticated_terminal_input(
  output: Output,
  governor_script_hash: ByteArray,
  timelock_script_hash: ByteArray,
  policy_id: PolicyId,
  asset_name: ByteArray,
) -> Bool {
  if quantity_of(output.value, policy_id, asset_name) != 1 {
    False
  } else {
    when Pair(output.address.payment_credential, output.datum) is {
      Pair(Script(hash), InlineDatum(raw)) ->
        if hash == governor_script_hash {
          expect datum: ProposalDatum = raw
          datum.schema_version == cardano_schema_version && datum.proposal_policy_id == policy_id && datum.proposal_asset_name == asset_name
        } else if
        hash == timelock_script_hash {
          expect datum: IntentDatum = raw
          datum.schema_version == cardano_schema_version && datum.proposal_policy_id == policy_id && datum.proposal_asset_name == asset_name
        } else {
          False
        }
      _ -> False
    }
  }
}

fn proposal_asset_name(seed: OutputReference) -> ByteArray {
  blake2b_256(builtin.serialise_data(seed))
}

fn is_valid_proposal_output(
  output: Output,
  governor_script_hash: ByteArray,
  policy_id: PolicyId,
  asset_name: ByteArray,
  current_time: Int,
  allowed_target_scripts: List<ByteArray>,
  min_proposal_stake: Int,
  min_voting_period_ms: Int,
  default_quorum: Int,
  tx: Transaction,
) -> Bool {
  when output.address.payment_credential is {
    Script(hash) ->
      if hash != governor_script_hash || quantity_of(
        output.value,
        policy_id,
        asset_name,
      ) != 1 {
        False
      } else {
        when output.datum is {
          InlineDatum(raw_datum) -> {
            expect datum: ProposalDatum = raw_datum
            and {
              datum.schema_version == cardano_schema_version,
              datum.id > 0,
              datum.proposal_policy_id == policy_id,
              datum.proposal_asset_name == asset_name,
              bytearray.length(datum.proposer) == 28,
              is_signed_by(tx.extra_signatories, datum.proposer),
              bytearray.length(datum.description_hash) == 32,
              bytearray.length(datum.action_hash) == 32,
              bytearray.length(datum.target_script_hash) == 28,
              !list.is_empty(allowed_target_scripts),
              list.has(allowed_target_scripts, datum.target_script_hash),
              datum.created_at == current_time,
              datum.for_votes == 0,
              datum.against_votes == 0,
              datum.quorum >= default_quorum,
              datum.deadline >= current_time + min_voting_period_ms,
              datum.status == Pending,
              list.is_empty(datum.voters),
              lovelace_of(output.value) >= min_proposal_stake,
            }
          }
          _ -> False
        }
      }
    _ -> False
  }
}

test proposal_asset_names_are_unique_by_output_index() {
  let first =
    OutputReference {
      transaction_id: #"0000000000000000000000000000000000000000000000000000000000000000",
      output_index: 0,
    }
  proposal_asset_name(first) != proposal_asset_name(
    OutputReference { ..first, output_index: 1 },
  )
}

const fixture_seed: OutputReference =
  OutputReference {
    transaction_id: #"0101010101010101010101010101010101010101010101010101010101010101",
    output_index: 0,
  }

const fixture_governor_hash: ByteArray =
  #"02020202020202020202020202020202020202020202020202020202"

const fixture_timelock_hash: ByteArray =
  #"03030303030303030303030303030303030303030303030303030303"

const fixture_target_hash: ByteArray =
  #"04040404040404040404040404040404040404040404040404040404"

const fixture_policy_id: PolicyId =
  #"05050505050505050505050505050505050505050505050505050505"

const fixture_proposer: ByteArray =
  #"06060606060606060606060606060606060606060606060606060606"

fn fixture_seed_input() -> Input {
  Input {
    output_reference: fixture_seed,
    output: Output {
      address: Address {
        payment_credential: Script(fixture_governor_hash),
        stake_credential: None,
      },
      value: assets.from_lovelace(2_000_000),
      datum: NoDatum,
      reference_script: None,
    },
  }
}

fn fixture_proposal_output(asset_name: ByteArray) -> Output {
  let datum =
    ProposalDatum {
      schema_version: cardano_schema_version,
      id: 1,
      proposal_policy_id: fixture_policy_id,
      proposal_asset_name: asset_name,
      proposer: fixture_proposer,
      description_hash: #"0707070707070707070707070707070707070707070707070707070707070707",
      action_hash: #"0808080808080808080808080808080808080808080808080808080808080808",
      target_script_hash: fixture_target_hash,
      created_at: 100,
      for_votes: 0,
      against_votes: 0,
      quorum: 2,
      deadline: 200,
      status: Pending,
      voters: [],
    }
  Output {
    address: Address {
      payment_credential: Script(fixture_governor_hash),
      stake_credential: None,
    },
    value: assets.from_lovelace(5_000_000)
      |> assets.add(fixture_policy_id, asset_name, 1),
    datum: InlineDatum(datum),
    reference_script: None,
  }
}

test mint_creates_one_exact_proposal_state() {
  let asset_name = proposal_asset_name(fixture_seed)
  proposal_nft.mint(
    fixture_seed,
    fixture_governor_hash,
    fixture_timelock_hash,
    [fixture_target_hash],
    5_000_000,
    100,
    2,
    builtin.i_data(0),
    fixture_policy_id,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_seed_input()],
      outputs: [fixture_proposal_output(asset_name)],
      mint: assets.from_asset(fixture_policy_id, asset_name, 1),
      validity_range: interval.between(100, 200),
      extra_signatories: [fixture_proposer],
    },
  )
}

test mint_rejects_duplicate_proposal_outputs() fail {
  let asset_name = proposal_asset_name(fixture_seed)
  let output = fixture_proposal_output(asset_name)
  proposal_nft.mint(
    fixture_seed,
    fixture_governor_hash,
    fixture_timelock_hash,
    [fixture_target_hash],
    5_000_000,
    100,
    2,
    builtin.i_data(0),
    fixture_policy_id,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_seed_input()],
      outputs: [output, output],
      mint: assets.from_asset(fixture_policy_id, asset_name, 1),
      validity_range: interval.between(100, 200),
      extra_signatories: [fixture_proposer],
    },
  )
}
