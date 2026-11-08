# M6 Heart-Brain/GCA compatibility envelope proposal (r2)

Status: **design-only, non-authoritative; not implemented, integrated, or activated**  
Date: 2026-10-04 · Schema: `vams.m6.gca-envelope.v1` · Readiness: **NOT READY**

## Purpose and non-authority

This envelope carries claims about a proposed decision, execution context, exact logical action, and later output/effect/settlement evidence. It is not an authority, policy evaluator, signature, proof verifier, permission, payment instruction, ethical-alignment proof, or release artifact. `ALLOW` is a claim, not a capability. JSON fields and source digests do not authenticate themselves. A future verifier must independently authenticate every required field against its approved source, recompute its value digest, enforce current policy and authority at every effect boundary, and deny on missing, unknown, stale, malformed, inconsistent, or unsupported input.

All references and source references are opaque. This proposal selects no source, trust root, identity, key, provider, model, circuit, host, chain, domain, verifier, policy value, F04/F05 authority, threshold, budget amount/unit meaning, or deployment setting. No code consumes this schema. Do not wire it to any effect path.

## Reconciliation to the conceptual Heart-Brain documents

`docs/team/Heart_Brain.md` labels Heart-Brain conceptual research architecture, but describes GCA as a constitutional vector, pre-execution refusal, CSP synchronization, Sentinel metrics, DAO updates, and ZK settlement. The referenced research report (`docs/team/heart_brain_research.md`, “Heart Brain Architecture — Component Map” and “Implementability Assessment”) says GCA and Planetary Constitution Vector are not implemented; vector initialization lacks a corpus; ZK-wargaming lacks a circuit framework; the named internal regulatory components do not establish GCA enforcement. The report also warns against inflated paper scope and identifies ethical-vector quantification as research work.

**Design deltas:** this interface models exact, auditable claims and deny-before-effect controls only. It does not represent “human good,” a Planetary Constitution Vector, Mahalanobis score, conscience interrupt, universal alignment, military classification, DAO authority, or automatic slashing as implemented truth. Model/circuit identity and any score can be carried only as source-bound claims; uncalibrated metrics remain telemetry and cannot authorize. Malicious memory/service output cannot mutate policy, authority, nonce, source map, or evidence root. A restricted infrastructure control does not claim completion of the research GCA.

## Version 1 required bindings

See [envelope.schema.json](envelope.schema.json), JSON Schema 2020-12. The root binds: actor root; provider/runtime/model/circuit identity; host/chain/domain; authority epoch; workflow definition; stable logical intent; canonical action/input commitments; permitted capabilities and bounded budget; policy root/version; anchor freshness/finality; claimed `ALLOW`/`DENY`/`UNKNOWN`; explicit replay nonce and expiry; output commitment; and effect/settlement receipts.

The required `source_bindings` map has exactly one entry for each required path. Each entry contains an opaque `source_ref`, `source_digest`, and `value_digest`. The `anchor_record` value digest covers the complete tuple `(anchor.ref, anchor.digest, anchor.checkpoint_ref, anchor.observed_at, anchor.fresh_until, anchor.finality_claim)`; separate freshness/finality entries do not replace this identity binding. The `action_commitment` value digest covers target, operation, canonical action and input commitments. Evidence class, artifact identity, review class, effect status, and readback each receive their own source-map entry. Validity issuance time and expiry are independently source-bound as `issued_at` and `expiry`; neither digest stands in for the other. A future semantic verifier must ensure map completeness/uniqueness, resolve the actual approved source, authenticate its provenance/freshness, recompute the source and value digests, and confirm the claim agrees. A map entry is still only an envelope claim until this occurs. No source is selected here. Schema-valid means syntax-valid only.

Action/input commitments use a proposed versioned canonicalization profile and separate digest domains; cross-language vectors for Rust, Python, Solidity, and Aiken remain required before any boundary is enabled. Stable logical intent is distinct from transport nonce and operation/idempotency UUID. Retries of one logical intent must preserve the exact action/input commitments and operation identity; changed payload under reused identity is a conflict.

Anchor freshness and finality are explicit claims with observation time; a future verifier compares them to approved chain/source semantics and trusted current time. `UNKNOWN` never falls back to ALLOW. Policy root/version and authority epoch are re-resolved immediately before each effect; a restart, model/runtime/workflow/policy update, epoch change, anchor change, or expiry invalidates pending approval unless the approved durable authority source explicitly authorizes continuity. Source outage or ambiguity denies before effect.

Output commitment, effect receipt, and settlement receipt are separate fields and separately source-bound. No receipt is not represented as a successful empty receipt. After a dispatch timeout, mark outcome indeterminate and reconcile the same logical intent/operation; never retry under a fresh identity to hide uncertainty. Independent read-back and side-effect observation require an operationally separate observer, not another function on the submitting adapter.

The schema cannot enforce authenticity, source freshness, route parity, ordering, atomicity, replay across workers, independent observation, or zero effect. Do not treat an error response or unpaid transaction as proof of no effect.

## Required route gates and zero-effect evidence

The eventual implementation must enforce the same deny/unknown outcome at all three route layers: (1) composer/UI admission before credentials or signing/tool effects are released; (2) direct Executor entry, including a route that bypasses composer/UI; and (3) direct settlement/payment entry, including API-only or proof-valid-but-wrong-job/root/model/domain attempts. No route is trusted because an earlier UI/composer check ran. At each route, a denied/unknown case must be independently observed to produce **zero protected effects** (no credential release, signing, tool/provider write, transaction, transfer, or settlement). Bounded diagnostics and explicitly authorized recovery remain permissible and are not counted as protected effects.

## Threat analysis and targeted test matrix (proposed; NOT RUN)

