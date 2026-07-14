//// VAMS VDSO Cardano Conformance Boundary
////
//// Cardano remains the authoritative host for its assigned governance,
//// identity, and insurance state domains.  This v1 canary module implements
//// commitment and non-economic transition conformance only.  RESERVE and
//// value-bearing transitions fail closed until destination fencing and
//// authenticated non-execution proofs are available.

use aiken/crypto.{keccak_256}
use aiken/primitive/bytearray
use aiken/primitive/int

const intent_v1_domain: ByteArray = #"56414d533a494e54454e543a7631"

/// Exact `unsigned_intent_cbor` from `vams-vm/vectors/vir-core-v1.json`.
const shared_unsigned_intent_cbor: ByteArray =
  #"90015820313131313131313131313131313131313131313131313131313131313131313183582030303030303030303030303030303030303030303030303030303030303030300104182a1903e75820665438cdbc643b5d3947e47fd56d14a792daa805dee405ffc423c445095392a15820606060606060606060606060606060606060606060606060606060606060606082845820202020202020202020202020202020202020202020202020202020202020202000058084582021212121212121212121212121212121212121212121212121212121212121210307805820902188534cc8e8be436828d1329c194c793d2f591921e6f0d42c48379bfb14fc5820507c1c9e5414952f2017497a5a6da6cf639c820712d2266d2978ae5a200a3dcf582061616161616161616161616161616161616161616161616161616161616161615820626262626262626262626262626262626262626262626262626262626262626202021864191388"

const shared_intent_id: ByteArray =
  #"34ff92df19e5c307274e04c67c86cc1df590f48c91013ccdf8fb488125b7824c"

/// Exact `settlement_metadata_cbor` from `vams-vm/vectors/vir-core-v1.json`.
const shared_settlement_cbor: ByteArray =
  #"8a025820c3142a5bebfe0b0d57272ba32a131a16bf681c2a9ac06a05a123cdc2d386ac4983582030303030303030303030303030303030303030303030303030303030303030300104000158207070707070707070707070707070707070707070707070707070707070707070582071717171717171717171717171717171717171717171717171717171717171711a0001e2405820727272727272727272727272727272727272727272727272727272727272727258207373737373737373737373737373737373737373737373737373737373737373"

const shared_settlement_commitment: ByteArray =
  #"efb5379cbf100ce26823274a3742474a454d77143c72e186ddfa0d70c35b4558"

const zero_hash: ByteArray =
  #"0000000000000000000000000000000000000000000000000000000000000000"

const max_uint64: Int = 18446744073709551615

const shadow_read_domain: ByteArray =
  #"56414d533a5644534f3a534841444f573a524541443a7631"

const sample_receipt_hash: ByteArray =
  #"c3142a5bebfe0b0d57272ba32a131a16bf681c2a9ac06a05a123cdc2d386ac49"

const sample_state_domain: ByteArray =
  #"3030303030303030303030303030303030303030303030303030303030303030"

const sample_source_reference: ByteArray =
  #"7070707070707070707070707070707070707070707070707070707070707070"

const sample_source_transaction: ByteArray =
  #"7171717171717171717171717171717171717171717171717171717171717171"

const sample_bridge_proof_hash: ByteArray =
  #"7272727272727272727272727272727272727272727272727272727272727272"

const sample_payload_hash: ByteArray =
  #"7373737373737373737373737373737373737373737373737373737373737373"

pub type VdsoAccessMode {
  Read
  Consume
  Reserve
  Accumulate
}

pub type VdsoHostAuthority {
  Polygon
  Cardano
}

pub type VdsoDomainAuthorityBinding {
  state_domain: ByteArray,
  host_authority: VdsoHostAuthority,
  authority_epoch: Int,
}

/// Restricted-CBOR host mapping shared by Rust, Python, and Aiken. Solidity's
/// ABI enum includes a leading NONE sentinel and is mapped semantically rather
/// than ABI-encoded into this value.
pub fn host_authority_wire(host: VdsoHostAuthority) -> Int {
  when host is {
    Polygon -> 0
    Cardano -> 1
  }
}

