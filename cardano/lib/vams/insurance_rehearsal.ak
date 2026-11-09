//// Applied-identity rehearsal fixtures for the insurance fund validator.
////
//// scripts/cardano/insurance_applied_rehearsal.py applies the six real
//// validator parameters, computes the applied script hash (the state policy
//// ID), and evaluates the compiled validator on the ScriptContext values built
//// here.
////
//// Everything is synthetic: guardian and claimant key hashes, the seed UTxO
//// and all amounts are fixtures, not ceremony inputs. Contexts are
//// ledger-shaped but not ledger-validated. Claim identities are derived here
//// independently of the validator module; a mismatch shows as a rejected
//// accept case. Not deployment evidence.
use aiken/cbor
use aiken/collection/list
use aiken/crypto.{blake2b_256}
use aiken/interval
use aiken/primitive/bytearray
use cardano/address.{Address, Inline, Script, VerificationKey}
use cardano/assets
use cardano/script_context.{Minting, ScriptContext, Spending}
use cardano/transaction.{
  InlineDatum, Input, Mint, NoDatum, Output, OutputReference, ScriptPurpose,
  Spend, Transaction,
}
use vams/types.{
  ApproveClaim, CancelClaim, ClaimIdentityPayload, ClaimRecord, Deposit,
  ExpireClaim, FundDatumV2, InitializeFund, InsuranceFundRedeemer, PayoutClaim,
  SubmitClaim,
}

/// handler: 0 mint, 1 spend. datum_bytes: serialized size of the fund datum
/// the transaction creates (0 when none).
pub type InsuranceCase {
  label: ByteArray,
  handler: Int,
  accept: Bool,
  datum_bytes: Int,
  context: ScriptContext,
}

const g1: ByteArray = #"a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1"
const g2: ByteArray = #"a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2"
const g3: ByteArray = #"a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3"
const g4: ByteArray = #"a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4"
const g5: ByteArray = #"a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5"
const outsider: ByteArray = #"a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6"
const claimant_a: ByteArray = #"c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1"
const claimant_b: ByteArray = #"c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2"
const stake_a: ByteArray = #"d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1d1"
const stake_b: ByteArray = #"d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2"
const payer: ByteArray = #"f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0"
const evidence: ByteArray = #"eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
const seed_tx: ByteArray = #"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
const state_tx: ByteArray = #"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
const fund_tx: ByteArray = #"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
const state_name: ByteArray = #"56414d535f494e535552414e43455f5354415445"

const t0: Int = 1_794_000_000_000
const window_ms: Int = 604_800_000
const balance: Int = 100_000_000
const fee: Int = 500_000

fn guardians() -> List<ByteArray> {
  [g1, g2, g3, g4, g5]
}

fn seed_ref() -> OutputReference {
  OutputReference { transaction_id: seed_tx, output_index: 0 }
}

fn state_ref() -> OutputReference {
  OutputReference { transaction_id: state_tx, output_index: 0 }
}

fn payer_ref() -> OutputReference {
  OutputReference { transaction_id: fund_tx, output_index: 0 }
}

/// Parameters in declaration order: genesis_ref, state_asset_name, guardians,
/// threshold, policy_epoch, max_payout_bps.
pub fn param_cbor(index: Int) -> ByteArray {
  when index is {
    0 -> cbor.serialise(seed_ref())
    1 -> cbor.serialise(state_name)
    2 -> cbor.serialise(guardians())
    3 -> cbor.serialise(3)
    4 -> cbor.serialise(1)
    _ -> cbor.serialise(5000)
  }
}

fn key(vkh: ByteArray) -> Address {
  Address { payment_credential: VerificationKey(vkh), stake_credential: None }
}

/// Base address (payment + stake key): the widest ordinary payout address.
fn base(vkh: ByteArray, stake: ByteArray) -> Address {
  Address { payment_credential: VerificationKey(vkh), stake_credential: Some(Inline(VerificationKey(stake))) }
}

