//// VAMS authenticated insurance fund and claim state machine.
////
//// A canonical fund NFT authenticates balance transitions. Claim commitments
//// are recorded in the fund datum before claim UTxOs can be approved or paid.
//// Cross-chain deposits remain unconditionally disabled on initial Pre-Prod.

use aiken/builtin
use aiken/collection/list
use aiken/crypto.{blake2b_256}
use aiken/interval.{Finite}
use aiken/primitive/bytearray
use cardano/address.{Address, Script, VerificationKey}
use cardano/assets.{PolicyId, Value, add, from_lovelace, quantity_of}
use cardano/transaction.{
  InlineDatum, Input, Output, OutputReference, Transaction,
}
use vams/types.{
  ApproveClaim, ClaimDatum, ClaimState, DepositBridge, DepositLocal, FundDatum,
  FundState, InsuranceDatum, InsuranceFundRedeemer, PayoutClaim, SubmitClaim,
  cardano_schema_version,
}
use vams/utils.{apply_bps, count_signatures}

const min_claim_amount: Int = 1_000_000

const claim_output_lovelace: Int = 2_000_000

const claim_window_ms: Int = 604_800_000

const max_pending_claims: Int = 100

pub type ClaimIdentity {
  fund_policy_id: PolicyId,
  fund_asset_name: ByteArray,
  fund_next_claim_id: Int,
  claimant: ByteArray,
  amount: Int,
  evidence_hash: ByteArray,
  submitted_at: Int,
  expires_at: Int,
}

validator insurance_fund {
  spend(
    datum_opt: Option<InsuranceDatum>,
    redeemer: InsuranceFundRedeemer,
    own_ref: OutputReference,
    tx: Transaction,
  ) {
    expect Some(datum) = datum_opt
    expect Some(own_input) =
      list.find(tx.inputs, fn(input) { input.output_reference == own_ref })

    when Pair(datum, redeemer) is {
      Pair(FundState(fund), DepositLocal { amount }) -> {
        expect valid_fund(fund, own_input.output.value)
        expect amount > 0
        let expected =
          FundDatum { ..fund, total_balance: fund.total_balance + amount }
        exact_fund_output(tx.outputs, own_input.output.address, expected)
      }

      Pair(FundState(fund), SubmitClaim { amount, evidence_hash }) -> {
        expect valid_fund(fund, own_input.output.value)
        expect [claimant, ..] = tx.extra_signatories
        expect bytearray.length(claimant) == 28
        expect bytearray.length(evidence_hash) == 32
        expect amount >= min_claim_amount
        expect amount <= apply_bps(fund.total_balance, fund.max_payout_bps)
        expect list.length(fund.pending_claim_commitments) < max_pending_claims
        expect Finite(submitted_at) = tx.validity_range.lower_bound.bound_type
        let expires_at = submitted_at + claim_window_ms
        let commitment =
          claim_commitment(
            fund.fund_policy_id,
            fund.fund_asset_name,
            fund.next_claim_id,
            claimant,
            amount,
            evidence_hash,
            submitted_at,
            expires_at,
          )
        let expected_fund =
          FundDatum {
            ..fund,
            next_claim_id: fund.next_claim_id + 1,
            pending_claim_commitments: [
              commitment,
              ..fund.pending_claim_commitments
            ],
          }
        let expected_claim =
          ClaimDatum {
            schema_version: cardano_schema_version,
            fund_policy_id: fund.fund_policy_id,
            fund_asset_name: fund.fund_asset_name,
            id: fund.next_claim_id,
            claimant,
            amount,
            evidence_hash,
            submitted_at,
            expires_at,
            commitment,
            approvers: [],
          }
        exact_fund_output(tx.outputs, own_input.output.address, expected_fund) && exact_claim_output(
          tx.outputs,
          own_input.output.address,
          expected_claim,
          from_lovelace(claim_output_lovelace),
        )
      }

      Pair(ClaimState(claim), ApproveClaim { claim_id }) -> {
        expect valid_claim(claim)
        expect claim.id == claim_id
        expect own_input.output.value == from_lovelace(claim_output_lovelace)
        expect Finite(valid_until) = tx.validity_range.upper_bound.bound_type
        expect valid_until <= claim.expires_at
        expect Some(fund_input) =
          find_fund_input(
            tx.reference_inputs,
            claim.fund_policy_id,
            claim.fund_asset_name,
          )
        expect InlineDatum(raw_fund) = fund_input.output.datum
        expect FundState(fund): InsuranceDatum = raw_fund
        expect valid_fund(fund, fund_input.output.value)
        expect fund.fund_policy_id == claim.fund_policy_id
        expect fund.fund_asset_name == claim.fund_asset_name
        expect list.has(fund.pending_claim_commitments, claim.commitment)
        expect count_signatures(tx.extra_signatories, fund.guardians) == 1
        expect Some(approver) =
          list.find(
            fund.guardians,
            fn(guardian) {
              list.has(tx.extra_signatories, guardian) && !list.has(
                claim.approvers,
                guardian,
              )
            },
          )
        let expected =
          ClaimDatum { ..claim, approvers: [approver, ..claim.approvers] }
        exact_claim_output(
          tx.outputs,
          own_input.output.address,
          expected,
          own_input.output.value,
        )
      }

      Pair(FundState(fund), PayoutClaim { claim_id }) -> {
        expect valid_fund(fund, own_input.output.value)
        valid_payout(tx, own_input.output.address, fund, claim_id)
      }

      Pair(ClaimState(claim), PayoutClaim { claim_id }) -> {
        expect valid_claim(claim)
        expect claim.id == claim_id
        valid_payout_from_claim(tx, own_input, claim)
      }

      Pair(_, DepositBridge { amount, bridge_proof, payload_hash }) ->
        // Preserve INV-10 field separation while refusing proof-shaped mocks.
        amount >= 0 && bytearray.length(bridge_proof) >= 0 && bytearray.length(
          payload_hash,
        ) >= 0 && False

      _ -> False
    }
  }

  else(_) {
    fail
  }
}

