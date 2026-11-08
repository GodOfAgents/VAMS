//// Native candidate tests: NOT RUN until an Aiken runner is specifically authorized.
//// Synthetic transaction contexts do not establish ledger/applied-budget evidence.
use aiken/collection/list
use aiken/cbor
use aiken/primitive/bytearray
use aiken/interval
use cardano/address.{Address, Script, VerificationKey}
use cardano/assets
use cardano/transaction.{InlineDatum, Input, NoDatum, Output, OutputReference, Transaction, ValidityRange}
use vams/governance_v2
use vams/governance_v2_transitions
use vams/governance_v2_types.{
  AuthorityDatumV2, CancelIntentV2, CancelProposalV2, CreateV2, ExecuteIntentV2,
  ExpireIntentV2, FinalizePassedV2, FinalizeRejectedV2, GovernanceAnchorV2, GovernanceBootstrapV2,
  GovernanceConfigV2, GovernanceRequestV2, IntentDatumV2, PassedV2, PendingV2,
  ProposalDatumV2, QueueV2, VoteLockV2, VoteV2,
}
use vams/governance_v2_vectors

const alice: ByteArray = #"01010101010101010101010101010101010101010101010101010101"
const bob: ByteArray = #"02020202020202020202020202020202020202020202020202020202"
const proposer: ByteArray = #"03030303030303030303030303030303030303030303030303030303"
const member4: ByteArray = #"04040404040404040404040404040404040404040404040404040404"
const member5: ByteArray = #"05050505050505050505050505050505050505050505050505050505"
const authority_policy: ByteArray = #"00000000000000000000000000000000000000000000000000000000"
const governor_hash: ByteArray = #"11111111111111111111111111111111111111111111111111111111"
const timelock_hash: ByteArray = #"22222222222222222222222222222222222222222222222222222222"
const proposal_policy: ByteArray = #"33333333333333333333333333333333333333333333333333333333"
const receipt_policy: ByteArray = #"44444444444444444444444444444444444444444444444444444444"
const intent_policy: ByteArray = #"55555555555555555555555555555555555555555555555555555555"
const vams_policy: ByteArray = #"66666666666666666666666666666666666666666666666666666666"

fn ref(index: Int) -> OutputReference {
  OutputReference {
    transaction_id: #"1111111111111111111111111111111111111111111111111111111111111111",
    output_index: index,
  }
}

fn script(hash: ByteArray) -> Address {
  Address { payment_credential: Script(hash), stake_credential: None }
}

fn key(hash: ByteArray) -> Address {
  Address { payment_credential: VerificationKey(hash), stake_credential: None }
}

fn out(address: Address, value: assets.Value, data: Data) -> Output {
  Output { address, value, datum: InlineDatum(data), reference_script: None }
}

fn pay(address: Address, value: assets.Value) -> Output {
  Output { address, value, datum: NoDatum, reference_script: None }
}

fn cfg() -> GovernanceConfigV2 {
  GovernanceConfigV2 {
    version: 2, network_id: 0, policy_epoch: 2, seed: ref(7),
    authority_policy_id: authority_policy, governor_script_hash: governor_hash,
    timelock_script_hash: timelock_hash, proposal_policy_id: proposal_policy,
    receipt_policy_id: receipt_policy, intent_policy_id: intent_policy,
    vams_policy_id: vams_policy, vams_asset_name: #"56414d53",
    members: [alice, bob, proposer, member4, member5], threshold: 3,
    normal_delay_ms: 172_800_000, emergency_disabled: True,
    authority_state_lovelace: 5_000_000, proposal_base_lovelace: 3_000_000,
    per_voter_refund_lovelace: 1_000_000, next_proposal_nonce: 1,
    next_intent_nonce: 0, max_lock_vams: 1_000_000_000,
    target_domains: [#"70726570726f642f74657374"],
  }
}

fn anchor() -> GovernanceAnchorV2 {
  GovernanceAnchorV2 { policy_id: authority_policy, asset_name: governance_v2_vectors.authority_name }
}

fn bootstrap() -> GovernanceBootstrapV2 {
  GovernanceBootstrapV2 { seed: ref(7), network_id: 0, policy_epoch: 2,
    members: [alice, bob, proposer, member4, member5] }
}

fn authority(c: GovernanceConfigV2) -> Input {
  Input { output_reference: ref(0), output: out(script(authority_policy),
    assets.from_lovelace(5_000_000) |> assets.add(authority_policy, governance_v2_vectors.authority_name, 1),
    AuthorityDatumV2 { config: c }) }
}

fn initial() -> ProposalDatumV2 {
  ProposalDatumV2 {
    version: 2, state: PendingV2, proposal_asset: governance_v2_vectors.proposal_name,
    nonce: 0, proposer_vkh: proposer,
    description_hash: #"6666666666666666666666666666666666666666666666666666666666666666",
    action_hash: #"7777777777777777777777777777777777777777777777777777777777777777",
    payload_hash: #"8888888888888888888888888888888888888888888888888888888888888888",
    target_domain: #"70726570726f642f74657374", policy_epoch: 2,
    quorum: 10, deadline: 2000, yes_weight: 0, no_weight: 0, locks: [],
  }
}

fn first(support: Bool) -> ProposalDatumV2 {
  let p = initial()
  ProposalDatumV2 { ..p,
    yes_weight: if support { 10 } else { 0 }, no_weight: if support { 0 } else { 10 },
    locks: [VoteLockV2 { voter_vkh: alice, locked_vams: 100, support, weight: 10,
      receipt_name: if support { governance_v2_vectors.alice_yes_receipt } else { governance_v2_vectors.alice_no_receipt } }],
  }
}

fn passed() -> ProposalDatumV2 {
  ProposalDatumV2 { ..first(True), state: PassedV2 }
}

fn two() -> ProposalDatumV2 {
  let p = first(True)
  ProposalDatumV2 { ..p, yes_weight: 40, locks: list.concat(p.locks, [
    VoteLockV2 { voter_vkh: bob, locked_vams: 900, support: True, weight: 30,
      receipt_name: governance_v2_vectors.bob_yes_receipt_after_alice },
  ]) }
}

/// Expected fixture value is built independently of production proposal_value.
fn pvalue(p: ProposalDatumV2) -> assets.Value {
  let stake = list.foldl(p.locks, 0, fn(lock, sum) { sum + lock.locked_vams })
  let value = assets.from_lovelace(3_000_000 + list.length(p.locks) * 1_000_000)
    |> assets.add(proposal_policy, p.proposal_asset, 1)
    |> assets.add(vams_policy, #"56414d53", stake)
  list.foldl(p.locks, value, fn(lock, acc) { assets.add(acc, receipt_policy, lock.receipt_name, 1) })
}

fn proposal_input(p: ProposalDatumV2) -> Input {
  Input { output_reference: ref(1), output: out(script(governor_hash), pvalue(p), p) }
}

fn funding(vkh: ByteArray, lovelace: Int, vams: Int) -> Input {
  Input { output_reference: ref(2), output: pay(key(vkh), assets.from_lovelace(lovelace)
    |> assets.add(vams_policy, #"56414d53", vams)) }
}

fn half_open(lower: Int, upper: Int) -> ValidityRange {
  let range = interval.between(lower, upper)
  interval.Interval { ..range,
    upper_bound: interval.IntervalBound { ..range.upper_bound, is_inclusive: False } }
}

fn tx(lower: Int, upper: Int) -> Transaction {
  Transaction { ..transaction.placeholder, fee: 200_000,
    validity_range: half_open(lower, upper) }
}

fn vote_tx(second: Bool) -> Transaction {
  let before = if second { first(True) } else { initial() }
  let after = if second { two() } else { first(True) }
  let voter = if second { bob } else { alice }
  Transaction { ..tx(1000, 1100),
    inputs: [proposal_input(before), funding(voter, 5_000_000, if second { 900 } else { 100 })],
    reference_inputs: [authority(cfg())], extra_signatories: [voter],
    outputs: [out(script(governor_hash), pvalue(after), after), pay(key(voter), assets.from_lovelace(3_800_000))],
    mint: assets.from_asset(receipt_policy, if second { governance_v2_vectors.bob_yes_receipt_after_alice } else { governance_v2_vectors.alice_yes_receipt }, 1),
  }
}

fn historical_intent_fixture() -> IntentDatumV2 {
  let p = passed()
  IntentDatumV2 {
    version: 2, proposal_id: governance_v2_vectors.passed_alice_state,
    proposal_asset: p.proposal_asset, action_hash: p.action_hash, payload_hash: p.payload_hash,
    target_domain: p.target_domain, policy_epoch: 2, nonce: 0, queue_time: 2000,
    execute_after: 172_802_000, lifetime: 604_800_000, proposer_vkh: proposer, consumed: False,
  }
}

fn intent() -> IntentDatumV2 {
  IntentDatumV2 { ..historical_intent_fixture(), queue_time: 2100, execute_after: 172_802_100 }
}

fn queue_tx() -> Transaction {
  let c = cfg()
  Transaction { ..tx(2000, 2100),
    inputs: [authority(c), proposal_input(passed()), funding(proposer, 1_000_000, 0)],
    extra_signatories: [alice, bob, proposer],
    outputs: [
      out(script(authority_policy), assets.from_lovelace(5_000_000) |> assets.add(authority_policy, governance_v2_vectors.authority_name, 1),
        AuthorityDatumV2 { config: GovernanceConfigV2 { ..c, next_intent_nonce: 1 } }),
      pay(key(alice), assets.from_lovelace(1_000_000) |> assets.add(vams_policy, #"56414d53", 100)),
      out(script(timelock_hash), assets.from_lovelace(3_000_000) |> assets.add(intent_policy, governance_v2_vectors.queued_alice_intent_upper, 1), intent()),
      pay(key(proposer), assets.from_lovelace(800_000)),
    ],
    mint: assets.from_asset(proposal_policy, governance_v2_vectors.proposal_name, -1)
      |> assets.add(receipt_policy, governance_v2_vectors.alice_yes_receipt, -1)
      |> assets.add(intent_policy, governance_v2_vectors.queued_alice_intent_upper, 1),
  }
}

fn terminal_tx(cancel: Bool) -> Transaction {
  let p = first(cancel)
  Transaction { ..tx(if cancel { 1000 } else { 2000 }, if cancel { 1100 } else { 2100 }),
    inputs: [proposal_input(p), funding(proposer, 1_000_000, 0)],
    reference_inputs: [authority(cfg())], extra_signatories: [proposer],
    outputs: [pay(key(alice), assets.from_lovelace(1_000_000) |> assets.add(vams_policy, #"56414d53", 100)),
      pay(key(proposer), assets.from_lovelace(3_000_000)), pay(key(proposer), assets.from_lovelace(800_000))],
    mint: assets.from_asset(proposal_policy, governance_v2_vectors.proposal_name, -1)
      |> assets.add(receipt_policy, if cancel { governance_v2_vectors.alice_yes_receipt } else { governance_v2_vectors.alice_no_receipt }, -1),
  }
}

fn intent_tx(cancel: Bool) -> Transaction {
  let c = cfg()
  Transaction { ..tx(if cancel { 2000 } else { 777_602_100 }, if cancel { 2100 } else { 777_602_200 }),
    inputs: [Input { output_reference: ref(3), output: out(script(timelock_hash),
      assets.from_lovelace(3_000_000) |> assets.add(intent_policy, governance_v2_vectors.queued_alice_intent_upper, 1), intent()) },
      funding(proposer, 1_000_000, 0)],
    reference_inputs: [authority(GovernanceConfigV2 { ..c, next_intent_nonce: 1 })],
    extra_signatories: if cancel { [alice, bob, proposer] } else { [proposer] },
    outputs: [pay(key(proposer), assets.from_lovelace(3_000_000)), pay(key(proposer), assets.from_lovelace(800_000))],
    mint: assets.from_asset(intent_policy, governance_v2_vectors.queued_alice_intent_upper, -1),
  }
}

fn genesis_tx() -> Transaction {
  let c = cfg()
  let c = GovernanceConfigV2 { ..c, next_proposal_nonce: 0 }
  let seed = Input { output_reference: ref(7), output: pay(key(proposer), assets.from_lovelace(8_000_000)) }
  Transaction { ..tx(1000, 1100), inputs: [seed], extra_signatories: [alice, bob, proposer],
    mint: assets.from_asset(authority_policy, governance_v2_vectors.authority_name, 1),
    outputs: [out(script(authority_policy),
      assets.from_lovelace(5_000_000) |> assets.add(authority_policy, governance_v2_vectors.authority_name, 1),
      AuthorityDatumV2 { config: c }), pay(key(proposer), assets.from_lovelace(2_800_000))],
  }
}

fn create_tx() -> Transaction {
  let c = cfg()
  let before = GovernanceConfigV2 { ..c, next_proposal_nonce: 0 }
  let p = initial()
  Transaction { ..tx(1000, 1100),
    inputs: [authority(before), funding(proposer, 5_000_000, 0)],
    extra_signatories: [alice, bob, proposer],
    mint: assets.from_asset(proposal_policy, governance_v2_vectors.proposal_name, 1),
    outputs: [authority(c).output, out(script(governor_hash), pvalue(p), p),
      pay(key(proposer), assets.from_lovelace(1_800_000))],
  }
}

fn maximal_proposal() -> ProposalDatumV2 {
  let p = initial()
  let voters = [alice, bob, proposer, member4, member5,
    #"06060606060606060606060606060606060606060606060606060606",
    #"07070707070707070707070707070707070707070707070707070707",
    #"08080808080808080808080808080808080808080808080808080808"]
  let locks = list.indexed_map(voters, fn(index, voter) {
    let lock = VoteLockV2 { voter_vkh: voter, locked_vams: 100, support: True, weight: 10, receipt_name: #"" }
    VoteLockV2 { ..lock, receipt_name: governance_v2.receipt_name(cfg(), p.proposal_asset, lock, index) }
  })
  ProposalDatumV2 { ..p, yes_weight: 80, locks }
}

test golden_identifiers_match_reference_bytes() {
  let c = cfg()
  let p = initial()
  expect [a] = first(True).locks
  expect [n] = first(False).locks
  expect [_, b] = two().locks
  and {
    governance_v2.authority_name(c) == governance_v2_vectors.authority_name,
    governance_v2.proposal_name(c, p) == governance_v2_vectors.proposal_name,
    governance_v2.receipt_name(c, p.proposal_asset, a, 0) == governance_v2_vectors.alice_yes_receipt,
    governance_v2.receipt_name(c, p.proposal_asset, n, 0) == governance_v2_vectors.alice_no_receipt,
    governance_v2.receipt_name(c, p.proposal_asset, b, 1) == governance_v2_vectors.bob_yes_receipt_after_alice,
    governance_v2.proposal_commitment(passed()) == governance_v2_vectors.passed_alice_state,
    governance_v2.intent_name(c, historical_intent_fixture()) == governance_v2_vectors.queued_alice_intent,
  }
}

test valid_singleton_genesis_requires_configured_custody_and_seed() {
  governance_v2_transitions.authority_genesis(bootstrap(), authority_policy, genesis_tx())
}

test genesis_without_three_members_rejects() fail {
  let value = genesis_tx()
  expect governance_v2_transitions.authority_genesis(bootstrap(), authority_policy,
    Transaction { ..value, extra_signatories: [proposer] })
  True
}


test genesis_wrong_seed_rejects() fail {
  let value = genesis_tx()
  expect [seed] = value.inputs
  expect governance_v2_transitions.authority_genesis(bootstrap(), authority_policy,
    Transaction { ..value, inputs: [Input { ..seed, output_reference: ref(8) }] })
  True
}


test create_advances_exact_nonce_and_mints_bound_proposal() {
  let c = cfg()
  let before = AuthorityDatumV2 { config: GovernanceConfigV2 { ..c, next_proposal_nonce: 0 } }
  let value = create_tx()
  and {
    governance_v2_transitions.authority_spend(bootstrap(), before, CreateV2, ref(0), value),
    governance_v2_transitions.policy_mint(anchor(), 1, proposal_policy, CreateV2, value),
  }
}

test advancing_nonce_without_proposal_mint_rejects() fail {
  let value = create_tx()
  expect governance_v2_transitions.create(anchor(), Transaction { ..value, mint: assets.zero })
  True
}


test advancing_wrong_proposal_nonce_rejects() fail {
  let value = create_tx()
  expect [a, p, change] = value.outputs
  let c = cfg()
  let wrong = AuthorityDatumV2 { config: GovernanceConfigV2 { ..c, next_proposal_nonce: 2 } }
  expect governance_v2_transitions.create(anchor(), Transaction { ..value,
    outputs: [Output { ..a, datum: InlineDatum(wrong) }, p, change],
  })
  True
}


test version1_request_rejects() fail {
  expect governance_v2_transitions.request_action(GovernanceRequestV2 { version: 1, action: CreateV2 }) == CreateV2
  True
}


test vote_with_real_custody_and_one_receipt() {
  let action = VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }
  and {
    governance_v2_transitions.governor_spend(anchor(), initial(), action, ref(1), vote_tx(False)),
    governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, action, vote_tx(False)),
  }
}

test second_vote_preserves_prior_record_and_actual_custody() {
  governance_v2_transitions.vote(anchor(), vote_tx(True), bob, True, 900)
}

test replacement_of_prior_voter_rejects() fail {
  let value = vote_tx(True)
  expect [state, change] = value.outputs
  let c = cfg()
  let p = two()
  expect [prior, added] = p.locks
  let changed = VoteLockV2 { ..prior, voter_vkh: member5 }
  let changed = VoteLockV2 { ..changed, receipt_name: governance_v2.receipt_name(c, p.proposal_asset, changed, 0) }
  let poisoned = ProposalDatumV2 { ..p, locks: [changed, added] }
  expect governance_v2_transitions.vote(anchor(), Transaction { ..value,
    outputs: [Output { ..state, value: pvalue(poisoned), datum: InlineDatum(poisoned) }, change],
  }, bob, True, 900)
  True
}


test fictitious_stake_rejects() fail {
  let value = vote_tx(False)
  expect [state, funds] = value.inputs
  let unfunded = Input { ..funds, output: Output { ..funds.output, value: assets.from_lovelace(5_000_000) } }
  expect governance_v2_transitions.vote(anchor(), Transaction { ..value, inputs: [state, unfunded] }, alice, True, 100)
  True
}


test duplicate_voter_rejects() fail {
  expect governance_v2_transitions.vote(anchor(), vote_tx(True), alice, True, 900)
  True
}


test forged_authority_reference_rejects() fail {
  let value = vote_tx(False)
  let fake = authority(cfg())
  let fake = Input { ..fake, output: Output { ..fake.output, value: assets.from_lovelace(5_000_000) } }
  expect governance_v2_transitions.vote(anchor(), Transaction { ..value, reference_inputs: [fake] }, alice, True, 100)
  True
}


test duplicated_authority_reference_rejects() fail {
  let value = vote_tx(False)
  expect governance_v2_transitions.vote(anchor(), Transaction { ..value,
    reference_inputs: [authority(cfg()), authority(cfg())],
  }, alice, True, 100)
  True
}


test receipt_policy_substitution_rejects() fail {
  expect governance_v2_transitions.policy_mint(anchor(), 2, proposal_policy,
    VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, vote_tx(False))
  True
}


test missing_vote_receipt_mint_rejects() fail {
  let value = vote_tx(False)
  expect governance_v2_transitions.vote(anchor(), Transaction { ..value, mint: assets.zero }, alice, True, 100)
  True
}


test finalize_passed_preserves_complete_value() {
  let p = passed()
  let value = Transaction { ..tx(2000, 2100),
    inputs: [proposal_input(first(True)), funding(proposer, 1_000_000, 0)],
    reference_inputs: [authority(cfg())], extra_signatories: [proposer],
    outputs: [out(script(governor_hash), pvalue(p), p), pay(key(proposer), assets.from_lovelace(800_000))],
  }
  governance_v2_transitions.governor_spend(anchor(), first(True), FinalizePassedV2, ref(1), value)
}

test premature_finalize_rejects() fail {
  let p = passed()
  let value = Transaction { ..tx(1900, 1999),
    inputs: [proposal_input(first(True)), funding(proposer, 1_000_000, 0)],
    reference_inputs: [authority(cfg())], extra_signatories: [proposer],
    outputs: [out(script(governor_hash), pvalue(p), p), pay(key(proposer), assets.from_lovelace(800_000))],
  }
  expect governance_v2_transitions.finalize_passed(anchor(), value)
  True
}


test eight_voters_preserve_value_and_fit_datum_bound() {
  let before = maximal_proposal()
  let after = ProposalDatumV2 { ..before, state: PassedV2 }
  let value = Transaction { ..tx(2000, 2100),
    inputs: [proposal_input(before), funding(proposer, 1_000_000, 0)],
    reference_inputs: [authority(cfg())], extra_signatories: [proposer],
    outputs: [out(script(governor_hash), pvalue(after), after), pay(key(proposer), assets.from_lovelace(800_000))],
  }
  governance_v2.small_datum(before) && governance_v2_transitions.finalize_passed(anchor(), value)
}

test ninth_voter_rejects() fail {
  let before = maximal_proposal()
  let voter = #"09090909090909090909090909090909090909090909090909090909"
  let lock = VoteLockV2 { voter_vkh: voter, locked_vams: 100, support: True, weight: 10, receipt_name: #"" }
  let lock = VoteLockV2 { ..lock, receipt_name: governance_v2.receipt_name(cfg(), before.proposal_asset, lock, 8) }
  let after = ProposalDatumV2 { ..before, yes_weight: 90, locks: list.concat(before.locks, [lock]) }
  let value = Transaction { ..tx(1000, 1100),
    inputs: [proposal_input(before), funding(voter, 5_000_000, 100)],
    reference_inputs: [authority(cfg())], extra_signatories: [voter],
    outputs: [out(script(governor_hash), pvalue(after), after), pay(key(voter), assets.from_lovelace(3_800_000))],
    mint: assets.from_asset(receipt_policy, lock.receipt_name, 1),
  }
  expect governance_v2_transitions.vote(anchor(), value, voter, True, 100)
  True
}


test rejected_proposal_burns_and_refunds() {
  governance_v2_transitions.terminal_proposal(anchor(), terminal_tx(False), False)
}

test cancelled_proposal_burns_and_refunds() {
  governance_v2_transitions.terminal_proposal(anchor(), terminal_tx(True), True)
}

test wrong_terminal_refund_recipient_rejects() fail {
  let value = terminal_tx(True)
  expect [voter, proposer_out, change] = value.outputs
  expect governance_v2_transitions.terminal_proposal(anchor(), Transaction { ..value,
    outputs: [Output { ..voter, address: key(member5) }, proposer_out, change],
  }, True)
  True
}


test omitted_terminal_refund_rejects() fail {
  let value = terminal_tx(True)
  expect [voter, _, change] = value.outputs
  expect governance_v2_transitions.terminal_proposal(anchor(), Transaction { ..value,
    outputs: [voter, Output { ..change, value: assets.from_lovelace(3_800_000) }],
  }, True)
  True
}


test queue_binds_passed_proposal_payload_epoch_nonce_and_refunds() {
  let value = queue_tx()
  and {
    governance_v2_transitions.authority_spend(bootstrap(), AuthorityDatumV2 { config: cfg() }, QueueV2, ref(0), value),
    governance_v2_transitions.governor_spend(anchor(), passed(), QueueV2, ref(1), value),
    governance_v2_transitions.policy_mint(anchor(), 1, proposal_policy, QueueV2, value),
    governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, QueueV2, value),
    governance_v2_transitions.policy_mint(anchor(), 3, intent_policy, QueueV2, value),
  }
}

test changed_authority_terms_reject_on_nonce_advance() fail {
  let value = queue_tx()
  expect [a, voter, i, change] = value.outputs
  let c = cfg()
  let bad = AuthorityDatumV2 { config: GovernanceConfigV2 { ..c, next_intent_nonce: 1, normal_delay_ms: 86_400_000 } }
  expect governance_v2_transitions.queue(anchor(), Transaction { ..value,
    outputs: [Output { ..a, datum: InlineDatum(bad) }, voter, i, change],
  })
  True
}


test wrong_queue_payload_rejects() fail {
  let value = queue_tx()
  expect [a, voter, i, change] = value.outputs
  let before = intent()
  let bad = IntentDatumV2 { ..before, payload_hash: before.action_hash }
  expect governance_v2_transitions.queue(anchor(), Transaction { ..value,
    outputs: [a, voter, Output { ..i, datum: InlineDatum(bad) }, change],
  })
  True
}


test twenty_four_hour_queue_rejects() fail {
  let value = queue_tx()
  expect [a, voter, i, change] = value.outputs
  let before = intent()
  let bad = IntentDatumV2 { ..before, execute_after: before.queue_time + 86_400_000 }
  expect governance_v2_transitions.queue(anchor(), Transaction { ..value,
    outputs: [a, voter, Output { ..i, datum: InlineDatum(bad) }, change],
  })
  True
}


test missing_queue_receipt_burn_rejects() fail {
  let value = queue_tx()
  expect governance_v2_transitions.queue(anchor(), Transaction { ..value,
    mint: assets.add(value.mint, receipt_policy, governance_v2_vectors.alice_yes_receipt, 1),
  })
  True
}


test valid_three_member_intent_cancel_refunds() {
  let value = intent_tx(True)
  and {
    governance_v2_transitions.timelock_spend(anchor(), intent(), CancelIntentV2, ref(3), value),
    governance_v2_transitions.policy_mint(anchor(), 3, intent_policy, CancelIntentV2, value),
  }
}

test two_members_cannot_cancel_intent() fail {
  let value = intent_tx(True)
  expect governance_v2_transitions.terminal_intent(anchor(), Transaction { ..value, extra_signatories: [alice, proposer] }, True)
  True
}


test duplicate_members_cannot_cancel_intent() fail {
  let value = intent_tx(True)
  expect governance_v2_transitions.terminal_intent(anchor(), Transaction { ..value, extra_signatories: [alice, alice, proposer] }, True)
  True
}


test expired_intent_is_burned_and_refunded_without_member_threshold() {
  let value = intent_tx(False)
  and {
    governance_v2_transitions.timelock_spend(anchor(), intent(), ExpireIntentV2, ref(3), value),
    governance_v2_transitions.policy_mint(anchor(), 3, intent_policy, ExpireIntentV2, value),
  }
}

test premature_intent_expiry_rejects() fail {
  let value = intent_tx(False)
  expect governance_v2_transitions.terminal_intent(anchor(), Transaction { ..value,
    validity_range: half_open(777_602_099, 777_602_100),
  }, False)
  True
}


test execute_intent_remains_disabled() {
  !governance_v2_transitions.timelock_spend(anchor(), intent(), ExecuteIntentV2, ref(3), intent_tx(False))
}

test missing_intent_burn_rejects() fail {
  let value = intent_tx(False)
  expect governance_v2_transitions.terminal_intent(anchor(), Transaction { ..value, mint: assets.zero }, False)
  True
}


test unbounded_validity_rejects() fail {
  let value = vote_tx(False)
  expect governance_v2_transitions.vote(anchor(), Transaction { ..value,
    validity_range: transaction.placeholder.validity_range,
  }, alice, True, 100)
  True
}

// Each mutation is a separate expected-failure case. No earlier abort may mask
// another mutation. These remain prepared source, with zero native executions.
test create_cannot_change_intent_counter() fail {
  let value = create_tx()
  expect [a, p, change] = value.outputs
  let c = cfg()
  let wrong = AuthorityDatumV2 { config: GovernanceConfigV2 { ..c, next_intent_nonce: 1 } }
  expect governance_v2_transitions.create(anchor(), Transaction { ..value,
    outputs: [Output { ..a, datum: InlineDatum(wrong) }, p, change],
  })
  True
}

test queue_cannot_change_proposal_counter() fail {
  let value = queue_tx()
  expect [a, voter, i, change] = value.outputs
  let c = cfg()
  let wrong = AuthorityDatumV2 { config: GovernanceConfigV2 {
    ..c, next_intent_nonce: 1, next_proposal_nonce: 2,
  } }
  expect governance_v2_transitions.queue(anchor(), Transaction { ..value,
    outputs: [Output { ..a, datum: InlineDatum(wrong) }, voter, i, change],
  })
  True
}

test create_duplicate_signer_cannot_supply_threshold() fail {
  let value = create_tx()
  expect governance_v2_transitions.create(anchor(), Transaction { ..value,
    extra_signatories: [alice, alice, proposer],
  })
  True
}

test create_nonmember_cannot_supply_third_signature() fail {
  let value = create_tx()
  let outsider = #"09090909090909090909090909090909090909090909090909090909"
  // The real funding key still signs; only two of these keys are members.
  expect governance_v2_transitions.create(anchor(), Transaction { ..value,
    extra_signatories: [alice, proposer, outsider],
  })
  True
}

test intent_cancel_nonmember_cannot_supply_third_signature() fail {
  let value = intent_tx(True)
  let outsider = #"09090909090909090909090909090909090909090909090909090909"
  expect governance_v2_transitions.terminal_intent(anchor(), Transaction { ..value,
    extra_signatories: [alice, proposer, outsider],
  }, True)
  True
}

test genesis_authority_asset_preimage_substitution_rejects() fail {
  let value = genesis_tx()
  expect [a, change] = value.outputs
  let substituted = assets.from_asset(authority_policy, governance_v2_vectors.proposal_name, 1)
  expect governance_v2_transitions.authority_genesis(bootstrap(), authority_policy,
    Transaction { ..value, mint: substituted,
      outputs: [Output { ..a, value: assets.from_lovelace(5_000_000)
        |> assets.add(authority_policy, governance_v2_vectors.proposal_name, 1) }, change],
    })
  True
}

test vote_receipt_name_substitution_rejects() fail {
  let value = vote_tx(False)
  expect [state, change] = value.outputs
  let substituted = assets.add(state.value, receipt_policy, governance_v2_vectors.alice_yes_receipt, -1)
    |> assets.add(receipt_policy, governance_v2_vectors.alice_no_receipt, 1)
  expect governance_v2_transitions.vote(anchor(), Transaction { ..value,
    mint: assets.from_asset(receipt_policy, governance_v2_vectors.alice_no_receipt, 1),
    outputs: [Output { ..state, value: substituted }, change],
  }, alice, True, 100)
  True
}

test vote_governed_ada_cannot_pay_fee() fail {
  let value = vote_tx(False)
  expect [state, change] = value.outputs
  // Total value still balances: move the fee amount out of the locked reserve.
  expect governance_v2_transitions.vote(anchor(), Transaction { ..value,
    outputs: [Output { ..state, value: assets.add(state.value, #"", #"", -200_000) },
      Output { ..change, value: assets.from_lovelace(4_000_000) }],
  }, alice, True, 100)
  True
}

test queue_locked_vams_cannot_become_funder_change() fail {
  let value = queue_tx()
  expect [a, voter, i, change] = value.outputs
  expect governance_v2_transitions.queue(anchor(), Transaction { ..value,
    outputs: [a, Output { ..voter, value: assets.add(voter.value, vams_policy, #"56414d53", -1) }, i,
      Output { ..change, value: assets.add(change.value, vams_policy, #"56414d53", 1) }],
  })
  True
}

test queue_redirected_voter_refund_rejects() fail {
  let value = queue_tx()
  expect [a, voter, i, change] = value.outputs
  expect governance_v2_transitions.queue(anchor(), Transaction { ..value,
    outputs: [a, Output { ..voter, address: key(member5) }, i, change],
  })
  True
}

test rejected_proposal_redirected_voter_refund_rejects() fail {
  let value = terminal_tx(False)
  expect [voter, proposer_out, change] = value.outputs
  expect governance_v2_transitions.terminal_proposal(anchor(), Transaction { ..value,
    outputs: [Output { ..voter, address: key(member5) }, proposer_out, change],
  }, False)
  True
}

test rejected_proposal_missing_receipt_burn_rejects() fail {
  let value = terminal_tx(False)
  expect governance_v2_transitions.terminal_proposal(anchor(), Transaction { ..value,
    mint: assets.add(value.mint, receipt_policy, governance_v2_vectors.alice_no_receipt, 1),
  }, False)
  True
}

test create_wrong_proposal_destination_rejects() fail {
  let value = create_tx()
  expect [a, p, change] = value.outputs
  expect governance_v2_transitions.create(anchor(), Transaction { ..value,
    outputs: [a, Output { ..p, address: key(member5) }, change],
  })
  True
}

test vote_wrong_continuing_destination_rejects() fail {
  let value = vote_tx(False)
  expect [state, change] = value.outputs
  expect governance_v2_transitions.vote(anchor(), Transaction { ..value,
    outputs: [Output { ..state, address: key(member5) }, change],
  }, alice, True, 100)
  True
}

test queue_wrong_intent_destination_rejects() fail {
  let value = queue_tx()
  expect [a, voter, i, change] = value.outputs
  expect governance_v2_transitions.queue(anchor(), Transaction { ..value,
    outputs: [a, voter, Output { ..i, address: key(member5) }, change],
  })
  True
}

test intent_cancel_redirected_proposer_refund_rejects() fail {
  let value = intent_tx(True)
  expect [refund, change] = value.outputs
  expect governance_v2_transitions.terminal_intent(anchor(), Transaction { ..value,
    outputs: [Output { ..refund, address: key(member5) }, change],
  }, True)
  True
}

test intent_expiry_redirected_proposer_refund_rejects() fail {
  let value = intent_tx(False)
  expect [refund, change] = value.outputs
  expect governance_v2_transitions.terminal_intent(anchor(), Transaction { ..value,
    outputs: [Output { ..refund, address: key(member5) }, change],
  }, False)
  True
}

test vote_at_deadline_rejects() fail {
  let value = vote_tx(False)
  expect governance_v2_transitions.vote(anchor(), Transaction { ..value,
    validity_range: half_open(2000, 2001),
  }, alice, True, 100)
  True
}

test proposal_cancel_at_deadline_rejects() fail {
  let value = terminal_tx(True)
  expect governance_v2_transitions.terminal_proposal(anchor(), Transaction { ..value,
    validity_range: half_open(2000, 2001),
  }, True)
  True
}

test negative_vote_lock_rejects() fail {
  expect governance_v2_transitions.vote(anchor(), vote_tx(False), alice, True, -1)
  True
}

test vote_lock_above_configured_maximum_rejects() fail {
  expect governance_v2_transitions.vote(anchor(), vote_tx(False), alice, True, 1_000_000_001)
  True
}

test forged_input_tally_above_u64_rejects() fail {
  let value = vote_tx(False)
  expect [state, funds] = value.inputs
  let p = initial()
  let wrong = ProposalDatumV2 { ..p, yes_weight: 18_446_744_073_709_551_616 }
  expect governance_v2_transitions.vote(anchor(), Transaction { ..value,
    inputs: [Input { ..state, output: Output { ..state.output, datum: InlineDatum(wrong) } }, funds],
  }, alice, True, 100)
  True
}

test equal_backed_tallies_cannot_finalize_passed() fail {
  let p = first(True)
  let lock = VoteLockV2 { voter_vkh: bob, locked_vams: 100, support: False, weight: 10, receipt_name: #"" }
  let lock = VoteLockV2 { ..lock,
    receipt_name: governance_v2.receipt_name(cfg(), p.proposal_asset, lock, 1),
  }
  let before = ProposalDatumV2 { ..p, no_weight: 10, locks: list.concat(p.locks, [lock]) }
  let after = ProposalDatumV2 { ..before, state: PassedV2 }
  let value = Transaction { ..tx(2000, 2100),
    inputs: [proposal_input(before), funding(proposer, 1_000_000, 0)],
    reference_inputs: [authority(cfg())], extra_signatories: [proposer],
    outputs: [out(script(governor_hash), pvalue(after), after), pay(key(proposer), assets.from_lovelace(800_000))],
  }
  expect governance_v2_transitions.finalize_passed(anchor(), value)
  True
}



//// Reference-width campaign: PREPARED_NOT_RUN. No native acceptance credit.
fn reference_width_vote(reference: OutputReference, is_reference: Bool) -> Transaction {
  let value = vote_tx(False)
  if is_reference {
    expect [authority_input] = value.reference_inputs
    Transaction { ..value, reference_inputs: [Input { ..authority_input, output_reference: reference }] }
  } else {
    expect [proposal, funding_input] = value.inputs
    Transaction { ..value, inputs: [Input { ..proposal, output_reference: reference }, funding_input] }
  }
}

fn reference_width_max_vote() -> Transaction {
  let value = vote_tx(False)
  expect [proposal, funding_input] = value.inputs
  expect [authority_input] = value.reference_inputs
  Transaction { ..value,
    inputs: [Input { ..proposal, output_reference: OutputReference {
      transaction_id: ref(1).transaction_id, output_index: 4_294_967_295,
    } }, funding_input],
    reference_inputs: [Input { ..authority_input, output_reference: OutputReference {
      transaction_id: #"2222222222222222222222222222222222222222222222222222222222222222",
      output_index: 4_294_967_295,
    } }],
  }
}

test width_regular_txid31_transition_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"11111111111111111111111111111111111111111111111111111111111111", output_index: 1 }
  let value = reference_width_vote(bad_reference, False)
  expect governance_v2_transitions.vote(anchor(), value, alice, True, 100)
  True
}

test width_regular_txid31_governor_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"11111111111111111111111111111111111111111111111111111111111111", output_index: 1 }
  let value = reference_width_vote(bad_reference, False)
  expect governance_v2_transitions.governor_spend(anchor(), initial(), VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, bad_reference, value)
  True
}

test width_regular_txid31_receipt_policy_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"11111111111111111111111111111111111111111111111111111111111111", output_index: 1 }
  let value = reference_width_vote(bad_reference, False)
  expect governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, value)
  True
}

test width_regular_txid33_transition_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"111111111111111111111111111111111111111111111111111111111111111111", output_index: 1 }
  let value = reference_width_vote(bad_reference, False)
  expect governance_v2_transitions.vote(anchor(), value, alice, True, 100)
  True
}

test width_regular_txid33_governor_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"111111111111111111111111111111111111111111111111111111111111111111", output_index: 1 }
  let value = reference_width_vote(bad_reference, False)
  expect governance_v2_transitions.governor_spend(anchor(), initial(), VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, bad_reference, value)
  True
}

test width_regular_txid33_receipt_policy_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"111111111111111111111111111111111111111111111111111111111111111111", output_index: 1 }
  let value = reference_width_vote(bad_reference, False)
  expect governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, value)
  True
}

test width_regular_index_negative_transition_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"1111111111111111111111111111111111111111111111111111111111111111", output_index: -1 }
  let value = reference_width_vote(bad_reference, False)
  expect governance_v2_transitions.vote(anchor(), value, alice, True, 100)
  True
}

test width_regular_index_negative_governor_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"1111111111111111111111111111111111111111111111111111111111111111", output_index: -1 }
  let value = reference_width_vote(bad_reference, False)
  expect governance_v2_transitions.governor_spend(anchor(), initial(), VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, bad_reference, value)
  True
}

