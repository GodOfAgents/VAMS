# F05 typed transaction mint-binding guard independent review - 2026-10-03

## Result: PASS

I reviewed the exact F05 verifier and test changes. The CBOR decoder represents maps as ordered pairs and preserves duplicate entries. The verifier now requires exactly one mint-map pair and a byte-string policy key before checking the expected policy ID and the V3 witness hash. A duplicate policy entry is rejected before subprocess simulation.

The regression also now loads and re-encodes the transaction with one CBOR helper module instance, avoiding class-identity mismatch between separately imported Map/Tag classes. Existing wrong-policy/witness checks remain, and the test asserts an unbound transaction causes zero simulator calls.

Scope is limited to F05 simulator-evidence binding and its test harness. Validator semantics, applied artifact identity, evidence case status, and mutation status are unchanged. No INV-1 through INV-10 control is modified. The slice grants no case/mutation credit.

The writer reports 21 passed and 15 nested passing subtests across the three related modules. I inspected source/tests and did not rerun tests, as requested.
