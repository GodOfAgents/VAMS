use aiken/collection/list
use aiken/interval.{Finite}
use cardano/address.{Script, VerificationKey}
use cardano/assets
use cardano/transaction.{InlineDatum, Input, OutputReference, Transaction}
use vams/governance.{
  bounded_tx, config_valid, finite_after, finite_before, finite_interval, isqrt,
  max_voters, max_voting_duration_ms, proposal_immutable, signer_threshold,
  unique_bytes, valid_domain, valid_hash, valid_lock, valid_vkh,
}
use vams/types.{
  AdvanceIntentNonce, AdvanceProposalNonce, AuthorityDatumV1, AuthorityRedeemer,
  Cancel, CreateProposal, FinalizePassed, FinalizeRejected, Genesis,
  GovernorRedeemer, ProposalCancelled, ProposalDatumV1, ProposalPassed,
  ProposalPending, ProposalRejected, ProposalStatusV1, Queue, Vote,
  VoteLockRecordV1,
}

validator authority_validator(
  authority_policy_id: ByteArray,
  authority_asset_name: ByteArray,
) {
  spend(
    datum_opt: Option<AuthorityDatumV1>,
    redeemer: AuthorityRedeemer,
    own_ref: OutputReference,
    tx: Transaction,
  ) {
    expect Some(before) = datum_opt
    expect bounded_tx(tx)
    expect Some(own_input) =
      list.find(tx.inputs, fn(input) { input.output_reference == own_ref })
    expect
      assets.quantity_of(
        own_input.output.value,
        authority_policy_id,
        authority_asset_name,
      ) == 1
    expect
      list.length(
        list.filter(
          tx.inputs,
          fn(input) {
            assets.quantity_of(
              input.output.value,
              authority_policy_id,
              authority_asset_name,
            ) == 1
          },
        ),
      ) == 1
    when redeemer is {
      AdvanceProposalNonce -> {
        expect Some(datum) = authority_continuation(tx, own_input)
        expect config_valid(before.config)
        expect config_valid(datum.config)
        expect datum.config.version == before.config.version
        expect
          datum.config.authority_policy_id == before.config.authority_policy_id
        expect datum.config.members == before.config.members
        expect datum.config.threshold == before.config.threshold
        expect
          datum.config.next_proposal_nonce == before.config.next_proposal_nonce + 1
        expect datum.config.next_intent_nonce == before.config.next_intent_nonce
        True
      }
      AdvanceIntentNonce -> {
        expect Some(datum) = authority_continuation(tx, own_input)
        expect config_valid(before.config)
        expect config_valid(datum.config)
        expect datum.config.version == before.config.version
        expect
          datum.config.authority_policy_id == before.config.authority_policy_id
        expect datum.config.members == before.config.members
        expect datum.config.threshold == before.config.threshold
        expect
          datum.config.next_proposal_nonce == before.config.next_proposal_nonce
        expect
          datum.config.next_intent_nonce == before.config.next_intent_nonce + 1
        True
      }
      Genesis -> False
    }
  }

  else(_) {
    fail
  }
}

