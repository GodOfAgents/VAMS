# Independent epoch mutant triad review

Review id: m3_f05_2a_proof_other_epoch_mutant_triage_review_r1_20261005
Outcome: PASS for one synthetic transaction_simulator negative attribution row
Case: r2_signature_for_other_epoch
Decision: R4.1 proof-domain B

## Triad results

The accepted positive control RUN.json SHA-256 is 932b2a1898482efd7326a667e345e3f129a861bfe2de1218dcdad43fbaae6093. Its exact fixture transaction hash matches, wrapper and simulator child both exited 0, and the structured result is script_accepted with target_script_invoked true. Its applied policy id, sole mint policy id, and compiled V3 script hash all equal 704a7ed54317bfa9c9879a9be02d8ae8859e999ce1a04298697d69ad. Its separate positive review is hash-linked and passed.

The normal-policy negative RUN.json SHA-256 is 02ac3c54834047e6a0fedb1b107bec7e37539b5b07ad0cd63998f936b1509d01. Its exact fixture transaction hash matches, wrapper exited 0, simulator child exited 1, and the structured result is generic compiled_evaluation with target_script_invoked true. The target Mint[0] binding uses the same normal applied policy id 704a7ed54317bfa9c9879a9be02d8ae8859e999ce1a04298697d69ad. This generic failure does not identify the named epoch condition on its own. The independent negative review passed attempt integrity only and explicitly withheld named-condition attribution.

The corrected one-expression mutant RUN.json SHA-256 is 5e5ac7bb9ddb69bd27e007d25de8483c590b5eb863bd3206ceced5a2f03b98a2. Its exact transaction/input/output hashes match the current mutant fixture. Wrapper and simulator child both exited 0, and the structured result is script_accepted with target_script_invoked true. The mutant expected policy id, sole mint policy id, and compiled V3 script hash all equal 6f2cfb8a849311c6e6076b466daafe77ae5a95de9b50c62caecfafa4. Teardown is clean for all three attempts.

The corrected mutant manifest identifies source line 122 in cardano/lib/vams/f05_authority.ak. The independently reviewed patch changes only the final epoch argument in authority_genesis_pop_preimage from 0 to 1; canonical state hash and output address guards remain unchanged. The mutant pre-execution review SHA-256 is 7e6b5dc315477798ca020c5e09ade9ca41274a3238e13fbfec72c563d2c3972c and is linked from the mutant RUN. Prior positive and negative run/review hashes also match the retained package copies.

The positive proof message has epoch bytes 0000000000000000 at offset 271, width 8. The normal negative and one-expression mutant use the same reviewed proof message with bytes 0000000000000001 at that field. The pre-execution review verified all five PoP signatures against that message, the mutant policy recompile/binding, body-bound funding signatures, and ADA/NFT conservation. The one-expression mutant accepts while preserving the same negative proof/message/signatures and input/state semantics, isolating the named epoch condition under its separately compiled and rebound policy.

## Attribution and limits

The triad supports exactly one negative row for r2_signature_for_other_epoch in the synthetic transaction_simulator evidence class under R4.1 choice B. The normal generic failure is paired with the condition-isolated mutant acceptance and accepted positive control; attribution does not rely on the generic failure label alone.

Credit is limited to synthetic alternate-applied-policy evidence. No mutation-suite credit, original-policy negative, ledger admission, Cardano Pre-Prod, live-network, or deployment-readiness credit is granted. The source manifest and runs remain synthetic test artifacts.

The retained RUN records contain structured R3 results, exact submitted hashes, pinned runner/tool identities, bindings, and clean teardown, but not raw simulator stdout/stderr or external execution attestations. This review does not repeat transaction execution and does not edit STATUS, HANDOFF, or classification records.
