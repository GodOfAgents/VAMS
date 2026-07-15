//// VAMS Cardano-local governance state machine.
////
//// Proposal creation is authenticated by proposal_nft.mint. Voting preserves
//// the exact state value and proposal NFT. Execution transfers both into one
//// exact timelock intent. Cross-chain actions are intentionally unavailable.

use aiken/collection/list
use aiken/interval.{Finite}
use aiken/primitive/bytearray
use cardano/address.{Address, Script, VerificationKey}
use cardano/assets.{PolicyId, Value, add, lovelace_of, quantity_of}
use cardano/transaction.{
  InlineDatum, Input, NoDatum, Output, OutputReference, Transaction,
}
use vams/types.{
  Active, Cancel, Execute, GovernorRedeemer, IntentDatum, Pending, ProposalDatum,
  Vote, cardano_schema_version,
}
use vams/utils.{is_signed_by, isqrt}

validator governor(
  vams_policy_id: PolicyId,
  vams_asset_name: ByteArray,
  timelock_script_hash: ByteArray,
  allowed_target_scripts: List<ByteArray>,
  min_proposal_stake: Int,
  min_voting_period_ms: Int,
  default_quorum: Int,
  normal_delay_ms: Int,
  max_intent_lifetime_ms: Int,
) {
  spend(
    datum_opt: Option<ProposalDatum>,
    redeemer: GovernorRedeemer,
    own_ref: OutputReference,
    tx: Transaction,
  ) {
    expect Some(datum) = datum_opt
    expect Some(own_input) =
      list.find(tx.inputs, fn(input) { input.output_reference == own_ref })
    expect
      valid_proposal_state(
        datum,
        own_input.output,
        allowed_target_scripts,
        min_proposal_stake,
        min_voting_period_ms,
        default_quorum,
      )

    when redeemer is {
      Vote { support, weight } -> {
        expect Finite(valid_until) = tx.validity_range.upper_bound.bound_type
        expect valid_until <= datum.deadline
        expect [voter, ..] = tx.extra_signatories
        expect !list.has(datum.voters, voter)
        let voter_balance =
          get_voter_vams_balance(tx, voter, vams_policy_id, vams_asset_name)
        expect weight > 0 && weight == isqrt(voter_balance)
        let expected =
          ProposalDatum {
            ..datum,
            for_votes: if support {
              datum.for_votes + weight
            } else {
              datum.for_votes
            },
            against_votes: if support {
              datum.against_votes
            } else {
              datum.against_votes + weight
            },
            status: Active,
            voters: [voter, ..datum.voters],
          }
        exact_state_output(
          tx.outputs,
          own_input.output.address,
          own_input.output.value,
          expected,
          datum.proposal_policy_id,
          datum.proposal_asset_name,
        )
      }

      Execute -> {
        expect Finite(valid_from) = tx.validity_range.lower_bound.bound_type
        expect valid_from > datum.deadline
        expect datum.for_votes + datum.against_votes >= datum.quorum
        expect datum.for_votes > datum.against_votes
        expect
          quantity_of(
            tx.mint,
            datum.proposal_policy_id,
            datum.proposal_asset_name,
          ) == 0
        let intent =
          IntentDatum {
            schema_version: cardano_schema_version,
            proposal_policy_id: datum.proposal_policy_id,
            proposal_asset_name: datum.proposal_asset_name,
            source_proposal: own_ref,
            action_hash: datum.action_hash,
            target_script_hash: datum.target_script_hash,
            execute_after: valid_from + normal_delay_ms,
            expires_at: valid_from + normal_delay_ms + max_intent_lifetime_ms,
            refund_key_hash: datum.proposer,
          }
        exact_timelock_output(
          tx.outputs,
          timelock_script_hash,
          own_input.output.value,
          intent,
          datum.proposal_policy_id,
          datum.proposal_asset_name,
        )
      }

      Cancel -> {
        expect Finite(valid_until) = tx.validity_range.upper_bound.bound_type
        expect valid_until <= datum.deadline
        expect is_signed_by(tx.extra_signatories, datum.proposer)
        expect
          quantity_of(
            tx.mint,
            datum.proposal_policy_id,
            datum.proposal_asset_name,
          ) == -1
        let refund =
          add(
            own_input.output.value,
            datum.proposal_policy_id,
            datum.proposal_asset_name,
            -1,
          )
        exact_key_output(tx.outputs, datum.proposer, refund) && count_outputs_with_asset(
          tx.outputs,
          datum.proposal_policy_id,
          datum.proposal_asset_name,
        ) == 0
      }
    }
  }

  else(_) {
    fail
  }
}

