# F05.2a current-source R3 applied-policy canary revalidation

Date: 2026-10-03
Status: local synthetic canaries passed; independent review pending.

## Result

The exact current public harness source, including the diagnostic correction, was executed through its snapshot-bound R3 transaction-simulator canary mode. The valid canary was accepted and the invalid-signature canary rejected by compiled evaluation. Both invoked policy 9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731 at Mint[0], both wrappers exited 0, and teardown was clean. The captured runner exit was 0. RUN.json binds current source, frozen inputs, exact arguments, toolchain, and output hashes.

## Scope and limits

This is synthetic local transaction-simulator evidence for two canaries only. It adds no registered F05 negative-case or mutation credit, ledger admission, or live-network evidence. The full unconditional_success suite remains blocked before an accept/reject verdict by the installed evaluator missing verifySignature. Current F05 remains 45/55 negatives and 18/21 mutations. Readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
