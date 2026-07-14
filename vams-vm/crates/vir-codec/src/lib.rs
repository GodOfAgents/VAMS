//! Restricted deterministic CBOR and VIR-Core domain-separated hashing.
//!
//! The codec accepts only definite positional arrays, unsigned integers, and
//! bounded byte strings. It rejects maps, tags, floats, text, indefinite
//! lengths, non-minimal integers, unknown versions, and trailing bytes.

use std::fmt;
use std::num::NonZeroU64;

use vir_types::{
    AccessMode, DomainAuthorityBinding, ExecutionPolicy, ExecutionTier, FailureCode, Hash32,
    HostAuthority, IntentCommitments, MAX_OBJECT_ACCESSES, ObjectAccess, ReceiptCommitments,
    SCHEMA_VERSION, SemanticReceipt, SettlementMetadata, SignatureSuite, StateObjectHeader,
    TransitionOutcome, UnsignedIntent,
};

const DOMAIN_INTENT: &[u8] = b"VAMS:INTENT:v1";
const DOMAIN_PROGRAM: &[u8] = b"VAMS:PROGRAM:v1";
const DOMAIN_WORKFLOW: &[u8] = b"VAMS:WORKFLOW:v1";
const DOMAIN_INPUT: &[u8] = b"VAMS:INPUT:v1";
const DOMAIN_OUTPUT: &[u8] = b"VAMS:OUTPUT:v1";
const DOMAIN_STATE: &[u8] = b"VAMS:STATE:v1";
const DOMAIN_RECEIPT: &[u8] = b"VAMS:RECEIPT:v1";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct DecodeError {
    code: FailureCode,
    offset: usize,
}

impl DecodeError {
    #[must_use]
    pub const fn new(code: FailureCode, offset: usize) -> Self {
        Self { code, offset }
    }

    #[must_use]
    pub const fn code(self) -> FailureCode {
        self.code
    }

    #[must_use]
    pub const fn offset(self) -> usize {
        self.offset
    }
}

impl fmt::Display for DecodeError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            formatter,
            "VIR codec error {:?} at byte {}",
            self.code, self.offset
        )
    }
}

impl std::error::Error for DecodeError {}

#[derive(Default)]
struct Encoder {
    bytes: Vec<u8>,
}

impl Encoder {
    fn into_bytes(self) -> Vec<u8> {
        self.bytes
    }

    fn uint(&mut self, value: u64) {
        self.major_value(0, value);
    }

    fn bytes(&mut self, value: &[u8]) {
        self.major_value(2, value.len() as u64);
        self.bytes.extend_from_slice(value);
    }

    fn array(&mut self, length: usize) {
        self.major_value(4, length as u64);
    }

    fn major_value(&mut self, major: u8, value: u64) {
        let prefix = major << 5;
        if value <= 23 {
            self.bytes.push(prefix | value as u8);
        } else if value <= u8::MAX as u64 {
            self.bytes.push(prefix | 24);
            self.bytes.push(value as u8);
        } else if value <= u16::MAX as u64 {
            self.bytes.push(prefix | 25);
            self.bytes.extend_from_slice(&(value as u16).to_be_bytes());
        } else if value <= u32::MAX as u64 {
            self.bytes.push(prefix | 26);
            self.bytes.extend_from_slice(&(value as u32).to_be_bytes());
        } else {
            self.bytes.push(prefix | 27);
            self.bytes.extend_from_slice(&value.to_be_bytes());
        }
    }
}

struct Decoder<'a> {
    bytes: &'a [u8],
    offset: usize,
}

impl<'a> Decoder<'a> {
    const fn new(bytes: &'a [u8]) -> Self {
        Self { bytes, offset: 0 }
    }

    fn finish(self) -> Result<(), DecodeError> {
        if self.offset == self.bytes.len() {
            Ok(())
        } else {
            Err(DecodeError::new(FailureCode::TrailingData, self.offset))
        }
    }

    fn semantic_error(&self, code: FailureCode) -> DecodeError {
        DecodeError::new(code, self.offset)
    }

    fn byte(&mut self) -> Result<u8, DecodeError> {
        let value = self
            .bytes
            .get(self.offset)
            .copied()
            .ok_or_else(|| self.semantic_error(FailureCode::MalformedEncoding))?;
        self.offset += 1;
        Ok(value)
    }