pub type VdsoObjectDatum {
  schema_version: Int,
  object_id: ByteArray,
  object_type: ByteArray,
  authority: ByteArray,
  host_authority: VdsoHostAuthority,
  state_domain: ByteArray,
  version: Int,
  data_commitment: ByteArray,
  policy_hash: ByteArray,
  /// Zero is non-economic. Positive values are blocked in the v1 canary.
  value_class: Int,
}

pub type VdsoTransition {
  mode: VdsoAccessMode,
  expected_version: Int,
  writer: ByteArray,
  canonical_transition: ByteArray,
}

/// Settlement metadata never enters the semantic transition commitment.
/// Keeping bridge_proof_hash and payload_hash as distinct fields preserves INV-10.
pub type VdsoSettlementMetadata {
  schema_version: Int,
  receipt_hash: ByteArray,
  binding: VdsoDomainAuthorityBinding,
  source_host: VdsoHostAuthority,
  destination_host: VdsoHostAuthority,
  source_chain_reference: ByteArray,
  source_transaction_hash: ByteArray,
  settled_at_height: Int,
  bridge_proof_hash: ByteArray,
  payload_hash: ByteArray,
}

/// Hash already-canonical CBOR bytes using the VDSO v1 Keccak primitive.
/// Canonical CBOR construction remains off-chain and is checked against the
/// shared Rust/Python/Aiken vector corpus. Solidity enforces the equivalent
/// host/proof rules at its ABI boundary.
pub fn canonical_commitment(canonical_cbor: ByteArray) -> ByteArray {
  keccak_256(canonical_cbor)
}

/// Hash a canonical unsigned intent using the exact raw ASCII domain prefix.
pub fn canonical_intent_id(
  canonical_unsigned_intent_cbor: ByteArray,
) -> ByteArray {
  keccak_256(bytearray.concat(intent_v1_domain, canonical_unsigned_intent_cbor))
}

/// Cross-host settlement metadata is valid only when proof and payload remain
/// separate, non-empty values and authority moves between distinct hosts.
fn is_bytes32(value: ByteArray) -> Bool {
  bytearray.length(value) == 32
}

fn is_nonzero_bytes32(value: ByteArray) -> Bool {
  is_bytes32(value) && value != zero_hash
}

fn valid_settlement_binding(binding: VdsoDomainAuthorityBinding) -> Bool {
  is_bytes32(binding.state_domain) && binding.authority_epoch >= 0 && binding.authority_epoch <= max_uint64
}

pub fn valid_cross_host_settlement(metadata: VdsoSettlementMetadata) -> Bool {
  metadata.schema_version == 2 && valid_settlement_binding(metadata.binding) && metadata.destination_host == metadata.binding.host_authority && metadata.source_host != metadata.destination_host && is_nonzero_bytes32(
    metadata.receipt_hash,
  ) && is_nonzero_bytes32(metadata.source_chain_reference) && is_nonzero_bytes32(
    metadata.source_transaction_hash,
  ) && metadata.settled_at_height > 0 && metadata.settled_at_height <= max_uint64 && is_nonzero_bytes32(
    metadata.bridge_proof_hash,
  ) && is_nonzero_bytes32(metadata.payload_hash) && metadata.bridge_proof_hash != metadata.payload_hash
}

pub fn valid_same_host_settlement(metadata: VdsoSettlementMetadata) -> Bool {
  metadata.schema_version == 2 && valid_settlement_binding(metadata.binding) && metadata.source_host == metadata.destination_host && metadata.destination_host == metadata.binding.host_authority && is_nonzero_bytes32(
    metadata.receipt_hash,
  ) && metadata.source_chain_reference == zero_hash && metadata.source_transaction_hash == zero_hash && metadata.settled_at_height == 0 && metadata.bridge_proof_hash == zero_hash && metadata.payload_hash == zero_hash
}