| ID | Threat / case | Expected check and evidence |
|---|---|---|
| S01 | Omit/change any mandatory field or source-map path | Schema/semantic reject; exact field map is complete and unique |
| S02 | Source ref absent, unauthenticated, stale, forged, wrong type, or digest mismatch | UNKNOWN/DENY before effect; verify source and value digest independently, including every required map path |
| S03 | Wrong actor root, job/workflow, provider, runtime, model, circuit, host, chain or domain | Proof/action rejected before payment; zero-effect observer record |
| S04 | Valid key but decision is DENY/UNKNOWN or policy anchor missing/stale | Hard gate prevents credential/signature/tool release; explicit UNKNOWN/DENY |
| S05 | Route 1: composer/UI denies, including bad anchor/root/domain | No credential release/signing/tool/provider/settlement effect; independent count is zero |
| S06 | Route 2: direct Executor call bypasses composer/UI | Executor independently applies identical policy; independent protected-effect count is zero |
| S07 | Route 3: direct settlement/API call bypasses UI/composer/Executor | Settlement independently verifies same policy and exact job/root/model/domain; transfer count zero |
| S08 | Action/input changed while reusing stable intent, operation ID, or nonce | Commitment mismatch/conflict; no second effect |
| S09 | Replay, duplicate nonce, expiry equality, future issue time, clock skew/rollback, or altered issued_at source | Reject or UNKNOWN; no effect; issued_at and expiry are independently source-bound; durable replay survives restart |
| S10 | Restart after approval but before effect | Recheck expiry/revocation/current source; stale generation cannot authorize silently |
| S11 | Policy update with pending work | Explicit revoke/grandfather/re-evaluate semantics from later approved policy; no old-policy replay |
| S12 | Crash after provider effect before checkpoint/receipt | Same-intent reconciliation prevents duplicate effect/payment; ambiguity stays UNKNOWN |
| S13 | Output/effect/settlement receipt missing, forged, stale, conflicting, or wrong-domain | Reject success claim; no settlement |
| S14 | Anchor claims fresh/final but source proof is absent, stale, substituted, or not final | Recompute the complete anchor-record tuple digest; UNKNOWN/DENY before effect |
| S15 | Capability widening, budget exceeded/raced, invalid numeric value, NaN/Inf/wrong dimensions | Reject; budgets use bounded integers; anomaly metrics remain telemetry-only |
| S16 | API-only model or missing activation proof | State restricted capability/evidence alternative; never fabricate activation proof |
| S17 | Malicious memory/tool/service result mutates policy, nonce, source map, or evidence root | Immutable protocol state rejects mutation; zero protected effect |
| S18 | Economic rejection/refund path | Economic rejection cannot replace pre-effect gate; only authorized bounded refund/recovery |
| S19 | Synthetic/local artifact relabeled ledger/testnet/live or review class upgraded | Evidence pipeline rejects promotion absent source-bound class, artifact, review record, accepted provenance, and independent review |
| S20 | Unknown schema version/field, duplicate JSON key, canonicalization disagreement | Reject before evaluation; cross-language vectors agree byte-for-byte |
| S21 | Attempt to use envelope as exception to INV-1..INV-10 | Existing authoritative controls remain in force |
| S22 | Secret/PII/raw payload inserted into source map/log | Reject or redact; retain only approved refs/digests |
| S23 | Substitute anchor ref, digest, or checkpoint while freshness/finality fields remain unchanged | Composite anchor-record value digest changes; deny before effect |
| S24 | Change evidence class, artifact ref/digest, review class, effect status, or readback claim without changing source map | Source-map mismatch; reject claim and do not promote evidence |
| S25 | Change validity.issued_at or validity.expires_at while retaining the other timestamp source binding | Source-map mismatch; reject future-issue, skew, or expiry claims before effect |

Every negative route test must assert zero effects through an independent observer/ledger, not infer it from an exception or unpaid transaction. For live claims the observer must have suitable operational separation from the submitter. Cross-language vectors are required for all enabled Rust/Python/Solidity/Aiken boundaries. This matrix is a design contract, not executed evidence.

## Invariant impact

No source or enforcement changes here; INV-1..INV-10 are **not modified or proven**. Later implementation: INV-1 emissions <=30% cannot be overridden by per-action budget; INV-2 yield <=30% remains contract-enforced; INV-3 session expiry <=24h cannot be extended; INV-4 target refs cannot widen session-key contract allowlists; INV-5 opaque actor claims are not OMS identity and offline fails closed; INV-6 TEE evidence must bind root EOA, not session key; INV-7 freshness fallback cannot be suppressed; INV-8 supply <=1 x 10^9 cannot be changed; INV-9 pending rewards remain fully backed; INV-10 bridge proof and payload hashes keep separate fields/domains.

## Open decisions and state

- **F04:** owner decision and reviewed design for canonical identity-policy anchor/trust root, provenance and migration.
- **F05:** owner dispositions for pending applied-parameter/proof-domain evidence and associated authority rules.
- **M4:** approved TEE/ZK verifier/circuit, public-input domain, code/activation identity, vector formats, settlement/fee/refund semantics.
- **M5:** provider/DA, runtime/model/circuit source identities; host/chain/domain source authorities; independent observer; durable nonce/epoch store; retry/recovery and budget semantics.
- **M6:** source-selection/governance for each binding; meaning/versioning of decision/workflow/capability fields; anchor freshness/finality policy; trustable runtime generation; privacy/retention; route owners and migration.
- No implementation, source integration, executable tests, activation, ledger admission, or live-network evidence is produced. **NOT READY**; deployment, Deposit, Slash activation, ExecuteIntent remain disabled.
