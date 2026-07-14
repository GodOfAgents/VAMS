//! Cross-client VIR-Core v1 conformance fixtures.

use vir_codec::{
    encode_semantic_receipt, encode_settlement_metadata, encode_state_object_header,
    encode_unsigned_intent, input_commitment, intent_id, output_commitment, receipt_hash,
    workflow_id,
};
use vir_runtime::{
    ExecutionContext, Program, VIR_VERSION, execute, opcode, supported_arithmetic_policy_hash,
    supported_gas_schedule_hash, supported_host_function_set_hash,
};
use vir_types::{
    AccessMode, DomainAuthorityBinding, ExecutionPolicy, ExecutionTier, FailureCode, Hash32,
    HostAuthority, IntentCommitments, ObjectAccess, SettlementMetadata, SignatureSuite,
    StateObjectHeader, UnsignedIntent,
};

pub const INTENT_CBOR_FIELD_ORDER: [&str; 16] = [
    "schemaVersion",
    "actorRoot",
    "domainAuthorityBinding",
    "nonce",
    "validUntilHeight",
    "programId",
    "workflowDefinitionHash",
    "accesses",
    "inputCommitment",
    "expectedOutputCommitment",
    "evidenceRoot",
    "sidecarRoot",
    "signatureSuite",
    "executionTier",
    "maxExecutionUnits",
    "maxSettlementCost",
];

pub const SETTLEMENT_CBOR_FIELD_ORDER: [&str; 8] = [
    "schemaVersion",
    "receiptHash",
    "domainAuthorityBinding",
    "sourceChainReference",
    "sourceTransactionHash",
    "settledAtHeight",
    "bridgeProofHash",
    "payloadHash",
];

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct GoldenVectors {
    pub state_object_header_cbor: Vec<u8>,
    pub program_bytecode: Vec<u8>,
    pub host_function_set_hash: Hash32,
    pub gas_schedule_hash: Hash32,
    pub arithmetic_policy_hash: Hash32,
    pub program_id: Hash32,
    pub unsigned_intent_cbor: Vec<u8>,
    pub intent_id: Hash32,
    pub semantic_receipt_cbor: Vec<u8>,
    pub semantic_receipt_hash: Hash32,
    pub settlement_metadata_cbor: Vec<u8>,
    pub workflow_id: Hash32,
}

#[must_use]
pub fn hex_encode(bytes: &[u8]) -> String {
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        use std::fmt::Write as _;
        let result = write!(&mut output, "{byte:02x}");
        debug_assert!(result.is_ok());
    }
    output
}

pub fn build_golden_vectors() -> Result<GoldenVectors, FailureCode> {
    let binding = DomainAuthorityBinding::new(hash(0x30), HostAuthority::CardanoPreProd, 4);

    let program_bytecode = vec![
        opcode::LOAD_INPUT,
        0,
        opcode::LOAD_INPUT,
        1,
        opcode::ADD_U64,
        opcode::HALT,
    ];
    let program = Program::new(
        program_bytecode.clone(),
        supported_host_function_set_hash(),
        supported_gas_schedule_hash(),
        supported_arithmetic_policy_hash(),
    )
    .map_err(|error| error.code())?;

    let read_access = ObjectAccess::new(hash(0x20), AccessMode::Read, 5, None)?;
    let accumulate_access = ObjectAccess::new(hash(0x21), AccessMode::Accumulate, 7, None)?;
    let inputs = [7_u64, 9_u64];
    let commitments = IntentCommitments::new(
        hash(0x31),
        hash(0x60),
        input_commitment(&inputs),
        output_commitment(&[16]),
        hash(0x61),
        hash(0x62),
    );
    let execution_policy = ExecutionPolicy::new(
        SignatureSuite::Secp256k1Mldsa65,
        ExecutionTier::Tier2,
        100,
        5_000,
    )?;
    let intent = UnsignedIntent::new(
        commitments,
        binding,
        42,
        999,
        program.id(),
        vec![read_access, accumulate_access],
        execution_policy,
    )?;

    let first_header = StateObjectHeader::new(hash(0x20), binding, 5, hash(0x40));
    let second_header = StateObjectHeader::new(hash(0x21), binding, 7, hash(0x41));
    let context = ExecutionContext::new(900, 100, hash(0x50));
    let receipt = execute(
        &program,
        &intent,
        binding,
        &[first_header.clone(), second_header],
        &inputs,
        context,
    )
    .map_err(|error| error.code())?;
    let semantic_receipt_hash = receipt_hash(&receipt);
    let settlement = SettlementMetadata::new(
        semantic_receipt_hash,
        binding,
        hash(0x70),
        hash(0x71),
        123_456,
        hash(0x72),
        hash(0x73),
    )?;
    let computed_intent_id = intent_id(&intent);

    Ok(GoldenVectors {
        state_object_header_cbor: encode_state_object_header(&first_header),
        program_bytecode,
        host_function_set_hash: supported_host_function_set_hash(),
        gas_schedule_hash: supported_gas_schedule_hash(),
        arithmetic_policy_hash: supported_arithmetic_policy_hash(),
        program_id: program.id(),
        unsigned_intent_cbor: encode_unsigned_intent(&intent),
        intent_id: computed_intent_id,
        semantic_receipt_cbor: encode_semantic_receipt(&receipt),
        semantic_receipt_hash,
        settlement_metadata_cbor: encode_settlement_metadata(&settlement),
        workflow_id: workflow_id(
            computed_intent_id,
            intent.workflow_definition_hash(),
            VIR_VERSION,
        ),
    })
}

