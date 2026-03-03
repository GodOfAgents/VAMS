//// VAMS Shared Types
////
//// Core data types shared across all VAMS Cardano validators.
//// These define the eUTXO datums and redeemers for governance,
//// timelock, insurance, and agent registry.

// ═══════════════════ Governance Types ═══════════════════

/// Status of a governance proposal
pub type ProposalStatus {
  /// Proposal created, accepting votes
  Pending
  /// Voting period active
  Active
  /// Passed quorum and majority threshold
  Passed
  /// Did not meet quorum or majority
  Rejected
  /// Executed on-chain after timelock
  Executed
  /// Cancelled by proposer before deadline
  Cancelled
}

/// On-chain governance proposal datum
/// Each proposal lives in its own UTXO
pub type ProposalDatum {
  /// Unique proposal identifier
  id: Int,
  /// Proposer's verification key hash
  proposer: ByteArray,
  /// IPFS hash of the full proposal text
  description_hash: ByteArray,
  /// Hash of the executable action payload
  action_hash: ByteArray,
  /// Quadratic-weighted votes in favor
  for_votes: Int,
  /// Quadratic-weighted votes against
  against_votes: Int,
  /// Minimum total participation required
  quorum: Int,
  /// Voting deadline (POSIX milliseconds)
  deadline: Int,
  /// Current proposal status
  status: ProposalStatus,
  /// List of voters (verification key hashes) who already voted
  voters: List<ByteArray>,
}

/// Redeemer actions for the Governor validator
pub type GovernorRedeemer {
  /// Create a new proposal
  CreateProposal {
    description_hash: ByteArray,
    action_hash: ByteArray,
    quorum: Int,
    deadline: Int,
  }
  /// Cast a vote on a proposal
  Vote { support: Bool, weight: Int }
  /// Execute a passed proposal (after timelock)
  Execute
  /// Cancel a proposal (proposer only, before deadline)
  Cancel
}

// ═══════════════════ Timelock Types ═══════════════════

/// Governance intent queued for cross-chain execution
pub type IntentDatum {
  /// Monotonically increasing nonce for replay protection
  nonce: Int,
  /// Target chain identifier (e.g., "polygon")
  target_chain: ByteArray,
  /// Hash of the action to execute on target chain
  action_hash: ByteArray,
  /// Earliest execution time (POSIX milliseconds)
  execute_after: Int,
  /// Reference to the governance proposal that spawned this
  proposal_id: Int,
  /// Whether this intent has been consumed
  consumed: Bool,
}

/// Redeemer actions for the Timelock validator
pub type TimelockRedeemer {
  /// Queue a new intent from a passed governance proposal
  QueueIntent { proposal_id: Int, delay_ms: Int }
  /// Release the intent for ICB relay (after delay)
  ExecuteIntent { mithril_proof: ByteArray }
  /// Cancel a queued intent (DAO vote required)
  CancelIntent
}

// ═══════════════════ Insurance Fund Types ═══════════════════

/// Insurance fund state datum
pub type FundDatum {
  /// Current ADA balance in the fund (lovelace)
  total_balance: Int,
  /// Number of pending claims
  pending_claims: Int,
  /// Last bridge deposit epoch
  last_bridge_epoch: Int,
  /// Maximum payout as basis points of fund (5000 = 50%)
  max_payout_bps: Int,
  /// Required approval threshold for claims
  approval_threshold: Int,
  /// Guardian verification key hashes
  guardians: List<ByteArray>,
}

/// Insurance claim datum
pub type ClaimDatum {
  /// Unique claim identifier
  id: Int,
  /// Claimant's verification key hash
  claimant: ByteArray,
  /// Requested amount in lovelace
  amount: Int,
  /// IPFS hash of evidence/proof
  evidence_hash: ByteArray,
  /// Number of guardian approvals received
  approvals: Int,
  /// Guardian keys that have approved
  approvers: List<ByteArray>,
  /// Whether claim has been paid out
  paid: Bool,
}

/// Redeemer actions for the InsuranceFund validator
pub type InsuranceFundRedeemer {
  /// Deposit from bridge (ICB relay proof required)
  Deposit { amount: Int, bridge_proof: ByteArray }
  /// Submit a new claim
  SubmitClaim { amount: Int, evidence_hash: ByteArray }
  /// Guardian approves a claim
  ApproveClaim { claim_id: Int }
  /// Payout an approved claim
  PayoutClaim { claim_id: Int }
}

// ═══════════════════ Agent Registry Types ═══════════════════

/// On-chain agent record datum (one UTXO per agent)
pub type AgentDatum {
  /// Decentralized Identifier (DID)
  did: ByteArray,
  /// Owner's verification key hash
  owner: ByteArray,
  /// Reputation score (0-10000 basis points)
  reputation_score: Int,
  /// Registration timestamp (POSIX ms)
  registered_at: Int,
  /// IPFS hash of agent metadata (capabilities, endpoints, etc.)
  metadata_hash: ByteArray,
  /// Whether the agent is currently active
  is_active: Bool,
  /// Staked amount (in lovelace equivalent)
  staked_amount: Int,
}

/// Redeemer actions for the AgentRegistry validator
pub type RegistryRedeemer {
  /// Register a new agent (mints identity NFT)
  RegisterAgent { did: ByteArray, metadata_hash: ByteArray }
  /// Update agent's metadata
  UpdateAgent { new_metadata_hash: ByteArray }
  /// Deregister an agent (burns identity NFT)
  DeregisterAgent
  /// Slash agent for misbehavior (reduces reputation + stake)
  SlashAgent { evidence_hash: ByteArray, slash_amount: Int }
}
