//// VAMS authenticated insurance-custody state machine.
////
//// The mint and spend handlers intentionally share one parameterized script.
//// Its script hash is therefore also the singleton state-token policy id,
//// avoiding a circular policy/validator hash dependency.

use aiken/cbor
use aiken/collection/dict
use aiken/collection/list
use aiken/crypto.{blake2b_256}
use aiken/fuzz
use aiken/interval.{Finite}
use aiken/primitive/bytearray
use cardano/address.{Address, Script, VerificationKey}
use cardano/assets.{PolicyId}
use cardano/transaction.{
  InlineDatum, Input, Output, OutputReference, Transaction,
}
use vams/types.{
  ApproveClaim, CancelClaim, ClaimIdentityPayload, ClaimRecord, Deposit,
  ExpireClaim, FundDatumV2, InitializeFund, InsuranceFundRedeemer,
  InsuranceStateRedeemer, PayoutClaim, SubmitClaim,
}
use vams/utils.{apply_bps, is_signed_by}

const fund_schema_version: Int = 2

const maximum_payout_bps: Int = 5000

const min_claim_amount: Int = 1_000_000

const claim_window_ms: Int = 604_800_000

const max_submission_interval_ms: Int = 300_000

const max_guardians: Int = 5

// The largest legitimate signer set is the five configured guardians plus the
// claimant. Keep this independent of the current datum guardian count so
// signer-list work remains bounded when policy parameters evolve.
const max_extra_signatories: Int = 6

const max_pending_claims: Int = 2

const max_transaction_inputs: Int = 16

const max_transaction_outputs: Int = 16

const max_fund_value_assets: Int = 16

const max_fund_datum_bytes: Int = 896

const max_asset_name_bytes: Int = 32

const verification_key_hash_bytes: Int = 28

const digest_bytes: Int = 32

const claim_identity_domain: ByteArray = "VAMS_INSURANCE_CLAIM_V2"

validator insurance_fund(
  genesis_ref: OutputReference,
  state_asset_name: ByteArray,
  configured_guardians: List<ByteArray>,
  configured_threshold: Int,
  configured_policy_epoch: Int,
  configured_max_payout_bps: Int,
) {
  mint(redeemer: InsuranceStateRedeemer, policy_id: PolicyId, tx: Transaction) {
    when redeemer is {
      InitializeFund ->
        validate_genesis(
          genesis_ref,
          state_asset_name,
          configured_guardians,
          configured_threshold,
          configured_policy_epoch,
          configured_max_payout_bps,
          policy_id,
          tx,
        )
    }
  }

  spend(
    datum_opt: Option<FundDatumV2>,
    redeemer: InsuranceFundRedeemer,
    own_ref: OutputReference,
    tx: Transaction,
  ) {
    expect Some(datum) = datum_opt
    validate_spend(
      state_asset_name,
      configured_guardians,
      configured_threshold,
      configured_policy_epoch,
      configured_max_payout_bps,
      datum,
      redeemer,
      own_ref,
      tx,
    )
  }

  else(_) {
    fail
  }
}

fn validate_genesis(
  genesis_ref: OutputReference,
  state_asset_name: ByteArray,
  configured_guardians: List<ByteArray>,
  configured_threshold: Int,
  configured_policy_epoch: Int,
  configured_max_payout_bps: Int,
  policy_id: PolicyId,
  tx: Transaction,
) -> Bool {
  expect finite_interval(tx, max_submission_interval_ms)
  expect bounded_extra_signatories(tx)
  expect valid_state_asset_name(state_asset_name)
  expect bounded_transaction_shape(tx)
  expect count_inputs_with_ref(tx.inputs, genesis_ref) == 1
  expect assets.quantity_of(tx.mint, policy_id, state_asset_name) == 1
  expect
    dict.to_pairs(assets.tokens(tx.mint, policy_id)) == [
      Pair(state_asset_name, 1),
    ]
  expect count_inputs_with_asset(tx.inputs, policy_id, state_asset_name) == 0
  expect [fund_output] =
    outputs_with_asset(tx.outputs, policy_id, state_asset_name)
  expect fund_output.address.payment_credential == Script(policy_id)
  expect fund_output.address.stake_credential == None
  expect assets.quantity_of(fund_output.value, policy_id, state_asset_name) == 1
  expect InlineDatum(raw_datum) = fund_output.datum
  expect datum: FundDatumV2 = raw_datum
  expect datum.schema_version == fund_schema_version
  expect datum.total_balance == assets.lovelace_of(fund_output.value)
  expect datum.next_claim_nonce == 0
  expect datum.pending_claims == []
  expect datum.policy_epoch == configured_policy_epoch
  expect datum.max_payout_bps == configured_max_payout_bps
  expect datum.approval_threshold == configured_threshold
  expect datum.guardians == configured_guardians
  expect bounded_fund_value(fund_output.value)
  valid_fund_state(datum, policy_id, state_asset_name)
}

fn validate_spend(
  state_asset_name: ByteArray,
  configured_guardians: List<ByteArray>,
  configured_threshold: Int,
  configured_policy_epoch: Int,
  configured_max_payout_bps: Int,
  datum: FundDatumV2,
  redeemer: InsuranceFundRedeemer,
  own_ref: OutputReference,
  tx: Transaction,
) -> Bool {
  expect valid_state_asset_name(state_asset_name)
  expect bounded_transaction_shape(tx)
  expect bounded_extra_signatories(tx)
  expect Some(own_input) =
    list.find(tx.inputs, fn(input) { input.output_reference == own_ref })
  expect Script(policy_id) = own_input.output.address.payment_credential
  expect
    assets.quantity_of(own_input.output.value, policy_id, state_asset_name) == 1
  expect count_inputs_with_asset(tx.inputs, policy_id, state_asset_name) == 1
  expect dict.to_pairs(assets.tokens(tx.mint, policy_id)) == []
  expect [continuing_output] =
    outputs_with_asset(tx.outputs, policy_id, state_asset_name)
  expect continuing_output.address == own_input.output.address
  expect
    assets.quantity_of(continuing_output.value, policy_id, state_asset_name) == 1
  expect InlineDatum(raw_next) = continuing_output.datum
  expect next: FundDatumV2 = raw_next
  expect datum.total_balance == assets.lovelace_of(own_input.output.value)
  expect next.total_balance == assets.lovelace_of(continuing_output.value)
  expect bounded_fund_value(own_input.output.value)
  expect bounded_fund_value(continuing_output.value)
  expect
    assets.without_lovelace(own_input.output.value) == assets.without_lovelace(
      continuing_output.value,
    )
  expect valid_fund_state(datum, policy_id, state_asset_name)
  expect valid_fund_state(next, policy_id, state_asset_name)
  expect datum.guardians == configured_guardians
  expect datum.approval_threshold == configured_threshold
  expect datum.policy_epoch == configured_policy_epoch
  expect datum.max_payout_bps == configured_max_payout_bps
  expect immutable_policy(datum, next)

  when redeemer is {
    Deposit { amount: _, bridge_proof: _, payload_hash: _ } -> False
    SubmitClaim {
      claim_nonce,
      claimant_vkh,
      payout_address,
      amount,
      evidence_hash,
    } ->
      validate_submit(
        datum,
        next,
        policy_id,
        state_asset_name,
        claim_nonce,
        claimant_vkh,
        payout_address,
        amount,
        evidence_hash,
        tx,
      )
    ApproveClaim { claim_id } -> validate_approve(datum, next, claim_id, tx)
    PayoutClaim { claim_id } ->
      validate_payout(datum, next, claim_id, own_input, continuing_output, tx)
    CancelClaim { claim_id } -> validate_cancel(datum, next, claim_id, tx)
    ExpireClaim { claim_id } -> validate_expire(datum, next, claim_id, tx)
  }
}

