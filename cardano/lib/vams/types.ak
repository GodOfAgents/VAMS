//// VAMS Shared Types
////
//// Core data types shared across all VAMS Cardano validators.
//// These define the eUTXO datums and redeemers for governance,
//// timelock, insurance, and agent registry.

use cardano/address.{Address}
use cardano/transaction.{OutputReference}

// ═══════════════════ Governance Types ═══════════════════

/// Frozen M3.2b governance configuration committed by the singleton genesis
/// output. The list fields are deliberately bounded by the validators.
pub type GovernanceConfigV1 {
  version: Int,
  network_id: Int,
  authority_state_lovelace: Int,
  proposal_base_lovelace: Int,
  per_voter_refund_lovelace: Int,
  policy_epoch: Int,
  authority_policy_id: ByteArray,
  governor_script_hash: ByteArray,
  timelock_script_hash: ByteArray,
  seed: OutputReference,
  members: List<ByteArray>,
  threshold: Int,
  normal_delay_ms: Int,
  emergency_disabled: Bool,
  next_proposal_nonce: Int,
  next_intent_nonce: Int,
  max_lock_vams: Int,
  caps: List<Int>,
  target_domains: List<ByteArray>,
}

pub type AuthorityDatumV1 {
  config: GovernanceConfigV1,
}

pub type ProposalStatusV1 {
  ProposalPending
  ProposalPassed
  ProposalRejected
  ProposalCancelled
}

pub type VoteLockRecordV1 {
  voter_vkh: ByteArray,
  locked_vams: Int,
  support: Bool,
  weight: Int,
  receipt_name: ByteArray,
}

pub type ProposalDatumV1 {
  version: Int,
  status: ProposalStatusV1,
  proposal_asset: ByteArray,
  nonce: Int,
  proposer_vkh: ByteArray,
  description_hash: ByteArray,
  action_hash: ByteArray,
  target_domain: ByteArray,
  policy_epoch: Int,
  quorum: Int,
  deadline: Int,
  yes_weight: Int,
  no_weight: Int,
  locks: List<VoteLockRecordV1>,
}

pub type IntentDatumV1 {
  version: Int,
  proposal_id: ByteArray,
  proposal_asset: ByteArray,
  action_hash: ByteArray,
  payload_hash: ByteArray,
  target_domain: ByteArray,
  policy_epoch: Int,
  nonce: Int,
  queue_time: Int,
  execute_after: Int,
  lifetime: Int,
  proposer_vkh: ByteArray,
  consumed: Bool,
}

pub type AuthorityRedeemer {
  Genesis
  AdvanceProposalNonce
  AdvanceIntentNonce
}

pub type GovernorRedeemer {
  CreateProposal
  Vote { support: Bool, locked_vams: Int }
  FinalizePassed
  FinalizeRejected
  Cancel
  Queue
}

/// Redeemers for the timelock state machine.
pub type TimelockRedeemer {
  CancelIntent
  ExpireIntent
  /// This branch is intentionally and permanently disabled until F05.
  ExecuteIntent
}

/// Versioned singleton insurance-fund state.
pub type FundDatumV2 {
  schema_version: Int,
  total_balance: Int,
  next_claim_nonce: Int,
  pending_claims: List<ClaimRecord>,
  policy_epoch: Int,
  max_payout_bps: Int,
  approval_threshold: Int,
  guardians: List<ByteArray>,
}

/// Durable claim state carried by the singleton fund output.
pub type ClaimRecord {
  claim_id: ByteArray,
  claim_nonce: Int,
  claimant_vkh: ByteArray,
  payout_address: Address,
  amount: Int,
  evidence_hash: ByteArray,
  submitted_at: Int,
  expires_at: Int,
  policy_epoch: Int,
  approvers: List<ByteArray>,
}

/// Canonical, versioned payload serialized before claim-id hashing.
pub type ClaimIdentityPayload {
  domain: ByteArray,
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
}

/// One-shot state-token policy action.
pub type InsuranceStateRedeemer {
  InitializeFund
}

