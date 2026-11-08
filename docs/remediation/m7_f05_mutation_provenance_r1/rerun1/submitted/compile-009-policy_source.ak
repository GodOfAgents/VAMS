//// F05.2a deployment-bound authority singleton minting policy.
////
//// This policy is separate from the fixed authority spending validator. Its
//// applied parameters bind the genesis reference and custody-supplied ordered
//// committee keys. The state-validator hash is a generated source constant,
//// derived from the pinned nullary validator build as specified by R2.

use aiken/collection/dict
use aiken/collection/list
use cardano/address.{Script}
use cardano/assets
use cardano/assets.{PolicyId}
use cardano/transaction.{InlineDatum, Input, Output, OutputReference, Transaction}
use vams/f05_authority.{
  AuthorityBootstrapRedeemer, AuthorityStateV3, BootstrapAuthority,
  authority_asset_name, authority_genesis_pop_preimage, same_output_reference,
  valid_bootstrap_proofs, valid_initial_authority,
}

const authority_initial_lovelace: Int = 10_000_000
/// Generated only from f05_authority_state's pinned Plutus V3 blueprint with
/// its exact empty applied-parameter list. See F05.2a Amendment R2.
const state_validator_script_hash: ByteArray = #"b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66"

validator f05_authority_policy(genesis_ref: OutputReference, initial_keys: List<ByteArray>) {
  mint(
    redeemer: AuthorityBootstrapRedeemer,
    policy_id: PolicyId,
    tx: Transaction,
  ) {
    let BootstrapAuthority { proofs } = redeemer
    validate_bootstrap(genesis_ref, initial_keys, proofs, policy_id, tx)
  }

  else(_) {
    fail
  }
}

fn validate_bootstrap(
  genesis_ref: OutputReference,
  initial_keys: List<ByteArray>,
  proofs: List<ByteArray>,
  policy_id: PolicyId,
  tx: Transaction,
) -> Bool {
  expect True
  expect count_state_credential_outputs(tx.outputs, state_validator_script_hash) == 1
  expect
    dict.to_pairs(assets.tokens(tx.mint, policy_id)) == [
      Pair(authority_asset_name, 1),
    ]
  expect [authority_output] = list.filter(tx.outputs, fn(output) {
    assets.quantity_of(output.value, policy_id, authority_asset_name) != 0
  })
  expect authority_output.address.payment_credential == Script(state_validator_script_hash)
  expect authority_output.address.stake_credential == None
  expect assets.quantity_of(authority_output.value, policy_id, authority_asset_name) == 1
  expect assets.lovelace_of(authority_output.value) == authority_initial_lovelace
  expect only_authority_nft(authority_output.value, policy_id)
  expect InlineDatum(raw_datum) = authority_output.datum
  expect state: AuthorityStateV3 = raw_datum
  expect valid_initial_authority(state, genesis_ref, initial_keys)
  let bootstrap_message = authority_genesis_pop_preimage(
    genesis_ref,
    state_validator_script_hash,
    initial_keys,
  )
  valid_bootstrap_proofs(initial_keys, proofs, bootstrap_message)
}

fn count_seed_input(inputs: List<Input>, seed_ref: OutputReference) -> Int {
  list.length(
    list.filter(inputs, fn(input) {
      same_output_reference(input.output_reference, seed_ref)
    }),
  )
}

fn count_state_credential_outputs(
  outputs: List<Output>,
  state_credential: ByteArray,
) -> Int {
  list.length(
    list.filter(outputs, fn(output) {
      output.address.payment_credential == Script(state_credential)
    }),
  )
}

fn only_authority_nft(value: assets.Value, policy_id: PolicyId) -> Bool {
  when assets.flatten(assets.without_lovelace(value)) is {
    [(policy, name, _)] ->
      policy == policy_id
        && name == authority_asset_name
    _ -> False
  }
}