fn validate_submit(
  datum: FundDatumV2,
  next: FundDatumV2,
  policy_id: PolicyId,
  state_asset_name: ByteArray,
  claim_nonce: Int,
  claimant_vkh: ByteArray,
  payout_address: Address,
  amount: Int,
  evidence_hash: ByteArray,
  tx: Transaction,
) -> Bool {
  expect finite_interval(tx, max_submission_interval_ms)
  expect Finite(submitted_at) = tx.validity_range.lower_bound.bound_type
  let expires_at = submitted_at + claim_window_ms
  expect claim_nonce == datum.next_claim_nonce
  expect bytearray.length(claimant_vkh) == verification_key_hash_bytes
  expect payout_address_matches_claimant(payout_address, claimant_vkh)
  expect bytearray.length(evidence_hash) == digest_bytes
  expect is_signed_by(tx.extra_signatories, claimant_vkh)
  expect amount >= min_claim_amount
  expect amount <= apply_bps(datum.total_balance, datum.max_payout_bps)
  expect list.length(datum.pending_claims) < max_pending_claims
  let claim_id =
    derive_claim_id(
      policy_id,
      state_asset_name,
      datum.policy_epoch,
      claim_nonce,
      claimant_vkh,
      payout_address,
      amount,
      evidence_hash,
      submitted_at,
      expires_at,
    )
  let claim =
    ClaimRecord {
      claim_id,
      claim_nonce,
      claimant_vkh,
      payout_address,
      amount,
      evidence_hash,
      submitted_at,
      expires_at,
      policy_epoch: datum.policy_epoch,
      approvers: [],
    }
  expect next.total_balance == datum.total_balance
  expect next.next_claim_nonce == datum.next_claim_nonce + 1
  next.pending_claims == list.concat(datum.pending_claims, [claim])
}

fn validate_approve(
  datum: FundDatumV2,
  next: FundDatumV2,
  claim_id: ByteArray,
  tx: Transaction,
) -> Bool {
  expect finite_interval(tx, max_submission_interval_ms)
  expect bytearray.length(claim_id) == digest_bytes
  expect [claim] = claims_with_id(datum.pending_claims, claim_id)
  expect finite_before_or_at(tx, claim.expires_at)
  expect [guardian] =
    list.filter(
      datum.guardians,
      fn(candidate) { list.has(tx.extra_signatories, candidate) },
    )
  expect !list.has(claim.approvers, guardian)
  let approved =
    ClaimRecord {
      claim_id: claim.claim_id,
      claim_nonce: claim.claim_nonce,
      claimant_vkh: claim.claimant_vkh,
      payout_address: claim.payout_address,
      amount: claim.amount,
      evidence_hash: claim.evidence_hash,
      submitted_at: claim.submitted_at,
      expires_at: claim.expires_at,
      policy_epoch: claim.policy_epoch,
      approvers: list.concat(claim.approvers, [guardian]),
    }
  expect next.total_balance == datum.total_balance
  expect next.next_claim_nonce == datum.next_claim_nonce
  next.pending_claims == replace_claim(datum.pending_claims, claim_id, approved)
}

fn validate_payout(
  datum: FundDatumV2,
  next: FundDatumV2,
  claim_id: ByteArray,
  own_input: Input,
  continuing_output: Output,
  tx: Transaction,
) -> Bool {
  expect finite_interval(tx, max_submission_interval_ms)
  expect bytearray.length(claim_id) == digest_bytes
  expect [claim] = claims_with_id(datum.pending_claims, claim_id)
  expect finite_strictly_before(tx, claim.expires_at)
  expect list.length(claim.approvers) >= datum.approval_threshold
  expect claim.amount >= min_claim_amount
  expect claim.amount <= apply_bps(datum.total_balance, datum.max_payout_bps)
  expect next.total_balance == datum.total_balance - claim.amount
  expect next.next_claim_nonce == datum.next_claim_nonce
  expect next.pending_claims == remove_claim(datum.pending_claims, claim_id)
  expect
    assets.lovelace_of(continuing_output.value) == assets.lovelace_of(
      own_input.output.value,
    ) - claim.amount
  expect [payout_output] =
    list.filter(
      tx.outputs,
      fn(output) { output.address == claim.payout_address },
    )
  expect assets.lovelace_of(payout_output.value) == claim.amount
  expect assets.without_lovelace(payout_output.value) == assets.zero
  address_net_lovelace(tx, claim.payout_address) >= claim.amount
}

fn validate_cancel(
  datum: FundDatumV2,
  next: FundDatumV2,
  claim_id: ByteArray,
  tx: Transaction,
) -> Bool {
  expect finite_interval(tx, max_submission_interval_ms)
  expect bytearray.length(claim_id) == digest_bytes
  expect [claim] = claims_with_id(datum.pending_claims, claim_id)
  expect finite_strictly_before(tx, claim.expires_at)
  expect is_signed_by(tx.extra_signatories, claim.claimant_vkh)
  expect next.total_balance == datum.total_balance
  expect next.next_claim_nonce == datum.next_claim_nonce
  next.pending_claims == remove_claim(datum.pending_claims, claim_id)
}

fn validate_expire(
  datum: FundDatumV2,
  next: FundDatumV2,
  claim_id: ByteArray,
  tx: Transaction,
) -> Bool {
  expect finite_interval(tx, max_submission_interval_ms)
  expect bytearray.length(claim_id) == digest_bytes
  expect [claim] = claims_with_id(datum.pending_claims, claim_id)
  expect finite_at_or_after(tx, claim.expires_at)
  expect next.total_balance == datum.total_balance
  expect next.next_claim_nonce == datum.next_claim_nonce
  next.pending_claims == remove_claim(datum.pending_claims, claim_id)
}

pub fn derive_claim_id(
  state_policy_id: ByteArray,
  state_asset_name: ByteArray,
  policy_epoch: Int,
  claim_nonce: Int,
  claimant_vkh: ByteArray,
  payout_address: Address,
  amount: Int,
  evidence_hash: ByteArray,
  submitted_at: Int,
  expires_at: Int,
) -> ByteArray {
  ClaimIdentityPayload {
    domain: claim_identity_domain,
    state_policy_id,
    state_asset_name,
    policy_epoch,
    claim_nonce,
    claimant_vkh,
    payout_address,
    amount,
    evidence_hash,
    submitted_at,
    expires_at,
  }
    |> cbor.serialise
    |> blake2b_256
}

fn valid_fund_state(
  datum: FundDatumV2,
  policy_id: PolicyId,
  state_asset_name: ByteArray,
) -> Bool {
  and {
    within_fund_datum_limit(cbor.serialise(datum)),
    valid_policy(datum),
    datum.next_claim_nonce >= 0,
    list.length(datum.pending_claims) <= max_pending_claims,
    claims_are_unique(datum.pending_claims),
    list.all(
      datum.pending_claims,
      fn(claim) { valid_claim(claim, datum, policy_id, state_asset_name) },
    ),
  }
}

