//// F04 fixed shared anchor issuance policy P0(S0).
//// P0 is parameterized only by the fixed S0 lock hash. It does not prove
//// registry compiler provenance or any registration/global uniqueness property.

use aiken/cbor
use aiken/collection/dict
use aiken/collection/list
use aiken/crypto.{blake2b_256}
use aiken/primitive/bytearray
use cardano/address.{Script}
use cardano/assets
use cardano/assets.{PolicyId}
use cardano/transaction.{InlineDatum, Input, Output, OutputReference, Transaction}
use vams/f04_anchor_types.{AnchorDatumV2, AnchorPolicyRedeemer, IssueAnchor}

const anchor_domain: ByteArray = #"56414d532f6167656e742d616e63686f722f763200"
const identity_domain: ByteArray = #"56414d532f6167656e742f763100"
const key_hash_bytes: Int = 28
const digest_bytes: Int = 32
const minimum_did_bytes: Int = 32
const maximum_did_bytes: Int = 256
const minimum_stake_lovelace: Int = 1_000_000_000
const maximum_u16: Int = 65_535
const maximum_u32: Int = 4_294_967_295
const maximum_u64: Int = 18_446_744_073_709_551_615
const maximum_inputs: Int = 16
const maximum_reference_inputs: Int = 4
const maximum_outputs: Int = 16
const maximum_datum_bytes: Int = 2_048
const expected_guardians: Int = 5
const required_guardians: Int = 3
const initial_reputation_bps: Int = 5_000

validator f04_anchor_policy(anchor_lock_script_hash: ByteArray) {
  mint(redeemer: AnchorPolicyRedeemer, policy_id: PolicyId, tx: Transaction) {
    expect IssueAnchor { anchor_seed } = redeemer
    validate_issue(anchor_lock_script_hash, anchor_seed, policy_id, tx)
  }

  else(_) {
    fail
  }
}

fn validate_issue(
  anchor_lock_script_hash: ByteArray,
  anchor_seed: OutputReference,
  policy_id: PolicyId,
  tx: Transaction,
) -> Bool {
  expect bounded_transaction(tx)
  expect count_inputs(tx.inputs, anchor_seed) == 1
  expect [Pair(anchor_name, quantity)] = dict.to_pairs(assets.tokens(tx.mint, policy_id))
  expect quantity == 1
  expect list.length(assets.flatten(tx.mint)) == 1
  expect [anchor_output] = list.filter(tx.outputs, fn(output) {
    assets.quantity_of(output.value, policy_id, anchor_name) != 0
  })
  expect count_outputs_with_asset(tx.outputs, policy_id, anchor_name) == 1
  expect InlineDatum(raw_anchor) = anchor_output.datum
  expect datum: AnchorDatumV2 = raw_anchor
  expect valid_anchor_datum(datum)
  expect datum.anchor_seed == anchor_seed
  expect anchor_seed != datum.bootstrap_ref
  expect count_inputs(tx.inputs, datum.bootstrap_ref) == 0
  expect count_references(tx.reference_inputs, datum.bootstrap_ref) == 1
  expect Some(bootstrap_input) = list.find(tx.reference_inputs, fn(input) {
    input.output_reference == datum.bootstrap_ref
  })
  expect InlineDatum(raw_bootstrap) = bootstrap_input.output.datum
  expect datum.identity_asset_name == derive_identity_name(
    datum.did, datum.founding_owner_vkh, datum.bootstrap_ref,
  )
  expect anchor_name == derive_anchor_name(datum)
  expect valid_pre_genesis(raw_bootstrap, bootstrap_input, datum)
  expect list.has(tx.extra_signatories, datum.founding_owner_vkh)
  expect signed_guardian_count(datum.initial_guardians, tx.extra_signatories) >= required_guardians
  expect bytearray.length(anchor_lock_script_hash) == key_hash_bytes
  expect anchor_output.address.payment_credential == Script(anchor_lock_script_hash)
  expect anchor_output.address.stake_credential == None
  expect anchor_output.reference_script == None
  expect assets.quantity_of(anchor_output.value, policy_id, anchor_name) == 1
  expect assets.lovelace_of(anchor_output.value) == datum.anchor_lovelace
  expect assets.flatten(assets.without_lovelace(anchor_output.value)) == [
    (policy_id, anchor_name, 1),
  ]
  expect bytearray.length(cbor.serialise(raw_anchor)) <= maximum_datum_bytes
  True
}