    fn fixed<const N: usize>(&mut self) -> Result<[u8; N], DecodeError> {
        let end = self
            .offset
            .checked_add(N)
            .ok_or_else(|| self.semantic_error(FailureCode::BoundsExceeded))?;
        let slice = self
            .bytes
            .get(self.offset..end)
            .ok_or_else(|| self.semantic_error(FailureCode::MalformedEncoding))?;
        let mut value = [0_u8; N];
        value.copy_from_slice(slice);
        self.offset = end;
        Ok(value)
    }

    fn major_value(&mut self, expected_major: u8) -> Result<u64, DecodeError> {
        let start = self.offset;
        let initial = self.byte()?;
        if initial >> 5 != expected_major {
            return Err(DecodeError::new(FailureCode::MalformedEncoding, start));
        }
        let additional = initial & 0x1f;
        match additional {
            value @ 0..=23 => Ok(u64::from(value)),
            24 => {
                let value = u64::from(self.byte()?);
                if value < 24 {
                    return Err(DecodeError::new(FailureCode::NonCanonicalEncoding, start));
                }
                Ok(value)
            }
            25 => {
                let value = u64::from(u16::from_be_bytes(self.fixed()?));
                if value <= u8::MAX as u64 {
                    return Err(DecodeError::new(FailureCode::NonCanonicalEncoding, start));
                }
                Ok(value)
            }
            26 => {
                let value = u64::from(u32::from_be_bytes(self.fixed()?));
                if value <= u16::MAX as u64 {
                    return Err(DecodeError::new(FailureCode::NonCanonicalEncoding, start));
                }
                Ok(value)
            }
            27 => {
                let value = u64::from_be_bytes(self.fixed()?);
                if value <= u32::MAX as u64 {
                    return Err(DecodeError::new(FailureCode::NonCanonicalEncoding, start));
                }
                Ok(value)
            }
            _ => Err(DecodeError::new(FailureCode::MalformedEncoding, start)),
        }
    }

    fn uint(&mut self) -> Result<u64, DecodeError> {
        self.major_value(0)
    }

    fn array(&mut self, maximum: usize) -> Result<usize, DecodeError> {
        let value = self.major_value(4)?;
        let length =
            usize::try_from(value).map_err(|_| self.semantic_error(FailureCode::BoundsExceeded))?;
        if length > maximum {
            return Err(self.semantic_error(FailureCode::BoundsExceeded));
        }
        Ok(length)
    }

    fn bytes(&mut self, maximum: usize) -> Result<&'a [u8], DecodeError> {
        let value = self.major_value(2)?;
        let length =
            usize::try_from(value).map_err(|_| self.semantic_error(FailureCode::BoundsExceeded))?;
        if length > maximum {
            return Err(self.semantic_error(FailureCode::BoundsExceeded));
        }
        let end = self
            .offset
            .checked_add(length)
            .ok_or_else(|| self.semantic_error(FailureCode::BoundsExceeded))?;
        let value = self
            .bytes
            .get(self.offset..end)
            .ok_or_else(|| self.semantic_error(FailureCode::MalformedEncoding))?;
        self.offset = end;
        Ok(value)
    }
}

fn encode_binding(encoder: &mut Encoder, binding: DomainAuthorityBinding) {
    encoder.array(3);
    encoder.bytes(binding.state_domain().as_bytes());
    encoder.uint(u64::from(binding.host_authority().as_u8()));
    encoder.uint(binding.authority_epoch());
}

fn decode_binding(decoder: &mut Decoder<'_>) -> Result<DomainAuthorityBinding, DecodeError> {
    require_array(decoder, 3)?;
    let state_domain = decode_hash(decoder)?;
    let raw_host = decoder.uint()?;
    let host = u8::try_from(raw_host)
        .map_err(|_| decoder.semantic_error(FailureCode::UnsupportedHostAuthority))?;
    let host = HostAuthority::try_from(host).map_err(|code| decoder.semantic_error(code))?;
    let authority_epoch = decoder.uint()?;
    Ok(DomainAuthorityBinding::new(
        state_domain,
        host,
        authority_epoch,
    ))
}