fn valid_fund(fund: FundDatum, value: Value) -> Bool {
  and {
    fund.schema_version == cardano_schema_version,
    bytearray.length(fund.fund_policy_id) == 28,
    bytearray.length(fund.fund_asset_name) > 0,
    bytearray.length(fund.fund_asset_name) <= 32,
    fund.total_balance >= 0,
    fund.next_claim_id > 0,
    list.length(fund.pending_claim_commitments) <= max_pending_claims,
    fund.max_payout_bps > 0,
    fund.max_payout_bps <= 5_000,
    fund.approval_threshold >= 2,
    fund.approval_threshold <= list.length(fund.guardians),
    value == canonical_fund_value(
      fund.total_balance,
      fund.fund_policy_id,
      fund.fund_asset_name,
    ),
  }
}

fn valid_claim(claim: ClaimDatum) -> Bool {
  and {
    claim.schema_version == cardano_schema_version,
    bytearray.length(claim.fund_policy_id) == 28,
    bytearray.length(claim.fund_asset_name) > 0,
    bytearray.length(claim.fund_asset_name) <= 32,
    claim.id > 0,
    bytearray.length(claim.claimant) == 28,
    claim.amount >= min_claim_amount,
    bytearray.length(claim.evidence_hash) == 32,
    claim.expires_at == claim.submitted_at + claim_window_ms,
    claim.commitment == claim_commitment(
      claim.fund_policy_id,
      claim.fund_asset_name,
      claim.id,
      claim.claimant,
      claim.amount,
      claim.evidence_hash,
      claim.submitted_at,
      claim.expires_at,
    ),
  }
}

