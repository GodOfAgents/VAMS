# M3.2a-R3 ADR remediation review

Date: 2026-09-26
Scope: documentation/design only. No Cardano source, shared types, blueprint,
lockfile, dependency packages, deployment, credentials, vendors or Git history
were changed.

## Input and reproduction

The accepted R2 package was verified before editing:
path /home/GodOfAgents/vams-evidence/m3-2a-r2-review-20260926-829ab544571f
SHA256SUMS digest 9dd4a9729213af10617008d0591fe31aae5fa92124e3ba145098bfc26469b3f5
sha256sum -c SHA256SUMS: all entries OK.

R2 findings were design defects: no authenticated nonce singleton/counters,
missing receipt/refund semantics, contradictory 32-voter/896-byte/16-output
bounds, incomplete lifecycle/F05 boundary, and no public compiled-handler
acceptance matrix.

## Exact remediation

ADR.md now specifies:

- one seed-OutputReference authority genesis, immutable singleton asset quantity
  one, fixed policy_epoch, and reference-input semantics;
- next_proposal_nonce and next_intent_nonce with exact old/new +1 transitions,
  skip/reuse/decrement/overflow rejection and domain-separated policy assets;
- proposal, receipt and intent policy responsibilities with exact redeemer,
  state, mint/burn, datum, value and cardinality checks;
- five-field VoteLockRecordV1, voter-signature and exact-value locking, receipt
  retention, exact credential-bound refunds, and terminal burn/refund behavior;
- exact Create, Vote, Finalize-Passed, Finalize-Rejected, Cancel and Queue paths;
- Queue as governor plus intent policy, not timelock QueueIntent;
- unconditional ExecuteIntent rejection before F05 and deferred successful
  execution to F05/M4;
- fixed bounds of five members, threshold three, eight voters, 16 inputs/outputs
  and assets, 896-byte datums, five-minute validity, 24-hour delay and seven-day
  intent lifetime;
- a public acceptance matrix with unique rejection reasons and mutation IDs.

## Disposable feasibility evidence

A temporary Aiken 1.1.21 model at /tmp/m3-2a-r3-feasibility compiled with:
aiken check /tmp/m3-2a-r3-feasibility -> exit 0
aiken build /tmp/m3-2a-r3-feasibility -> exit 0

The canonical-CBOR model using bounded 64-bit amount/nonce/deadline/tally fields
and bounded 32-bit epoch/quorum/weight fields measured ProposalDatumV1 sizes:
0 records 220 bytes; 1 record 304 bytes; 8 records 892 bytes; 9 records
976 bytes. The maximum Queue topology is 11 outputs (8 refunds, authority
continuation, intent output, change), at most 3 principal inputs and 12
distinct non-ADA assets. Cancel/Finalize-Rejected are at most 2 principal
inputs, 9 outputs and 10 distinct non-ADA assets. All are below the frozen
16-count limits. These are schema/serialization bounds only; they are not
applied-validator size or evaluator-budget evidence.

## Verification

- current pinned provenance verifier with Aiken 1.1.21: exit 0, check_exit 0,
  build_exit 0, ok true;
- documentation validation: passed;
- FINDINGS.json parse: passed;
- recursive submodule status: captured;
- git diff --check: passed;
- continuity source hashes: unchanged during the slice.

## Status and impact

This is local design remediation, not independent acceptance. F01-F05 remain
open; Deposit and Execute remain disabled; M3 is OPEN; Pre-Prod admission is
INCONCLUSIVE; promotion is NOT READY. INV-1 through INV-10, M1/M2 containment,
mock behavior, deployment state and F01 custody logic are unchanged.

The next single slice is independent M3.2a-R4 design-feasibility review.
