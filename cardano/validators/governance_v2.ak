//// Versioned candidate entrypoints; not activated or natively qualified.
//// Legacy compiled identities cannot be reused for these schemas.
use cardano/assets.{PolicyId}
use cardano/transaction.{OutputReference, Transaction}
use vams/governance_v2_transitions
use vams/governance_v2_types.{
  AuthorityDatumV2, GovernanceAnchorV2, GovernanceBootstrapV2, GovernanceRequestV2,
  InitializeV2, IntentDatumV2, ProposalDatumV2,
}

/// Shared mint/spend script identity removes the authority hash cycle, following
/// the existing insurance singleton pattern without modifying insurance code.
validator governance_authority_v2(bootstrap: GovernanceBootstrapV2) {
  mint(request: GovernanceRequestV2, policy_id: PolicyId, tx: Transaction) {
    let action = governance_v2_transitions.request_action(request)
    expect action == InitializeV2
    governance_v2_transitions.authority_genesis(bootstrap, policy_id, tx)
  }
  spend(datum: Option<AuthorityDatumV2>, request: GovernanceRequestV2, own_ref: OutputReference, tx: Transaction) {
    let action = governance_v2_transitions.request_action(request)
    expect Some(before) = datum
    governance_v2_transitions.authority_spend(bootstrap, before, action, own_ref, tx)
  }
  else(_) { fail }
}

validator governor_v2(anchor: GovernanceAnchorV2) {
  spend(datum: Option<ProposalDatumV2>, request: GovernanceRequestV2, own_ref: OutputReference, tx: Transaction) {
    let action = governance_v2_transitions.request_action(request)
    expect Some(before) = datum
    governance_v2_transitions.governor_spend(anchor, before, action, own_ref, tx)
  }
  else(_) { fail }
}

validator timelock_v2(anchor: GovernanceAnchorV2) {
  spend(datum: Option<IntentDatumV2>, request: GovernanceRequestV2, own_ref: OutputReference, tx: Transaction) {
    let action = governance_v2_transitions.request_action(request)
    expect Some(before) = datum
    governance_v2_transitions.timelock_spend(anchor, before, action, own_ref, tx)
  }
  else(_) { fail }
}

validator proposal_policy_v2(anchor: GovernanceAnchorV2) {
  mint(request: GovernanceRequestV2, policy_id: PolicyId, tx: Transaction) {
    let action = governance_v2_transitions.request_action(request)
    governance_v2_transitions.policy_mint(anchor, 1, policy_id, action, tx)
  }
  else(_) { fail }
}

validator receipt_policy_v2(anchor: GovernanceAnchorV2) {
  mint(request: GovernanceRequestV2, policy_id: PolicyId, tx: Transaction) {
    let action = governance_v2_transitions.request_action(request)
    governance_v2_transitions.policy_mint(anchor, 2, policy_id, action, tx)
  }
  else(_) { fail }
}

validator intent_policy_v2(anchor: GovernanceAnchorV2) {
  mint(request: GovernanceRequestV2, policy_id: PolicyId, tx: Transaction) {
    let action = governance_v2_transitions.request_action(request)
    governance_v2_transitions.policy_mint(anchor, 3, policy_id, action, tx)
  }
  else(_) { fail }
}
