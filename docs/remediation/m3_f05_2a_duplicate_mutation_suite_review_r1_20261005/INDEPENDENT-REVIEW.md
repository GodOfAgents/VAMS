# Independent review: PASS

Date: 2026-10-05
Bundle: `_duplicate_mutation_review_bundle_20261005`
Case: `applied_keys_duplicate`
Entrypoint: `f05_authority_policy.f05_authority_policy.mint / Mint[0]`

## Review basis

This is a byte and metadata review of the isolated bundle. No transaction
simulation was executed and no canonical repository file was modified.

The following integrity checks passed before this review was written:

- Every entry in `BUNDLE.SHA256SUMS` matched its bundled file.
- `SHA256SUMS` matched `RUN.json`.
- `prior_review/SHA256SUMS` matched `prior_review/INDEPENDENT-REVIEW.md`.
- `SCRIPT.SHA256SUMS` matched the bundled `capture_script.py` digest recorded
  by `BUNDLE.SHA256SUMS`. The historical source path named by that file is not
  present in this checkout, so source checkout provenance was not re-resolved.

The captured script uses the historical repository layout to resolve its
fixture family and runner paths. Because those dependencies and the source
fixture files are not part of this isolated bundle, the script was reviewed as
captured provenance and was not replayed here.

## Required control and mutation evidence

The hash-verified `RUN.json` records all three expected Mint[0] outcomes:

| Run | Recorded stage | Result |
| --- | --- | --- |
| `positive_control` | `script_accepted` | PASS |
| `original_negative` | `compiled_evaluation` | PASS |
| `matching_mutant` | `script_accepted` | PASS |

For every run, `target_script_invoked` is true, the wrapper exit is zero, and
cleanup is `clean` with the child reaped, process group empty, and snapshot
descriptors closed. For each run, the manifest policy ID equals
`expected_policy_id`, `compiled_script_hash`, and the sole submitted
`policy_ids[0]`. Submitted transaction, input, and output hashes also match
the corresponding manifest artifacts.

The manifest validation metadata for every run records two valid body-bound
ephemeral funding signatures, `valid_body_bound_ephemeral_signatures: true`,
ADA and native-asset conservation as true, and
`private_keys_persisted: false`.

## Scope and credit classification

`mutation_suite` is true and the mutation is scoped to
`remove_key_uniqueness_order_guard` for the synthetic alternate-applied-policy
transaction-simulator capture. The bundle claims no original-policy credit,
negative-case credit, ledger-admission credit, Cardano pre-prod credit,
live-network credit, or deployment-readiness credit. The manifest independently
records the same no-credit scope.

The classification remains `pending independent review and classification
overlay`. This PASS records control and attribution evidence only; it does not
promote the case to original-policy, ledger, live-network, or deployment
evidence.

## Decision

**PASS** — all requested bundle integrity, control-stage, binding, cleanup,
signature, conservation, key-persistence, scope, and credit checks passed from
the supplied byte-verified records. No simulation was rerun.