fn settlement_fixture(
  schema_version: Int,
  source_host: VdsoHostAuthority,
  destination_host: VdsoHostAuthority,
  destination_authority: VdsoHostAuthority,
  source_chain_reference: ByteArray,
  source_transaction_hash: ByteArray,
  settled_at_height: Int,
  bridge_proof_hash: ByteArray,
  payload_hash: ByteArray,
) -> VdsoSettlementMetadata {
  VdsoSettlementMetadata {
    schema_version,
    receipt_hash: sample_receipt_hash,
    binding: VdsoDomainAuthorityBinding {
      state_domain: sample_state_domain,
      host_authority: destination_authority,
      authority_epoch: 4,
    },
    source_host,
    destination_host,
    source_chain_reference,
    source_transaction_hash,
    settled_at_height,
    bridge_proof_hash,
    payload_hash,
  }
}

pub fn is_cardano_canary_mode(mode: VdsoAccessMode) -> Bool {
  when mode is {
    Read -> True
    Accumulate -> True
    Consume -> False
    Reserve -> False
  }
}

pub fn valid_cardano_transition(
  before: VdsoObjectDatum,
  after: VdsoObjectDatum,
  transition: VdsoTransition,
) -> Bool {
  let common_fields_unchanged =
    before.schema_version == 1 && after.schema_version == before.schema_version && before.object_id == after.object_id && before.object_type == after.object_type && before.authority == after.authority && before.host_authority == Cardano && after.host_authority == Cardano && before.state_domain == after.state_domain && before.policy_hash == after.policy_hash && before.value_class == 0 && after.value_class == 0 && transition.writer == before.authority && transition.expected_version == before.version && transition.canonical_transition != #""

  if !common_fields_unchanged {
    False
  } else {
    when transition.mode is {
      Read ->
        after.version == before.version && after.data_commitment == before.data_commitment
      Accumulate ->
        after.version == before.version + 1 && after.data_commitment != before.data_commitment
      Consume -> False
      Reserve -> False
    }
  }
}

/// Standalone, conformance-only evaluator for the private VDSO shadow worker.
///
/// This function is exported with `aiken export` and evaluated with
/// `aiken uplc eval` for every shadow transition. It accepts commitment-only
/// inputs, reconstructs a non-economic Cardano READ transition, and returns
/// the transition commitment. Any mutation mode, root mismatch, malformed
/// canonical preimage, or commitment mismatch returns the all-zero sentinel.
/// It is deliberately not a validator entrypoint.
pub fn shadow_read_commitment(
  mode: Int,
  sequence: Int,
  expected_previous_root: ByteArray,
  actual_previous_root: ByteArray,
  input_commitment: ByteArray,
  canonical_transition: ByteArray,
  expected_commitment: ByteArray,
) -> ByteArray {
  let canonical_shape_is_valid =
    bytearray.length(canonical_transition) == 96 && bytearray.slice(
      canonical_transition,
      start: 0,
      end: 23,
    ) == shadow_read_domain && int.from_bytearray_big_endian(
      bytearray.slice(canonical_transition, start: 24, end: 31),
    ) == sequence && bytearray.slice(canonical_transition, start: 32, end: 63) == actual_previous_root && bytearray.slice(
      canonical_transition,
      start: 64,
      end: 95,
    ) == input_commitment

  let before =
    VdsoObjectDatum {
      schema_version: 1,
      object_id: input_commitment,
      object_type: zero_hash,
      authority: expected_previous_root,
      host_authority: Cardano,
      state_domain: sample_state_domain,
      version: sequence,
      data_commitment: input_commitment,
      policy_hash: zero_hash,
      value_class: 0,
    }
  let computed_commitment = canonical_commitment(canonical_transition)
  let transition =
    VdsoTransition {
      mode: Read,
      expected_version: sequence,
      writer: expected_previous_root,
      canonical_transition,
    }

  if mode == 0 && sequence >= 0 && sequence <= max_uint64 && is_nonzero_bytes32(
    expected_previous_root,
  ) && expected_previous_root == actual_previous_root && is_nonzero_bytes32(
    input_commitment,
  ) && is_nonzero_bytes32(expected_commitment) && canonical_shape_is_valid && computed_commitment == expected_commitment && valid_cardano_transition(
    before,
    before,
    transition,
  ) {
    computed_commitment
  } else {
    zero_hash
  }
}