fn valid_policy(datum: FundDatumV2) -> Bool {
  and {
    datum.schema_version == fund_schema_version,
    datum.total_balance >= 0,
    datum.policy_epoch >= 0,
    datum.max_payout_bps > 0,
    datum.max_payout_bps <= maximum_payout_bps,
    !list.is_empty(datum.guardians),
    list.length(datum.guardians) <= max_guardians,
    list.length(list.unique(datum.guardians)) == list.length(datum.guardians),
    list.all(
      datum.guardians,
      fn(guardian) { bytearray.length(guardian) == verification_key_hash_bytes },
    ),
    datum.approval_threshold > 0,
    datum.approval_threshold <= list.length(datum.guardians),
  }
}

fn valid_state_asset_name(state_asset_name: ByteArray) -> Bool {
  bytearray.length(state_asset_name) > 0 && bytearray.length(state_asset_name) <= max_asset_name_bytes
}

fn bounded_transaction_shape(tx: Transaction) -> Bool {
  list.length(tx.inputs) <= max_transaction_inputs && list.length(tx.outputs) <= max_transaction_outputs
}

fn bounded_extra_signatories(tx: Transaction) -> Bool {
  list.length(tx.extra_signatories) <= max_extra_signatories && list.length(
    list.unique(tx.extra_signatories),
  ) == list.length(tx.extra_signatories)
}

fn bounded_fund_value(value: assets.Value) -> Bool {
  list.length(
    assets.flatten_with(
      value,
      fn(policy_id, asset_name, _quantity) {
        if policy_id == #"" && asset_name == #"" {
          None
        } else {
          Some(1)
        }
      },
    ),
  ) <= max_fund_value_assets
}

fn within_fund_datum_limit(serialised: ByteArray) -> Bool {
  bytearray.length(serialised) <= max_fund_datum_bytes
}

fn valid_claim(
  claim: ClaimRecord,
  datum: FundDatumV2,
  policy_id: PolicyId,
  state_asset_name: ByteArray,
) -> Bool {
  and {
    bytearray.length(claim.claim_id) == digest_bytes,
    claim.claim_nonce >= 0,
    claim.claim_nonce < datum.next_claim_nonce,
    bytearray.length(claim.claimant_vkh) == verification_key_hash_bytes,
    payout_address_matches_claimant(claim.payout_address, claim.claimant_vkh),
    claim.amount >= min_claim_amount,
    bytearray.length(claim.evidence_hash) == digest_bytes,
    claim.expires_at == claim.submitted_at + claim_window_ms,
    claim.policy_epoch == datum.policy_epoch,
    list.length(list.unique(claim.approvers)) == list.length(claim.approvers),
    list.length(claim.approvers) <= list.length(datum.guardians),
    list.all(
      claim.approvers,
      fn(approver) { list.has(datum.guardians, approver) },
    ),
    claim.claim_id == derive_claim_id(
      policy_id,
      state_asset_name,
      claim.policy_epoch,
      claim.claim_nonce,
      claim.claimant_vkh,
      claim.payout_address,
      claim.amount,
      claim.evidence_hash,
      claim.submitted_at,
      claim.expires_at,
    ),
  }
}

fn immutable_policy(before: FundDatumV2, after: FundDatumV2) -> Bool {
  and {
    before.schema_version == after.schema_version,
    before.policy_epoch == after.policy_epoch,
    before.max_payout_bps == after.max_payout_bps,
    before.approval_threshold == after.approval_threshold,
    before.guardians == after.guardians,
  }
}

fn payout_address_matches_claimant(
  payout_address: Address,
  claimant_vkh: ByteArray,
) -> Bool {
  when payout_address.payment_credential is {
    VerificationKey(hash) -> hash == claimant_vkh
    Script(_) -> False
  }
}

fn finite_interval(tx: Transaction, max_span: Int) -> Bool {
  when
    (
      tx.validity_range.lower_bound.bound_type,
      tx.validity_range.upper_bound.bound_type,
    )
  is {
    (Finite(lower), Finite(upper)) ->
      upper >= lower && upper - lower <= max_span
    _ -> False
  }
}

fn finite_before_or_at(tx: Transaction, deadline: Int) -> Bool {
  when
    (
      tx.validity_range.lower_bound.bound_type,
      tx.validity_range.upper_bound.bound_type,
    )
  is {
    (Finite(lower), Finite(upper)) ->
      upper >= lower && lower < deadline && upper <= deadline
    _ -> False
  }
}

fn finite_strictly_before(tx: Transaction, deadline: Int) -> Bool {
  when
    (
      tx.validity_range.lower_bound.bound_type,
      tx.validity_range.upper_bound.bound_type,
    )
  is {
    (Finite(lower), Finite(upper)) ->
      upper >= lower && lower < deadline && upper < deadline
    _ -> False
  }
}

fn finite_at_or_after(tx: Transaction, deadline: Int) -> Bool {
  when
    (
      tx.validity_range.lower_bound.bound_type,
      tx.validity_range.upper_bound.bound_type,
    )
  is {
    (Finite(lower), Finite(upper)) -> upper >= lower && lower >= deadline
    _ -> False
  }
}

fn claims_are_unique(claims: List<ClaimRecord>) -> Bool {
  let ids = list.map(claims, fn(claim) { claim.claim_id })
  let nonces = list.map(claims, fn(claim) { claim.claim_nonce })
  list.length(list.unique(ids)) == list.length(ids) && list.length(
    list.unique(nonces),
  ) == list.length(nonces)
}

fn claims_with_id(
  claims: List<ClaimRecord>,
  claim_id: ByteArray,
) -> List<ClaimRecord> {
  list.filter(claims, fn(claim) { claim.claim_id == claim_id })
}

fn replace_claim(
  claims: List<ClaimRecord>,
  claim_id: ByteArray,
  replacement: ClaimRecord,
) -> List<ClaimRecord> {
  list.map(
    claims,
    fn(claim) {
      if claim.claim_id == claim_id {
        replacement
      } else {
        claim
      }
    },
  )
}

fn remove_claim(
  claims: List<ClaimRecord>,
  claim_id: ByteArray,
) -> List<ClaimRecord> {
  list.filter(claims, fn(claim) { claim.claim_id != claim_id })
}

fn outputs_with_asset(
  outputs: List<Output>,
  policy_id: PolicyId,
  asset_name: ByteArray,
) -> List<Output> {
  list.filter(
    outputs,
    fn(output) { assets.quantity_of(output.value, policy_id, asset_name) != 0 },
  )
}

fn count_inputs_with_asset(
  inputs: List<Input>,
  policy_id: PolicyId,
  asset_name: ByteArray,
) -> Int {
  list.count(
    inputs,
    fn(input) {
      assets.quantity_of(input.output.value, policy_id, asset_name) != 0
    },
  )
}

fn count_inputs_with_ref(
  inputs: List<Input>,
  output_reference: OutputReference,
) -> Int {
  list.count(inputs, fn(input) { input.output_reference == output_reference })
}

fn address_net_lovelace(tx: Transaction, address: Address) -> Int {
  let paid =
    list.foldl(
      tx.outputs,
      0,
      fn(output, total) {
        if output.address == address {
          total + assets.lovelace_of(output.value)
        } else {
          total
        }
      },
    )
  let spent =
    list.foldl(
      tx.inputs,
      0,
      fn(input, total) {
        if input.output.address == address {
          total + assets.lovelace_of(input.output.value)
        } else {
          total
        }
      },
    )
  paid - spent
}

test max_payout_is_50_percent() {
  maximum_payout_bps == 5000
}

test min_claim_is_1_ada() {
  min_claim_amount == 1_000_000
}

test claim_window_is_7_days() {
  claim_window_ms == 7 * 24 * 60 * 60 * 1000
}

// Test fixtures construct complete ledger contexts. Expected state transitions
// use explicit records and equations rather than transition builders.