test width_regular_index_negative_receipt_policy_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"1111111111111111111111111111111111111111111111111111111111111111", output_index: -1 }
  let value = reference_width_vote(bad_reference, False)
  expect governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, value)
  True
}

test width_regular_index_overflow_transition_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"1111111111111111111111111111111111111111111111111111111111111111", output_index: 4294967296 }
  let value = reference_width_vote(bad_reference, False)
  expect governance_v2_transitions.vote(anchor(), value, alice, True, 100)
  True
}

test width_regular_index_overflow_governor_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"1111111111111111111111111111111111111111111111111111111111111111", output_index: 4294967296 }
  let value = reference_width_vote(bad_reference, False)
  expect governance_v2_transitions.governor_spend(anchor(), initial(), VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, bad_reference, value)
  True
}

test width_regular_index_overflow_receipt_policy_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"1111111111111111111111111111111111111111111111111111111111111111", output_index: 4294967296 }
  let value = reference_width_vote(bad_reference, False)
  expect governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, value)
  True
}

test width_reference_txid31_transition_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"11111111111111111111111111111111111111111111111111111111111111", output_index: 1 }
  let value = reference_width_vote(bad_reference, True)
  expect governance_v2_transitions.vote(anchor(), value, alice, True, 100)
  True
}

test width_reference_txid31_governor_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"11111111111111111111111111111111111111111111111111111111111111", output_index: 1 }
  let value = reference_width_vote(bad_reference, True)
  expect governance_v2_transitions.governor_spend(anchor(), initial(), VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, ref(1), value)
  True
}

test width_reference_txid31_receipt_policy_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"11111111111111111111111111111111111111111111111111111111111111", output_index: 1 }
  let value = reference_width_vote(bad_reference, True)
  expect governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, value)
  True
}

test width_reference_txid33_transition_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"111111111111111111111111111111111111111111111111111111111111111111", output_index: 1 }
  let value = reference_width_vote(bad_reference, True)
  expect governance_v2_transitions.vote(anchor(), value, alice, True, 100)
  True
}

test width_reference_txid33_governor_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"111111111111111111111111111111111111111111111111111111111111111111", output_index: 1 }
  let value = reference_width_vote(bad_reference, True)
  expect governance_v2_transitions.governor_spend(anchor(), initial(), VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, ref(1), value)
  True
}

test width_reference_txid33_receipt_policy_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"111111111111111111111111111111111111111111111111111111111111111111", output_index: 1 }
  let value = reference_width_vote(bad_reference, True)
  expect governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, value)
  True
}

test width_reference_index_negative_transition_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"1111111111111111111111111111111111111111111111111111111111111111", output_index: -1 }
  let value = reference_width_vote(bad_reference, True)
  expect governance_v2_transitions.vote(anchor(), value, alice, True, 100)
  True
}

test width_reference_index_negative_governor_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"1111111111111111111111111111111111111111111111111111111111111111", output_index: -1 }
  let value = reference_width_vote(bad_reference, True)
  expect governance_v2_transitions.governor_spend(anchor(), initial(), VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, ref(1), value)
  True
}

test width_reference_index_negative_receipt_policy_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"1111111111111111111111111111111111111111111111111111111111111111", output_index: -1 }
  let value = reference_width_vote(bad_reference, True)
  expect governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, value)
  True
}

test width_reference_index_overflow_transition_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"1111111111111111111111111111111111111111111111111111111111111111", output_index: 4294967296 }
  let value = reference_width_vote(bad_reference, True)
  expect governance_v2_transitions.vote(anchor(), value, alice, True, 100)
  True
}

test width_reference_index_overflow_governor_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"1111111111111111111111111111111111111111111111111111111111111111", output_index: 4294967296 }
  let value = reference_width_vote(bad_reference, True)
  expect governance_v2_transitions.governor_spend(anchor(), initial(), VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, ref(1), value)
  True
}

test width_reference_index_overflow_receipt_policy_rejects() fail {
  let bad_reference = OutputReference { transaction_id: #"1111111111111111111111111111111111111111111111111111111111111111", output_index: 4294967296 }
  let value = reference_width_vote(bad_reference, True)
  expect governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, value)
  True
}

test width_u32max_unique_references_transition_accepts() {
  let value = reference_width_max_vote()
  governance_v2_transitions.vote(anchor(), value, alice, True, 100)
}

test width_u32max_unique_references_governor_accepts() {
  let value = reference_width_max_vote()
  governance_v2_transitions.governor_spend(anchor(), initial(), VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, OutputReference { transaction_id: ref(1).transaction_id, output_index: 4_294_967_295 }, value)
}

test width_u32max_unique_references_receipt_policy_accepts() {
  let value = reference_width_max_vote()
  governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, value)
}


//// Timing amendment: PREPARED_NOT_RUN, no Aiken/ledger/budget credit.
fn queue_with_intent(value: Transaction, i: IntentDatumV2) -> Transaction {
  expect [a, voter, output, change] = value.outputs
  let name = governance_v2.intent_name(cfg(), i)
  Transaction { ..value,
    outputs: [a, voter, Output { ..output,
      value: assets.from_lovelace(3_000_000) |> assets.add(intent_policy, name, 1),
      datum: InlineDatum(i) }, change],
    mint: assets.from_asset(proposal_policy, governance_v2_vectors.proposal_name, -1)
      |> assets.add(receipt_policy, governance_v2_vectors.alice_yes_receipt, -1)
      |> assets.add(intent_policy, name, 1),
  }
}

