//// VAMS Governor Validator
////
//// On-chain governance with quadratic voting for the VAMS protocol.
//// Each proposal is a separate UTXO with a ProposalDatum.
////
//// Flow:
////   1. CreateProposal → mints a new proposal UTXO
////   2. Vote → spends + recreates proposal UTXO with updated tallies
////   3. Execute → consumes passed proposal, creates timelock intent
////   4. Cancel → proposer burns proposal before deadline
////
//// AUDIT FIXES APPLIED:
////   AK01 — Vote weight now verified against on-chain VAMS token balance
////   AK03 — has_valid_continuing_output now inspects tx.outputs

use aiken/collection/list
use aiken/interval.{Finite}
use cardano/address.{Address, Script, VerificationKey}
use cardano/assets.{PolicyId}
use cardano/transaction.{InlineDatum, Output, OutputReference, Transaction}
use vams/types.{
  Active, Cancel, Execute, GovernorRedeemer, Pending, ProposalDatum, Vote,
}
use vams/utils.{has_deadline_passed, is_signed_by, isqrt}

// ═══════════════════ Constants ═══════════════════
// Constants min_proposal_stake, min_voting_period_ms, and default_quorum 
// have been parameterized.

// ═══════════════════ Validator ═══════════════════

/// AUDIT FIX: AK01 — Added vams_policy_id and vams_asset_name as
/// validator parameters so we can look up voter's on-chain VAMS balance.
/// AK08 — Added timelock_script_hash to verify bridging execution output.
validator governor(
  vams_policy_id: PolicyId,
  vams_asset_name: ByteArray,
  timelock_script_hash: ByteArray,
  min_proposal_stake: Int,
  min_voting_period_ms: Int,
  default_quorum: Int,
) {
  spend(
    datum_opt: Option<ProposalDatum>,
    redeemer: GovernorRedeemer,
    own_ref: OutputReference,
    tx: Transaction,
  ) {
    // Datum must exist for spending
    expect Some(datum) = datum_opt

    // Resolve our own address from the spent input
    let own_address = resolve_own_address(tx, own_ref)

    when redeemer is {
      // ── Vote on existing proposal ──
      Vote { support, weight } -> {
        // Proposal must be Pending or Active
        expect datum.status == Pending || datum.status == Active

        // Extract current time from validity range
        expect Finite(current_time) = tx.validity_range.lower_bound.bound_type

        // Deadline must not have passed
        expect !has_deadline_passed(datum.deadline, current_time)

        // Voter must have signed the transaction
        let voter_bytes = get_first_signatory(tx)
        expect is_signed_by(tx.extra_signatories, voter_bytes)

        // Voter must not have already voted
        expect !list.has(datum.voters, voter_bytes)

        // ── AUDIT FIX: AK01 ──
        // Verify weight against on-chain VAMS token balance.
        // Sum voter's VAMS tokens from all transaction inputs they own.
        let voter_balance =
          get_voter_vams_balance(
            tx,
            voter_bytes,
            vams_policy_id,
            vams_asset_name,
          )

        // Weight must equal isqrt(voter_balance) — quadratic voting
        expect weight == isqrt(voter_balance)
        expect weight > 0

        // Verify the output recreates the proposal with updated votes
        let expected_for =
          if support {
            datum.for_votes + weight
          } else {
            datum.for_votes
          }
        let expected_against =
          if !support {
            datum.against_votes + weight
          } else {
            datum.against_votes
          }

        // ── AUDIT FIX: AK03 ──
        // Must produce a continuing output at our own address with updated datum
        expect
          has_valid_continuing_output(
            tx.outputs,
            own_address,
            datum.id,
            expected_for,
            expected_against,
            datum,
            voter_bytes,
          )

        True
      }

      // ── Execute a passed proposal ──
      Execute -> {
        expect Finite(current_time) = tx.validity_range.lower_bound.bound_type

        // Deadline must have passed
        expect has_deadline_passed(datum.deadline, current_time)

        // Must have met quorum
        let total_votes = datum.for_votes + datum.against_votes
        expect total_votes >= datum.quorum

        // Must have majority
        expect datum.for_votes > datum.against_votes

        // Status must be Pending or Active (not already executed)
        expect datum.status == Pending || datum.status == Active

        // ── AUDIT FIX: AK08 ──
        // Ensure a Timelock intent UTXO is created.
        expect
          list.any(
            tx.outputs,
            fn(out) {
              when out.address.payment_credential is {
                Script(hash) -> hash == timelock_script_hash
                _ -> False
              }
            },
          )

        True
      }

      // ── Cancel a proposal (proposer only) ──
      Cancel -> {
        // Only the proposer can cancel
        expect is_signed_by(tx.extra_signatories, datum.proposer)

        // Can only cancel if still Pending or Active
        expect datum.status == Pending || datum.status == Active

        True
      }

      // CreateProposal is handled at the minting policy level
      _ -> False
    }
  }

  else(_) {
    fail
  }
}