const test_policy_id: ByteArray =
  #"11111111111111111111111111111111111111111111111111111111"

const test_other_policy: ByteArray =
  #"22222222222222222222222222222222222222222222222222222222"

const test_state_name: ByteArray = #"56414d535f494e535552414e43455f5354415445"

const test_guardian_one: ByteArray =
  #"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

const test_guardian_two: ByteArray =
  #"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

const test_guardian_three: ByteArray =
  #"cccccccccccccccccccccccccccccccccccccccccccccccccccccccc"

const test_claimant: ByteArray =
  #"dddddddddddddddddddddddddddddddddddddddddddddddddddddddd"

const test_evidence: ByteArray =
  #"eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"

const test_balance: Int = 20_000_000

const test_claim_amount: Int = 4_000_000

const test_submitted_at: Int = 1_700_000_000_000

const test_expiry: Int = 1_700_604_800_000

fn test_ref(index: Int) -> OutputReference {
  OutputReference {
    transaction_id: #"0101010101010101010101010101010101010101010101010101010101010101",
    output_index: index,
  }
}

fn test_guardians() -> List<ByteArray> {
  [test_guardian_one, test_guardian_two, test_guardian_three]
}

fn test_guardian_count(count: Int) -> List<ByteArray> {
  list.map(
    list.range(1, count),
    fn(index) {
      bytearray.from_int_big_endian(index, verification_key_hash_bytes)
    },
  )
}

fn test_state_address() -> Address {
  address.from_script(test_policy_id)
}

fn test_claimant_address() -> Address {
  address.from_verification_key(test_claimant)
}

fn test_value(lovelace: Int) -> assets.Value {
  assets.from_lovelace(lovelace)
    |> assets.add(test_policy_id, test_state_name, 1)
    |> assets.add(test_other_policy, #"01", 7)
}

fn test_claim(approvers: List<ByteArray>) -> ClaimRecord {
  test_claim_at(0, approvers)
}

fn test_claim_at(nonce: Int, approvers: List<ByteArray>) -> ClaimRecord {
  test_claim_details(
    nonce,
    test_claimant_address(),
    test_claim_amount,
    test_evidence,
    approvers,
  )
}

fn test_claim_details(
  nonce: Int,
  payout_address: Address,
  amount: Int,
  evidence_hash: ByteArray,
  approvers: List<ByteArray>,
) -> ClaimRecord {
  let claim_id =
    derive_claim_id(
      test_policy_id,
      test_state_name,
      7,
      nonce,
      test_claimant,
      payout_address,
      amount,
      evidence_hash,
      test_submitted_at,
      test_expiry,
    )
  ClaimRecord {
    claim_id,
    claim_nonce: nonce,
    claimant_vkh: test_claimant,
    payout_address,
    amount,
    evidence_hash,
    submitted_at: test_submitted_at,
    expires_at: test_expiry,
    policy_epoch: 7,
    approvers,
  }
}

test claim_identity_vector_matches_independent_cbor() {
  derive_claim_id(
    test_policy_id,
    test_state_name,
    7,
    0,
    test_claimant,
    test_claimant_address(),
    test_claim_amount,
    test_evidence,
    test_submitted_at,
    test_expiry,
  ) == #"35d18a32277854e33159c1658a3abfb18661b2d82e9e02b014a69ff6e53e2466"
}

fn test_datum(
  total_balance: Int,
  next_claim_nonce: Int,
  pending_claims: List<ClaimRecord>,
) -> FundDatumV2 {
  FundDatumV2 {
    schema_version: fund_schema_version,
    total_balance,
    next_claim_nonce,
    pending_claims,
    policy_epoch: 7,
    max_payout_bps: 5000,
    approval_threshold: 2,
    guardians: test_guardians(),
  }
}

fn test_output(
  output_address: Address,
  value: assets.Value,
  datum: FundDatumV2,
) -> Output {
  Output {
    address: output_address,
    value,
    datum: InlineDatum(datum),
    reference_script: None,
  }
}

fn test_state_input(datum: FundDatumV2) -> Input {
  Input {
    output_reference: test_ref(0),
    output: test_output(
      test_state_address(),
      test_value(datum.total_balance),
      datum,
    ),
  }
}

fn test_tx(
  before: FundDatumV2,
  after: FundDatumV2,
  extra_outputs: List<Output>,
  signers: List<ByteArray>,
  lower: Int,
  upper: Int,
) -> Transaction {
  Transaction {
    ..transaction.placeholder,
    inputs: [test_state_input(before)],
    outputs: [
      test_output(test_state_address(), test_value(after.total_balance), after),
      ..extra_outputs
    ],
    validity_range: interval.between(lower, upper),
    extra_signatories: signers,
  }
}

fn test_submit_redeemer() -> InsuranceFundRedeemer {
  SubmitClaim {
    claim_nonce: 0,
    claimant_vkh: test_claimant,
    payout_address: test_claimant_address(),
    amount: test_claim_amount,
    evidence_hash: test_evidence,
  }
}

fn run_test_spend(
  before: FundDatumV2,
  after: FundDatumV2,
  redeemer: InsuranceFundRedeemer,
  tx: Transaction,
) -> Bool {
  validate_spend(
    test_state_name,
    test_guardians(),
    2,
    7,
    5000,
    before,
    redeemer,
    test_ref(0),
    tx,
  )
}

test valid_genesis_context() {
  let initial = test_datum(test_balance, 0, [])
  let output =
    test_output(test_state_address(), test_value(test_balance), initial)
  let seed =
    Input {
      output_reference: test_ref(9),
      output: Output {
        address: address.from_verification_key(test_guardian_one),
        value: assets.from_lovelace(2_000_000),
        datum: transaction.NoDatum,
        reference_script: None,
      },
    }
  let tx =
    Transaction {
      ..transaction.placeholder,
      inputs: [seed],
      outputs: [output],
      mint: assets.from_asset(test_policy_id, test_state_name, 1),
      validity_range: interval.between(
        test_submitted_at,
        test_submitted_at + max_submission_interval_ms,
      ),
    }
  validate_genesis(
    test_ref(9),
    test_state_name,
    test_guardians(),
    2,
    7,
    5000,
    test_policy_id,
    tx,
  )
}

test genesis_interval_below_limit_accepts() {
  finite_interval(
    Transaction {
      ..transaction.placeholder,
      validity_range: interval.between(
        test_submitted_at,
        test_submitted_at + max_submission_interval_ms - 1,
      ),
    },
    max_submission_interval_ms,
  )
}

test genesis_interval_at_limit_accepts() {
  finite_interval(
    Transaction {
      ..transaction.placeholder,
      validity_range: interval.between(
        test_submitted_at,
        test_submitted_at + max_submission_interval_ms,
      ),
    },
    max_submission_interval_ms,
  )
}

test genesis_interval_above_limit_rejects() {
  !finite_interval(
    Transaction {
      ..transaction.placeholder,
      validity_range: interval.between(
        test_submitted_at,
        test_submitted_at + max_submission_interval_ms + 1,
      ),
    },
    max_submission_interval_ms,
  )
}

test genesis_unbounded_interval_rejects() {
  !finite_interval(transaction.placeholder, max_submission_interval_ms)
}

test genesis_reversed_interval_rejects() {
  !finite_interval(
    Transaction {
      ..transaction.placeholder,
      validity_range: interval.between(test_submitted_at + 1, test_submitted_at),
    },
    max_submission_interval_ms,
  )
}

test extra_signatories_at_limit_accepts() {
  bounded_extra_signatories(
    Transaction {
      ..transaction.placeholder,
      extra_signatories: [
        test_guardian_one,
        test_guardian_two,
        test_guardian_three,
        bytearray.from_int_big_endian(4, verification_key_hash_bytes),
        bytearray.from_int_big_endian(5, verification_key_hash_bytes),
        test_claimant,
      ],
    },
  )
}

test extra_signatories_above_limit_rejects() fail {
  bounded_extra_signatories(
    Transaction {
      ..transaction.placeholder,
      extra_signatories: [
        test_guardian_one,
        test_guardian_two,
        test_guardian_three,
        bytearray.from_int_big_endian(4, verification_key_hash_bytes),
        bytearray.from_int_big_endian(5, verification_key_hash_bytes),
        test_claimant,
        bytearray.from_int_big_endian(6, verification_key_hash_bytes),
      ],
    },
  )
}

test duplicate_extra_signatories_rejects() fail {
  bounded_extra_signatories(
    Transaction {
      ..transaction.placeholder,
      extra_signatories: [test_guardian_one, test_guardian_one],
    },
  )
}

test valid_submit_context() {
  let before = test_datum(test_balance, 0, [])
  let after = test_datum(test_balance, 1, [test_claim([])])
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_claimant],
      test_submitted_at,
      test_submitted_at + max_submission_interval_ms,
    )
  run_test_spend(before, after, test_submit_redeemer(), tx)
}

