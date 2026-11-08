use aiken/collection/dict
use aiken/collection/list
use aiken/primitive/bytearray
use cardano/address.{Script}
use cardano/assets.{PolicyId}
use cardano/transaction.{InlineDatum, OutputReference, Transaction}
use vams/governance.{
  authority_asset_name, bounded_tx, config_valid, finite_interval,
  intent_asset_name, proposal_asset_name, receipt_asset_name,
  valid_domain, valid_hash, valid_vkh,
}
use vams/types.{
  AuthorityDatumV1, AuthorityRedeemer, Cancel, CreateProposal, FinalizeRejected,
  Genesis, GovernanceConfigV1, GovernorRedeemer, IntentDatumV1, ProposalDatumV1,
  ProposalPending, Queue, Vote, VoteLockRecordV1,
}

validator authority_policy(seed_ref: OutputReference) {
  mint(redeemer: AuthorityRedeemer, policy_id: PolicyId, tx: Transaction) {
    expect bounded_tx(tx)
    expect finite_interval(tx)
    when redeemer is {
      Genesis -> {
        expect count_seed(tx, seed_ref) == 1
        expect exactly_one_mint(tx, policy_id, 1)
        expect Some(config) = find_authority_config(tx)
        expect config_valid(config)
        expect config.seed == seed_ref
        expect config.authority_policy_id == policy_id
        expect minted_name(tx, policy_id) == authority_asset_name(config)
        expect minted_asset_len(tx, policy_id)
        True
      }
      _ -> False
    }
  }

  else(_) {
    fail
  }
}

validator proposal_policy {
  mint(redeemer: GovernorRedeemer, policy_id: PolicyId, tx: Transaction) {
    expect bounded_tx(tx)
    expect finite_interval(tx)
    when redeemer is {
      CreateProposal -> {
        expect exactly_one_mint(tx, policy_id, 1)
        expect Some(datum) = find_proposal(tx)
        expect datum.status == ProposalPending
        expect datum.proposal_asset == minted_name(tx, policy_id)
        expect Some(config) = find_authority_config(tx)
        expect
          minted_name(tx, policy_id) == proposal_asset_name(
            config,
            datum.proposer_vkh,
            datum.action_hash,
            datum.target_domain,
            datum.nonce,
          )
        expect valid_proposal_shape(datum)
        True
      }
      FinalizeRejected -> burn_one(tx, policy_id)
      Cancel -> burn_one(tx, policy_id)
      Queue -> burn_one(tx, policy_id)
      _ -> False
    }
  }

  else(_) {
    fail
  }
}

validator receipt_policy {
  mint(redeemer: GovernorRedeemer, policy_id: PolicyId, tx: Transaction) {
    expect bounded_tx(tx)
    expect finite_interval(tx)
    when redeemer is {
      Vote { support, locked_vams } -> {
        expect exactly_one_mint(tx, policy_id, 1)
        expect locked_vams > 0
        expect [voter, ..] = tx.extra_signatories
        expect valid_vkh(voter)
        expect Some(datum) = find_proposal(tx)
        expect list.length(datum.locks) <= 8
        expect datum.locks != []
        expect Some(proposal_policy) = find_input_script_policy(tx)
        expect
          minted_name(tx, policy_id) == receipt_asset_name(
            policy_id,
            proposal_policy,
            datum.proposal_asset,
            voter,
            locked_vams,
            support,
            list.length(datum.locks) - 1,
          )
        expect
          list.any(
            datum.locks,
            fn(lock) {
              lock.voter_vkh == voter && lock.locked_vams == locked_vams && lock.support == support && lock.receipt_name == minted_name(
                tx,
                policy_id,
              )
            },
          )
        True
      }
      FinalizeRejected -> burn_all(tx, policy_id)
      Cancel -> burn_all(tx, policy_id)
      Queue -> burn_all(tx, policy_id)
      _ -> False
    }
  }

  else(_) {
    fail
  }
}

