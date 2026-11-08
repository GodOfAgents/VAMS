//// Complete transaction predicates shared by all v2 spend/mint callers.
//// Compilation, ledger/budget checks and independent review are NOT yet run.
use aiken/collection/list
use cardano/address.{Script}
use cardano/assets
use cardano/transaction.{InlineDatum, Input, OutputReference, Transaction}
use vams/governance.{isqrt}
use vams/governance_v2.{
  authority_name, authority_value, before_ms, bootstrap_valid, config_valid,
  delay_ms, digest32, envelope, funded_outputs, inline_output, intent_name,
  key_address, key_hash, lifetime_ms, matches_bootstrap, now_ms,
  payment_output, proposal_commitment, proposal_valid, proposal_value,
  read_authority, read_proposal, receipt_burns, receipt_name, script_address,
  small_datum, threshold, u64_max, uint64, upper_ms, voter_limit, voter_refunds,
  voting_duration_ms,
}
use vams/governance_v2_types.{
  AuthorityDatumV2, CancelIntentV2, CancelProposalV2, CreateV2, ExecuteIntentV2,
  ExpireIntentV2, FinalizePassedV2, FinalizeRejectedV2, GovernanceActionV2,
  GovernanceAnchorV2, GovernanceBootstrapV2, GovernanceConfigV2, GovernanceRequestV2,
  IntentDatumV2, PassedV2, PendingV2, ProposalDatumV2,
  QueueV2, VoteLockV2, VoteV2,
}

pub fn request_action(request: GovernanceRequestV2) -> GovernanceActionV2 {
  expect request.version == 2
  request.action
}

pub fn create(anchor: GovernanceAnchorV2, tx: Transaction) -> Bool {
  expect envelope(tx)
  let (authority, c) = read_authority(anchor, tx, True)
  expect c.next_proposal_nonce < u64_max && threshold(c, tx)
  expect Some(proposal_output) = list.at(tx.outputs, 1)
  expect InlineDatum(raw) = proposal_output.datum
  expect small_datum(raw)
  expect p: ProposalDatumV2 = raw
  expect p.state == PendingV2 && p.locks == []
  expect p.nonce == c.next_proposal_nonce
  expect list.has(tx.extra_signatories, p.proposer_vkh)
  expect p.deadline > now_ms(tx) && p.deadline <= now_ms(tx) + voting_duration_ms
  expect proposal_valid(c, p)
  expect tx.mint == assets.from_asset(c.proposal_policy_id, p.proposal_asset, 1)
  let next = AuthorityDatumV2 {
    config: GovernanceConfigV2 { ..c, next_proposal_nonce: c.next_proposal_nonce + 1 },
  }
  funded_outputs(c, tx, [authority], [
    inline_output(script_address(c.authority_policy_id), authority_value(c), next),
    inline_output(script_address(c.governor_script_hash), proposal_value(c, p), p),
  ], c.proposal_base_lovelace, 0, None)
}

pub fn vote(anchor: GovernanceAnchorV2, tx: Transaction, voter: ByteArray, support: Bool, locked: Int) -> Bool {
  expect envelope(tx)
  let (_, c) = read_authority(anchor, tx, False)
  let (input, p) = read_proposal(c, tx)
  expect p.state == PendingV2 && before_ms(tx, p.deadline)
  expect key_hash(voter) && tx.extra_signatories == [voter]
  expect list.length(p.locks) < voter_limit
  expect !list.any(p.locks, fn(lock) { lock.voter_vkh == voter })
  expect locked > 0 && locked <= c.max_lock_vams
  let initial = VoteLockV2 {
    voter_vkh: voter, locked_vams: locked, support, weight: isqrt(locked), receipt_name: #"",
  }
  let added = VoteLockV2 {
    ..initial, receipt_name: receipt_name(c, p.proposal_asset, initial, list.length(p.locks)),
  }
  let after = ProposalDatumV2 {
    ..p,
    locks: list.concat(p.locks, [added]),
    yes_weight: p.yes_weight + if support { added.weight } else { 0 },
    no_weight: p.no_weight + if support { 0 } else { added.weight },
  }
  expect proposal_valid(c, after)
  expect tx.mint == assets.from_asset(c.receipt_policy_id, added.receipt_name, 1)
  funded_outputs(c, tx, [input], [
    inline_output(script_address(c.governor_script_hash), proposal_value(c, after), after),
  ], c.per_voter_refund_lovelace, locked, Some(voter))
}

pub fn finalize_passed(anchor: GovernanceAnchorV2, tx: Transaction) -> Bool {
  expect envelope(tx)
  let (_, c) = read_authority(anchor, tx, False)
  let (input, p) = read_proposal(c, tx)
  expect p.state == PendingV2 && now_ms(tx) >= p.deadline
  expect p.yes_weight + p.no_weight >= p.quorum && p.yes_weight > p.no_weight
  expect tx.mint == assets.zero
  let after = ProposalDatumV2 { ..p, state: PassedV2 }
  funded_outputs(c, tx, [input], [
    inline_output(script_address(c.governor_script_hash), input.output.value, after),
  ], 0, 0, None)
}

