//// VAMS shared Cardano types.
////
//// These are pre-deployment schema-v2 datums. Every authoritative state UTxO
//// carries an authentication asset; user-provided integer identifiers are
//// informational and never serve as the security identity of a state object.

use cardano/assets.{PolicyId}
use cardano/transaction.{OutputReference}

pub const cardano_schema_version: Int = 2

// Governance -----------------------------------------------------------------

pub type ProposalStatus {
  Pending
  Active
}

pub type ProposalDatum {
  schema_version: Int,
  /// Informational identifier. The proposal NFT and UTxO reference are canonical.
  id: Int,
  proposal_policy_id: PolicyId,
  proposal_asset_name: ByteArray,
  proposer: ByteArray,
  description_hash: ByteArray,
  /// Blake2b-256 hash of the exact inline datum emitted by the timelock.
  action_hash: ByteArray,
  /// Cardano-local target script hash. Cross-chain execution is disabled.
  target_script_hash: ByteArray,
  created_at: Int,
  for_votes: Int,
  against_votes: Int,
  quorum: Int,
  deadline: Int,
  status: ProposalStatus,
  voters: List<ByteArray>,
}

pub type GovernorRedeemer {
  Vote { support: Bool, weight: Int }
  Execute
  Cancel
}

// Timelock -------------------------------------------------------------------

pub type IntentDatum {
  schema_version: Int,
  proposal_policy_id: PolicyId,
  proposal_asset_name: ByteArray,
  source_proposal: OutputReference,
  action_hash: ByteArray,
  target_script_hash: ByteArray,
  execute_after: Int,
  expires_at: Int,
  refund_key_hash: ByteArray,
}

pub type TimelockRedeemer {
  /// Execute an exact Cardano-local output after the delay.
  ExecuteLocal
  /// Reserved wire branch. It always fails closed until a real verifier exists.
  ExecuteBridge { bridge_proof: ByteArray, payload_hash: ByteArray }
  CancelIntent
}

// Insurance ------------------------------------------------------------------

pub type FundDatum {
  schema_version: Int,
  fund_policy_id: PolicyId,
  fund_asset_name: ByteArray,
  total_balance: Int,
  next_claim_id: Int,
  /// Commitments authenticate claim UTxOs created by a canonical fund transition.
  pending_claim_commitments: List<ByteArray>,
  max_payout_bps: Int,
  approval_threshold: Int,
  guardians: List<ByteArray>,
}

pub type ClaimDatum {
  schema_version: Int,
  fund_policy_id: PolicyId,
  fund_asset_name: ByteArray,
  id: Int,
  claimant: ByteArray,
  amount: Int,
  evidence_hash: ByteArray,
  submitted_at: Int,
  expires_at: Int,
  commitment: ByteArray,
  approvers: List<ByteArray>,
}

pub type InsuranceDatum {
  FundState(FundDatum)
  ClaimState(ClaimDatum)
}

pub type InsuranceFundRedeemer {
  DepositLocal { amount: Int }
  /// Reserved wire branch. It always fails closed until a real verifier exists.
  DepositBridge {
    amount: Int,
    bridge_proof: ByteArray,
    payload_hash: ByteArray,
  }
  SubmitClaim { amount: Int, evidence_hash: ByteArray }
  ApproveClaim { claim_id: Int }
  PayoutClaim { claim_id: Int }
}

// Agent registry -------------------------------------------------------------

pub type AgentDatum {
  schema_version: Int,
  identity_policy_id: PolicyId,
  identity_asset_name: ByteArray,
  did: ByteArray,
  owner: ByteArray,
  reputation_score: Int,
  registered_at: Int,
  metadata_hash: ByteArray,
  is_active: Bool,
  staked_amount: Int,
  /// Empty in the initial Pre-Prod profile: slashing is disabled.
  authorized_slashers: List<ByteArray>,
}

pub type RegistryRedeemer {
  UpdateAgent { new_metadata_hash: ByteArray }
  DeregisterAgent
  /// Reserved wire branch. It always fails closed in the initial profile.
  SlashAgent { evidence_hash: ByteArray, slash_amount: Int }
}
