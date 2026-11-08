//// VAMS Agent Registry Validator
////
//// Versioned F04 identity registry. The validator is intentionally strict:
//// legacy datums/redeemers are not accepted, identity units are bound to the
//// parameterized NFT policy, and every mutable transition is nonce/epoch bound.

use aiken/cbor
use aiken/collection/dict
use aiken/collection/list
use aiken/crypto.{blake2b_256}
use aiken/primitive/bytearray
use cardano/address.{Script}
use cardano/assets
use cardano/transaction.{InlineDatum, Input, Output, OutputReference, Transaction}
use vams/types.{
  AgentDatumV1, AgentNftRedeemer, BurnIdentity, DeregisterAgent, MintIdentity, RegistryAuthorityPayloadV1, RegistryAuthorityV1, RegistryRedeemerV1,
  RegisterAgent, SlashAgent, UpdateAgent,
}
use vams/utils.{is_signed_by}

const registry_schema_version: Int = 1
const min_agent_stake: Int = 1_000_000_000
const initial_reputation: Int = 5_000
const max_reputation: Int = 10_000
const min_did_length: Int = 32
const max_did_length: Int = 256
const verification_key_hash_bytes: Int = 28
const digest_bytes: Int = 32
const max_u16: Int = 65_535
const max_u64: Int = 18_446_744_073_709_551_615
const max_authorized_slashers: Int = 5
const max_transaction_inputs: Int = 16
const max_transaction_outputs: Int = 16
const max_transaction_assets: Int = 16
const max_datum_bytes: Int = 896
const identity_domain: ByteArray = #"56414d532f6167656e742f763100"

validator agent_registry(
  bootstrap_ref: OutputReference,
  trusted_authority_script_hash: ByteArray,
  trusted_authority_policy_id: ByteArray,
  trusted_authority_asset_name: ByteArray,
  trusted_authority_state_lovelace: Int,
  trusted_reserve_credential: ByteArray,
  trusted_authority_datum_commitment: ByteArray,
) {
  mint(redeemer: AgentNftRedeemer, policy_id: ByteArray, tx: Transaction) {
    let policy_tokens = assets.tokens(tx.mint, policy_id)
    expect [Pair(asset_name, amount)] = dict.to_pairs(policy_tokens)
    when redeemer is {
      MintIdentity { .. } -> False
      BurnIdentity { identity_asset_name, owner_vkh } ->
        amount == -1
          && bytearray.length(identity_asset_name) == digest_bytes
          && identity_asset_name == asset_name
          && bytearray.length(owner_vkh) == verification_key_hash_bytes
          && list.has(tx.extra_signatories, owner_vkh)
          && list.length(list.filter(tx.inputs, fn(input) {
            valid_burn_input(input, policy_id, asset_name, owner_vkh, bootstrap_ref, tx)
          })) == 1
          && list.length(list.filter(tx.outputs, fn(output) {
            assets.quantity_of(output.value, policy_id, asset_name) != 0
          })) == 0
    }
  }

  spend(
    datum_opt: Option<AgentDatumV1>,
    redeemer: RegistryRedeemerV1,
    own_ref: OutputReference,
    tx: Transaction,
  ) {
    expect Some(datum) = datum_opt
    expect Some(own_input) = list.find(tx.inputs, fn(input) { input.output_reference == own_ref })
    expect Script(script_hash) = own_input.output.address.payment_credential
    expect datum.identity_policy_id == script_hash
    expect bounded_transaction(tx)
    expect valid_datum(datum)
    expect unique_authority_reference(
      tx.reference_inputs,
      datum.identity_policy_id,
      bootstrap_ref,
      trusted_authority_script_hash,
      trusted_authority_policy_id,
      trusted_authority_asset_name,
      trusted_authority_state_lovelace,
      trusted_reserve_credential,
      trusted_authority_datum_commitment,
    )

    when redeemer is {
      RegisterAgent { did, metadata_hash, operator } ->
        validate_register(
          datum, did, metadata_hash, operator, own_input, tx,
          bootstrap_ref, trusted_authority_script_hash,
          trusted_authority_policy_id, trusted_authority_asset_name,
          trusted_authority_state_lovelace, trusted_reserve_credential,
          trusted_authority_datum_commitment,
        )
      UpdateAgent {
        new_metadata_hash,
        new_operator,
        expected_nonce,
        expected_action_epoch,
      } ->
        validate_update(
          datum, new_metadata_hash, new_operator, expected_nonce,
          expected_action_epoch, own_input, tx,
          bootstrap_ref, trusted_authority_script_hash,
          trusted_authority_policy_id, trusted_authority_asset_name,
          trusted_authority_state_lovelace, trusted_reserve_credential,
          trusted_authority_datum_commitment,
        )
      DeregisterAgent { expected_nonce, expected_action_epoch } ->
        validate_deregister(
          datum, expected_nonce, expected_action_epoch, own_input, tx,
          bootstrap_ref, trusted_authority_script_hash,
          trusted_authority_policy_id, trusted_authority_asset_name,
          trusted_authority_state_lovelace, trusted_reserve_credential,
          trusted_authority_datum_commitment,
        )
      SlashAgent { .. } -> False
    }
  }

  else(_) {
    fail
  }
}