fn bounded_transaction(tx: Transaction) -> Bool {
  list.length(tx.inputs) <= maximum_inputs
    && list.length(tx.reference_inputs) <= maximum_reference_inputs
    && list.length(tx.outputs) <= maximum_outputs
}

fn count_inputs(inputs: List<Input>, reference: OutputReference) -> Int {
  list.length(list.filter(inputs, fn(input) {
    input.output_reference == reference
  }))
}

fn count_references(inputs: List<Input>, reference: OutputReference) -> Int {
  list.length(list.filter(inputs, fn(input) {
    input.output_reference == reference
  }))
}

fn valid_pre_genesis(
  raw: Data,
  input: Input,
  datum: AnchorDatumV2,
) -> Bool {
  expect Constr(2, fields) = raw
  expect [
    schema_data,
    did_data,
    founder_data,
    controller_data,
    operator_data,
    guardians_data,
    metadata_data,
    stake_data,
  ] = fields
  let did = builtin.un_b_data(did_data)
  let founder = builtin.un_b_data(founder_data)
  let controller = builtin.un_b_data(controller_data)
  let operator = builtin.un_b_data(operator_data)
  let guardians = list.map(builtin.un_list_data(guardians_data), builtin.un_b_data)
  let metadata = builtin.un_b_data(metadata_data)
  let stake = builtin.un_i_data(stake_data)
  expect Script(registry_hash) = input.output.address.payment_credential
  builtin.un_i_data(schema_data) == 2
    && list.length(fields) == 8
    && bytearray.length(did) >= minimum_did_bytes
    && bytearray.length(did) <= maximum_did_bytes
    && valid_utf8(did)
    && bytearray.length(founder) == key_hash_bytes
    && bytearray.length(controller) == key_hash_bytes
    && bytearray.length(operator) == key_hash_bytes
    && bytearray.length(metadata) == digest_bytes
    && stake >= minimum_stake_lovelace
    && stake <= maximum_u64
    && registry_hash == datum.registry_script_hash
    && input.output.address.stake_credential == None
    && assets.lovelace_of(input.output.value) == stake
    && assets.flatten(assets.without_lovelace(input.output.value)) == []
    && did == datum.did
    && founder == datum.founding_owner_vkh
    && controller == datum.initial_controller_vkh
    && operator == datum.initial_operator_vkh
    && guardians == datum.initial_guardians
    && metadata == datum.initial_metadata_hash
    && stake == datum.initial_stake_lovelace
}

fn valid_anchor_datum(datum: AnchorDatumV2) -> Bool {
  datum.schema_version == 2
    && valid_output_reference(datum.anchor_seed)
    && valid_output_reference(datum.bootstrap_ref)
    && datum.anchor_seed != datum.bootstrap_ref
    && bytearray.length(datum.identity_policy_id) == key_hash_bytes
    && bytearray.length(datum.identity_asset_name) == digest_bytes
    && bytearray.length(datum.did) >= minimum_did_bytes
    && bytearray.length(datum.did) <= maximum_did_bytes
    && valid_utf8(datum.did)
    && bytearray.length(datum.founding_owner_vkh) == key_hash_bytes
    && bytearray.length(datum.initial_controller_vkh) == key_hash_bytes
    && bytearray.length(datum.initial_operator_vkh) == key_hash_bytes
    && valid_guardians(
      datum.initial_guardians,
      datum.founding_owner_vkh,
      datum.initial_controller_vkh,
      datum.initial_operator_vkh,
    )
    && bytearray.length(datum.registry_script_hash) == key_hash_bytes
    && bytearray.length(datum.initial_metadata_hash) == digest_bytes
    && datum.genesis_control_epoch == 0
    && datum.genesis_guardian_epoch == 0
    && datum.anchor_lovelace > 0
    && datum.anchor_lovelace <= maximum_u64
    && datum.initial_stake_lovelace >= minimum_stake_lovelace
    && datum.initial_stake_lovelace <= maximum_u64
    && datum.initial_reputation_bps == initial_reputation_bps
}

