# Independent review: F05.2a evidence classification R7

Date: 2026-10-05
Verdict: PASS for the narrow R6-to-R7 evidence-classification amendment.
Scope: Read-only review of R6/R7 status and amendment, frozen source-registry identity, and cited R20/R21/R22 plus integrated triad review. No simulator, tests, or build run. No R6/R7 overlay, STATUS, or HANDOFF edited.

## Comparison and counts

R6 CASE-STATUS.json SHA-256: 419e5c1dfeaa76b346ae739d092d974b853e889fa0b96283a9f09e9155cdc4f5. R7 CASE-STATUS.json SHA-256: a2b95b91ff427585a7275f8f9d970e0dfa8cd22b4d7013d960b1834196e29bee. R6/R7 SHA256SUMS file hashes: 55677f3e3e08427f33aa5bc96d9d6225f836f0669c6201bcc943e2697fb5f089 / ab134d4ead6e20f19c16eaf14a8d0ccd91b716853a7fa075555a296d0840ccac. Both overlay checksum sweeps pass.

Normalized R7-to-R6 comparison (remove the new row, restore it to pending, reverse derived count delta, and ignore schema-version bump) confirms exactly one change: r2_signature_for_other_network moved from pending to pass. The original case ID and assertion sign_tuple_with_another_network_magic are preserved. Source registry path and SHA-256 are unchanged at docs/remediation/m3_f05_2a/authority_bootstrap_public_fixtures.json / 98a05d24d476b1aee2754768322dc4b794e5afb5fabec28ade17a2888285467d; hashing the current registry yields the same value and assertions_changed remains false. All other negative rows are unchanged. The full mutations object is byte-semantically unchanged: total 21, passed 18, pending 3, failed 0. Other top-level fields are unchanged, including inherited evidence_category_clarification metadata; that field is retained as historical metadata, not a new R7 credit rule.

Counts reconcile: 51/55 overall pass, 4 pending, 0 failed. Categories are transaction_simulator 47/51 pass with 4 pending, context_only 3/3 pass, routing_only 1/1 pass. Mutation status remains 18/21, 3 pending, 0 failed.

## Evidence references and boundaries

R7 points to the R20 accepted synthetic positive RUN SHA-256 f83f9efb074e5b7396d395a61154adc8d716b57a3a4193119b46e03d3e531e8a and its independent positive review a86e5fe5594048f9bff65f92a4dcf6f124dfe25063578d1aeeaf21a933f6c6ff; the R21 unmodified-policy negative RUN e31385db7d8c0e0b7ebc4610298813ed66373a59a736109d354db4addc9ec179 and independent integrity review ffa6066975cb41f950a0d6d601e2fe18384c37055ba212ba179243717d97d0fe; and R22 same-negative one-guard mutant RUN 364d859090a4d80549a63bb57b04b0f36d1d89b967cc5707e3dc784c79315eaa, pre-execution review 1d92f77fcd16b90c19ebb1330f46aa7175eea84b74e635f89120b7a0cf07b6f7, plus integrated triad review df63119b2896ee637d2c7bfff8fe99c0204763643f4170bbf0e7f8ef4b478895. The cited R20/R21/R22 RUN and review SHA-256 values match the exact files. The triad review SHA256SUMS check passes.

The integrated review supports exactly this one synthetic transaction_simulator negative row under R4.1 choice B. R22 is attribution evidence only, not a mutation-suite result. The amendment expressly grants no original-policy, full-ledger-admission, Cardano Pre-Prod, live-network, or readiness credit. F05/M3 remains open; deployment and gated activations remain disabled. This review makes no broader readiness claim.

## Read-only verification

- sha256sum -c SHA256SUMS in R6 and R7 overlay directories: all listed files verified OK.
- Python stdlib JSON comparison normalized R7 to R6; equality holds for every field after the single target-row move and expected derived-count changes.
- sha256sum on cited R20/R21/R22 RUN/review files matches the exact R7 support references.
- sha256sum -c SHA256SUMS in integrated triad review directory: INDEPENDENT-REVIEW.md OK.

No simulator, test, build, or network command was run.