fn validate_register(
  datum: AgentDatumV1,
  did: ByteArray,
  metadata_hash: ByteArray,
  operator: ByteArray,
  own_input: Input,
  tx: Transaction,
  bootstrap_ref: OutputReference,
  trusted_authority_script_hash: ByteArray,
  trusted_authority_policy_id: ByteArray,
  trusted_authority_asset_name: ByteArray,
  trusted_authority_state_lovelace: Int,
  trusted_reserve_credential: ByteArray,
  trusted_authority_datum_commitment: ByteArray,
) -> Bool {
  expect input_identity(own_input, datum) == 0
  expect is_signed_by(tx.extra_signatories, datum.owner)
  expect valid_did(did)
  expect bootstrap_consumed(tx, bootstrap_ref)
  expect derive_identity_name(did, datum.owner, bootstrap_ref) == datum.identity_asset_name
  expect bytearray.length(metadata_hash) == digest_bytes
  expect bytearray.length(operator) == verification_key_hash_bytes
  expect assets.quantity_of(tx.mint, datum.identity_policy_id, datum.identity_asset_name) == 1
  expect count_minted_assets(tx.mint) == 1
  expect [next_output] = outputs_with_asset(tx.outputs, datum.identity_policy_id, datum.identity_asset_name)
  expect assets.quantity_of(next_output.value, datum.identity_policy_id, datum.identity_asset_name) == 1
  expect next_output.address == own_input.output.address
  expect conserved_registration_value(own_input.output.value, next_output.value, datum.identity_policy_id, datum.identity_asset_name)
  expect InlineDatum(raw_next) = next_output.datum
  expect next: AgentDatumV1 = raw_next
  expect next.schema_version == registry_schema_version
  expect next.identity_policy_id == datum.identity_policy_id
  expect next.identity_asset_name == datum.identity_asset_name
  expect next.nonce == 0
  expect next.did == did
  expect next.owner == datum.owner
  expect next.operator == operator
  expect next.stake_lovelace >= min_agent_stake
  expect assets.lovelace_of(next_output.value) == next.stake_lovelace
  expect exact_identity_value(next_output.value, datum.identity_policy_id, datum.identity_asset_name)
  expect next.reputation_bps == initial_reputation
  expect next.metadata_hash == metadata_hash
  expect next.status == 0
  expect next.action_epoch == authority_epoch(
    tx.reference_inputs, datum.identity_policy_id, bootstrap_ref,
    trusted_authority_script_hash, trusted_authority_policy_id,
    trusted_authority_asset_name, trusted_authority_state_lovelace,
    trusted_reserve_credential, trusted_authority_datum_commitment,
  )
  expect next.authorized_slashers == []
  valid_datum(next)
}