validator governor_validator {
  spend(
    datum_opt: Option<ProposalDatumV1>,
    redeemer: GovernorRedeemer,
    own_ref: OutputReference,
    tx: Transaction,
  ) {
    expect Some(before) = datum_opt
    expect bounded_tx(tx)
    expect finite_interval(tx)
    expect valid_proposal(before)
    expect Some(own_input) =
      list.find(tx.inputs, fn(input) { input.output_reference == own_ref })
    expect Script(_) = own_input.output.address.payment_credential
    when redeemer is {
      CreateProposal -> False
      Vote { support, locked_vams } -> {
        expect before.status == ProposalPending
        expect list.length(before.locks) < max_voters
        expect
          !list.any(
            before.locks,
            fn(lock) {
              when tx.extra_signatories is {
                [signer, ..] -> lock.voter_vkh == signer
                _ -> False
              }
            },
          )
        expect [voter, ..] = tx.extra_signatories
        expect valid_vkh(voter)
        expect list.has(tx.extra_signatories, voter)
        expect locked_vams > 0
        expect locked_vams <= 1_000_000_000
        expect isqrt(locked_vams) > 0
        expect finite_before(tx, before.deadline)
        expect valid_vote_continuation(tx, own_input, before, support, locked_vams, voter)
        True
      }
      FinalizePassed -> {
        expect before.status == ProposalPending
        expect finite_after(tx, before.deadline)
        expect before.yes_weight + before.no_weight >= before.quorum
        expect before.yes_weight > before.no_weight
        expect valid_status_continuation(tx, own_input, before, ProposalPassed)
        True
      }
      FinalizeRejected -> {
        expect before.status == ProposalPending
        expect finite_after(tx, before.deadline)
        expect
          before.yes_weight + before.no_weight < before.quorum || before.yes_weight <= before.no_weight
        expect valid_status_continuation(tx, own_input, before, ProposalRejected)
        True
      }
      Cancel -> {
        expect before.status == ProposalPending
        expect finite_before(tx, before.deadline)
        expect list.has(tx.extra_signatories, before.proposer_vkh)
        expect valid_status_continuation(tx, own_input, before, ProposalCancelled)
        True
      }
      Queue -> {
        expect before.status == ProposalPassed
        expect finite_interval(tx)
        expect list.length(tx.extra_signatories) <= 5
        expect list.length(tx.inputs) >= 2
        True
      }
    }
  }

  else(_) {
    fail
  }
}

fn valid_proposal(datum: ProposalDatumV1) -> Bool {
  datum.version == 1 && valid_hash(datum.proposal_asset) && datum.nonce >= 0 && valid_vkh(
    datum.proposer_vkh,
  ) && valid_hash(datum.description_hash) && valid_hash(datum.action_hash) && valid_domain(
    datum.target_domain,
  ) && datum.policy_epoch >= 0 && datum.quorum > 0 && datum.deadline >= 0 && datum.yes_weight >= 0 && datum.no_weight >= 0 && list.length(
    datum.locks,
  ) <= max_voters && unique_locks(datum.locks) && list.all(
    datum.locks,
    valid_lock,
  )
}

fn unique_locks(locks: List<VoteLockRecordV1>) -> Bool {
  let voters = list.map(locks, fn(lock) { lock.voter_vkh })
  unique_bytes(voters)
}

fn valid_vote_continuation(
  tx: Transaction,
  own_input: Input,
  before: ProposalDatumV1,
  support: Bool,
  locked: Int,
  voter: ByteArray,
) -> Bool {
  when list.find(tx.outputs, fn(output) {
    output.address == own_input.output.address
  }) is {
    Some(output) ->
      when output.datum is {
        InlineDatum(raw) -> {
          expect after: ProposalDatumV1 = raw
          proposal_immutable(before, after) && after.status == ProposalPending && list.length(
            after.locks,
          ) == list.length(before.locks) + 1 && after.yes_weight == before.yes_weight + if support {
            isqrt(locked)
          } else {
            0
          } && after.no_weight == before.no_weight + if support {
            0
          } else {
            isqrt(locked)
          } && list.any(
            after.locks,
            fn(lock) {
              lock.voter_vkh == voter && lock.locked_vams == locked && lock.support == support
            },
          )
        }
        _ -> False
      }
    None -> False
  }
}

fn valid_status_continuation(
  tx: Transaction,
  own_input: Input,
  before: ProposalDatumV1,
  status: ProposalStatusV1,
) -> Bool {
  when list.find(tx.outputs, fn(output) {
    output.address == own_input.output.address
  }) is {
    Some(output) ->
      when output.datum is {
        InlineDatum(raw) -> {
          expect after: ProposalDatumV1 = raw
          proposal_immutable(before, after) && after.status == status && after.yes_weight == before.yes_weight && after.no_weight == before.no_weight && after.locks == before.locks
        }
        _ -> False
      }
    None -> False
  }
}

fn authority_continuation(tx: Transaction, own_input: Input) -> Option<AuthorityDatumV1> {
  when list.find(tx.outputs, fn(output) {
    output.address == own_input.output.address
  }) is {
    Some(output) ->
      when output.datum is {
        InlineDatum(raw) -> {
          expect datum: AuthorityDatumV1 = raw
          Some(datum)
        }
        _ -> None
      }
    None -> None
  }
}
