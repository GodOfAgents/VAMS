# Independent integrated epoch triad review r2

Outcome: PASS for one synthetic transaction_simulator negative attribution row.
Case r2_signature_for_other_epoch; preserved assertion sign_tuple_with_nonzero_epoch; R4.1 B.

The independent byte review 6c9d866cdac936efc135571fd9cf875b860d3abbf77c0b8d717dad1d850b4a89 independently rebuilt exact normal and mutant applied policies, verified all 15 PoP and six body-bound funding signatures, conservation, and the unique library epoch expression change from 0 to 1 at line 122.

Positive RUN SHA-256 932b2a1898482efd7326a667e345e3f129a861bfe2de1218dcdad43fbaae6093: wrapper/child 0/0, script_accepted.
Negative RUN SHA-256 02ac3c54834047e6a0fedb1b107bec7e37539b5b07ad0cd63998f936b1509d01: wrapper/child 0/1, compiled_evaluation.
Corrected mutant RUN SHA-256 5e5ac7bb9ddb69bd27e007d25de8483c590b5eb863bd3206ceced5a2f03b98a2: wrapper/child 0/0, script_accepted.

All three records have target_script_invoked true, exact submitted transaction/input/output hashes and sizes, and clean teardown. Normal positive/negative applied/mint/V3 identity is 704a7ed54317bfa9c9879a9be02d8ae8859e999ce1a04298697d69ad; mutant identity is 6f2cfb8a849311c6e6076b466daafe77ae5a95de9b50c62caecfafa4. Pinned Aiken and runner hashes match executable bytes. All run and linked-review checksums verify, including the original mutant pre-execution review 7e6b5dc315477798ca020c5e09ade9ca41274a3238e13fbfec72c563d2c3972c and positive review 24fd754d809519e81601c17ce96cace9d5cb23b9c62e4f4c0f2eb0822a683377.

Independent decoded comparisons establish: positive and negative bodies are identical; normal-negative to mutant body differs only by required policy-id substitution. Other witness fields are identical except funding signatures and V3 script. Resolved funding outputs differ only in public-key addresses; values and other fields are identical. Negative and mutant retain identical five proofs, message, public parameters, input references and state semantics. Messages differ solely at the final eight-byte epoch field (offset 271); normal positive binds 0, negative binds 1. The independently rebuilt mutant changes only that preimage epoch encoding, retaining verification, other guards and canonical state-validator address.

Generic compiled_evaluation alone provides no named attribution. Combined with condition-isolated mutant acceptance and accepted positive control, this triad meets R4.1 B for the nonzero-epoch assertion.

VERIFY-TRIAD.py is the exact read-only verifier payload executed by scoped WSL Python through base64-decoded -c; final exit 0. It verifies checksums, submitted bytes, run/review links, tool hashes, R4.1 row, identities and decoded transaction deltas. An earlier reviewer checksum check assumed directory-relative names; it was corrected to support existing canonical-relative names while confining resolution to this checkout. No artifact checksum failure was concealed. No simulator was executed by this reviewer.

Structured R3 results and hashes are retained; raw simulator output and external execution attestations are absent. PASS permits exactly one synthetic alternate-applied-policy transaction_simulator row after separate classification review. Classification/totals were not changed here. No mutation-suite, original-policy, full-ledger-admission, Cardano Pre-Prod, live-network or readiness credit is granted. INV-1 through INV-10 are not touched; canonical source remains unchanged. F05/M3 OPEN; NOT READY; deployment, Deposit, Slash activation and ExecuteIntent disabled. STATUS/HANDOFF untouched.
