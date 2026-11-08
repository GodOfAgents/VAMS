# F05.2a evidence-contract amendment R4 - 2026-10-05

Status: owner-authorized amendment; independent review is required before fixture generation or execution.

The owner selected C for all six applied-parameter cases and B for all four proof-domain cases. R4 pins the frozen R1/R2/R3/R3.1 contracts and accepted registry by SHA-256, embeds every complete original R2 row, and preserves every case ID, assertion, verifier property, expected rejection, and target reference.

For choice C, build a new synthetic CBOR transaction rebound to each alternate applied Plutus V3 policy. The prior keep-transaction construction does not apply. For choice B, use test-only parameter-bound synthetic CBOR and ephemeral test keys only. Derive and record exact parameters, compiled bytes/hash, policy ID, transaction/raw vectors, witness binding, funding signatures, and value conservation.

Before simulator execution, an independent reviewer must verify exact fixture bytes and bindings. Each case requires an accepted positive control. Rejection must invoke the compiled Mint[0] entrypoint and be attributable to the preserved named condition. Use a condition-isolated compiled mutant or equivalent independently reviewed entrypoint evidence; if attribution is not established, retain PENDING.

Funding witnesses must verify against the final transaction body hash and use ephemeral test keys only. Never access original committee or wallet credentials. Preserve value and native-asset conservation, including fees, collateral, and change.

R4 grants no evidence for original applied policy 9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731, full ledger admission, or live behavior. No credit is awarded now. Accepted totals remain 45/55 negatives and 18/21 mutations. All ten rows remain PENDING; F05/M3 remain open; readiness is NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Contract: docs/remediation/m3_f05_2a/tx_sim_evidence_contract_r4.json.
