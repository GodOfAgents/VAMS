use vir_conformance::{
    INTENT_CBOR_FIELD_ORDER, SETTLEMENT_CBOR_FIELD_ORDER, build_golden_vectors, hex_encode,
};

fn main() {
    let vectors = match build_golden_vectors() {
        Ok(value) => value,
        Err(code) => {
            eprintln!("failed to build golden vectors: {code:?}");
            std::process::exit(1);
        }
    };

    println!("{{");
    println!("  \"schema\": \"vir-core-v1\",");
    println!("  \"host_authority\": \"cardano-pre-prod\",");
    println!("  \"cardano_access_modes\": [\"READ\", \"ACCUMULATE\"],");
    println!(
        "  \"intent_cbor_field_order\": [{}],",
        INTENT_CBOR_FIELD_ORDER
            .iter()
            .map(|field| format!("\"{field}\""))
            .collect::<Vec<_>>()
            .join(", ")
    );
    println!("  \"max_settlement_cost_type\": \"u64\",");
    println!("  \"signature_suite\": 2,");
    println!("  \"execution_tier\": 2,");
    println!("  \"max_execution_units\": 100,");
    println!("  \"max_settlement_cost\": 5000,");
    println!(
        "  \"settlement_cbor_field_order\": [{}],",
        SETTLEMENT_CBOR_FIELD_ORDER
            .iter()
            .map(|field| format!("\"{field}\""))
            .collect::<Vec<_>>()
            .join(", ")
    );
    println!("  \"settlement_kind\": \"cross-host\",");
    println!("  \"unsupported_policy_commitment\": 43,");
    println!("  \"unsupported_policy_commitment_cbor_uint\": \"182b\",");
    println!("  \"invalid_settlement_metadata\": 44,");
    println!("  \"host_function_set_policy_ascii\": \"VAMS:VIR:v1:host-functions:none\",");
    println!(
        "  \"host_function_set_hash\": \"{}\",",
        hex_encode(vectors.host_function_set_hash.as_bytes())
    );
    println!(
        "  \"gas_schedule_policy_ascii\": \"VAMS:VIR:v1:gas:push=1,load-input=1,add=2,sub=2,mul=3,div=3,eq=2,dup=1,drop=1,halt=0\","
    );
    println!(
        "  \"gas_schedule_hash\": \"{}\",",
        hex_encode(vectors.gas_schedule_hash.as_bytes())
    );
    println!(
        "  \"arithmetic_policy_ascii\": \"VAMS:VIR:v1:arithmetic:u64,checked-overflow,checked-underflow,zero-divisor-reject\","
    );
    println!(
        "  \"arithmetic_policy_hash\": \"{}\",",
        hex_encode(vectors.arithmetic_policy_hash.as_bytes())
    );
    println!(
        "  \"state_object_header_cbor\": \"{}\",",
        hex_encode(&vectors.state_object_header_cbor)
    );
    println!(
        "  \"program_bytecode\": \"{}\",",
        hex_encode(&vectors.program_bytecode)
    );
    println!(
        "  \"program_id\": \"{}\",",
        hex_encode(vectors.program_id.as_bytes())
    );
    println!(
        "  \"unsigned_intent_cbor\": \"{}\",",
        hex_encode(&vectors.unsigned_intent_cbor)
    );
    println!(
        "  \"intent_id\": \"{}\",",
        hex_encode(vectors.intent_id.as_bytes())
    );
    println!(
        "  \"semantic_receipt_cbor\": \"{}\",",
        hex_encode(&vectors.semantic_receipt_cbor)
    );
    println!(
        "  \"semantic_receipt_hash\": \"{}\",",
        hex_encode(vectors.semantic_receipt_hash.as_bytes())
    );
    println!(
        "  \"settlement_metadata_cbor\": \"{}\",",
        hex_encode(&vectors.settlement_metadata_cbor)
    );
    println!(
        "  \"workflow_id\": \"{}\"",
        hex_encode(vectors.workflow_id.as_bytes())
    );
    println!("}}");
}