fn validate_update(
  datum: AgentDatumV1,
  new_metadata_hash: ByteArray,
  new_operator: ByteArray,
  expected_nonce: Int,
  expected_action_epoch: Int,
  own_input: Input,
  tx: Transaction,
  bootstrap_ref: OutputReference,
  trusted_authority_script_hash: ByteArray,
  trusted_authority_policy_id: ByteArray,
  trusted_authority_asset_name: ByteArray,
  trusted_authority_state_lovelace: Int,
  trusted_reserve_credential: ByteArray,
  trusted_authority_datum_commitment: ByteArray,
) -> Bool {
  expect input_identity(own_input, datum) == 1
  expect datum.status == 0
  expect authority_epoch(
    tx.reference_inputs, datum.identity_policy_id, bootstrap_ref,
    trusted_authority_script_hash, trusted_authority_policy_id,
    trusted_authority_asset_name, trusted_authority_state_lovelace,
    trusted_reserve_credential, trusted_authority_datum_commitment,
  ) == datum.action_epoch
  expect expected_nonce == datum.nonce
  expect expected_action_epoch == datum.action_epoch
  expect bytearray.length(new_metadata_hash) == digest_bytes
  expect bytearray.length(new_operator) == verification_key_hash_bytes
  expect (is_signed_by(tx.extra_signatories, datum.owner) || (new_operator == datum.operator && is_signed_by(tx.extra_signatories, datum.operator)))
  expect [next_output] = outputs_with_asset(tx.outputs, datum.identity_policy_id, datum.identity_asset_name)
  expect unique_state_output(tx.outputs, datum.identity_policy_id, datum.identity_asset_name)
  expect next_output.address == own_input.output.address
  expect assets.quantity_of(next_output.value, datum.identity_policy_id, datum.identity_asset_name) == 1
  expect InlineDatum(raw_next) = next_output.datum
  expect next: AgentDatumV1 = raw_next
  expect next.schema_version == datum.schema_version
  expect next.identity_policy_id == datum.identity_policy_id
  expect next.identity_asset_name == datum.identity_asset_name
  expect next.nonce == datum.nonce + 1
  expect next.did == datum.did
  expect next.owner == datum.owner
  expect next.operator == new_operator
  expect next.stake_lovelace == datum.stake_lovelace
  expect next.reputation_bps == datum.reputation_bps
  expect next.metadata_hash == new_metadata_hash
  expect next.status == datum.status
  expect next.action_epoch == datum.action_epoch
  expect next.registered_at_ms == datum.registered_at_ms
  expect next.authorized_slashers == datum.authorized_slashers
  expect conserved_full_value(own_input.output.value, next_output.value)
  valid_datum(next)
}

fn validate_deregister(
  datum: AgentDatumV1,
  expected_nonce: Int,
  expected_action_epoch: Int,
  own_input: Input,
  tx: Transaction,
  bootstrap_ref: OutputReference,
  trusted_authority_script_hash: ByteArray,
  trusted_authority_policy_id: ByteArray,
  trusted_authority_asset_name: ByteArray,
  trusted_authority_state_lovelace: Int,
  trusted_reserve_credential: ByteArray,
  trusted_authority_datum_commitment: ByteArray,
) -> Bool {
  expect input_identity(own_input, datum) == 1
  expect datum.status == 0
  expect authority_epoch(
    tx.reference_inputs, datum.identity_policy_id, bootstrap_ref,
    trusted_authority_script_hash, trusted_authority_policy_id,
    trusted_authority_asset_name, trusted_authority_state_lovelace,
    trusted_reserve_credential, trusted_authority_datum_commitment,
  ) == datum.action_epoch
  expect is_signed_by(tx.extra_signatories, datum.owner)
  expect expected_nonce == datum.nonce
  expect expected_action_epoch == datum.action_epoch
  expect assets.quantity_of(tx.mint, datum.identity_policy_id, datum.identity_asset_name) == -1
  expect count_minted_assets(tx.mint) == 1
  expect count_state_outputs(tx.outputs, datum.identity_policy_id, datum.identity_asset_name) == 0
  expect [payout] = list.filter(tx.outputs, fn(output) { output.address == address.from_verification_key(datum.owner) })
  expect assets.lovelace_of(payout.value) == assets.lovelace_of(own_input.output.value)
  expect assets.quantity_of(payout.value, datum.identity_policy_id, datum.identity_asset_name) == 0
  expect conserved_non_identity(own_input.output.value, payout.value, datum.identity_policy_id, datum.identity_asset_name)
  expect list.length(list.filter(tx.outputs, fn(output) { output.address == address.from_verification_key(datum.owner) })) == 1
  True
}

fn unique_authority_reference(
  refs: List<Input>, identity_policy_id: ByteArray, bootstrap_ref: OutputReference,
  trusted_authority_script_hash: ByteArray, trusted_authority_policy_id: ByteArray,
  trusted_authority_asset_name: ByteArray, trusted_authority_state_lovelace: Int,
  trusted_reserve_credential: ByteArray, trusted_authority_datum_commitment: ByteArray,
) -> Bool {
  list.length(list.filter(refs, fn(input) {
    valid_authority_input(input, identity_policy_id, bootstrap_ref, trusted_authority_script_hash,
      trusted_authority_policy_id, trusted_authority_asset_name, trusted_authority_state_lovelace,
      trusted_reserve_credential, trusted_authority_datum_commitment)
  })) == 1 && list.length(refs) == 1
}