fn claim_id(policy: ByteArray, nonce: Int, claimant: ByteArray, payout: Address, amount: Int, submitted: Int) -> ByteArray {
  ClaimIdentityPayload {
    domain: "VAMS_INSURANCE_CLAIM_V2", state_policy_id: policy, state_asset_name: state_name,
    policy_epoch: 1, claim_nonce: nonce, claimant_vkh: claimant, payout_address: payout,
    amount, evidence_hash: evidence, submitted_at: submitted, expires_at: submitted + window_ms,
  }
    |> cbor.serialise
    |> blake2b_256
}

fn claim(policy: ByteArray, nonce: Int, claimant: ByteArray, payout: Address, amount: Int, submitted: Int, approvers: List<ByteArray>) -> ClaimRecord {
  ClaimRecord {
    claim_id: claim_id(policy, nonce, claimant, payout, amount, submitted), claim_nonce: nonce,
    claimant_vkh: claimant, payout_address: payout, amount, evidence_hash: evidence,
    submitted_at: submitted, expires_at: submitted + window_ms, policy_epoch: 1, approvers,
  }
}

/// Claim A: simple key address. Claim B (max cases): base address.
fn claim_a(policy: ByteArray, approvers: List<ByteArray>) -> ClaimRecord {
  claim(policy, 0, claimant_a, key(claimant_a), 10_000_000, t0, approvers)
}

fn claim_wide_a(policy: ByteArray, approvers: List<ByteArray>) -> ClaimRecord {
  claim(policy, 0, claimant_a, base(claimant_a, stake_a), 10_000_000, t0, approvers)
}

fn claim_wide_b(policy: ByteArray, approvers: List<ByteArray>) -> ClaimRecord {
  claim(policy, 1, claimant_b, base(claimant_b, stake_b), 12_000_000, t0 + 200_000, approvers)
}

fn datum(total: Int, next_nonce: Int, claims: List<ClaimRecord>) -> FundDatumV2 {
  FundDatumV2 {
    schema_version: 2, total_balance: total, next_claim_nonce: next_nonce, pending_claims: claims,
    policy_epoch: 1, max_payout_bps: 5000, approval_threshold: 3, guardians: guardians(),
  }
}

fn state_output(policy: ByteArray, address_hash: ByteArray, d: FundDatumV2) -> Output {
  Output {
    address: Address { payment_credential: Script(address_hash), stake_credential: None },
    value: assets.from_lovelace(d.total_balance) |> assets.add(policy, state_name, 1),
    datum: InlineDatum(d), reference_script: None,
  }
}

fn state_input(policy: ByteArray, d: FundDatumV2) -> Input {
  Input { output_reference: state_ref(), output: state_output(policy, policy, d) }
}

fn payer_input(lovelace: Int) -> Input {
  Input { output_reference: payer_ref(),
    output: Output { address: key(payer), value: assets.from_lovelace(lovelace), datum: NoDatum, reference_script: None } }
}

fn pay(address: Address, lovelace: Int) -> Output {
  Output { address, value: assets.from_lovelace(lovelace), datum: NoDatum, reference_script: None }
}

fn window(lower: Int, upper: Int) -> interval.Interval<Int> {
  interval.between(lower, upper)
}

fn build(inputs: List<Input>, outputs: List<Output>, signers: List<ByteArray>, lower: Int, upper: Int,
  mint: assets.Value, redeemers: Pairs<ScriptPurpose, Data>) -> Transaction {
  Transaction { ..transaction.placeholder,
    inputs, outputs, fee, mint, validity_range: window(lower, upper), extra_signatories: signers, redeemers,
    id: #"dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
  }
}

/// A fund transition paid for by a separate fee input, with change returned.
fn transition(policy: ByteArray, before: FundDatumV2, after: FundDatumV2, extra: List<Output>,
  signers: List<ByteArray>, lower: Int, upper: Int, redeemer: Data, continuing_hash: ByteArray) -> Transaction {
  build([state_input(policy, before), payer_input(5_000_000)],
    list.concat([state_output(policy, continuing_hash, after)], list.concat(extra, [pay(key(payer), 5_000_000 - fee)])),
    signers, lower, upper, assets.zero, [Pair(Spend(state_ref()), redeemer)])
}

