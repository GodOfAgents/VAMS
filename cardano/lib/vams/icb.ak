//// VAMS ICB bridge conformance helpers.
////
//// No production verifier is available in the initial Cardano Pre-Prod
//// profile. Proof-shaped bytes must therefore fail closed. These functions
//// remain public only to keep the pre-deployment wire boundary explicit.

use aiken/fuzz
use aiken/primitive/bytearray

pub type BridgeMessage {
  source_chain: ByteArray,
  dest_chain: ByteArray,
  payload_hash: ByteArray,
  sequence: Int,
  timestamp: Int,
}

pub fn verify_bridge_proof(
  proof: ByteArray,
  expected_payload_hash: ByteArray,
) -> Bool {
  bytearray.length(proof) >= 0 && bytearray.length(expected_payload_hash) >= 0 && False
}

pub fn verify_mithril_proof(proof: ByteArray) -> Bool {
  bytearray.length(proof) >= 0 && False
}

pub fn is_from_polygon(source: ByteArray) -> Bool {
  source == "polygon"
}

pub fn is_to_cardano(dest: ByteArray) -> Bool {
  dest == "cardano"
}

pub fn is_valid_nonce(new_nonce: Int, last_nonce: Int) -> Bool {
  new_nonce > last_nonce
}

test bridge_proof_always_fails_closed() {
  let proof =
    #"00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
  !verify_bridge_proof(proof, #"abcdef")
}

test mithril_proof_always_fails_closed() {
  !verify_mithril_proof(
    #"0000000000000000000000000000000000000000000000000000000000000000",
  )
}

test bridge_hosts_remain_explicit() {
  is_from_polygon("polygon") && is_to_cardano("cardano") && !is_from_polygon(
    "ethereum",
  )
}

test nonce_replay_is_rejected() {
  !is_valid_nonce(4, 4) && !is_valid_nonce(3, 4) && is_valid_nonce(5, 4)
}

test prop_nonce_replay_always_rejected(nonce via fuzz.int()) {
  !is_valid_nonce(nonce, nonce)
}

test prop_nonce_strictly_increases(
  (last_nonce, raw_delta) via fuzz.both(fuzz.int(), fuzz.int_at_least(1)),
) {
  let delta = raw_delta % 1_000_000 + 1
  is_valid_nonce(last_nonce + delta, last_nonce)
}