fn valid_proposal_state(
  datum: ProposalDatum,
  output: Output,
  allowed_target_scripts: List<ByteArray>,
  min_proposal_stake: Int,
  min_voting_period_ms: Int,
  default_quorum: Int,
) -> Bool {
  and {
    datum.schema_version == cardano_schema_version,
    datum.id > 0,
    bytearray.length(datum.proposal_asset_name) == 32,
    quantity_of(
      output.value,
      datum.proposal_policy_id,
      datum.proposal_asset_name,
    ) == 1,
    bytearray.length(datum.proposer) == 28,
    bytearray.length(datum.description_hash) == 32,
    bytearray.length(datum.action_hash) == 32,
    bytearray.length(datum.target_script_hash) == 28,
    !list.is_empty(allowed_target_scripts),
    list.has(allowed_target_scripts, datum.target_script_hash),
    datum.created_at >= 0,
    datum.for_votes >= 0,
    datum.against_votes >= 0,
    datum.quorum >= default_quorum,
    datum.deadline >= datum.created_at + min_voting_period_ms,
    datum.status == Pending || datum.status == Active,
    lovelace_of(output.value) >= min_proposal_stake,
  }
}

fn get_voter_vams_balance(
  tx: Transaction,
  voter: ByteArray,
  policy_id: PolicyId,
  asset_name: ByteArray,
) -> Int {
  list.foldl(
    tx.inputs,
    0,
    fn(input, total) {
      when input.output.address.payment_credential is {
        VerificationKey(hash) ->
          if hash == voter {
            total + quantity_of(input.output.value, policy_id, asset_name)
          } else {
            total
          }
        _ -> total
      }
    },
  )
}

fn exact_state_output(
  outputs: List<Output>,
  address: Address,
  value: Value,
  expected: ProposalDatum,
  policy_id: PolicyId,
  asset_name: ByteArray,
) -> Bool {
  let matches =
    list.filter(
      outputs,
      fn(output) {
        output.address == address && output.value == value && has_proposal_datum(
          output,
          expected,
        )
      },
    )
  list.length(matches) == 1 && count_outputs_with_asset(
    outputs,
    policy_id,
    asset_name,
  ) == 1
}

fn exact_timelock_output(
  outputs: List<Output>,
  timelock_script_hash: ByteArray,
  value: Value,
  expected: IntentDatum,
  policy_id: PolicyId,
  asset_name: ByteArray,
) -> Bool {
  let matches =
    list.filter(
      outputs,
      fn(output) {
        when output.address.payment_credential is {
          Script(hash) ->
            hash == timelock_script_hash && output.value == value && has_intent_datum(
              output,
              expected,
            )
          _ -> False
        }
      },
    )
  list.length(matches) == 1 && count_outputs_with_asset(
    outputs,
    policy_id,
    asset_name,
  ) == 1
}

fn exact_key_output(
  outputs: List<Output>,
  key_hash: ByteArray,
  value: Value,
) -> Bool {
  list.length(
    list.filter(
      outputs,
      fn(output) {
        when output.address.payment_credential is {
          VerificationKey(hash) -> hash == key_hash && output.value == value
          _ -> False
        }
      },
    ),
  ) == 1
}

fn has_proposal_datum(output: Output, expected: ProposalDatum) -> Bool {
  when output.datum is {
    InlineDatum(raw) -> {
      expect actual: ProposalDatum = raw
      actual == expected
    }
    _ -> False
  }
}

fn has_intent_datum(output: Output, expected: IntentDatum) -> Bool {
  when output.datum is {
    InlineDatum(raw) -> {
      expect actual: IntentDatum = raw
      actual == expected
    }
    _ -> False
  }
}

fn count_outputs_with_asset(
  outputs: List<Output>,
  policy_id: PolicyId,
  asset_name: ByteArray,
) -> Int {
  list.length(
    list.filter(
      outputs,
      fn(output) { quantity_of(output.value, policy_id, asset_name) == 1 },
    ),
  )
}

