# F05.2a applied genesis parameter: decision required — 2026-10-02

## Current-ledger reconciliation - 2026-10-03

No negative case or mutation is accepted from this design review. The previously shown 36/55 negative and 4/21 mutation totals are historical to the 2026-10-02 review and are superseded by the accepted current overlay: **45/55 negative cases PASS (10 pending); 18/21 mutations PASS (3 pending)**. The overlay is `docs/remediation/m3_f05_2a_evidence_classification_r1/CASE-STATUS.json`, SHA-256 `8a571af3c92957ced0dc4d1c17c03776ac6a774d19a8ac20fce10c0fff1e5cc2`. All six applied-parameter variants covered by this decision remain pending; the registry assertions are unchanged.


Independent current-ledger review: PASS for the referenced overlay hash, 45/55 and 18/21 totals, pending counts, and all six listed applied-parameter case IDs. The reviewer could not verify byte-level continuity of the A/B/C wording because this decision file is absent from HEAD and no pre-amendment copy/hash was retained. The current A/B/C paths are substantively consistent with corrected design review r2; wording continuity is unverified. No tests or source checks were rerun for this documentation reconciliation.

The frozen evidence contract marks this as ledger_tx_sim, expects rejection at
compiled target Mint[0], names the original applied policy
9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731, and describes the
mutation as compile_with_different_genesis_ref_keep_transaction. Its alternate
compiled target hash and preservation delta are unset. The original fixture
uses genesis reference aa…aa#7.

Independent read-only design review (corrected): /home/GodOfAgents/vams-evidence/
m3-f05-2a-applied-genesis-design-review-20261002-r2/REVIEW.json
SHA256 a1a0102c87d5414a9a1467a0d847c735ab1ea3f39ea8e0d3187df1544d0d20f4.
The original r1 artifact is superseded. The corrected review confirms a literal
fixed CBOR transaction and original policy ID cannot invoke an alternate
applied policy, while the current harness's direct synthetic UPLC context path
can test that behavior after correct evidence reclassification.

Current harness inspection adds a relevant classification detail. In
scripts/remediation/test_f05_2a_authority_bootstrap_public.py, _run_suite
compiles an applied_* variant and reconstructs a synthetic Plutus ScriptContext
using variant[policy_id] for mint, purpose and the authority NFT. _evaluate
directly invokes compiled UPLC; it is not a CBOR transaction simulator.
Therefore a script-context negative can be meaningful after the evidence
contract is amended and the alternate derived policy ID is recorded, but it does
not satisfy the current ledger_tx_sim classification. The same misclassification
and original-policy-ID claim appear in applied_keys_parameter and
applied_keys_bad_count/bad_length/duplicate/unsorted. A literal fixed transaction
cannot establish alternate-parameter behavior. A full rebound CBOR transaction
would be a different transaction and must update policy mint, NFT values,
script witness and body-bound funding signatures before bounded tx simulation.

Decision required for the parameter-variant case family (genesis plus the five
applied_keys_* cases):
A. Close/reclassify each as applied-identity evidence only. Derive and record
each alternate applied script hash/policy ID, but claim no behavior rejection
and award no negative-case credit.
B. Amend each evidence contract to synthetic compiled UPLC evaluation over a
constructed ScriptContext. Derive each alternate policy ID; accept only
independently reviewed compiled-entrypoint outcomes, classified as synthetic
script-context evidence and not transaction simulation, ledger admission, or
live evidence.
C. Amend each contract and build new synthetic CBOR transactions bound to
each alternate policy. These are not keep_transaction cases; only bounded
simulator evidence can result, never ledger admission or live evidence.

No source, fixture, registry, or contract has been changed. No compilation,
tests, ledger admission, or live-network operation was performed for this
design review. No activation criteria were relaxed. F05/M3 remain open,
Pre-Prod INCONCLUSIVE, promotion NOT READY; deployment, Deposit, Slash
activation, and ExecuteIntent remain disabled. T06/history and the other
mandatory gates remain outstanding.
