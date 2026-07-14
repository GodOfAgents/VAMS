//! Pure commitment-only evaluator used by the private VDSO shadow worker.
//!
//! This binary deliberately exposes one operation: a non-mutating READ.  It
//! accepts only fixed-width commitments and a canonical transition preimage,
//! validates the root/sequence bindings, and prints the computed Keccak-256
//! commitment.  It has no network or storage capability.

use std::env;

use vir_codec::keccak256;
use vir_types::AccessMode;

const SHADOW_READ_DOMAIN: &[u8] = b"VAMS:VDSO:SHADOW:READ:v1";
const HASH_LENGTH: usize = 32;
const SEQUENCE_LENGTH: usize = 8;
const CANONICAL_LENGTH: usize =
    SHADOW_READ_DOMAIN.len() + SEQUENCE_LENGTH + HASH_LENGTH + HASH_LENGTH;

fn decode_hex<const N: usize>(value: &str) -> Result<[u8; N], &'static str> {
    if value.len() != N * 2 || !value.is_ascii() {
        return Err("invalid fixed-width hex input");
    }
    let mut output = [0_u8; N];
    for (index, chunk) in value.as_bytes().chunks_exact(2).enumerate() {
        let high = decode_nibble(chunk[0])?;
        let low = decode_nibble(chunk[1])?;
        output[index] = (high << 4) | low;
    }
    Ok(output)
}

fn decode_vec(value: &str) -> Result<Vec<u8>, &'static str> {
    if !value.len().is_multiple_of(2) || !value.is_ascii() {
        return Err("invalid hex input");
    }
    let mut output = Vec::with_capacity(value.len() / 2);
    for chunk in value.as_bytes().chunks_exact(2) {
        output.push((decode_nibble(chunk[0])? << 4) | decode_nibble(chunk[1])?);
    }
    Ok(output)
}

const fn decode_nibble(value: u8) -> Result<u8, &'static str> {
    match value {
        b'0'..=b'9' => Ok(value - b'0'),
        b'a'..=b'f' => Ok(value - b'a' + 10),
        b'A'..=b'F' => Ok(value - b'A' + 10),
        _ => Err("invalid hex input"),
    }
}

fn evaluate(arguments: &[String]) -> Result<[u8; HASH_LENGTH], &'static str> {
    if arguments.len() != 7 {
        return Err("expected seven evaluator arguments");
    }

    let action = arguments[0]
        .parse::<u8>()
        .map_err(|_| "invalid access mode")?;
    let mode = AccessMode::try_from(action).map_err(|_| "unsupported access mode")?;
    if mode != AccessMode::Read || mode.is_mutating() {
        return Err("shadow evaluator permits READ only");
    }

    let sequence = arguments[1]
        .parse::<u64>()
        .map_err(|_| "invalid sequence")?;
    let expected_previous_root = decode_hex::<HASH_LENGTH>(&arguments[2])?;
    let actual_previous_root = decode_hex::<HASH_LENGTH>(&arguments[3])?;
    let input_commitment = decode_hex::<HASH_LENGTH>(&arguments[4])?;
    let canonical_transition = decode_vec(&arguments[5])?;
    let expected_commitment = decode_hex::<HASH_LENGTH>(&arguments[6])?;

    if expected_previous_root == [0_u8; HASH_LENGTH]
        || expected_previous_root != actual_previous_root
        || input_commitment == [0_u8; HASH_LENGTH]
        || expected_commitment == [0_u8; HASH_LENGTH]
        || canonical_transition.len() != CANONICAL_LENGTH
    {
        return Err("invalid commitment-only transition");
    }

    let domain_end = SHADOW_READ_DOMAIN.len();
    let sequence_end = domain_end + SEQUENCE_LENGTH;
    let root_end = sequence_end + HASH_LENGTH;
    if &canonical_transition[..domain_end] != SHADOW_READ_DOMAIN
        || canonical_transition[domain_end..sequence_end] != sequence.to_be_bytes()
        || canonical_transition[sequence_end..root_end] != actual_previous_root
        || canonical_transition[root_end..] != input_commitment
    {
        return Err("canonical transition binding mismatch");
    }

    let computed = *keccak256(&canonical_transition).as_bytes();
    if computed != expected_commitment {
        return Err("transition commitment mismatch");
    }
    Ok(computed)
}

fn encode_hex(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        output.push(char::from(HEX[usize::from(byte >> 4)]));
        output.push(char::from(HEX[usize::from(byte & 0x0f)]));
    }
    output
}

fn main() {
    let arguments = env::args().skip(1).collect::<Vec<_>>();
    match evaluate(&arguments) {
        Ok(commitment) => println!("{}", encode_hex(&commitment)),
        Err(message) => {
            eprintln!("shadow evaluation rejected: {message}");
            std::process::exit(2);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_arguments() -> Vec<String> {
        let previous_root = [0x11_u8; HASH_LENGTH];
        let input_commitment = [0x22_u8; HASH_LENGTH];
        let sequence = 7_u64;
        let mut canonical = Vec::with_capacity(CANONICAL_LENGTH);
        canonical.extend_from_slice(SHADOW_READ_DOMAIN);
        canonical.extend_from_slice(&sequence.to_be_bytes());
        canonical.extend_from_slice(&previous_root);
        canonical.extend_from_slice(&input_commitment);
        let output = keccak256(&canonical);
        vec![
            "0".to_owned(),
            sequence.to_string(),
            encode_hex(&previous_root),
            encode_hex(&previous_root),
            encode_hex(&input_commitment),
            encode_hex(&canonical),
            encode_hex(output.as_bytes()),
        ]
    }

    #[test]
    fn accepts_commitment_only_read() {
        let arguments = valid_arguments();
        let result = evaluate(&arguments);
        assert!(result.is_ok());
    }

    #[test]
    fn rejects_mutation_root_and_canonical_mismatch() {
        let mut mutation = valid_arguments();
        mutation[0] = "3".to_owned();
        assert!(evaluate(&mutation).is_err());

        let mut wrong_root = valid_arguments();
        wrong_root[3] = encode_hex(&[0x12_u8; HASH_LENGTH]);
        assert!(evaluate(&wrong_root).is_err());

        let mut wrong_canonical = valid_arguments();
        wrong_canonical[5] = encode_hex(&[0_u8; CANONICAL_LENGTH]);
        assert!(evaluate(&wrong_canonical).is_err());
    }
}
