//// F04 immutable anchor foundation wire types.
//// These types are local to the foundation; existing shared V1 types remain untouched.

use cardano/transaction.{OutputReference}

/// Anchor datum wire shape. This single constructor is intentionally Constr0.
pub type AnchorDatumV2 {
  schema_version: Int,
  anchor_seed: OutputReference,
  bootstrap_ref: OutputReference,
  identity_policy_id: ByteArray,
  identity_asset_name: ByteArray,
  did: ByteArray,
  founding_owner_vkh: ByteArray,
  initial_controller_vkh: ByteArray,
  initial_operator_vkh: ByteArray,
  initial_guardians: List<ByteArray>,
  registry_script_hash: ByteArray,
  initial_metadata_hash: ByteArray,
  genesis_control_epoch: Int,
  genesis_guardian_epoch: Int,
  anchor_lovelace: Int,
  initial_stake_lovelace: Int,
  initial_reputation_bps: Int,
}

/// The sole P0 mint redeemer. Constructor 0 contains the consumed anchor seed.
pub type AnchorPolicyRedeemer {
  IssueAnchor { anchor_seed: OutputReference }
}
