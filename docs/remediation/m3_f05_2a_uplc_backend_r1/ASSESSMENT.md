# F05 UPLC evaluator and transaction-simulator diagnostic

Date: 2026-10-03
Status: accepted after independent review, with synthetic-scope limits.

No validator, harness, runner, fixture, toolchain, or invariant source changed. The earlier direct aiken uplc eval positive-context capture exited 101 with "Default Function not found - verifySignature" and no CPU or memory result. The public suite stopped at its canonical positive before running negatives. This is an evaluator failure, not a validator rejection. Its ephemeral policy ID differs from the frozen applied policy.

Pinned Aiken 1.1.21 focused native tests passed 2/2 in a disposable, network-isolated Cardano copy: the accepted applied-policy fixture passed and the seed-missing regression rejected. This is native synthetic handler evidence only.

The R3 snapshot-bound runner accepted the frozen valid transaction and rejected the invalid-signature transaction after target Mint[0] invocation. Both wrappers exited 0 with clean teardown; simulator child exits were 0 and 1. The applied policy, sole mint policy, and script witness hash were all 9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731.

These results confirm only these two synthetic fixtures through the local simulator. They earn no registered negative-case or mutation credit, ledger admission, or live-network evidence. Counts remain 45/55 negatives and 18/21 mutations.

Exact commands, tool/source/fixture hashes, output hashes, and exit classifications are in RUN.json and adjacent captures. Aiken SHA-256: 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79. Native test: aiken check --debug --trace-level silent --match-tests "f05_authority_policy.{..}", through the network-isolated bwrap invocation in RUN.json: exit 0, 2/2. R3 commands are recorded in RUN.json.

Independent review PASS for the integrated record. The reviewer verified RUN.json parses and current source, runner, registry, Aiken binary, fixture, and captured-output hashes; independently replayed the R3 valid and invalid-signature cases; and confirmed exact-policy binding, Mint[0] invocation, and clean teardown. The disposable native-test copy was no longer available for byte comparison during review, so the reviewer could not independently confirm its source bytes against the canonical hashes. This provenance limit does not affect the narrower R3 findings; the native 2/2 remains synthetic handler evidence only.

Next single slice: adapt or augment the public mutation harness to use the snapshot-bound R3 runner on the frozen exact-policy fixture, limited to one positive, one existing negative, and target-invocation controls. Test this slice and obtain independent integrated review before expansion. Six applied-parameter cases still require the owner's A/B/C evidence-contract choice; four signature-domain negatives remain pending. Testnet readiness is NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
