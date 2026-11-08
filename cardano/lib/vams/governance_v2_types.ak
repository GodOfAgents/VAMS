//// Governance v2 is explicit: no legacy datum or redeemer is reinterpreted.
//// Applied identities and bootstrap custodians remain ceremony inputs.
use cardano/transaction.{OutputReference}

pub type GovernanceBootstrapV2 {
  seed: OutputReference,
  network_id: Int,
  policy_epoch: Int,
  members: List<ByteArray>,
}

/// The authority mint and spend handlers share one script/policy identity.
pub type GovernanceAnchorV2 {
  policy_id: ByteArray,
  asset_name: ByteArray,
}

pub type GovernanceConfigV2 {
  version: Int,
  network_id: Int,
  policy_epoch: Int,
  seed: OutputReference,
  authority_policy_id: ByteArray,
  governor_script_hash: ByteArray,
  timelock_script_hash: ByteArray,
  proposal_policy_id: ByteArray,
  receipt_policy_id: ByteArray,
  intent_policy_id: ByteArray,
  vams_policy_id: ByteArray,
  vams_asset_name: ByteArray,
  members: List<ByteArray>,
  threshold: Int,
  normal_delay_ms: Int,
  emergency_disabled: Bool,
  authority_state_lovelace: Int,
  proposal_base_lovelace: Int,
  per_voter_refund_lovelace: Int,
  next_proposal_nonce: Int,
  next_intent_nonce: Int,
  max_lock_vams: Int,
  target_domains: List<ByteArray>,
}

pub type AuthorityDatumV2 {
  config: GovernanceConfigV2,
}

pub type ProposalStateV2 {
  PendingV2
  PassedV2
}

pub type VoteLockV2 {
  voter_vkh: ByteArray,
  locked_vams: Int,
  support: Bool,
  weight: Int,
  receipt_name: ByteArray,
}

pub type ProposalDatumV2 {
  version: Int,
  state: ProposalStateV2,
  proposal_asset: ByteArray,
  nonce: Int,
  proposer_vkh: ByteArray,
  description_hash: ByteArray,
  action_hash: ByteArray,
  payload_hash: ByteArray,
  target_domain: ByteArray,
  policy_epoch: Int,
  quorum: Int,
  deadline: Int,
  yes_weight: Int,
  no_weight: Int,
  locks: List<VoteLockV2>,
}

pub type IntentDatumV2 {
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

/// Constructor order is part of v2. Legacy actions do not use this type.
pub type GovernanceActionV2 {
  InitializeV2
  CreateV2
  VoteV2 { voter_vkh: ByteArray, support: Bool, locked_vams: Int }
  FinalizePassedV2
  FinalizeRejectedV2
  CancelProposalV2
  QueueV2
  CancelIntentV2
  ExpireIntentV2
  ExecuteIntentV2
}

/// The outer version prevents old constructor tags acquiring new meanings.
pub type GovernanceRequestV2 {
  version: Int,
  action: GovernanceActionV2,
}