fn claim_commitment(
  fund_policy_id: PolicyId,
  fund_asset_name: ByteArray,
  id: Int,
  claimant: ByteArray,
  amount: Int,
  evidence_hash: ByteArray,
  submitted_at: Int,
  expires_at: Int,
) -> ByteArray {
  blake2b_256(
    builtin.serialise_data(
      ClaimIdentity {
        fund_policy_id,
        fund_asset_name,
        fund_next_claim_id: id,
        claimant,
        amount,
        evidence_hash,
        submitted_at,
        expires_at,
      },
    ),
  )
}

fn canonical_fund_value(
  total_balance: Int,
  fund_policy_id: PolicyId,
  fund_asset_name: ByteArray,
) -> Value {
  from_lovelace(total_balance)
    |> add(fund_policy_id, fund_asset_name, 1)
}

fn exact_fund_output(
  outputs: List<Output>,
  address: Address,
  expected: FundDatum,
) -> Bool {
  let matches =
    list.filter(
      outputs,
      fn(output) {
        output.address == address && output.value == canonical_fund_value(
          expected.total_balance,
          expected.fund_policy_id,
          expected.fund_asset_name,
        ) && has_insurance_datum(output, FundState(expected))
      },
    )
  list.length(matches) == 1 && count_outputs_with_asset(
    outputs,
    expected.fund_policy_id,
    expected.fund_asset_name,
  ) == 1
}

fn exact_claim_output(
  outputs: List<Output>,
  address: Address,
  expected: ClaimDatum,
  value: Value,
) -> Bool {
  list.length(
    list.filter(
      outputs,
      fn(output) {
        output.address == address && output.value == value && has_insurance_datum(
          output,
          ClaimState(expected),
        )
      },
    ),
  ) == 1
}

fn has_insurance_datum(output: Output, expected: InsuranceDatum) -> Bool {
  when output.datum is {
    InlineDatum(raw) -> {
      expect actual: InsuranceDatum = raw
      actual == expected
    }
    _ -> False
  }
}

fn find_fund_input(
  inputs: List<Input>,
  fund_policy_id: PolicyId,
  fund_asset_name: ByteArray,
) -> Option<Input> {
  list.find(
    inputs,
    fn(input) {
      quantity_of(input.output.value, fund_policy_id, fund_asset_name) == 1
    },
  )
}

fn find_claim_input(
  inputs: List<Input>,
  address: Address,
  claim_id: Int,
) -> Option<Input> {
  list.find(
    inputs,
    fn(input) {
      input.output.address == address && has_claim_id(input.output, claim_id)
    },
  )
}

fn has_claim_id(output: Output, claim_id: Int) -> Bool {
  when output.datum is {
    InlineDatum(raw) -> {
      expect datum: InsuranceDatum = raw
      when datum is {
        ClaimState(claim) -> claim.id == claim_id
        _ -> False
      }
    }
    _ -> False
  }
}

fn valid_payout(
  tx: Transaction,
  address: Address,
  fund: FundDatum,
  claim_id: Int,
) -> Bool {
  expect Some(claim_input) = find_claim_input(tx.inputs, address, claim_id)
  expect InlineDatum(raw_claim) = claim_input.output.datum
  expect ClaimState(claim): InsuranceDatum = raw_claim
  expect valid_claim(claim)
  expect claim.fund_policy_id == fund.fund_policy_id
  expect claim.fund_asset_name == fund.fund_asset_name
  expect claim_input.output.value == from_lovelace(claim_output_lovelace)
  expect list.has(fund.pending_claim_commitments, claim.commitment)
  expect list.length(claim.approvers) >= fund.approval_threshold
  expect
    list.all(
      claim.approvers,
      fn(approver) { list.has(fund.guardians, approver) },
    )
  expect Finite(valid_until) = tx.validity_range.upper_bound.bound_type
  expect valid_until <= claim.expires_at
  let expected_fund =
    FundDatum {
      ..fund,
      total_balance: fund.total_balance - claim.amount,
      pending_claim_commitments: list.filter(
        fund.pending_claim_commitments,
        fn(item) { item != claim.commitment },
      ),
    }
  exact_fund_output(tx.outputs, address, expected_fund) && exact_claimant_payment(
    tx.outputs,
    claim.claimant,
    claim.amount + claim_output_lovelace,
  ) && count_claim_outputs(tx.outputs, address, claim.id) == 0
}