test submit_without_claimant_signature_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let after = test_datum(test_balance, 1, [test_claim([])])
  let tx =
    test_tx(
      before,
      after,
      [],
      [],
      test_submitted_at,
      test_submitted_at + max_submission_interval_ms,
    )
  run_test_spend(before, after, test_submit_redeemer(), tx)
}

test valid_approve_context() {
  let claim = test_claim([])
  let before = test_datum(test_balance, 1, [claim])
  let after = test_datum(test_balance, 1, [test_claim([test_guardian_one])])
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_guardian_one],
      test_submitted_at + 1,
      test_submitted_at + 2,
    )
  run_test_spend(before, after, ApproveClaim { claim_id: claim.claim_id }, tx)
}

test valid_payout_context() {
  let claim = test_claim([test_guardian_one, test_guardian_two])
  let before = test_datum(test_balance, 1, [claim])
  let after = test_datum(test_balance - test_claim_amount, 1, [])
  let payout =
    Output {
      address: test_claimant_address(),
      value: assets.from_lovelace(test_claim_amount),
      datum: transaction.NoDatum,
      reference_script: None,
    }
  let tx =
    test_tx(
      before,
      after,
      [payout],
      [],
      test_submitted_at + 1,
      test_submitted_at + 2,
    )
  run_test_spend(before, after, PayoutClaim { claim_id: claim.claim_id }, tx)
}

test valid_cancel_context() {
  let claim = test_claim([])
  let before = test_datum(test_balance, 1, [claim])
  let after = test_datum(test_balance, 1, [])
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_claimant],
      test_submitted_at + 1,
      test_submitted_at + 2,
    )
  run_test_spend(before, after, CancelClaim { claim_id: claim.claim_id }, tx)
}

test valid_expire_context() {
  let claim = test_claim([])
  let before = test_datum(test_balance, 1, [claim])
  let after = test_datum(test_balance, 1, [])
  let tx = test_tx(before, after, [], [], test_expiry, test_expiry + 1)
  run_test_spend(before, after, ExpireClaim { claim_id: claim.claim_id }, tx)
}

test deposit_empty_proof_rejects() {
  let datum = test_datum(test_balance, 0, [])
  let tx =
    test_tx(datum, datum, [], [], test_submitted_at, test_submitted_at + 1)
  !run_test_spend(
    datum,
    datum,
    Deposit { amount: 1, bridge_proof: #"", payload_hash: #"" },
    tx,
  )
}

test deposit_structural_proof_rejects() {
  let datum = test_datum(test_balance, 0, [])
  let tx =
    test_tx(datum, datum, [], [], test_submitted_at, test_submitted_at + 1)
  !run_test_spend(
    datum,
    datum,
    Deposit {
      amount: 5_000_000,
      bridge_proof: #"abababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababab",
      payload_hash: #"cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd",
    },
    tx,
  )
}

test prop_deposit_always_rejects(
  ((amount, bridge_proof), payload_hash) via fuzz.both(
    fuzz.both(fuzz.int(), fuzz.bytearray()),
    fuzz.bytearray(),
  ),
) {
  let datum = test_datum(test_balance, 0, [])
  let tx =
    test_tx(datum, datum, [], [], test_submitted_at, test_submitted_at + 1)
  !run_test_spend(
    datum,
    datum,
    Deposit { amount, bridge_proof, payload_hash },
    tx,
  )
}

test missing_state_token_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let after = test_datum(test_balance, 1, [test_claim([])])
  let bad_output =
    test_output(
      test_state_address(),
      assets.from_lovelace(test_balance)
        |> assets.add(test_other_policy, #"01", 7),
      after,
    )
  let tx =
    Transaction {
      ..test_tx(
        before,
        after,
        [],
        [test_claimant],
        test_submitted_at,
        test_submitted_at + 1,
      ),
      outputs: [bad_output],
    }
  run_test_spend(before, after, test_submit_redeemer(), tx)
}

test duplicated_state_token_output_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let after = test_datum(test_balance, 1, [test_claim([])])
  let state_output =
    test_output(test_state_address(), test_value(test_balance), after)
  let tx =
    Transaction {
      ..test_tx(
        before,
        after,
        [],
        [test_claimant],
        test_submitted_at,
        test_submitted_at + 1,
      ),
      outputs: [state_output, state_output],
    }
  run_test_spend(before, after, test_submit_redeemer(), tx)
}

test substituted_state_token_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let after = test_datum(test_balance, 1, [test_claim([])])
  let bad_value =
    assets.from_lovelace(test_balance)
      |> assets.add(test_other_policy, test_state_name, 1)
      |> assets.add(test_other_policy, #"01", 7)
  let tx =
    Transaction {
      ..test_tx(
        before,
        after,
        [],
        [test_claimant],
        test_submitted_at,
        test_submitted_at + 1,
      ),
      outputs: [test_output(test_state_address(), bad_value, after)],
    }
  run_test_spend(before, after, test_submit_redeemer(), tx)
}

test normal_state_mint_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let after = test_datum(test_balance, 1, [test_claim([])])
  let tx =
    Transaction {
      ..test_tx(
        before,
        after,
        [],
        [test_claimant],
        test_submitted_at,
        test_submitted_at + 1,
      ),
      mint: assets.from_asset(test_policy_id, test_state_name, 1),
    }
  run_test_spend(before, after, test_submit_redeemer(), tx)
}

test normal_state_burn_rejects() fail {
  let datum = test_datum(test_balance, 1, [test_claim([])])
  let tx =
    Transaction {
      ..test_tx(
        datum,
        datum,
        [],
        [],
        test_submitted_at + 1,
        test_submitted_at + 2,
      ),
      mint: assets.from_asset(test_policy_id, test_state_name, -1),
    }
  run_test_spend(
    datum,
    datum,
    CancelClaim { claim_id: test_claim([]).claim_id },
    tx,
  )
}

test missing_continuing_output_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let after = test_datum(test_balance, 1, [test_claim([])])
  let tx =
    Transaction {
      ..test_tx(
        before,
        after,
        [],
        [test_claimant],
        test_submitted_at,
        test_submitted_at + 1,
      ),
      outputs: [],
    }
  run_test_spend(before, after, test_submit_redeemer(), tx)
}