fn sample_before() -> VdsoObjectDatum {
  VdsoObjectDatum {
    schema_version: 1,
    object_id: #"01",
    object_type: #"02",
    authority: #"03",
    host_authority: Cardano,
    state_domain: #"04",
    version: 7,
    data_commitment: #"05",
    policy_hash: #"06",
    value_class: 0,
  }
}

test cardano_read_preserves_state() {
  let before = sample_before()
  valid_cardano_transition(
    before,
    before,
    VdsoTransition {
      mode: Read,
      expected_version: 7,
      writer: #"03",
      canonical_transition: #"07",
    },
  )
}

test cardano_accumulate_increments_version() {
  let before = sample_before()
  let after = VdsoObjectDatum { ..before, version: 8, data_commitment: #"08" }
  valid_cardano_transition(
    before,
    after,
    VdsoTransition {
      mode: Accumulate,
      expected_version: 7,
      writer: #"03",
      canonical_transition: #"09",
    },
  )
}

test cardano_reserve_fails_closed() {
  let before = sample_before()
  !valid_cardano_transition(
    before,
    before,
    VdsoTransition {
      mode: Reserve,
      expected_version: 7,
      writer: #"03",
      canonical_transition: #"0a",
    },
  )
}

test cardano_value_bearing_accumulate_fails_closed() {
  let before = VdsoObjectDatum { ..sample_before(), value_class: 1 }
  let after = VdsoObjectDatum { ..before, version: 8, data_commitment: #"08" }
  !valid_cardano_transition(
    before,
    after,
    VdsoTransition {
      mode: Accumulate,
      expected_version: 7,
      writer: #"03",
      canonical_transition: #"09",
    },
  )
}

test shadow_read_commitment_accepts_commitment_only_read() {
  let previous_root =
    #"1111111111111111111111111111111111111111111111111111111111111111"
  let input_commitment =
    #"2222222222222222222222222222222222222222222222222222222222222222"
  let canonical_transition =
    #"56414d533a5644534f3a534841444f573a524541443a7631000000000000000711111111111111111111111111111111111111111111111111111111111111112222222222222222222222222222222222222222222222222222222222222222"
  let expected_commitment = canonical_commitment(canonical_transition)

  shadow_read_commitment(
    0,
    7,
    previous_root,
    previous_root,
    input_commitment,
    canonical_transition,
    expected_commitment,
  ) == expected_commitment
}

test shadow_read_commitment_rejects_mutation_and_root_mismatch() {
  let previous_root =
    #"1111111111111111111111111111111111111111111111111111111111111111"
  let wrong_root =
    #"1212121212121212121212121212121212121212121212121212121212121212"
  let input_commitment =
    #"2222222222222222222222222222222222222222222222222222222222222222"
  let canonical_transition =
    #"56414d533a5644534f3a534841444f573a524541443a7631000000000000000711111111111111111111111111111111111111111111111111111111111111112222222222222222222222222222222222222222222222222222222222222222"
  let expected_commitment = canonical_commitment(canonical_transition)

  and {
    shadow_read_commitment(
      1,
      7,
      previous_root,
      previous_root,
      input_commitment,
      canonical_transition,
      expected_commitment,
    ) == zero_hash,
    shadow_read_commitment(
      0,
      7,
      previous_root,
      wrong_root,
      input_commitment,
      canonical_transition,
      expected_commitment,
    ) == zero_hash,
  }
}

test keccak_empty_matches_shared_vector() {
  canonical_commitment(#"") == #"c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
}

test polygon_host_wire_is_zero() {
  host_authority_wire(Polygon) == 0
}

test cardano_host_wire_is_one() {
  host_authority_wire(Cardano) == 1
}

test shared_unsigned_intent_matches_cross_language_intent_id() {
  canonical_intent_id(shared_unsigned_intent_cbor) == shared_intent_id
}

test shared_settlement_matches_cross_language_commitment() {
  canonical_commitment(shared_settlement_cbor) == shared_settlement_commitment
}

test cross_host_settlement_accepts_separated_proof_and_payload() {
  valid_cross_host_settlement(
    settlement_fixture(
      2,
      Polygon,
      Cardano,
      Cardano,
      sample_source_reference,
      sample_source_transaction,
      123456,
      sample_bridge_proof_hash,
      sample_payload_hash,
    ),
  )
}

test cross_host_settlement_rejects_wrong_host_version_or_commitments() {
  let same_host =
    settlement_fixture(
      2,
      Cardano,
      Cardano,
      Cardano,
      sample_source_reference,
      sample_source_transaction,
      1,
      sample_bridge_proof_hash,
      sample_payload_hash,
    )
  let destination_mismatch =
    settlement_fixture(
      2,
      Cardano,
      Polygon,
      Cardano,
      sample_source_reference,
      sample_source_transaction,
      1,
      sample_bridge_proof_hash,
      sample_payload_hash,
    )
  let empty_proof =
    settlement_fixture(
      2,
      Polygon,
      Cardano,
      Cardano,
      sample_source_reference,
      sample_source_transaction,
      1,
      #"",
      sample_payload_hash,
    )
  let empty_payload =
    settlement_fixture(
      2,
      Polygon,
      Cardano,
      Cardano,
      sample_source_reference,
      sample_source_transaction,
      1,
      sample_bridge_proof_hash,
      #"",
    )
  let aliased =
    settlement_fixture(
      2,
      Polygon,
      Cardano,
      Cardano,
      sample_source_reference,
      sample_source_transaction,
      1,
      sample_bridge_proof_hash,
      sample_bridge_proof_hash,
    )
  let legacy_schema =
    settlement_fixture(
      1,
      Polygon,
      Cardano,
      Cardano,
      sample_source_reference,
      sample_source_transaction,
      1,
      sample_bridge_proof_hash,
      sample_payload_hash,
    )
  let zero_height =
    settlement_fixture(
      2,
      Polygon,
      Cardano,
      Cardano,
      sample_source_reference,
      sample_source_transaction,
      0,
      sample_bridge_proof_hash,
      sample_payload_hash,
    )
  let height_overflow =
    settlement_fixture(
      2,
      Polygon,
      Cardano,
      Cardano,
      sample_source_reference,
      sample_source_transaction,
      max_uint64 + 1,
      sample_bridge_proof_hash,
      sample_payload_hash,
    )
  let epoch_overflow =
    VdsoSettlementMetadata {
      ..settlement_fixture(
        2,
        Polygon,
        Cardano,
        Cardano,
        sample_source_reference,
        sample_source_transaction,
        1,
        sample_bridge_proof_hash,
        sample_payload_hash,
      ),
      binding: VdsoDomainAuthorityBinding {
        state_domain: sample_state_domain,
        host_authority: Cardano,
        authority_epoch: max_uint64 + 1,
      },
    }

  and {
    !valid_cross_host_settlement(same_host),
    !valid_cross_host_settlement(destination_mismatch),
    !valid_cross_host_settlement(empty_proof),
    !valid_cross_host_settlement(empty_payload),
    !valid_cross_host_settlement(aliased),
    !valid_cross_host_settlement(legacy_schema),
    !valid_cross_host_settlement(zero_height),
    !valid_cross_host_settlement(height_overflow),
    !valid_cross_host_settlement(epoch_overflow),
  }
}

test same_host_settlement_requires_equal_authority_and_zero_tuple() {
  let local =
    settlement_fixture(
      2,
      Cardano,
      Cardano,
      Cardano,
      zero_hash,
      zero_hash,
      0,
      zero_hash,
      zero_hash,
    )
  let partial =
    settlement_fixture(
      2,
      Cardano,
      Cardano,
      Cardano,
      zero_hash,
      sample_source_transaction,
      0,
      zero_hash,
      zero_hash,
    )

  valid_same_host_settlement(local) && !valid_same_host_settlement(partial)
}