const fn hash(byte: u8) -> Hash32 {
    Hash32::new([byte; 32])
}

#[cfg(test)]
mod tests {
    use super::*;
    use vir_codec::{
        decode_semantic_receipt, decode_settlement_metadata, decode_state_object_header,
        decode_unsigned_intent,
    };

    fn must<T, E: std::fmt::Debug>(result: Result<T, E>) -> T {
        match result {
            Ok(value) => value,
            Err(error) => panic!("unexpected error: {error:?}"),
        }
    }

    const STATE_HEADER_CBOR: &str = "850158202020202020202020202020202020202020202020202020202020202020202020835820303030303030303030303030303030303030303030303030303030303030303001040558204040404040404040404040404040404040404040404040404040404040404040";
    const HOST_FUNCTION_SET_HASH: &str =
        "926aa059fa0db9477ba813b969d5c1dcf92fbcdbf7e00d6ceeec13ceef33e860";
    const GAS_SCHEDULE_HASH: &str =
        "ea7983ef0e10911d248e354efebafd3b05a479e50ba5f0cfa46890f74034f773";
    const ARITHMETIC_POLICY_HASH: &str =
        "e6231804a0697191feee14abb9b5806f393a2725a10c0fc92f0159ee79c893a5";
    const PROGRAM_ID: &str = "665438cdbc643b5d3947e47fd56d14a792daa805dee405ffc423c445095392a1";
    const INTENT_CBOR: &str = "90015820313131313131313131313131313131313131313131313131313131313131313183582030303030303030303030303030303030303030303030303030303030303030300104182a1903e75820665438cdbc643b5d3947e47fd56d14a792daa805dee405ffc423c445095392a15820606060606060606060606060606060606060606060606060606060606060606082845820202020202020202020202020202020202020202020202020202020202020202000058084582021212121212121212121212121212121212121212121212121212121212121210307805820902188534cc8e8be436828d1329c194c793d2f591921e6f0d42c48379bfb14fc5820507c1c9e5414952f2017497a5a6da6cf639c820712d2266d2978ae5a200a3dcf582061616161616161616161616161616161616161616161616161616161616161615820626262626262626262626262626262626262626262626262626262626262626202021864191388";
    const INTENT_ID: &str = "34ff92df19e5c307274e04c67c86cc1df590f48c91013ccdf8fb488125b7824c";
    const RECEIPT_CBOR: &str = "8901582034ff92df19e5c307274e04c67c86cc1df590f48c91013ccdf8fb488125b7824c5820665438cdbc643b5d3947e47fd56d14a792daa805dee405ffc423c445095392a183582030303030303030303030303030303030303030303030303030303030303030300104582050505050505050505050505050505050505050505050505050505050505050505820b883c242e3ffd091ed553156773dfa7fc9d644da21c4d787e871dd6bf6f949795820507c1c9e5414952f2017497a5a6da6cf639c820712d2266d2978ae5a200a3dcf048100";
    const RECEIPT_HASH: &str = "c3142a5bebfe0b0d57272ba32a131a16bf681c2a9ac06a05a123cdc2d386ac49";
    const SETTLEMENT_CBOR: &str = "88015820c3142a5bebfe0b0d57272ba32a131a16bf681c2a9ac06a05a123cdc2d386ac498358203030303030303030303030303030303030303030303030303030303030303030010458207070707070707070707070707070707070707070707070707070707070707070582071717171717171717171717171717171717171717171717171717171717171711a0001e2405820727272727272727272727272727272727272727272727272727272727272727258207373737373737373737373737373737373737373737373737373737373737373";
    const WORKFLOW_ID: &str = "4eac49f32545e8f3cfe916cf340c169778d9d9f76420354cbffe9233c29871e2";

    #[test]
    fn golden_fixture_is_deterministic() {
        let first = must(build_golden_vectors());
        let second = must(build_golden_vectors());
        assert_eq!(first, second);
    }

