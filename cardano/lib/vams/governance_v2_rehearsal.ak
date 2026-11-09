//// Applied-identity rehearsal fixtures for governance v2.
////
//// scripts/cardano/governance_v2_applied_rehearsal.py applies the real
//// validator parameters, computes the resulting script hashes, and evaluates
//// each compiled validator against the ScriptContext values built here.
////
//// Everything is synthetic: custodian key hashes, the seed UTxO, the VAMS
//// token policy and all amounts are fixtures, not ceremony inputs. Contexts are
//// ledger-shaped but are not ledger-validated (no fee, min-UTxO, collateral or
//// balance check). Not deployment evidence.
use aiken/cbor
use aiken/collection/list
use aiken/interval
use aiken/primitive/bytearray
use cardano/address.{Address, Script, VerificationKey}
use cardano/assets
use cardano/script_context.{Minting, ScriptContext, Spending}
use cardano/transaction.{
  InlineDatum, Input, Mint, NoDatum, Output, OutputReference, ScriptPurpose,
  Spend, Transaction, ValidityRange,
}
use vams/governance.{isqrt}
use vams/governance_v2
use vams/governance_v2_types.{
  AuthorityDatumV2, CancelIntentV2, CancelProposalV2, CreateV2, ExecuteIntentV2,
  ExpireIntentV2, FinalizePassedV2, FinalizeRejectedV2, GovernanceActionV2,
  GovernanceAnchorV2, GovernanceBootstrapV2, GovernanceConfigV2,
  GovernanceRequestV2, InitializeV2, IntentDatumV2, PassedV2, PendingV2,
  ProposalDatumV2, QueueV2, VoteLockV2, VoteV2,
}

/// Applied script hashes / policy IDs, computed by the rehearsal driver.
pub type Deployment {
  authority: ByteArray,
  governor: ByteArray,
  timelock: ByteArray,
  proposal: ByteArray,
  receipt: ByteArray,
  intent: ByteArray,
}

/// script: 0 authority, 1 governor, 2 timelock, 3 proposal policy,
/// 4 receipt policy, 5 intent policy.
pub type RehearsalCase {
  label: ByteArray,
  script: Int,
  accept: Bool,
  context: ScriptContext,
}

const alice: ByteArray = #"01010101010101010101010101010101010101010101010101010101"
const bob: ByteArray = #"02020202020202020202020202020202020202020202020202020202"
const proposer: ByteArray = #"03030303030303030303030303030303030303030303030303030303"
const member4: ByteArray = #"04040404040404040404040404040404040404040404040404040404"
const member5: ByteArray = #"05050505050505050505050505050505050505050505050505050505"
const vams_policy: ByteArray = #"66666666666666666666666666666666666666666666666666666666"
const vams_name: ByteArray = #"56414d53"
const forged_policy: ByteArray = #"77777777777777777777777777777777777777777777777777777777"
const wrong_governor: ByteArray = #"88888888888888888888888888888888888888888888888888888888"
const seed_tx: ByteArray = #"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
const gov_tx: ByteArray = #"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
const fund_tx: ByteArray = #"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"

/// Rehearsal clock (POSIX ms, late 2026) and fee.
const t0: Int = 1_794_000_000_000
const deadline: Int = 1_794_003_600_000
const fee: Int = 400_000

fn members() -> List<ByteArray> {
  [alice, bob, proposer, member4, member5]
}

fn seed_ref() -> OutputReference {
  OutputReference { transaction_id: seed_tx, output_index: 0 }
}

fn gov_ref(index: Int) -> OutputReference {
  OutputReference { transaction_id: gov_tx, output_index: index }
}

fn fund_ref() -> OutputReference {
  OutputReference { transaction_id: fund_tx, output_index: 0 }
}

fn script(hash: ByteArray) -> Address {
  Address { payment_credential: Script(hash), stake_credential: None }
}

