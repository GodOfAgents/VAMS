"""Design-package syntax checks only; no authorization or effect semantics."""
import json
from pathlib import Path
import jsonschema

ROOT = Path(__file__).resolve().parent
schema = json.loads((ROOT / "envelope.schema.json").read_text(encoding="utf-8"))
jsonschema.Draft202012Validator.check_schema(schema)

bindings = schema["properties"]["source_bindings"]
required = bindings["required"]
assert len(required) == len(set(required))
assert set(required) == set(bindings["properties"])
assert len(required) == 33

digest = "a" * 64
claim = {"ref": "opaque:ref1", "digest": digest}
source_bindings = {
    key: {"source_ref": "opaque:source", "source_digest": digest, "value_digest": digest}
    for key in required
}
instance = {
    "schema_id": "vams.m6.gca-envelope.v1",
    "envelope_id": "00000000-0000-4000-8000-000000000001",
    "actor_root": claim,
    "execution_context": {"provider": claim, "runtime": claim, "model": claim, "circuit": claim},
    "host_chain_domain": {"host": claim, "chain": claim, "domain": claim},
    "authority_epoch": 1,
    "workflow_definition": claim,
    "logical_intent": claim,
    "operation_id": "00000000-0000-4000-8000-000000000002",
    "action": {
        "target": claim,
        "operation": "write",
        "action_commitment": digest,
        "input_commitment": digest,
        "output_commitment": digest,
    },
    "capabilities": {"permitted_refs": ["cap:one"], "commitment": digest},
    "budget": {
        "unit_ref": "unit:opaque",
        "requested_units": 1,
        "maximum_units": 2,
        "commitment": digest,
    },
    "policy": {"root": claim, "version": 1},
    "anchor": {
        "ref": "anchor:opaque",
        "digest": digest,
        "observed_at": "2026-10-04T00:00:00Z",
        "fresh_until": "2026-10-04T00:01:00Z",
        "finality_claim": "UNKNOWN",
        "checkpoint_ref": "checkpoint:opaque",
    },
    "decision": {"outcome": "UNKNOWN", "record_digest": digest},
    "nonce": digest,
    "validity": {
        "issued_at": "2026-10-04T00:00:00Z",
        "expires_at": "2026-10-04T00:01:00Z",
    },
    "effect": {
        "status": "NOT_STARTED",
        "effect_receipt": None,
        "settlement_receipt": None,
        "readback": None,
    },
    "evidence": {
        "class": "synthetic",
        "artifact": claim,
        "review_class": "not_reviewed",
    },
    "source_bindings": source_bindings,
}
validator = jsonschema.Draft202012Validator(
    schema, format_checker=jsonschema.FormatChecker()
)
assert not list(validator.iter_errors(instance))
print("JSON Schema 2020-12 meta-validation: PASS")
print("complete 33-path synthetic claim shape: PASS")
for key in ("host", "anchor_record", "evidence_class", "effect_status", "readback", "issued_at"):
    candidate = json.loads(json.dumps(instance))
    candidate["source_bindings"].pop(key)
    assert list(validator.iter_errors(candidate))
print("missing-source-binding rejections: PASS")
candidate = json.loads(json.dumps(instance))
candidate["nonce"] = "xyz"
assert list(validator.iter_errors(candidate))
candidate = json.loads(json.dumps(instance))
candidate["unexpected"] = True
assert list(validator.iter_errors(candidate))
print("malformed nonce and unknown-field rejections: PASS")
print("synthetic syntax only; no authentication or effect behavior tested")