fn valid_output_reference(reference: OutputReference) -> Bool {
  reference.output_index >= 0 && reference.output_index <= maximum_u32
}

fn valid_utf8(value: ByteArray) -> Bool {
  bytearray.from_string(bytearray.to_string(value)) == value
}

fn valid_guardians(
  guardians: List<ByteArray>,
  founder: ByteArray,
  controller: ByteArray,
  operator: ByteArray,
) -> Bool {
  list.length(guardians) == expected_guardians
    && guardians_sorted_distinct(guardians)
    && list.all(guardians, fn(guardian) {
      bytearray.length(guardian) == key_hash_bytes
        && guardian != founder
        && guardian != controller
        && guardian != operator
    })
}

fn guardians_sorted_distinct(guardians: List<ByteArray>) -> Bool {
  when guardians is {
    [] -> True
    [_] -> True
    [first, second, ..rest] ->
      bytearray.compare(first, second) == Less
        && guardians_sorted_distinct([second, ..rest])
  }
}

fn signed_guardian_count(
  guardians: List<ByteArray>,
  signatories: List<ByteArray>,
) -> Int {
  list.length(list.filter(guardians, fn(guardian) {
    list.has(signatories, guardian)
  }))
}

fn count_outputs_with_asset(
  outputs: List<Output>,
  policy_id: PolicyId,
  asset_name: ByteArray,
) -> Int {
  list.length(list.filter(outputs, fn(output) {
    assets.quantity_of(output.value, policy_id, asset_name) != 0
  }))
}

fn derive_identity_name(
  did: ByteArray,
  owner_vkh: ByteArray,
  bootstrap_ref: OutputReference,
) -> ByteArray {
  blake2b_256(concat_fields([
    identity_domain,
    bytearray.from_int_big_endian(bytearray.length(did), 2),
    did,
    owner_vkh,
    bootstrap_ref.transaction_id,
    bytearray.from_int_big_endian(bootstrap_ref.output_index, 4),
  ]))
}

fn derive_anchor_name(datum: AnchorDatumV2) -> ByteArray {
  blake2b_256(concat_fields([
    anchor_domain,
    bytearray.from_int_big_endian(datum.schema_version, 2),
    datum.anchor_seed.transaction_id,
    bytearray.from_int_big_endian(datum.anchor_seed.output_index, 4),
    datum.bootstrap_ref.transaction_id,
    bytearray.from_int_big_endian(datum.bootstrap_ref.output_index, 4),
    datum.identity_policy_id,
    datum.identity_asset_name,
    bytearray.from_int_big_endian(bytearray.length(datum.did), 2),
    datum.did,
    datum.founding_owner_vkh,
    datum.initial_controller_vkh,
    datum.initial_operator_vkh,
    list.at(datum.initial_guardians, 0),
    list.at(datum.initial_guardians, 1),
    list.at(datum.initial_guardians, 2),
    list.at(datum.initial_guardians, 3),
    list.at(datum.initial_guardians, 4),
    datum.registry_script_hash,
    datum.initial_metadata_hash,
    bytearray.from_int_big_endian(datum.genesis_control_epoch, 8),
    bytearray.from_int_big_endian(datum.genesis_guardian_epoch, 8),
    bytearray.from_int_big_endian(datum.anchor_lovelace, 8),
    bytearray.from_int_big_endian(datum.initial_stake_lovelace, 8),
    bytearray.from_int_big_endian(datum.initial_reputation_bps, 2),
  ]))
}

fn concat_fields(fields: List<ByteArray>) -> ByteArray {
  when fields is {
    [] -> #""
    [field, ..rest] -> bytearray.concat(field, concat_fields(rest))
  }
}
