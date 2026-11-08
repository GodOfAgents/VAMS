//// F05 testnet authority singleton types and canonical V3 encodings.
////
//// This module is deliberately separate from the governance AuthorityDatumV1.
//// The initial singleton is bootstrapped only; authority transitions are not
//// enabled by F05.2a.

use aiken/collection/list
use aiken/crypto.{sha2_256, verify_ed25519_signature}
use aiken/primitive/bytearray
use cardano/transaction.{OutputReference}

pub const authority_schema_version: Int = 3
pub const authority_threshold: Int = 3
/// Reserved for the R4 four-of-five emergency authorization rule. No emergency
/// action is enabled by this bootstrap-only slice.
pub const authority_emergency_threshold: Int = 4

pub const authority_asset_name: ByteArray = #"56414d532d4630352d415554482d5633"

const bootstrap_domain: ByteArray = #"56414d532d4630352d415554482d424f4f5453545241502d563300"
const state_domain: ByteArray = #"56414d532d4630352d415554482d53544154452d563300"
const pending_domain: ByteArray = #"56414d532d4630352d415554482d50454e44494e472d563300"
const genesis_pop_domain: ByteArray = #"56414d532d4630352d415554484f524954592d47454e455349532d504f502d563100"
const authority_key_bytes: Int = 32
const authority_keys_bytes: Int = 160
const authority_hash_bytes: Int = 32
const authority_signature_bytes: Int = 64

pub type AuthorityStatusV3 {
  AuthorityActive
  AuthorityPaused
}

pub type PendingKindV3 {
  PendingNone
  PendingRotate
  PendingUnpause
}

/// The pending data is kept in the singleton datum and canonically hashed into
/// AuthorityStateV3. NONE uses the R4 all-zero encoding and zero pending hash.
pub type AuthorityPendingTransitionV3 {
  kind: PendingKindV3,
  from_epoch: Int,
  to_epoch: Int,
  authorized_at_ms: Int,
  activation_at_ms: Int,
  next_key_count: Int,
  ordered_next_keys: ByteArray,
}

/// Field values correspond to CONTRACT.json authority_preimages.state_fields.
pub type AuthorityStateV3 {
  schema_version: Int,
  bootstrap_tx_hash: ByteArray,
  bootstrap_output_index: Int,
  epoch: Int,
  ordered_keys: List<ByteArray>,
  threshold: Int,
  status: AuthorityStatusV3,
  pending: AuthorityPendingTransitionV3,
}

pub type AuthorityBootstrapRedeemer {
  BootstrapAuthority { proofs: List<ByteArray> }
}

pub type AuthoritySpendRedeemer {
  DisabledAuthorityTransition
}

pub fn same_output_reference(left: OutputReference, right: OutputReference) -> Bool {
  left.transaction_id == right.transaction_id && left.output_index == right.output_index
}

pub fn valid_initial_authority(
  state: AuthorityStateV3,
  genesis_ref: OutputReference,
  initial_keys: List<ByteArray>,
) -> Bool {
  True
    && state.bootstrap_tx_hash == genesis_ref.transaction_id
    && state.bootstrap_output_index == genesis_ref.output_index
    && state.bootstrap_output_index >= 0
    && state.bootstrap_output_index <= 65_535
    && state.epoch == 0
    && state.threshold == authority_threshold
    && state.status == AuthorityActive
    && valid_ordered_keys(initial_keys)
    && state.ordered_keys == initial_keys
    && canonical_none(state.pending)
    && pending_hash(state.pending) == zero_bytes(authority_hash_bytes)
}