/// Redeemer actions for the InsuranceFund validator
pub type InsuranceFundRedeemer {
  /// Reserved for the future F05 bridge contract; rejects in M3.1b.
  Deposit { amount: Int, bridge_proof: ByteArray, payload_hash: ByteArray }
  SubmitClaim {
    claim_nonce: Int,
    claimant_vkh: ByteArray,
    payout_address: Address,
    amount: Int,
    evidence_hash: ByteArray,
  }
  ApproveClaim { claim_id: ByteArray }
  PayoutClaim { claim_id: ByteArray }
  CancelClaim { claim_id: ByteArray }
  ExpireClaim { claim_id: ByteArray }
}

// ═══════════════════ Agent Registry Types ═══════════════════

/// On-chain agent record datum (one UTXO per agent)
/// Versioned on-chain agent record datum (one UTXO per agent).
///
/// This is the only accepted registry datum shape. The field order is frozen
/// by the M3 F04 identity contract; legacy eight-field datums are not
/// represented and cannot be decoded by the registry boundary.
pub type AgentDatumV1 {
  schema_version: Int,
  identity_policy_id: ByteArray,
  identity_asset_name: ByteArray,
  nonce: Int,
  did: ByteArray,
  owner: ByteArray,
  operator: ByteArray,
  stake_lovelace: Int,
  reputation_bps: Int,
  metadata_hash: ByteArray,
  status: Int,
  action_epoch: Int,
  registered_at_ms: Int,
  authorized_slashers: List<ByteArray>,
}

/// Versioned registry transition redeemers. Numeric tags and field order are
/// frozen by IDENTITY_SPEC.json; no legacy defaults or coercions are allowed.
pub type RegistryRedeemerV1 {
  RegisterAgent {
    did: ByteArray,
    metadata_hash: ByteArray,
    operator: ByteArray,
  }
  UpdateAgent {
    new_metadata_hash: ByteArray,
    new_operator: ByteArray,
    expected_nonce: Int,
    expected_action_epoch: Int,
  }
  DeregisterAgent {
    expected_nonce: Int,
    expected_action_epoch: Int,
  }
  SlashAgent {
    evidence_hash: ByteArray,
    slash_amount: Int,
    expected_nonce: Int,
    expected_action_epoch: Int,
  }
}

pub type AgentNftRedeemer {
  MintIdentity { did: ByteArray, owner_vkh: ByteArray }
  BurnIdentity { identity_asset_name: ByteArray, owner_vkh: ByteArray }
}

/// Exact authority datum carried by the singleton RegistryAuthorityV1
/// reference input. All values are explicit; callers must not infer defaults.
pub type RegistryAuthorityV1 {
  schema_version: Int,
  identity_policy_id: ByteArray,
  bootstrap_ref: OutputReference,
  action_epoch: Int,
  slash_enabled: Bool,
  authority_script_hash: ByteArray,
  authority_policy_id: ByteArray,
  authority_asset_name: ByteArray,
  authority_quantity: Int,
  authority_state_lovelace: Int,
  reserve_credential: ByteArray,
  authority_address: ByteArray,
  datum_hash: ByteArray,
}

/// Non-self-referential authority anchor preimage. Mutable epoch/enablement
/// and the registry policy identifier are deliberately excluded so the
/// commitment cannot depend on its own applied validator hash.
pub type RegistryAuthorityPayloadV1 {
  schema_version: Int,
  identity_policy_id: ByteArray,
  bootstrap_ref: OutputReference,
  action_epoch: Int,
  slash_enabled: Bool,
  authority_script_hash: ByteArray,
  authority_policy_id: ByteArray,
  authority_asset_name: ByteArray,
  authority_quantity: Int,
  authority_state_lovelace: Int,
  reserve_credential: ByteArray,
  authority_address: ByteArray,
}

/// Authenticated post-F05 action authorization reference.
pub type RegistryActionV1 {
  schema_version: Int,
  action_policy_id: ByteArray,
  action_asset_name: ByteArray,
  action_quantity: Int,
  action_epoch: Int,
  action_nonce: Int,
}

/// Verified post-F05 evidence attestation.
pub type EvidenceAttestationV1 {
  schema_version: Int,
  identity_policy_id: ByteArray,
  identity_asset_name: ByteArray,
  action_epoch: Int,
  nonce: Int,
  evidence_hash: ByteArray,
  authorized_slasher: ByteArray,
  valid_until: Int,
  status: Int,
  verifier_id: ByteArray,
}
