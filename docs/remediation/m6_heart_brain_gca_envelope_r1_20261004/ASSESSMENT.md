# M6 Heart-Brain/GCA envelope design assessment (r2)

Date: 2026-10-04  
Disposition: **ACCEPTED DESIGN ONLY**  
Readiness: **NOT READY**

## Scope

This slice specifies a versioned, non-authoritative GCA decision/effect envelope. It does not select any F04/F05 authority, trust root, identity, key, provider, model, circuit, host, chain, domain, verifier, policy value, budget meaning, or deployment setting. No runtime or effect path consumes the schema.

The final package contains the proposal, JSON Schema 2020-12, and a reproducible schema-only checker. It includes 25 proposed cases covering mandatory claim bindings, source binding, route parity, zero-effect observation, replay, restart/update invalidation, evidence classification, privacy, and INV-1  –INV-10. Those cases are proposed, not run.

## Verification

Exact command:

`python3 -B /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m6_heart_brain_gca_envelope_r1_20261004/validate_schema.py`

Result: exit 0. Draft 2020-12 meta-validation passed; a synthetic complete 33-path envelope passed shape validation; missing source binding, malformed nonce, and unknown-field cases were rejected. The checker explicitly makes no claim about authentication or effect behavior.

Repository check: `git diff --check`   — exit 0.

Independent red-team review: **PASS** for the exact hashes listed in `REVIEW.md`. The review confirmed the complete source-binding map, including the complete anchor tuple, separate issued_at/expiry, evidence class/artifact/review status, effect status and readback. It confirmed that authority choices remain open and the design does not claim enforcement or readiness.

## Invariant and evidence impact

No enforcement source or contract changed. INV-1 through INV-10 are not modified or proven. The design carries constraints for each and preserves bridge proof/payload separation.

The schema exercise is synthetic syntax evidence only. It is not an authorization test, effect test, ledger-admission test, chain rehearsal, or live-network observation. No F05 count changes. F05 remains 45/55 negative cases and 18/21 mutations. F04 canonical policy anchoring/registration binding remains unresolved. Overall readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

## Residual design-to-implementation work

Before implementation, owners must resolve the listed trust/source choices and route ownership. Future implementation must authenticate every field to its approved source and prove identical DENY/UNKNOWN enforcement at composer/UI, direct Executor, and direct settlement routes with an independent zero-effect observer. Cross-language vectors and durable replay/recovery tests remain required.

The reviewer recorded a non-blocking implementation hardening note: bound `capabilities.permitted_refs` and total envelope size at all three routes. The schema design does not establish those runtime limits.