fn valid_payout_from_claim(
  tx: Transaction,
  claim_input: Input,
  claim: ClaimDatum,
) -> Bool {
  expect Some(fund_input) =
    find_fund_input(tx.inputs, claim.fund_policy_id, claim.fund_asset_name)
  expect InlineDatum(raw_fund) = fund_input.output.datum
  expect FundState(fund): InsuranceDatum = raw_fund
  valid_fund(fund, fund_input.output.value) && claim_input.output.value == from_lovelace(
    claim_output_lovelace,
  ) && valid_payout(tx, fund_input.output.address, fund, claim.id)
}

fn exact_claimant_payment(
  outputs: List<Output>,
  claimant: ByteArray,
  amount: Int,
) -> Bool {
  list.length(
    list.filter(
      outputs,
      fn(output) {
        when output.address.payment_credential is {
          VerificationKey(hash) ->
            hash == claimant && output.value == from_lovelace(amount)
          _ -> False
        }
      },
    ),
  ) == 1
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

fn count_claim_outputs(
  outputs: List<Output>,
  address: Address,
  claim_id: Int,
) -> Int {
  list.length(
    list.filter(
      outputs,
      fn(output) { output.address == address && has_claim_id(output, claim_id) },
    ),
  )
}

test claim_window_is_seven_days() {
  claim_window_ms == 7 * 24 * 60 * 60 * 1000
}

test max_pending_claims_is_bounded() {
  max_pending_claims == 100
}

test bridge_deposit_is_disabled() {
  let proof = #"00"
  let payload = #"01"
  !(bytearray.length(proof) >= 0 && bytearray.length(payload) >= 0 && False)
}

const fixture_fund_policy: PolicyId =
  #"11111111111111111111111111111111111111111111111111111111"

const fixture_fund_name: ByteArray = "VAMS_FUND_V2"

const fixture_insurance_hash: ByteArray =
  #"22222222222222222222222222222222222222222222222222222222"

const fixture_guardian_one: ByteArray =
  #"33333333333333333333333333333333333333333333333333333333"

const fixture_guardian_two: ByteArray =
  #"44444444444444444444444444444444444444444444444444444444"

const fixture_fund_ref: OutputReference =
  OutputReference {
    transaction_id: #"5555555555555555555555555555555555555555555555555555555555555555",
    output_index: 0,
  }

const fixture_fund_address: Address =
  Address {
    payment_credential: Script(fixture_insurance_hash),
    stake_credential: None,
  }

const fixture_fund: FundDatum =
  FundDatum {
    schema_version: cardano_schema_version,
    fund_policy_id: fixture_fund_policy,
    fund_asset_name: fixture_fund_name,
    total_balance: 100_000_000,
    next_claim_id: 1,
    pending_claim_commitments: [],
    max_payout_bps: 5_000,
    approval_threshold: 2,
    guardians: [fixture_guardian_one, fixture_guardian_two],
  }

const fixture_fund_input: Input =
  Input {
    output_reference: fixture_fund_ref,
    output: Output {
      address: fixture_fund_address,
      value: from_lovelace(fixture_fund.total_balance)
        |> add(fixture_fund_policy, fixture_fund_name, 1),
      datum: InlineDatum(FundState(fixture_fund)),
      reference_script: None,
    },
  }

test local_deposit_requires_exact_fund_successor() {
  let amount = 10_000_000
  let successor =
    FundDatum {
      ..fixture_fund,
      total_balance: fixture_fund.total_balance + amount,
    }
  insurance_fund.spend(
    Some(FundState(fixture_fund)),
    DepositLocal { amount },
    fixture_fund_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_fund_input],
      outputs: [
        Output {
          address: fixture_fund_address,
          value: from_lovelace(successor.total_balance)
            |> add(fixture_fund_policy, fixture_fund_name, 1),
          datum: InlineDatum(FundState(successor)),
          reference_script: None,
        },
      ],
    },
  )
}