fn encode_hash(encoder: &mut Encoder, hash: Hash32) {
    encoder.bytes(hash.as_bytes());
}

fn decode_hash(decoder: &mut Decoder<'_>) -> Result<Hash32, DecodeError> {
    let bytes = decoder.bytes(32)?;
    if bytes.len() != 32 {
        return Err(decoder.semantic_error(FailureCode::MalformedEncoding));
    }
    let mut hash = [0_u8; 32];
    hash.copy_from_slice(bytes);
    Ok(Hash32::new(hash))
}

fn require_array(decoder: &mut Decoder<'_>, expected: usize) -> Result<(), DecodeError> {
    let actual = decoder.array(expected)?;
    if actual != expected {
        return Err(decoder.semantic_error(FailureCode::InvalidSchema));
    }
    Ok(())
}

fn require_schema(decoder: &mut Decoder<'_>) -> Result<(), DecodeError> {
    let schema = decoder.uint()?;
    if schema != u64::from(SCHEMA_VERSION) {
        return Err(decoder.semantic_error(FailureCode::UnsupportedVersion));
    }
    Ok(())
}

fn encode_access(encoder: &mut Encoder, access: &ObjectAccess) {
    encoder.array(4);
    encode_hash(encoder, access.object_id());
    encoder.uint(u64::from(access.mode().as_u8()));
    encoder.uint(access.expected_version());
    match access.fencing_token() {
        None => encoder.array(0),
        Some(token) => {
            encoder.array(1);
            encoder.uint(token.get());
        }
    }
}

fn decode_access(decoder: &mut Decoder<'_>) -> Result<ObjectAccess, DecodeError> {
    require_array(decoder, 4)?;
    let object_id = decode_hash(decoder)?;
    let raw_mode = decoder.uint()?;
    let mode =
        u8::try_from(raw_mode).map_err(|_| decoder.semantic_error(FailureCode::AccessDenied))?;
    let mode = AccessMode::try_from(mode).map_err(|code| decoder.semantic_error(code))?;
    let expected_version = decoder.uint()?;
    let token_length = decoder.array(1)?;
    let fencing_token = match token_length {
        0 => None,
        1 => {
            let value = decoder.uint()?;
            Some(
                NonZeroU64::new(value)
                    .ok_or_else(|| decoder.semantic_error(FailureCode::InvalidFencingToken))?,
            )
        }
        _ => return Err(decoder.semantic_error(FailureCode::InvalidFencingToken)),
    };
    ObjectAccess::new(object_id, mode, expected_version, fencing_token)
        .map_err(|code| decoder.semantic_error(code))
}

#[must_use]
pub fn encode_state_object_header(header: &StateObjectHeader) -> Vec<u8> {
    let mut encoder = Encoder::default();
    encoder.array(5);
    encoder.uint(u64::from(SCHEMA_VERSION));
    encode_hash(&mut encoder, header.object_id());
    encode_binding(&mut encoder, header.binding());
    encoder.uint(header.version());
    encode_hash(&mut encoder, header.state_commitment());
    encoder.into_bytes()
}

pub fn decode_state_object_header(bytes: &[u8]) -> Result<StateObjectHeader, DecodeError> {
    let mut decoder = Decoder::new(bytes);
    require_array(&mut decoder, 5)?;
    require_schema(&mut decoder)?;
    let object_id = decode_hash(&mut decoder)?;
    let binding = decode_binding(&mut decoder)?;
    let version = decoder.uint()?;
    let state_commitment = decode_hash(&mut decoder)?;
    decoder.finish()?;
    Ok(StateObjectHeader::new(
        object_id,
        binding,
        version,
        state_commitment,
    ))
}

#[must_use]
pub fn encode_unsigned_intent(intent: &UnsignedIntent) -> Vec<u8> {
    let mut encoder = Encoder::default();
    encoder.array(16);
    encoder.uint(u64::from(SCHEMA_VERSION));
    encode_hash(&mut encoder, intent.actor_root());
    encode_binding(&mut encoder, intent.binding());
    encoder.uint(intent.nonce());
    encoder.uint(intent.valid_until_height());
    encode_hash(&mut encoder, intent.program_id());
    encode_hash(&mut encoder, intent.workflow_definition_hash());
    encoder.array(intent.accesses().len());
    for access in intent.accesses() {
        encode_access(&mut encoder, access);
    }
    encode_hash(&mut encoder, intent.input_commitment());
    encode_hash(&mut encoder, intent.expected_output_commitment());
    encode_hash(&mut encoder, intent.evidence_root());
    encode_hash(&mut encoder, intent.sidecar_root());
    encoder.uint(u64::from(intent.signature_suite().as_u8()));
    encoder.uint(u64::from(intent.execution_tier().as_u8()));
    encoder.uint(intent.max_execution_units());
    encoder.uint(intent.max_settlement_cost());
    encoder.into_bytes()
}

