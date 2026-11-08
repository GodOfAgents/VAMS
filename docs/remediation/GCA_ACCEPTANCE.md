# Heart-Brain/GCA compatibility acceptance

This is a proposed implementation/test contract. It is not a universal moral-alignment claim. Reconcile with docs/team/Heart_Brain.md and heart_brain_research.md and document design deltas.

## Mandatory bindings

One canonical versioned envelope must bind actor root, provider/runtime/model/circuit identity, host/chain/domain, authority epoch, workflow definition, stable logical intent, canonical action/input commitment, permitted capabilities/budget, policy root/version, anchor freshness/finality, decision ALLOW/DENY/UNKNOWN, nonce/expiry, output commitment and effect/settlement receipt. Bind each field to its actual authenticated source; JSON fields alone do not prove it. Publish Rust/Python/Solidity/Aiken cross-language vectors for the enabled boundaries.

## Required negative cases

| Case | Expected result |
|---|---|
| Missing/stale/forged policy anchor | No new protected effect; explicit UNKNOWN or DENY; bounded diagnostics/recovery remain permitted. |
| Handler uses valid keys for denied action | Hard capability gate rejects before credentials/signing/tool effects are released. |
| Direct route bypasses composer or UI | Executor and settlement enforce the same policy; no trusted route bypass. |
| Proof valid for another job/root/model/domain | Verification and payment reject. |
| Restart after approval, before effect | Current expiry/revocation policy is rechecked; old approval cannot silently authorize a new action. |
| Crash after effect, before checkpoint | Reconciliation prevents duplicate effect/payment. |
| Policy update with pending work | Explicit revoke/grandfather/re-evaluate semantics; no old-policy replay. |
| Missing activations or API-only model | Stated alternative evidence/restricted capabilities, not fabricated activation proof. |
| NaN/Inf/wrong dimensions/uncalibrated metric | Rejection or non-authoritative uncertainty; no automatic constitutional pass. |
| Malicious memory or service output | Cannot mutate protocol policy, authorization, nonces or evidence roots. |
| Economic rejection | Does not replace pre-effect enforcement; preserve authorized refund/recovery. |

For DENY/UNKNOWN tests, assert the effect count is zero using an observer, not just an error or unpaid transaction. For actual live claims, the observer must have appropriate operational separation from the submitter, not merely be a second function on the same adapter.

## Modularity and memory boundary

Protocol-owned memory engineering is expressed through verifiable memory/state interfaces; the protocol mandates the safety boundary, not one memory algorithm or storage layout. Hybrid, vector, graph, episodic, semantic, and other Service Block implementations remain interchangeable. When a named implementation is selected, retain its implementation parameters, thresholds, and corresponding tests.

Mandatory durable protocol safety state includes authority, policy versions, nonces, obligations, evidence, and settlement receipts. Memory records and artifacts must retain the context/provenance references needed to recover policy inputs and verify lineage, source trust class, derivation/taint lineage, freshness and state-version references, write authority, and applicable retention/revocation data. Do not require raw private memory or personal provenance on-chain; any commitments require privacy review. Integrity and provenance checks establish that bytes and declared lineage match their commitments; they do not establish source truth, semantic correctness, or alignment.

Capability-preservation evidence for an implementation must show that relevant context and provenance remain available to policy decisions; policy versions remain available and continuous across tasks, restarts, and updates, or stale approvals are rejected; recovery preserves pending obligations and effect/settlement accounting; taint survives summaries and derived artifacts; revocation invalidates known dependent state and clean replay uses an authorized checkpoint; and memory records, summaries, or service output cannot escalate authority or bypass pre-effect enforcement. Conformance evidence need not expose a provider's internal algorithm.

These criteria do not claim equal model reasoning, global DID uniqueness, completed GCA, universal alignment, or deletion from maliciously exported copies. GCA enforcement claims still require the stronger end-to-end evidence above and the other mandatory envelope bindings.

## Research versus release labels

It is useful to implement a narrow deterministic, governed internal safety policy for testing the enforcement interface, but name that policy and its limits. Do not call it the completed Planetary Constitution Vector. Statistical anomaly detection is supporting telemetry until supported by held-out calibration. A proof that a computation ran is not proof that the policy captures every ethical meaning or that all external facts were true.

A restricted infrastructure milestone can be useful without a full research GCA. The selected dual-host release still needs sound custody/authority and all declared safety controls. Any weaker claim or narrower scope must be explicit and reviewed.
