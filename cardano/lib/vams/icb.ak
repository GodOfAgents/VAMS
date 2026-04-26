//// VAMS ICB Bridge Verification
////
//// Helpers for verifying cross-chain messages between
//// Polygon (Hands) and Cardano (Brain) via the ICB relay.

use aiken/primitive/bytearray

// ═══════════════════ Bridge Verification ═══════════════════

/// ICB bridge message structure
pub type BridgeMessage {
  /// Source chain identifier
  source_chain: ByteArray,
  /// Destination chain identifier
  dest_chain: ByteArray,
  /// Payload hash
  payload_hash: ByteArray,
  /// Sequence number for ordering
  sequence: Int,
  /// Relay timestamp
  timestamp: Int,
}

/// Verify that a bridge proof is well-formed
/// In production, this would verify a Mithril certificate or
/// Rosen Bridge proof. 
/// TODO [Testnet]: For testnet, we verify structure only. Replace with full verification before mainnet.
pub fn verify_bridge_proof(
  proof: ByteArray,
  expected_payload_hash: ByteArray,
) -> Bool {
  // Proof must be non-empty
  let proof_len = bytearray.length(proof)
  // Minimum proof length: 64 bytes (hash + signature)
  // For testnet: verify non-empty and payload hash is non-empty
  proof_len >= 64 && bytearray.length(expected_payload_hash) > 0
}

/// Verify that a Mithril finality proof is valid
/// Mithril provides lightweight proofs of Cardano chain state
/// TODO [Testnet]: Production will verify Mithril certificate chain
/// Testnet only verifies proof is non-empty and well-structured
pub fn verify_mithril_proof(proof: ByteArray) -> Bool {
  bytearray.length(proof) >= 32
}

/// Check that the source chain matches expected origin
pub fn is_from_polygon(source: ByteArray) -> Bool {
  source == "polygon"
}

/// Check that destination is Cardano
pub fn is_to_cardano(dest: ByteArray) -> Bool {
  dest == "cardano"
}

// ═══════════════════ Nonce Tracking ═══════════════════

/// Verify nonce is strictly greater than the last processed nonce
/// Prevents replay attacks on cross-chain messages
pub fn is_valid_nonce(new_nonce: Int, last_nonce: Int) -> Bool {
  new_nonce > last_nonce
}

// ═══════════════════ Tests ═══════════════════

test verify_bridge_proof_short() {
  // 32 bytes of proof data — too short (< 64)
  let proof =
    #"0000000000000000000000000000000000000000000000000000000000000000"
  let payload = #"abcdef"
  verify_bridge_proof(proof, payload) == False
}

test verify_bridge_proof_long() {
  // 64+ bytes of proof data
  let proof =
    #"00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
  let payload = #"abcdef"
  verify_bridge_proof(proof, payload) == True
}

test verify_mithril_proof_valid() {
  // 32 bytes of proof
  let proof =
    #"0000000000000000000000000000000000000000000000000000000000000000"
  verify_mithril_proof(proof) == True
}

test is_from_polygon_true() {
  is_from_polygon("polygon") == True
}

test is_from_polygon_false() {
  is_from_polygon("ethereum") == False
}

test is_valid_nonce_increasing() {
  is_valid_nonce(5, 4) == True
}

test is_valid_nonce_replay() {
  is_valid_nonce(4, 4) == False
}

test is_valid_nonce_reorder() {
  is_valid_nonce(3, 4) == False
}