pub fn terminal_proposal(anchor: GovernanceAnchorV2, tx: Transaction, cancel: Bool) -> Bool {
  expect envelope(tx)
  let (_, c) = read_authority(anchor, tx, False)
  let (input, p) = read_proposal(c, tx)
  expect p.state == PendingV2
  expect if cancel {
    before_ms(tx, p.deadline) && list.has(tx.extra_signatories, p.proposer_vkh)
  } else {
    now_ms(tx) >= p.deadline && (p.yes_weight + p.no_weight < p.quorum || p.yes_weight <= p.no_weight)
  }
  expect tx.mint == receipt_burns(c, p)
  let refunds = list.concat(voter_refunds(c, p), [
    payment_output(key_address(p.proposer_vkh), assets.from_lovelace(c.proposal_base_lovelace)),
  ])
  funded_outputs(c, tx, [input], refunds, 0, 0, None)
}

pub fn queue(anchor: GovernanceAnchorV2, tx: Transaction) -> Bool {
  expect envelope(tx)
  let (authority, c) = read_authority(anchor, tx, True)
  let (input, p) = read_proposal(c, tx)
  expect p.state == PassedV2 && now_ms(tx) >= p.deadline
  expect c.next_intent_nonce < u64_max && threshold(c, tx)
  expect list.has(tx.extra_signatories, p.proposer_vkh)
  let queued = upper_ms(tx)
  expect uint64(queued + delay_ms + lifetime_ms)
  let intent = IntentDatumV2 {
    version: 2, proposal_id: proposal_commitment(p), proposal_asset: p.proposal_asset,
    action_hash: p.action_hash, payload_hash: p.payload_hash, target_domain: p.target_domain,
    policy_epoch: c.policy_epoch, nonce: c.next_intent_nonce, queue_time: queued,
    execute_after: queued + delay_ms, lifetime: lifetime_ms, proposer_vkh: p.proposer_vkh,
    consumed: False,
  }
  let name = intent_name(c, intent)
  expect tx.mint == assets.add(receipt_burns(c, p), c.intent_policy_id, name, 1)
  let next = AuthorityDatumV2 {
    config: GovernanceConfigV2 { ..c, next_intent_nonce: c.next_intent_nonce + 1 },
  }
  let expected = list.concat([
    inline_output(script_address(c.authority_policy_id), authority_value(c), next),
  ], list.concat(voter_refunds(c, p), [
    inline_output(script_address(c.timelock_script_hash),
      assets.from_lovelace(c.proposal_base_lovelace) |> assets.add(c.intent_policy_id, name, 1), intent),
  ]))
  funded_outputs(c, tx, [authority, input], expected, 0, 0, None)
}

fn read_intent(c: GovernanceConfigV2, tx: Transaction) -> (Input, IntentDatumV2) {
  expect [input] = list.filter(tx.inputs, fn(input) { input.output.address == script_address(c.timelock_script_hash) })
  expect input.output.reference_script == None
  expect InlineDatum(raw) = input.output.datum
  expect small_datum(raw)
  expect i: IntentDatumV2 = raw
  expect i.version == 2 && !i.consumed
  expect digest32(i.proposal_id) && digest32(i.proposal_asset)
  expect digest32(i.action_hash) && digest32(i.payload_hash) && key_hash(i.proposer_vkh)
  expect i.policy_epoch == c.policy_epoch && list.has(c.target_domains, i.target_domain)
  expect uint64(i.nonce) && i.nonce < c.next_intent_nonce && uint64(i.queue_time)
  expect i.execute_after == i.queue_time + delay_ms && i.lifetime == lifetime_ms
  expect uint64(i.execute_after + i.lifetime)
  expect input.output.value == (assets.from_lovelace(c.proposal_base_lovelace)
    |> assets.add(c.intent_policy_id, intent_name(c, i), 1))
  (input, i)
}

pub fn terminal_intent(anchor: GovernanceAnchorV2, tx: Transaction, cancel: Bool) -> Bool {
  expect envelope(tx)
  let (_, c) = read_authority(anchor, tx, False)
  let (input, i) = read_intent(c, tx)
  expect if cancel { threshold(c, tx) } else { now_ms(tx) >= i.execute_after + i.lifetime }
  expect tx.mint == assets.from_asset(c.intent_policy_id, intent_name(c, i), -1)
  funded_outputs(c, tx, [input], [
    payment_output(key_address(i.proposer_vkh), assets.from_lovelace(c.proposal_base_lovelace)),
  ], 0, 0, None)
}