fn queue_window(lower: Int, upper: Int) -> Transaction {
  let value = queue_tx()
  let current = intent()
  queue_with_intent(Transaction { ..value, validity_range: half_open(lower, upper) },
    IntentDatumV2 { ..current, queue_time: upper, execute_after: upper + 172_800_000 })
}

test upper_anchor_identifier_matches_reference_bytes() {
  governance_v2.intent_name(cfg(), intent()) == governance_v2_vectors.queued_alice_intent_upper
}

test timing_upper_anchor_transition_accepts() {
  let value = queue_tx()
  governance_v2_transitions.queue(anchor(), value)
}

test timing_backdated_lower_anchor_transition_rejects() fail {
  let value = queue_with_intent(queue_tx(), historical_intent_fixture())
  expect governance_v2_transitions.queue(anchor(), value)
  True
}

test timing_queue_overflow_transition_rejects() fail {
  let upper = governance_v2.u64_max - 172_800_000 - 604_800_000 + 1
  let value = queue_window(upper - 100, upper)
  expect governance_v2_transitions.queue(anchor(), value)
  True
}

test timing_upper_anchor_authority_accepts() {
  let value = queue_tx()
  governance_v2_transitions.authority_spend(bootstrap(), AuthorityDatumV2 { config: cfg() }, QueueV2, ref(0), value)
}

test timing_backdated_lower_anchor_authority_rejects() fail {
  let value = queue_with_intent(queue_tx(), historical_intent_fixture())
  expect governance_v2_transitions.authority_spend(bootstrap(), AuthorityDatumV2 { config: cfg() }, QueueV2, ref(0), value)
  True
}

test timing_queue_overflow_authority_rejects() fail {
  let upper = governance_v2.u64_max - 172_800_000 - 604_800_000 + 1
  let value = queue_window(upper - 100, upper)
  expect governance_v2_transitions.authority_spend(bootstrap(), AuthorityDatumV2 { config: cfg() }, QueueV2, ref(0), value)
  True
}

test timing_upper_anchor_governor_accepts() {
  let value = queue_tx()
  governance_v2_transitions.governor_spend(anchor(), passed(), QueueV2, ref(1), value)
}

test timing_backdated_lower_anchor_governor_rejects() fail {
  let value = queue_with_intent(queue_tx(), historical_intent_fixture())
  expect governance_v2_transitions.governor_spend(anchor(), passed(), QueueV2, ref(1), value)
  True
}

test timing_queue_overflow_governor_rejects() fail {
  let upper = governance_v2.u64_max - 172_800_000 - 604_800_000 + 1
  let value = queue_window(upper - 100, upper)
  expect governance_v2_transitions.governor_spend(anchor(), passed(), QueueV2, ref(1), value)
  True
}

test timing_upper_anchor_proposal_policy_accepts() {
  let value = queue_tx()
  governance_v2_transitions.policy_mint(anchor(), 1, proposal_policy, QueueV2, value)
}

test timing_backdated_lower_anchor_proposal_policy_rejects() fail {
  let value = queue_with_intent(queue_tx(), historical_intent_fixture())
  expect governance_v2_transitions.policy_mint(anchor(), 1, proposal_policy, QueueV2, value)
  True
}

test timing_queue_overflow_proposal_policy_rejects() fail {
  let upper = governance_v2.u64_max - 172_800_000 - 604_800_000 + 1
  let value = queue_window(upper - 100, upper)
  expect governance_v2_transitions.policy_mint(anchor(), 1, proposal_policy, QueueV2, value)
  True
}

test timing_upper_anchor_receipt_policy_accepts() {
  let value = queue_tx()
  governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, QueueV2, value)
}

test timing_backdated_lower_anchor_receipt_policy_rejects() fail {
  let value = queue_with_intent(queue_tx(), historical_intent_fixture())
  expect governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, QueueV2, value)
  True
}

test timing_queue_overflow_receipt_policy_rejects() fail {
  let upper = governance_v2.u64_max - 172_800_000 - 604_800_000 + 1
  let value = queue_window(upper - 100, upper)
  expect governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, QueueV2, value)
  True
}

test timing_upper_anchor_intent_policy_accepts() {
  let value = queue_tx()
  governance_v2_transitions.policy_mint(anchor(), 3, intent_policy, QueueV2, value)
}

test timing_backdated_lower_anchor_intent_policy_rejects() fail {
  let value = queue_with_intent(queue_tx(), historical_intent_fixture())
  expect governance_v2_transitions.policy_mint(anchor(), 3, intent_policy, QueueV2, value)
  True
}

test timing_queue_overflow_intent_policy_rejects() fail {
  let upper = governance_v2.u64_max - 172_800_000 - 604_800_000 + 1
  let value = queue_window(upper - 100, upper)
  expect governance_v2_transitions.policy_mint(anchor(), 3, intent_policy, QueueV2, value)
  True
}

test timing_closed_vote_transition_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: interval.between(1000, 1100) }
  expect governance_v2_transitions.vote(anchor(), value, alice, True, 100)
  True
}

test timing_closed_vote_governor_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: interval.between(1000, 1100) }
  expect governance_v2_transitions.governor_spend(anchor(), initial(), VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, ref(1), value)
  True
}

test timing_closed_vote_receipt_policy_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: interval.between(1000, 1100) }
  expect governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, value)
  True
}

test timing_open_lower_vote_transition_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: interval.entirely_between(1000, 1100) }
  expect governance_v2_transitions.vote(anchor(), value, alice, True, 100)
  True
}

test timing_open_lower_vote_governor_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: interval.entirely_between(1000, 1100) }
  expect governance_v2_transitions.governor_spend(anchor(), initial(), VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, ref(1), value)
  True
}

test timing_open_lower_vote_receipt_policy_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: interval.entirely_between(1000, 1100) }
  expect governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, value)
  True
}

test timing_empty_vote_transition_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(1000, 1000) }
  expect governance_v2_transitions.vote(anchor(), value, alice, True, 100)
  True
}

test timing_empty_vote_governor_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(1000, 1000) }
  expect governance_v2_transitions.governor_spend(anchor(), initial(), VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, ref(1), value)
  True
}

test timing_empty_vote_receipt_policy_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(1000, 1000) }
  expect governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, value)
  True
}

test timing_inverted_vote_transition_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(1100, 1000) }
  expect governance_v2_transitions.vote(anchor(), value, alice, True, 100)
  True
}

test timing_inverted_vote_governor_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(1100, 1000) }
  expect governance_v2_transitions.governor_spend(anchor(), initial(), VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, ref(1), value)
  True
}

test timing_inverted_vote_receipt_policy_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(1100, 1000) }
  expect governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, value)
  True
}

test timing_too_wide_vote_transition_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(0, 300_001) }
  expect governance_v2_transitions.vote(anchor(), value, alice, True, 100)
  True
}

test timing_too_wide_vote_governor_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(0, 300_001) }
  expect governance_v2_transitions.governor_spend(anchor(), initial(), VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, ref(1), value)
  True
}

test timing_too_wide_vote_receipt_policy_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(0, 300_001) }
  expect governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, value)
  True
}

test timing_negative_vote_transition_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(-1, 1000) }
  expect governance_v2_transitions.vote(anchor(), value, alice, True, 100)
  True
}

test timing_negative_vote_governor_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(-1, 1000) }
  expect governance_v2_transitions.governor_spend(anchor(), initial(), VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, ref(1), value)
  True
}

test timing_negative_vote_receipt_policy_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(-1, 1000) }
  expect governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, value)
  True
}

test timing_upper_overflow_vote_transition_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(governance_v2.u64_max - 100, governance_v2.u64_max + 1) }
  expect governance_v2_transitions.vote(anchor(), value, alice, True, 100)
  True
}

test timing_upper_overflow_vote_governor_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(governance_v2.u64_max - 100, governance_v2.u64_max + 1) }
  expect governance_v2_transitions.governor_spend(anchor(), initial(), VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, ref(1), value)
  True
}

test timing_upper_overflow_vote_receipt_policy_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(governance_v2.u64_max - 100, governance_v2.u64_max + 1) }
  expect governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, value)
  True
}

test timing_deadline_straddle_vote_transition_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(1999, 2001) }
  expect governance_v2_transitions.vote(anchor(), value, alice, True, 100)
  True
}

test timing_deadline_straddle_vote_governor_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(1999, 2001) }
  expect governance_v2_transitions.governor_spend(anchor(), initial(), VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, ref(1), value)
  True
}

test timing_deadline_straddle_vote_receipt_policy_rejects() fail {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(1999, 2001) }
  expect governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, value)
  True
}

test timing_vote_until_exclusive_deadline_transition_accepts() {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(1999, 2000) }
  governance_v2_transitions.vote(anchor(), value, alice, True, 100)
}

test timing_vote_until_exclusive_deadline_governor_accepts() {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(1999, 2000) }
  governance_v2_transitions.governor_spend(anchor(), initial(), VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, ref(1), value)
}

test timing_vote_until_exclusive_deadline_receipt_policy_accepts() {
  let base = vote_tx(False)
  let value = Transaction { ..base, validity_range: half_open(1999, 2000) }
  governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }, value)
}

test timing_queue_one_ms_accepts() {
  let value = queue_window(2000, 2001)
  governance_v2_transitions.queue(anchor(), value)
}

test timing_queue_max_width_accepts() {
  let value = queue_window(2000, 302000)
  governance_v2_transitions.queue(anchor(), value)
}

test timing_queue_last_safe_u64_accepts() {
  let value = queue_window(governance_v2.u64_max - 172_800_000 - 604_800_000 - 100, governance_v2.u64_max - 172_800_000 - 604_800_000)
  governance_v2_transitions.queue(anchor(), value)
}

test timing_expiry_straddle_timelock_rejects() fail {
  let base = intent_tx(False)
  let value = Transaction { ..base, validity_range: half_open(777_602_099, 777_602_101) }
  expect governance_v2_transitions.timelock_spend(anchor(), intent(), ExpireIntentV2, ref(3), value)
  True
}

test timing_expiry_exact_lower_timelock_accepts() {
  let value = intent_tx(False)
  governance_v2_transitions.timelock_spend(anchor(), intent(), ExpireIntentV2, ref(3), value)
}

test timing_expiry_straddle_intent_policy_rejects() fail {
  let base = intent_tx(False)
  let value = Transaction { ..base, validity_range: half_open(777_602_099, 777_602_101) }
  expect governance_v2_transitions.policy_mint(anchor(), 3, intent_policy, ExpireIntentV2, value)
  True
}

test timing_expiry_exact_lower_intent_policy_accepts() {
  let value = intent_tx(False)
  governance_v2_transitions.policy_mint(anchor(), 3, intent_policy, ExpireIntentV2, value)
}


//// Asset boundary refinement25: proposed definitions; native/ledger/budget NOT_RUN.
//// The original141tests above are retained byte-for-byte. Shared-call functions
//// are not applied UPLC wrapper, signature or ledger qualification.
fn asset_boundary_rebase(p: ProposalDatumV2, name: ByteArray) -> ProposalDatumV2 {
  let locks = list.indexed_map(p.locks, fn(index, lock) {
    VoteLockV2 { ..lock, receipt_name: governance_v2.receipt_name(cfg(), name, lock, index) }
  })
  ProposalDatumV2 { ..p, proposal_asset: name, locks }
}

fn asset_boundary_vote(name: ByteArray) -> Transaction {
  let value = vote_tx(False)
  let before = asset_boundary_rebase(initial(), name)
  let after = asset_boundary_rebase(first(True), name)
  expect [lock] = after.locks
  expect [_, change] = value.outputs
  Transaction { ..value,
    inputs: [proposal_input(before), funding(alice, 5_000_000, 100)],
    outputs: [out(script(governor_hash), pvalue(after), after), change],
    mint: assets.from_asset(receipt_policy, lock.receipt_name, 1),
  }
}

fn asset_boundary_queue(name: ByteArray) -> Transaction {
  let value = queue_tx()
  let p = asset_boundary_rebase(passed(), name)
  expect [lock] = p.locks
  let queued = IntentDatumV2 { ..intent(), proposal_asset: name,
    proposal_id: governance_v2.proposal_commitment(p) }
  let queued_name = governance_v2.intent_name(cfg(), queued)
  expect [a, refund, _, change] = value.outputs
  Transaction { ..value,
    inputs: [authority(cfg()), proposal_input(p), funding(proposer, 1_000_000, 0)],
    outputs: [a, refund, out(script(timelock_hash), assets.from_lovelace(3_000_000)
      |> assets.add(intent_policy, queued_name, 1), queued), change],
    mint: assets.from_asset(proposal_policy, name, -1)
      |> assets.add(receipt_policy, lock.receipt_name, -1)
      |> assets.add(intent_policy, queued_name, 1),
  }
}

fn asset_boundary_intent(name: ByteArray) -> Transaction {
  let value = queue_tx()
  expect [a, refund, queued, change] = value.outputs
  Transaction { ..value,
    outputs: [a, refund, Output { ..queued, value: assets.from_lovelace(3_000_000)
      |> assets.add(intent_policy, name, 1) }, change],
    mint: assets.from_asset(proposal_policy, governance_v2_vectors.proposal_name, -1)
      |> assets.add(receipt_policy, governance_v2_vectors.alice_yes_receipt, -1)
      |> assets.add(intent_policy, name, 1),
  }
}

fn asset_boundary_conserves(value: Transaction) -> Bool {
  let incoming = list.foldl(value.inputs, assets.zero,
    fn(input, total) { assets.merge(total, input.output.value) })
  let outgoing = list.foldl(value.outputs, assets.from_lovelace(value.fee),
    fn(output, total) { assets.merge(total, output.value) })
  assets.merge(incoming, value.mint) == outgoing
}

fn asset_boundary_queue_call(value: Transaction, caller: Int) -> Bool {
  when caller is {
    0 -> governance_v2_transitions.queue(anchor(), value)
    1 -> governance_v2_transitions.authority_spend(bootstrap(), AuthorityDatumV2 { config: cfg() }, QueueV2, ref(0), value)
    2 -> governance_v2_transitions.governor_spend(anchor(), passed(), QueueV2, ref(1), value)
    3 -> governance_v2_transitions.policy_mint(anchor(), 1, proposal_policy, QueueV2, value)
    4 -> governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, QueueV2, value)
    5 -> governance_v2_transitions.policy_mint(anchor(), 3, intent_policy, QueueV2, value)
    _ -> False
  }
}

fn asset_boundary_vote_call(value: Transaction, caller: Int) -> Bool {
  let action = VoteV2 { voter_vkh: alice, support: True, locked_vams: 100 }
  when caller is {
    0 -> governance_v2_transitions.vote(anchor(), value, alice, True, 100)
    1 -> governance_v2_transitions.governor_spend(anchor(), initial(), action, ref(1), value)
    2 -> governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, action, value)
    _ -> False
  }
}

test asset_boundary_queue_transition_baseline_accepts() { asset_boundary_queue_call(queue_tx(), 0) }

test asset_boundary_queue_authority_spend_baseline_accepts() { asset_boundary_queue_call(queue_tx(), 1) }

test asset_boundary_queue_governor_spend_baseline_accepts() { asset_boundary_queue_call(queue_tx(), 2) }

test asset_boundary_queue_proposal_policy_baseline_accepts() { asset_boundary_queue_call(queue_tx(), 3) }

test asset_boundary_queue_receipt_policy_baseline_accepts() { asset_boundary_queue_call(queue_tx(), 4) }

test asset_boundary_queue_intent_policy_baseline_accepts() { asset_boundary_queue_call(queue_tx(), 5) }

test asset_boundary_vote_transition_baseline_accepts() { asset_boundary_vote_call(vote_tx(False), 0) }

test asset_boundary_vote_governor_spend_baseline_accepts() { asset_boundary_vote_call(vote_tx(False), 1) }

test asset_boundary_vote_receipt_policy_baseline_accepts() { asset_boundary_vote_call(vote_tx(False), 2) }

