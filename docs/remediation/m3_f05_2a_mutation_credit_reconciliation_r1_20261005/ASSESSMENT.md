# F05.2a mutation-credit reconciliation R1

Date: 2026-10-05
Canonical checkout: /home/GodOfAgents/code/VAMS-testnet
HEAD: 829ab544571f12efe50ecb5740f129c8acb3e16f
Scope: read-only evidence-contract reconciliation; no execution or source change

## Decision

The two remaining mutation IDs, `remove_key_uniqueness_order_guard` (paired negative `applied_keys_duplicate`) and `remove_key_order_guard` (paired negative `applied_keys_unsorted`), remain PENDING in the mutation ledger. A separately captured mutation-suite artifact is required before either row can move to PASS.

## Basis

The governing R4.1 amendment requires independently reviewed positive, negative, and mutant-control transactions, while the 21-row mutation ledger is a distinct acceptance surface. Its contract generator records these two rows as `alternate_parameter_mutation` with expected baseline rejection and matching-mutant acceptance, and with mutant policy identity pending isolated compilation. See `docs/remediation/m3_f05_2a_evidence_contract_r4_1_20261005/AMENDMENT.md` and `docs/remediation/m3_f05_2a/tx_sim_evidence_contract_r4_1.json`.

The R5 duplicate and unsorted triads are already independently reviewed as synthetic alternate-applied-policy negative-case attribution. Their paired reviews explicitly mark the one-guard mutant as attribution evidence and `mutation_suite: false`: duplicate triad review SHA-256 `1ee2dc4e2d5cb2bcbf5005068e5ccf96a60f9b70a115b8edafab65ab9630ce86`; unsorted triad review SHA-256 `9f3b58dc98ee5144705db7f4101181904a93166d7d6b3e5730688e922216e54b`. Those artifacts establish the named negative guards but do not satisfy the mutation-ledger executor/classification contract.

The R10 direct-UPLC full capture and review are synthetic context-only. The R10 overlay promotes only `unconditional_success` under `direct_uplc_context_only`; it grants no transaction-simulator or mutation-suite credit. R10 CASE-STATUS SHA-256 `5ef6fb8e4ecb13f175523df42f832e987d6de1689e6d5b5f65940c014b377b56`; independent review SHA-256 `8da682084c7c665b2ed6594685bc364f56bcda176041431d3106b6f3af4527ae`.

## Required next evidence

For one guard at a time, capture a mutation-suite record that identifies the exact baseline and independently rebound mutant policy/script bytes, preserves all 21 IDs and the R4.1 synthetic-only boundary, and passes independent review. It must not be inferred from the existing triads or direct-UPLC context capture. Until that exists, counts remain 19/21 mutations PASS, 2 PENDING; negatives remain 53/55 PASS and transaction-simulator negatives 49/51 PASS. No original-policy, ledger-admission, Cardano Pre-Prod, live-network, or deployment-readiness credit follows.

No production source, fixture registry, credentials, deployment state, or gated activation changed. F05/M3 remains OPEN; readiness is NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
