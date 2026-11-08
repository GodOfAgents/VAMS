# F05 positive-control evaluator diagnosis and harness classification

Date: 2026-10-03
Status: bounded harness diagnostic correction implemented; independent review pending.

## Finding

The compiled Plutus V3 policy uses verify_ed25519_signature. Pinned Aiken 1.1.21 direct UPLC evaluation exits 101 with Default Function not found - verifySignature while resolving the unsupported builtin, before an accept/reject verdict. Independent read-only reproduction found the same evaluator limitation in preinstalled Aiken 1.1.23. The former harness converted this runtime limitation into a generic fixture-rejected assertion.

## Bounded change and verification

The harness now classifies an explicit missing-default-function diagnostic as evaluator capability failure and states that UPLC evaluation aborted before an accept/reject verdict. Other nonaccepted positive-control results retain the compiled fixture-rejection assertion. No validator, fixture, evidence contract, or credit ledger changed.

The focused diagnostic tests passed 3/3 using the pinned Python 3.12.14/pytest 9.1.1 command in RUN.json. The full public harness still exits 1 at the positive control, now with the precise unsupported-verifySignature error. It produces no RESULT.json; zero negatives and zero mutations executed. Syntax compilation passed. Exact stderr, exit, commands, and source hashes are captured in this folder.

## Evidence and limits

R3.1 still accepts only the #33 single-case overlay; all other cases/mutations remain pending. This change grants no case or mutation credit, ledger admission, or live evidence. Existing R3 transaction-simulator canaries remain synthetic and do not establish complete F05 acceptance. No key was created for live use, and no installation, fetch, chain action, or deployment occurred.

Full-suite remediation requires replacing the incompatible direct UPLC evaluator with the transaction-simulator route while faithfully constructing each case and preserving target-policy binding. Any broader evidence promotion must follow the owner decisions already documented for applied-parameter and proof-domain families.