// ═══════════════════ Helper Functions ═══════════════════

/// Get the first signatory from a transaction
fn get_first_signatory(tx: Transaction) -> ByteArray {
  expect [first, ..] = tx.extra_signatories
  first
}

/// Resolve our own script address from the spent input reference
fn resolve_own_address(tx: Transaction, own_ref: OutputReference) -> Address {
  expect Some(own_input) =
    list.find(tx.inputs, fn(input) { input.output_reference == own_ref })
  own_input.output.address
}

/// AUDIT FIX: AK01 — Sum the voter's VAMS token balance from tx inputs.
/// Finds all inputs signed by the voter that contain VAMS tokens.
fn get_voter_vams_balance(
  tx: Transaction,
  voter_vkh: ByteArray,
  policy_id: PolicyId,
  asset_name: ByteArray,
) -> Int {
  list.foldl(
    tx.inputs,
    0,
    fn(input, acc) {
      // Check if this input is owned by the voter (payment credential matches)
      let is_voter_input =
        when input.output.address.payment_credential is {
          VerificationKey(hash) -> hash == voter_vkh
          _ -> False
        }
      if is_voter_input {
        acc + assets.quantity_of(input.output.value, policy_id, asset_name)
      } else {
        acc
      }
    },
  )
}

/// AUDIT FIX: AK03 — Now actually inspects tx.outputs to verify
/// the continuing output has the correctly updated datum.
fn has_valid_continuing_output(
  outputs: List<Output>,
  own_address: Address,
  proposal_id: Int,
  expected_for: Int,
  expected_against: Int,
  original: ProposalDatum,
  voter_bytes: ByteArray,
) -> Bool {
  // Find the continuing output at our own validator address
  when list.find(outputs, fn(output) { output.address == own_address }) is {
    Some(output) -> {
      // Extract and verify the inline datum
      expect InlineDatum(raw_datum) = output.datum
      expect updated_datum: ProposalDatum = raw_datum
      // Verify state transition correctness
      updated_datum.id == proposal_id && updated_datum.for_votes == expected_for && updated_datum.against_votes == expected_against && list.has(
        updated_datum.voters,
        voter_bytes,
      ) && list.length(updated_datum.voters) == list.length(original.voters) + 1 && updated_datum.proposer == original.proposer && updated_datum.quorum == original.quorum && updated_datum.deadline == original.deadline && updated_datum.description_hash == original.description_hash && updated_datum.action_hash == original.action_hash
    }
    // No continuing output found — invalid
    None -> False
  }
}

// ═══════════════════ Tests ═══════════════════

test quadratic_weight_100k() {
  isqrt(100_000) == 316
}

test quadratic_weight_1m() {
  isqrt(1_000_000) == 1000
}

test quadratic_weight_10k() {
  isqrt(10_000) == 100
}
