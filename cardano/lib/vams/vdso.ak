//// VAMS VDSO Cardano Conformance Boundary
////
//// Cardano remains the authoritative host for its assigned governance,
//// identity, and insurance state domains.  This v1 canary module implements
//// commitment and non-economic transition conformance only.  RESERVE and
//// value-bearing transitions fail closed until destination fencing and
//// authenticated non-execution proofs are available.

use aiken/crypto.{keccak_256}
use aiken/primitive/bytearray

const intent_v1_domain: ByteArray = #"56414d533a494e54454e543a7631"

/// Exact `unsigned_intent_cbor` from `vams-vm/vectors/vir-core-v1.json`.
const shared_unsigned_intent_cbor: ByteArray = #"90015820313131313131313131313131313131313131313131313131313131313131313183582030303030303030303030303030303030303030303030303030303030303030300104182a1903e75820665438cdbc643b5d3947e47fd56d14a792daa805dee405ffc423c445095392a15820606060606060606060606060606060606060606060606060606060606060606082845820202020202020202020202020202020202020202020202020202020202020202000058084582021212121212121212121212121212121212121212121212121212121212121210307805820902188534cc8e8be436828d1329c194c793d2f591921e6f0d42c48379bfb14fc5820507c1c9e5414952f2017497a5a6da6cf639c820712d2266d2978ae5a200a3dcf582061616161616161616161616161616161616161616161616161616161616161615820626262626262626262626262626262626262626262626262626262626262626202021864191388"

const shared_intent_id: ByteArray = #"34ff92df19e5c307274e04c67c86cc1df590f48c91013ccdf8fb488125b7824c"

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

/// Consensus wire mapping shared by Rust, Solidity, Python, and Aiken.
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
/// Keeping bridge_proof and payload_hash as distinct fields preserves INV-10.
pub type VdsoSettlementMetadata {
  source_host: VdsoHostAuthority,
  destination_host: VdsoHostAuthority,
  bridge_proof: ByteArray,
  payload_hash: ByteArray,
  finalized_height: Int,
}

/// Hash already-canonical CBOR bytes using the VDSO v1 Keccak primitive.
/// Canonical CBOR construction remains off-chain and is checked against the
/// shared Rust/Python/Solidity/Aiken vector corpus.
pub fn canonical_commitment(canonical_cbor: ByteArray) -> ByteArray {
  keccak_256(canonical_cbor)
}

/// Hash a canonical unsigned intent using the exact raw ASCII domain prefix.
pub fn canonical_intent_id(canonical_unsigned_intent_cbor: ByteArray) -> ByteArray {
  keccak_256(
    bytearray.concat(intent_v1_domain, canonical_unsigned_intent_cbor),
  )
}

/// Cross-host settlement metadata is valid only when proof and payload remain
/// separate, non-empty values and authority moves between distinct hosts.
pub fn valid_cross_host_settlement(metadata: VdsoSettlementMetadata) -> Bool {
  metadata.source_host != metadata.destination_host &&
    !bytearray.is_empty(metadata.bridge_proof) &&
    !bytearray.is_empty(metadata.payload_hash) &&
    metadata.bridge_proof != metadata.payload_hash &&
    metadata.finalized_height >= 0
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
    before.schema_version == 1 &&
      after.schema_version == before.schema_version &&
      before.object_id == after.object_id &&
      before.object_type == after.object_type &&
      before.authority == after.authority &&
      before.host_authority == Cardano &&
      after.host_authority == Cardano &&
      before.state_domain == after.state_domain &&
      before.policy_hash == after.policy_hash &&
      before.value_class == 0 &&
      after.value_class == 0 &&
      transition.writer == before.authority &&
      transition.expected_version == before.version &&
      transition.canonical_transition != #""

  if !common_fields_unchanged {
    False
  } else {
    when transition.mode is {
      Read ->
        after.version == before.version &&
          after.data_commitment == before.data_commitment
      Accumulate ->
        after.version == before.version + 1 &&
          after.data_commitment != before.data_commitment
      Consume -> False
      Reserve -> False
    }
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

test keccak_empty_matches_shared_vector() {
  canonical_commitment(#"") ==
    #"c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
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

test cross_host_settlement_accepts_separated_proof_and_payload() {
  valid_cross_host_settlement(
    VdsoSettlementMetadata {
      source_host: Polygon,
      destination_host: Cardano,
      bridge_proof: #"01",
      payload_hash: #"02",
      finalized_height: 1,
    },
  )
}

test cross_host_settlement_rejects_same_host_empty_or_aliased_fields() {
  let same_host =
    VdsoSettlementMetadata {
      source_host: Cardano,
      destination_host: Cardano,
      bridge_proof: #"01",
      payload_hash: #"02",
      finalized_height: 1,
    }
  let empty_proof =
    VdsoSettlementMetadata {
      source_host: Polygon,
      destination_host: Cardano,
      bridge_proof: #"",
      payload_hash: #"02",
      finalized_height: 1,
    }
  let empty_payload =
    VdsoSettlementMetadata {
      source_host: Polygon,
      destination_host: Cardano,
      bridge_proof: #"01",
      payload_hash: #"",
      finalized_height: 1,
    }
  let aliased =
    VdsoSettlementMetadata {
      source_host: Polygon,
      destination_host: Cardano,
      bridge_proof: #"01",
      payload_hash: #"01",
      finalized_height: 1,
    }

  and {
    !valid_cross_host_settlement(same_host),
    !valid_cross_host_settlement(empty_proof),
    !valid_cross_host_settlement(empty_payload),
    !valid_cross_host_settlement(aliased),
  }
}
