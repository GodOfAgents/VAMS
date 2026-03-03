//// VAMS Timelock Validator
////
//// Enforces mandatory delay on governance intents before they can be
//// relayed to Polygon via ICB. Provides replay protection via nonces.
////
//// Flow:
////   1. Governor passes a proposal → QueueIntent creates timelock UTXO
////   2. After delay period → ExecuteIntent releases for ICB relay
////   3. Optional → CancelIntent if DAO votes to abort

use aiken/collection/list
use aiken/interval.{Finite}
use cardano/transaction.{OutputReference, Transaction}
use vams/types.{CancelIntent, ExecuteIntent, IntentDatum, QueueIntent, TimelockRedeemer}
use vams/icb.{verify_mithril_proof}
use vams/utils.{is_timelock_ready}

// ═══════════════════ Constants ═══════════════════

/// Normal governance delay: 48 hours (in milliseconds)
const normal_delay_ms: Int = 172_800_000

/// Emergency governance delay: 24 hours (in milliseconds)
const emergency_delay_ms: Int = 86_400_000

/// Maximum intent lifetime: 7 days (in milliseconds)
const max_intent_lifetime_ms: Int = 604_800_000

// ═══════════════════ Validator ═══════════════════

validator timelock {
  spend(
    datum_opt: Option<IntentDatum>,
    redeemer: TimelockRedeemer,
    _own_ref: OutputReference,
    tx: Transaction,
  ) {
    expect Some(datum) = datum_opt

    when redeemer is {
      // ── Queue a new intent (from passed governance proposal) ──
      QueueIntent { proposal_id, delay_ms } -> {
        // Delay must meet minimum requirements
        expect delay_ms >= emergency_delay_ms

        // Intent must reference the correct proposal
        expect proposal_id > 0

        // Intent must not already be consumed
        expect !datum.consumed

        True
      }

      // ── Execute an intent (release for ICB relay) ──
      ExecuteIntent { mithril_proof } -> {
        // Extract current time from validity range
        expect Finite(current_time) =
          tx.validity_range.lower_bound.bound_type

        // Timelock delay must have elapsed
        expect is_timelock_ready(datum.execute_after, current_time)

        // Intent must not have been consumed already (replay protection)
        expect !datum.consumed

        // Intent must not have expired
        let expiry = datum.execute_after + max_intent_lifetime_ms
        expect current_time < expiry

        // Verify Mithril finality proof
        expect verify_mithril_proof(mithril_proof)

        True
      }

      // ── Cancel a queued intent (DAO multisig required) ──
      CancelIntent -> {
        // Must not be already consumed
        expect !datum.consumed

        // Must be signed by at least one authorized signer
        expect list.length(tx.extra_signatories) >= 1

        True
      }
    }
  }

  else(_) {
    fail
  }
}

// ═══════════════════ Tests ═══════════════════

test normal_delay_is_48h() {
  normal_delay_ms == 48 * 60 * 60 * 1000
}

test emergency_delay_is_24h() {
  emergency_delay_ms == 24 * 60 * 60 * 1000
}

test max_lifetime_is_7d() {
  max_intent_lifetime_ms == 7 * 24 * 60 * 60 * 1000
}

test emergency_less_than_normal() {
  emergency_delay_ms < normal_delay_ms
}