test redirected_fund_value_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let after = test_datum(test_balance - 1_000_000, 1, [test_claim([])])
  let redirected =
    Output {
      address: address.from_verification_key(test_guardian_one),
      value: assets.from_lovelace(1_000_000),
      datum: transaction.NoDatum,
      reference_script: None,
    }
  let tx =
    test_tx(
      before,
      after,
      [redirected],
      [test_claimant],
      test_submitted_at,
      test_submitted_at + 1,
    )
  run_test_spend(before, after, test_submit_redeemer(), tx)
}

test altered_non_ada_fund_asset_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let after = test_datum(test_balance, 1, [test_claim([])])
  let bad_value =
    assets.from_lovelace(test_balance)
      |> assets.add(test_policy_id, test_state_name, 1)
      |> assets.add(test_other_policy, #"01", 8)
  let tx =
    Transaction {
      ..test_tx(
        before,
        after,
        [],
        [test_claimant],
        test_submitted_at,
        test_submitted_at + 1,
      ),
      outputs: [test_output(test_state_address(), bad_value, after)],
    }
  run_test_spend(before, after, test_submit_redeemer(), tx)
}

test output_datum_balance_mismatch_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let after = test_datum(test_balance, 1, [test_claim([])])
  let tx =
    Transaction {
      ..test_tx(
        before,
        after,
        [],
        [test_claimant],
        test_submitted_at,
        test_submitted_at + 1,
      ),
      outputs: [
        test_output(test_state_address(), test_value(test_balance - 1), after),
      ],
    }
  run_test_spend(before, after, test_submit_redeemer(), tx)
}

test input_datum_balance_mismatch_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let after = test_datum(test_balance, 1, [test_claim([])])
  let bad_input =
    Input {
      output_reference: test_ref(0),
      output: test_output(
        test_state_address(),
        test_value(test_balance - 1),
        before,
      ),
    }
  let tx =
    Transaction {
      ..test_tx(
        before,
        after,
        [],
        [test_claimant],
        test_submitted_at,
        test_submitted_at + 1,
      ),
      inputs: [bad_input],
    }
  run_test_spend(before, after, test_submit_redeemer(), tx)
}

test duplicated_claim_identity_rejects() fail {
  let claim = test_claim([])
  let datum = test_datum(test_balance, 1, [claim, claim])
  let tx =
    test_tx(
      datum,
      datum,
      [],
      [test_claimant],
      test_submitted_at + 1,
      test_submitted_at + 2,
    )
  run_test_spend(datum, datum, CancelClaim { claim_id: claim.claim_id }, tx)
}

test duplicated_claim_nonce_rejects() fail {
  let first = test_claim([])
  let second =
    test_claim_details(
      0,
      test_claimant_address(),
      test_claim_amount + 1,
      test_evidence,
      [],
    )
  let datum = test_datum(test_balance, 1, [first, second])
  let tx =
    test_tx(
      datum,
      datum,
      [],
      [test_claimant],
      test_submitted_at + 1,
      test_submitted_at + 2,
    )
  run_test_spend(datum, datum, CancelClaim { claim_id: first.claim_id }, tx)
}

test guardian_policy_mutation_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let valid_after = test_datum(test_balance, 1, [test_claim([])])
  let after = FundDatumV2 { ..valid_after, guardians: [test_guardian_one] }
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_claimant],
      test_submitted_at,
      test_submitted_at + 1,
    )
  run_test_spend(before, after, test_submit_redeemer(), tx)
}

test threshold_mutation_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let valid_after = test_datum(test_balance, 1, [test_claim([])])
  let after = FundDatumV2 { ..valid_after, approval_threshold: 1 }
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_claimant],
      test_submitted_at,
      test_submitted_at + 1,
    )
  run_test_spend(before, after, test_submit_redeemer(), tx)
}

test payout_cap_mutation_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let valid_after = test_datum(test_balance, 1, [test_claim([])])
  let after = FundDatumV2 { ..valid_after, max_payout_bps: 4000 }
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_claimant],
      test_submitted_at,
      test_submitted_at + 1,
    )
  run_test_spend(before, after, test_submit_redeemer(), tx)
}

test policy_epoch_mutation_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let valid_after = test_datum(test_balance, 1, [test_claim([])])
  let after = FundDatumV2 { ..valid_after, policy_epoch: 8 }
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_claimant],
      test_submitted_at,
      test_submitted_at + 1,
    )
  run_test_spend(before, after, test_submit_redeemer(), tx)
}

test wrong_submission_nonce_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let after = test_datum(test_balance, 1, [test_claim([])])
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_claimant],
      test_submitted_at,
      test_submitted_at + 1,
    )
  run_test_spend(
    before,
    after,
    SubmitClaim {
      claim_nonce: 1,
      claimant_vkh: test_claimant,
      payout_address: test_claimant_address(),
      amount: test_claim_amount,
      evidence_hash: test_evidence,
    },
    tx,
  )
}

test wrong_derived_claim_identity_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let valid_claim = test_claim([])
  let wrong_claim =
    ClaimRecord {
      ..valid_claim,
      claim_id: #"ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
    }
  let after = test_datum(test_balance, 1, [wrong_claim])
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_claimant],
      test_submitted_at,
      test_submitted_at + 1,
    )
  run_test_spend(before, after, test_submit_redeemer(), tx)
}

test malformed_evidence_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let malformed =
    test_claim_details(0, test_claimant_address(), test_claim_amount, #"ee", [])
  let after = test_datum(test_balance, 1, [malformed])
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_claimant],
      test_submitted_at,
      test_submitted_at + 1,
    )
  run_test_spend(
    before,
    after,
    SubmitClaim {
      claim_nonce: 0,
      claimant_vkh: test_claimant,
      payout_address: test_claimant_address(),
      amount: test_claim_amount,
      evidence_hash: #"ee",
    },
    tx,
  )
}

test payout_address_not_owned_by_claimant_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let wrong_address = address.from_verification_key(test_guardian_one)
  let malformed =
    test_claim_details(0, wrong_address, test_claim_amount, test_evidence, [])
  let after = test_datum(test_balance, 1, [malformed])
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_claimant],
      test_submitted_at,
      test_submitted_at + 1,
    )
  run_test_spend(
    before,
    after,
    SubmitClaim {
      claim_nonce: 0,
      claimant_vkh: test_claimant,
      payout_address: wrong_address,
      amount: test_claim_amount,
      evidence_hash: test_evidence,
    },
    tx,
  )
}

test excessive_submission_amount_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let excessive =
    test_claim_details(
      0,
      test_claimant_address(),
      10_000_001,
      test_evidence,
      [],
    )
  let after = test_datum(test_balance, 1, [excessive])
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_claimant],
      test_submitted_at,
      test_submitted_at + 1,
    )
  run_test_spend(
    before,
    after,
    SubmitClaim {
      claim_nonce: 0,
      claimant_vkh: test_claimant,
      payout_address: test_claimant_address(),
      amount: 10_000_001,
      evidence_hash: test_evidence,
    },
    tx,
  )
}

test overlong_submission_interval_rejects() fail {
  let before = test_datum(test_balance, 0, [])
  let after = test_datum(test_balance, 1, [test_claim([])])
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_claimant],
      test_submitted_at,
      test_submitted_at + max_submission_interval_ms + 1,
    )
  run_test_spend(before, after, test_submit_redeemer(), tx)
}