    #[test]
    fn generated_values_match_committed_cross_client_vectors() {
        let vectors = must(build_golden_vectors());
        assert_eq!(
            hex_encode(&vectors.state_object_header_cbor),
            STATE_HEADER_CBOR
        );
        assert_eq!(
            hex_encode(vectors.host_function_set_hash.as_bytes()),
            HOST_FUNCTION_SET_HASH
        );
        assert_eq!(
            hex_encode(vectors.gas_schedule_hash.as_bytes()),
            GAS_SCHEDULE_HASH
        );
        assert_eq!(
            hex_encode(vectors.arithmetic_policy_hash.as_bytes()),
            ARITHMETIC_POLICY_HASH
        );
        assert_eq!(hex_encode(vectors.program_id.as_bytes()), PROGRAM_ID);
        assert_eq!(hex_encode(&vectors.unsigned_intent_cbor), INTENT_CBOR);
        assert_eq!(hex_encode(vectors.intent_id.as_bytes()), INTENT_ID);
        assert_eq!(hex_encode(&vectors.semantic_receipt_cbor), RECEIPT_CBOR);
        assert_eq!(
            hex_encode(vectors.semantic_receipt_hash.as_bytes()),
            RECEIPT_HASH
        );
        assert_eq!(
            hex_encode(&vectors.settlement_metadata_cbor),
            SETTLEMENT_CBOR
        );
        assert_eq!(hex_encode(vectors.workflow_id.as_bytes()), WORKFLOW_ID);

        let committed = include_str!("../../../vectors/vir-core-v1.json");
        for value in [
            STATE_HEADER_CBOR,
            HOST_FUNCTION_SET_HASH,
            GAS_SCHEDULE_HASH,
            ARITHMETIC_POLICY_HASH,
            PROGRAM_ID,
            INTENT_CBOR,
            INTENT_ID,
            RECEIPT_CBOR,
            RECEIPT_HASH,
            SETTLEMENT_CBOR,
            WORKFLOW_ID,
        ] {
            assert!(committed.contains(value));
        }
        let mut offset = 0;
        for field in INTENT_CBOR_FIELD_ORDER {
            let needle = format!("\"{field}\"");
            let relative = committed[offset..].find(&needle);
            assert!(relative.is_some());
            if let Some(position) = relative {
                offset += position + needle.len();
            }
        }
        let mut offset = 0;
        for field in SETTLEMENT_CBOR_FIELD_ORDER {
            let needle = format!("\"{field}\"");
            let relative = committed[offset..].find(&needle);
            assert!(relative.is_some());
            if let Some(position) = relative {
                offset += position + needle.len();
            }
        }
        assert!(committed.contains("\"unsupported_policy_commitment\": 43"));
        assert!(committed.contains("\"unsupported_policy_commitment_cbor_uint\": \"182b\""));
        assert!(committed.contains("\"invalid_settlement_metadata\": 44"));
    }

    #[test]
    fn every_cbor_artifact_round_trips_independently() {
        let vectors = must(build_golden_vectors());
        assert!(decode_state_object_header(&vectors.state_object_header_cbor).is_ok());
        assert!(decode_unsigned_intent(&vectors.unsigned_intent_cbor).is_ok());
        assert!(decode_semantic_receipt(&vectors.semantic_receipt_cbor).is_ok());
        assert!(decode_settlement_metadata(&vectors.settlement_metadata_cbor).is_ok());
    }

    #[test]
    fn sample_explicitly_exercises_cardano_domain_authority() {
        let vectors = must(build_golden_vectors());
        let header = must(decode_state_object_header(
            &vectors.state_object_header_cbor,
        ));
        assert_eq!(
            header.binding().host_authority(),
            HostAuthority::CardanoPreProd
        );
        assert_eq!(header.binding().authority_epoch(), 4);
        let intent = must(decode_unsigned_intent(&vectors.unsigned_intent_cbor));
        assert_eq!(intent.signature_suite(), SignatureSuite::Secp256k1Mldsa65);
        assert_eq!(intent.execution_tier(), ExecutionTier::Tier2);
        assert_eq!(intent.max_execution_units(), 100);
        assert_eq!(intent.max_settlement_cost(), 5_000);
        assert_eq!(intent.accesses().len(), 2);
        assert_eq!(intent.accesses()[0].mode(), AccessMode::Read);
        assert_eq!(intent.accesses()[1].mode(), AccessMode::Accumulate);
        assert_eq!(intent.accesses()[0].fencing_token(), None);
        assert_eq!(intent.accesses()[1].fencing_token(), None);
    }

    #[test]
    fn failure_code_43_has_stable_wire_representation() {
        assert_eq!(FailureCode::UnsupportedPolicyCommitment.as_u16(), 43);
        assert_eq!(
            FailureCode::try_from(43),
            Ok(FailureCode::UnsupportedPolicyCommitment)
        );
    }

    #[test]
    fn sample_cross_host_settlement_preserves_inv_10() {
        let vectors = must(build_golden_vectors());
        let settlement = must(decode_settlement_metadata(
            &vectors.settlement_metadata_cbor,
        ));
        assert!(settlement.is_cross_host());
        assert!(!settlement.source_transaction_hash().is_zero());
        assert!(!settlement.bridge_proof_hash().is_zero());
        assert!(!settlement.payload_hash().is_zero());
        assert_ne!(settlement.bridge_proof_hash(), settlement.payload_hash());
    }
}