fn authority_epoch(
  refs: List<Input>, identity_policy_id: ByteArray, bootstrap_ref: OutputReference,
  trusted_authority_script_hash: ByteArray, trusted_authority_policy_id: ByteArray,
  trusted_authority_asset_name: ByteArray, trusted_authority_state_lovelace: Int,
  trusted_reserve_credential: ByteArray, trusted_authority_datum_commitment: ByteArray,
) -> Int {
  expect [input] = list.filter(refs, fn(candidate) {
    valid_authority_input(candidate, identity_policy_id, bootstrap_ref, trusted_authority_script_hash,
      trusted_authority_policy_id, trusted_authority_asset_name, trusted_authority_state_lovelace,
      trusted_reserve_credential, trusted_authority_datum_commitment)
  })
  expect InlineDatum(raw) = input.output.datum
  expect authority: RegistryAuthorityV1 = raw
  authority.action_epoch
}

fn valid_authority_input(
  input: Input, identity_policy_id: ByteArray, bootstrap_ref: OutputReference,
  trusted_authority_script_hash: ByteArray, trusted_authority_policy_id: ByteArray,
  trusted_authority_asset_name: ByteArray, trusted_authority_state_lovelace: Int,
  trusted_reserve_credential: ByteArray, trusted_authority_datum_commitment: ByteArray,
) -> Bool {
  expect Script(_) = input.output.address.payment_credential
  expect InlineDatum(raw) = input.output.datum
  expect authority: RegistryAuthorityV1 = raw
  authority.schema_version == registry_schema_version
    && authority.identity_policy_id == identity_policy_id
    && authority.bootstrap_ref == bootstrap_ref
    && authority.authority_script_hash == trusted_authority_script_hash
    && authority.authority_policy_id == trusted_authority_policy_id
    && authority.authority_asset_name == trusted_authority_asset_name
    && authority.authority_state_lovelace == trusted_authority_state_lovelace
    && authority.reserve_credential == trusted_reserve_credential
    && bytearray.length(authority.authority_script_hash) == 28
    && bytearray.length(authority.authority_policy_id) == 28
    && bytearray.length(authority.authority_asset_name) == 32
    && authority.authority_quantity == 1
    && authority.authority_state_lovelace > 0
    && input.output.address == address.from_script(authority.authority_script_hash)
    && assets.quantity_of(input.output.value, authority.authority_policy_id, authority.authority_asset_name) == 1
    && assets.lovelace_of(input.output.value) == authority.authority_state_lovelace
    && bytearray.length(authority.reserve_credential) == verification_key_hash_bytes
    && bytearray.length(authority.authority_address) == verification_key_hash_bytes
    && authority.authority_address == authority.authority_script_hash
    && bytearray.length(trusted_authority_datum_commitment) == digest_bytes
    && authority.datum_hash == trusted_authority_datum_commitment
    && blake2b_256(cbor.serialise(RegistryAuthorityPayloadV1 {
      schema_version: authority.schema_version,
      identity_policy_id: #"",
      bootstrap_ref: authority.bootstrap_ref,
      action_epoch: 0,
      slash_enabled: False,
      authority_script_hash: authority.authority_script_hash,
      authority_policy_id: authority.authority_policy_id,
      authority_asset_name: authority.authority_asset_name,
      authority_quantity: authority.authority_quantity,
      authority_state_lovelace: authority.authority_state_lovelace,
      reserve_credential: authority.reserve_credential,
      authority_address: authority.authority_address,
    })) == trusted_authority_datum_commitment
    && exact_authority_value(input.output.value, authority.authority_policy_id, authority.authority_asset_name, authority.authority_state_lovelace)
}

fn bootstrap_consumed(tx: Transaction, bootstrap_ref: OutputReference) -> Bool {
  list.length(list.filter(tx.inputs, fn(input) { input.output_reference == bootstrap_ref })) == 1
}

fn derive_identity_name(did: ByteArray, owner: ByteArray, seed: OutputReference) -> ByteArray {
  blake2b_256(
    bytearray.concat(
      identity_domain,
      bytearray.concat(
        bytearray.from_int_big_endian(bytearray.length(did), 2),
        bytearray.concat(
          did,
          bytearray.concat(
            owner,
            bytearray.concat(seed.transaction_id, bytearray.from_int_big_endian(seed.output_index, 4)),
          ),
        ),
      ),
    ),
  )
}

