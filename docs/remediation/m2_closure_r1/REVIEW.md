# M2 closure record

Date: 2026-09-24  
Scope: documentation-only recording of independently accepted M2 results  
Current disposition: `M2R4-01 = REMEDIATED`; `F08 = REMEDIATED`;
`M2 = COMPLETE`; overall promotion readiness = `NOT READY`

## Completed M2 slices

- M2.1: canonical versioned Gateway request-authentication envelope.
- M2.2: durable atomic replay reservation and signer revocation.
- M2.3: closed protected-route classification and real HTTP enforcement.
- M2.4a: fail-closed SQLite replay/revocation schema validation.
- M2.4b-R5: Envoy 1.39.1 live-ingress boundary and trusted semantic request.
- INV-5 traceability-control synchronization.
- Frontend `/nodes` disposition with the route retained as authenticated.
- Mandatory frontend telemetry/security tests and production-bundle scan in CI.
- M2R4-01 closed command-contract enforcement for the four protected frontend
  CI steps.

## Independent evidence chain

| Review | Outcome | Package | `SHA256SUMS` SHA-256 |
| --- | --- | --- | --- |
| M2-R3 | Runtime claims passed; one Medium frontend CI enforcement gap | `/home/GodOfAgents/vams-evidence/m2-r3-review-20260924-829ab544571f` | `f9dc304951a9420dcd967d56861bd5c116185d202a751a8be999526839c797e3` |
| M2-R4 | Authoritative workflow passed; M2R4-01 found in the validator | `/home/GodOfAgents/vams-evidence/m2-r4-delta-review-20260924-829ab544571f` | `f6ba4ad3374e83b8ae5bc7b9f37a00d263ba2e028f6e8468ca509373887b3044` |
| M2-R5 | PASS; M2R4-01 accepted, no material finding, F08/M2 closure recommended | `/home/GodOfAgents/vams-evidence/m2-r5-delta-review-20260924-829ab544571f` | `d9936e1015d72601010266ec57e57a8b1aff35c33ea7ae7f06b27605813a7aba` |

The R5 prerequisite was strictly reverified before this record was edited:
the observed manifest digest matched exactly and all four manifest entries
passed `sha256sum -c`. The R5 package is the acceptance evidence; this slice
creates no runtime evidence. Historical R2/R3/R4 review files remain unchanged
and retain their accurate earlier-state verdicts.

### M2.4b-R4 supersession

The historical M2.4b-R4 `BLOCKED` verdict remains accurate for its earlier
policy requiring rejection of every obsolete-folding representation. It does
not control the current disposition: the reviewed M2.4b-R5 RFC 9112
normalization contract superseded that policy, and the subsequent independent
M2-R3, M2-R4 delta, and M2-R5 delta evidence accepted the resulting runtime and
CI boundary. Accordingly, M2.4b-R4 must not be used to reopen F08 or M2.

## F08 disposition and final CI correction

F08 is `REMEDIATED`. The accepted chain covers request identity, route-policy
completeness, durable restart/worker replay and revocation, strict schema
handling, trusted Envoy ingress, authenticated `/nodes`, and fail-closed
frontend CI enforcement. The final M2R4-01 correction replaced permissive
command-presence recognition with an exact contract for unique install, test,
build, and scan steps: only the reviewed `run` property and exact command body
are allowed, with fixed ordering and no alternate-success shell commands.

## Invariants and mock mode

| Invariant | Closure impact |
| --- | --- |
| INV-1 | Unchanged; no regional-emissions code changed. |
| INV-2 | Unchanged; no insurance-yield code changed. |
| INV-3 | Preserved; session-key behavior is outside this documentation slice. |
| INV-4 | Preserved; contract-whitelist behavior is outside this documentation slice. |
| INV-5 | Preserved; the accepted synchronized CLR/OMS controls remain authoritative. |
| INV-6 | Preserved; TEE root-identity behavior is unchanged. |
| INV-7 | Unchanged; no oracle behavior changed. |
| INV-8 | Unchanged; no supply-cap behavior changed. |
| INV-9 | Unchanged; no reward-solvency behavior changed. |
| INV-10 | Preserved; `bridge_proof` and `payload_hash` remain separate. |

M1 containment and mock-mode behavior are unchanged. F17 and F09 remain
`REMEDIATED`.

## Remaining blockers and next milestone

M2 completion is not overall promotion readiness. VAMS remains `NOT READY` for
testnet promotion, deployment, release, or production. The separate T06/history
issue remains open, and M3-M9 remain open. Per `docs/remediation/PLAN.md`, the
next single milestone is **M3 — Cardano authority and state machines**,
covering F01-F05 under its documented review contract.