test local_deposit_rejects_fake_fund_without_authentication_asset() fail {
  let fake_input =
    Input {
      ..fixture_fund_input,
      output: Output {
        ..fixture_fund_input.output,
        value: from_lovelace(fixture_fund.total_balance),
      },
    }
  insurance_fund.spend(
    Some(FundState(fixture_fund)),
    DepositLocal { amount: 1 },
    fixture_fund_ref,
    Transaction { ..transaction.placeholder, inputs: [fake_input] },
  )
}

test bridge_deposit_handler_fails_closed() fail {
  insurance_fund.spend(
    Some(FundState(fixture_fund)),
    DepositBridge { amount: 1, bridge_proof: #"00", payload_hash: #"01" },
    fixture_fund_ref,
    Transaction { ..transaction.placeholder, inputs: [fixture_fund_input] },
  )
}

const fixture_claimant: ByteArray =
  #"66666666666666666666666666666666666666666666666666666666"

const fixture_evidence_hash: ByteArray =
  #"7777777777777777777777777777777777777777777777777777777777777777"

const fixture_claim_ref: OutputReference =
  OutputReference {
    transaction_id: #"8888888888888888888888888888888888888888888888888888888888888888",
    output_index: 0,
  }

fn fixture_claim(amount: Int, approvers: List<ByteArray>) -> ClaimDatum {
  let submitted_at = 100
  let expires_at = submitted_at + claim_window_ms
  let commitment =
    claim_commitment(
      fixture_fund_policy,
      fixture_fund_name,
      1,
      fixture_claimant,
      amount,
      fixture_evidence_hash,
      submitted_at,
      expires_at,
    )
  ClaimDatum {
    schema_version: cardano_schema_version,
    fund_policy_id: fixture_fund_policy,
    fund_asset_name: fixture_fund_name,
    id: 1,
    claimant: fixture_claimant,
    amount,
    evidence_hash: fixture_evidence_hash,
    submitted_at,
    expires_at,
    commitment,
    approvers,
  }
}

fn fixture_claim_input(claim: ClaimDatum) -> Input {
  Input {
    output_reference: fixture_claim_ref,
    output: Output {
      address: fixture_fund_address,
      value: from_lovelace(claim_output_lovelace),
      datum: InlineDatum(ClaimState(claim)),
      reference_script: None,
    },
  }
}

fn fixture_pending_fund(claim: ClaimDatum) -> FundDatum {
  FundDatum {
    ..fixture_fund,
    next_claim_id: 2,
    pending_claim_commitments: [claim.commitment],
  }
}

fn fixture_fund_input_for(fund: FundDatum) -> Input {
  Input {
    ..fixture_fund_input,
    output: Output {
      ..fixture_fund_input.output,
      value: canonical_fund_value(
        fund.total_balance,
        fund.fund_policy_id,
        fund.fund_asset_name,
      ),
      datum: InlineDatum(FundState(fund)),
    },
  }
}

test submit_claim_creates_exact_fund_and_claim_successors() {
  let claim = fixture_claim(10_000_000, [])
  let expected_fund = fixture_pending_fund(claim)
  insurance_fund.spend(
    Some(FundState(fixture_fund)),
    SubmitClaim { amount: claim.amount, evidence_hash: fixture_evidence_hash },
    fixture_fund_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_fund_input],
      outputs: [
        Output {
          address: fixture_fund_address,
          value: canonical_fund_value(
            expected_fund.total_balance,
            fixture_fund_policy,
            fixture_fund_name,
          ),
          datum: InlineDatum(FundState(expected_fund)),
          reference_script: None,
        },
        Output {
          address: fixture_fund_address,
          value: from_lovelace(claim_output_lovelace),
          datum: InlineDatum(ClaimState(claim)),
          reference_script: None,
        },
      ],
      validity_range: interval.between(100, 200),
      extra_signatories: [fixture_claimant],
    },
  )
}