fn conserved_registration_value(before: assets.Value, after: assets.Value, policy_id: ByteArray, asset_name: ByteArray) -> Bool {
  assets.lovelace_of(before) == assets.lovelace_of(after)
    && assets.quantity_of(before, policy_id, asset_name) == 0
    && assets.quantity_of(after, policy_id, asset_name) == 1
    && conserved_non_identity(before, after, policy_id, asset_name)
}

fn conserved_non_identity(before: assets.Value, after: assets.Value, policy_id: ByteArray, asset_name: ByteArray) -> Bool {
  list.all(
    assets.flatten_with(before, fn(policy, name, quantity) {
      if policy == policy_id && name == asset_name { None } else { Some(assets.quantity_of(after, policy, name) == quantity) }
    }),
    fn(ok) { ok },
  )
    && list.all(
      assets.flatten_with(after, fn(policy, name, quantity) {
        if policy == policy_id && name == asset_name { None } else { Some(assets.quantity_of(before, policy, name) == quantity) }
      }),
      fn(ok) { ok },
    )
}

fn valid_burn_input(
  input: Input, policy_id: ByteArray, asset_name: ByteArray, owner_vkh: ByteArray,
  bootstrap_ref: OutputReference, tx: Transaction,
) -> Bool {
  expect Script(script_hash) = input.output.address.payment_credential
  expect InlineDatum(raw) = input.output.datum
  expect datum: AgentDatumV1 = raw
  script_hash == policy_id
    && valid_datum(datum)
    && datum.identity_policy_id == policy_id
    && datum.identity_asset_name == asset_name
    && derive_identity_name(datum.did, datum.owner, bootstrap_ref) == asset_name
    && datum.owner == owner_vkh
    && datum.status == 0
    && assets.quantity_of(input.output.value, policy_id, asset_name) == 1
    && list.length(list.filter(tx.outputs, fn(output) {
      output.address == address.from_verification_key(owner_vkh)
    })) == 1
    && expect_owner_payout(tx.outputs, input.output.value, policy_id, asset_name, owner_vkh)
}

fn expect_owner_payout(
  outputs: List<Output>, before: assets.Value, policy_id: ByteArray,
  asset_name: ByteArray, owner_vkh: ByteArray,
) -> Bool {
  expect [payout] = list.filter(outputs, fn(output) {
    output.address == address.from_verification_key(owner_vkh)
  })
  assets.lovelace_of(payout.value) == assets.lovelace_of(before)
    && assets.quantity_of(payout.value, policy_id, asset_name) == 0
    && conserved_non_identity(before, payout.value, policy_id, asset_name)
}

fn input_identity(input: Input, datum: AgentDatumV1) -> Int {
  assets.quantity_of(input.output.value, datum.identity_policy_id, datum.identity_asset_name)
}

fn valid_datum(datum: AgentDatumV1) -> Bool {
  datum.schema_version == registry_schema_version
    && bytearray.length(datum.identity_policy_id) == 28
    && bytearray.length(datum.identity_asset_name) == 32
    && datum.nonce >= 0
    && datum.nonce <= max_u64
    && valid_did(datum.did)
    && bytearray.length(datum.owner) == verification_key_hash_bytes
    && bytearray.length(datum.operator) == verification_key_hash_bytes
    && datum.stake_lovelace >= min_agent_stake
    && datum.stake_lovelace <= max_u64
    && datum.reputation_bps >= 0
    && datum.reputation_bps <= max_reputation
    && datum.reputation_bps <= max_u16
    && bytearray.length(datum.metadata_hash) == digest_bytes
    && (datum.status == 0 || datum.status == 1)
    && datum.action_epoch >= 0
    && datum.action_epoch <= max_u64
    && datum.registered_at_ms >= 0
    && datum.registered_at_ms <= max_u64
    && list.length(datum.authorized_slashers) <= max_authorized_slashers
    && list.length(list.unique(datum.authorized_slashers)) == list.length(datum.authorized_slashers)
    && list.all(datum.authorized_slashers, fn(slasher) { bytearray.length(slasher) == verification_key_hash_bytes })
    && bytearray.length(cbor.serialise(datum)) <= max_datum_bytes
}

fn valid_did(did: ByteArray) -> Bool {
  let size = bytearray.length(did)
  // AgentDatumV1.did is the identity-significant raw UTF-8 byte sequence.
  // Round-tripping rejects malformed UTF-8 without normalizing those bytes.
  size >= min_did_length
    && size <= max_did_length
    && bytearray.from_string(bytearray.to_string(did)) == did
}

