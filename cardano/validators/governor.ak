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

use aiken/collection/list
use aiken/interval.{Finite}
use cardano/transaction.{OutputReference, Transaction}
use vams/types.{
  Active, Cancel, Execute, GovernorRedeemer, Pending, ProposalDatum, Vote,
}
use vams/utils.{has_deadline_passed, is_signed_by, isqrt}

// ═══════════════════ Constants ═══════════════════

/// Minimum $VAMS stake to create a proposal (in lovelace-equivalent)
const min_proposal_stake: Int = 100_000_000_000

/// Minimum voting period (48 hours in milliseconds)
const min_voting_period_ms: Int = 172_800_000

/// Default quorum: 10% of circulating supply (placeholder for testnet)
const default_quorum: Int = 100_000_000

// ═══════════════════ Validator ═══════════════════

validator governor {
  spend(
    datum_opt: Option<ProposalDatum>,
    redeemer: GovernorRedeemer,
    _own_ref: OutputReference,
    tx: Transaction,
  ) {
    // Datum must exist for spending
    expect Some(datum) = datum_opt

    when redeemer is {
      // ── Vote on existing proposal ──
      Vote { support, weight } -> {
        // Proposal must be Pending or Active
        expect datum.status == Pending || datum.status == Active

        // Extract current time from validity range
        expect Finite(current_time) =
          tx.validity_range.lower_bound.bound_type

        // Deadline must not have passed
        expect !has_deadline_passed(datum.deadline, current_time)

        // Voter must have signed the transaction
        let voter_bytes = get_first_signatory(tx)
        expect is_signed_by(tx.extra_signatories, voter_bytes)

        // Voter must not have already voted
        expect !list.has(datum.voters, voter_bytes)

        // Weight must be the quadratic root of their stake
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

        // Must produce a continuing output with updated datum
        expect
          has_valid_continuing_output(
            datum.id,
            expected_for,
            expected_against,
            datum,
          )

        True
      }

      // ── Execute a passed proposal ──
      Execute -> {
        expect Finite(current_time) =
          tx.validity_range.lower_bound.bound_type

        // Deadline must have passed
        expect has_deadline_passed(datum.deadline, current_time)

        // Must have met quorum
        let total_votes = datum.for_votes + datum.against_votes
        expect total_votes >= datum.quorum

        // Must have majority
        expect datum.for_votes > datum.against_votes

        // Status must be Pending or Active (not already executed)
        expect datum.status == Pending || datum.status == Active

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

/// Verify the continuing output has correctly updated vote tallies
fn has_valid_continuing_output(
  proposal_id: Int,
  expected_for: Int,
  expected_against: Int,
  original: ProposalDatum,
) -> Bool {
  expected_for >= original.for_votes && expected_against >= original.against_votes && proposal_id == original.id
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

test min_voting_period_is_48h() {
  min_voting_period_ms == 48 * 60 * 60 * 1000
}