test asset_boundary_00_fixture_conserves() {
  let value = asset_boundary_intent(#"58f33eddb53a0ce46181c7f45d3eff749e5e3a0ad63f97ec1800be6342274eae")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_00_queue_transition_rejects() fail {
  let value = asset_boundary_intent(#"58f33eddb53a0ce46181c7f45d3eff749e5e3a0ad63f97ec1800be6342274eae")
  expect asset_boundary_queue_call(value, 0)
  True
}

test asset_boundary_00_queue_authority_spend_rejects() fail {
  let value = asset_boundary_intent(#"58f33eddb53a0ce46181c7f45d3eff749e5e3a0ad63f97ec1800be6342274eae")
  expect asset_boundary_queue_call(value, 1)
  True
}

test asset_boundary_00_queue_governor_spend_rejects() fail {
  let value = asset_boundary_intent(#"58f33eddb53a0ce46181c7f45d3eff749e5e3a0ad63f97ec1800be6342274eae")
  expect asset_boundary_queue_call(value, 2)
  True
}

test asset_boundary_00_queue_proposal_policy_rejects() fail {
  let value = asset_boundary_intent(#"58f33eddb53a0ce46181c7f45d3eff749e5e3a0ad63f97ec1800be6342274eae")
  expect asset_boundary_queue_call(value, 3)
  True
}

test asset_boundary_00_queue_receipt_policy_rejects() fail {
  let value = asset_boundary_intent(#"58f33eddb53a0ce46181c7f45d3eff749e5e3a0ad63f97ec1800be6342274eae")
  expect asset_boundary_queue_call(value, 4)
  True
}

test asset_boundary_00_queue_intent_policy_rejects() fail {
  let value = asset_boundary_intent(#"58f33eddb53a0ce46181c7f45d3eff749e5e3a0ad63f97ec1800be6342274eae")
  expect asset_boundary_queue_call(value, 5)
  True
}

test asset_boundary_01_fixture_conserves() {
  let value = asset_boundary_vote(#"8582bcb60082b5ce50f8fff412dfef8f9e4132803a59ea4b49ca36cc9c187bab")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_01_vote_transition_rejects() fail {
  let value = asset_boundary_vote(#"8582bcb60082b5ce50f8fff412dfef8f9e4132803a59ea4b49ca36cc9c187bab")
  expect asset_boundary_vote_call(value, 0)
  True
}

test asset_boundary_01_vote_governor_spend_rejects() fail {
  let value = asset_boundary_vote(#"8582bcb60082b5ce50f8fff412dfef8f9e4132803a59ea4b49ca36cc9c187bab")
  expect asset_boundary_vote_call(value, 1)
  True
}

test asset_boundary_01_vote_receipt_policy_rejects() fail {
  let value = asset_boundary_vote(#"8582bcb60082b5ce50f8fff412dfef8f9e4132803a59ea4b49ca36cc9c187bab")
  expect asset_boundary_vote_call(value, 2)
  True
}

test asset_boundary_02_fixture_conserves() {
  let value = asset_boundary_queue(#"db47eb94d156f77104df7d027bda4d9013ebec87999dcffb9ef7da7404c981a2")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_02_queue_transition_rejects() fail {
  let value = asset_boundary_queue(#"db47eb94d156f77104df7d027bda4d9013ebec87999dcffb9ef7da7404c981a2")
  expect asset_boundary_queue_call(value, 0)
  True
}

test asset_boundary_02_queue_authority_spend_rejects() fail {
  let value = asset_boundary_queue(#"db47eb94d156f77104df7d027bda4d9013ebec87999dcffb9ef7da7404c981a2")
  expect asset_boundary_queue_call(value, 1)
  True
}

test asset_boundary_02_queue_governor_spend_rejects() fail {
  let value = asset_boundary_queue(#"db47eb94d156f77104df7d027bda4d9013ebec87999dcffb9ef7da7404c981a2")
  expect asset_boundary_queue_call(value, 2)
  True
}

test asset_boundary_02_queue_proposal_policy_rejects() fail {
  let value = asset_boundary_queue(#"db47eb94d156f77104df7d027bda4d9013ebec87999dcffb9ef7da7404c981a2")
  expect asset_boundary_queue_call(value, 3)
  True
}

test asset_boundary_02_queue_receipt_policy_rejects() fail {
  let value = asset_boundary_queue(#"db47eb94d156f77104df7d027bda4d9013ebec87999dcffb9ef7da7404c981a2")
  expect asset_boundary_queue_call(value, 4)
  True
}

test asset_boundary_02_queue_intent_policy_rejects() fail {
  let value = asset_boundary_queue(#"db47eb94d156f77104df7d027bda4d9013ebec87999dcffb9ef7da7404c981a2")
  expect asset_boundary_queue_call(value, 5)
  True
}

test asset_boundary_03_fixture_conserves() {
  let value = asset_boundary_vote(#"f47d8a1f74780fee0101ef4fd3b368d61fb4ccc9805144ebece4c5f524174267")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_03_vote_transition_rejects() fail {
  let value = asset_boundary_vote(#"f47d8a1f74780fee0101ef4fd3b368d61fb4ccc9805144ebece4c5f524174267")
  expect asset_boundary_vote_call(value, 0)
  True
}

test asset_boundary_03_vote_governor_spend_rejects() fail {
  let value = asset_boundary_vote(#"f47d8a1f74780fee0101ef4fd3b368d61fb4ccc9805144ebece4c5f524174267")
  expect asset_boundary_vote_call(value, 1)
  True
}

test asset_boundary_03_vote_receipt_policy_rejects() fail {
  let value = asset_boundary_vote(#"f47d8a1f74780fee0101ef4fd3b368d61fb4ccc9805144ebece4c5f524174267")
  expect asset_boundary_vote_call(value, 2)
  True
}

test asset_boundary_04_fixture_conserves() {
  let value = asset_boundary_queue(#"521b1e2c1110ab17e077168870ed9dba211cfb914aac1a1ab03ede5b4cd7cf25")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_04_queue_transition_rejects() fail {
  let value = asset_boundary_queue(#"521b1e2c1110ab17e077168870ed9dba211cfb914aac1a1ab03ede5b4cd7cf25")
  expect asset_boundary_queue_call(value, 0)
  True
}

test asset_boundary_04_queue_authority_spend_rejects() fail {
  let value = asset_boundary_queue(#"521b1e2c1110ab17e077168870ed9dba211cfb914aac1a1ab03ede5b4cd7cf25")
  expect asset_boundary_queue_call(value, 1)
  True
}

test asset_boundary_04_queue_governor_spend_rejects() fail {
  let value = asset_boundary_queue(#"521b1e2c1110ab17e077168870ed9dba211cfb914aac1a1ab03ede5b4cd7cf25")
  expect asset_boundary_queue_call(value, 2)
  True
}

test asset_boundary_04_queue_proposal_policy_rejects() fail {
  let value = asset_boundary_queue(#"521b1e2c1110ab17e077168870ed9dba211cfb914aac1a1ab03ede5b4cd7cf25")
  expect asset_boundary_queue_call(value, 3)
  True
}

test asset_boundary_04_queue_receipt_policy_rejects() fail {
  let value = asset_boundary_queue(#"521b1e2c1110ab17e077168870ed9dba211cfb914aac1a1ab03ede5b4cd7cf25")
  expect asset_boundary_queue_call(value, 4)
  True
}

test asset_boundary_04_queue_intent_policy_rejects() fail {
  let value = asset_boundary_queue(#"521b1e2c1110ab17e077168870ed9dba211cfb914aac1a1ab03ede5b4cd7cf25")
  expect asset_boundary_queue_call(value, 5)
  True
}

test asset_boundary_05_fixture_conserves() {
  let value = asset_boundary_vote(#"ddd8c6a3b68f92cf45ce5bc478c38e97ee513aa5ae46ae82aeb5a7c6a603642b")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_05_vote_transition_rejects() fail {
  let value = asset_boundary_vote(#"ddd8c6a3b68f92cf45ce5bc478c38e97ee513aa5ae46ae82aeb5a7c6a603642b")
  expect asset_boundary_vote_call(value, 0)
  True
}

test asset_boundary_05_vote_governor_spend_rejects() fail {
  let value = asset_boundary_vote(#"ddd8c6a3b68f92cf45ce5bc478c38e97ee513aa5ae46ae82aeb5a7c6a603642b")
  expect asset_boundary_vote_call(value, 1)
  True
}

test asset_boundary_05_vote_receipt_policy_rejects() fail {
  let value = asset_boundary_vote(#"ddd8c6a3b68f92cf45ce5bc478c38e97ee513aa5ae46ae82aeb5a7c6a603642b")
  expect asset_boundary_vote_call(value, 2)
  True
}

test asset_boundary_06_fixture_conserves() {
  let value = asset_boundary_queue(#"37bd9541ae9a1a95d1dafdd74278a4abbe6375ad516c4e8e551aa8cae3d37358")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_06_queue_transition_rejects() fail {
  let value = asset_boundary_queue(#"37bd9541ae9a1a95d1dafdd74278a4abbe6375ad516c4e8e551aa8cae3d37358")
  expect asset_boundary_queue_call(value, 0)
  True
}

test asset_boundary_06_queue_authority_spend_rejects() fail {
  let value = asset_boundary_queue(#"37bd9541ae9a1a95d1dafdd74278a4abbe6375ad516c4e8e551aa8cae3d37358")
  expect asset_boundary_queue_call(value, 1)
  True
}

test asset_boundary_06_queue_governor_spend_rejects() fail {
  let value = asset_boundary_queue(#"37bd9541ae9a1a95d1dafdd74278a4abbe6375ad516c4e8e551aa8cae3d37358")
  expect asset_boundary_queue_call(value, 2)
  True
}

test asset_boundary_06_queue_proposal_policy_rejects() fail {
  let value = asset_boundary_queue(#"37bd9541ae9a1a95d1dafdd74278a4abbe6375ad516c4e8e551aa8cae3d37358")
  expect asset_boundary_queue_call(value, 3)
  True
}

test asset_boundary_06_queue_receipt_policy_rejects() fail {
  let value = asset_boundary_queue(#"37bd9541ae9a1a95d1dafdd74278a4abbe6375ad516c4e8e551aa8cae3d37358")
  expect asset_boundary_queue_call(value, 4)
  True
}

test asset_boundary_06_queue_intent_policy_rejects() fail {
  let value = asset_boundary_queue(#"37bd9541ae9a1a95d1dafdd74278a4abbe6375ad516c4e8e551aa8cae3d37358")
  expect asset_boundary_queue_call(value, 5)
  True
}

test asset_boundary_07_fixture_conserves() {
  let value = asset_boundary_vote(#"50fdc5e989db73f2c06790c91cb9734ce3bdf01494e2b6ced63521f4a6efce80")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_07_vote_transition_rejects() fail {
  let value = asset_boundary_vote(#"50fdc5e989db73f2c06790c91cb9734ce3bdf01494e2b6ced63521f4a6efce80")
  expect asset_boundary_vote_call(value, 0)
  True
}

test asset_boundary_07_vote_governor_spend_rejects() fail {
  let value = asset_boundary_vote(#"50fdc5e989db73f2c06790c91cb9734ce3bdf01494e2b6ced63521f4a6efce80")
  expect asset_boundary_vote_call(value, 1)
  True
}

test asset_boundary_07_vote_receipt_policy_rejects() fail {
  let value = asset_boundary_vote(#"50fdc5e989db73f2c06790c91cb9734ce3bdf01494e2b6ced63521f4a6efce80")
  expect asset_boundary_vote_call(value, 2)
  True
}

test asset_boundary_08_fixture_conserves() {
  let value = asset_boundary_queue(#"d9004a4bb8afcec950bb0c76ab3817f32b38d4aef71013dae38082ea6824c684")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_08_queue_transition_rejects() fail {
  let value = asset_boundary_queue(#"d9004a4bb8afcec950bb0c76ab3817f32b38d4aef71013dae38082ea6824c684")
  expect asset_boundary_queue_call(value, 0)
  True
}

test asset_boundary_08_queue_authority_spend_rejects() fail {
  let value = asset_boundary_queue(#"d9004a4bb8afcec950bb0c76ab3817f32b38d4aef71013dae38082ea6824c684")
  expect asset_boundary_queue_call(value, 1)
  True
}

test asset_boundary_08_queue_governor_spend_rejects() fail {
  let value = asset_boundary_queue(#"d9004a4bb8afcec950bb0c76ab3817f32b38d4aef71013dae38082ea6824c684")
  expect asset_boundary_queue_call(value, 2)
  True
}

test asset_boundary_08_queue_proposal_policy_rejects() fail {
  let value = asset_boundary_queue(#"d9004a4bb8afcec950bb0c76ab3817f32b38d4aef71013dae38082ea6824c684")
  expect asset_boundary_queue_call(value, 3)
  True
}

test asset_boundary_08_queue_receipt_policy_rejects() fail {
  let value = asset_boundary_queue(#"d9004a4bb8afcec950bb0c76ab3817f32b38d4aef71013dae38082ea6824c684")
  expect asset_boundary_queue_call(value, 4)
  True
}

test asset_boundary_08_queue_intent_policy_rejects() fail {
  let value = asset_boundary_queue(#"d9004a4bb8afcec950bb0c76ab3817f32b38d4aef71013dae38082ea6824c684")
  expect asset_boundary_queue_call(value, 5)
  True
}

test asset_boundary_09_fixture_conserves() {
  let value = asset_boundary_vote(#"a3bffc17007ff92d8232c58994aaa4c9ad35af324acf9c322bf67c61d3553a3b")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_09_vote_transition_rejects() fail {
  let value = asset_boundary_vote(#"a3bffc17007ff92d8232c58994aaa4c9ad35af324acf9c322bf67c61d3553a3b")
  expect asset_boundary_vote_call(value, 0)
  True
}

test asset_boundary_09_vote_governor_spend_rejects() fail {
  let value = asset_boundary_vote(#"a3bffc17007ff92d8232c58994aaa4c9ad35af324acf9c322bf67c61d3553a3b")
  expect asset_boundary_vote_call(value, 1)
  True
}

test asset_boundary_09_vote_receipt_policy_rejects() fail {
  let value = asset_boundary_vote(#"a3bffc17007ff92d8232c58994aaa4c9ad35af324acf9c322bf67c61d3553a3b")
  expect asset_boundary_vote_call(value, 2)
  True
}

test asset_boundary_10_fixture_conserves() {
  let value = asset_boundary_queue(#"e60cc38d68a729fa6ec553bc65765f520d396c2a682b66c77eee60b972920a54")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_10_queue_transition_rejects() fail {
  let value = asset_boundary_queue(#"e60cc38d68a729fa6ec553bc65765f520d396c2a682b66c77eee60b972920a54")
  expect asset_boundary_queue_call(value, 0)
  True
}

test asset_boundary_10_queue_authority_spend_rejects() fail {
  let value = asset_boundary_queue(#"e60cc38d68a729fa6ec553bc65765f520d396c2a682b66c77eee60b972920a54")
  expect asset_boundary_queue_call(value, 1)
  True
}

test asset_boundary_10_queue_governor_spend_rejects() fail {
  let value = asset_boundary_queue(#"e60cc38d68a729fa6ec553bc65765f520d396c2a682b66c77eee60b972920a54")
  expect asset_boundary_queue_call(value, 2)
  True
}

test asset_boundary_10_queue_proposal_policy_rejects() fail {
  let value = asset_boundary_queue(#"e60cc38d68a729fa6ec553bc65765f520d396c2a682b66c77eee60b972920a54")
  expect asset_boundary_queue_call(value, 3)
  True
}

test asset_boundary_10_queue_receipt_policy_rejects() fail {
  let value = asset_boundary_queue(#"e60cc38d68a729fa6ec553bc65765f520d396c2a682b66c77eee60b972920a54")
  expect asset_boundary_queue_call(value, 4)
  True
}

test asset_boundary_10_queue_intent_policy_rejects() fail {
  let value = asset_boundary_queue(#"e60cc38d68a729fa6ec553bc65765f520d396c2a682b66c77eee60b972920a54")
  expect asset_boundary_queue_call(value, 5)
  True
}

test asset_boundary_11_fixture_conserves() {
  let value = asset_boundary_vote(#"aab2968a9ab77778924f03674ed0309dfe0cd2bb75de04aec543a73879ed1426")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_11_vote_transition_rejects() fail {
  let value = asset_boundary_vote(#"aab2968a9ab77778924f03674ed0309dfe0cd2bb75de04aec543a73879ed1426")
  expect asset_boundary_vote_call(value, 0)
  True
}

test asset_boundary_11_vote_governor_spend_rejects() fail {
  let value = asset_boundary_vote(#"aab2968a9ab77778924f03674ed0309dfe0cd2bb75de04aec543a73879ed1426")
  expect asset_boundary_vote_call(value, 1)
  True
}

test asset_boundary_11_vote_receipt_policy_rejects() fail {
  let value = asset_boundary_vote(#"aab2968a9ab77778924f03674ed0309dfe0cd2bb75de04aec543a73879ed1426")
  expect asset_boundary_vote_call(value, 2)
  True
}

test asset_boundary_12_fixture_conserves() {
  let value = asset_boundary_queue(#"9c38d29b5dc09c8a4cc6d13145f66723781ecbe87f39396c11fa2b53f7a17387")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_12_queue_transition_rejects() fail {
  let value = asset_boundary_queue(#"9c38d29b5dc09c8a4cc6d13145f66723781ecbe87f39396c11fa2b53f7a17387")
  expect asset_boundary_queue_call(value, 0)
  True
}

test asset_boundary_12_queue_authority_spend_rejects() fail {
  let value = asset_boundary_queue(#"9c38d29b5dc09c8a4cc6d13145f66723781ecbe87f39396c11fa2b53f7a17387")
  expect asset_boundary_queue_call(value, 1)
  True
}

test asset_boundary_12_queue_governor_spend_rejects() fail {
  let value = asset_boundary_queue(#"9c38d29b5dc09c8a4cc6d13145f66723781ecbe87f39396c11fa2b53f7a17387")
  expect asset_boundary_queue_call(value, 2)
  True
}

test asset_boundary_12_queue_proposal_policy_rejects() fail {
  let value = asset_boundary_queue(#"9c38d29b5dc09c8a4cc6d13145f66723781ecbe87f39396c11fa2b53f7a17387")
  expect asset_boundary_queue_call(value, 3)
  True
}

test asset_boundary_12_queue_receipt_policy_rejects() fail {
  let value = asset_boundary_queue(#"9c38d29b5dc09c8a4cc6d13145f66723781ecbe87f39396c11fa2b53f7a17387")
  expect asset_boundary_queue_call(value, 4)
  True
}

test asset_boundary_12_queue_intent_policy_rejects() fail {
  let value = asset_boundary_queue(#"9c38d29b5dc09c8a4cc6d13145f66723781ecbe87f39396c11fa2b53f7a17387")
  expect asset_boundary_queue_call(value, 5)
  True
}

test asset_boundary_13_fixture_conserves() {
  let value = asset_boundary_vote(#"c8176eb14d9be1bcb4a7a3c7c4873848507ed2628d7ae2cac7983471e7fafc79")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_13_vote_transition_rejects() fail {
  let value = asset_boundary_vote(#"c8176eb14d9be1bcb4a7a3c7c4873848507ed2628d7ae2cac7983471e7fafc79")
  expect asset_boundary_vote_call(value, 0)
  True
}

test asset_boundary_13_vote_governor_spend_rejects() fail {
  let value = asset_boundary_vote(#"c8176eb14d9be1bcb4a7a3c7c4873848507ed2628d7ae2cac7983471e7fafc79")
  expect asset_boundary_vote_call(value, 1)
  True
}

test asset_boundary_13_vote_receipt_policy_rejects() fail {
  let value = asset_boundary_vote(#"c8176eb14d9be1bcb4a7a3c7c4873848507ed2628d7ae2cac7983471e7fafc79")
  expect asset_boundary_vote_call(value, 2)
  True
}

test asset_boundary_14_fixture_conserves() {
  let value = asset_boundary_queue(#"e87e9c5842c893d8e1b94007d55154ec64effa83fe6a1d4b12902f579c4cb772")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_14_queue_transition_rejects() fail {
  let value = asset_boundary_queue(#"e87e9c5842c893d8e1b94007d55154ec64effa83fe6a1d4b12902f579c4cb772")
  expect asset_boundary_queue_call(value, 0)
  True
}

test asset_boundary_14_queue_authority_spend_rejects() fail {
  let value = asset_boundary_queue(#"e87e9c5842c893d8e1b94007d55154ec64effa83fe6a1d4b12902f579c4cb772")
  expect asset_boundary_queue_call(value, 1)
  True
}

test asset_boundary_14_queue_governor_spend_rejects() fail {
  let value = asset_boundary_queue(#"e87e9c5842c893d8e1b94007d55154ec64effa83fe6a1d4b12902f579c4cb772")
  expect asset_boundary_queue_call(value, 2)
  True
}

test asset_boundary_14_queue_proposal_policy_rejects() fail {
  let value = asset_boundary_queue(#"e87e9c5842c893d8e1b94007d55154ec64effa83fe6a1d4b12902f579c4cb772")
  expect asset_boundary_queue_call(value, 3)
  True
}

test asset_boundary_14_queue_receipt_policy_rejects() fail {
  let value = asset_boundary_queue(#"e87e9c5842c893d8e1b94007d55154ec64effa83fe6a1d4b12902f579c4cb772")
  expect asset_boundary_queue_call(value, 4)
  True
}

test asset_boundary_14_queue_intent_policy_rejects() fail {
  let value = asset_boundary_queue(#"e87e9c5842c893d8e1b94007d55154ec64effa83fe6a1d4b12902f579c4cb772")
  expect asset_boundary_queue_call(value, 5)
  True
}

test asset_boundary_15_fixture_conserves() {
  let value = asset_boundary_vote(#"0f7d528d578d877798bb89bb940d0a9a61129c211b0a6fbbc4b459a225f7bc37")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_15_vote_transition_rejects() fail {
  let value = asset_boundary_vote(#"0f7d528d578d877798bb89bb940d0a9a61129c211b0a6fbbc4b459a225f7bc37")
  expect asset_boundary_vote_call(value, 0)
  True
}

test asset_boundary_15_vote_governor_spend_rejects() fail {
  let value = asset_boundary_vote(#"0f7d528d578d877798bb89bb940d0a9a61129c211b0a6fbbc4b459a225f7bc37")
  expect asset_boundary_vote_call(value, 1)
  True
}

test asset_boundary_15_vote_receipt_policy_rejects() fail {
  let value = asset_boundary_vote(#"0f7d528d578d877798bb89bb940d0a9a61129c211b0a6fbbc4b459a225f7bc37")
  expect asset_boundary_vote_call(value, 2)
  True
}

test asset_boundary_16_fixture_conserves() {
  let value = asset_boundary_queue(#"1d027978371047852b91c170809f7561539aff1e0f1938bd11e7e9913169e1bf")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_16_queue_transition_rejects() fail {
  let value = asset_boundary_queue(#"1d027978371047852b91c170809f7561539aff1e0f1938bd11e7e9913169e1bf")
  expect asset_boundary_queue_call(value, 0)
  True
}

test asset_boundary_16_queue_authority_spend_rejects() fail {
  let value = asset_boundary_queue(#"1d027978371047852b91c170809f7561539aff1e0f1938bd11e7e9913169e1bf")
  expect asset_boundary_queue_call(value, 1)
  True
}

test asset_boundary_16_queue_governor_spend_rejects() fail {
  let value = asset_boundary_queue(#"1d027978371047852b91c170809f7561539aff1e0f1938bd11e7e9913169e1bf")
  expect asset_boundary_queue_call(value, 2)
  True
}

test asset_boundary_16_queue_proposal_policy_rejects() fail {
  let value = asset_boundary_queue(#"1d027978371047852b91c170809f7561539aff1e0f1938bd11e7e9913169e1bf")
  expect asset_boundary_queue_call(value, 3)
  True
}

test asset_boundary_16_queue_receipt_policy_rejects() fail {
  let value = asset_boundary_queue(#"1d027978371047852b91c170809f7561539aff1e0f1938bd11e7e9913169e1bf")
  expect asset_boundary_queue_call(value, 4)
  True
}

test asset_boundary_16_queue_intent_policy_rejects() fail {
  let value = asset_boundary_queue(#"1d027978371047852b91c170809f7561539aff1e0f1938bd11e7e9913169e1bf")
  expect asset_boundary_queue_call(value, 5)
  True
}

test asset_boundary_17_fixture_conserves() {
  let value = asset_boundary_vote(#"6f34297567b8031faab8fd89d94a740e820d2832e80ad01b44ae2a128209cd7f")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_17_vote_transition_rejects() fail {
  let value = asset_boundary_vote(#"6f34297567b8031faab8fd89d94a740e820d2832e80ad01b44ae2a128209cd7f")
  expect asset_boundary_vote_call(value, 0)
  True
}

test asset_boundary_17_vote_governor_spend_rejects() fail {
  let value = asset_boundary_vote(#"6f34297567b8031faab8fd89d94a740e820d2832e80ad01b44ae2a128209cd7f")
  expect asset_boundary_vote_call(value, 1)
  True
}

test asset_boundary_17_vote_receipt_policy_rejects() fail {
  let value = asset_boundary_vote(#"6f34297567b8031faab8fd89d94a740e820d2832e80ad01b44ae2a128209cd7f")
  expect asset_boundary_vote_call(value, 2)
  True
}

test asset_boundary_18_fixture_conserves() {
  let value = asset_boundary_queue(#"b53f7dcbdc5214cdcc3e1115d5783c7e29acb9d44b45c0ea2aee9e3ddfd8d9e2")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_18_queue_transition_rejects() fail {
  let value = asset_boundary_queue(#"b53f7dcbdc5214cdcc3e1115d5783c7e29acb9d44b45c0ea2aee9e3ddfd8d9e2")
  expect asset_boundary_queue_call(value, 0)
  True
}

test asset_boundary_18_queue_authority_spend_rejects() fail {
  let value = asset_boundary_queue(#"b53f7dcbdc5214cdcc3e1115d5783c7e29acb9d44b45c0ea2aee9e3ddfd8d9e2")
  expect asset_boundary_queue_call(value, 1)
  True
}

test asset_boundary_18_queue_governor_spend_rejects() fail {
  let value = asset_boundary_queue(#"b53f7dcbdc5214cdcc3e1115d5783c7e29acb9d44b45c0ea2aee9e3ddfd8d9e2")
  expect asset_boundary_queue_call(value, 2)
  True
}

test asset_boundary_18_queue_proposal_policy_rejects() fail {
  let value = asset_boundary_queue(#"b53f7dcbdc5214cdcc3e1115d5783c7e29acb9d44b45c0ea2aee9e3ddfd8d9e2")
  expect asset_boundary_queue_call(value, 3)
  True
}

test asset_boundary_18_queue_receipt_policy_rejects() fail {
  let value = asset_boundary_queue(#"b53f7dcbdc5214cdcc3e1115d5783c7e29acb9d44b45c0ea2aee9e3ddfd8d9e2")
  expect asset_boundary_queue_call(value, 4)
  True
}

test asset_boundary_18_queue_intent_policy_rejects() fail {
  let value = asset_boundary_queue(#"b53f7dcbdc5214cdcc3e1115d5783c7e29acb9d44b45c0ea2aee9e3ddfd8d9e2")
  expect asset_boundary_queue_call(value, 5)
  True
}

test asset_boundary_19_fixture_conserves() {
  let value = asset_boundary_vote(#"0639e808bd21884d2e6a473f782dbaa1b6637e8d93d0634b175a8824c68d9f08")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_19_vote_transition_rejects() fail {
  let value = asset_boundary_vote(#"0639e808bd21884d2e6a473f782dbaa1b6637e8d93d0634b175a8824c68d9f08")
  expect asset_boundary_vote_call(value, 0)
  True
}

test asset_boundary_19_vote_governor_spend_rejects() fail {
  let value = asset_boundary_vote(#"0639e808bd21884d2e6a473f782dbaa1b6637e8d93d0634b175a8824c68d9f08")
  expect asset_boundary_vote_call(value, 1)
  True
}

test asset_boundary_19_vote_receipt_policy_rejects() fail {
  let value = asset_boundary_vote(#"0639e808bd21884d2e6a473f782dbaa1b6637e8d93d0634b175a8824c68d9f08")
  expect asset_boundary_vote_call(value, 2)
  True
}

test asset_boundary_20_fixture_conserves() {
  let value = asset_boundary_queue(#"3e511e1a0df5eac3114a004a17747663d67a2f08589612560dddaaab4e9274a8")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_20_queue_transition_rejects() fail {
  let value = asset_boundary_queue(#"3e511e1a0df5eac3114a004a17747663d67a2f08589612560dddaaab4e9274a8")
  expect asset_boundary_queue_call(value, 0)
  True
}

test asset_boundary_20_queue_authority_spend_rejects() fail {
  let value = asset_boundary_queue(#"3e511e1a0df5eac3114a004a17747663d67a2f08589612560dddaaab4e9274a8")
  expect asset_boundary_queue_call(value, 1)
  True
}

test asset_boundary_20_queue_governor_spend_rejects() fail {
  let value = asset_boundary_queue(#"3e511e1a0df5eac3114a004a17747663d67a2f08589612560dddaaab4e9274a8")
  expect asset_boundary_queue_call(value, 2)
  True
}

test asset_boundary_20_queue_proposal_policy_rejects() fail {
  let value = asset_boundary_queue(#"3e511e1a0df5eac3114a004a17747663d67a2f08589612560dddaaab4e9274a8")
  expect asset_boundary_queue_call(value, 3)
  True
}

test asset_boundary_20_queue_receipt_policy_rejects() fail {
  let value = asset_boundary_queue(#"3e511e1a0df5eac3114a004a17747663d67a2f08589612560dddaaab4e9274a8")
  expect asset_boundary_queue_call(value, 4)
  True
}

test asset_boundary_20_queue_intent_policy_rejects() fail {
  let value = asset_boundary_queue(#"3e511e1a0df5eac3114a004a17747663d67a2f08589612560dddaaab4e9274a8")
  expect asset_boundary_queue_call(value, 5)
  True
}

test asset_boundary_21_fixture_conserves() {
  let value = asset_boundary_vote(#"cea8ba4f5321fbdd9f39a0c54fad6d07ce1e419e00ec609e81d53058db702324")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_21_vote_transition_rejects() fail {
  let value = asset_boundary_vote(#"cea8ba4f5321fbdd9f39a0c54fad6d07ce1e419e00ec609e81d53058db702324")
  expect asset_boundary_vote_call(value, 0)
  True
}

test asset_boundary_21_vote_governor_spend_rejects() fail {
  let value = asset_boundary_vote(#"cea8ba4f5321fbdd9f39a0c54fad6d07ce1e419e00ec609e81d53058db702324")
  expect asset_boundary_vote_call(value, 1)
  True
}

test asset_boundary_21_vote_receipt_policy_rejects() fail {
  let value = asset_boundary_vote(#"cea8ba4f5321fbdd9f39a0c54fad6d07ce1e419e00ec609e81d53058db702324")
  expect asset_boundary_vote_call(value, 2)
  True
}

test asset_boundary_22_fixture_conserves() {
  let value = asset_boundary_queue(#"62a27a672c960879bd72f9d0350c69d66f3d75a64782f1d64e0f68dbee16135f")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_22_queue_transition_rejects() fail {
  let value = asset_boundary_queue(#"62a27a672c960879bd72f9d0350c69d66f3d75a64782f1d64e0f68dbee16135f")
  expect asset_boundary_queue_call(value, 0)
  True
}

test asset_boundary_22_queue_authority_spend_rejects() fail {
  let value = asset_boundary_queue(#"62a27a672c960879bd72f9d0350c69d66f3d75a64782f1d64e0f68dbee16135f")
  expect asset_boundary_queue_call(value, 1)
  True
}

test asset_boundary_22_queue_governor_spend_rejects() fail {
  let value = asset_boundary_queue(#"62a27a672c960879bd72f9d0350c69d66f3d75a64782f1d64e0f68dbee16135f")
  expect asset_boundary_queue_call(value, 2)
  True
}

test asset_boundary_22_queue_proposal_policy_rejects() fail {
  let value = asset_boundary_queue(#"62a27a672c960879bd72f9d0350c69d66f3d75a64782f1d64e0f68dbee16135f")
  expect asset_boundary_queue_call(value, 3)
  True
}

test asset_boundary_22_queue_receipt_policy_rejects() fail {
  let value = asset_boundary_queue(#"62a27a672c960879bd72f9d0350c69d66f3d75a64782f1d64e0f68dbee16135f")
  expect asset_boundary_queue_call(value, 4)
  True
}

test asset_boundary_22_queue_intent_policy_rejects() fail {
  let value = asset_boundary_queue(#"62a27a672c960879bd72f9d0350c69d66f3d75a64782f1d64e0f68dbee16135f")
  expect asset_boundary_queue_call(value, 5)
  True
}

test asset_boundary_23_fixture_conserves() {
  let value = asset_boundary_vote(#"25e9b2b04d7346eadd99b1665915b1bf4df48b6d42257893f5390a7ac200cd86")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_23_vote_transition_rejects() fail {
  let value = asset_boundary_vote(#"25e9b2b04d7346eadd99b1665915b1bf4df48b6d42257893f5390a7ac200cd86")
  expect asset_boundary_vote_call(value, 0)
  True
}

test asset_boundary_23_vote_governor_spend_rejects() fail {
  let value = asset_boundary_vote(#"25e9b2b04d7346eadd99b1665915b1bf4df48b6d42257893f5390a7ac200cd86")
  expect asset_boundary_vote_call(value, 1)
  True
}

test asset_boundary_23_vote_receipt_policy_rejects() fail {
  let value = asset_boundary_vote(#"25e9b2b04d7346eadd99b1665915b1bf4df48b6d42257893f5390a7ac200cd86")
  expect asset_boundary_vote_call(value, 2)
  True
}

test asset_boundary_24_fixture_conserves() {
  let value = asset_boundary_queue(#"492e0450126d2b26b80dfb877fc787b58f83059f89d2ae37d78b0936fb237e")
  and { governance_v2.envelope(value), asset_boundary_conserves(value) }
}

test asset_boundary_24_queue_transition_rejects() fail {
  let value = asset_boundary_queue(#"492e0450126d2b26b80dfb877fc787b58f83059f89d2ae37d78b0936fb237e")
  expect asset_boundary_queue_call(value, 0)
  True
}

test asset_boundary_24_queue_authority_spend_rejects() fail {
  let value = asset_boundary_queue(#"492e0450126d2b26b80dfb877fc787b58f83059f89d2ae37d78b0936fb237e")
  expect asset_boundary_queue_call(value, 1)
  True
}

test asset_boundary_24_queue_governor_spend_rejects() fail {
  let value = asset_boundary_queue(#"492e0450126d2b26b80dfb877fc787b58f83059f89d2ae37d78b0936fb237e")
  expect asset_boundary_queue_call(value, 2)
  True
}

test asset_boundary_24_queue_proposal_policy_rejects() fail {
  let value = asset_boundary_queue(#"492e0450126d2b26b80dfb877fc787b58f83059f89d2ae37d78b0936fb237e")
  expect asset_boundary_queue_call(value, 3)
  True
}

test asset_boundary_24_queue_receipt_policy_rejects() fail {
  let value = asset_boundary_queue(#"492e0450126d2b26b80dfb877fc787b58f83059f89d2ae37d78b0936fb237e")
  expect asset_boundary_queue_call(value, 4)
  True
}

test asset_boundary_24_queue_intent_policy_rejects() fail {
  let value = asset_boundary_queue(#"492e0450126d2b26b80dfb877fc787b58f83059f89d2ae37d78b0936fb237e")
  expect asset_boundary_queue_call(value, 5)
  True
}


//// Remainder26: PROPOSED refinements; all native/ledger/budget checks NOT_RUN.
//// Earlier289test/helper bodies preserved; only imports extended above.
//// Resource controls test envelope bounds, not valid signed ledger transactions.
fn remainder_before(value: Transaction, index: Int) -> ProposalDatumV2 {
  expect Some(input) = list.at(value.inputs, index)
  expect InlineDatum(raw) = input.output.datum
  expect p: ProposalDatumV2 = raw
  p
}

fn remainder_intent_before(value: Transaction) -> IntentDatumV2 {
  expect Some(input) = list.at(value.inputs, 0)
  expect InlineDatum(raw) = input.output.datum
  expect i: IntentDatumV2 = raw
  i
}

fn remainder_eighth_before() -> ProposalDatumV2 {
  ProposalDatumV2 { ..maximal_proposal(), yes_weight: 70,
    locks: list.take(maximal_proposal().locks, 7) }
}

fn remainder_base(action: Int) -> Transaction {
  when action is {
    0 -> create_tx()
    1 -> vote_tx(False)
    2 -> Transaction { ..tx(2000, 2100),
      inputs: [proposal_input(first(True)), funding(proposer, 1_000_000, 0)],
      reference_inputs: [authority(cfg())], extra_signatories: [proposer],
      outputs: [out(script(governor_hash), pvalue(passed()), passed()),
        pay(key(proposer), assets.from_lovelace(800_000))] }
    3 -> terminal_tx(False)
    4 -> terminal_tx(True)
    5 -> queue_tx()
    6 -> intent_tx(True)
    7 -> intent_tx(False)
    // Non-executing terminal-intent stand-in; never an execution specification.
    8 -> intent_tx(True)
    9 -> {
      let before = remainder_eighth_before()
      let after = maximal_proposal()
      expect Some(last) = list.at(after.locks, 7)
      Transaction { ..tx(1000, 1100),
        inputs: [proposal_input(before), funding(last.voter_vkh, 5_000_000, 100)],
        reference_inputs: [authority(cfg())], extra_signatories: [last.voter_vkh],
        outputs: [out(script(governor_hash), pvalue(after), after),
          pay(key(last.voter_vkh), assets.from_lovelace(3_800_000))],
        mint: assets.from_asset(receipt_policy, last.receipt_name, 1) }
    }
    _ -> fail
  }
}

fn remainder_call(action: Int, value: Transaction, caller: Int) -> Bool {
  when action is {
    0 -> when caller is {
      0 -> governance_v2_transitions.create(anchor(), value)
      1 -> governance_v2_transitions.authority_spend(bootstrap(), AuthorityDatumV2 {
        config: GovernanceConfigV2 { ..cfg(), next_proposal_nonce: 0 } }, CreateV2, ref(0), value)
      2 -> governance_v2_transitions.policy_mint(anchor(), 1, proposal_policy, CreateV2, value)
      _ -> False
    }
    1 -> asset_boundary_vote_call(value, caller)
    2 -> when caller is {
      0 -> governance_v2_transitions.finalize_passed(anchor(), value)
      1 -> governance_v2_transitions.governor_spend(anchor(), remainder_before(value, 0), FinalizePassedV2, ref(1), value)
      _ -> False
    }
    3 | 4 -> {
      let cancel = action == 4
      let request = if cancel { CancelProposalV2 } else { FinalizeRejectedV2 }
      when caller is {
        0 -> governance_v2_transitions.terminal_proposal(anchor(), value, cancel)
        1 -> governance_v2_transitions.governor_spend(anchor(), remainder_before(value, 0), request, ref(1), value)
        2 -> governance_v2_transitions.policy_mint(anchor(), 1, proposal_policy, request, value)
        3 -> governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, request, value)
        _ -> False
      }
    }
    5 -> asset_boundary_queue_call(value, caller)
    6 | 7 -> {
      let cancel = action == 6
      let request = if cancel { CancelIntentV2 } else { ExpireIntentV2 }
      when caller is {
        0 -> governance_v2_transitions.terminal_intent(anchor(), value, cancel)
        1 -> governance_v2_transitions.timelock_spend(anchor(), remainder_intent_before(value), request, ref(3), value)
        2 -> governance_v2_transitions.policy_mint(anchor(), 3, intent_policy, request, value)
        _ -> False
      }
    }
    8 -> when caller is {
      0 -> governance_v2_transitions.timelock_spend(anchor(), remainder_intent_before(value), ExecuteIntentV2, ref(3), value)
      1 -> governance_v2_transitions.policy_mint(anchor(), 3, intent_policy, ExecuteIntentV2, value)
      _ -> False
    }
    9 -> {
      expect Some(last) = list.at(maximal_proposal().locks, 7)
      let request = VoteV2 { voter_vkh: last.voter_vkh, support: True, locked_vams: 100 }
      when caller is {
        0 -> governance_v2_transitions.vote(anchor(), value, last.voter_vkh, True, 100)
        1 -> governance_v2_transitions.governor_spend(anchor(), remainder_before(value, 0), request, ref(1), value)
        2 -> governance_v2_transitions.policy_mint(anchor(), 2, receipt_policy, request, value)
        _ -> False
      }
    }
    _ -> False
  }
}

fn remainder_replace_output(value: Transaction, index: Int, output: Output) -> Transaction {
  Transaction { ..value, outputs: list.indexed_map(value.outputs,
    fn(i, before) { if i == index { output } else { before } }) }
}

fn remainder_raw(size: Int) -> Data { bytearray.from_int_big_endian(0, size) }

fn remainder_last(value: Transaction) -> Output {
  expect Some(output) = list.at(value.outputs, list.length(value.outputs) - 1)
  output
}

fn remainder_mutant(action: Int, variant: Int, at_limit: Bool) -> Transaction {
  let value = remainder_base(action)
  when variant is {
    0 | 1 -> {
      let count = if variant == 0 { 1 } else { (if at_limit { 16 } else { 17 }) - list.length(value.inputs) }
      let extra = list.map(list.range(0, count - 1), fn(i) {
        Input { output_reference: ref(100 + i), output: pay(key(proposer), assets.from_lovelace(2_000_000)) }
      })
      let change = remainder_last(value)
      Transaction { ..remainder_replace_output(value, list.length(value.outputs) - 1,
        Output { ..change, value: assets.add(change.value, #"", #"", count * 2_000_000) }),
        inputs: list.concat(value.inputs, extra) }
    }
    2 | 3 -> {
      let count = if variant == 2 { 1 } else { (if at_limit { 16 } else { 17 }) - list.length(value.outputs) }
      let outputs = list.map(list.range(0, count - 1), fn(_) { pay(key(proposer), assets.from_lovelace(2_000_000)) })
      Transaction { ..value, outputs: list.concat(value.outputs, outputs),
        inputs: list.indexed_map(value.inputs, fn(i, input) {
          if i == list.length(value.inputs) - 1 {
            Input { ..input, output: Output { ..input.output,
              value: assets.add(input.output.value, #"", #"", count * 2_000_000) } }
          } else { input }
        }) }
    }
    4 -> {
      let auxiliary = list.foldl(list.range(0, if at_limit { 14 } else { 15 }), assets.zero,
        fn(i, acc) { assets.add(acc, vams_policy, bytearray.from_int_big_endian(i, 1), 1) })
      let change = remainder_last(value)
      Transaction { ..remainder_replace_output(value, list.length(value.outputs) - 1,
        Output { ..change, value: assets.merge(change.value, auxiliary) }),
        inputs: list.indexed_map(value.inputs, fn(i, input) {
          if i == list.length(value.inputs) - 1 {
            Input { ..input, output: Output { ..input.output, value: assets.merge(input.output.value, auxiliary) } }
          } else { input }
        }) }
    }
    5 | 16 -> {
      let index = if variant == 16 { 0 } else { list.length(value.outputs) - 1 }
      expect Some(output) = list.at(value.outputs, index)
      remainder_replace_output(value, index, Output { ..output,
        datum: InlineDatum(remainder_raw(if at_limit { 866 } else { 867 })) })
    }
    6 -> Transaction { ..value, extra_signatories: if at_limit {
      [alice, bob, proposer, member4, member5]
    } else { [alice, bob, proposer, member4, member5,
      #"06060606060606060606060606060606060606060606060606060606"] } }
    7 -> {
      if action == 0 || action == 1 || action == 2 {
        let index = if action == 0 { 1 } else { 0 }
        expect Some(output) = list.at(value.outputs, index)
        expect InlineDatum(raw) = output.datum
        expect p: ProposalDatumV2 = raw
        remainder_replace_output(value, index, Output { ..output,
          datum: InlineDatum(ProposalDatumV2 { ..p, version: 1 }) })
      } else {
        Transaction { ..value, inputs: list.indexed_map(value.inputs, fn(index, input) {
          if index == 0 {
            expect InlineDatum(raw) = input.output.datum
            let changed: Data = if action == 3 || action == 4 {
              expect p: ProposalDatumV2 = raw
              ProposalDatumV2 { ..p, version: 1 }
            } else {
              expect i: IntentDatumV2 = raw
              IntentDatumV2 { ..i, version: 1 }
            }
            Input { ..input, output: Output { ..input.output, datum: InlineDatum(changed) } }
          } else { input }
        }) }
      }
    }
    8 -> {
      expect Some(output) = list.at(value.outputs, 0)
      remainder_replace_output(value, 0, Output { ..output, address: key(bob) })
    }
    9 -> Transaction { ..value, validity_range: half_open(-1, 1) }
    10 -> Transaction { ..value, validity_range: half_open(1999, 2000) }
    11 -> Transaction { ..value, validity_range: half_open(2001, 2002) }
    12 -> Transaction { ..value, validity_range: half_open(2000, 2100) }
    13 -> Transaction { ..value, validity_range: half_open(2100, 2100) }
    14 -> Transaction { ..value, validity_range: half_open(172_802_099, 172_802_100) }
    _ -> fail
  }
}

fn remainder_probe_shape(action: Int, variant: Int, value: Transaction) -> Bool {
  let base = remainder_base(action)
  when variant is {
    0 -> list.length(value.inputs) == list.length(base.inputs) + 1 && governance_v2.envelope(value)
    1 -> list.length(value.inputs) == 17
    2 -> list.length(value.outputs) == list.length(base.outputs) + 1 && governance_v2.envelope(value)
    3 -> list.length(value.outputs) == 17
    4 -> list.length(assets.flatten(remainder_last(value).value)) == 17
    5 | 16 -> {
      let index = if variant == 16 { 0 } else { list.length(value.outputs) - 1 }
      expect Some(output) = list.at(value.outputs, index)
      expect InlineDatum(raw) = output.datum
      bytearray.length(cbor.serialise(raw)) == 897
    }
    6 -> list.length(value.extra_signatories) == 6
    7 -> {
      if action == 0 || action == 1 || action == 2 {
        expect Some(output) = list.at(value.outputs, if action == 0 { 1 } else { 0 })
        expect InlineDatum(raw) = output.datum
        expect p: ProposalDatumV2 = raw
        p.version == 1
      } else if action == 3 || action == 4 { remainder_before(value, 0).version == 1 }
      else { remainder_intent_before(value).version == 1 }
    }
    8 -> {
      expect Some(output) = list.at(value.outputs, 0)
      output.address == key(bob)
    }
    9 -> governance_v2.now_ms(value) == -1 && governance_v2.upper_ms(value) == 1
    10 -> governance_v2.now_ms(value) == 1999 && governance_v2.upper_ms(value) == 2000
    11 -> governance_v2.now_ms(value) == 2001 && governance_v2.upper_ms(value) == 2002
    12 -> governance_v2.now_ms(value) == 2000 && governance_v2.upper_ms(value) == 2100
    13 -> governance_v2.now_ms(value) == 2100 && governance_v2.upper_ms(value) == 2100
    14 -> governance_v2.now_ms(value) == 172_802_099 && governance_v2.upper_ms(value) == 172_802_100
    _ -> False
  }
}

test remainder26_create_transition_baseline_accepts() {
  remainder_call(0, remainder_base(0), 0)
}

test remainder26_create_authority_spend_baseline_accepts() {
  remainder_call(0, remainder_base(0), 1)
}

test remainder26_create_proposal_policy_baseline_accepts() {
  remainder_call(0, remainder_base(0), 2)
}

test remainder26_vote_transition_baseline_accepts() {
  remainder_call(1, remainder_base(1), 0)
}

test remainder26_vote_governor_spend_baseline_accepts() {
  remainder_call(1, remainder_base(1), 1)
}

test remainder26_vote_receipt_policy_baseline_accepts() {
  remainder_call(1, remainder_base(1), 2)
}

test remainder26_finalize_passed_transition_baseline_accepts() {
  remainder_call(2, remainder_base(2), 0)
}

test remainder26_finalize_passed_governor_spend_baseline_accepts() {
  remainder_call(2, remainder_base(2), 1)
}

test remainder26_finalize_rejected_transition_baseline_accepts() {
  remainder_call(3, remainder_base(3), 0)
}

test remainder26_finalize_rejected_governor_spend_baseline_accepts() {
  remainder_call(3, remainder_base(3), 1)
}

test remainder26_finalize_rejected_proposal_policy_baseline_accepts() {
  remainder_call(3, remainder_base(3), 2)
}

test remainder26_finalize_rejected_receipt_policy_baseline_accepts() {
  remainder_call(3, remainder_base(3), 3)
}

test remainder26_cancel_transition_baseline_accepts() {
  remainder_call(4, remainder_base(4), 0)
}

test remainder26_cancel_governor_spend_baseline_accepts() {
  remainder_call(4, remainder_base(4), 1)
}

test remainder26_cancel_proposal_policy_baseline_accepts() {
  remainder_call(4, remainder_base(4), 2)
}

test remainder26_cancel_receipt_policy_baseline_accepts() {
  remainder_call(4, remainder_base(4), 3)
}

test remainder26_queue_transition_baseline_accepts() {
  remainder_call(5, remainder_base(5), 0)
}

test remainder26_queue_authority_spend_baseline_accepts() {
  remainder_call(5, remainder_base(5), 1)
}

test remainder26_queue_governor_spend_baseline_accepts() {
  remainder_call(5, remainder_base(5), 2)
}

test remainder26_queue_proposal_policy_baseline_accepts() {
  remainder_call(5, remainder_base(5), 3)
}

test remainder26_queue_receipt_policy_baseline_accepts() {
  remainder_call(5, remainder_base(5), 4)
}

test remainder26_queue_intent_policy_baseline_accepts() {
  remainder_call(5, remainder_base(5), 5)
}

test remainder26_cancelintent_transition_baseline_accepts() {
  remainder_call(6, remainder_base(6), 0)
}

test remainder26_cancelintent_timelock_spend_baseline_accepts() {
  remainder_call(6, remainder_base(6), 1)
}

test remainder26_cancelintent_intent_policy_baseline_accepts() {
  remainder_call(6, remainder_base(6), 2)
}

test remainder26_expireintent_transition_baseline_accepts() {
  remainder_call(7, remainder_base(7), 0)
}

test remainder26_expireintent_timelock_spend_baseline_accepts() {
  remainder_call(7, remainder_base(7), 1)
}

test remainder26_expireintent_intent_policy_baseline_accepts() {
  remainder_call(7, remainder_base(7), 2)
}

test remainder26_executeintent_timelock_spend_baseline_disabled() {
  !remainder_call(8, remainder_base(8), 0)
}

test remainder26_executeintent_intent_policy_baseline_disabled() {
  !remainder_call(8, remainder_base(8), 1)
}

test remainder26_eighth_vote_transition_baseline_accepts() {
  remainder_call(9, remainder_base(9), 0)
}

test remainder26_eighth_vote_governor_spend_baseline_accepts() {
  remainder_call(9, remainder_base(9), 1)
}

test remainder26_eighth_vote_receipt_policy_baseline_accepts() {
  remainder_call(9, remainder_base(9), 2)
}

test remainder26_maximum_width_datum_eighth_vote_maximum_width_construction() {
  let value = remainder_mutant(9, 16, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(9, 16, value) }
}

test remainder26_maximum_width_datum_eighth_vote_maximum_width_transition_rejects() fail {
  let value = remainder_mutant(9, 16, False)
  expect remainder_call(9, value, 0)
  True
}

test remainder26_maximum_width_datum_eighth_vote_maximum_width_governor_spend_rejects() fail {
  let value = remainder_mutant(9, 16, False)
  expect remainder_call(9, value, 1)
  True
}

test remainder26_maximum_width_datum_eighth_vote_maximum_width_receipt_policy_rejects() fail {
  let value = remainder_mutant(9, 16, False)
  expect remainder_call(9, value, 2)
  True
}

test remainder26_time_before_vote_negative_window_construction() {
  let value = remainder_mutant(1, 9, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(1, 9, value) }
}

test remainder26_time_before_vote_negative_window_transition_rejects() fail {
  let value = remainder_mutant(1, 9, False)
  expect remainder_call(1, value, 0)
  True
}

test remainder26_time_before_vote_negative_window_governor_spend_rejects() fail {
  let value = remainder_mutant(1, 9, False)
  expect remainder_call(1, value, 1)
  True
}

test remainder26_time_before_vote_negative_window_receipt_policy_rejects() fail {
  let value = remainder_mutant(1, 9, False)
  expect remainder_call(1, value, 2)
  True
}

test remainder26_time_before_cancel_negative_window_construction() {
  let value = remainder_mutant(4, 9, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(4, 9, value) }
}

test remainder26_time_before_cancel_negative_window_transition_rejects() fail {
  let value = remainder_mutant(4, 9, False)
  expect remainder_call(4, value, 0)
  True
}

test remainder26_time_before_cancel_negative_window_governor_spend_rejects() fail {
  let value = remainder_mutant(4, 9, False)
  expect remainder_call(4, value, 1)
  True
}

test remainder26_time_before_cancel_negative_window_proposal_policy_rejects() fail {
  let value = remainder_mutant(4, 9, False)
  expect remainder_call(4, value, 2)
  True
}

test remainder26_time_before_cancel_negative_window_receipt_policy_rejects() fail {
  let value = remainder_mutant(4, 9, False)
  expect remainder_call(4, value, 3)
  True
}

test remainder26_time_before_finalize_passed_before_deadline_construction() {
  let value = remainder_mutant(2, 10, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(2, 10, value) }
}

test remainder26_time_before_finalize_passed_before_deadline_transition_rejects() fail {
  let value = remainder_mutant(2, 10, False)
  expect remainder_call(2, value, 0)
  True
}

test remainder26_time_before_finalize_passed_before_deadline_governor_spend_rejects() fail {
  let value = remainder_mutant(2, 10, False)
  expect remainder_call(2, value, 1)
  True
}

test remainder26_time_before_finalize_rejected_before_deadline_construction() {
  let value = remainder_mutant(3, 10, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(3, 10, value) }
}

test remainder26_time_before_finalize_rejected_before_deadline_transition_rejects() fail {
  let value = remainder_mutant(3, 10, False)
  expect remainder_call(3, value, 0)
  True
}

test remainder26_time_before_finalize_rejected_before_deadline_governor_spend_rejects() fail {
  let value = remainder_mutant(3, 10, False)
  expect remainder_call(3, value, 1)
  True
}

test remainder26_time_before_finalize_rejected_before_deadline_proposal_policy_rejects() fail {
  let value = remainder_mutant(3, 10, False)
  expect remainder_call(3, value, 2)
  True
}

test remainder26_time_before_finalize_rejected_before_deadline_receipt_policy_rejects() fail {
  let value = remainder_mutant(3, 10, False)
  expect remainder_call(3, value, 3)
  True
}

test remainder26_time_after_vote_after_deadline_construction() {
  let value = remainder_mutant(1, 11, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(1, 11, value) }
}

test remainder26_time_after_vote_after_deadline_transition_rejects() fail {
  let value = remainder_mutant(1, 11, False)
  expect remainder_call(1, value, 0)
  True
}

test remainder26_time_after_vote_after_deadline_governor_spend_rejects() fail {
  let value = remainder_mutant(1, 11, False)
  expect remainder_call(1, value, 1)
  True
}

test remainder26_time_after_vote_after_deadline_receipt_policy_rejects() fail {
  let value = remainder_mutant(1, 11, False)
  expect remainder_call(1, value, 2)
  True
}

test remainder26_time_after_cancel_after_deadline_construction() {
  let value = remainder_mutant(4, 11, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(4, 11, value) }
}

test remainder26_time_after_cancel_after_deadline_transition_rejects() fail {
  let value = remainder_mutant(4, 11, False)
  expect remainder_call(4, value, 0)
  True
}

test remainder26_time_after_cancel_after_deadline_governor_spend_rejects() fail {
  let value = remainder_mutant(4, 11, False)
  expect remainder_call(4, value, 1)
  True
}

test remainder26_time_after_cancel_after_deadline_proposal_policy_rejects() fail {
  let value = remainder_mutant(4, 11, False)
  expect remainder_call(4, value, 2)
  True
}

test remainder26_time_after_cancel_after_deadline_receipt_policy_rejects() fail {
  let value = remainder_mutant(4, 11, False)
  expect remainder_call(4, value, 3)
  True
}

test remainder26_create_topology_one_over_create_inputs_exact_construction() {
  let value = remainder_mutant(0, 0, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(0, 0, value) }
}

test remainder26_create_topology_one_over_create_inputs_exact_transition_rejects() fail {
  let value = remainder_mutant(0, 0, False)
  expect remainder_call(0, value, 0)
  True
}

test remainder26_create_topology_one_over_create_inputs_exact_authority_spend_rejects() fail {
  let value = remainder_mutant(0, 0, False)
  expect remainder_call(0, value, 1)
  True
}

test remainder26_create_topology_one_over_create_inputs_exact_proposal_policy_rejects() fail {
  let value = remainder_mutant(0, 0, False)
  expect remainder_call(0, value, 2)
  True
}

test remainder26_create_topology_one_over_create_inputs_global_construction() {
  let value = remainder_mutant(0, 1, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(0, 1, value) }
}

test remainder26_create_topology_one_over_create_inputs_global_transition_rejects() fail {
  let value = remainder_mutant(0, 1, False)
  expect remainder_call(0, value, 0)
  True
}

test remainder26_create_topology_one_over_create_inputs_global_authority_spend_rejects() fail {
  let value = remainder_mutant(0, 1, False)
  expect remainder_call(0, value, 1)
  True
}

test remainder26_create_topology_one_over_create_inputs_global_proposal_policy_rejects() fail {
  let value = remainder_mutant(0, 1, False)
  expect remainder_call(0, value, 2)
  True
}

test remainder26_create_topology_one_over_create_inputs_global_resource_at_limit() {
  let value = remainder_mutant(0, 1, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_create_topology_one_over_create_outputs_exact_construction() {
  let value = remainder_mutant(0, 2, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(0, 2, value) }
}

test remainder26_create_topology_one_over_create_outputs_exact_transition_rejects() fail {
  let value = remainder_mutant(0, 2, False)
  expect remainder_call(0, value, 0)
  True
}

test remainder26_create_topology_one_over_create_outputs_exact_authority_spend_rejects() fail {
  let value = remainder_mutant(0, 2, False)
  expect remainder_call(0, value, 1)
  True
}

test remainder26_create_topology_one_over_create_outputs_exact_proposal_policy_rejects() fail {
  let value = remainder_mutant(0, 2, False)
  expect remainder_call(0, value, 2)
  True
}

test remainder26_create_topology_one_over_create_outputs_global_construction() {
  let value = remainder_mutant(0, 3, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(0, 3, value) }
}

test remainder26_create_topology_one_over_create_outputs_global_transition_rejects() fail {
  let value = remainder_mutant(0, 3, False)
  expect remainder_call(0, value, 0)
  True
}

test remainder26_create_topology_one_over_create_outputs_global_authority_spend_rejects() fail {
  let value = remainder_mutant(0, 3, False)
  expect remainder_call(0, value, 1)
  True
}

test remainder26_create_topology_one_over_create_outputs_global_proposal_policy_rejects() fail {
  let value = remainder_mutant(0, 3, False)
  expect remainder_call(0, value, 2)
  True
}

test remainder26_create_topology_one_over_create_outputs_global_resource_at_limit() {
  let value = remainder_mutant(0, 3, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_create_topology_one_over_create_assets_construction() {
  let value = remainder_mutant(0, 4, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(0, 4, value) }
}

test remainder26_create_topology_one_over_create_assets_transition_rejects() fail {
  let value = remainder_mutant(0, 4, False)
  expect remainder_call(0, value, 0)
  True
}

test remainder26_create_topology_one_over_create_assets_authority_spend_rejects() fail {
  let value = remainder_mutant(0, 4, False)
  expect remainder_call(0, value, 1)
  True
}

test remainder26_create_topology_one_over_create_assets_proposal_policy_rejects() fail {
  let value = remainder_mutant(0, 4, False)
  expect remainder_call(0, value, 2)
  True
}

test remainder26_create_topology_one_over_create_assets_resource_at_limit() {
  let value = remainder_mutant(0, 4, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_create_topology_one_over_create_datum_bytes_construction() {
  let value = remainder_mutant(0, 5, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(0, 5, value) }
}

test remainder26_create_topology_one_over_create_datum_bytes_transition_rejects() fail {
  let value = remainder_mutant(0, 5, False)
  expect remainder_call(0, value, 0)
  True
}

test remainder26_create_topology_one_over_create_datum_bytes_authority_spend_rejects() fail {
  let value = remainder_mutant(0, 5, False)
  expect remainder_call(0, value, 1)
  True
}

test remainder26_create_topology_one_over_create_datum_bytes_proposal_policy_rejects() fail {
  let value = remainder_mutant(0, 5, False)
  expect remainder_call(0, value, 2)
  True
}

test remainder26_create_topology_one_over_create_datum_bytes_resource_at_limit() {
  let value = remainder_mutant(0, 5, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_create_topology_one_over_create_signers_construction() {
  let value = remainder_mutant(0, 6, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(0, 6, value) }
}

test remainder26_create_topology_one_over_create_signers_transition_rejects() fail {
  let value = remainder_mutant(0, 6, False)
  expect remainder_call(0, value, 0)
  True
}

test remainder26_create_topology_one_over_create_signers_authority_spend_rejects() fail {
  let value = remainder_mutant(0, 6, False)
  expect remainder_call(0, value, 1)
  True
}

test remainder26_create_topology_one_over_create_signers_proposal_policy_rejects() fail {
  let value = remainder_mutant(0, 6, False)
  expect remainder_call(0, value, 2)
  True
}

test remainder26_create_topology_one_over_create_signers_resource_at_limit() {
  let value = remainder_mutant(0, 6, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_create_datum_mutation_create_datum_version_construction() {
  let value = remainder_mutant(0, 7, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(0, 7, value) }
}

test remainder26_create_datum_mutation_create_datum_version_transition_rejects() fail {
  let value = remainder_mutant(0, 7, False)
  expect remainder_call(0, value, 0)
  True
}

test remainder26_create_datum_mutation_create_datum_version_authority_spend_rejects() fail {
  let value = remainder_mutant(0, 7, False)
  expect remainder_call(0, value, 1)
  True
}

test remainder26_create_datum_mutation_create_datum_version_proposal_policy_rejects() fail {
  let value = remainder_mutant(0, 7, False)
  expect remainder_call(0, value, 2)
  True
}

test remainder26_create_timing_boundary_create_create_at_deadline_construction() {
  let value = remainder_mutant(0, 12, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(0, 12, value) }
}

test remainder26_create_timing_boundary_create_create_at_deadline_transition_rejects() fail {
  let value = remainder_mutant(0, 12, False)
  expect remainder_call(0, value, 0)
  True
}

test remainder26_create_timing_boundary_create_create_at_deadline_authority_spend_rejects() fail {
  let value = remainder_mutant(0, 12, False)
  expect remainder_call(0, value, 1)
  True
}

test remainder26_create_timing_boundary_create_create_at_deadline_proposal_policy_rejects() fail {
  let value = remainder_mutant(0, 12, False)
  expect remainder_call(0, value, 2)
  True
}

test remainder26_vote_topology_one_over_vote_inputs_exact_construction() {
  let value = remainder_mutant(1, 0, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(1, 0, value) }
}

test remainder26_vote_topology_one_over_vote_inputs_exact_transition_rejects() fail {
  let value = remainder_mutant(1, 0, False)
  expect remainder_call(1, value, 0)
  True
}

test remainder26_vote_topology_one_over_vote_inputs_exact_governor_spend_rejects() fail {
  let value = remainder_mutant(1, 0, False)
  expect remainder_call(1, value, 1)
  True
}

test remainder26_vote_topology_one_over_vote_inputs_exact_receipt_policy_rejects() fail {
  let value = remainder_mutant(1, 0, False)
  expect remainder_call(1, value, 2)
  True
}

test remainder26_vote_topology_one_over_vote_inputs_global_construction() {
  let value = remainder_mutant(1, 1, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(1, 1, value) }
}

test remainder26_vote_topology_one_over_vote_inputs_global_transition_rejects() fail {
  let value = remainder_mutant(1, 1, False)
  expect remainder_call(1, value, 0)
  True
}

test remainder26_vote_topology_one_over_vote_inputs_global_governor_spend_rejects() fail {
  let value = remainder_mutant(1, 1, False)
  expect remainder_call(1, value, 1)
  True
}

test remainder26_vote_topology_one_over_vote_inputs_global_receipt_policy_rejects() fail {
  let value = remainder_mutant(1, 1, False)
  expect remainder_call(1, value, 2)
  True
}

test remainder26_vote_topology_one_over_vote_inputs_global_resource_at_limit() {
  let value = remainder_mutant(1, 1, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_vote_topology_one_over_vote_outputs_exact_construction() {
  let value = remainder_mutant(1, 2, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(1, 2, value) }
}

test remainder26_vote_topology_one_over_vote_outputs_exact_transition_rejects() fail {
  let value = remainder_mutant(1, 2, False)
  expect remainder_call(1, value, 0)
  True
}

test remainder26_vote_topology_one_over_vote_outputs_exact_governor_spend_rejects() fail {
  let value = remainder_mutant(1, 2, False)
  expect remainder_call(1, value, 1)
  True
}

test remainder26_vote_topology_one_over_vote_outputs_exact_receipt_policy_rejects() fail {
  let value = remainder_mutant(1, 2, False)
  expect remainder_call(1, value, 2)
  True
}

test remainder26_vote_topology_one_over_vote_outputs_global_construction() {
  let value = remainder_mutant(1, 3, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(1, 3, value) }
}

test remainder26_vote_topology_one_over_vote_outputs_global_transition_rejects() fail {
  let value = remainder_mutant(1, 3, False)
  expect remainder_call(1, value, 0)
  True
}

test remainder26_vote_topology_one_over_vote_outputs_global_governor_spend_rejects() fail {
  let value = remainder_mutant(1, 3, False)
  expect remainder_call(1, value, 1)
  True
}

test remainder26_vote_topology_one_over_vote_outputs_global_receipt_policy_rejects() fail {
  let value = remainder_mutant(1, 3, False)
  expect remainder_call(1, value, 2)
  True
}

test remainder26_vote_topology_one_over_vote_outputs_global_resource_at_limit() {
  let value = remainder_mutant(1, 3, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_vote_topology_one_over_vote_assets_construction() {
  let value = remainder_mutant(1, 4, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(1, 4, value) }
}

test remainder26_vote_topology_one_over_vote_assets_transition_rejects() fail {
  let value = remainder_mutant(1, 4, False)
  expect remainder_call(1, value, 0)
  True
}

test remainder26_vote_topology_one_over_vote_assets_governor_spend_rejects() fail {
  let value = remainder_mutant(1, 4, False)
  expect remainder_call(1, value, 1)
  True
}

test remainder26_vote_topology_one_over_vote_assets_receipt_policy_rejects() fail {
  let value = remainder_mutant(1, 4, False)
  expect remainder_call(1, value, 2)
  True
}

test remainder26_vote_topology_one_over_vote_assets_resource_at_limit() {
  let value = remainder_mutant(1, 4, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_vote_topology_one_over_vote_datum_bytes_construction() {
  let value = remainder_mutant(1, 5, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(1, 5, value) }
}

test remainder26_vote_topology_one_over_vote_datum_bytes_transition_rejects() fail {
  let value = remainder_mutant(1, 5, False)
  expect remainder_call(1, value, 0)
  True
}

test remainder26_vote_topology_one_over_vote_datum_bytes_governor_spend_rejects() fail {
  let value = remainder_mutant(1, 5, False)
  expect remainder_call(1, value, 1)
  True
}

test remainder26_vote_topology_one_over_vote_datum_bytes_receipt_policy_rejects() fail {
  let value = remainder_mutant(1, 5, False)
  expect remainder_call(1, value, 2)
  True
}

test remainder26_vote_topology_one_over_vote_datum_bytes_resource_at_limit() {
  let value = remainder_mutant(1, 5, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_vote_topology_one_over_vote_signers_construction() {
  let value = remainder_mutant(1, 6, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(1, 6, value) }
}

test remainder26_vote_topology_one_over_vote_signers_transition_rejects() fail {
  let value = remainder_mutant(1, 6, False)
  expect remainder_call(1, value, 0)
  True
}

test remainder26_vote_topology_one_over_vote_signers_governor_spend_rejects() fail {
  let value = remainder_mutant(1, 6, False)
  expect remainder_call(1, value, 1)
  True
}

test remainder26_vote_topology_one_over_vote_signers_receipt_policy_rejects() fail {
  let value = remainder_mutant(1, 6, False)
  expect remainder_call(1, value, 2)
  True
}

test remainder26_vote_topology_one_over_vote_signers_resource_at_limit() {
  let value = remainder_mutant(1, 6, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_vote_datum_mutation_vote_datum_version_construction() {
  let value = remainder_mutant(1, 7, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(1, 7, value) }
}

test remainder26_vote_datum_mutation_vote_datum_version_transition_rejects() fail {
  let value = remainder_mutant(1, 7, False)
  expect remainder_call(1, value, 0)
  True
}

test remainder26_vote_datum_mutation_vote_datum_version_governor_spend_rejects() fail {
  let value = remainder_mutant(1, 7, False)
  expect remainder_call(1, value, 1)
  True
}

test remainder26_vote_datum_mutation_vote_datum_version_receipt_policy_rejects() fail {
  let value = remainder_mutant(1, 7, False)
  expect remainder_call(1, value, 2)
  True
}

test remainder26_finalize_passed_destination_finalize_passed_destination_construction() {
  let value = remainder_mutant(2, 8, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(2, 8, value) }
}

test remainder26_finalize_passed_destination_finalize_passed_destination_transition_rejects() fail {
  let value = remainder_mutant(2, 8, False)
  expect remainder_call(2, value, 0)
  True
}

test remainder26_finalize_passed_destination_finalize_passed_destination_governor_spend_rejects() fail {
  let value = remainder_mutant(2, 8, False)
  expect remainder_call(2, value, 1)
  True
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_inputs_exact_construction() {
  let value = remainder_mutant(2, 0, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(2, 0, value) }
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_inputs_exact_transition_rejects() fail {
  let value = remainder_mutant(2, 0, False)
  expect remainder_call(2, value, 0)
  True
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_inputs_exact_governor_spend_rejects() fail {
  let value = remainder_mutant(2, 0, False)
  expect remainder_call(2, value, 1)
  True
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_inputs_global_construction() {
  let value = remainder_mutant(2, 1, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(2, 1, value) }
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_inputs_global_transition_rejects() fail {
  let value = remainder_mutant(2, 1, False)
  expect remainder_call(2, value, 0)
  True
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_inputs_global_governor_spend_rejects() fail {
  let value = remainder_mutant(2, 1, False)
  expect remainder_call(2, value, 1)
  True
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_inputs_global_resource_at_limit() {
  let value = remainder_mutant(2, 1, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_outputs_exact_construction() {
  let value = remainder_mutant(2, 2, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(2, 2, value) }
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_outputs_exact_transition_rejects() fail {
  let value = remainder_mutant(2, 2, False)
  expect remainder_call(2, value, 0)
  True
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_outputs_exact_governor_spend_rejects() fail {
  let value = remainder_mutant(2, 2, False)
  expect remainder_call(2, value, 1)
  True
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_outputs_global_construction() {
  let value = remainder_mutant(2, 3, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(2, 3, value) }
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_outputs_global_transition_rejects() fail {
  let value = remainder_mutant(2, 3, False)
  expect remainder_call(2, value, 0)
  True
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_outputs_global_governor_spend_rejects() fail {
  let value = remainder_mutant(2, 3, False)
  expect remainder_call(2, value, 1)
  True
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_outputs_global_resource_at_limit() {
  let value = remainder_mutant(2, 3, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_assets_construction() {
  let value = remainder_mutant(2, 4, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(2, 4, value) }
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_assets_transition_rejects() fail {
  let value = remainder_mutant(2, 4, False)
  expect remainder_call(2, value, 0)
  True
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_assets_governor_spend_rejects() fail {
  let value = remainder_mutant(2, 4, False)
  expect remainder_call(2, value, 1)
  True
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_assets_resource_at_limit() {
  let value = remainder_mutant(2, 4, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_datum_bytes_construction() {
  let value = remainder_mutant(2, 5, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(2, 5, value) }
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_datum_bytes_transition_rejects() fail {
  let value = remainder_mutant(2, 5, False)
  expect remainder_call(2, value, 0)
  True
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_datum_bytes_governor_spend_rejects() fail {
  let value = remainder_mutant(2, 5, False)
  expect remainder_call(2, value, 1)
  True
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_datum_bytes_resource_at_limit() {
  let value = remainder_mutant(2, 5, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_signers_construction() {
  let value = remainder_mutant(2, 6, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(2, 6, value) }
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_signers_transition_rejects() fail {
  let value = remainder_mutant(2, 6, False)
  expect remainder_call(2, value, 0)
  True
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_signers_governor_spend_rejects() fail {
  let value = remainder_mutant(2, 6, False)
  expect remainder_call(2, value, 1)
  True
}

test remainder26_finalize_passed_topology_one_over_finalize_passed_signers_resource_at_limit() {
  let value = remainder_mutant(2, 6, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_finalize_passed_datum_mutation_finalize_passed_datum_version_construction() {
  let value = remainder_mutant(2, 7, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(2, 7, value) }
}

test remainder26_finalize_passed_datum_mutation_finalize_passed_datum_version_transition_rejects() fail {
  let value = remainder_mutant(2, 7, False)
  expect remainder_call(2, value, 0)
  True
}

test remainder26_finalize_passed_datum_mutation_finalize_passed_datum_version_governor_spend_rejects() fail {
  let value = remainder_mutant(2, 7, False)
  expect remainder_call(2, value, 1)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_inputs_exact_construction() {
  let value = remainder_mutant(3, 0, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(3, 0, value) }
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_inputs_exact_transition_rejects() fail {
  let value = remainder_mutant(3, 0, False)
  expect remainder_call(3, value, 0)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_inputs_exact_governor_spend_rejects() fail {
  let value = remainder_mutant(3, 0, False)
  expect remainder_call(3, value, 1)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_inputs_exact_proposal_policy_rejects() fail {
  let value = remainder_mutant(3, 0, False)
  expect remainder_call(3, value, 2)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_inputs_exact_receipt_policy_rejects() fail {
  let value = remainder_mutant(3, 0, False)
  expect remainder_call(3, value, 3)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_inputs_global_construction() {
  let value = remainder_mutant(3, 1, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(3, 1, value) }
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_inputs_global_transition_rejects() fail {
  let value = remainder_mutant(3, 1, False)
  expect remainder_call(3, value, 0)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_inputs_global_governor_spend_rejects() fail {
  let value = remainder_mutant(3, 1, False)
  expect remainder_call(3, value, 1)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_inputs_global_proposal_policy_rejects() fail {
  let value = remainder_mutant(3, 1, False)
  expect remainder_call(3, value, 2)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_inputs_global_receipt_policy_rejects() fail {
  let value = remainder_mutant(3, 1, False)
  expect remainder_call(3, value, 3)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_inputs_global_resource_at_limit() {
  let value = remainder_mutant(3, 1, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_outputs_exact_construction() {
  let value = remainder_mutant(3, 2, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(3, 2, value) }
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_outputs_exact_transition_rejects() fail {
  let value = remainder_mutant(3, 2, False)
  expect remainder_call(3, value, 0)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_outputs_exact_governor_spend_rejects() fail {
  let value = remainder_mutant(3, 2, False)
  expect remainder_call(3, value, 1)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_outputs_exact_proposal_policy_rejects() fail {
  let value = remainder_mutant(3, 2, False)
  expect remainder_call(3, value, 2)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_outputs_exact_receipt_policy_rejects() fail {
  let value = remainder_mutant(3, 2, False)
  expect remainder_call(3, value, 3)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_outputs_global_construction() {
  let value = remainder_mutant(3, 3, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(3, 3, value) }
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_outputs_global_transition_rejects() fail {
  let value = remainder_mutant(3, 3, False)
  expect remainder_call(3, value, 0)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_outputs_global_governor_spend_rejects() fail {
  let value = remainder_mutant(3, 3, False)
  expect remainder_call(3, value, 1)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_outputs_global_proposal_policy_rejects() fail {
  let value = remainder_mutant(3, 3, False)
  expect remainder_call(3, value, 2)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_outputs_global_receipt_policy_rejects() fail {
  let value = remainder_mutant(3, 3, False)
  expect remainder_call(3, value, 3)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_outputs_global_resource_at_limit() {
  let value = remainder_mutant(3, 3, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_assets_construction() {
  let value = remainder_mutant(3, 4, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(3, 4, value) }
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_assets_transition_rejects() fail {
  let value = remainder_mutant(3, 4, False)
  expect remainder_call(3, value, 0)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_assets_governor_spend_rejects() fail {
  let value = remainder_mutant(3, 4, False)
  expect remainder_call(3, value, 1)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_assets_proposal_policy_rejects() fail {
  let value = remainder_mutant(3, 4, False)
  expect remainder_call(3, value, 2)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_assets_receipt_policy_rejects() fail {
  let value = remainder_mutant(3, 4, False)
  expect remainder_call(3, value, 3)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_assets_resource_at_limit() {
  let value = remainder_mutant(3, 4, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_datum_bytes_construction() {
  let value = remainder_mutant(3, 5, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(3, 5, value) }
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_datum_bytes_transition_rejects() fail {
  let value = remainder_mutant(3, 5, False)
  expect remainder_call(3, value, 0)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_datum_bytes_governor_spend_rejects() fail {
  let value = remainder_mutant(3, 5, False)
  expect remainder_call(3, value, 1)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_datum_bytes_proposal_policy_rejects() fail {
  let value = remainder_mutant(3, 5, False)
  expect remainder_call(3, value, 2)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_datum_bytes_receipt_policy_rejects() fail {
  let value = remainder_mutant(3, 5, False)
  expect remainder_call(3, value, 3)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_datum_bytes_resource_at_limit() {
  let value = remainder_mutant(3, 5, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_signers_construction() {
  let value = remainder_mutant(3, 6, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(3, 6, value) }
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_signers_transition_rejects() fail {
  let value = remainder_mutant(3, 6, False)
  expect remainder_call(3, value, 0)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_signers_governor_spend_rejects() fail {
  let value = remainder_mutant(3, 6, False)
  expect remainder_call(3, value, 1)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_signers_proposal_policy_rejects() fail {
  let value = remainder_mutant(3, 6, False)
  expect remainder_call(3, value, 2)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_signers_receipt_policy_rejects() fail {
  let value = remainder_mutant(3, 6, False)
  expect remainder_call(3, value, 3)
  True
}

test remainder26_finalize_rejected_topology_one_over_finalize_rejected_signers_resource_at_limit() {
  let value = remainder_mutant(3, 6, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_finalize_rejected_datum_mutation_finalize_rejected_datum_version_construction() {
  let value = remainder_mutant(3, 7, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(3, 7, value) }
}

test remainder26_finalize_rejected_datum_mutation_finalize_rejected_datum_version_transition_rejects() fail {
  let value = remainder_mutant(3, 7, False)
  expect remainder_call(3, value, 0)
  True
}

test remainder26_finalize_rejected_datum_mutation_finalize_rejected_datum_version_governor_spend_rejects() fail {
  let value = remainder_mutant(3, 7, False)
  expect remainder_call(3, value, 1)
  True
}

test remainder26_finalize_rejected_datum_mutation_finalize_rejected_datum_version_proposal_policy_rejects() fail {
  let value = remainder_mutant(3, 7, False)
  expect remainder_call(3, value, 2)
  True
}

test remainder26_finalize_rejected_datum_mutation_finalize_rejected_datum_version_receipt_policy_rejects() fail {
  let value = remainder_mutant(3, 7, False)
  expect remainder_call(3, value, 3)
  True
}

test remainder26_finalize_rejected_timing_boundary_finalize_rejected_before_deadline_construction() {
  let value = remainder_mutant(3, 10, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(3, 10, value) }
}

test remainder26_finalize_rejected_timing_boundary_finalize_rejected_before_deadline_transition_rejects() fail {
  let value = remainder_mutant(3, 10, False)
  expect remainder_call(3, value, 0)
  True
}

test remainder26_finalize_rejected_timing_boundary_finalize_rejected_before_deadline_governor_spend_rejects() fail {
  let value = remainder_mutant(3, 10, False)
  expect remainder_call(3, value, 1)
  True
}

test remainder26_finalize_rejected_timing_boundary_finalize_rejected_before_deadline_proposal_policy_rejects() fail {
  let value = remainder_mutant(3, 10, False)
  expect remainder_call(3, value, 2)
  True
}

test remainder26_finalize_rejected_timing_boundary_finalize_rejected_before_deadline_receipt_policy_rejects() fail {
  let value = remainder_mutant(3, 10, False)
  expect remainder_call(3, value, 3)
  True
}

test remainder26_cancel_topology_one_over_cancel_inputs_exact_construction() {
  let value = remainder_mutant(4, 0, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(4, 0, value) }
}

test remainder26_cancel_topology_one_over_cancel_inputs_exact_transition_rejects() fail {
  let value = remainder_mutant(4, 0, False)
  expect remainder_call(4, value, 0)
  True
}

test remainder26_cancel_topology_one_over_cancel_inputs_exact_governor_spend_rejects() fail {
  let value = remainder_mutant(4, 0, False)
  expect remainder_call(4, value, 1)
  True
}

test remainder26_cancel_topology_one_over_cancel_inputs_exact_proposal_policy_rejects() fail {
  let value = remainder_mutant(4, 0, False)
  expect remainder_call(4, value, 2)
  True
}

test remainder26_cancel_topology_one_over_cancel_inputs_exact_receipt_policy_rejects() fail {
  let value = remainder_mutant(4, 0, False)
  expect remainder_call(4, value, 3)
  True
}

test remainder26_cancel_topology_one_over_cancel_inputs_global_construction() {
  let value = remainder_mutant(4, 1, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(4, 1, value) }
}

test remainder26_cancel_topology_one_over_cancel_inputs_global_transition_rejects() fail {
  let value = remainder_mutant(4, 1, False)
  expect remainder_call(4, value, 0)
  True
}

test remainder26_cancel_topology_one_over_cancel_inputs_global_governor_spend_rejects() fail {
  let value = remainder_mutant(4, 1, False)
  expect remainder_call(4, value, 1)
  True
}

test remainder26_cancel_topology_one_over_cancel_inputs_global_proposal_policy_rejects() fail {
  let value = remainder_mutant(4, 1, False)
  expect remainder_call(4, value, 2)
  True
}

test remainder26_cancel_topology_one_over_cancel_inputs_global_receipt_policy_rejects() fail {
  let value = remainder_mutant(4, 1, False)
  expect remainder_call(4, value, 3)
  True
}

test remainder26_cancel_topology_one_over_cancel_inputs_global_resource_at_limit() {
  let value = remainder_mutant(4, 1, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_cancel_topology_one_over_cancel_outputs_exact_construction() {
  let value = remainder_mutant(4, 2, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(4, 2, value) }
}

test remainder26_cancel_topology_one_over_cancel_outputs_exact_transition_rejects() fail {
  let value = remainder_mutant(4, 2, False)
  expect remainder_call(4, value, 0)
  True
}

test remainder26_cancel_topology_one_over_cancel_outputs_exact_governor_spend_rejects() fail {
  let value = remainder_mutant(4, 2, False)
  expect remainder_call(4, value, 1)
  True
}

test remainder26_cancel_topology_one_over_cancel_outputs_exact_proposal_policy_rejects() fail {
  let value = remainder_mutant(4, 2, False)
  expect remainder_call(4, value, 2)
  True
}

test remainder26_cancel_topology_one_over_cancel_outputs_exact_receipt_policy_rejects() fail {
  let value = remainder_mutant(4, 2, False)
  expect remainder_call(4, value, 3)
  True
}

test remainder26_cancel_topology_one_over_cancel_outputs_global_construction() {
  let value = remainder_mutant(4, 3, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(4, 3, value) }
}

test remainder26_cancel_topology_one_over_cancel_outputs_global_transition_rejects() fail {
  let value = remainder_mutant(4, 3, False)
  expect remainder_call(4, value, 0)
  True
}

test remainder26_cancel_topology_one_over_cancel_outputs_global_governor_spend_rejects() fail {
  let value = remainder_mutant(4, 3, False)
  expect remainder_call(4, value, 1)
  True
}

test remainder26_cancel_topology_one_over_cancel_outputs_global_proposal_policy_rejects() fail {
  let value = remainder_mutant(4, 3, False)
  expect remainder_call(4, value, 2)
  True
}

test remainder26_cancel_topology_one_over_cancel_outputs_global_receipt_policy_rejects() fail {
  let value = remainder_mutant(4, 3, False)
  expect remainder_call(4, value, 3)
  True
}

test remainder26_cancel_topology_one_over_cancel_outputs_global_resource_at_limit() {
  let value = remainder_mutant(4, 3, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_cancel_topology_one_over_cancel_assets_construction() {
  let value = remainder_mutant(4, 4, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(4, 4, value) }
}

test remainder26_cancel_topology_one_over_cancel_assets_transition_rejects() fail {
  let value = remainder_mutant(4, 4, False)
  expect remainder_call(4, value, 0)
  True
}

test remainder26_cancel_topology_one_over_cancel_assets_governor_spend_rejects() fail {
  let value = remainder_mutant(4, 4, False)
  expect remainder_call(4, value, 1)
  True
}

test remainder26_cancel_topology_one_over_cancel_assets_proposal_policy_rejects() fail {
  let value = remainder_mutant(4, 4, False)
  expect remainder_call(4, value, 2)
  True
}

test remainder26_cancel_topology_one_over_cancel_assets_receipt_policy_rejects() fail {
  let value = remainder_mutant(4, 4, False)
  expect remainder_call(4, value, 3)
  True
}

test remainder26_cancel_topology_one_over_cancel_assets_resource_at_limit() {
  let value = remainder_mutant(4, 4, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_cancel_topology_one_over_cancel_datum_bytes_construction() {
  let value = remainder_mutant(4, 5, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(4, 5, value) }
}

test remainder26_cancel_topology_one_over_cancel_datum_bytes_transition_rejects() fail {
  let value = remainder_mutant(4, 5, False)
  expect remainder_call(4, value, 0)
  True
}

test remainder26_cancel_topology_one_over_cancel_datum_bytes_governor_spend_rejects() fail {
  let value = remainder_mutant(4, 5, False)
  expect remainder_call(4, value, 1)
  True
}

test remainder26_cancel_topology_one_over_cancel_datum_bytes_proposal_policy_rejects() fail {
  let value = remainder_mutant(4, 5, False)
  expect remainder_call(4, value, 2)
  True
}

test remainder26_cancel_topology_one_over_cancel_datum_bytes_receipt_policy_rejects() fail {
  let value = remainder_mutant(4, 5, False)
  expect remainder_call(4, value, 3)
  True
}

test remainder26_cancel_topology_one_over_cancel_datum_bytes_resource_at_limit() {
  let value = remainder_mutant(4, 5, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_cancel_topology_one_over_cancel_signers_construction() {
  let value = remainder_mutant(4, 6, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(4, 6, value) }
}

test remainder26_cancel_topology_one_over_cancel_signers_transition_rejects() fail {
  let value = remainder_mutant(4, 6, False)
  expect remainder_call(4, value, 0)
  True
}

test remainder26_cancel_topology_one_over_cancel_signers_governor_spend_rejects() fail {
  let value = remainder_mutant(4, 6, False)
  expect remainder_call(4, value, 1)
  True
}

test remainder26_cancel_topology_one_over_cancel_signers_proposal_policy_rejects() fail {
  let value = remainder_mutant(4, 6, False)
  expect remainder_call(4, value, 2)
  True
}

test remainder26_cancel_topology_one_over_cancel_signers_receipt_policy_rejects() fail {
  let value = remainder_mutant(4, 6, False)
  expect remainder_call(4, value, 3)
  True
}

test remainder26_cancel_topology_one_over_cancel_signers_resource_at_limit() {
  let value = remainder_mutant(4, 6, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_cancel_datum_mutation_cancel_datum_version_construction() {
  let value = remainder_mutant(4, 7, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(4, 7, value) }
}

test remainder26_cancel_datum_mutation_cancel_datum_version_transition_rejects() fail {
  let value = remainder_mutant(4, 7, False)
  expect remainder_call(4, value, 0)
  True
}

test remainder26_cancel_datum_mutation_cancel_datum_version_governor_spend_rejects() fail {
  let value = remainder_mutant(4, 7, False)
  expect remainder_call(4, value, 1)
  True
}

test remainder26_cancel_datum_mutation_cancel_datum_version_proposal_policy_rejects() fail {
  let value = remainder_mutant(4, 7, False)
  expect remainder_call(4, value, 2)
  True
}

test remainder26_cancel_datum_mutation_cancel_datum_version_receipt_policy_rejects() fail {
  let value = remainder_mutant(4, 7, False)
  expect remainder_call(4, value, 3)
  True
}

test remainder26_queue_topology_one_over_queue_inputs_exact_construction() {
  let value = remainder_mutant(5, 0, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(5, 0, value) }
}

test remainder26_queue_topology_one_over_queue_inputs_exact_transition_rejects() fail {
  let value = remainder_mutant(5, 0, False)
  expect remainder_call(5, value, 0)
  True
}

test remainder26_queue_topology_one_over_queue_inputs_exact_authority_spend_rejects() fail {
  let value = remainder_mutant(5, 0, False)
  expect remainder_call(5, value, 1)
  True
}

test remainder26_queue_topology_one_over_queue_inputs_exact_governor_spend_rejects() fail {
  let value = remainder_mutant(5, 0, False)
  expect remainder_call(5, value, 2)
  True
}

test remainder26_queue_topology_one_over_queue_inputs_exact_proposal_policy_rejects() fail {
  let value = remainder_mutant(5, 0, False)
  expect remainder_call(5, value, 3)
  True
}

test remainder26_queue_topology_one_over_queue_inputs_exact_receipt_policy_rejects() fail {
  let value = remainder_mutant(5, 0, False)
  expect remainder_call(5, value, 4)
  True
}

test remainder26_queue_topology_one_over_queue_inputs_exact_intent_policy_rejects() fail {
  let value = remainder_mutant(5, 0, False)
  expect remainder_call(5, value, 5)
  True
}

test remainder26_queue_topology_one_over_queue_inputs_global_construction() {
  let value = remainder_mutant(5, 1, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(5, 1, value) }
}

test remainder26_queue_topology_one_over_queue_inputs_global_transition_rejects() fail {
  let value = remainder_mutant(5, 1, False)
  expect remainder_call(5, value, 0)
  True
}

test remainder26_queue_topology_one_over_queue_inputs_global_authority_spend_rejects() fail {
  let value = remainder_mutant(5, 1, False)
  expect remainder_call(5, value, 1)
  True
}

test remainder26_queue_topology_one_over_queue_inputs_global_governor_spend_rejects() fail {
  let value = remainder_mutant(5, 1, False)
  expect remainder_call(5, value, 2)
  True
}

test remainder26_queue_topology_one_over_queue_inputs_global_proposal_policy_rejects() fail {
  let value = remainder_mutant(5, 1, False)
  expect remainder_call(5, value, 3)
  True
}

test remainder26_queue_topology_one_over_queue_inputs_global_receipt_policy_rejects() fail {
  let value = remainder_mutant(5, 1, False)
  expect remainder_call(5, value, 4)
  True
}

test remainder26_queue_topology_one_over_queue_inputs_global_intent_policy_rejects() fail {
  let value = remainder_mutant(5, 1, False)
  expect remainder_call(5, value, 5)
  True
}

test remainder26_queue_topology_one_over_queue_inputs_global_resource_at_limit() {
  let value = remainder_mutant(5, 1, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_queue_topology_one_over_queue_outputs_exact_construction() {
  let value = remainder_mutant(5, 2, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(5, 2, value) }
}

test remainder26_queue_topology_one_over_queue_outputs_exact_transition_rejects() fail {
  let value = remainder_mutant(5, 2, False)
  expect remainder_call(5, value, 0)
  True
}

test remainder26_queue_topology_one_over_queue_outputs_exact_authority_spend_rejects() fail {
  let value = remainder_mutant(5, 2, False)
  expect remainder_call(5, value, 1)
  True
}

test remainder26_queue_topology_one_over_queue_outputs_exact_governor_spend_rejects() fail {
  let value = remainder_mutant(5, 2, False)
  expect remainder_call(5, value, 2)
  True
}

test remainder26_queue_topology_one_over_queue_outputs_exact_proposal_policy_rejects() fail {
  let value = remainder_mutant(5, 2, False)
  expect remainder_call(5, value, 3)
  True
}

test remainder26_queue_topology_one_over_queue_outputs_exact_receipt_policy_rejects() fail {
  let value = remainder_mutant(5, 2, False)
  expect remainder_call(5, value, 4)
  True
}

test remainder26_queue_topology_one_over_queue_outputs_exact_intent_policy_rejects() fail {
  let value = remainder_mutant(5, 2, False)
  expect remainder_call(5, value, 5)
  True
}

test remainder26_queue_topology_one_over_queue_outputs_global_construction() {
  let value = remainder_mutant(5, 3, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(5, 3, value) }
}

test remainder26_queue_topology_one_over_queue_outputs_global_transition_rejects() fail {
  let value = remainder_mutant(5, 3, False)
  expect remainder_call(5, value, 0)
  True
}

test remainder26_queue_topology_one_over_queue_outputs_global_authority_spend_rejects() fail {
  let value = remainder_mutant(5, 3, False)
  expect remainder_call(5, value, 1)
  True
}

test remainder26_queue_topology_one_over_queue_outputs_global_governor_spend_rejects() fail {
  let value = remainder_mutant(5, 3, False)
  expect remainder_call(5, value, 2)
  True
}

test remainder26_queue_topology_one_over_queue_outputs_global_proposal_policy_rejects() fail {
  let value = remainder_mutant(5, 3, False)
  expect remainder_call(5, value, 3)
  True
}

test remainder26_queue_topology_one_over_queue_outputs_global_receipt_policy_rejects() fail {
  let value = remainder_mutant(5, 3, False)
  expect remainder_call(5, value, 4)
  True
}

test remainder26_queue_topology_one_over_queue_outputs_global_intent_policy_rejects() fail {
  let value = remainder_mutant(5, 3, False)
  expect remainder_call(5, value, 5)
  True
}

test remainder26_queue_topology_one_over_queue_outputs_global_resource_at_limit() {
  let value = remainder_mutant(5, 3, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_queue_topology_one_over_queue_assets_construction() {
  let value = remainder_mutant(5, 4, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(5, 4, value) }
}

test remainder26_queue_topology_one_over_queue_assets_transition_rejects() fail {
  let value = remainder_mutant(5, 4, False)
  expect remainder_call(5, value, 0)
  True
}

test remainder26_queue_topology_one_over_queue_assets_authority_spend_rejects() fail {
  let value = remainder_mutant(5, 4, False)
  expect remainder_call(5, value, 1)
  True
}

test remainder26_queue_topology_one_over_queue_assets_governor_spend_rejects() fail {
  let value = remainder_mutant(5, 4, False)
  expect remainder_call(5, value, 2)
  True
}

test remainder26_queue_topology_one_over_queue_assets_proposal_policy_rejects() fail {
  let value = remainder_mutant(5, 4, False)
  expect remainder_call(5, value, 3)
  True
}

test remainder26_queue_topology_one_over_queue_assets_receipt_policy_rejects() fail {
  let value = remainder_mutant(5, 4, False)
  expect remainder_call(5, value, 4)
  True
}

test remainder26_queue_topology_one_over_queue_assets_intent_policy_rejects() fail {
  let value = remainder_mutant(5, 4, False)
  expect remainder_call(5, value, 5)
  True
}

test remainder26_queue_topology_one_over_queue_assets_resource_at_limit() {
  let value = remainder_mutant(5, 4, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_queue_topology_one_over_queue_datum_bytes_construction() {
  let value = remainder_mutant(5, 5, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(5, 5, value) }
}

test remainder26_queue_topology_one_over_queue_datum_bytes_transition_rejects() fail {
  let value = remainder_mutant(5, 5, False)
  expect remainder_call(5, value, 0)
  True
}

test remainder26_queue_topology_one_over_queue_datum_bytes_authority_spend_rejects() fail {
  let value = remainder_mutant(5, 5, False)
  expect remainder_call(5, value, 1)
  True
}

test remainder26_queue_topology_one_over_queue_datum_bytes_governor_spend_rejects() fail {
  let value = remainder_mutant(5, 5, False)
  expect remainder_call(5, value, 2)
  True
}

test remainder26_queue_topology_one_over_queue_datum_bytes_proposal_policy_rejects() fail {
  let value = remainder_mutant(5, 5, False)
  expect remainder_call(5, value, 3)
  True
}

test remainder26_queue_topology_one_over_queue_datum_bytes_receipt_policy_rejects() fail {
  let value = remainder_mutant(5, 5, False)
  expect remainder_call(5, value, 4)
  True
}

test remainder26_queue_topology_one_over_queue_datum_bytes_intent_policy_rejects() fail {
  let value = remainder_mutant(5, 5, False)
  expect remainder_call(5, value, 5)
  True
}

test remainder26_queue_topology_one_over_queue_datum_bytes_resource_at_limit() {
  let value = remainder_mutant(5, 5, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_queue_topology_one_over_queue_signers_construction() {
  let value = remainder_mutant(5, 6, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(5, 6, value) }
}

test remainder26_queue_topology_one_over_queue_signers_transition_rejects() fail {
  let value = remainder_mutant(5, 6, False)
  expect remainder_call(5, value, 0)
  True
}

test remainder26_queue_topology_one_over_queue_signers_authority_spend_rejects() fail {
  let value = remainder_mutant(5, 6, False)
  expect remainder_call(5, value, 1)
  True
}

test remainder26_queue_topology_one_over_queue_signers_governor_spend_rejects() fail {
  let value = remainder_mutant(5, 6, False)
  expect remainder_call(5, value, 2)
  True
}

test remainder26_queue_topology_one_over_queue_signers_proposal_policy_rejects() fail {
  let value = remainder_mutant(5, 6, False)
  expect remainder_call(5, value, 3)
  True
}

test remainder26_queue_topology_one_over_queue_signers_receipt_policy_rejects() fail {
  let value = remainder_mutant(5, 6, False)
  expect remainder_call(5, value, 4)
  True
}

test remainder26_queue_topology_one_over_queue_signers_intent_policy_rejects() fail {
  let value = remainder_mutant(5, 6, False)
  expect remainder_call(5, value, 5)
  True
}

test remainder26_queue_topology_one_over_queue_signers_resource_at_limit() {
  let value = remainder_mutant(5, 6, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_cancelintent_topology_one_over_cancelintent_inputs_exact_construction() {
  let value = remainder_mutant(6, 0, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(6, 0, value) }
}

test remainder26_cancelintent_topology_one_over_cancelintent_inputs_exact_transition_rejects() fail {
  let value = remainder_mutant(6, 0, False)
  expect remainder_call(6, value, 0)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_inputs_exact_timelock_spend_rejects() fail {
  let value = remainder_mutant(6, 0, False)
  expect remainder_call(6, value, 1)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_inputs_exact_intent_policy_rejects() fail {
  let value = remainder_mutant(6, 0, False)
  expect remainder_call(6, value, 2)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_inputs_global_construction() {
  let value = remainder_mutant(6, 1, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(6, 1, value) }
}

test remainder26_cancelintent_topology_one_over_cancelintent_inputs_global_transition_rejects() fail {
  let value = remainder_mutant(6, 1, False)
  expect remainder_call(6, value, 0)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_inputs_global_timelock_spend_rejects() fail {
  let value = remainder_mutant(6, 1, False)
  expect remainder_call(6, value, 1)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_inputs_global_intent_policy_rejects() fail {
  let value = remainder_mutant(6, 1, False)
  expect remainder_call(6, value, 2)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_inputs_global_resource_at_limit() {
  let value = remainder_mutant(6, 1, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_cancelintent_topology_one_over_cancelintent_outputs_exact_construction() {
  let value = remainder_mutant(6, 2, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(6, 2, value) }
}

test remainder26_cancelintent_topology_one_over_cancelintent_outputs_exact_transition_rejects() fail {
  let value = remainder_mutant(6, 2, False)
  expect remainder_call(6, value, 0)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_outputs_exact_timelock_spend_rejects() fail {
  let value = remainder_mutant(6, 2, False)
  expect remainder_call(6, value, 1)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_outputs_exact_intent_policy_rejects() fail {
  let value = remainder_mutant(6, 2, False)
  expect remainder_call(6, value, 2)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_outputs_global_construction() {
  let value = remainder_mutant(6, 3, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(6, 3, value) }
}

test remainder26_cancelintent_topology_one_over_cancelintent_outputs_global_transition_rejects() fail {
  let value = remainder_mutant(6, 3, False)
  expect remainder_call(6, value, 0)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_outputs_global_timelock_spend_rejects() fail {
  let value = remainder_mutant(6, 3, False)
  expect remainder_call(6, value, 1)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_outputs_global_intent_policy_rejects() fail {
  let value = remainder_mutant(6, 3, False)
  expect remainder_call(6, value, 2)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_outputs_global_resource_at_limit() {
  let value = remainder_mutant(6, 3, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_cancelintent_topology_one_over_cancelintent_assets_construction() {
  let value = remainder_mutant(6, 4, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(6, 4, value) }
}

test remainder26_cancelintent_topology_one_over_cancelintent_assets_transition_rejects() fail {
  let value = remainder_mutant(6, 4, False)
  expect remainder_call(6, value, 0)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_assets_timelock_spend_rejects() fail {
  let value = remainder_mutant(6, 4, False)
  expect remainder_call(6, value, 1)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_assets_intent_policy_rejects() fail {
  let value = remainder_mutant(6, 4, False)
  expect remainder_call(6, value, 2)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_assets_resource_at_limit() {
  let value = remainder_mutant(6, 4, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_cancelintent_topology_one_over_cancelintent_datum_bytes_construction() {
  let value = remainder_mutant(6, 5, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(6, 5, value) }
}

test remainder26_cancelintent_topology_one_over_cancelintent_datum_bytes_transition_rejects() fail {
  let value = remainder_mutant(6, 5, False)
  expect remainder_call(6, value, 0)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_datum_bytes_timelock_spend_rejects() fail {
  let value = remainder_mutant(6, 5, False)
  expect remainder_call(6, value, 1)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_datum_bytes_intent_policy_rejects() fail {
  let value = remainder_mutant(6, 5, False)
  expect remainder_call(6, value, 2)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_datum_bytes_resource_at_limit() {
  let value = remainder_mutant(6, 5, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_cancelintent_topology_one_over_cancelintent_signers_construction() {
  let value = remainder_mutant(6, 6, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(6, 6, value) }
}

test remainder26_cancelintent_topology_one_over_cancelintent_signers_transition_rejects() fail {
  let value = remainder_mutant(6, 6, False)
  expect remainder_call(6, value, 0)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_signers_timelock_spend_rejects() fail {
  let value = remainder_mutant(6, 6, False)
  expect remainder_call(6, value, 1)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_signers_intent_policy_rejects() fail {
  let value = remainder_mutant(6, 6, False)
  expect remainder_call(6, value, 2)
  True
}

test remainder26_cancelintent_topology_one_over_cancelintent_signers_resource_at_limit() {
  let value = remainder_mutant(6, 6, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_cancelintent_datum_mutation_cancelintent_datum_version_construction() {
  let value = remainder_mutant(6, 7, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(6, 7, value) }
}

test remainder26_cancelintent_datum_mutation_cancelintent_datum_version_transition_rejects() fail {
  let value = remainder_mutant(6, 7, False)
  expect remainder_call(6, value, 0)
  True
}

test remainder26_cancelintent_datum_mutation_cancelintent_datum_version_timelock_spend_rejects() fail {
  let value = remainder_mutant(6, 7, False)
  expect remainder_call(6, value, 1)
  True
}

test remainder26_cancelintent_datum_mutation_cancelintent_datum_version_intent_policy_rejects() fail {
  let value = remainder_mutant(6, 7, False)
  expect remainder_call(6, value, 2)
  True
}

test remainder26_cancelintent_timing_boundary_cancelintent_empty_window_construction() {
  let value = remainder_mutant(6, 13, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(6, 13, value) }
}

test remainder26_cancelintent_timing_boundary_cancelintent_empty_window_transition_rejects() fail {
  let value = remainder_mutant(6, 13, False)
  expect remainder_call(6, value, 0)
  True
}

test remainder26_cancelintent_timing_boundary_cancelintent_empty_window_timelock_spend_rejects() fail {
  let value = remainder_mutant(6, 13, False)
  expect remainder_call(6, value, 1)
  True
}

test remainder26_cancelintent_timing_boundary_cancelintent_empty_window_intent_policy_rejects() fail {
  let value = remainder_mutant(6, 13, False)
  expect remainder_call(6, value, 2)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_inputs_exact_construction() {
  let value = remainder_mutant(7, 0, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(7, 0, value) }
}

test remainder26_expireintent_topology_one_over_expireintent_inputs_exact_transition_rejects() fail {
  let value = remainder_mutant(7, 0, False)
  expect remainder_call(7, value, 0)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_inputs_exact_timelock_spend_rejects() fail {
  let value = remainder_mutant(7, 0, False)
  expect remainder_call(7, value, 1)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_inputs_exact_intent_policy_rejects() fail {
  let value = remainder_mutant(7, 0, False)
  expect remainder_call(7, value, 2)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_inputs_global_construction() {
  let value = remainder_mutant(7, 1, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(7, 1, value) }
}

test remainder26_expireintent_topology_one_over_expireintent_inputs_global_transition_rejects() fail {
  let value = remainder_mutant(7, 1, False)
  expect remainder_call(7, value, 0)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_inputs_global_timelock_spend_rejects() fail {
  let value = remainder_mutant(7, 1, False)
  expect remainder_call(7, value, 1)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_inputs_global_intent_policy_rejects() fail {
  let value = remainder_mutant(7, 1, False)
  expect remainder_call(7, value, 2)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_inputs_global_resource_at_limit() {
  let value = remainder_mutant(7, 1, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_expireintent_topology_one_over_expireintent_outputs_exact_construction() {
  let value = remainder_mutant(7, 2, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(7, 2, value) }
}

test remainder26_expireintent_topology_one_over_expireintent_outputs_exact_transition_rejects() fail {
  let value = remainder_mutant(7, 2, False)
  expect remainder_call(7, value, 0)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_outputs_exact_timelock_spend_rejects() fail {
  let value = remainder_mutant(7, 2, False)
  expect remainder_call(7, value, 1)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_outputs_exact_intent_policy_rejects() fail {
  let value = remainder_mutant(7, 2, False)
  expect remainder_call(7, value, 2)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_outputs_global_construction() {
  let value = remainder_mutant(7, 3, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(7, 3, value) }
}

test remainder26_expireintent_topology_one_over_expireintent_outputs_global_transition_rejects() fail {
  let value = remainder_mutant(7, 3, False)
  expect remainder_call(7, value, 0)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_outputs_global_timelock_spend_rejects() fail {
  let value = remainder_mutant(7, 3, False)
  expect remainder_call(7, value, 1)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_outputs_global_intent_policy_rejects() fail {
  let value = remainder_mutant(7, 3, False)
  expect remainder_call(7, value, 2)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_outputs_global_resource_at_limit() {
  let value = remainder_mutant(7, 3, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_expireintent_topology_one_over_expireintent_assets_construction() {
  let value = remainder_mutant(7, 4, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(7, 4, value) }
}

test remainder26_expireintent_topology_one_over_expireintent_assets_transition_rejects() fail {
  let value = remainder_mutant(7, 4, False)
  expect remainder_call(7, value, 0)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_assets_timelock_spend_rejects() fail {
  let value = remainder_mutant(7, 4, False)
  expect remainder_call(7, value, 1)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_assets_intent_policy_rejects() fail {
  let value = remainder_mutant(7, 4, False)
  expect remainder_call(7, value, 2)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_assets_resource_at_limit() {
  let value = remainder_mutant(7, 4, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_expireintent_topology_one_over_expireintent_datum_bytes_construction() {
  let value = remainder_mutant(7, 5, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(7, 5, value) }
}

test remainder26_expireintent_topology_one_over_expireintent_datum_bytes_transition_rejects() fail {
  let value = remainder_mutant(7, 5, False)
  expect remainder_call(7, value, 0)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_datum_bytes_timelock_spend_rejects() fail {
  let value = remainder_mutant(7, 5, False)
  expect remainder_call(7, value, 1)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_datum_bytes_intent_policy_rejects() fail {
  let value = remainder_mutant(7, 5, False)
  expect remainder_call(7, value, 2)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_datum_bytes_resource_at_limit() {
  let value = remainder_mutant(7, 5, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_expireintent_topology_one_over_expireintent_signers_construction() {
  let value = remainder_mutant(7, 6, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(7, 6, value) }
}

test remainder26_expireintent_topology_one_over_expireintent_signers_transition_rejects() fail {
  let value = remainder_mutant(7, 6, False)
  expect remainder_call(7, value, 0)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_signers_timelock_spend_rejects() fail {
  let value = remainder_mutant(7, 6, False)
  expect remainder_call(7, value, 1)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_signers_intent_policy_rejects() fail {
  let value = remainder_mutant(7, 6, False)
  expect remainder_call(7, value, 2)
  True
}

test remainder26_expireintent_topology_one_over_expireintent_signers_resource_at_limit() {
  let value = remainder_mutant(7, 6, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_expireintent_datum_mutation_expireintent_datum_version_construction() {
  let value = remainder_mutant(7, 7, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(7, 7, value) }
}

test remainder26_expireintent_datum_mutation_expireintent_datum_version_transition_rejects() fail {
  let value = remainder_mutant(7, 7, False)
  expect remainder_call(7, value, 0)
  True
}

test remainder26_expireintent_datum_mutation_expireintent_datum_version_timelock_spend_rejects() fail {
  let value = remainder_mutant(7, 7, False)
  expect remainder_call(7, value, 1)
  True
}

test remainder26_expireintent_datum_mutation_expireintent_datum_version_intent_policy_rejects() fail {
  let value = remainder_mutant(7, 7, False)
  expect remainder_call(7, value, 2)
  True
}

test remainder26_executeintent_destination_executeintent_destination_construction() {
  let value = remainder_mutant(8, 8, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(8, 8, value) }
}

test remainder26_executeintent_destination_executeintent_destination_timelock_spend_rejects() fail {
  let value = remainder_mutant(8, 8, False)
  expect remainder_call(8, value, 0)
  True
}

test remainder26_executeintent_destination_executeintent_destination_intent_policy_rejects() fail {
  let value = remainder_mutant(8, 8, False)
  expect remainder_call(8, value, 1)
  True
}

test remainder26_executeintent_topology_one_over_executeintent_inputs_exact_construction() {
  let value = remainder_mutant(8, 0, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(8, 0, value) }
}

test remainder26_executeintent_topology_one_over_executeintent_inputs_exact_timelock_spend_rejects() fail {
  let value = remainder_mutant(8, 0, False)
  expect remainder_call(8, value, 0)
  True
}

test remainder26_executeintent_topology_one_over_executeintent_inputs_exact_intent_policy_rejects() fail {
  let value = remainder_mutant(8, 0, False)
  expect remainder_call(8, value, 1)
  True
}

test remainder26_executeintent_topology_one_over_executeintent_inputs_global_construction() {
  let value = remainder_mutant(8, 1, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(8, 1, value) }
}

test remainder26_executeintent_topology_one_over_executeintent_inputs_global_timelock_spend_rejects() fail {
  let value = remainder_mutant(8, 1, False)
  expect remainder_call(8, value, 0)
  True
}

test remainder26_executeintent_topology_one_over_executeintent_inputs_global_intent_policy_rejects() fail {
  let value = remainder_mutant(8, 1, False)
  expect remainder_call(8, value, 1)
  True
}

test remainder26_executeintent_topology_one_over_executeintent_inputs_global_resource_at_limit() {
  let value = remainder_mutant(8, 1, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_executeintent_topology_one_over_executeintent_outputs_exact_construction() {
  let value = remainder_mutant(8, 2, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(8, 2, value) }
}

test remainder26_executeintent_topology_one_over_executeintent_outputs_exact_timelock_spend_rejects() fail {
  let value = remainder_mutant(8, 2, False)
  expect remainder_call(8, value, 0)
  True
}

test remainder26_executeintent_topology_one_over_executeintent_outputs_exact_intent_policy_rejects() fail {
  let value = remainder_mutant(8, 2, False)
  expect remainder_call(8, value, 1)
  True
}

test remainder26_executeintent_topology_one_over_executeintent_outputs_global_construction() {
  let value = remainder_mutant(8, 3, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(8, 3, value) }
}

test remainder26_executeintent_topology_one_over_executeintent_outputs_global_timelock_spend_rejects() fail {
  let value = remainder_mutant(8, 3, False)
  expect remainder_call(8, value, 0)
  True
}

test remainder26_executeintent_topology_one_over_executeintent_outputs_global_intent_policy_rejects() fail {
  let value = remainder_mutant(8, 3, False)
  expect remainder_call(8, value, 1)
  True
}

test remainder26_executeintent_topology_one_over_executeintent_outputs_global_resource_at_limit() {
  let value = remainder_mutant(8, 3, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_executeintent_topology_one_over_executeintent_assets_construction() {
  let value = remainder_mutant(8, 4, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(8, 4, value) }
}

test remainder26_executeintent_topology_one_over_executeintent_assets_timelock_spend_rejects() fail {
  let value = remainder_mutant(8, 4, False)
  expect remainder_call(8, value, 0)
  True
}

test remainder26_executeintent_topology_one_over_executeintent_assets_intent_policy_rejects() fail {
  let value = remainder_mutant(8, 4, False)
  expect remainder_call(8, value, 1)
  True
}

test remainder26_executeintent_topology_one_over_executeintent_assets_resource_at_limit() {
  let value = remainder_mutant(8, 4, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_executeintent_topology_one_over_executeintent_datum_bytes_construction() {
  let value = remainder_mutant(8, 5, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(8, 5, value) }
}

test remainder26_executeintent_topology_one_over_executeintent_datum_bytes_timelock_spend_rejects() fail {
  let value = remainder_mutant(8, 5, False)
  expect remainder_call(8, value, 0)
  True
}

test remainder26_executeintent_topology_one_over_executeintent_datum_bytes_intent_policy_rejects() fail {
  let value = remainder_mutant(8, 5, False)
  expect remainder_call(8, value, 1)
  True
}

test remainder26_executeintent_topology_one_over_executeintent_datum_bytes_resource_at_limit() {
  let value = remainder_mutant(8, 5, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_executeintent_topology_one_over_executeintent_signers_construction() {
  let value = remainder_mutant(8, 6, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(8, 6, value) }
}

test remainder26_executeintent_topology_one_over_executeintent_signers_timelock_spend_rejects() fail {
  let value = remainder_mutant(8, 6, False)
  expect remainder_call(8, value, 0)
  True
}

test remainder26_executeintent_topology_one_over_executeintent_signers_intent_policy_rejects() fail {
  let value = remainder_mutant(8, 6, False)
  expect remainder_call(8, value, 1)
  True
}

test remainder26_executeintent_topology_one_over_executeintent_signers_resource_at_limit() {
  let value = remainder_mutant(8, 6, True)
  and { asset_boundary_conserves(value), governance_v2.envelope(value) }
}

test remainder26_executeintent_datum_mutation_executeintent_datum_version_construction() {
  let value = remainder_mutant(8, 7, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(8, 7, value) }
}

test remainder26_executeintent_datum_mutation_executeintent_datum_version_timelock_spend_rejects() fail {
  let value = remainder_mutant(8, 7, False)
  expect remainder_call(8, value, 0)
  True
}

test remainder26_executeintent_datum_mutation_executeintent_datum_version_intent_policy_rejects() fail {
  let value = remainder_mutant(8, 7, False)
  expect remainder_call(8, value, 1)
  True
}

test remainder26_executeintent_timing_boundary_executeintent_before_execute_construction() {
  let value = remainder_mutant(8, 14, False)
  and { asset_boundary_conserves(value), remainder_probe_shape(8, 14, value) }
}

test remainder26_executeintent_timing_boundary_executeintent_before_execute_timelock_spend_rejects() fail {
  let value = remainder_mutant(8, 14, False)
  expect remainder_call(8, value, 0)
  True
}

test remainder26_executeintent_timing_boundary_executeintent_before_execute_intent_policy_rejects() fail {
  let value = remainder_mutant(8, 14, False)
  expect remainder_call(8, value, 1)
  True
}