test unknown_claim_approval_rejects() fail {
  let claim = test_claim([])
  let before = test_datum(test_balance, 1, [claim])
  let after = test_datum(test_balance, 1, [test_claim([test_guardian_one])])
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_guardian_one],
      test_submitted_at + 1,
      test_submitted_at + 2,
    )
  run_test_spend(
    before,
    after,
    ApproveClaim {
      claim_id: #"ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
    },
    tx,
  )
}

test duplicate_guardian_approval_rejects() fail {
  let claim = test_claim([test_guardian_one])
  let before = test_datum(test_balance, 1, [claim])
  let duplicated = test_claim([test_guardian_one, test_guardian_one])
  let after = test_datum(test_balance, 1, [duplicated])
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_guardian_one],
      test_submitted_at + 1,
      test_submitted_at + 2,
    )
  run_test_spend(before, after, ApproveClaim { claim_id: claim.claim_id }, tx)
}

test unauthorized_guardian_approval_rejects() fail {
  let claim = test_claim([])
  let before = test_datum(test_balance, 1, [claim])
  let after = before
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_claimant],
      test_submitted_at + 1,
      test_submitted_at + 2,
    )
  run_test_spend(before, after, ApproveClaim { claim_id: claim.claim_id }, tx)
}

test multiple_guardians_in_one_approval_rejects() fail {
  let claim = test_claim([])
  let before = test_datum(test_balance, 1, [claim])
  let after = test_datum(test_balance, 1, [test_claim([test_guardian_one])])
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_guardian_one, test_guardian_two],
      test_submitted_at + 1,
      test_submitted_at + 2,
    )
  run_test_spend(before, after, ApproveClaim { claim_id: claim.claim_id }, tx)
}

test payout_without_threshold_rejects() fail {
  let claim = test_claim([test_guardian_one])
  let before = test_datum(test_balance, 1, [claim])
  let after = test_datum(test_balance - test_claim_amount, 1, [])
  let payout =
    Output {
      address: test_claimant_address(),
      value: assets.from_lovelace(test_claim_amount),
      datum: transaction.NoDatum,
      reference_script: None,
    }
  let tx =
    test_tx(
      before,
      after,
      [payout],
      [],
      test_submitted_at + 1,
      test_submitted_at + 2,
    )
  run_test_spend(before, after, PayoutClaim { claim_id: claim.claim_id }, tx)
}

test excessive_payout_at_execution_rejects() fail {
  let claim = test_claim([test_guardian_one, test_guardian_two])
  let before = test_datum(6_000_000, 1, [claim])
  let after = test_datum(2_000_000, 1, [])
  let payout =
    Output {
      address: test_claimant_address(),
      value: assets.from_lovelace(test_claim_amount),
      datum: transaction.NoDatum,
      reference_script: None,
    }
  let tx =
    test_tx(
      before,
      after,
      [payout],
      [],
      test_submitted_at + 1,
      test_submitted_at + 2,
    )
  run_test_spend(before, after, PayoutClaim { claim_id: claim.claim_id }, tx)
}

test substituted_payout_recipient_rejects() fail {
  let claim = test_claim([test_guardian_one, test_guardian_two])
  let before = test_datum(test_balance, 1, [claim])
  let after = test_datum(test_balance - test_claim_amount, 1, [])
  let payout =
    Output {
      address: address.from_verification_key(test_guardian_one),
      value: assets.from_lovelace(test_claim_amount),
      datum: transaction.NoDatum,
      reference_script: None,
    }
  let tx =
    test_tx(
      before,
      after,
      [payout],
      [],
      test_submitted_at + 1,
      test_submitted_at + 2,
    )
  run_test_spend(before, after, PayoutClaim { claim_id: claim.claim_id }, tx)
}

test substituted_payout_amount_rejects() fail {
  let claim = test_claim([test_guardian_one, test_guardian_two])
  let before = test_datum(test_balance, 1, [claim])
  let after = test_datum(test_balance - test_claim_amount, 1, [])
  let payout =
    Output {
      address: test_claimant_address(),
      value: assets.from_lovelace(test_claim_amount - 1),
      datum: transaction.NoDatum,
      reference_script: None,
    }
  let tx =
    test_tx(
      before,
      after,
      [payout],
      [],
      test_submitted_at + 1,
      test_submitted_at + 2,
    )
  run_test_spend(before, after, PayoutClaim { claim_id: claim.claim_id }, tx)
}

test payout_with_non_lovelace_asset_rejects() fail {
  let claim = test_claim([test_guardian_one, test_guardian_two])
  let before = test_datum(test_balance, 1, [claim])
  let after = test_datum(test_balance - test_claim_amount, 1, [])
  let payout =
    Output {
      address: test_claimant_address(),
      value: assets.from_lovelace(test_claim_amount)
        |> assets.add(test_other_policy, #"02", 1),
      datum: transaction.NoDatum,
      reference_script: None,
    }
  let tx =
    test_tx(
      before,
      after,
      [payout],
      [],
      test_submitted_at + 1,
      test_submitted_at + 2,
    )
  run_test_spend(before, after, PayoutClaim { claim_id: claim.claim_id }, tx)
}

test claimant_funded_output_rejects() fail {
  let claim = test_claim([test_guardian_one, test_guardian_two])
  let before = test_datum(test_balance, 1, [claim])
  let after = test_datum(test_balance - test_claim_amount, 1, [])
  let claimant_input =
    Input {
      output_reference: test_ref(2),
      output: Output {
        address: test_claimant_address(),
        value: assets.from_lovelace(test_claim_amount),
        datum: transaction.NoDatum,
        reference_script: None,
      },
    }
  let payout =
    Output {
      address: test_claimant_address(),
      value: assets.from_lovelace(test_claim_amount),
      datum: transaction.NoDatum,
      reference_script: None,
    }
  let base_tx =
    test_tx(
      before,
      after,
      [payout],
      [],
      test_submitted_at + 1,
      test_submitted_at + 2,
    )
  let tx =
    Transaction {
      ..base_tx,
      inputs: [test_state_input(before), claimant_input],
    }
  run_test_spend(before, after, PayoutClaim { claim_id: claim.claim_id }, tx)
}

test expired_approval_rejects() fail {
  let claim = test_claim([])
  let before = test_datum(test_balance, 1, [claim])
  let after = test_datum(test_balance, 1, [test_claim([test_guardian_one])])
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_guardian_one],
      test_expiry,
      test_expiry + 1,
    )
  run_test_spend(before, after, ApproveClaim { claim_id: claim.claim_id }, tx)
}

test approval_ending_at_expiry_is_valid() {
  let claim = test_claim([])
  let before = test_datum(test_balance, 1, [claim])
  let after = test_datum(test_balance, 1, [test_claim([test_guardian_one])])
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_guardian_one],
      test_expiry - 1,
      test_expiry,
    )
  run_test_spend(before, after, ApproveClaim { claim_id: claim.claim_id }, tx)
}

test payout_ending_at_expiry_rejects() fail {
  let claim = test_claim([test_guardian_one, test_guardian_two])
  let before = test_datum(test_balance, 1, [claim])
  let after = test_datum(test_balance - test_claim_amount, 1, [])
  let payout =
    Output {
      address: test_claimant_address(),
      value: assets.from_lovelace(test_claim_amount),
      datum: transaction.NoDatum,
      reference_script: None,
    }
  let tx = test_tx(before, after, [payout], [], test_expiry - 1, test_expiry)
  run_test_spend(before, after, PayoutClaim { claim_id: claim.claim_id }, tx)
}

