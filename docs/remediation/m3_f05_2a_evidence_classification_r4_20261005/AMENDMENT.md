# F05.2a evidence-classification amendment R4

**Disposition: awaiting independent review.** This overlay changes only the disposition of original negative case applied_keys_parameter: pending to transaction-simulator pass. It preserves the case ID, registry ID, security assertion, source registry SHA-256, every other negative-case disposition, and all mutation entries. The R3 source status is docs/remediation/m3_f05_2a_evidence_classification_r3_20261005/CASE-STATUS.json.

## Exact evidence

- R10 positive-control RUN: docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r10_20261005/RUN.json, SHA-256 fdd13ca0572ba92c302d0e5537ee2670520570dcf25977feb39ebebaa6a3a2c9.
- R11 normal-policy negative RUN: docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r11_20261005/RUN.json, SHA-256 ca0e17acffdffe5877ee6f1b6ffc2facefbbb70a89ab29c78f488b9c5da92cad.
- R12 one-guard mutant positive-control RUN: docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r12_20261005/RUN.json, SHA-256 bcd3e120ecd05b07e35f128f267da0f62f8e6c133042d854166326dfca53b19d.
- Independent triad review: docs/remediation/m3_f05_2a_applied_keys_parameter_triad_review_r1_20261005/INDEPENDENT-REVIEW.md, SHA-256 893a0474e9a3e039834501c139cb546f563d6f708d3428ec0024cbc577492958.

The accepted synthetic triad binds the same alternate applied policy and input context across the R10/R11 normal-policy pair and the R12 exact one-guard mutant. It supports attribution to the named ordered-keys/initial-keys condition at compiled Mint[0], within transaction-simulator scope.

## Scope and limits

This evidence uses a synthetic alternate applied policy only. It grants no mutation-suite credit, original-policy credit, full-ledger-admission credit, Cardano Pre-Prod credit, or live-network credit. Captures are local structured runner records; raw simulator stdout/stderr and external attestation are unavailable. The overlay itself has not received independent review and must not be treated as accepted classification until that review passes.

Counts in this proposed successor: negative cases 48/55 pass, 7 pending, 0 failed; transaction-simulator 44/51 pass, 7 pending, 0 failed. Context-only and routing-only totals are unchanged. Mutation-suite results remain 18/21 pass, 3 pending, 0 failed.

F05/M3 remains open; readiness is NOT READY. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