pub fn decode_unsigned_intent(bytes: &[u8]) -> Result<UnsignedIntent, DecodeError> {
    let mut decoder = Decoder::new(bytes);
    require_array(&mut decoder, 16)?;
    require_schema(&mut decoder)?;
    let actor_root = decode_hash(&mut decoder)?;
    let binding = decode_binding(&mut decoder)?;
    let nonce = decoder.uint()?;
    let valid_until_height = decoder.uint()?;
    let program_id = decode_hash(&mut decoder)?;
    let workflow_definition_hash = decode_hash(&mut decoder)?;
    let access_count = decoder.array(MAX_OBJECT_ACCESSES)?;
    let mut accesses = Vec::with_capacity(access_count);
    for _ in 0..access_count {
        accesses.push(decode_access(&mut decoder)?);
    }
    let input_commitment = decode_hash(&mut decoder)?;
    let expected_output_commitment = decode_hash(&mut decoder)?;
    let evidence_root = decode_hash(&mut decoder)?;
    let sidecar_root = decode_hash(&mut decoder)?;
    let raw_signature_suite = decoder.uint()?;
    let signature_suite = u8::try_from(raw_signature_suite)
        .map_err(|_| decoder.semantic_error(FailureCode::InvalidSignatureSuite))?;
    let signature_suite =
        SignatureSuite::try_from(signature_suite).map_err(|code| decoder.semantic_error(code))?;
    let raw_execution_tier = decoder.uint()?;
    let execution_tier = u8::try_from(raw_execution_tier)
        .map_err(|_| decoder.semantic_error(FailureCode::InvalidExecutionTier))?;
    let execution_tier =
        ExecutionTier::try_from(execution_tier).map_err(|code| decoder.semantic_error(code))?;
    let max_execution_units = decoder.uint()?;
    let max_settlement_cost = decoder.uint()?;
    decoder.finish()?;
    let commitments = IntentCommitments::new(
        actor_root,
        workflow_definition_hash,
        input_commitment,
        expected_output_commitment,
        evidence_root,
        sidecar_root,
    );
    let execution_policy = ExecutionPolicy::new(
        signature_suite,
        execution_tier,
        max_execution_units,
        max_settlement_cost,
    )
    .map_err(|code| DecodeError::new(code, bytes.len()))?;
    UnsignedIntent::new(
        commitments,
        binding,
        nonce,
        valid_until_height,
        program_id,
        accesses,
        execution_policy,
    )
    .map_err(|code| DecodeError::new(code, bytes.len()))
}

fn encode_outcome(encoder: &mut Encoder, outcome: TransitionOutcome) {
    match outcome {
        TransitionOutcome::Success => {
            encoder.array(1);
            encoder.uint(0);
        }
        TransitionOutcome::Failure {
            code,
            instruction_index,
        } => {
            encoder.array(3);
            encoder.uint(1);
            encoder.uint(u64::from(code.as_u16()));
            encoder.uint(u64::from(instruction_index));
        }
    }
}

fn decode_outcome(decoder: &mut Decoder<'_>) -> Result<TransitionOutcome, DecodeError> {
    let length = decoder.array(3)?;
    let discriminator = decoder.uint()?;
    match (length, discriminator) {
        (1, 0) => Ok(TransitionOutcome::Success),
        (3, 1) => {
            let raw_code = decoder.uint()?;
            let raw_index = decoder.uint()?;
            let code = u16::try_from(raw_code)
                .map_err(|_| decoder.semantic_error(FailureCode::InvalidOutcome))?;
            let code = FailureCode::try_from(code)
                .map_err(|_| decoder.semantic_error(FailureCode::InvalidOutcome))?;
            let instruction_index = u32::try_from(raw_index)
                .map_err(|_| decoder.semantic_error(FailureCode::InvalidOutcome))?;
            Ok(TransitionOutcome::Failure {
                code,
                instruction_index,
            })
        }
        _ => Err(decoder.semantic_error(FailureCode::InvalidOutcome)),
    }
}