fn key(hash: ByteArray) -> Address {
  Address { payment_credential: VerificationKey(hash), stake_credential: None }
}

fn inline(address: Address, value: assets.Value, data: Data) -> Output {
  Output { address, value, datum: InlineDatum(data), reference_script: None }
}

fn pay(address: Address, value: assets.Value) -> Output {
  Output { address, value, datum: NoDatum, reference_script: None }
}

fn vams(lovelace: Int, amount: Int) -> assets.Value {
  assets.from_lovelace(lovelace) |> assets.add(vams_policy, vams_name, amount)
}

fn half_open(lower: Int, upper: Int) -> ValidityRange {
  let range = interval.between(lower, upper)
  interval.Interval {
    ..range,
    upper_bound: interval.IntervalBound { ..range.upper_bound, is_inclusive: False },
  }
}

pub fn bootstrap() -> GovernanceBootstrapV2 {
  GovernanceBootstrapV2 { seed: seed_ref(), network_id: 0, policy_epoch: 1, members: members() }
}

pub fn config(d: Deployment, proposal_nonce: Int, intent_nonce: Int) -> GovernanceConfigV2 {
  GovernanceConfigV2 {
    version: 2, network_id: 0, policy_epoch: 1, seed: seed_ref(),
    authority_policy_id: d.authority, governor_script_hash: d.governor,
    timelock_script_hash: d.timelock, proposal_policy_id: d.proposal,
    receipt_policy_id: d.receipt, intent_policy_id: d.intent,
    vams_policy_id: vams_policy, vams_asset_name: vams_name,
    members: members(), threshold: 3,
    normal_delay_ms: governance_v2.delay_ms, emergency_disabled: True,
    authority_state_lovelace: 5_000_000, proposal_base_lovelace: 3_000_000,
    per_voter_refund_lovelace: 2_000_000, next_proposal_nonce: proposal_nonce,
    next_intent_nonce: intent_nonce, max_lock_vams: 1_000_000_000,
    target_domains: [#"70726570726f642f74657374"],
  }
}

pub fn anchor(authority: ByteArray) -> GovernanceAnchorV2 {
  let d = Deployment { authority, governor: #"", timelock: #"", proposal: #"", receipt: #"", intent: #"" }
  GovernanceAnchorV2 { policy_id: authority, asset_name: governance_v2.authority_name(config(d, 0, 0)) }
}

fn authority_output(c: GovernanceConfigV2) -> Output {
  inline(script(c.authority_policy_id),
    assets.from_lovelace(c.authority_state_lovelace)
      |> assets.add(c.authority_policy_id, governance_v2.authority_name(c), 1),
    AuthorityDatumV2 { config: c })
}

fn authority_input(c: GovernanceConfigV2) -> Input {
  Input { output_reference: gov_ref(0), output: authority_output(c) }
}

fn initial(d: Deployment) -> ProposalDatumV2 {
  let p = ProposalDatumV2 {
    version: 2, state: PendingV2, proposal_asset: #"", nonce: 0, proposer_vkh: proposer,
    description_hash: #"6666666666666666666666666666666666666666666666666666666666666666",
    action_hash: #"7777777777777777777777777777777777777777777777777777777777777777",
    payload_hash: #"8888888888888888888888888888888888888888888888888888888888888888",
    target_domain: #"70726570726f642f74657374", policy_epoch: 1,
    quorum: 10, deadline, yes_weight: 0, no_weight: 0, locks: [],
  }
  ProposalDatumV2 { ..p, proposal_asset: governance_v2.proposal_name(config(d, 1, 0), p) }
}

fn with_vote(d: Deployment, p: ProposalDatumV2, voter: ByteArray, locked: Int, support: Bool) -> ProposalDatumV2 {
  let lock = VoteLockV2 { voter_vkh: voter, locked_vams: locked, support, weight: isqrt(locked), receipt_name: #"" }
  let lock = VoteLockV2 { ..lock,
    receipt_name: governance_v2.receipt_name(config(d, 1, 0), p.proposal_asset, lock, list.length(p.locks)) }
  ProposalDatumV2 { ..p,
    locks: list.concat(p.locks, [lock]),
    yes_weight: p.yes_weight + if support { lock.weight } else { 0 },
    no_weight: p.no_weight + if support { 0 } else { lock.weight },
  }
}

/// Built from config terms independently of the production value function.
fn proposal_value(d: Deployment, p: ProposalDatumV2) -> assets.Value {
  let stake = list.foldl(p.locks, 0, fn(lock, sum) { sum + lock.locked_vams })
  let value = vams(3_000_000 + list.length(p.locks) * 2_000_000, stake)
    |> assets.add(d.proposal, p.proposal_asset, 1)
  list.foldl(p.locks, value, fn(lock, acc) { assets.add(acc, d.receipt, lock.receipt_name, 1) })
}

fn proposal_output(d: Deployment, p: ProposalDatumV2) -> Output {
  inline(script(d.governor), proposal_value(d, p), p)
}

fn proposal_input(d: Deployment, p: ProposalDatumV2) -> Input {
  Input { output_reference: gov_ref(1), output: proposal_output(d, p) }
}

fn funding(vkh: ByteArray, lovelace: Int, amount: Int) -> Input {
  Input { output_reference: fund_ref(), output: pay(key(vkh), vams(lovelace, amount)) }
}

/// Protocol outputs followed by the funder's change, as funded_outputs expects.
fn with_change(expected: List<Output>, funder: ByteArray, available: Int, required: Int, available_vams: Int, required_vams: Int) -> List<Output> {
  let change = available - required - fee
  if change == 0 && available_vams == required_vams {
    expected
  } else {
    list.concat(expected, [pay(key(funder), vams(change, available_vams - required_vams))])
  }
}

fn intent_of(p: ProposalDatumV2, queued: Int, delay: Int) -> IntentDatumV2 {
  IntentDatumV2 {
    version: 2, proposal_id: governance_v2.proposal_commitment(p), proposal_asset: p.proposal_asset,
    action_hash: p.action_hash, payload_hash: p.payload_hash, target_domain: p.target_domain,
    policy_epoch: 1, nonce: 0, queue_time: queued, execute_after: queued + delay,
    lifetime: governance_v2.lifetime_ms, proposer_vkh: p.proposer_vkh, consumed: False,
  }
}

fn intent_output(d: Deployment, i: IntentDatumV2) -> Output {
  inline(script(d.timelock),
    assets.from_lovelace(3_000_000) |> assets.add(d.intent, governance_v2.intent_name(config(d, 1, 1), i), 1), i)
}

fn request(action: GovernanceActionV2) -> Data {
  let r: Data = GovernanceRequestV2 { version: 2, action }
  r
}

fn purpose_rank(purpose: ScriptPurpose) -> (Int, ByteArray, Int) {
  when purpose is {
    Mint(policy) -> (0, policy, 0)
    Spend(reference) -> (1, reference.transaction_id, reference.output_index)
    _ -> (9, #"", 0)
  }
}

/// Ledger order: Mint before Spend; policies and references ascending.
fn purpose_order(left: Pair<ScriptPurpose, Data>, right: Pair<ScriptPurpose, Data>) -> Ordering {
  let (lk, lb, li) = purpose_rank(left.1st)
  let (rk, rb, ri) = purpose_rank(right.1st)
  if lk != rk {
    if lk < rk { Less } else { Greater }
  } else {
    when bytearray.compare(lb, rb) is {
      Equal -> if li == ri { Equal } else if li < ri { Less } else { Greater }
      other -> other
    }
  }
}

fn build(lower: Int, upper: Int, inputs: List<Input>, reference_inputs: List<Input>, signers: List<ByteArray>,
  outputs: List<Output>, mint: assets.Value, redeemers: Pairs<ScriptPurpose, Data>) -> Transaction {
  Transaction { ..transaction.placeholder,
    inputs, reference_inputs, outputs, fee, mint,
    validity_range: half_open(lower, upper),
    extra_signatories: signers,
    redeemers: list.sort(redeemers, purpose_order),
    id: #"dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
  }
}

fn minting(label: ByteArray, script_index: Int, accept: Bool, tx: Transaction, policy: ByteArray, redeemer: Data) -> RehearsalCase {
  RehearsalCase { label, script: script_index, accept,
    context: ScriptContext { transaction: tx, redeemer, info: Minting(policy) } }
}

fn spending(label: ByteArray, script_index: Int, accept: Bool, tx: Transaction, input: Input, redeemer: Data) -> RehearsalCase {
  expect InlineDatum(datum) = input.output.datum
  RehearsalCase { label, script: script_index, accept,
    context: ScriptContext { transaction: tx, redeemer,
      info: Spending { output: input.output_reference, datum: Some(datum) } } }
}

// ---- Transactions ----------------------------------------------------------

fn genesis_tx(d: Deployment, seed: OutputReference) -> Transaction {
  let c = config(d, 0, 0)
  let r = request(InitializeV2)
  build(t0, t0 + 120_000, [Input { output_reference: seed, output: pay(key(proposer), assets.from_lovelace(8_000_000)) }], [],
    [alice, bob, proposer],
    with_change([authority_output(c)], proposer, 8_000_000, 5_000_000, 0, 0),
    assets.from_asset(d.authority, governance_v2.authority_name(c), 1),
    [Pair(Mint(d.authority), r)])
}

fn create_tx(d: Deployment, governor: ByteArray) -> Transaction {
  let p = initial(d)
  let r = request(CreateV2)
  build(t0 + 120_000, t0 + 240_000, [authority_input(config(d, 0, 0)), funding(proposer, 10_000_000, 0)], [],
    [alice, bob, proposer],
    with_change([authority_output(config(d, 1, 0)), inline(script(governor), proposal_value(d, p), p)],
      proposer, 10_000_000, 3_000_000, 0, 0),
    assets.from_asset(d.proposal, p.proposal_asset, 1),
    [Pair(Spend(gov_ref(0)), r), Pair(Mint(d.proposal), r)])
}

fn vote_tx(d: Deployment, before: ProposalDatumV2, after: ProposalDatumV2, voter: ByteArray, locked: Int, support: Bool, authority: Input, version: Int) -> Transaction {
  expect Some(added) = list.last(after.locks)
  let r: Data = GovernanceRequestV2 { version, action: VoteV2 { voter_vkh: voter, support, locked_vams: locked } }
  build(t0 + 300_000, t0 + 400_000, [proposal_input(d, before), funding(voter, 10_000_000, locked)], [authority],
    [voter],
    with_change([proposal_output(d, after)], voter, 10_000_000, 2_000_000, locked, locked),
    assets.from_asset(d.receipt, added.receipt_name, 1),
    [Pair(Spend(gov_ref(1)), r), Pair(Mint(d.receipt), r)])
}

fn finalize_passed_tx(d: Deployment) -> Transaction {
  let p = with_vote(d, initial(d), alice, 100, True)
  let r = request(FinalizePassedV2)
  build(deadline, deadline + 100_000, [proposal_input(d, p), funding(proposer, 5_000_000, 0)], [authority_input(config(d, 1, 0))],
    [proposer],
    with_change([proposal_output(d, ProposalDatumV2 { ..p, state: PassedV2 })], proposer, 5_000_000, 0, 0, 0),
    assets.zero, [Pair(Spend(gov_ref(1)), r)])
}

fn terminal_tx(d: Deployment, cancel: Bool, refund_to: ByteArray) -> Transaction {
  let p = with_vote(d, initial(d), alice, 100, cancel)
  expect [lock] = p.locks
  let r = request(if cancel { CancelProposalV2 } else { FinalizeRejectedV2 })
  let (lower, upper) = if cancel { (t0 + 400_000, t0 + 500_000) } else { (deadline, deadline + 100_000) }
  build(lower, upper, [proposal_input(d, p), funding(proposer, 5_000_000, 0)], [authority_input(config(d, 1, 0))],
    [proposer],
    with_change([pay(key(refund_to), vams(2_000_000, 100)), pay(key(proposer), assets.from_lovelace(3_000_000))],
      proposer, 5_000_000, 0, 0, 0),
    assets.from_asset(d.proposal, p.proposal_asset, -1) |> assets.add(d.receipt, lock.receipt_name, -1),
    [Pair(Spend(gov_ref(1)), r), Pair(Mint(d.proposal), r), Pair(Mint(d.receipt), r)])
}

fn queued_at() -> Int {
  deadline + 200_000
}

fn queue_tx(d: Deployment, delay: Int) -> Transaction {
  let p = ProposalDatumV2 { ..with_vote(d, initial(d), alice, 100, True), state: PassedV2 }
  expect [lock] = p.locks
  let i = intent_of(p, queued_at(), delay)
  let name = governance_v2.intent_name(config(d, 1, 1), i)
  let r = request(QueueV2)
  build(deadline + 100_000, queued_at(),
    [authority_input(config(d, 1, 0)), proposal_input(d, p), funding(proposer, 5_000_000, 0)], [],
    [alice, bob, proposer],
    with_change([authority_output(config(d, 1, 1)), pay(key(alice), vams(2_000_000, 100)), intent_output(d, i)],
      proposer, 5_000_000, 0, 0, 0),
    assets.from_asset(d.proposal, p.proposal_asset, -1)
      |> assets.add(d.receipt, lock.receipt_name, -1)
      |> assets.add(d.intent, name, 1),
    [Pair(Spend(gov_ref(0)), r), Pair(Spend(gov_ref(1)), r), Pair(Mint(d.proposal), r),
      Pair(Mint(d.receipt), r), Pair(Mint(d.intent), r)])
}

fn queued_intent(d: Deployment) -> IntentDatumV2 {
  let p = ProposalDatumV2 { ..with_vote(d, initial(d), alice, 100, True), state: PassedV2 }
  intent_of(p, queued_at(), governance_v2.delay_ms)
}

fn intent_input(d: Deployment) -> Input {
  Input { output_reference: gov_ref(3), output: intent_output(d, queued_intent(d)) }
}

fn intent_tx(d: Deployment, action: GovernanceActionV2, signers: List<ByteArray>, lower: Int) -> Transaction {
  let i = queued_intent(d)
  let r = request(action)
  build(lower, lower + 100_000, [intent_input(d), funding(proposer, 5_000_000, 0)], [authority_input(config(d, 1, 1))],
    signers,
    with_change([pay(key(proposer), assets.from_lovelace(3_000_000))], proposer, 5_000_000, 0, 0, 0),
    assets.from_asset(d.intent, governance_v2.intent_name(config(d, 1, 1), i), -1),
    [Pair(Spend(gov_ref(3)), r), Pair(Mint(d.intent), r)])
}

fn expiry_time() -> Int {
  queued_at() + governance_v2.delay_ms + governance_v2.lifetime_ms
}

// ---- Maximum-width (eight voter) stress transactions ------------------------

fn eight_voters() -> List<ByteArray> {
  [alice, bob, proposer, member4, member5,
    #"06060606060606060606060606060606060606060606060606060606",
    #"07070707070707070707070707070707070707070707070707070707",
    #"08080808080808080808080808080808080808080808080808080808"]
}

fn with_votes(d: Deployment, voters: List<ByteArray>, support: Bool) -> ProposalDatumV2 {
  list.foldl(voters, initial(d), fn(voter, p) { with_vote(d, p, voter, 100, support) })
}

fn refunds(p: ProposalDatumV2) -> List<Output> {
  list.map(p.locks, fn(lock) { pay(key(lock.voter_vkh), vams(2_000_000, lock.locked_vams)) })
}

fn burns(d: Deployment, p: ProposalDatumV2) -> assets.Value {
  list.foldl(p.locks, assets.from_asset(d.proposal, p.proposal_asset, -1),
    fn(lock, value) { assets.add(value, d.receipt, lock.receipt_name, -1) })
}

fn eighth_vote_tx(d: Deployment) -> Transaction {
  let before = with_votes(d, list.take(eight_voters(), 7), True)
  let voter = #"08080808080808080808080808080808080808080808080808080808"
  vote_tx(d, before, with_vote(d, before, voter, 100, True), voter, 100, True, c1_input(d), 2)
}

fn rejected_n_tx(d: Deployment) -> Transaction {
  let p = with_votes(d, eight_voters(), False)
  let r = request(FinalizeRejectedV2)
  build(deadline, deadline + 100_000, [proposal_input(d, p), funding(proposer, 5_000_000, 0)], [c1_input(d)],
    [proposer],
    with_change(list.concat(refunds(p), [pay(key(proposer), assets.from_lovelace(3_000_000))]),
      proposer, 5_000_000, 0, 0, 0),
    burns(d, p),
    [Pair(Spend(gov_ref(1)), r), Pair(Mint(d.proposal), r), Pair(Mint(d.receipt), r)])
}

fn passed_n(d: Deployment) -> ProposalDatumV2 {
  ProposalDatumV2 { ..with_votes(d, eight_voters(), True), state: PassedV2 }
}

fn queue_n_tx(d: Deployment) -> Transaction {
  let p = passed_n(d)
  let i = intent_of(p, queued_at(), governance_v2.delay_ms)
  let name = governance_v2.intent_name(config(d, 1, 1), i)
  let r = request(QueueV2)
  build(deadline + 100_000, queued_at(),
    [authority_input(config(d, 1, 0)), proposal_input(d, p), funding(proposer, 5_000_000, 0)], [],
    [alice, bob, proposer],
    with_change(list.concat([authority_output(config(d, 1, 1))], list.concat(refunds(p), [intent_output(d, i)])),
      proposer, 5_000_000, 0, 0, 0),
    burns(d, p) |> assets.add(d.intent, name, 1),
    [Pair(Spend(gov_ref(0)), r), Pair(Spend(gov_ref(1)), r), Pair(Mint(d.proposal), r),
      Pair(Mint(d.receipt), r), Pair(Mint(d.intent), r)])
}

// ---- Cases -----------------------------------------------------------------

/// Number of cases served by case_at (indices 0 to 41).
pub fn case_total() -> Int {
  42
}

fn p0(d: Deployment) -> ProposalDatumV2 {
  initial(d)
}

fn p1(d: Deployment, support: Bool) -> ProposalDatumV2 {
  with_vote(d, initial(d), alice, 100, support)
}

fn passed(d: Deployment) -> ProposalDatumV2 {
  ProposalDatumV2 { ..p1(d, True), state: PassedV2 }
}

fn vote_request(voter: ByteArray, locked: Int, version: Int) -> Data {
  let r: Data = GovernanceRequestV2 { version, action: VoteV2 { voter_vkh: voter, support: True, locked_vams: locked } }
  r
}

fn c1_input(d: Deployment) -> Input {
  authority_input(config(d, 1, 0))
}

fn vote1(d: Deployment, authority: Input, version: Int) -> Transaction {
  vote_tx(d, p0(d), p1(d, True), alice, 100, True, authority, version)
}

fn vote2(d: Deployment, after: ProposalDatumV2) -> Transaction {
  vote_tx(d, p1(d, True), after, bob, 900, True, c1_input(d), 2)
}

/// One case per call keeps each evaluation inside the default budget.
pub fn case_at(d: Deployment, index: Int) -> RehearsalCase {
  when index is {
    0 -> minting("genesis/authority_mint", 0, True, genesis_tx(d, seed_ref()), d.authority, request(InitializeV2))
    1 -> spending("create/authority_spend", 0, True, create_tx(d, d.governor), authority_input(config(d, 0, 0)), request(CreateV2))
    2 -> minting("create/proposal_mint", 3, True, create_tx(d, d.governor), d.proposal, request(CreateV2))
    3 -> spending("vote1/governor_spend", 1, True, vote1(d, c1_input(d), 2), proposal_input(d, p0(d)), vote_request(alice, 100, 2))
    4 -> minting("vote1/receipt_mint", 4, True, vote1(d, c1_input(d), 2), d.receipt, vote_request(alice, 100, 2))
    5 -> spending("vote2/governor_spend", 1, True, vote2(d, with_vote(d, p1(d, True), bob, 900, True)), proposal_input(d, p1(d, True)), vote_request(bob, 900, 2))
    6 -> minting("vote2/receipt_mint", 4, True, vote2(d, with_vote(d, p1(d, True), bob, 900, True)), d.receipt, vote_request(bob, 900, 2))
    7 -> spending("finalize_passed/governor_spend", 1, True, finalize_passed_tx(d), proposal_input(d, p1(d, True)), request(FinalizePassedV2))
    8 -> spending("finalize_rejected/governor_spend", 1, True, terminal_tx(d, False, alice), proposal_input(d, p1(d, False)), request(FinalizeRejectedV2))
    9 -> minting("finalize_rejected/proposal_burn", 3, True, terminal_tx(d, False, alice), d.proposal, request(FinalizeRejectedV2))
    10 -> minting("finalize_rejected/receipt_burn", 4, True, terminal_tx(d, False, alice), d.receipt, request(FinalizeRejectedV2))
    11 -> spending("cancel_proposal/governor_spend", 1, True, terminal_tx(d, True, alice), proposal_input(d, p1(d, True)), request(CancelProposalV2))
    12 -> minting("cancel_proposal/proposal_burn", 3, True, terminal_tx(d, True, alice), d.proposal, request(CancelProposalV2))
    13 -> minting("cancel_proposal/receipt_burn", 4, True, terminal_tx(d, True, alice), d.receipt, request(CancelProposalV2))
    14 -> spending("queue/authority_spend", 0, True, queue_tx(d, governance_v2.delay_ms), c1_input(d), request(QueueV2))
    15 -> spending("queue/governor_spend", 1, True, queue_tx(d, governance_v2.delay_ms), proposal_input(d, passed(d)), request(QueueV2))
    16 -> minting("queue/proposal_burn", 3, True, queue_tx(d, governance_v2.delay_ms), d.proposal, request(QueueV2))
    17 -> minting("queue/receipt_burn", 4, True, queue_tx(d, governance_v2.delay_ms), d.receipt, request(QueueV2))
    18 -> minting("queue/intent_mint", 5, True, queue_tx(d, governance_v2.delay_ms), d.intent, request(QueueV2))
    19 -> spending("cancel_intent/timelock_spend", 2, True, intent_tx(d, CancelIntentV2, [alice, bob, proposer], queued_at() + 100_000), intent_input(d), request(CancelIntentV2))
    20 -> minting("cancel_intent/intent_burn", 5, True, intent_tx(d, CancelIntentV2, [alice, bob, proposer], queued_at() + 100_000), d.intent, request(CancelIntentV2))
    21 -> spending("expire_intent/timelock_spend", 2, True, intent_tx(d, ExpireIntentV2, [proposer], expiry_time()), intent_input(d), request(ExpireIntentV2))
    22 -> minting("expire_intent/intent_burn", 5, True, intent_tx(d, ExpireIntentV2, [proposer], expiry_time()), d.intent, request(ExpireIntentV2))
    // Adversarial cases: each must be rejected by the applied validator.
    23 -> spending("reject/execute_intent_disabled", 2, False, intent_tx(d, ExecuteIntentV2, [proposer], expiry_time()), intent_input(d), request(ExecuteIntentV2))
    24 -> spending("reject/two_member_intent_cancel", 2, False, intent_tx(d, CancelIntentV2, [alice, proposer], queued_at() + 100_000), intent_input(d), request(CancelIntentV2))
    25 -> spending("reject/queue_with_24h_delay", 1, False, queue_tx(d, 86_400_000), proposal_input(d, passed(d)), request(QueueV2))
    26 -> spending("reject/vote_replaces_prior_voter", 1, False, vote2(d, with_vote(d, p0(d), bob, 900, True)), proposal_input(d, p1(d, True)), vote_request(bob, 900, 2))
    27 -> spending("reject/rejected_refund_redirected", 1, False, terminal_tx(d, False, bob), proposal_input(d, p1(d, False)), request(FinalizeRejectedV2))
    28 -> spending("reject/forged_authority_reference", 1, False, vote1(d, authority_input(config(Deployment { ..d, authority: forged_policy }, 1, 0)), 2), proposal_input(d, p0(d)), vote_request(alice, 100, 2))
    29 -> spending("reject/version_1_request", 1, False, vote1(d, c1_input(d), 1), proposal_input(d, p0(d)), vote_request(alice, 100, 1))
    30 -> minting("reject/genesis_wrong_seed", 0, False, genesis_tx(d, OutputReference { transaction_id: seed_tx, output_index: 1 }), d.authority, request(InitializeV2))
    31 -> spending("reject/create_wrong_governor_destination", 0, False, create_tx(d, wrong_governor), authority_input(config(d, 0, 0)), request(CreateV2))
    // Maximum-width (eight voter) budget cases.
    32 -> spending("max_vote8/governor_spend", 1, True, eighth_vote_tx(d), proposal_input(d, with_votes(d, list.take(eight_voters(), 7), True)), vote_request(#"08080808080808080808080808080808080808080808080808080808", 100, 2))
    33 -> minting("max_vote8/receipt_mint", 4, True, eighth_vote_tx(d), d.receipt, vote_request(#"08080808080808080808080808080808080808080808080808080808", 100, 2))
    34 -> spending("max_rejected8/governor_spend", 1, True, rejected_n_tx(d), proposal_input(d, with_votes(d, eight_voters(), False)), request(FinalizeRejectedV2))
    35 -> minting("max_rejected8/proposal_burn", 3, True, rejected_n_tx(d), d.proposal, request(FinalizeRejectedV2))
    36 -> minting("max_rejected8/receipt_burn", 4, True, rejected_n_tx(d), d.receipt, request(FinalizeRejectedV2))
    37 -> spending("max_queue8/authority_spend", 0, True, queue_n_tx(d), c1_input(d), request(QueueV2))
    38 -> spending("max_queue8/governor_spend", 1, True, queue_n_tx(d), proposal_input(d, passed_n(d)), request(QueueV2))
    39 -> minting("max_queue8/proposal_burn", 3, True, queue_n_tx(d), d.proposal, request(QueueV2))
    40 -> minting("max_queue8/receipt_burn", 4, True, queue_n_tx(d), d.receipt, request(QueueV2))
    _ -> minting("max_queue8/intent_mint", 5, True, queue_n_tx(d), d.intent, request(QueueV2))
  }
}

// ---- Exported entry points for the rehearsal driver (aiken export) ---------

pub fn bootstrap_cbor() -> ByteArray {
  cbor.serialise(bootstrap())
}

pub fn anchor_cbor(authority: ByteArray) -> ByteArray {
  cbor.serialise(anchor(authority))
}

pub fn case_cbor(authority: ByteArray, governor: ByteArray, timelock: ByteArray, proposal: ByteArray, receipt: ByteArray, intent: ByteArray, index: Int) -> ByteArray {
  cbor.serialise(case_at(Deployment { authority, governor, timelock, proposal, receipt, intent }, index))
}