fn size(d: FundDatumV2) -> Int {
  bytearray.length(cbor.serialise(d))
}

fn spend_case(label: ByteArray, accept: Bool, policy: ByteArray, before: FundDatumV2, after: FundDatumV2,
  extra: List<Output>, signers: List<ByteArray>, lower: Int, upper: Int, redeemer: InsuranceFundRedeemer) -> InsuranceCase {
  spend_case_to(label, accept, policy, before, after, extra, signers, lower, upper, redeemer, policy)
}

fn spend_case_to(label: ByteArray, accept: Bool, policy: ByteArray, before: FundDatumV2, after: FundDatumV2,
  extra: List<Output>, signers: List<ByteArray>, lower: Int, upper: Int, redeemer: InsuranceFundRedeemer,
  continuing_hash: ByteArray) -> InsuranceCase {
  let r: Data = redeemer
  let before_data: Data = before
  InsuranceCase { label, handler: 1, accept, datum_bytes: size(after),
    context: ScriptContext {
      transaction: transition(policy, before, after, extra, signers, lower, upper, r, continuing_hash),
      redeemer: r,
      info: Spending { output: state_ref(), datum: Some(before_data) },
    } }
}

fn genesis_case(label: ByteArray, accept: Bool, policy: ByteArray, seed: OutputReference) -> InsuranceCase {
  let d = datum(balance, 0, [])
  let r: Data = InitializeFund
  let seed_input = Input { output_reference: seed,
    output: Output { address: key(payer), value: assets.from_lovelace(120_000_000), datum: NoDatum, reference_script: None } }
  let tx = build([seed_input], [state_output(policy, policy, d), pay(key(payer), 120_000_000 - balance - fee)],
    [payer], t0, t0 + 120_000, assets.from_asset(policy, state_name, 1), [Pair(Mint(policy), r)])
  InsuranceCase { label, handler: 0, accept, datum_bytes: size(d),
    context: ScriptContext { transaction: tx, redeemer: r, info: Minting(policy) } }
}

fn submit(nonce: Int, claimant: ByteArray, payout: Address, amount: Int) -> InsuranceFundRedeemer {
  SubmitClaim { claim_nonce: nonce, claimant_vkh: claimant, payout_address: payout, amount, evidence_hash: evidence }
}

/// Number of cases served by case_at (indices 0 to 16).
pub fn case_total() -> Int {
  17
}