fn exact_identity_value(value: assets.Value, policy_id: ByteArray, asset_name: ByteArray) -> Bool {
  list.all(
    assets.flatten_with(value, fn(policy, name, quantity) {
      if policy == #"" && name == #"" {
        Some(True)
      } else {
        Some(policy == policy_id && name == asset_name && quantity == 1)
      }
    }),
    fn(ok) { ok },
  )
}

fn conserved_full_value(before: assets.Value, after: assets.Value) -> Bool {
  list.all(
    assets.flatten_with(before, fn(policy, name, quantity) {
      Some(assets.quantity_of(after, policy, name) == quantity)
    }),
    fn(ok) { ok },
  )
    && list.all(
      assets.flatten_with(after, fn(policy, name, quantity) {
        Some(assets.quantity_of(before, policy, name) == quantity)
      }),
      fn(ok) { ok },
    )
}

fn exact_authority_value(value: assets.Value, policy_id: ByteArray, asset_name: ByteArray, lovelace: Int) -> Bool {
  list.all(
    assets.flatten_with(value, fn(policy, name, quantity) {
      if policy == #"" && name == #"" {
        Some(quantity == lovelace)
      } else {
        Some(policy == policy_id && name == asset_name && quantity == 1)
      }
    }),
    fn(ok) { ok },
  )
    && assets.quantity_of(value, policy_id, asset_name) == 1
    && assets.lovelace_of(value) == lovelace
}

fn bounded_transaction(tx: Transaction) -> Bool {
  list.length(tx.inputs) <= max_transaction_inputs
    && list.length(tx.reference_inputs) <= 4
    && list.length(tx.outputs) <= max_transaction_outputs
    && list.length(assets.flatten_with(tx.mint, fn(policy_id, asset_name, quantity) {
      if policy_id == #"" && asset_name == #"" { None } else { Some(quantity) }
    })) <= max_transaction_assets
}

fn count_minted_assets(value: assets.Value) -> Int {
  list.length(assets.flatten_with(value, fn(policy_id, asset_name, quantity) {
    if policy_id == #"" && asset_name == #"" { None } else { Some(quantity) }
  }))
}

fn outputs_with_asset(outputs: List<Output>, policy_id: ByteArray, asset_name: ByteArray) -> List<Output> {
  list.filter(outputs, fn(output) { assets.quantity_of(output.value, policy_id, asset_name) != 0 })
}

fn unique_state_output(outputs: List<Output>, policy_id: ByteArray, asset_name: ByteArray) -> Bool {
  list.length(outputs_with_asset(outputs, policy_id, asset_name)) == 1
}

fn count_state_outputs(outputs: List<Output>, policy_id: ByteArray, asset_name: ByteArray) -> Int {
  list.length(outputs_with_asset(outputs, policy_id, asset_name))
}

test min_stake_is_one_thousand_ada() { min_agent_stake == 1_000_000_000 }
test initial_reputation_is_fifty_percent() { initial_reputation == 5_000 }
test did_lower_bound() { valid_did(bytearray.from_string(@"00000000000000000000000000000000")) == True }
test did_upper_bound() { valid_did(bytearray.from_string(@"0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000")) == True }
test did_out_of_bounds() { valid_did(bytearray.from_string(@"0000000000000000000000000000000")) == False }
test did_above_upper_bound() { valid_did(bytearray.from_string(@"00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000")) == False }
test did_rejects_malformed_utf8_bytes() fail { valid_did(#"ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff") }
test did_accepts_non_hex_utf8_presentation() { valid_did(bytearray.from_string(@"VAMS-agent-identity-000000000000")) == True }

test option_b_raw_utf8_vector_derives_frozen_identity() {
  derive_identity_name(
    #"6469643a76616d733a6167656e743a0101010101010101010101010101010101",
    #"22222222222222222222222222222222222222222222222222222222",
    OutputReference {
      transaction_id: #"1111111111111111111111111111111111111111111111111111111111111111",
      output_index: 7,
    },
  ) == #"3643e533306496437abad612c84592b4f07e9cef3cf424125cb8bd4c36427145"
}

test option_b_ascii_hex_reinterpretation_changes_identity() {
  derive_identity_name(
    bytearray.from_string(@"6469643a76616d733a6167656e743a0101010101010101010101010101010101"),
    #"22222222222222222222222222222222222222222222222222222222",
    OutputReference {
      transaction_id: #"1111111111111111111111111111111111111111111111111111111111111111",
      output_index: 7,
    },
  ) != #"3643e533306496437abad612c84592b4f07e9cef3cf424125cb8bd4c36427145"
}