pub fn authority_genesis(b: GovernanceBootstrapV2, policy_id: ByteArray, tx: Transaction) -> Bool {
  expect envelope(tx) && bootstrap_valid(b) && key_hash(policy_id)
  expect tx.reference_inputs == []
  expect [seed] = tx.inputs
  expect seed.output_reference == b.seed
  expect Some(output) = list.at(tx.outputs, 0)
  expect InlineDatum(raw) = output.datum
  expect small_datum(raw)
  expect datum: AuthorityDatumV2 = raw
  let c = datum.config
  expect config_valid(c) && matches_bootstrap(c, b)
  expect c.authority_policy_id == policy_id && threshold(c, tx)
  expect c.next_proposal_nonce == 0 && c.next_intent_nonce == 0
  expect tx.mint == assets.from_asset(policy_id, authority_name(c), 1)
  funded_outputs(c, tx, [], [
    inline_output(script_address(policy_id), authority_value(c), datum),
  ], c.authority_state_lovelace, 0, None)
}

pub fn authority_spend(b: GovernanceBootstrapV2, before: AuthorityDatumV2, action: GovernanceActionV2, own_ref: OutputReference, tx: Transaction) -> Bool {
  expect envelope(tx) && bootstrap_valid(b) && config_valid(before.config)
  expect Some(own) = list.find(tx.inputs, fn(input) { input.output_reference == own_ref })
  expect Script(policy_id) = own.output.address.payment_credential
  let anchor = GovernanceAnchorV2 { policy_id, asset_name: authority_name(before.config) }
  let (authenticated, c) = read_authority(anchor, tx, True)
  expect authenticated.output_reference == own_ref && c == before.config
  expect matches_bootstrap(c, b)
  when action is {
    CreateV2 -> create(anchor, tx)
    QueueV2 -> queue(anchor, tx)
    _ -> False
  }
}

pub fn governor_spend(anchor: GovernanceAnchorV2, before: ProposalDatumV2, action: GovernanceActionV2, own_ref: OutputReference, tx: Transaction) -> Bool {
  expect envelope(tx)
  let consumed = action == QueueV2
  let (_, c) = read_authority(anchor, tx, consumed)
  let (input, p) = read_proposal(c, tx)
  expect input.output_reference == own_ref && p == before
  when action is {
    VoteV2 { voter_vkh, support, locked_vams } -> vote(anchor, tx, voter_vkh, support, locked_vams)
    FinalizePassedV2 -> finalize_passed(anchor, tx)
    FinalizeRejectedV2 -> terminal_proposal(anchor, tx, False)
    CancelProposalV2 -> terminal_proposal(anchor, tx, True)
    QueueV2 -> queue(anchor, tx)
    _ -> False
  }
}

pub fn timelock_spend(anchor: GovernanceAnchorV2, before: IntentDatumV2, action: GovernanceActionV2, own_ref: OutputReference, tx: Transaction) -> Bool {
  when action is {
    ExecuteIntentV2 -> False
    CancelIntentV2 -> {
      expect envelope(tx)
      let (_, c) = read_authority(anchor, tx, False)
      let (input, i) = read_intent(c, tx)
      expect input.output_reference == own_ref && i == before
      terminal_intent(anchor, tx, True)
    }
    ExpireIntentV2 -> {
      expect envelope(tx)
      let (_, c) = read_authority(anchor, tx, False)
      let (input, i) = read_intent(c, tx)
      expect input.output_reference == own_ref && i == before
      terminal_intent(anchor, tx, False)
    }
    _ -> False
  }
}

/// kind1 proposal, kind2 receipts, kind3 intents. No caller chooses a different
/// policy: each validator wrapper supplies a literal and authenticates own ID.
pub fn policy_mint(anchor: GovernanceAnchorV2, kind: Int, policy_id: ByteArray, action: GovernanceActionV2, tx: Transaction) -> Bool {
  expect envelope(tx)
  let consumed = action == CreateV2 || action == QueueV2
  let (_, c) = read_authority(anchor, tx, consumed)
  when kind is {
    1 -> {
      expect policy_id == c.proposal_policy_id
      when action is {
        CreateV2 -> create(anchor, tx)
        FinalizeRejectedV2 -> terminal_proposal(anchor, tx, False)
        CancelProposalV2 -> terminal_proposal(anchor, tx, True)
        QueueV2 -> queue(anchor, tx)
        _ -> False
      }
    }
    2 -> {
      expect policy_id == c.receipt_policy_id
      when action is {
        VoteV2 { voter_vkh, support, locked_vams } -> vote(anchor, tx, voter_vkh, support, locked_vams)
        FinalizeRejectedV2 -> terminal_proposal(anchor, tx, False)
        CancelProposalV2 -> terminal_proposal(anchor, tx, True)
        QueueV2 -> queue(anchor, tx)
        _ -> False
      }
    }
    3 -> {
      expect policy_id == c.intent_policy_id
      when action is {
        QueueV2 -> queue(anchor, tx)
        CancelIntentV2 -> terminal_intent(anchor, tx, True)
        ExpireIntentV2 -> terminal_intent(anchor, tx, False)
        _ -> False
      }
    }
    _ -> False
  }
}