#[must_use]
pub fn encode_semantic_receipt(receipt: &SemanticReceipt) -> Vec<u8> {
    let mut encoder = Encoder::default();
    encoder.array(9);
    encoder.uint(u64::from(SCHEMA_VERSION));
    encode_hash(&mut encoder, receipt.intent_id());
    encode_hash(&mut encoder, receipt.program_id());
    encode_binding(&mut encoder, receipt.binding());
    encode_hash(&mut encoder, receipt.pre_state_root());
    encode_hash(&mut encoder, receipt.post_state_root());
    encode_hash(&mut encoder, receipt.output_commitment());
    encoder.uint(receipt.gas_used());
    encode_outcome(&mut encoder, receipt.outcome());
    encoder.into_bytes()
}

pub fn decode_semantic_receipt(bytes: &[u8]) -> Result<SemanticReceipt, DecodeError> {
    let mut decoder = Decoder::new(bytes);
    require_array(&mut decoder, 9)?;
    require_schema(&mut decoder)?;
    let intent_id = decode_hash(&mut decoder)?;
    let program_id = decode_hash(&mut decoder)?;
    let binding = decode_binding(&mut decoder)?;
    let pre_state_root = decode_hash(&mut decoder)?;
    let post_state_root = decode_hash(&mut decoder)?;
    let output_commitment = decode_hash(&mut decoder)?;
    let gas_used = decoder.uint()?;
    let outcome = decode_outcome(&mut decoder)?;
    decoder.finish()?;
    Ok(SemanticReceipt::new(
        intent_id,
        program_id,
        binding,
        ReceiptCommitments::new(pre_state_root, post_state_root, output_commitment),
        gas_used,
        outcome,
    ))
}

#[must_use]
pub fn encode_settlement_metadata(metadata: &SettlementMetadata) -> Vec<u8> {
    let mut encoder = Encoder::default();
    encoder.array(8);
    encoder.uint(u64::from(SCHEMA_VERSION));
    encode_hash(&mut encoder, metadata.receipt_hash());
    encode_binding(&mut encoder, metadata.binding());
    encode_hash(&mut encoder, metadata.source_chain_reference());
    encode_hash(&mut encoder, metadata.source_transaction_hash());
    encoder.uint(metadata.settled_at_height());
    encode_hash(&mut encoder, metadata.bridge_proof_hash());
    encode_hash(&mut encoder, metadata.payload_hash());
    encoder.into_bytes()
}

pub fn decode_settlement_metadata(bytes: &[u8]) -> Result<SettlementMetadata, DecodeError> {
    let mut decoder = Decoder::new(bytes);
    require_array(&mut decoder, 8)?;
    require_schema(&mut decoder)?;
    let receipt_hash = decode_hash(&mut decoder)?;
    let binding = decode_binding(&mut decoder)?;
    let source_chain_reference = decode_hash(&mut decoder)?;
    let source_transaction_hash = decode_hash(&mut decoder)?;
    let settled_at_height = decoder.uint()?;
    let bridge_proof_hash = decode_hash(&mut decoder)?;
    let payload_hash = decode_hash(&mut decoder)?;
    decoder.finish()?;
    SettlementMetadata::new(
        receipt_hash,
        binding,
        source_chain_reference,
        source_transaction_hash,
        settled_at_height,
        bridge_proof_hash,
        payload_hash,
    )
    .map_err(|code| DecodeError::new(code, bytes.len()))
}

#[must_use]
pub fn encode_u64_values(values: &[u64]) -> Vec<u8> {
    let mut encoder = Encoder::default();
    encoder.array(values.len());
    for value in values {
        encoder.uint(*value);
    }
    encoder.into_bytes()
}

pub fn decode_u64_values(bytes: &[u8], maximum: usize) -> Result<Vec<u64>, DecodeError> {
    let mut decoder = Decoder::new(bytes);
    let length = decoder.array(maximum)?;
    let mut values = Vec::with_capacity(length);
    for _ in 0..length {
        values.push(decoder.uint()?);
    }
    decoder.finish()?;
    Ok(values)
}