test quadratic_weight_100k() {
  isqrt(100_000) == 316
}

test quadratic_weight_1m() {
  isqrt(1_000_000) == 1000
}

const fixture_vams_policy: PolicyId =
  #"10101010101010101010101010101010101010101010101010101010"

const fixture_proposal_policy: PolicyId =
  #"20202020202020202020202020202020202020202020202020202020"

const fixture_timelock_hash: ByteArray =
  #"30303030303030303030303030303030303030303030303030303030"

const fixture_governor_hash: ByteArray =
  #"40404040404040404040404040404040404040404040404040404040"

const fixture_proposer: ByteArray =
  #"50505050505050505050505050505050505050505050505050505050"

const fixture_proposal_asset: ByteArray =
  #"6060606060606060606060606060606060606060606060606060606060606060"

const fixture_proposal_ref: OutputReference =
  OutputReference {
    transaction_id: #"7070707070707070707070707070707070707070707070707070707070707070",
    output_index: 0,
  }

const fixture_proposal_address: Address =
  Address {
    payment_credential: Script(fixture_governor_hash),
    stake_credential: None,
  }

const fixture_proposal_value: Value =
  assets.from_lovelace(10_000_000)
    |> add(fixture_proposal_policy, fixture_proposal_asset, 1)

const fixture_proposal: ProposalDatum =
  ProposalDatum {
    schema_version: cardano_schema_version,
    id: 1,
    proposal_policy_id: fixture_proposal_policy,
    proposal_asset_name: fixture_proposal_asset,
    proposer: fixture_proposer,
    description_hash: #"8080808080808080808080808080808080808080808080808080808080808080",
    action_hash: #"9090909090909090909090909090909090909090909090909090909090909090",
    target_script_hash: #"a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0",
    created_at: 0,
    for_votes: 0,
    against_votes: 0,
    quorum: 1,
    deadline: 1_000,
    status: Pending,
    voters: [],
  }

const fixture_proposal_input: Input =
  Input {
    output_reference: fixture_proposal_ref,
    output: Output {
      address: fixture_proposal_address,
      value: fixture_proposal_value,
      datum: InlineDatum(fixture_proposal),
      reference_script: None,
    },
  }

test cancel_burns_authentication_asset_and_refunds_exact_value() {
  let refund =
    Output {
      address: Address {
        payment_credential: VerificationKey(fixture_proposer),
        stake_credential: None,
      },
      value: add(
        fixture_proposal_value,
        fixture_proposal_policy,
        fixture_proposal_asset,
        -1,
      ),
      datum: NoDatum,
      reference_script: None,
    }
  governor.spend(
    fixture_vams_policy,
    "VAMS",
    fixture_timelock_hash,
    [fixture_proposal.target_script_hash],
    5_000_000,
    100,
    1,
    172_800_000,
    604_800_000,
    Some(fixture_proposal),
    Cancel,
    fixture_proposal_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_proposal_input],
      outputs: [refund],
      mint: assets.from_asset(
        fixture_proposal_policy,
        fixture_proposal_asset,
        -1,
      ),
      validity_range: interval.before(999),
      extra_signatories: [fixture_proposer],
    },
  )
}

test cancel_rejects_unauthorized_signer() fail {
  governor.spend(
    fixture_vams_policy,
    "VAMS",
    fixture_timelock_hash,
    [fixture_proposal.target_script_hash],
    5_000_000,
    100,
    1,
    172_800_000,
    604_800_000,
    Some(fixture_proposal),
    Cancel,
    fixture_proposal_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_proposal_input],
      mint: assets.from_asset(
        fixture_proposal_policy,
        fixture_proposal_asset,
        -1,
      ),
      validity_range: interval.before(999),
      extra_signatories: [
        #"ffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
      ],
    },
  )
}

const fixture_voter: ByteArray =
  #"b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0"

fn fixture_voter_input() -> Input {
  Input {
    output_reference: OutputReference {
      transaction_id: #"b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1",
      output_index: 0,
    },
    output: Output {
      address: Address {
        payment_credential: VerificationKey(fixture_voter),
        stake_credential: None,
      },
      value: assets.from_asset(fixture_vams_policy, "VAMS", 100),
      datum: NoDatum,
      reference_script: None,
    },
  }
}