pub fn case_at(p: ByteArray, index: Int) -> InsuranceCase {
  let empty = datum(balance, 0, [])
  let a0 = claim_a(p, [])
  let a3 = claim_a(p, [g1, g2, g3])
  let after_submit = datum(balance, 1, [a0])
  when index is {
    0 -> genesis_case("genesis/state_mint", True, p, seed_ref())
    1 -> spend_case("submit/spend", True, p, empty, after_submit, [], [claimant_a], t0, t0 + 120_000,
      submit(0, claimant_a, key(claimant_a), 10_000_000))
    2 -> spend_case("approve/spend", True, p, after_submit, datum(balance, 1, [claim_a(p, [g1])]), [], [g1],
      t0 + 300_000, t0 + 400_000, ApproveClaim { claim_id: a0.claim_id })
    3 -> spend_case("payout/spend", True, p, datum(balance, 1, [a3]), datum(balance - 10_000_000, 1, []),
      [pay(key(claimant_a), 10_000_000)], [], t0 + 300_000, t0 + 400_000, PayoutClaim { claim_id: a3.claim_id })
    4 -> spend_case("cancel/spend", True, p, after_submit, datum(balance, 1, []), [], [claimant_a],
      t0 + 300_000, t0 + 400_000, CancelClaim { claim_id: a0.claim_id })
    5 -> spend_case("expire/spend", True, p, after_submit, datum(balance, 1, []), [], [],
      t0 + window_ms, t0 + window_ms + 100_000, ExpireClaim { claim_id: a0.claim_id })
    // Maximum-width states: two pending claims, base payout addresses, five guardians.
    6 -> spend_case("max_submit_second/spend", True, p,
      datum(balance, 1, [claim_wide_a(p, [g1, g2, g3, g4])]),
      datum(balance, 2, [claim_wide_a(p, [g1, g2, g3, g4]), claim_wide_b(p, [])]),
      [], [claimant_b], t0 + 200_000, t0 + 300_000, submit(1, claimant_b, base(claimant_b, stake_b), 12_000_000))
    7 -> spend_case("max_approve_fifth/spend", True, p,
      datum(balance, 2, [claim_wide_a(p, [g1, g2, g3, g4]), claim_wide_b(p, [g1, g2, g3, g4, g5])]),
      datum(balance, 2, [claim_wide_a(p, [g1, g2, g3, g4, g5]), claim_wide_b(p, [g1, g2, g3, g4, g5])]),
      [], [g5], t0 + 400_000, t0 + 500_000, ApproveClaim { claim_id: claim_wide_a(p, []).claim_id })
    8 -> spend_case("max_payout/spend", True, p,
      datum(balance, 2, [claim_wide_a(p, [g1, g2, g3, g4, g5]), claim_wide_b(p, [g1, g2, g3, g4, g5])]),
      datum(balance - 10_000_000, 2, [claim_wide_b(p, [g1, g2, g3, g4, g5])]),
      [pay(base(claimant_a, stake_a), 10_000_000)], [], t0 + 400_000, t0 + 500_000,
      PayoutClaim { claim_id: claim_wide_a(p, []).claim_id })
    // Adversarial cases.
    9 -> spend_case("reject/deposit_disabled", False, p, empty, datum(balance + 5_000_000, 0, []), [], [payer],
      t0, t0 + 100_000, Deposit { amount: 5_000_000, bridge_proof: #"00", payload_hash: evidence })
    10 -> spend_case("reject/payout_below_threshold", False, p, datum(balance, 1, [claim_a(p, [g1, g2])]),
      datum(balance - 10_000_000, 1, []), [pay(key(claimant_a), 10_000_000)], [], t0 + 300_000, t0 + 400_000,
      PayoutClaim { claim_id: a3.claim_id })
    11 -> spend_case("reject/payout_redirected", False, p, datum(balance, 1, [a3]), datum(balance - 10_000_000, 1, []),
      [pay(key(outsider), 10_000_000)], [], t0 + 300_000, t0 + 400_000, PayoutClaim { claim_id: a3.claim_id })
    12 -> spend_case("reject/approve_by_non_guardian", False, p, after_submit,
      datum(balance, 1, [claim_a(p, [outsider])]), [], [outsider], t0 + 300_000, t0 + 400_000,
      ApproveClaim { claim_id: a0.claim_id })
    13 -> spend_case_to("reject/fund_moved_to_other_script", False, p, after_submit, datum(balance, 1, [claim_a(p, [g1])]),
      [], [g1], t0 + 300_000, t0 + 400_000, ApproveClaim { claim_id: a0.claim_id },
      #"99999999999999999999999999999999999999999999999999999999")
    14 -> genesis_case("reject/genesis_wrong_seed", False, p, OutputReference { transaction_id: seed_tx, output_index: 1 })
    15 -> spend_case("reject/submit_replayed_nonce", False, p, after_submit,
      datum(balance, 2, [a0, claim(p, 0, claimant_a, key(claimant_a), 10_000_000, t0 + 300_000, [])]),
      [], [claimant_a], t0 + 300_000, t0 + 400_000, submit(0, claimant_a, key(claimant_a), 10_000_000))
    _ -> spend_case("reject/payout_after_expiry", False, p, datum(balance, 1, [a3]), datum(balance - 10_000_000, 1, []),
      [pay(key(claimant_a), 10_000_000)], [], t0 + window_ms, t0 + window_ms + 100_000,
      PayoutClaim { claim_id: a3.claim_id })
  }
}

pub fn case_cbor(policy: ByteArray, index: Int) -> ByteArray {
  cbor.serialise(case_at(policy, index))
}