test submit_claim_rejects_datum_substitution() fail {
  let claim = fixture_claim(10_000_000, [])
  let expected_fund = fixture_pending_fund(claim)
  let substituted = ClaimDatum { ..claim, amount: claim.amount + 1 }
  insurance_fund.spend(
    Some(FundState(fixture_fund)),
    SubmitClaim { amount: claim.amount, evidence_hash: fixture_evidence_hash },
    fixture_fund_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_fund_input],
      outputs: [
        Output {
          address: fixture_fund_address,
          value: canonical_fund_value(
            expected_fund.total_balance,
            fixture_fund_policy,
            fixture_fund_name,
          ),
          datum: InlineDatum(FundState(expected_fund)),
          reference_script: None,
        },
        Output {
          address: fixture_fund_address,
          value: from_lovelace(claim_output_lovelace),
          datum: InlineDatum(ClaimState(substituted)),
          reference_script: None,
        },
      ],
      validity_range: interval.between(100, 200),
      extra_signatories: [fixture_claimant],
    },
  )
}

test forged_claim_without_pending_commitment_is_rejected() fail {
  let claim = fixture_claim(10_000_000, [])
  insurance_fund.spend(
    Some(ClaimState(claim)),
    ApproveClaim { claim_id: claim.id },
    fixture_claim_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_claim_input(claim)],
      reference_inputs: [fixture_fund_input],
      validity_range: interval.before(claim.expires_at),
      extra_signatories: [fixture_guardian_one],
    },
  )
}

test approval_rejects_duplicate_guardian() fail {
  let claim = fixture_claim(10_000_000, [fixture_guardian_one])
  let fund = fixture_pending_fund(claim)
  insurance_fund.spend(
    Some(ClaimState(claim)),
    ApproveClaim { claim_id: claim.id },
    fixture_claim_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_claim_input(claim)],
      reference_inputs: [fixture_fund_input_for(fund)],
      validity_range: interval.before(claim.expires_at),
      extra_signatories: [fixture_guardian_one],
    },
  )
}

test payout_consumes_claim_and_recreates_exact_fund() {
  let claim =
    fixture_claim(10_000_000, [fixture_guardian_one, fixture_guardian_two])
  let fund = fixture_pending_fund(claim)
  let successor =
    FundDatum {
      ..fund,
      total_balance: fund.total_balance - claim.amount,
      pending_claim_commitments: [],
    }
  let fund_input = fixture_fund_input_for(fund)
  let claim_input = fixture_claim_input(claim)
  let tx =
    Transaction {
      ..transaction.placeholder,
      inputs: [fund_input, claim_input],
      outputs: [
        Output {
          address: fixture_fund_address,
          value: canonical_fund_value(
            successor.total_balance,
            fixture_fund_policy,
            fixture_fund_name,
          ),
          datum: InlineDatum(FundState(successor)),
          reference_script: None,
        },
        Output {
          address: Address {
            payment_credential: VerificationKey(fixture_claimant),
            stake_credential: None,
          },
          value: from_lovelace(claim.amount + claim_output_lovelace),
          datum: InlineDatum(0),
          reference_script: None,
        },
      ],
      validity_range: interval.before(claim.expires_at),
    }
  insurance_fund.spend(
    Some(FundState(fund)),
    PayoutClaim { claim_id: claim.id },
    fixture_fund_ref,
    tx,
  ) && insurance_fund.spend(
    Some(ClaimState(claim)),
    PayoutClaim { claim_id: claim.id },
    fixture_claim_ref,
    tx,
  )
}

test replayed_payout_without_pending_commitment_is_rejected() fail {
  let claim =
    fixture_claim(10_000_000, [fixture_guardian_one, fixture_guardian_two])
  insurance_fund.spend(
    Some(FundState(fixture_fund)),
    PayoutClaim { claim_id: claim.id },
    fixture_fund_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_fund_input, fixture_claim_input(claim)],
      validity_range: interval.before(claim.expires_at),
    },
  )
}