validator intent_policy {
  mint(redeemer: GovernorRedeemer, policy_id: PolicyId, tx: Transaction) {
    expect bounded_tx(tx)
    expect finite_interval(tx)
    when redeemer is {
      Queue -> {
        expect exactly_one_mint(tx, policy_id, 1)
        expect Some(datum) = find_intent(tx)
        expect datum.consumed == False
        expect datum.proposal_asset != ""
        expect datum.proposal_id != ""
        expect datum.execute_after == datum.queue_time + 86_400_000
        expect datum.lifetime == 604_800_000
        expect datum.proposal_asset != minted_name(tx, policy_id)
        expect Some(proposal_policy) = find_input_script_policy(tx)
        expect
          minted_name(tx, policy_id) == intent_asset_name(
            policy_id,
            proposal_policy,
            datum.proposal_asset,
            datum.proposer_vkh,
            datum.queue_time,
            datum.action_hash,
          )
        True
      }
      _ -> False
    }
  }

  else(_) {
    fail
  }
}

fn count_seed(tx: Transaction, seed: OutputReference) -> Int {
  list.length(
    list.filter(tx.inputs, fn(input) { input.output_reference == seed }),
  )
}

fn exactly_one_mint(tx: Transaction, policy: PolicyId, quantity: Int) -> Bool {
  when dict.to_pairs(assets.tokens(tx.mint, policy)) is {
    [Pair(_, amount)] -> amount == quantity
    _ -> False
  }
}

fn burn_one(tx: Transaction, policy: PolicyId) -> Bool {
  when dict.to_pairs(assets.tokens(tx.mint, policy)) is {
    [Pair(_, amount)] -> amount == -1
    _ -> False
  }
}

fn burn_all(tx: Transaction, policy: PolicyId) -> Bool {
  when dict.to_pairs(assets.tokens(tx.mint, policy)) is {
    [_] -> True
    _ -> False
  }
}

fn minted_name(tx: Transaction, policy: PolicyId) -> ByteArray {
  when dict.to_pairs(assets.tokens(tx.mint, policy)) is {
    [Pair(name, _)] -> name
    _ -> ""
  }
}

fn minted_asset_len(tx: Transaction, policy: PolicyId) -> Bool {
  bytearray.length(minted_name(tx, policy)) == 32
}

fn find_authority_config(tx: Transaction) -> Option<GovernanceConfigV1> {
  when list.find(tx.outputs, fn(output) {
    when output.datum is {
      InlineDatum(raw) -> {
        expect datum: AuthorityDatumV1 = raw
        config_valid(datum.config) && assets.quantity_of(
          output.value,
          datum.config.authority_policy_id,
          authority_asset_name(datum.config),
        ) == 1
      }
      _ -> False
    }
  }) is {
    Some(output) ->
      when output.datum is {
        InlineDatum(raw) -> {
          expect datum: AuthorityDatumV1 = raw
          Some(datum.config)
        }
        _ -> None
      }
    None -> None
  }
}

fn find_input_script_policy(tx: Transaction) -> Option<ByteArray> {
  when
    list.find(
      tx.inputs,
      fn(input) {
        when input.output.address.payment_credential is {
          Script(_) -> True
          _ -> False
        }
      },
    )
  is {
    Some(input) ->
      when input.output.address.payment_credential is {
        Script(hash) -> Some(hash)
        _ -> None
      }
    None -> None
  }
}

fn find_proposal(tx: Transaction) -> Option<ProposalDatumV1> {
  when list.find(tx.outputs, fn(_output) { True }) is {
    Some(output) ->
      when output.datum is {
        InlineDatum(raw) -> {
          expect datum: ProposalDatumV1 = raw
          Some(datum)
        }
        _ -> None
      }
    None -> None
  }
}

fn find_intent(tx: Transaction) -> Option<IntentDatumV1> {
  when list.find(tx.outputs, fn(_output) { True }) is {
    Some(output) ->
      when output.datum is {
        InlineDatum(raw) -> {
          expect datum: IntentDatumV1 = raw
          Some(datum)
        }
        _ -> None
      }
    None -> None
  }
}

fn valid_proposal_shape(datum: ProposalDatumV1) -> Bool {
  datum.version == 1 && valid_hash(datum.proposal_asset) && valid_vkh(
    datum.proposer_vkh,
  ) && valid_hash(datum.description_hash) && valid_hash(datum.action_hash) && valid_domain(
    datum.target_domain,
  ) && datum.quorum > 0 && datum.deadline >= 0 && datum.yes_weight == 0 && datum.no_weight == 0 && datum.locks == []
}