#[must_use]
pub fn intent_id(intent: &UnsignedIntent) -> Hash32 {
    prefixed_hash(DOMAIN_INTENT, &encode_unsigned_intent(intent))
}

#[must_use]
pub fn program_id(
    vir_version: u16,
    bytecode: &[u8],
    host_function_set_hash: Hash32,
    gas_schedule_hash: Hash32,
    arithmetic_policy_hash: Hash32,
) -> Hash32 {
    let bytecode_hash = keccak256(bytecode);
    let mut preimage = Vec::with_capacity(DOMAIN_PROGRAM.len() + 2 + 32 * 4);
    preimage.extend_from_slice(DOMAIN_PROGRAM);
    preimage.extend_from_slice(&vir_version.to_be_bytes());
    preimage.extend_from_slice(bytecode_hash.as_bytes());
    preimage.extend_from_slice(host_function_set_hash.as_bytes());
    preimage.extend_from_slice(gas_schedule_hash.as_bytes());
    preimage.extend_from_slice(arithmetic_policy_hash.as_bytes());
    keccak256(&preimage)
}

#[must_use]
pub fn workflow_id(
    intent_id: Hash32,
    workflow_definition_hash: Hash32,
    runtime_version: u16,
) -> Hash32 {
    let mut preimage = Vec::with_capacity(DOMAIN_WORKFLOW.len() + 66);
    preimage.extend_from_slice(DOMAIN_WORKFLOW);
    preimage.extend_from_slice(intent_id.as_bytes());
    preimage.extend_from_slice(workflow_definition_hash.as_bytes());
    preimage.extend_from_slice(&runtime_version.to_be_bytes());
    keccak256(&preimage)
}

#[must_use]
pub fn input_commitment(values: &[u64]) -> Hash32 {
    prefixed_hash(DOMAIN_INPUT, &encode_u64_values(values))
}

#[must_use]
pub fn output_commitment(values: &[u64]) -> Hash32 {
    prefixed_hash(DOMAIN_OUTPUT, &encode_u64_values(values))
}

#[must_use]
pub fn derive_post_state_root(
    pre_state_root: Hash32,
    intent_id: Hash32,
    output_commitment: Hash32,
) -> Hash32 {
    let mut preimage = Vec::with_capacity(DOMAIN_STATE.len() + 96);
    preimage.extend_from_slice(DOMAIN_STATE);
    preimage.extend_from_slice(pre_state_root.as_bytes());
    preimage.extend_from_slice(intent_id.as_bytes());
    preimage.extend_from_slice(output_commitment.as_bytes());
    keccak256(&preimage)
}

#[must_use]
pub fn receipt_hash(receipt: &SemanticReceipt) -> Hash32 {
    prefixed_hash(DOMAIN_RECEIPT, &encode_semantic_receipt(receipt))
}

fn prefixed_hash(domain: &[u8], payload: &[u8]) -> Hash32 {
    let mut preimage = Vec::with_capacity(domain.len() + payload.len());
    preimage.extend_from_slice(domain);
    preimage.extend_from_slice(payload);
    keccak256(&preimage)
}

/// Ethereum-compatible Keccak-256, using Keccak padding (`0x01`) rather than
/// FIPS SHA3 padding (`0x06`).
#[must_use]
pub fn keccak256(input: &[u8]) -> Hash32 {
    const RATE: usize = 136;
    let mut state = [0_u64; 25];
    let mut chunks = input.chunks_exact(RATE);
    for chunk in chunks.by_ref() {
        absorb_block(&mut state, chunk);
        keccak_f1600(&mut state);
    }

    let remainder = chunks.remainder();
    let mut final_block = [0_u8; RATE];
    final_block[..remainder.len()].copy_from_slice(remainder);
    final_block[remainder.len()] ^= 0x01;
    final_block[RATE - 1] ^= 0x80;
    absorb_block(&mut state, &final_block);
    keccak_f1600(&mut state);

    let mut output = [0_u8; 32];
    for (index, lane) in state.iter().take(4).enumerate() {
        output[index * 8..(index + 1) * 8].copy_from_slice(&lane.to_le_bytes());
    }
    Hash32::new(output)
}