test vote_recreates_one_exact_successor() {
  let expected =
    ProposalDatum {
      ..fixture_proposal,
      for_votes: 10,
      status: Active,
      voters: [fixture_voter],
    }
  let successor =
    Output {
      address: fixture_proposal_address,
      value: fixture_proposal_value,
      datum: InlineDatum(expected),
      reference_script: None,
    }
  governor.spend(
    fixture_vams_policy,
    "VAMS",
    fixture_timelock_hash,
    [fixture_proposal.target_script_hash],
    5_000_000,
    100,
    1,
    172_800_000,
    604_800_000,
    Some(fixture_proposal),
    Vote { support: True, weight: 10 },
    fixture_proposal_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_proposal_input, fixture_voter_input()],
      outputs: [successor],
      validity_range: interval.before(999),
      extra_signatories: [fixture_voter],
    },
  )
}

test vote_rejects_duplicate_voter() fail {
  let voted =
    ProposalDatum {
      ..fixture_proposal,
      status: Active,
      voters: [fixture_voter],
    }
  let voted_input =
    Input {
      ..fixture_proposal_input,
      output: Output {
        ..fixture_proposal_input.output,
        datum: InlineDatum(voted),
      },
    }
  governor.spend(
    fixture_vams_policy,
    "VAMS",
    fixture_timelock_hash,
    [fixture_proposal.target_script_hash],
    5_000_000,
    100,
    1,
    172_800_000,
    604_800_000,
    Some(voted),
    Vote { support: True, weight: 10 },
    fixture_proposal_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [voted_input, fixture_voter_input()],
      validity_range: interval.before(999),
      extra_signatories: [fixture_voter],
    },
  )
}

test vote_rejects_value_substitution() fail {
  let expected =
    ProposalDatum {
      ..fixture_proposal,
      for_votes: 10,
      status: Active,
      voters: [fixture_voter],
    }
  let substituted =
    Output {
      address: fixture_proposal_address,
      value: assets.from_lovelace(10_000_001)
        |> add(fixture_proposal_policy, fixture_proposal_asset, 1),
      datum: InlineDatum(expected),
      reference_script: None,
    }
  governor.spend(
    fixture_vams_policy,
    "VAMS",
    fixture_timelock_hash,
    [fixture_proposal.target_script_hash],
    5_000_000,
    100,
    1,
    172_800_000,
    604_800_000,
    Some(fixture_proposal),
    Vote { support: True, weight: 10 },
    fixture_proposal_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_proposal_input, fixture_voter_input()],
      outputs: [substituted],
      validity_range: interval.before(999),
      extra_signatories: [fixture_voter],
    },
  )
}

test execute_rejects_malformed_timelock_intent() fail {
  let approved =
    ProposalDatum { ..fixture_proposal, for_votes: 1, status: Active }
  let approved_input =
    Input {
      ..fixture_proposal_input,
      output: Output {
        ..fixture_proposal_input.output,
        datum: InlineDatum(approved),
      },
    }
  let malformed_intent =
    IntentDatum {
      schema_version: cardano_schema_version,
      proposal_policy_id: fixture_proposal_policy,
      proposal_asset_name: fixture_proposal_asset,
      source_proposal: fixture_proposal_ref,
      action_hash: #"ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
      target_script_hash: fixture_proposal.target_script_hash,
      execute_after: 1001 + 172_800_000,
      expires_at: 1001 + 172_800_000 + 604_800_000,
      refund_key_hash: fixture_proposer,
    }
  governor.spend(
    fixture_vams_policy,
    "VAMS",
    fixture_timelock_hash,
    [fixture_proposal.target_script_hash],
    5_000_000,
    100,
    1,
    172_800_000,
    604_800_000,
    Some(approved),
    Execute,
    fixture_proposal_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [approved_input],
      outputs: [
        Output {
          address: Address {
            payment_credential: Script(fixture_timelock_hash),
            stake_credential: None,
          },
          value: fixture_proposal_value,
          datum: InlineDatum(malformed_intent),
          reference_script: None,
        },
      ],
      validity_range: interval.between(1001, 2000),
    },
  )
}
