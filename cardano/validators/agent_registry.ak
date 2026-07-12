//// VAMS Agent Registry Validator
////
//// On-chain DID registry for AI agents on the VAMS network.
//// Each agent is a separate UTXO with an AgentDatum.
//// Registration mints an identity NFT (CIP-68 pattern).
////
//// Flow:
////   1. RegisterAgent → mints NFT + creates agent UTXO
////   2. UpdateAgent → spends + recreates with updated metadata
////   3. DeregisterAgent → burns NFT + consumes agent UTXO
////   4. SlashAgent → reduces reputation/stake for misbehavior

use aiken/primitive/bytearray
use cardano/transaction.{OutputReference, Transaction}
use vams/types.{
  AgentDatum, DeregisterAgent, RegisterAgent, RegistryRedeemer, SlashAgent,
  UpdateAgent,
}
use vams/utils.{count_signatures, in_range, is_signed_by}

// ═══════════════════ Constants ═══════════════════

/// Minimum stake to register an agent (1,000 ADA in lovelace)
const min_agent_stake: Int = 1_000_000_000

/// Maximum reputation score (10,000 = 100.00%)
const max_reputation: Int = 10_000

/// Initial reputation for new agents (5,000 = 50.00%)
const initial_reputation: Int = 5_000

/// Minimum DID length (bytes)
const min_did_length: Int = 32

/// Slash penalty for misbehavior: 10% of stake
const slash_penalty_bps: Int = 1_000

// ═══════════════════ Validator ═══════════════════

validator agent_registry {
  spend(
    datum_opt: Option<AgentDatum>,
    redeemer: RegistryRedeemer,
    _own_ref: OutputReference,
    tx: Transaction,
  ) {
    expect Some(datum) = datum_opt

    when redeemer is {
      // ── Register a new agent ──
      RegisterAgent { did, metadata_hash } -> {
        // Owner must sign
        expect is_signed_by(tx.extra_signatories, datum.owner)

        // DID must meet minimum length
        expect bytearray.length(did) >= min_did_length

        // Metadata hash must be provided
        expect bytearray.length(metadata_hash) > 0

        // Must deposit minimum stake
        expect datum.staked_amount >= min_agent_stake

        // Initial reputation must be set correctly
        expect datum.reputation_score == initial_reputation

        // Agent must be marked active
        expect datum.is_active

        True
      }

      // ── Update agent metadata ──
      UpdateAgent { new_metadata_hash } -> {
        // Only the owner can update
        expect is_signed_by(tx.extra_signatories, datum.owner)

        // Agent must be active
        expect datum.is_active

        // New metadata must be provided
        expect bytearray.length(new_metadata_hash) > 0

        True
      }

      // ── Deregister an agent ──
      DeregisterAgent -> {
        // Only the owner can deregister
        expect is_signed_by(tx.extra_signatories, datum.owner)

        // Agent must be active
        expect datum.is_active

        True
      }

      // ── Slash an agent for misbehavior ──
      SlashAgent { evidence_hash, slash_amount } -> {
        // Evidence must be provided
        expect bytearray.length(evidence_hash) > 0

        // Agent must be active
        expect datum.is_active

        // Slash amount must be positive and within bounds
        let max_slash = datum.staked_amount * slash_penalty_bps / 10_000
        expect slash_amount > 0 && slash_amount <= max_slash

        // AUDIT FIX: AK05 — Must be signed by an authorized slasher from the
        // datum's whitelist, not just any signer.  An empty authorized_slashers
        // list means slashing is locked (safe default for newly registered agents).
        let authorized_sig_count =
          count_signatures(tx.extra_signatories, datum.authorized_slashers)
        expect authorized_sig_count >= 1

        True
      }
    }
  }

  else(_) {
    fail
  }
}

// ═══════════════════ Tests ═══════════════════

test initial_reputation_is_50_percent() {
  initial_reputation == 5_000
}

test max_reputation_is_100_percent() {
  max_reputation == 10_000
}

test reputation_in_valid_range() {
  in_range(initial_reputation, 0, max_reputation) == True
}

test min_stake_is_1000_ada() {
  min_agent_stake == 1_000 * 1_000_000
}

test slash_penalty_is_10_percent() {
  slash_penalty_bps == 1_000
}

test slash_max_calculation() {
  let stake = 1_000_000_000
  stake * slash_penalty_bps / 10_000 == 100_000_000
}
