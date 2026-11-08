# F05.2a unconditional-success full synthetic suite R2

Status: **pass for direct-UPLC synthetic harness only; independent review required; no mutation credit yet**.

The repaired harness completed with status `pass`, no failures, 57 baseline positive/negative context evaluations, and 21 compiled mutation records. The `unconditional_success` mutation includes an accepted separately rebound positive control and 55/55 accepted negative subcases. Each subcase records mutant policy ID, script hash, context hash, genesis-reference CBOR hash, and initial-key CBOR hash. The capture is direct-UPLC context evidence: it contains no transaction witness, body-bound funding signature, ledger-admission, Pre-Prod, live-network, or deployment evidence.

RUN.json SHA-256: `0ba7df6632bdca84bfc71ae43c02f36fb2b4e44884ae31c40e15e4b44d0244e3`. The run used the pinned Aiken 1.1.21 toolchain and the repaired harness; no private keys are persisted by the capture. Existing mutation rows are observed as detected by the synthetic harness, but the registered mutation ledger remains 18/21 until independent review and a separate classification decision.

No production validator, original policy, fixture registry, credentials, deployment state, or activation gate changed in this execution.