fn absorb_block(state: &mut [u64; 25], block: &[u8]) {
    for (index, bytes) in block.chunks_exact(8).enumerate() {
        let mut lane = [0_u8; 8];
        lane.copy_from_slice(bytes);
        state[index] ^= u64::from_le_bytes(lane);
    }
}

fn keccak_f1600(state: &mut [u64; 25]) {
    const ROUND_CONSTANTS: [u64; 24] = [
        0x0000_0000_0000_0001,
        0x0000_0000_0000_8082,
        0x8000_0000_0000_808a,
        0x8000_0000_8000_8000,
        0x0000_0000_0000_808b,
        0x0000_0000_8000_0001,
        0x8000_0000_8000_8081,
        0x8000_0000_0000_8009,
        0x0000_0000_0000_008a,
        0x0000_0000_0000_0088,
        0x0000_0000_8000_8009,
        0x0000_0000_8000_000a,
        0x0000_0000_8000_808b,
        0x8000_0000_0000_008b,
        0x8000_0000_0000_8089,
        0x8000_0000_0000_8003,
        0x8000_0000_0000_8002,
        0x8000_0000_0000_0080,
        0x0000_0000_0000_800a,
        0x8000_0000_8000_000a,
        0x8000_0000_8000_8081,
        0x8000_0000_0000_8080,
        0x0000_0000_8000_0001,
        0x8000_0000_8000_8008,
    ];
    const ROTATION: [u32; 25] = [
        0, 1, 62, 28, 27, 36, 44, 6, 55, 20, 3, 10, 43, 25, 39, 41, 45, 15, 21, 8, 18, 2, 61, 56,
        14,
    ];

    for round_constant in ROUND_CONSTANTS {
        let mut columns = [0_u64; 5];
        for x in 0..5 {
            columns[x] = state[x] ^ state[x + 5] ^ state[x + 10] ^ state[x + 15] ^ state[x + 20];
        }
        for x in 0..5 {
            let delta = columns[(x + 4) % 5] ^ columns[(x + 1) % 5].rotate_left(1);
            for y in 0..5 {
                state[x + 5 * y] ^= delta;
            }
        }

        let mut lanes = [0_u64; 25];
        for x in 0..5 {
            for y in 0..5 {
                lanes[y + 5 * ((2 * x + 3 * y) % 5)] =
                    state[x + 5 * y].rotate_left(ROTATION[x + 5 * y]);
            }
        }

        for x in 0..5 {
            for y in 0..5 {
                state[x + 5 * y] =
                    lanes[x + 5 * y] ^ ((!lanes[(x + 1) % 5 + 5 * y]) & lanes[(x + 2) % 5 + 5 * y]);
            }
        }
        state[0] ^= round_constant;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hash(byte: u8) -> Hash32 {
        Hash32::new([byte; 32])
    }

    fn hex(hash: Hash32) -> String {
        let mut output = String::with_capacity(64);
        for byte in hash.as_bytes() {
            use std::fmt::Write as _;
            let result = write!(&mut output, "{byte:02x}");
            assert!(result.is_ok());
        }
        output
    }

    #[test]
    fn keccak_matches_published_vectors() {
        assert_eq!(
            hex(keccak256(b"")),
            "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
        );
        assert_eq!(
            hex(keccak256(b"abc")),
            "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45"
        );
    }

    #[test]
    fn state_header_round_trip_preserves_cardano_authority() {
        let binding = DomainAuthorityBinding::new(hash(2), HostAuthority::CardanoPreProd, 3);
        let header = StateObjectHeader::new(hash(1), binding, 9, hash(4));
        let encoded = encode_state_object_header(&header);
        let decoded = decode_state_object_header(&encoded);
        assert_eq!(decoded, Ok(header));
    }

    #[test]
    fn intent_round_trip_preserves_polygon_authority_and_fence() {
        let binding = DomainAuthorityBinding::new(hash(2), HostAuthority::PolygonAmoy, 3);
        let token = NonZeroU64::new(11);
        assert!(token.is_some());
        let access = ObjectAccess::new(hash(4), AccessMode::Reserve, 9, token);
        assert!(access.is_ok());
        let commitments =
            IntentCommitments::new(hash(5), hash(6), hash(7), hash(8), hash(9), hash(10));
        let policy = ExecutionPolicy::new(
            SignatureSuite::Secp256k1Mldsa65,
            ExecutionTier::Tier2,
            100,
            50,
        );
        assert!(policy.is_ok());
        let intent = UnsignedIntent::new(
            commitments,
            binding,
            5,
            100,
            hash(11),
            access.into_iter().collect(),
            match policy {
                Ok(value) => value,
                Err(code) => panic!("unexpected execution policy error: {code:?}"),
            },
        );
        assert!(intent.is_ok());
        let intent = match intent {
            Ok(value) => value,
            Err(code) => panic!("unexpected intent error: {code:?}"),
        };
        let encoded = encode_unsigned_intent(&intent);
        assert_eq!(decode_unsigned_intent(&encoded), Ok(intent));
    }

    #[test]
    fn rejects_non_minimal_integer_and_trailing_data() {
        let non_minimal_schema = [0x85, 0x18, 0x01];
        let error = decode_state_object_header(&non_minimal_schema);
        assert!(matches!(
            error,
            Err(value) if value.code() == FailureCode::NonCanonicalEncoding
        ));

        let binding = DomainAuthorityBinding::new(hash(2), HostAuthority::PolygonAmoy, 3);
        let header = StateObjectHeader::new(hash(1), binding, 9, hash(4));
        let mut encoded = encode_state_object_header(&header);
        encoded.push(0);
        let error = decode_state_object_header(&encoded);
        assert!(matches!(
            error,
            Err(value) if value.code() == FailureCode::TrailingData
        ));
    }

    #[test]
    fn semantic_receipt_cannot_decode_as_settlement_metadata() {
        let binding = DomainAuthorityBinding::new(hash(3), HostAuthority::PolygonAmoy, 1);
        let receipt = SemanticReceipt::new(
            hash(1),
            hash(2),
            binding,
            ReceiptCommitments::new(hash(4), hash(5), hash(6)),
            10,
            TransitionOutcome::Success,
        );
        let encoded = encode_semantic_receipt(&receipt);
        assert_eq!(decode_semantic_receipt(&encoded), Ok(receipt));
        assert!(decode_settlement_metadata(&encoded).is_err());
    }

    #[test]
    fn settlement_round_trip_enforces_local_tuple_and_proof_separation() {
        let binding = DomainAuthorityBinding::new(hash(3), HostAuthority::PolygonAmoy, 1);
        let local = match SettlementMetadata::new(
            hash(1),
            binding,
            Hash32::ZERO,
            Hash32::ZERO,
            0,
            Hash32::ZERO,
            Hash32::ZERO,
        ) {
            Ok(value) => value,
            Err(code) => panic!("unexpected local settlement error: {code:?}"),
        };
        let local_cbor = encode_settlement_metadata(&local);
        assert_eq!(decode_settlement_metadata(&local_cbor), Ok(local));

        let cross_host = match SettlementMetadata::new(
            hash(1),
            binding,
            hash(2),
            hash(3),
            4,
            hash(5),
            hash(6),
        ) {
            Ok(value) => value,
            Err(code) => panic!("unexpected cross-host settlement error: {code:?}"),
        };
        let mut collision_cbor = encode_settlement_metadata(&cross_host);
        let length = collision_cbor.len();
        let bridge_proof = collision_cbor[length - 66..length - 34].to_vec();
        collision_cbor[length - 32..].copy_from_slice(&bridge_proof);
        let collision = decode_settlement_metadata(&collision_cbor);
        assert!(matches!(
            collision,
            Err(value) if value.code() == FailureCode::InvalidSettlementMetadata
        ));
    }

    #[test]
    fn canonical_u64_vectors_round_trip_at_encoding_boundaries() {
        let values = [
            0,
            23,
            24,
            u8::MAX as u64,
            u8::MAX as u64 + 1,
            u16::MAX as u64,
            u16::MAX as u64 + 1,
            u32::MAX as u64,
            u32::MAX as u64 + 1,
            u64::MAX,
        ];
        let encoded = encode_u64_values(&values);
        assert_eq!(
            decode_u64_values(&encoded, values.len()),
            Ok(values.to_vec())
        );
    }
}
