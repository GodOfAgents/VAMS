use aiken/collection/list
use aiken/crypto.{sha2_256}
use aiken/primitive/bytearray

// Fixed 21 ABI words. New digest domain; existing VIR/Cardano domains unchanged.
pub fn encode_action_context_v1(words: List<ByteArray>) -> Option<ByteArray> {
  when words is {
    [actor, provider, runtime, model, host, workflow, intent, action, input_hash,
      policy, target, nonce, unit, scheme, epoch, version, capabilities, _budget,
      issued, expires, chain] -> {
      let zero = #"0000000000000000000000000000000000000000000000000000000000000000"
      let scheme_n = bytearray.to_int_big_endian(scheme)
      let hashes = [actor, provider, runtime, host, workflow, intent, action,
        input_hash, policy, target, nonce, unit]
      if list.all(words, fn(word) { bytearray.length(word) == 32 }) &&
        list.all(hashes, fn(word) { word != zero }) && bytearray.length(model) == 32 &&
        (scheme_n == 1 || scheme_n == 2) &&
        bytearray.to_int_big_endian(actor) < if scheme_n == 1 { 1461501637330902918203684832716283019655932542976 } else { 26959946667150639794667015087019630673637144422540572481103610249216 } &&
        bytearray.to_int_big_endian(epoch) > 0 && bytearray.to_int_big_endian(version) > 0 &&
        bytearray.to_int_big_endian(capabilities) > 0 && bytearray.to_int_big_endian(chain) > 0 &&
        bytearray.to_int_big_endian(expires) > bytearray.to_int_big_endian(issued) {
        Some(list.foldl(words, #"56414d533a414354494f4e2d434f4e544558543a763100",
          fn(word, accumulated) { bytearray.concat(accumulated, word) }))
      } else { None }
    }
    _ -> None
  }
}

pub fn action_context_digest_v1(words: List<ByteArray>) -> Option<ByteArray> {
  when encode_action_context_v1(words) is {
    Some(encoded) -> Some(sha2_256(encoded))
    None -> None
  }
}

// Exact inverse framing; no Cardano authority, policy or proof is inferred.
pub fn decode_action_context_v1(encoded: ByteArray) -> Option<List<ByteArray>> {
  if bytearray.length(encoded) != 695 {
    None
  } else if bytearray.slice(encoded, 0, 22) != #"56414d533a414354494f4e2d434f4e544558543a763100" {
    None
  } else {
    // Pinned slice endpoints and list.range are inclusive. Bound all21words.
    let words = list.map(list.range(0, 20), fn(index) {
      bytearray.slice(encoded, 23 + 32 * index, 54 + 32 * index)
    })
    when encode_action_context_v1(words) is {
      Some(_) -> Some(words)
      None -> None
    }
  }
}
