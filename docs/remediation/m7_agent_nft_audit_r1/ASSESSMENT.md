# F04 identity-path audit - 2026-10-03

Status: implementation blocked on the normative identity-entrypoint decision. This is a source and evidence reconciliation only; no source, fixture, evaluator, blueprint, dependency, credential, or deployment state changed.

## Current source and evidence

Current SHA-256 values:

- `cardano/validators/agent_nft.ak`: `7653cd2a9db99a69424f79164c123ce35d274db75f25f74e0a9f4c4c9b9d36bd`.
- `cardano/validators/agent_registry.ak`: `7655acb5d48cb0abcfe85dadfe9aa9c80046bff3aeeaf0720cb706084adbb5cd`.
- Frozen `docs/remediation/m3_f04_design_r1/IDENTITY_SPEC.json`: `eaabb61ef8a4f454ab7bb2f138ea67a767f3effdff917fc95520be7de9c90c80`.
- Accepted `docs/remediation/m3_f04_closure_r1/REVIEW.md`: `838975109145e7fb12e87c9132a5af6428da9d30d350d6c448d3c4a4bf436fa7`.

The frozen identity spec labels itself `design-frozen-not-implemented` and defines the identity policy as the hash of applied `agent_nft` using the consumed bootstrap `OutputReference`. The accepted R6 closure is explicitly bounded to the Option-B `agent_registry` implementation and describes that registry mint/spend path as the implemented identity contract. The current standalone `agent_nft` mint handler returns `False` for every redeemer; its `else` branch fails. The registry validator has the active `MintIdentity` mint checks and the spend state machine. The old design spec has not been amended to record a superseding normative decision or retirement of the standalone policy.

## Fresh current-evidence check

Exact command:

`PYTHONDONTWRITEBYTECODE=1 python3 scripts/remediation/test_f04_public_validator.py --aiken /home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/unpacked/aiken-x86_64-unknown-linux-musl/aiken --output docs/remediation/m7_agent_nft_audit_r1/f04-current-results.json`

Result: exit 0; 49 fixture rows executed, 67 compiled evaluations, zero pending, zero failed rows. The current run covers `agent_registry.mint` and `agent_registry.spend` only (18 mint and 49 spend evaluations). Applied registry policy ID: `fc12374cec6b4aa60b7bfae27528101c5c5f8251ac1338e0dccd2a76`; current applied program SHA-256 `14a1e93902d8851c476feeb25e089c9b3a201e20793216c89970d24a9ce2b75d`; unapplied program SHA-256 `c5d4ab792f530756283a8ffde9d389f6ff7ed2e87a82112d56480fe0127b4a8f`. Result JSON SHA-256: `49ff0bb445bce698a2758bccce09d067c2783d85df78461d7da8f3440cc7ddc9`.

This is local synthetic compiled-validator evaluation, not ledger admission, transaction confirmation, or live-network evidence. It does not validate the standalone `agent_nft` mint entrypoint and does not change F04 closure scope by itself.

## Independent review

Read-only review by `/root/f05_status_reconciliation`: PASS for the curated audit packet; all 14 packet hashes matched. The reviewer confirmed that accepted R6 evidence uses `agent_registry.agent_registry.mint`, while the frozen identity spec names standalone `agent_nft.agent_nft.mint`, and that the current F04 evaluator tests the registry path. The reviewer did not change source. This is a reconciliation review, not an independent rerun of the Aiken evaluations.

## Smallest required owner decision

Choose one normative path before source remediation:

- **A. Registry path is normative:** authorize reconciliation of the frozen spec and F04 records to identify `agent_registry.agent_registry.mint` as the accepted identity policy and record standalone `agent_nft` as retired and fail-closed; or
- **B. Standalone policy remains normative:** reaffirm `agent_nft.agent_nft.mint` as required and authorize a separately scoped compatible implementation/migration with linked tests and review.

Until that choice is recorded, preserve both source paths and do not claim that the frozen identity spec is implemented. No applied policy ID or F04 count is being transferred between the two entrypoints.

## Roadmap and readiness

F04 closure record remains REMEDIATED only for its accepted bounded Option-B registry scope; this audit identifies a normative-document mismatch requiring owner resolution and does not silently reopen or broaden that accepted evidence. F01-F03 and F05 remain open; M3 remains open. F05 remains 45/55 negative cases and 18/21 mutations, with the signature-domain and six applied-parameter owner decisions unresolved. G1 remains failed (7 warnings after the accepted governance-policy cleanup). INV-1 through INV-10 revalidation, mock containment, provenance/reproducible builds, security/dependency checks, privileged-role controls, Cardano Pre-Prod and Polygon Amoy prerequisites, and T06/history remain unresolved. Readiness is NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Next single slice after the owner decision: update only the normative F04 identity records and corresponding acceptance evidence for the selected path; then independently review the exact integrated records before resuming validator remediation. No deployment action is authorized here.
