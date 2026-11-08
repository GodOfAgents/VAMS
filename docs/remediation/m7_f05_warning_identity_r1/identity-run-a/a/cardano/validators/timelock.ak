use aiken/collection/list
use aiken/interval.{Finite}
use cardano/transaction.{InlineDatum, OutputReference, Transaction}
use vams/governance.{
  bounded_tx, finite_after, finite_interval, intent_immutable,
  max_intent_lifetime_ms, normal_delay_ms, signer_threshold, valid_domain,
  valid_hash, valid_vkh,
}
use vams/types.{
  AuthorityDatumV1, CancelIntent, ExecuteIntent, ExpireIntent,
  GovernanceConfigV1, IntentDatumV1, TimelockRedeemer,
}

validator timelock_validator {
  spend(
    datum_opt: Option<IntentDatumV1>,
    redeemer: TimelockRedeemer,
    own_ref: OutputReference,
    tx: Transaction,
  ) {
    expect Some(before) = datum_opt
    expect bounded_tx(tx)
    expect finite_interval(tx)
    expect valid_intent(before)
    expect Some(_) =
      list.find(tx.inputs, fn(input) { input.output_reference == own_ref })
    when redeemer is {
      CancelIntent -> {
        expect !before.consumed
        expect Some(config) = find_authority_config(tx)
        expect
          signer_threshold(
            tx.extra_signatories,
            config.members,
            config.threshold,
          )
        True
      }
      ExpireIntent -> {
        expect !before.consumed
        expect finite_after(tx, before.execute_after + before.lifetime)
        True
      }
      ExecuteIntent ->
        // F05 has not supplied an authenticated finality/replay contract.
        False
    }
  }

  else(_) {
    fail
  }
}

fn valid_intent(datum: IntentDatumV1) -> Bool {
  datum.version == 1 && valid_hash(datum.proposal_id) && valid_hash(
    datum.proposal_asset,
  ) && valid_hash(datum.action_hash) && valid_hash(datum.payload_hash) && valid_domain(
    datum.target_domain,
  ) && datum.policy_epoch >= 0 && datum.nonce >= 0 && datum.queue_time >= 0 && datum.execute_after == datum.queue_time + normal_delay_ms && datum.lifetime == max_intent_lifetime_ms && valid_vkh(
    datum.proposer_vkh,
  )
}

fn find_authority_config(tx: Transaction) -> Option<GovernanceConfigV1> {
  when list.find(tx.inputs, fn(input) { True }) is {
    Some(input) ->
      when input.output.datum is {
        InlineDatum(raw) -> {
          expect datum: AuthorityDatumV1 = raw
          Some(datum.config)
        }
        _ -> None
      }
    None -> None
  }
}