/// Canonical 279-byte bootstrap proof-of-possession message from F05.2a R2.
/// The network values are the fixed F05.1-R4 Cardano Pre-Prod domain tuple.
pub fn authority_genesis_pop_preimage(
  genesis_ref: OutputReference,
  state_validator_hash: ByteArray,
  keys: List<ByteArray>,
) -> ByteArray {
  bytearray.concat(
    genesis_pop_domain,
    bytearray.concat(
        bytearray.from_int_big_endian(2, 1),
        bytearray.concat(
          bytearray.from_int_big_endian(0, 8),
          bytearray.concat(
            bytearray.from_int_big_endian(1, 4),
            bytearray.concat(
              bytearray.from_int_big_endian(0, 1),
              bytearray.concat(
                genesis_ref.transaction_id,
                bytearray.concat(
                  bytearray.from_int_big_endian(genesis_ref.output_index, 2),
                  bytearray.concat(
                    state_validator_hash,
                    bytearray.concat(
                      bytearray.from_int_big_endian(list.length(keys), 1),
                      bytearray.concat(
                        encoded_ordered_keys(keys),
                        bytearray.from_int_big_endian(0, 8),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
    ),
  )
}

/// Require exactly one proof per ordered key and verify each positional pair.
pub fn valid_bootstrap_proofs(
  keys: List<ByteArray>,
  proofs: List<ByteArray>,
  message: ByteArray,
) -> Bool {
  when keys is {
    [key_1, key_2, key_3, key_4, key_5] ->
      when proofs is {
        [proof_1, proof_2, proof_3, proof_4, proof_5] ->
          bytearray.length(proof_1) == authority_signature_bytes
            && bytearray.length(proof_2) == authority_signature_bytes
            && bytearray.length(proof_3) == authority_signature_bytes
            && bytearray.length(proof_4) == authority_signature_bytes
            && bytearray.length(proof_5) == authority_signature_bytes
            && verify_ed25519_signature(key_1, message, proof_1)
            && verify_ed25519_signature(key_2, message, proof_2)
            && verify_ed25519_signature(key_3, message, proof_3)
            && verify_ed25519_signature(key_4, message, proof_4)
            && verify_ed25519_signature(key_5, message, proof_5)
        _ -> False
      }
    _ -> False
  }
}

/// Exact R4 fixed-width authority bootstrap preimage (266 bytes).
pub fn authority_bootstrap_preimage(state: AuthorityStateV3) -> ByteArray {
  bytearray.concat(
    bootstrap_domain,
    bytearray.concat(
      bytearray.from_int_big_endian(state.schema_version, 2),
      bytearray.concat(
        state.bootstrap_tx_hash,
        bytearray.concat(
          bytearray.from_int_big_endian(state.bootstrap_output_index, 2),
          bytearray.concat(
            bytearray.from_int_big_endian(state.epoch, 8),
            bytearray.concat(
              bytearray.from_int_big_endian(list.length(state.ordered_keys), 1),
              bytearray.concat(
                encoded_ordered_keys(state.ordered_keys),
                bytearray.concat(
                  bytearray.from_int_big_endian(state.threshold, 1),
                  bytearray.concat(
                    bytearray.from_int_big_endian(status_code(state.status), 1),
                    pending_hash(state.pending),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  )
}

/// Exact R4 fixed-width authority state preimage (262 bytes).
pub fn authority_state_preimage(state: AuthorityStateV3) -> ByteArray {
  bytearray.concat(
    state_domain,
    bytearray.concat(
      bytearray.from_int_big_endian(state.schema_version, 2),
      bytearray.concat(
        state.bootstrap_tx_hash,
        bytearray.concat(
          bytearray.from_int_big_endian(state.bootstrap_output_index, 2),
          bytearray.concat(
            bytearray.from_int_big_endian(state.epoch, 8),
            bytearray.concat(
              bytearray.from_int_big_endian(list.length(state.ordered_keys), 1),
              bytearray.concat(
                encoded_ordered_keys(state.ordered_keys),
                bytearray.concat(
                  bytearray.from_int_big_endian(state.threshold, 1),
                  bytearray.concat(
                    bytearray.from_int_big_endian(status_code(state.status), 1),
                    pending_hash(state.pending),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  )
}

pub fn authority_state_hash(state: AuthorityStateV3) -> ByteArray {
  sha2_256(authority_state_preimage(state))
}

pub fn pending_hash(pending: AuthorityPendingTransitionV3) -> ByteArray {
  when pending.kind is {
    PendingNone -> zero_bytes(authority_hash_bytes)
    _ -> sha2_256(bytearray.concat(pending_domain, encoded_pending_fields(pending)))
  }
}

fn canonical_none(pending: AuthorityPendingTransitionV3) -> Bool {
  pending.kind == PendingNone
    && pending.from_epoch == 0
    && pending.to_epoch == 0
    && pending.authorized_at_ms == 0
    && pending.activation_at_ms == 0
    && pending.next_key_count == 0
    && pending.ordered_next_keys == zero_bytes(authority_keys_bytes)
}

fn encoded_pending_fields(pending: AuthorityPendingTransitionV3) -> ByteArray {
  bytearray.concat(
    bytearray.from_int_big_endian(pending_kind_code(pending.kind), 1),
    bytearray.concat(
      bytearray.from_int_big_endian(pending.from_epoch, 8),
      bytearray.concat(
        bytearray.from_int_big_endian(pending.to_epoch, 8),
        bytearray.concat(
          bytearray.from_int_big_endian(pending.authorized_at_ms, 8),
          bytearray.concat(
            bytearray.from_int_big_endian(pending.activation_at_ms, 8),
            bytearray.concat(
              bytearray.from_int_big_endian(pending.next_key_count, 1),
              pending.ordered_next_keys,
            ),
          ),
        ),
      ),
    ),
  )
}

fn valid_ordered_keys(keys: List<ByteArray>) -> Bool {
  when keys is {
    [first, second, third, fourth, fifth] ->
      bytearray.length(first) == authority_key_bytes
        && bytearray.length(second) == authority_key_bytes
        && bytearray.length(third) == authority_key_bytes
        && bytearray.length(fourth) == authority_key_bytes
        && bytearray.length(fifth) == authority_key_bytes
        && bytearray.to_int_big_endian(first) < bytearray.to_int_big_endian(second)
        && bytearray.to_int_big_endian(second) < bytearray.to_int_big_endian(third)
        && bytearray.to_int_big_endian(third) < bytearray.to_int_big_endian(fourth)
        && bytearray.to_int_big_endian(fourth) < bytearray.to_int_big_endian(fifth)
    _ -> False
  }
}

fn encoded_ordered_keys(keys: List<ByteArray>) -> ByteArray {
  when keys is {
    [first, second, third, fourth, fifth] ->
      bytearray.concat(
        first,
        bytearray.concat(
          second,
          bytearray.concat(third, bytearray.concat(fourth, fifth)),
        ),
      )
    _ -> #""
  }
}

fn status_code(status: AuthorityStatusV3) -> Int {
  when status is {
    AuthorityActive -> 1
    AuthorityPaused -> 2
  }
}

fn pending_kind_code(kind: PendingKindV3) -> Int {
  when kind is {
    PendingNone -> 0
    PendingRotate -> 1
    PendingUnpause -> 2
  }
}

fn zero_bytes(length: Int) -> ByteArray {
  bytearray.from_int_big_endian(0, length)
}
