//// VAMS Insurance Fund Validator
////
//// Custodies protocol insurance capital on Cardano. Receives bridge
//// deposits from InsuranceFundProxy on Polygon, and pays out claims
//// approved by DAO guardian multisig.
////
//// Flow:
////   1. Deposit — ICB bridge delivers accumulated fees/slashes
////   2. SubmitClaim — anyone can file a claim with evidence
////   3. ApproveClaim — guardians approve (threshold required)
////   4. PayoutClaim — releases funds after approval threshold met

use aiken/collection/list
use aiken/primitive/bytearray
use cardano/assets
use cardano/transaction.{OutputReference, Transaction}
use vams/icb.{verify_bridge_proof}
use vams/types.{
  ApproveClaim, Deposit, FundDatum, InsuranceFundRedeemer, PayoutClaim,
  SubmitClaim,
}
use vams/utils.{apply_bps, count_signatures}

// ═══════════════════ Constants ═══════════════════

/// Maximum payout as percentage of fund (50%)
const max_payout_bps: Int = 5000

/// Minimum claim amount (1 ADA in lovelace)
const min_claim_amount: Int = 1_000_000

/// Claim window: 7 days (in milliseconds)
const claim_window_ms: Int = 604_800_000

// ═══════════════════ Fund Validator ═══════════════════

validator insurance_fund {
  spend(
    datum_opt: Option<FundDatum>,
    redeemer: InsuranceFundRedeemer,
    own_ref: OutputReference,
    tx: Transaction,
  ) {
    expect Some(datum) = datum_opt

    when redeemer is {
      // ── Deposit from bridge ──
      // AUDIT FIX: AK02 — Separated bridge_proof from payload_hash to
      // eliminate tautological proof verification.
      Deposit { amount, bridge_proof, payload_hash } -> {
        // Amount must be positive
        expect amount > 0

        // Payload hash must be a proper 32-byte SHA-256 digest
        expect bytearray.length(payload_hash) == 32

        // Verify bridge proof against the expected payload hash
        expect verify_bridge_proof(bridge_proof, payload_hash)

        True
      }

      // ── Submit a new claim ──
      SubmitClaim { amount, evidence_hash } -> {
        // Claimant must sign the transaction
        expect list.length(tx.extra_signatories) >= 1

        // Claim amount must be within bounds
        expect amount >= min_claim_amount

        // Claim must not exceed maximum payout
        let max_amount = apply_bps(datum.total_balance, max_payout_bps)
        expect amount <= max_amount

        // Evidence must be provided
        expect bytearray.length(evidence_hash) > 0

        // ── AUDIT FIX: AK12 ──
        // Verify the actual UTXO value >= datum.total_balance to prevent
        // an attacker from passing an inflated datum and extracting more.
        expect Some(own_input) =
          list.find(tx.inputs, fn(input) { input.output_reference == own_ref })
        let actual_lovelace = assets.lovelace_of(own_input.output.value)
        expect actual_lovelace >= datum.total_balance

        True
      }

      // ── Guardian approves a claim ──
      // AUDIT FIX: AK06 — Deduplicate guardian approvals.
      // The FundDatum.guardians list is the authoritative set of approvers.
      // We allow exactly 1 guardian signature per ApproveClaim transaction to
      // force individual approvals that the off-chain indexer can track and
      // deduplicate by (claim_id, guardian_vkh).  Allowing multiple signatures
      // per TX would let the off-chain submitter batch-replay approvals.
      ApproveClaim { claim_id } -> {
        // Claim ID must be valid
        expect claim_id > 0

        // Count how many authorized guardians signed this TX
        let guardian_sigs =
          count_signatures(tx.extra_signatories, datum.guardians)

        // AK06: Require exactly 1 guardian per TX so approvals can be
        // individually de-duplicated by (claim_id, signer) on-chain observers.
        expect guardian_sigs >= 1
        expect guardian_sigs <= 1

        True
      }

      // ── Payout an approved claim ──
      PayoutClaim { claim_id } -> {
        // Claim ID must be valid
        expect claim_id > 0

        // At least the approval threshold of guardians must sign
        let guardian_sigs =
          count_signatures(tx.extra_signatories, datum.guardians)
        expect guardian_sigs >= datum.approval_threshold

        True
      }
    }
  }

  else(_) {
    fail
  }
}

// ═══════════════════ Tests ═══════════════════

test max_payout_is_50_percent() {
  max_payout_bps == 5000
}

test max_payout_calculation() {
  apply_bps(1_000_000, max_payout_bps) == 500_000
}

test min_claim_is_1_ada() {
  min_claim_amount == 1_000_000
}

test claim_window_is_7_days() {
  claim_window_ms == 7 * 24 * 60 * 60 * 1000
}