test cancel_ending_at_expiry_rejects() fail {
  let claim = test_claim([])
  let before = test_datum(test_balance, 1, [claim])
  let after = test_datum(test_balance, 1, [])
  let tx =
    test_tx(before, after, [], [test_claimant], test_expiry - 1, test_expiry)
  run_test_spend(before, after, CancelClaim { claim_id: claim.claim_id }, tx)
}

test expired_payout_rejects() fail {
  let claim = test_claim([test_guardian_one, test_guardian_two])
  let before = test_datum(test_balance, 1, [claim])
  let after = test_datum(test_balance - test_claim_amount, 1, [])
  let payout =
    Output {
      address: test_claimant_address(),
      value: assets.from_lovelace(test_claim_amount),
      datum: transaction.NoDatum,
      reference_script: None,
    }
  let tx = test_tx(before, after, [payout], [], test_expiry, test_expiry + 1)
  run_test_spend(before, after, PayoutClaim { claim_id: claim.claim_id }, tx)
}

test premature_expiry_rejects() fail {
  let claim = test_claim([])
  let before = test_datum(test_balance, 1, [claim])
  let after = test_datum(test_balance, 1, [])
  let tx = test_tx(before, after, [], [], test_expiry - 2, test_expiry - 1)
  run_test_spend(before, after, ExpireClaim { claim_id: claim.claim_id }, tx)
}

test non_claimant_cancel_rejects() fail {
  let claim = test_claim([])
  let before = test_datum(test_balance, 1, [claim])
  let after = test_datum(test_balance, 1, [])
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_guardian_one],
      test_submitted_at + 1,
      test_submitted_at + 2,
    )
  run_test_spend(before, after, CancelClaim { claim_id: claim.claim_id }, tx)
}

test repeated_payout_rejects() fail {
  let settled_id = test_claim([]).claim_id
  let datum = test_datum(test_balance, 1, [])
  let tx =
    test_tx(datum, datum, [], [], test_submitted_at + 1, test_submitted_at + 2)
  run_test_spend(datum, datum, PayoutClaim { claim_id: settled_id }, tx)
}

test payout_retaining_selected_claim_rejects() fail {
  let claim = test_claim([test_guardian_one, test_guardian_two])
  let before = test_datum(test_balance, 1, [claim])
  let after =
    FundDatumV2 { ..before, total_balance: test_balance - test_claim_amount }
  let payout =
    Output {
      address: test_claimant_address(),
      value: assets.from_lovelace(test_claim_amount),
      datum: transaction.NoDatum,
      reference_script: None,
    }
  let tx =
    test_tx(
      before,
      after,
      [payout],
      [],
      test_submitted_at + 1,
      test_submitted_at + 2,
    )
  run_test_spend(before, after, PayoutClaim { claim_id: claim.claim_id }, tx)
}

test repeated_cancel_rejects() fail {
  let settled_id = test_claim([]).claim_id
  let datum = test_datum(test_balance, 1, [])
  let tx =
    test_tx(
      datum,
      datum,
      [],
      [test_claimant],
      test_submitted_at + 1,
      test_submitted_at + 2,
    )
  run_test_spend(datum, datum, CancelClaim { claim_id: settled_id }, tx)
}

test repeated_expiry_rejects() fail {
  let settled_id = test_claim([]).claim_id
  let datum = test_datum(test_balance, 1, [])
  let tx = test_tx(datum, datum, [], [], test_expiry, test_expiry + 1)
  run_test_spend(datum, datum, ExpireClaim { claim_id: settled_id }, tx)
}

test claim_capacity_overflow_rejects() fail {
  let claims =
    list.map(
      list.range(0, max_pending_claims - 1),
      fn(nonce) { test_claim_at(nonce, []) },
    )
  let before = test_datum(test_balance, max_pending_claims, claims)
  let overflow = test_claim_at(max_pending_claims, [])
  let after =
    test_datum(
      test_balance,
      max_pending_claims + 1,
      list.concat(claims, [overflow]),
    )
  let tx =
    test_tx(
      before,
      after,
      [],
      [test_claimant],
      test_submitted_at,
      test_submitted_at + 1,
    )
  run_test_spend(
    before,
    after,
    SubmitClaim {
      claim_nonce: max_pending_claims,
      claimant_vkh: test_claimant,
      payout_address: test_claimant_address(),
      amount: test_claim_amount,
      evidence_hash: test_evidence,
    },
    tx,
  )
}

test guardian_cap_below_accepts() {
  let datum =
    FundDatumV2 {
      ..test_datum(test_balance, 0, []),
      guardians: test_guardian_count(max_guardians - 1),
    }
  valid_policy(datum)
}

test guardian_cap_at_accepts() {
  let datum =
    FundDatumV2 {
      ..test_datum(test_balance, 0, []),
      guardians: test_guardian_count(max_guardians),
    }
  valid_policy(datum)
}

test guardian_cap_above_rejects() {
  let datum =
    FundDatumV2 {
      ..test_datum(test_balance, 0, []),
      guardians: test_guardian_count(max_guardians + 1),
    }
  !valid_policy(datum)
}

test fund_datum_byte_cap_boundaries() {
  and {
    within_fund_datum_limit(
      bytearray.from_int_big_endian(0, max_fund_datum_bytes - 1),
    ),
    within_fund_datum_limit(
      bytearray.from_int_big_endian(0, max_fund_datum_bytes),
    ),
    !within_fund_datum_limit(
      bytearray.from_int_big_endian(0, max_fund_datum_bytes + 1),
    ),
  }
}

test genesis_missing_seed_rejects() fail {
  let initial = test_datum(test_balance, 0, [])
  let tx =
    Transaction {
      ..transaction.placeholder,
      outputs: [
        test_output(test_state_address(), test_value(test_balance), initial),
      ],
      mint: assets.from_asset(test_policy_id, test_state_name, 1),
    }
  validate_genesis(
    test_ref(9),
    test_state_name,
    test_guardians(),
    2,
    7,
    5000,
    test_policy_id,
    tx,
  )
}

test genesis_duplicate_seed_rejects() fail {
  let initial = test_datum(test_balance, 0, [])
  let seed =
    Input {
      output_reference: test_ref(9),
      output: Output {
        address: address.from_verification_key(test_guardian_one),
        value: assets.from_lovelace(2_000_000),
        datum: transaction.NoDatum,
        reference_script: None,
      },
    }
  let tx =
    Transaction {
      ..transaction.placeholder,
      inputs: [seed, seed],
      outputs: [
        test_output(test_state_address(), test_value(test_balance), initial),
      ],
      mint: assets.from_asset(test_policy_id, test_state_name, 1),
    }
  validate_genesis(
    test_ref(9),
    test_state_name,
    test_guardians(),
    2,
    7,
    5000,
    test_policy_id,
    tx,
  )
}

test genesis_non_singleton_mint_rejects() fail {
  let initial = test_datum(test_balance, 0, [])
  let seed =
    Input {
      output_reference: test_ref(9),
      output: Output {
        address: address.from_verification_key(test_guardian_one),
        value: assets.from_lovelace(2_000_000),
        datum: transaction.NoDatum,
        reference_script: None,
      },
    }
  let tx =
    Transaction {
      ..transaction.placeholder,
      inputs: [seed],
      outputs: [
        test_output(test_state_address(), test_value(test_balance), initial),
      ],
      mint: assets.from_asset(test_policy_id, test_state_name, 2),
    }
  validate_genesis(
    test_ref(9),
    test_state_name,
    test_guardians(),
    2,
    7,
    5000,
    test_policy_id,
    tx,
  )
}
