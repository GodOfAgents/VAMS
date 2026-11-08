# VAMS Research Watch: Implementable Research Consolidation

**Reporting window requested:** September 4-October 2, 2026  
**Prepared:** October 2, 2026; updated October 5, 2026  
**Requested update:** Four research items dated September 29-October 4, 2026  
**Target architecture:** VAMS v0.4.0 through v0.8.0; proposed follow-on hardening, not a declaration of a new release  
**Artifact:** `research_report.md`  
**Status:** Proposed engineering backlog. Implementation status is unassessed.  
**Coverage:** Original 18 Research Watch entries: 58 work items (27 P0, 20 P1, 11 P2). This update adds four requested packages, RW-059-RW-062, for **62 total: 29 P0, 21 P1, 11 P2, and one P0/P1 package**. The mixed package is counted once.

## Executive decision

The implementable result of this research period is **a set of explicit, testable contracts around authority, effects, durability, evidence, and infrastructure adapters**. It is not a recommendation to add another consensus layer or to adopt every paper, draft, vendor platform, or bridge mentioned in the reports.

The first implementation slice should make **one real Service Block operation** safe end to end: resolve its exact identity and implementation; bind approval to the exact action; derive current, bounded authority; reserve budget; enforce policy at the effect boundary; reconcile provider outcomes; and retain evidence outside the agent's control. Extend that verified pattern to other enabled capabilities rather than implementing isolated subsystems for every work item.

The most consequential design distinction is: **agent continuity is durable; permission is bounded and revocable; external effects depend on provider contracts; evidence proves only its explicitly stated property.** A restarted agent must preserve obligations without reviving stale authority. A valid signature, TEE quote, proof, log, or DA commitment must not acquire stronger meaning than its actual guarantee.

### Priority interpretation

| Priority | Importance and relevance | Required treatment |
|---|---|---|
| **P0 - critical** | Directly relevant to preventing unauthorized effects, duplicate spending, invalid state transitions, misleading security claims, or unauditable operation. | A release blocker **for the capability that is enabled or claimed**. Build or verify the minimum control and its negative tests first. |
| **P1 - high** | Material improvement to modularity, recoverability, qualification, privacy, routing, or operating assurance. | Plan after the minimum P0 path, or bring forward when a deployment explicitly requires the stronger property. |
| **P2 - research / optional** | Implementable as a bounded prototype, but dependent on unverified research, immature integration, specialized hardware, or unresolved cost/security tradeoffs. | Run an isolated experiment with an adoption criterion. Do not make it a universal protocol dependency or a baseline testnet blocker. |

**Conditionality matters:** a TEE, ZKML, cross-chain, or DA control is P0 when that route is enabled or its guarantee is advertised. VAMS does not have to build every such route to complete an internal testnet. An unsupported route should stay explicitly disabled and fail closed. P0 priority is not a claim that an item is currently missing from the repository.

### Provenance and confidence boundary

This document consolidates the recommendations in the **current conversation**, not a fresh literature review or repository audit. The earlier reports contain research titles, links, benchmark claims, incident descriptions, and assertions about VAMS main. Those assertions and citations have **not been independently revalidated for this consolidation**. Earlier claims that the repository was read or that a component is deployed, qualified, or incomplete are not accepted here as evidence of present implementation status.

The source appendix preserves **96 distinct research/source leads** exactly as identifiable from the reports, with readable source IDs. Dates, titles, and publication types are **as reported in the chat**. Visible URLs are copied as leads, not certified bibliographic references. No missing URL or opaque earlier citation has been reconstructed. Benchmark percentages, incident loss totals, product launch claims, and quantum-hardware timelines are deliberately not used as engineering acceptance criteria.

Source references such as [S074](#s074) mean **the recommendation was motivated by that source as described in the conversation**; they do not certify that the source exists, was accurately summarized, or has been reproduced. Before adopting a particular algorithm, library, cryptosuite, standard profile, or vendor dependency, verify the primary source and implementation independently. The generic control requirements can be evaluated directly against VAMS's threat model and code.

The reporting window is not the publication window: older work was included when the reports described it as newly relevant. R01-R18 are chronological entry labels created for this consolidation, not fabricated chat timestamps.

**October 5 update verification boundary.** The original consolidation and S001-S096 retain their original unverified status. The four added items are reviewed separately in [Section 3.7](#research-update), with a scoped source record in [Section 8.4](#update-sources). AACP is work in progress, not an adopted standard; published findings and proposed VAMS changes are distinguished. The NEAR incident post was located but could not be retrieved directly; its relayed narrative is explicitly marked as reported. No VAMS repository status or upstream experiment is certified by this update.

## Navigation

- [1. Architecture boundaries and implementation rules](#boundaries)
- [2. Priority index](#priority-index)
- [3. Detailed implementation backlog](#backlog)
- [3.7 Requested four-item update and priority table](#research-update)
- [4. Shared schema families](#schema-families)
- [5. Acceptance suites and conditional release gates](#acceptance)
- [6. Recommended implementation sequence](#sequence)
- [7. Deferred claims and non-goals](#non-goals)
- [8. Research/source traceability](#sources)
- [8.4 Primary references and verification record for this update](#update-sources)

<a id="boundaries"></a>
## 1. Architecture boundaries and implementation rules

### 1.1 Preserve the VAMS design intent

Use the organizing rule already established in the discussion: **Heart constrains; Brain composes; Service Blocks implement; Sentinel verifies; Agentic Economy coordinates incentives.** The proposed work refines these boundaries; it does not move arbitrary model behavior or memory engineering into protocol consensus.

| Boundary | Preserve | Make explicit through this backlog |
|---|---|---|
| Heart / authority | Principal- and domain-controlled policy; replaceable cognition. | Delegation attenuation, current-policy checks, bounded credentials, spend limits, and owner-scoped revocation. |
| Brain / Composer | Freedom to plan and choose modular services. | A proposal cannot grant authority, change policy, approve itself, or silently substitute an implementation. |
| Service Blocks | Heterogeneous implementations, runtimes, memory designs, and providers. | Versioned interfaces, effect contracts, capability boundaries, qualification, and declared assurance. |
| Neuron / durability | Recoverable identity, obligations, state, and workflow progress. | External-effect uncertainty, checkpoint lineage, model/runtime handoff, and capability re-derivation. |
| Sentinel / evidence | Independent analysis and verification. | Evidence provenance, collection outside the subject's authority, explicit uncertainty, and no unsupported semantic slashing. |
| VDSO / cross-domain state | One authoritative state-transition history per declared state domain. | Finality, epoch/fencing, semantic adapters, source predicates, replay rules, and separate execution/settlement. |
| Memory services | AI engineers remain free to build different memory systems. | Provenance, freshness, ownership, revocation, and allowed-use contracts; protocol safety state is not cognitive memory. |
| Agentic Economy | Provider choice and payment for explicitly agreed services. | Clear pricing basis, bounded exposure, evidence requirements, and independence-aware verification. |

**One authoritative writer is a logical authority/serialization invariant, not a demand for one physical machine, one human controller, one cloud, or one global trust root.** Replication and decentralized consensus can implement one accepted state history. Resolver choice, key custody, policy authorities, and quarantine remain scoped to the relevant sovereign principal/domain.

### 1.2 Treat the version comparison as a design mapping

The reports frame v0.4 around modular Service Blocks, Composer, and Sentinel, and frame v0.8 around typed evidence, capabilities, authority epochs, fencing, and separated settlement. This document uses that framing to identify refinements. It does **not** establish a source-verified historical diff between repository versions.

| Starting abstraction in the discussion | Required refinement |
|---|---|
| A registered or selected Service Block | A resolved, version-pinned, qualified implementation with an explicit effect contract. |
| A durable or immortal agent | Durable obligations and accepted state; bounded, re-derived authority; safe treatment of uncertain external effects. |
| A verified action | Separate authorization, enforcement, execution, observed effect, and settlement evidence. |
| A trusted TEE or ZK wrapper | A statement-specific assurance profile with exact workload/numerical/coverage/trust assumptions. |
| Cross-chain communication | Typed source semantics, finality, current authority, bounded effects, and untrusted transport. |
| A DA receipt | Evidence of the particular publication/retrieval/sampling/retention property actually checked. |
| Multi-agent agreement | Evidence sources evaluated for independence, correlation, and incentive alignment. |

### 1.3 Implementation constraints

**Extend existing primitives before adding new ones.** The names in this report are conceptual interfaces, not assertions that matching files/contracts exist. Several can be fields or profiles of one current record. First inspect the repository and map each work item to existing code, tests, ADRs, and owners.

**Never make the model the policy root.** Model-based review, learned policies, steganalysis, and counterfactual repair can assist, but they do not replace deterministic controls at consequential sinks. Any suggested policy or action change needs the same authorized path as other changes.

**Do not promise guarantees outside mediation.** A local gate cannot undo a provider's earlier commitment, force a malicious recipient to delete data, prove all covert channels absent, or establish full source-chain correctness from a small invariant set. Each profile must state its protected boundary and residual assumptions.

**Minimize evidence exposure.** Raw prompts, secrets, personal memory, syscall traces, and detailed social graphs do not belong on a public chain by default. Use encrypted off-chain evidence, access control, retention limits, and selective commitments only after analyzing metadata and dictionary-attack risks.

**Make the source of authority portable.** No mandatory central registrar/resolver, VAMS-wide surveillance operator, vendor-specific DPU, cloud key custodian, foreign coordination chain, or global shutdown authority is introduced by this report.

<a id="priority-index"></a>
## 2. Priority index

All items are **proposed or to-be-verified**, not implementation-complete. Dependencies are logical prerequisites, not a requirement to execute in numeric ID order. Detailed acceptance tests and evidence artifacts follow in Section 3.

### P0: Critical controls (29)

| ID | Work item | Implementation surface |
|---|---|---|
| [RW-001](#rw-001) | Canonical evidence taxonomy and transition receipts | Cross-cutting / Sentinel / VDSO |
| [RW-002](#rw-002) | Crypto-agile identities and separately declared security guarantees | Identity / Heart / proof admission |
| [RW-003](#rw-003) | Approval-to-effect binding and semantic canonicalization | VIR / Service Block dispatch / effect adapters |
| [RW-004](#rw-004) | Deterministic authorization at the external-effect boundary | Heart policy boundary / Neuron / adapters |
| [RW-005](#rw-005) | Delegation provenance and monotonically attenuated authority | Identity / Heart / agent-to-agent invocation |
| [RW-006](#rw-006) | Bounded authority lifetime, contextual consent, and key revocation | Heart / credential lifecycle / VDSO epochs |
| [RW-007](#rw-007) | Authority cuts and bounded quiescence for asynchronous work | Durable runtime / delegation / external providers |
| [RW-008](#rw-008) | Atomic shared budgets and durable spend reservations | Agentic Economy / Heart / durable state |
| [RW-009](#rw-009) | Explicit external-effect contracts, idempotency, and reconciliation | Neuron / DBOS integration / Service Block adapters |
| [RW-010](#rw-010) | Transitive effect constraints and non-amplifying credentials | Service Block sandbox / reference monitor / providers |
| [RW-011](#rw-011) | Closed-world Service Block resolution and version-pinned invocation | Registry / Composer / gateway / dispatch |
| [RW-013](#rw-013) | Durable identity, obligations, effect history, and verified milestones | Neuron / DBOS integration / canonical state |
| [RW-016](#rw-016) | Governed model-context reconstruction and denial-of-wallet limits | Neuron context assembly / budget gate |
| [RW-017](#rw-017) | Separate untrusted context from authority and constrain data flows | Brain inputs / Neuron / Heart boundary |
| [RW-021](#rw-021) | Isolate the inference engine from durable authority | Neuron / model-serving process / sandbox |
| [RW-022](#rw-022) | Enforced communication and capability-reachability manifests | Service Block sandbox / networking / host isolation |
| [RW-023](#rw-023) | Agent-independent observation and tamper-evident audit collection | Sentinel evidence ingestion / effect gateway / host monitor |
| [RW-026](#rw-026) | Adversarial qualification for Service Blocks, skills, A2A, and MCP | Registry admission / Neuron adapters / security testing |
| [RW-027](#rw-027) | Scoped composite TEE attestation and workload-bound receipts | TEE adapters / verifier admission / key release |
| [RW-034](#rw-034) | Scheme-neutral proof statements and explicit assurance profiles | Proof plugins / VDSO / Sentinel / Composer |
| [RW-041](#rw-041) | Canonical cross-domain statements and explicit lane policies | VDSO / cross-chain adapters / VIR |
| [RW-042](#rw-042) | Source-domain invariant and economic-bound checks before export | VDSO export admission / bridge/mint policy |
| [RW-043](#rw-043) | Bounded signer roles and operational trust-domain independence | Bridge/governance signing / key operations |
| [RW-044](#rw-044) | Cross-domain finality, replay protection, and uncertain-settlement handling | VDSO / reservation and settlement adapters |
| [RW-048](#rw-048) | DA admission based on independently verified evidence | DA adapters / evidence storage / Sentinel |
| [RW-057](#rw-057) | A consolidated adversarial conformance and fault-injection suite | Repository testing / Phase-6 evidence generation |
| [RW-058](#rw-058) | Evidence-based admission, quarantine, and release claims | Service Block admission / deployment governance |
| [RW-059](#rw-059) | Configuration-bound capability certification without authority amplification | Qualification / Heart / runtime admission |
| [RW-060](#rw-060) | Hostile prompt-template and flow-configuration containment | Gateway / renderer / sandbox |

### P1: High-relevance improvements (21)

| ID | Work item | Implementation surface |
|---|---|---|
| [RW-012](#rw-012) | Machine-enforced task protocols and bounded plan verification | Brain / Composer / Neuron |
| [RW-014](#rw-014) | Execution-substrate portability and model replacement | Neuron runtime adapter layer / Composer |
| [RW-015](#rw-015) | Verifiable Memory and artifact provenance without a mandated memory algorithm | Memory Service Blocks / artifact layer |
| [RW-018](#rw-018) | Execution-state revocation and provenance-guided replay | Neuron recovery / Memory Service Blocks |
| [RW-019](#rw-019) | Least-privilege memory curation with environmental revalidation | Memory Service Blocks |
| [RW-024](#rw-024) | Evidence-first Sentinel review and assurance assessment | Sentinel / review Service Blocks |
| [RW-025](#rw-025) | Dependency-aware verification and anti-collusion assignment | Sentinel / Composer / Agentic Economy |
| [RW-028](#rw-028) | Reproducible build-to-measurement provenance and transparency | Service Block supply chain / TEE qualification |
| [RW-029](#rw-029) | Sovereign encrypted state custody and attestation-gated key release | Stateful confidential Service Blocks / memory / recovery |
| [RW-030](#rw-030) | Scoped compute rights and explicit output-disclosure policy | Confidential data / memory / inference Service Blocks |
| [RW-031](#rw-031) | Measured confidential-execution capability and performance profiles | Service Block catalog / Composer pricing |
| [RW-035](#rw-035) | Reproducible proof-build provenance and model qualification | ZKML build pipeline / proof adapter qualification |
| [RW-036](#rw-036) | Explicit numerical semantics and deterministic-inference qualification | Inference providers / proof reference runtime |
| [RW-045](#rw-045) | Independent cross-domain observations with explicit abstention | Sentinel / chain observers / evidence normalization |
| [RW-049](#rw-049) | DA security classes and network-aware availability measurement | DA routing / Composer / availability policy |
| [RW-050](#rw-050) | Separate sovereign registration from discovery and resolution | Registry / Composer / VNS and vams:// planning |
| [RW-051](#rw-051) | Metadata-only discovery and least-privilege capability activation | Composer / registry client / credential broker |
| [RW-052](#rw-052) | Separate service quality, model identity, proof validity, and economic claims | Agentic Economy / provider qualification / pricing |
| [RW-054](#rw-054) | Principal-controlled payment policy across execution providers | Payment Service Blocks / wallets / Agentic Economy |
| [RW-056](#rw-056) | Typed multi-principal coordination and evidence-based consequences | Agentic Economy / agent interaction protocols / Sentinel |
| [RW-061](#rw-061) | Quantization-bound proof identity and numerical qualification | ZKML / inference / proof admission |

### P2: Bounded research experiments (11)

| ID | Work item | Implementation surface |
|---|---|---|
| [RW-020](#rw-020) | Optional accelerator-state checkpoint and restore capability | Inference Service Blocks / runtime providers |
| [RW-032](#rw-032) | Narrow-TCB and hybrid trusted-controller experiments | Confidential runtime research / specialized Service Blocks |
| [RW-033](#rw-033) | Host-independent enforcement and DPU-style evidence adapters | High-assurance runtime research / Sentinel |
| [RW-037](#rw-037) | Composable proof graphs and segmented inference proving | Proof Service Blocks / aggregator research |
| [RW-038](#rw-038) | Sound circuit-optimization and debloating experiment | ZKML compiler research |
| [RW-039](#rw-039) | Sampled verification with explicit coverage and anti-grinding controls | Verifiable-inference audit research / proof policy |
| [RW-040](#rw-040) | Alternative and post-quantum proof backend evaluation | Proof research / crypto-agility |
| [RW-046](#rw-046) | Authenticated multi-hop delivery history and pluggable interoperability adapters | CLR / VDSO transport research |
| [RW-047](#rw-047) | Aggregate cross-domain checkpoints with logical epochs | VDSO proof aggregation research |
| [RW-053](#rw-053) | Optional evidence-quorum authorization for high-consequence actions | Heart authorization / governance / critical VDSO lanes |
| [RW-055](#rw-055) | Counterfactual and negative-twin review as advisory verification | Sentinel review Service Blocks |

### P0/P1: Mixed-priority package (1)

| ID | Work item | Implementation surface |
|---|---|---|
| [RW-062](#rw-062) | Independent route admission (P0), health and staged recovery (P1) | VDSO / cross-chain adapters / Sentinel / settlement |

<a id="backlog"></a>
## 3. Detailed implementation backlog

Each item states its architectural relevance, a minimum implementable output, observable acceptance conditions, dependencies, and research lineage. **P2 describes implementable experiments, not validated production benefits.** P0 controls may be satisfied by existing implementation once independently demonstrated.

### 3.1 Authority, external effects, and durable execution

<a id="rw-001"></a>
#### RW-001 | P0 | Canonical evidence taxonomy and transition receipts

**Surface:** Cross-cutting / Sentinel / VDSO  
**Classification:** Direct control; foundational schema

**Importance / architectural relevance.** Unifies the repeated Execution Evidence, TransitionReceipt, assurance-spine, CATP, and auditability proposals. Across v0.4-v0.8, replace an undifferentiated verified flag with explicit claims about identity, provenance, authorization, enforcement, dispatch, computation, observed effect, availability, and settlement.

**Minimum implementable output.** Define versioned EvidenceEnvelope and ActionTransition records. Bind intent and operation IDs, producer, statement type, subject/artifact digest, policy revision, dependency versions, authority epoch, freshness conditions, evidence references, and decision. Preserve the adapter-normalized action AND a commitment to the original typed request. Represent unknown, refused, disputed, compensated, and indeterminate outcomes; never infer an external effect from an authorization or dispatch receipt. Keep execution and settlement lifecycles separate and linked.

**Acceptance tests.** A signed authorization with no provider observation cannot become EFFECT_OBSERVED or SETTLED. A modified policy, input, implementation, or dependency invalidates the relevant binding. Identical normalized actions with materially different original requests are rejected unless the equivalence is explicitly justified. An independent verifier can validate a receipt without the original agent process.

**Evidence to retain:** Versioned schema, canonical encoding vectors, transition validation tests, and an assurance-claim table.  
**Dependencies:** None; may begin independently.  
**Research lineage:** [S008](#s008), [S012](#s012), [S016](#s016), [S024](#s024), [S063](#s063), [S087](#s087).

<a id="rw-002"></a>
#### RW-002 | P0 | Crypto-agile identities and separately declared security guarantees

**Surface:** Identity / Heart / proof admission  
**Classification:** Direct compatibility control; new cryptosuites remain gated

**Importance / architectural relevance.** Long-lived identities must outlive individual cryptosuites. Preserve the distinction between authorization, proof, confidentiality, and settlement security instead of calling a route post-quantum because one component is. This is a migration requirement, not endorsement of any quantum-computing timeline in the reports.

**Minimum implementable output.** Attach suite ID/version, signer role, key version, validity interval, security epoch, and explicit verification policy to credentials and evidence. Specify whether a hybrid policy requires BOTH signatures; reject downgrade or substitution. Design root rotation and recovery with continuity commitments and principal-approved recovery authority. Track KEM/encryption suites independently from signatures. Do not activate an unreviewed PQ verifier merely to match a design document.

**Acceptance tests.** Rotate a root without changing agent identity or losing obligations. Reject retired-key replay, ambiguous hybrid acceptance, unsupported suites, and forced downgrade. A route with classical confidentiality or settlement cannot advertise end-to-end post-quantum security.

**Evidence to retain:** Cryptosuite registry schema, migration/recovery ADR, negative vectors, and route-security matrix.  
**Dependencies:** [RW-001](#rw-001)  
**Research lineage:** [S015](#s015), [S017](#s017), [S026](#s026), [S039](#s039), [S043](#s043).

<a id="rw-003"></a>
#### RW-003 | P0 | Approval-to-effect binding and semantic canonicalization

**Surface:** VIR / Service Block dispatch / effect adapters  
**Classification:** Direct safety control

**Importance / architectural relevance.** Merges approval laundering, formation-consistent dispatch, execution-finality, and CATP outputs. Approval must apply to the exact operation that reaches the effect adapter, not only a tool name or a lossy normalized string.

**Minimum implementable output.** Create an ExecutionFormation commitment covering principal, original typed request, canonical action, intent/task, target resource, Service Block identity, implementation/schema/effect-profile versions, policy, authority epoch, expiry, and adapter identity. Bind this before approval and recheck at dispatch and final effect. Use explicit typed encodings, domain separation, and unambiguous units; do not use shell-string equivalence as authorization. Changed implementations or semantics require reauthorization unless a separately reviewed compatibility rule applies.

**Acceptance tests.** Exercise scope, argument, temporal, tool, delegation, and semantic substitution. Swap an adapter after approval; alter arguments or units; create a normalization collision; reconnect to a different implementation. Every material mismatch must deny the effect, even when the approval signature remains valid.

**Evidence to retain:** ExecutionFormation schema, canonicalization specification, dispatch fence, and six-class laundering regressions.  
**Dependencies:** [RW-001](#rw-001)  
**Research lineage:** [S012](#s012), [S028](#s028), [S063](#s063), [S069](#s069), [S082](#s082), [S086](#s086), [S087](#s087).

<a id="rw-004"></a>
#### RW-004 | P0 | Deterministic authorization at the external-effect boundary

**Surface:** Heart policy boundary / Neuron / adapters  
**Classification:** Direct safety control; required for consequential effects

**Importance / architectural relevance.** Consolidates out-of-band policy, ActGov, attested enforcement, and action-guard recommendations. The Brain proposes; a small enforcement component determines whether the exact effect is permitted under current authority. A model reviewer is not the root of authorization.

**Minimum implementable output.** Place a deterministic reference monitor in front of each supported mutation sink. Validate the exact formation, delegated capability, resource, current state version, policy, epoch, budget, nonce, and expiry. Use a transaction, compare-and-swap, or provider-enforced fencing to bind admission to effect; document the residual race where a provider cannot participate. Keep policy input separate from untrusted model/tool content. Deny on missing or stale evidence. Keep signing keys and unrestricted provider credentials outside the model process.

**Acceptance tests.** Change policy or revoke authority between planning and dispatch; stale intent must not execute. Poison tool output without changing trusted policy; authorization must not expand. Directly bypass the model client and call the sink; the same check must still apply.

**Evidence to retain:** Reference-monitor interface, one real protected adapter, bypass tests, and a defined admission linearization point.  
**Dependencies:** [RW-001](#rw-001), [RW-003](#rw-003)  
**Research lineage:** [S009](#s009), [S012](#s012), [S020](#s020), [S028](#s028), [S037](#s037), [S059](#s059), [S063](#s063), [S094](#s094).

<a id="rw-005"></a>
#### RW-005 | P0 | Delegation provenance and monotonically attenuated authority

**Surface:** Identity / Heart / agent-to-agent invocation  
**Classification:** Direct safety control

**Importance / architectural relevance.** Separates principal, agent, operator, developer, and runtime identity. A signed lineage proves provenance, not present permission. Multiple reports converge on preserving the origin principal through every delegation hop while preventing child authority from exceeding its parents.

**Minimum implementable output.** Define DelegationProvenance separately from EffectiveCapability. Bind parent/root, audience, task/resource scope, operation limits, depth, policy epoch, expiry, proof-of-possession requirements, and revocation lineage. Compute effective authority as the intersection of ancestor grants, local policy, and resource policy. Support sovereign organizational or non-human roots where explicitly authorized; do not force every agent into a centrally registered human identity. Missing, cyclic, invalid, or unresolvable lineage fails closed.

**Acceptance tests.** A child cannot increase budget, target scope, expiry, delegation depth, or permitted operations. Revoking a parent invalidates descendants at protected sinks. A multi-hop request preserves the original principal; a provenance-only object cannot authorize execution.

**Evidence to retain:** Delegation schema, attenuation evaluator, root-policy profiles, and multi-hop adversarial vectors.  
**Dependencies:** [RW-001](#rw-001)  
**Research lineage:** [S006](#s006), [S007](#s007), [S013](#s013), [S032](#s032), [S037](#s037), [S038](#s038), [S043](#s043), [S085](#s085).

<a id="rw-006"></a>
#### RW-006 | P0 | Bounded authority lifetime, contextual consent, and key revocation

**Surface:** Heart / credential lifecycle / VDSO epochs  
**Classification:** Direct safety control

**Importance / architectural relevance.** Agent continuity must not become permanent permission. Consolidates residual-consent replay, short-lived workload tokens, revocation epochs, and authority fencing. Approval from an earlier task does not automatically authorize a new task after restart or context change.

**Minimum implementable output.** Bind capabilities to task/intent, resource, audience, permitted effect, authority and policy epochs, expiry, and relevant consent context. Re-derive authority after material changes; do not demand new human approval for every harmless context compaction when a still-valid explicit grant covers continuation. Issue short-lived sink credentials, rotate signing keys, and propagate parent revocation. State the revocation freshness bound at each sink; cached credentials cannot imply instantaneous global revocation.

**Acceptance tests.** Approve a sensitive task, persist and restart the agent, change the task, then attempt replay: deny. Exercise stale caches, rotated keys, delegated credentials, offline sinks, and time skew. Accepted continuation must show a current grant for the same authorized scope.

**Evidence to retain:** Capability lifecycle state machine, revocation/freshness policy, rotation drill, and residual-authority replay test.  
**Dependencies:** [RW-002](#rw-002), [RW-005](#rw-005)  
**Research lineage:** [S023](#s023), [S039](#s039), [S043](#s043), [S057](#s057), [S081](#s081).

<a id="rw-007"></a>
#### RW-007 | P0 | Authority cuts and bounded quiescence for asynchronous work

**Surface:** Durable runtime / delegation / external providers  
**Classification:** Direct control; applies when queued or delegated effects are enabled

**Importance / architectural relevance.** A process stop or token revocation is not proof that queued, delegated, or provider-side work can no longer act. Make durably revocable a counterpart to durably continuable, without claiming that already committed external effects can be undone.

**Minimum implementable output.** Create an AuthorityCut for a root and retired epoch at an explicit cut point. Fence future admissions and delegation expansion; enumerate outstanding reservations, callbacks, jobs, and provider operations. Track acknowledgements and provider frontiers. Produce a scoped QuiescenceReport listing fenced, completed, canceled, and unresolved paths. Report QUIESCENT only for a declared, fully mediated sink set; otherwise remain INDETERMINATE. Compensation is a new authorized action, not retroactive erasure.

**Acceptance tests.** Revoke while jobs are queued or in flight, kill/restart workers, and deliver late callbacks from stale replicas. Old-root operations cannot newly cross a fenced sink. Missing provider acknowledgement prevents a global quiescence claim. Effects committed before the cut remain recorded.

**Evidence to retain:** AuthorityCut and QuiescenceReport schemas, outstanding-effect index, and cut/restart/late-callback canary.  
**Dependencies:** [RW-006](#rw-006), [RW-009](#rw-009)  
**Research lineage:** [S010](#s010), [S023](#s023), [S057](#s057), [S081](#s081).

<a id="rw-008"></a>
#### RW-008 | P0 | Atomic shared budgets and durable spend reservations

**Surface:** Agentic Economy / Heart / durable state  
**Classification:** Direct economic safety control

**Importance / architectural relevance.** A signed spending grant cannot independently enforce one shared budget across replicas, retries, and descendants. Consolidate bounded-capability receipts, issuer policy, x402-style payment proposals, and durable reservation accounting into a single state-domain contract.

**Minimum implementable output.** Use one authoritative atomic budget ledger per grant or economic authority domain. Define exact units, reservation IDs, operation IDs, limit periods, spend/commit state, refund rules, fencing, and child-budget allocation. Reserve before admitting an effect. Conservatively retain exposure for uncertain provider outcomes rather than automatically refunding and retrying. Reconcile actual provider charges separately from token-count estimates. Do not introduce distributed writers for the same balance.

**Acceptance tests.** Two replicas concurrently spending the last allowance cannot both succeed. Crash after reservation, duplicate delivery, child delegation, delayed charge, and timeout must not increase total authorized exposure. An indeterminate effect cannot release budget without the specified reconciliation evidence.

**Evidence to retain:** Budget ledger schema, atomic reservation implementation, conservation invariants, and concurrency/fault tests.  
**Dependencies:** [RW-006](#rw-006), [RW-009](#rw-009)  
**Research lineage:** [S023](#s023), [S064](#s064), [S068](#s068), [S074](#s074).

<a id="rw-009"></a>
#### RW-009 | P0 | Explicit external-effect contracts, idempotency, and reconciliation

**Surface:** Neuron / DBOS integration / Service Block adapters  
**Classification:** Direct safety control; no universal exactly-once claim

**Importance / architectural relevance.** This is the central durable-agent correction across the reports: workflow replay safety is distinct from provider-side side-effect uniqueness. An adapter must declare the guarantees it can actually supply; strong model reasoning is not a substitute for an idempotency contract.

**Minimum implementable output.** Define EffectContract fields for operation identity, provider idempotency scope and retention, provider effect ID, transactional reservation support, status/query semantics, cancellation, in-flight bounds when known, and receipt authenticity. Track ADMITTED, DISPATCHED, OBSERVED_COMMITTED, OBSERVED_NOT_COMMITTED, and INDETERMINATE with separate settlement state. Never blindly retry a non-idempotent mutation after ambiguous transport failure. Use human/operator escalation when no bounded reconciliation exists.

**Acceptance tests.** Inject lost acknowledgement, late commit, duplicate delivery, worker restart, partial batch completion, and expired idempotency retention. No duplicate accepted effect is permitted within the declared contract. When the contract cannot decide safely, the result remains INDETERMINATE rather than invented success or failure.

**Evidence to retain:** EffectContract qualification profile, provider-backed fault harness, reconciliation adapter, and guarantee documentation.  
**Dependencies:** [RW-001](#rw-001), [RW-003](#rw-003)  
**Research lineage:** [S010](#s010), [S019](#s019), [S023](#s023), [S024](#s024), [S057](#s057), [S074](#s074).

<a id="rw-010"></a>
#### RW-010 | P0 | Transitive effect constraints and non-amplifying credentials

**Surface:** Service Block sandbox / reference monitor / providers  
**Classification:** Direct safety control

**Importance / architectural relevance.** An allowed entry-point call can trigger subprocesses, filesystem changes, network access, callbacks, spending, and further delegation. A Service Block must not borrow its ambient cloud role, wallet, or API key to amplify the caller's authority.

**Minimum implementable output.** Define an EffectEnvelope covering writable objects/paths, network destinations, processes, credential operations, delegation, monetary bounds, and cross-domain effects. Constrain actual execution with least-privilege OS/provider permissions and short-lived brokered credentials. Enforce query/resource restrictions and permitted response fields at the service boundary. Predicted effect closures aid approval, but incomplete prediction never replaces runtime controls. External services outside mediation retain explicitly documented limitations.

**Acceptance tests.** Approve a benign command that triggers a package hook, child process, SSRF, or privileged backend request. Effects outside the envelope must be blocked at their sinks. A service-account token with broader privileges cannot authorize the caller to exercise those privileges.

**Evidence to retain:** EffectEnvelope schema, credential broker contract, sink policies, and transitive-effect/SSRF regression suite.  
**Dependencies:** [RW-004](#rw-004), [RW-005](#rw-005)  
**Research lineage:** [S020](#s020), [S021](#s021), [S039](#s039), [S069](#s069), [S086](#s086).

<a id="rw-011"></a>
#### RW-011 | P0 | Closed-world Service Block resolution and version-pinned invocation

**Surface:** Registry / Composer / gateway / dispatch  
**Classification:** Direct safety control

**Importance / architectural relevance.** Discovery metadata, interface syntax, and implementation identity are different objects. Resolve a concrete executable Service Block before checking authority, and prevent a stable tool name from silently changing meaning while approval is pending.

**Minimum implementable output.** Resolve calls against an authenticated registry view into Service Block ID, namespace owner, version, schema digest, implementation digest, effect profile, and adapter identity. Reject undeclared tools and ambiguous namespaces. Pin the resolved identity into ExecutionFormation. Handle updates as explicit version transitions; stale registry responses, quarantined implementations, and incompatible successors cannot inherit approvals. Do not require a single global naming authority.

**Acceptance tests.** Test fabricated tools, namespace shadowing, borrowed arguments, wrong schemas, stale versions, registry rollback, and implementation swaps after approval. A correctly signed but incompatible successor must require new authorization.

**Evidence to retain:** Resolver contract, versioned manifest schema, dispatch pinning, and resolution/upgrade adversarial fixtures.  
**Dependencies:** [RW-001](#rw-001), [RW-003](#rw-003)  
**Research lineage:** [S032](#s032), [S051](#s051), [S077](#s077), [S082](#s082), [S086](#s086).

<a id="rw-012"></a>
#### RW-012 | P1 | Machine-enforced task protocols and bounded plan verification

**Surface:** Brain / Composer / Neuron  
**Classification:** Direct implementable improvement; not universal formal verification

**Importance / architectural relevance.** Combine CaMeLoT-style plan checks with executable operating protocols. Long-horizon execution should not depend on a model remembering phase ordering, review gates, or allowed transitions. Formal verification applies only to the extracted model and its assumptions.

**Minimum implementable output.** Compile a small typed workflow into a finite or explicitly bounded state machine. Declare admissible states, transitions, invariants, milestone predicates, forbidden ordering, timeouts, and escalation. Generate a PlanVerificationReceipt binding plan, policy, verifier, assumptions, and counterexample. Require runtime checks for dynamic state and revalidation after plan changes. Keep arbitrary cognitive strategies and memory algorithms outside protocol consensus.

**Acceptance tests.** Reject plans that spend before approval, publish before required review, or bypass a required check. A changed plan invalidates its previous receipt. Dynamic revocation still blocks a statically accepted plan. Unbounded loops or unknown transitions are not silently certified.

**Evidence to retain:** TaskProtocol schema, one compiled workflow, bounded property checks, and counterexample fixtures.  
**Dependencies:** [RW-003](#rw-003), [RW-004](#rw-004), [RW-011](#rw-011)  
**Research lineage:** [S042](#s042), [S047](#s047), [S054](#s054), [S089](#s089), [S095](#s095).

<a id="rw-013"></a>
#### RW-013 | P0 | Durable identity, obligations, effect history, and verified milestones

**Surface:** Neuron / DBOS integration / canonical state  
**Classification:** Direct control for an Immortal Agent claim

**Importance / architectural relevance.** Externalize continuity from model context. The durable unit is identity plus authorized obligations, accepted state, budgets, checkpoint lineage, effect records, and evidence-backed milestones. Persistent chat history or a model's completion statement is not canonical progress.

**Minimum implementable output.** Define a TaskBlueprint and milestone ledger with objective commitment, dependency/artifact roots, acceptance predicate, reviewer/evidence requirements, outstanding duties, and authority epoch. Commit accepted transitions through one authoritative writer with version checks and fencing. Separate candidate conclusions from accepted results. Preserve useful failed attempts as provenance-bearing knowledge, not as automatically trusted facts. Keep model prompts and private memory in the service layer.

**Acceptance tests.** Kill and restart a worker mid-task; obligations and effect references survive. Competing replicas cannot accept the same milestone twice or overwrite newer state. A persuasive false completion without required evidence is rejected. Recovery does not reinstate expired authority.

**Evidence to retain:** Durable task/obligation schema, milestone acceptance rules, recovery tests, and explicit continuity guarantees.  
**Dependencies:** [RW-001](#rw-001), [RW-006](#rw-006), [RW-009](#rw-009)  
**Research lineage:** [S010](#s010), [S019](#s019), [S047](#s047), [S054](#s054), [S089](#s089), [S095](#s095).

<a id="rw-014"></a>
#### RW-014 | P1 | Execution-substrate portability and model replacement

**Surface:** Neuron runtime adapter layer / Composer  
**Classification:** Direct interface improvement; broad live migration is deferred

**Importance / architectural relevance.** An agent that survives process restart but cannot survive a model or runtime replacement has limited sovereignty. Separate task semantics and effect contracts from the DBOS-specific or model-specific execution binding.

**Minimum implementable output.** Define an ExecutionSubstrateContract for loading canonical state, checkpoints, pending effects, artifact references, capability re-derivation, and milestone commits. Preserve DBOS as the initial implementation; build a minimal alternate test runner rather than rewriting the runtime. Require a quiescent/fenced handoff and schema compatibility. Different stochastic outputs are acceptable if authority, task invariants, and accepted effects remain consistent.

**Acceptance tests.** Start on model/runtime A, interrupt at a documented boundary, resume on B, and demonstrate identical obligation/effect accounting and no old-worker writes. Reject incompatible checkpoint versions and unsupported effect contracts; no promise of bitwise cognitive continuity.

**Evidence to retain:** Runtime adapter interface, portability manifest, and A-to-B recovery demonstration.  
**Dependencies:** [RW-013](#rw-013)  
**Research lineage:** [S001](#s001), [S019](#s019), [S029](#s029), [S047](#s047), [S054](#s054), [S095](#s095).

### 3.2 Memory, context, isolation, and evidence independence

<a id="rw-015"></a>
#### RW-015 | P1 | Verifiable Memory and artifact provenance without a mandated memory algorithm

**Surface:** Memory Service Blocks / artifact layer  
**Classification:** Direct modular interface improvement

**Importance / architectural relevance.** Standardize what can be verified about memory, not how memory engineers represent or retrieve it. Consolidate provenance, freshness, poisoning, derivation, ownership, and revocation proposals while keeping protocol safety state separate from cognitive memory.

**Minimum implementable output.** Define MemoryRecord and ArtifactProvenance envelopes for content commitments, producer/source references, source trust class, derivation lineage, observation/verification times, state-version references, write authority, retention, and revocation. Preserve labels through summaries and new artifacts. Let vector, graph, episodic, semantic, or other providers implement storage and retrieval. Do not publish private content, personal provenance, or raw memory on-chain; even commitments require a privacy analysis for guessable inputs.

**Acceptance tests.** A summary cannot promote untrusted source content to trusted authority merely by being persisted. Unauthorized writes and stale records are rejected or visibly labeled. Two different memory implementations can produce conforming evidence without adopting the same internal representation.

**Evidence to retain:** Memory/artifact envelope schemas, provider conformance tests, and an explicit protocol-state versus cognitive-memory boundary.  
**Dependencies:** [RW-001](#rw-001), [RW-005](#rw-005)  
**Research lineage:** [S010](#s010), [S035](#s035), [S046](#s046), [S070](#s070), [S078](#s078), [S080](#s080).

<a id="rw-016"></a>
#### RW-016 | P0 | Governed model-context reconstruction and denial-of-wallet limits

**Surface:** Neuron context assembly / budget gate  
**Classification:** Direct resource safety control

**Importance / architectural relevance.** Durable storage does not imply indefinite re-ingestion into paid model calls. Consolidate billable-state leases, context growth limits, recursive tool-loop bounds, and economic exposure controls for resumed agents.

**Minimum implementable output.** Introduce ContextAdmissionPolicy or BillableStateLease with source, expiry, size/token ceilings, re-ingestion count, recursion bounds, per-call and cumulative spend limits, compaction policy, and progress criteria. Charge against the authoritative budget before paid calls. Preserve full evidence off the model context path where needed; compacted text must retain provenance. Support an explicit stop/escalation outcome instead of unlimited retry or summarization loops.

**Acceptance tests.** Inject oversized recurring tool responses, nested plans, and malicious retained memory; costs and context cannot grow beyond configured limits. Restarting a worker cannot reset cumulative usage. A legitimate long-running job can continue under a renewed explicit budget rather than being silently terminated.

**Evidence to retain:** Context-admission interface, durable usage counters, malicious-state replay corpus, and budget-bound test results.  
**Dependencies:** [RW-004](#rw-004), [RW-008](#rw-008)  
**Research lineage:** [S023](#s023), [S068](#s068), [S074](#s074), [S077](#s077).

<a id="rw-017"></a>
#### RW-017 | P0 | Separate untrusted context from authority and constrain data flows

**Surface:** Brain inputs / Neuron / Heart boundary  
**Classification:** Direct authority-isolation control; semantic detection remains heuristic

**Importance / architectural relevance.** Memory, tool descriptions, tool outputs, retrieved documents, and inter-agent messages can collectively influence a model. Labels and prompt wording alone cannot enforce instruction/data separation inside an LLM; actual protection must come from external capability and output controls.

**Minimum implementable output.** Attach a ContextEvidenceEnvelope with origin, channel, content/provenance commitment, classification, taint lineage, and allowed sinks. Keep credentials and signing keys out of model-visible text. Feed the policy engine only independently trusted authorization inputs, not the poisoned context that generated a proposal. Constrain writes, disclosures, and delegation even when the model follows an injected instruction. Preserve provenance through artifact-to-memory-to-artifact paths.

**Acceptance tests.** Split an injection across tool metadata, tool output, and memory; the model may be influenced but cannot gain forbidden sink authority. Three agents sharing artifacts cannot turn an untrusted document into a new grant. Sensitive data cannot reach an unauthorized egress through approved-but-overbroad tools.

**Evidence to retain:** Context provenance schema, trusted-input policy boundary, allowed-sink rules, and fragmented/memory-hopping injection tests.  
**Dependencies:** [RW-004](#rw-004), [RW-010](#rw-010)  
**Research lineage:** [S032](#s032), [S052](#s052), [S080](#s080), [S093](#s093), [S094](#s094).

<a id="rw-018"></a>
#### RW-018 | P1 | Execution-state revocation and provenance-guided replay

**Surface:** Neuron recovery / Memory Service Blocks  
**Classification:** Direct recovery prototype; not a universal proof of forgetting

**Importance / architectural relevance.** Deleting a memory row or rotating a secret does not automatically clean derived summaries, pending plans, caches, or already exported artifacts. Add a recoverable dependency model for revoking contaminated cognitive state without confusing it with durable protocol history.

**Minimum implementable output.** Track source-to-derived-state dependencies, checkpoints, pending plans, context/cache versions, revocation epochs, and clean replay boundaries. On revocation, block future use, invalidate affected caches/plans, and replay from a clean checkpoint with renewed authority. Preserve required audit facts while removing prohibited cognitive reuse. Distinguish access revocation, cryptographic key destruction, deletion attempts, and behavioral replay evidence; none proves deletion from a malicious external recipient.

**Acceptance tests.** Inject a test secret or poisoned fact, create derived state, revoke it, then resume. Verify no known dependent plan/cache is reused and compare against a clean replay baseline. Record unknown dependencies or already exported copies as limitations; do not claim universal machine unlearning.

**Evidence to retain:** StateDependency and RevocationReceipt schemas, selective replay prototype, and documented deletion/forgetting assurance scope.  
**Dependencies:** [RW-013](#rw-013), [RW-015](#rw-015), [RW-017](#rw-017)  
**Research lineage:** [S046](#s046), [S057](#s057), [S081](#s081).

<a id="rw-019"></a>
#### RW-019 | P1 | Least-privilege memory curation with environmental revalidation

**Surface:** Memory Service Blocks  
**Classification:** Direct service-level experiment

**Importance / architectural relevance.** Prevent durable memory from fossilizing stale or false observations. A curator can recheck selected facts against the authorized environment without being granted production-write or canonical-memory-write authority.

**Minimum implementable output.** Give the curator read-only, resource-scoped probing capabilities. Record which source/environment state was checked, when, by which method, and what remains uncertain. Emit proposed memory updates rather than directly committing them. Apply a separate writer policy for promotion, retention, and conflict resolution. Avoid interpreting a model confidence score as verification.

**Acceptance tests.** Present stale and conflicting records; revalidation detects differences and proposes a provenance-bearing update. A compromised curator cannot change production objects, expand its query scope, or commit memory without the independent write gate.

**Evidence to retain:** Read-only curator Service Block prototype, freshness policy, and stale/conflicting-memory tests.  
**Dependencies:** [RW-015](#rw-015)  
**Research lineage:** [S035](#s035).

<a id="rw-020"></a>
#### RW-020 | P2 | Optional accelerator-state checkpoint and restore capability

**Surface:** Inference Service Blocks / runtime providers  
**Classification:** Bounded research prototype; not protocol consensus

**Importance / architectural relevance.** Workflow checkpoints and GPU execution-state checkpoints solve different problems. KV-cache, scheduler, and adapter snapshots may reduce recovery cost, but must never become the source of canonical task state or a prerequisite for all durable agents.

**Minimum implementable output.** Define AcceleratorCheckpointProvider with runtime/model/tokenizer/configuration identities, checkpoint epoch, workflow/state binding, encrypted manifest, integrity digest, and compatibility policy. Measure whether restore preserves the declared numerical and confidentiality profile. Treat incompatible or unverifiable snapshots as disposable acceleration artifacts; recompute from canonical state. Restore must re-derive current authority.

**Acceptance tests.** Corrupt or roll back a snapshot, change model/runtime configuration, and revoke the old authority. Reject unsafe restoration without losing canonical obligations. Compare cold recomputation with valid restore for time, storage, cost, and output consistency.

**Evidence to retain:** Checkpoint capability sketch, compatibility matrix, and restore-versus-recompute benchmark.  
**Dependencies:** [RW-013](#rw-013), [RW-028](#rw-028), [RW-029](#rw-029), [RW-036](#rw-036)  
**Research lineage:** [S001](#s001), [S010](#s010), [S046](#s046).

<a id="rw-021"></a>
#### RW-021 | P0 | Isolate the inference engine from durable authority

**Surface:** Neuron / model-serving process / sandbox  
**Classification:** Direct containment control

**Importance / architectural relevance.** TEE placement or an authenticated model does not make parsers, inference engines, extensions, or generated tokens trustworthy. Keep the model-serving process outside the authority boundary so its compromise cannot directly sign, spend, or write canonical state.

**Minimum implementable output.** Run inference with no raw wallet keys, root credentials, unrestricted network, governance access, or canonical-state write permission. Use a narrow IPC/API to the effect gate. Pin and inventory model, tokenizer, engine, parser, plugin, image, and dependency digests. Separate mutable working files and caches from authority/evidence stores. Handle runtime security advisories through qualification policy rather than trusting an old attestation indefinitely.

**Acceptance tests.** Simulate full compromise of the inference process; direct signing, settlement, secret retrieval, state mutation, and log destruction must remain denied. Malformed generated tool output is parsed as untrusted input and cannot bypass the effect boundary.

**Evidence to retain:** Process/credential separation design, least-privilege runtime profile, component inventory, and assumed-compromise tests.  
**Dependencies:** [RW-004](#rw-004), [RW-010](#rw-010)  
**Research lineage:** [S022](#s022), [S040](#s040), [S053](#s053), [S071](#s071), [S083](#s083), [S093](#s093).

<a id="rw-022"></a>
#### RW-022 | P0 | Enforced communication and capability-reachability manifests

**Surface:** Service Block sandbox / networking / host isolation  
**Classification:** Direct containment control

**Importance / architectural relevance.** Observed benign traffic and readable natural-language transcripts do not establish isolation or non-collusion. Enumerate shared stores, caches, IPC, network routes, logs, DA, chain writes, and spawned workers as possible communication paths.

**Minimum implementable output.** Attach a RuntimeReachabilityManifest to each admitted workload. Enforce default-deny routes and explicit scopes for filesystem, egress, wallet/API access, IPC, shared storage, cache namespaces, spawning, delegation, and self-modification. Compare declared versus effective permissions. Describe timing/resource-sharing channels that the isolation profile does not close; do not claim covert-channel freedom on commodity shared hosts. Security controls are owner/domain selected, not a central VAMS surveillance service.

**Acceptance tests.** Two nominally isolated agents attempt to coordinate via shared cache, logs, artifact storage, DA, and undeclared network endpoints. Deny unapproved edges or downgrade the isolation claim. Context reset and process restart must not recreate forbidden access.

**Evidence to retain:** Reachability manifest, enforcement mapping, shared-resource inventory, and communication-path adversarial suite.  
**Dependencies:** [RW-010](#rw-010), [RW-021](#rw-021)  
**Research lineage:** [S013](#s013), [S049](#s049), [S061](#s061), [S062](#s062), [S067](#s067), [S073](#s073), [S080](#s080), [S083](#s083).

<a id="rw-023"></a>
#### RW-023 | P0 | Agent-independent observation and tamper-evident audit collection

**Surface:** Sentinel evidence ingestion / effect gateway / host monitor  
**Classification:** Direct evidence-integrity control

**Importance / architectural relevance.** An agent cannot be the sole narrator or custodian of its own authoritative audit trail. DA protects committed records, not events suppressed before commitment. Independent collection must be outside the agent's mutation authority and its trust boundary must be explicit.

**Minimum implementable output.** Emit ObservationReceipts from a protected gateway, sandbox monitor, kernel collector, or stronger independent domain. Bind intent, formation, effect ID, policy, runtime identity, observed event class, sequence/order, and evidence root. Detect truncation and missing sequence ranges. Encrypt and minimize telemetry; keep raw traces off-chain with controlled retention. A kernel collector can resist the agent process but not a fully compromised kernel; use stronger profiles for stronger claims.

**Acceptance tests.** Let the agent delete and falsify local logs, split actions across tools, and kill its process. Protected receipts survive or a verifiable gap is raised. Disable the collector: high-assurance effects fail closed or follow an explicitly approved degraded policy, never silently claim complete observation.

**Evidence to retain:** ObservationReceipt schema, independent collector prototype, retention policy, and trace-tampering/gap-detection tests.  
**Dependencies:** [RW-001](#rw-001), [RW-021](#rw-021), [RW-022](#rw-022)  
**Research lineage:** [S016](#s016), [S030](#s030), [S071](#s071), [S075](#s075), [S076](#s076), [S083](#s083).

<a id="rw-024"></a>
#### RW-024 | P1 | Evidence-first Sentinel review and assurance assessment

**Surface:** Sentinel / review Service Blocks  
**Classification:** Direct audit-method improvement

**Importance / architectural relevance.** Actor conclusions can bias reviewers, and several attestations can repeat the same unsupported assertion. Distinguish raw observation, derived measurement, actor claim, independent verification, and the exact property each proves.

**Minimum implementable output.** Provide a conclusion-blind first-pass review of raw or independently obtained evidence. Attach provenance, dependency freshness, verification scope, and uncertainty to findings. Keep semantic/model judgments advisory unless backed by a deterministic predicate appropriate to the action. Require any correction or substitute action to obtain fresh authorization. Hashing a self-report does not make it independent evidence.

**Acceptance tests.** Give reviewers persuasive but false self-reports plus contradictory raw observations. Measure fault localization and false positives with and without actor conclusions. Missing evidence must result in insufficient-evidence status rather than an invented clean bill of health.

**Evidence to retain:** Sentinel evidence-class schema, review protocol, misleading-self-report benchmark, and uncertainty reporting.  
**Dependencies:** [RW-001](#rw-001), [RW-023](#rw-023)  
**Research lineage:** [S013](#s013), [S016](#s016), [S030](#s030), [S063](#s063), [S066](#s066), [S085](#s085).

<a id="rw-025"></a>
#### RW-025 | P1 | Dependency-aware verification and anti-collusion assignment

**Surface:** Sentinel / Composer / Agentic Economy  
**Classification:** Direct design and test improvement; economic scoring remains experimental

**Importance / architectural relevance.** Different addresses, models, or workers do not necessarily represent independent failure domains. Shared operators, software, inputs, roots, economics, and repeated pairings can correlate verifier failures.

**Minimum implementable output.** Maintain a privacy-conscious VerificationDependencyProfile distinguishing asserted from attested relationships. Apply explicit independence rules to critical verifier selection; track repeated reciprocal review and concentrated assignments. Test randomized rotation and exclusion of economically linked pairs. Fail closed when a required independence condition is unestablished; never convert an opaque learned collusion score into automatic slashing.

**Acceptance tests.** A nominal N-of-M set sharing one source/operator is not admitted as N independent observations. Corrupt a common input and compare homogeneous with diversity-constrained assignments. Test repeated shared-incentive interactions and record both detection failures and false accusations.

**Evidence to retain:** Dependency profile, assignment policy, correlated-failure/anti-collusion simulations, and limitations analysis.  
**Dependencies:** [RW-023](#rw-023), [RW-024](#rw-024)  
**Research lineage:** [S005](#s005), [S013](#s013), [S030](#s030), [S045](#s045), [S061](#s061), [S067](#s067), [S073](#s073), [S085](#s085), [S095](#s095).

<a id="rw-026"></a>
#### RW-026 | P0 | Adversarial qualification for Service Blocks, skills, A2A, and MCP

**Surface:** Registry admission / Neuron adapters / security testing  
**Classification:** Direct admission control

**Importance / architectural relevance.** Transport compatibility and signed registration are not security qualification. Test untrusted instructions and protocol state machines for source-to-sink authority escalation before a component receives consequential capabilities.

**Minimum implementable output.** Build a conformance suite for context ownership, origin-principal preservation, capability claims, delegation, namespaces, schema/version binding, stale sessions, credentials, and untrusted skill/tool content. Use harmless canary secrets, wallets, files, and endpoints. Model selected protocol flows as explicit states and transitions. Associate qualification with exact implementation/configuration versions and invalidate it on material change.

**Acceptance tests.** An authenticated malicious Service Block cannot expand authority through a description, tool result, installed skill, delegated request, or forged capability advertisement. Cross-client context access, identity stripping, credential harvesting, and namespace shadowing must be rejected at the relevant boundary.

**Evidence to retain:** Versioned conformance corpus, source-to-sink threat map, admission results, and quarantine triggers.  
**Dependencies:** [RW-004](#rw-004), [RW-005](#rw-005), [RW-011](#rw-011), [RW-017](#rw-017), [RW-022](#rw-022)  
**Research lineage:** [S006](#s006), [S032](#s032), [S037](#s037), [S043](#s043), [S051](#s051), [S052](#s052), [S093](#s093), [S094](#s094).

### 3.3 Confidential execution and sovereign state

<a id="rw-027"></a>
#### RW-027 | P0 | Scoped composite TEE attestation and workload-bound receipts

**Surface:** TEE adapters / verifier admission / key release  
**Classification:** Direct control; only for enabled confidential-compute claims

**Importance / architectural relevance.** A CPU quote, a GPU quote, a workload measurement, and a policy decision establish different facts. Consolidate EnclaveX, cMCP, CPU/GPU evidence, NACRE, and production comparisons into explicit assurance profiles rather than TEE=true.

**Minimum implementable output.** Define ConfidentialExecutionEvidence containing required CPU and accelerator attestations, trusted measurements, workload/model/runtime bindings, policy digest, nonce/freshness, input/output commitments where actually enforced, TCB version/status, and verification roots. Require evidence that the CPU, GPU, channel, and job belong to the same authorized session; two separately fresh quotes alone do not prove this binding. Verify the root/principal association according to current VAMS identity rules. No attestation implies output correctness, harmlessness, or authorization by itself.

**Acceptance tests.** CPU-valid/GPU-nonconfidential fails a confidential-GPU profile. Mix-and-match quotes from different hosts or sessions, stale quotes, wrong workload, invalid TCB, and missing channel binding are rejected. Mock fixtures can never be promoted as live hardware evidence.

**Evidence to retain:** Composite attestation schema, verifier policy profiles, negative quote corpus, and one live-evidence qualification run.  
**Dependencies:** [RW-001](#rw-001), [RW-002](#rw-002)  
**Research lineage:** [S002](#s002), [S009](#s009), [S022](#s022), [S027](#s027), [S031](#s031), [S040](#s040), [S065](#s065), [S070](#s070), [S090](#s090), [S096](#s096).

<a id="rw-028"></a>
#### RW-028 | P1 | Reproducible build-to-measurement provenance and transparency

**Surface:** Service Block supply chain / TEE qualification  
**Classification:** Direct qualification improvement; claim gating applies immediately

**Importance / architectural relevance.** Attestation of a binary measurement does not independently establish that it corresponds to reviewed source. Add build provenance and transparent admission history without treating an append-only log as proof that the build is safe.

**Minimum implementable output.** Bind source/dependency lockfiles, toolchain/build recipe, SBOM, reproducible artifact digest, workload measurement, reviewer decision, and TCB policy. Rebuild selected artifacts with an independent builder; record nonreproducible components and any alternative assurance profile rather than claiming equivalence. Maintain independently witnessed or principal-verifiable admission/transparency records to detect targeted or rollbacked workload substitutions. Define revocation of vulnerable builds.

**Acceptance tests.** Rebuild one admitted workload independently and compare artifact/measurement outputs. A valid quote for an unreviewed or substituted build fails the claimed assurance profile. Replayed transparency state or a revoked TCB/build is detected. Opaque vendor components remain explicitly declared trust assumptions.

**Evidence to retain:** Build manifest, reproduction script/results, measurement allowlist policy, transparency proof example, and revocation procedure.  
**Dependencies:** [RW-027](#rw-027)  
**Research lineage:** [S002](#s002), [S033](#s033), [S039](#s039), [S053](#s053), [S070](#s070), [S078](#s078).

<a id="rw-029"></a>
#### RW-029 | P1 | Sovereign encrypted state custody and attestation-gated key release

**Surface:** Stateful confidential Service Blocks / memory / recovery  
**Classification:** Direct architecture prototype

**Importance / architectural relevance.** Separate the operator supplying compute from the principal controlling decryption and durable state updates. Preserve modular memory while enabling long-lived private state to survive provider changes without becoming permanently operator-readable.

**Minimum implementable output.** Define SovereignStateEnvelope with ciphertext commitment, canonical version/epoch, principal-controlled key policy, admitted workload profile, key-release conditions, retention, and recovery rules. Use fresh attestation before release and bind releases to the intended workload/session. Design autonomous delegated release with explicit bounds so users need not remain online for every permitted task. Specify recovery, migration fencing, rollback resistance, and revocation; avoid an obligatory central VAMS key custodian.

**Acceptance tests.** The storage or compute operator cannot decrypt outside the admitted workload and policy. Replay an old encrypted snapshot, migrate to a second provider, lose/recover a device, and revoke the old runtime. State version and authority remain singular; undeclared recovery authorities cannot release keys.

**Evidence to retain:** State/key envelope, key-release service contract, recovery ADR, and encrypted-state migration canary.  
**Dependencies:** [RW-006](#rw-006), [RW-013](#rw-013), [RW-027](#rw-027), [RW-028](#rw-028)  
**Research lineage:** [S022](#s022), [S060](#s060), [S070](#s070), [S078](#s078), [S090](#s090), [S096](#s096).

<a id="rw-030"></a>
#### RW-030 | P1 | Scoped compute rights and explicit output-disclosure policy

**Surface:** Confidential data / memory / inference Service Blocks  
**Classification:** Direct service-level control

**Importance / architectural relevance.** Permission to compute over private data is not permission to read or export it. A TEE can protect inputs from a host while the allowed application still leaks them through its result. Keep authorization, attestation, output release, and settlement distinct.

**Minimum implementable output.** Define ComputeRight binding principal, data/object commitment, workload digest, query scope, invocation/budget limits, expiry, and output-disclosure policy. Enforce release through a small output gate with domain-specific controls such as fixed result schemas, minimization, rate/aggregate limits, or a carefully specified privacy mechanism. Model-based leakage classifiers are defense-in-depth, not proof of confidentiality. Do not require rights to be transferable NFTs or tokenized assets.

**Acceptance tests.** An authorized workload cannot return raw protected inputs when only aggregates or a bounded derived result are allowed. Repeated queries cannot exceed policy limits. A valid TEE result still fails if its disclosure is unauthorized; record residual semantic/inference leakage assumptions.

**Evidence to retain:** ComputeRight and OutputReleasePolicy schemas, one private-query Service Block, and exfiltration/disclosure tests.  
**Dependencies:** [RW-004](#rw-004), [RW-027](#rw-027), [RW-029](#rw-029)  
**Research lineage:** [S020](#s020), [S050](#s050), [S060](#s060), [S064](#s064), [S096](#s096).

<a id="rw-031"></a>
#### RW-031 | P1 | Measured confidential-execution capability and performance profiles

**Surface:** Service Block catalog / Composer pricing  
**Classification:** Direct measurement and routing improvement

**Importance / architectural relevance.** Confidential-compute performance depends on hardware, software, topology, and workload. Do not turn vendor-reported benchmark numbers into generic VAMS latency or pricing assumptions.

**Minimum implementable output.** Create ConfidentialExecutionProfile covering CPU/GPU modes, firmware/driver, runtime, parallelism/topology, attestation policy, memory-transfer configuration, and benchmark workload. Measure confidential versus comparable nonconfidential runs for latency, throughput, cost, memory, failure recovery, and verification overhead. Bind results to the tested configuration and qualification epoch; distinguish provider assertions from independently reproduced measurements.

**Acceptance tests.** Changing topology, driver, engine, or security mode invalidates stale benchmark applicability. Composer cannot satisfy a confidential-GPU request with a CPU-only profile. Published capability/pricing records state confidence, workload, and reproducibility rather than one universal TEE-overhead percentage.

**Evidence to retain:** Capability/performance schema, reproducible benchmark harness, and profile-aware routing policy.  
**Dependencies:** [RW-011](#rw-011), [RW-027](#rw-027)  
**Research lineage:** [S027](#s027), [S031](#s031), [S040](#s040), [S065](#s065), [S090](#s090).

<a id="rw-032"></a>
#### RW-032 | P2 | Narrow-TCB and hybrid trusted-controller experiments

**Surface:** Confidential runtime research / specialized Service Blocks  
**Classification:** Bounded research prototype; property-specific only

**Importance / architectural relevance.** Explore separating resource management from protected-state authority and verifying selected accelerator behavior with a small trusted controller. This does not establish arbitrary inference correctness or make every untrusted GPU suitable for confidential work.

**Minimum implementable output.** Compare NACRE/LGT4CG-style narrow trust boundaries and CPU-TEE-controlled untrusted-accelerator patterns against one concrete property, such as a restricted kernel result check or a specified privacy accounting rule. Declare what data the GPU sees, adversary access, verification error bounds, supported dynamic shapes, and trusted code. Model protected-state commits separately from host scheduling authority.

**Acceptance tests.** A malicious accelerator violating the selected property is rejected within the declared assumptions and detection bound. A valid property-specific receipt cannot be upgraded into full inference, privacy, or state-correctness evidence. Measure overhead and unsupported workloads before considering adoption.

**Evidence to retain:** Threat model, small prototype, property-specific evidence profile, and adoption/no-adoption experiment memo.  
**Dependencies:** [RW-027](#rw-027), [RW-030](#rw-030), [RW-034](#rw-034)  
**Research lineage:** [S022](#s022), [S040](#s040), [S050](#s050).

<a id="rw-033"></a>
#### RW-033 | P2 | Host-independent enforcement and DPU-style evidence adapters

**Surface:** High-assurance runtime research / Sentinel  
**Classification:** Optional implementation profile; never a mandatory vendor dependency

**Importance / architectural relevance.** Independent hardware may strengthen observation or quarantine when the application host is compromised. Adopt an interface for stronger assurance rather than making a particular DPU, cloud, or vendor the root of VAMS sovereignty.

**Minimum implementable output.** Define RuntimeIsolationProfile capabilities for agent-process isolation, host-level enforcement, TEE protection, and host-independent observer/enforcer domains. Prototype an external gateway or available hardware adapter. State exactly which traffic/effects it can see and stop; network visibility does not imply visibility into all internal or encrypted computation. Bind independent telemetry to workload identity and policy.

**Acceptance tests.** Compromise the application host in a controlled test; verify only the effects the independent domain is designed to mediate remain enforceable. Loss of observer connectivity downgrades or blocks the high-assurance route. Ordinary VAMS users remain free to select other explicit assurance profiles.

**Evidence to retain:** Isolation-profile schema, independent adapter proof-of-concept, and visibility/failure-mode matrix.  
**Dependencies:** [RW-022](#rw-022), [RW-023](#rw-023), [RW-027](#rw-027)  
**Research lineage:** [S049](#s049), [S071](#s071), [S075](#s075), [S083](#s083).

### 3.4 Verifiable computation and proof qualification

<a id="rw-034"></a>
#### RW-034 | P0 | Scheme-neutral proof statements and explicit assurance profiles

**Surface:** Proof plugins / VDSO / Sentinel / Composer  
**Classification:** Direct admission control; required for any claimed proof guarantee

**Importance / architectural relevance.** Full computation proofs, sampled checks, TEE attestations, authorization proofs, and observations are different products. Also separate deterministic execution, model identity, numerical fidelity, output usefulness, and computational effort.

**Minimum implementable output.** Define ProofEnvelope and ProofSecurityProfile with statement type, exact computation/model commitment, public inputs, program/circuit/verifier digests, scheme/version, parameters/assumptions, codec, setup requirements, coverage, privacy properties, and composition metadata. Encode sampling/detection assumptions separately from cryptographic soundness. Keep authorizationSecurity, proofSecurity, confidentialitySecurity, and settlementSecurity distinct. A policy chooses admissible evidence; no implicit substitution between classes.

**Acceptance tests.** A sampled proof cannot satisfy a full-execution requirement. A TEE receipt cannot masquerade as a mathematical computation proof. A valid proof for different weights, numerical semantics, inputs, or verifier version fails. A wrapper with weaker assumptions is reflected in the resulting security profile.

**Evidence to retain:** Proof/evidence profile schemas, plugin admission rules, scheme-neutral serialization vectors, and downgrade tests.  
**Dependencies:** [RW-001](#rw-001), [RW-002](#rw-002)  
**Research lineage:** [S003](#s003), [S008](#s008), [S015](#s015), [S025](#s025), [S026](#s026), [S034](#s034), [S088](#s088), [S091](#s091).

<a id="rw-035"></a>
#### RW-035 | P1 | Reproducible proof-build provenance and model qualification

**Surface:** ZKML build pipeline / proof adapter qualification  
**Classification:** Direct supply-chain improvement; required before admitting custom circuits

**Importance / architectural relevance.** Proof verification alone does not establish that the verified circuit represents the intended model or that an optimizer preserved semantics. Track model identity and qualification independently from advertised parameter count or proving effort.

**Minimum implementable output.** Build a ProofBuildManifest linking approved weights/model digest, tokenizer/preprocessing, canonical numerical specification, compiler, source circuit, optimizer profile, optimized circuit, verification key, verifier binary, and conformance evidence. Reproduce builds and run differential/adversarial vectors against the reference statement. Treat formal optimizer soundness as a distinct artifact from test coverage. Version and review all changes before qualification.

**Acceptance tests.** Replace weights with a trivial or incorrect model, swap a verification key, alter preprocessing, or change compiler constraints. Qualification must fail or explicitly identify the changed statement. Two independently reproduced builds agree or expose a documented nondeterministic component.

**Evidence to retain:** Reproducible proof-build manifest, model qualification record, reference vectors, and circuit/verifier promotion checks.  
**Dependencies:** [RW-001](#rw-001), [RW-034](#rw-034)  
**Research lineage:** [S025](#s025), [S033](#s033), [S034](#s034), [S088](#s088), [S091](#s091).

<a id="rw-036"></a>
#### RW-036 | P1 | Explicit numerical semantics and deterministic-inference qualification

**Surface:** Inference providers / proof reference runtime  
**Classification:** Direct specification and benchmark work

**Importance / architectural relevance.** A model hash does not fully specify executed inference. Batching, floating-point reductions, cache state, scheduling, tokenizer, and sampling can matter. Determinism is one declared property, not proof that the implementation computes the intended model.

**Minimum implementable output.** Define NumericalExecutionProfile and, where needed, DeterministicInferenceProfile binding model, tokenizer, dtype, quantization, engine/kernel configuration, sampler state, cache semantics, and equivalence rule. Choose exact equality, a specified numeric tolerance, or a stochastic contract according to the application. Compare the claimed canonical computation with the user-facing reference model. Do not require bitwise equality for all generic agent tasks or unsupported heterogeneous hardware.

**Acceptance tests.** Vary batching, prefill/decode, KV reuse/eviction, scheduling, restart, and supported hardware while holding declared inputs fixed. A route advertising determinism passes its exact criterion; nondeterminism is disclosed rather than hidden. A repeatable but wrong model still fails reference correctness checks.

**Evidence to retain:** Numerical profile, inference equivalence corpus, reproducibility report, and receipt binding to configuration.  
**Dependencies:** [RW-034](#rw-034), [RW-035](#rw-035)  
**Research lineage:** [S001](#s001), [S027](#s027), [S088](#s088), [S091](#s091).

<a id="rw-037"></a>
#### RW-037 | P2 | Composable proof graphs and segmented inference proving

**Surface:** Proof Service Blocks / aggregator research  
**Classification:** Bounded research prototype

**Importance / architectural relevance.** Explore model partitioning and cryptographically linked sub-proofs while preserving a single complete statement. The modular proving market is an optional economic extension, not an immediate protocol requirement.

**Minimum implementable output.** Define CompositeProofEnvelope with graph/topology identity, segment ranges, model/program commitments, boundary input/output commitments, predecessor links, backend versions, aggregation rules, and final statement. Prototype a small model with at least two proving segments. Specify ordering, completeness, and boundary consistency checks; account for private activations and data movement.

**Acceptance tests.** Omit, duplicate, reorder, or substitute a segment and mismatch a boundary activation; aggregation rejects. Compare full proving with segmented proving for total time, peak memory, communication, verifier cost, and privacy, not only best-case parallel speedup.

**Evidence to retain:** Proof-DAG schema, small compositional prover demo, negative linkage tests, and economics benchmark.  
**Dependencies:** [RW-034](#rw-034), [RW-035](#rw-035), [RW-036](#rw-036)  
**Research lineage:** [S003](#s003), [S015](#s015), [S026](#s026), [S088](#s088).

<a id="rw-038"></a>
#### RW-038 | P2 | Sound circuit-optimization and debloating experiment

**Surface:** ZKML compiler research  
**Classification:** Bounded optimization experiment; no production shortcut

**Importance / architectural relevance.** Remove redundant constraints only with justified semantics. A faster proof over an underconstrained circuit is a security failure, not an optimization success.

**Minimum implementable output.** Select one fixed circuit and optimizer version. Preserve the pre-optimization circuit, optimization log, abstract-analysis or proof artifact, final circuit, and verification-key linkage. Test adversarial witnesses at range/sign/bit-decomposition boundaries. Evaluate interaction with segmentation separately because a globally redundant check may not be redundant after partitioning.

**Acceptance tests.** Invalid witnesses excluded by the original specification remain excluded. Removing a necessary check is detected by the qualification process. Report full prover/verifier cost, proof size, and soundness assumptions; differential tests alone must not be labeled a general soundness proof.

**Evidence to retain:** Optimization provenance extension, reproducible before/after benchmark, and adversarial witness suite.  
**Dependencies:** [RW-035](#rw-035)  
**Research lineage:** [S025](#s025), [S003](#s003).

<a id="rw-039"></a>
#### RW-039 | P2 | Sampled verification with explicit coverage and anti-grinding controls

**Surface:** Verifiable-inference audit research / proof policy  
**Classification:** Bounded research profile; never silently full verification

**Importance / architectural relevance.** Sampling can reduce proving cost but leaves untested computation. Verification of sampled chunks does not prove that every chunk is correct or that a quantized canonical model matches the advertised floating-point model.

**Minimum implementable output.** Commit the complete trace before selecting unpredictable challenges. Bind trace, task, epoch, challenge source, sample policy, total/sample counts, and abort/retry policy. State detection probability under the actual corruption model. For uniform sampling without replacement over N eligible chunks with m fixed corrupt chunks, use 1 - C(N-m,k)/C(N,k); adjust for exclusions and adaptive behavior. Address challenge grinding and repeated aborts. Keep numerical fidelity separate.

**Acceptance tests.** Plant one and several corrupt chunks; compare empirical detection with the stated bound. Reject post-challenge trace changes and repeated challenge selection. Insufficient coverage cannot satisfy a stronger task policy. Measure proof, verification, trace storage, and privacy costs.

**Evidence to retain:** SampledProofProfile, challenge protocol, fault-injection results, and explicit assurance/economic policy.  
**Dependencies:** [RW-034](#rw-034), [RW-035](#rw-035), [RW-036](#rw-036)  
**Research lineage:** [S003](#s003), [S088](#s088), [S091](#s091).

<a id="rw-040"></a>
#### RW-040 | P2 | Alternative and post-quantum proof backend evaluation

**Surface:** Proof research / crypto-agility  
**Classification:** Bounded comparative research; adoption requires fresh verification

**Importance / architectural relevance.** Keep Akita/Longfellow and other proof families as candidates, not approved dependencies. Separate prospective private-authorization proofs from inference proofs and account for any classical wrapper or settlement path.

**Minimum implementable output.** After independently verifying the cited work and implementations, benchmark one bounded authorization predicate or small computation under candidate backends. Record assumption set, security parameters, trusted setup, prover memory/time, proof size, verifier cost, distributed proving support, and implementation maturity. Assess whether a PQ property survives serialization, aggregation, compression, signatures, and settlement. Do not infer security from a product label.

**Acceptance tests.** The same explicit statement is verified across backends or differences are documented. Unsupported or downgraded parameters fail admission. No experimental result changes the production security label or cryptosuite policy without independent review.

**Evidence to retain:** Backend comparison matrix, test vectors, prototype adapter, and cryptographic review/adoption decision.  
**Dependencies:** [RW-002](#rw-002), [RW-034](#rw-034), [RW-035](#rw-035)  
**Research lineage:** [S008](#s008), [S015](#s015), [S017](#s017), [S026](#s026).

### 3.5 Cross-domain orchestration and data availability

<a id="rw-041"></a>
#### RW-041 | P0 | Canonical cross-domain statements and explicit lane policies

**Surface:** VDSO / cross-chain adapters / VIR  
**Classification:** Direct control; applies to enabled cross-domain transitions

**Importance / architectural relevance.** Cross-chain message semantics, transport, verification, routing, execution, and state authority must remain separate. A valid source proof is not proof that the destination interpreted identities, amounts, units, or effects correctly.

**Minimum implementable output.** Define CrossDomainLanePolicy and canonical messages covering domains, operation/message ID, source object/state commitment, principal and role, source authority epoch, typed amount/asset/fee units, semantic-adapter version, finality/verifier policy, destination action, nonce, expiry, and execution rules. Normalize through versioned deterministic adapters. Relayers transport evidence but gain no authority. Preserve one authoritative state-transition history per domain; this does not require one physical machine or central operator.

**Acceptance tests.** Test foreign-chain identity confusion, sign/range/decimal errors, parser disagreement, unknown operation types, mismatched domains, and adapter upgrades. A valid proof attached to the wrong semantic statement fails. Destination policy cannot be weakened by changing the transport.

**Evidence to retain:** Lane-policy and message schemas, canonical vectors, semantic-adapter specification, and heterogeneous-chain negative tests.  
**Dependencies:** [RW-001](#rw-001), [RW-003](#rw-003), [RW-005](#rw-005), [RW-006](#rw-006)  
**Research lineage:** [S036](#s036), [S041](#s041), [S048](#s048), [S079](#s079), [S084](#s084), [S092](#s092).

<a id="rw-042"></a>
#### RW-042 | P0 | Source-domain invariant and economic-bound checks before export

**Surface:** VDSO export admission / bridge/mint policy  
**Classification:** Direct control; only the declared invariants are guaranteed

**Importance / architectural relevance.** Valid finality, conservation, and signatures can coexist with an unauthorized or economically invalid source transition. Add concrete source-health predicates rather than assuming that an accepted source event is safe to export.

**Minimum implementable output.** For each transition class, declare checkable source predicates: issuance authorization, supply/accounting bounds, role validity, state version, escrow/reservation, quarantine status, and permitted value limits. Bind the evaluated invariant set and source context into export evidence. Deny or quarantine failed or unknown required checks. Do not invent a generic SourceStateValidity flag claiming that every possible source-chain bug has been excluded.

**Acceptance tests.** Construct a finalized and correctly signed source event that violates a declared mint, escrow, or authority invariant while preserving bridge conservation. Export must fail. Negative/overflowing fee arithmetic and unauthorized administrative identity derivation fail before destination effects.

**Evidence to retain:** Per-operation invariant registry, source-health evidence, bounded mint/export policy, and valid-proof/invalid-state regressions.  
**Dependencies:** [RW-008](#rw-008), [RW-041](#rw-041)  
**Research lineage:** [S014](#s014), [S018](#s018), [S041](#s041), [S058](#s058).

<a id="rw-043"></a>
#### RW-043 | P0 | Bounded signer roles and operational trust-domain independence

**Surface:** Bridge/governance signing / key operations  
**Classification:** Direct key and infrastructure safety control

**Importance / architectural relevance.** A threshold of keys inside one compromised administrative domain is not independent authority. Bind signer role and current epoch to bounded operations, and make compromise response effective at the actual verification point.

**Minimum implementable output.** Inventory signer/operator/cloud/HSM or TEE dependencies, recovery paths, RPC observations, and deployment/update authority. Separate roles for mint, export, upgrade, observation, and emergency quarantine. Enforce operation/epoch limits and key rotation. Choose explicit threshold and independence policies for high-consequence lanes; do not assert generic N-of-M Byzantine safety without a defined threat and quorum-intersection model. Retired or compromised authorities must be fenceable.

**Acceptance tests.** A valid retired-key signature fails. A current signer cannot exceed its operation role or economic bound. Simulate loss of one cloud/admin domain and show which guarantees remain; correlated key placement cannot satisfy an independence requirement.

**Evidence to retain:** Signer trust-domain map, bounded role policy, rotation/compromise runbook, and valid-signature-but-invalid-authority tests.  
**Dependencies:** [RW-002](#rw-002), [RW-006](#rw-006), [RW-041](#rw-041)  
**Research lineage:** [S005](#s005), [S018](#s018), [S039](#s039), [S058](#s058), [S084](#s084).

<a id="rw-044"></a>
#### RW-044 | P0 | Cross-domain finality, replay protection, and uncertain-settlement handling

**Surface:** VDSO / reservation and settlement adapters  
**Classification:** Direct cross-domain safety control

**Importance / architectural relevance.** Messages can be delivered more than once, arrive out of order, or refer to nonfinal/reorganized source state. Keep semantic admission, external execution, and settlement distinct; asynchronous cross-chain operations are not automatically atomic.

**Minimum implementable output.** Bind finality evidence and its policy to each source state, plus lane, nonce/sequence, authority epoch, destination, and operation ID. Maintain durable replay/consumption state and explicit reservations. On reorganization, missing proof, timeout, or uncertain settlement, retain an indeterminate/quarantined state until the specified resolution rule applies. Do not automatically unlock or refund value when a late commit remains possible. Define compensation as a separate authorized operation.

**Acceptance tests.** Inject duplicate/out-of-order messages, stale epochs, source reorganization, late destination commitment, destination restart, and missing acknowledgements. At most one authorized acceptance occurs under the declared contract, and uncertainty cannot create a second spend or authoritative history.

**Evidence to retain:** Cross-domain state machine, replay/finality policy, reconciliation rules, and asynchronous fault-injection tests.  
**Dependencies:** [RW-008](#rw-008), [RW-009](#rw-009), [RW-041](#rw-041), [RW-043](#rw-043)  
**Research lineage:** [S023](#s023), [S044](#s044), [S048](#s048), [S074](#s074), [S079](#s079), [S084](#s084), [S092](#s092).

<a id="rw-045"></a>
#### RW-045 | P1 | Independent cross-domain observations with explicit abstention

**Surface:** Sentinel / chain observers / evidence normalization  
**Classification:** Direct observability improvement; heuristics never authorize settlement

**Importance / architectural relevance.** Multiple observations are useful only with declared independence and semantics. Heterogeneous chains and explorers can disagree, and approximate transaction correlation must be allowed to abstain.

**Minimum implementable output.** Define CrossDomainObservation with source event/root, extractor and schema version, finality reference, observer identity/trust domain, destination correlation method, and MATCH/NO_MATCH/AMBIGUOUS status. Use independently operated observation paths where required. Separate deterministic proof verification from probabilistic forensic matching and provider health scores. An observer quorum is not a substitute for the lane's source-consensus proof.

**Acceptance tests.** Return mismatched explorer/RPC data and omit a destination event; the system abstains instead of forcing a match. Two endpoints backed by the same operator do not count as independent by default. A high heuristic correlation score cannot release funds.

**Evidence to retain:** Observation schema, independent observer adapters, ambiguity fixtures, and deterministic-versus-heuristic policy boundary.  
**Dependencies:** [RW-041](#rw-041), [RW-044](#rw-044)  
**Research lineage:** [S011](#s011), [S013](#s013), [S036](#s036), [S048](#s048), [S085](#s085).

<a id="rw-046"></a>
#### RW-046 | P2 | Authenticated multi-hop delivery history and pluggable interoperability adapters

**Surface:** CLR / VDSO transport research  
**Classification:** Bounded interoperability prototype; no external protocol dependency

**Importance / architectural relevance.** Preserve verification provenance across heterogeneous routes without creating another state authority. Use XIR, XIM, CLPR, and CCIP-style separation as comparators, not as automatically verified or mandatory VAMS integrations.

**Minimum implementable output.** After source/spec verification, define CrossDomainDeliveryChain with original message commitment, ordered hops, each protocol/verifier/semantic-adapter identity, trust-anchor version, receipts, finality policy, and destination binding. Prototype a local two-hop route first. Require every hop to satisfy the end-to-end policy; extra hops do not automatically add assurance and may introduce weaker assumptions. Keep transport and executor substitution explicitly controlled.

**Acceptance tests.** Reorder, omit, duplicate, or substitute a hop; reject. A route containing a weaker verification policy cannot satisfy a stronger end-to-end requirement. Relayer failure affects delivery, not authority. Compare latency, proof cost, availability, and new trust dependencies.

**Evidence to retain:** Protocol-comparison ADR, delivery-chain schema, two-hop prototype, and end-to-end trust analysis.  
**Dependencies:** [RW-041](#rw-041), [RW-044](#rw-044), [RW-045](#rw-045)  
**Research lineage:** [S011](#s011), [S048](#s048), [S079](#s079), [S084](#s084), [S092](#s092).

<a id="rw-047"></a>
#### RW-047 | P2 | Aggregate cross-domain checkpoints with logical epochs

**Surface:** VDSO proof aggregation research  
**Classification:** Bounded research design; not shared-clock consensus

**Importance / architectural relevance.** An aggregate commitment can make multiple domain states easier to reference, but does not by itself establish simultaneity, causal consistency, or a new canonical writer. Heterogeneous chains cannot be assumed to share finality clocks.

**Minimum implementable output.** Define CrossDomainCheckpoint with logical coordination epoch, domain roots, per-domain authority epochs and finality evidence, relevant message frontiers, DA/evidence references, and aggregate commitment. Specify an admissible consistent cut or dependency rule rather than matching wall-clock timestamps. Preserve each domain's authority; the aggregate is evidence, not permission to mutate constituent states.

**Acceptance tests.** Combine roots from incompatible causal frontiers, stale epochs, or nonfinal states; reject the claimed checkpoint profile. Verify that the aggregate cannot write to either source domain. Measure proof/reference savings versus construction and availability cost.

**Evidence to retain:** Checkpoint schema, consistency assumptions, synthetic Polygon/Cardano-style fixture, and no-second-writer tests.  
**Dependencies:** [RW-044](#rw-044), [RW-048](#rw-048)  
**Research lineage:** [S048](#s048), [S056](#s056), [S092](#s092).

<a id="rw-048"></a>
#### RW-048 | P0 | DA admission based on independently verified evidence

**Surface:** DA adapters / evidence storage / Sentinel  
**Classification:** Direct control; required when availability is part of a guarantee

**Importance / architectural relevance.** A provider receipt, successful submission call, and content availability are distinct facts. Fail closed on mock or unverifiable paths, and do not equate one successful retrieval with indefinite retention or network-wide recoverability.

**Minimum implementable output.** Define DAReceipt/EvidenceAvailabilityProfile binding network, namespace, payload commitment, publication reference, finality, inclusion evidence, retrieval challenge/result, observer identity, verification method, and time/retention scope. Independently verify commitment and retrieve the intended bytes using a separate observation path where feasible. Store sensitive evidence encrypted with access and retention policy. Qualify each actual adapter at a pinned version; existing provider readiness is not assumed.

**Acceptance tests.** A fabricated receipt, missing blob, wrong bytes, stale publication, or submitting-adapter self-assertion cannot satisfy the required profile. Simulate an unavailable independent observer and later content loss; claims downgrade or fail according to policy rather than remaining permanently available.

**Evidence to retain:** DA evidence schema, adapter qualification tests, submit/verify/retrieve canary, and explicit retention guarantees.  
**Dependencies:** [RW-001](#rw-001), [RW-002](#rw-002)  
**Research lineage:** [S004](#s004), [S011](#s011), [S016](#s016), [S075](#s075).

<a id="rw-049"></a>
#### RW-049 | P1 | DA security classes and network-aware availability measurement

**Surface:** DA routing / Composer / availability policy  
**Classification:** Direct policy and measurement work; DA protocol redesign deferred

**Importance / architectural relevance.** Route by required availability/security properties rather than provider name or cheapest latency. Publication, sampling, retrieval, recoverability, censorship resistance, and retention are separate dimensions with explicit assumptions.

**Minimum implementable output.** Define workload profiles for disposable telemetry, checkpoints, dispute evidence, and governance-critical records. Map profiles to commitment/encoding scheme, retrieval or sampling method, sample policy, reconstruction assumptions, observer diversity, finality, and retention. Evaluate network routing and peer-discovery dependencies. Avoid invented confidence scores detached from an adversary/encoding model; experimental coded-array changes remain provider research.

**Acceptance tests.** Withhold fragments, correlate observers, delay discovery, and expire retention. The router cannot satisfy a critical evidence profile using a weaker published-only or self-reported path. Benchmark security/cost tradeoffs and explain availability uncertainty.

**Evidence to retain:** DA class policy, provider capability matrix, adversarial sampling/retrieval tests, and route-selection rules.  
**Dependencies:** [RW-048](#rw-048)  
**Research lineage:** [S004](#s004), [S011](#s011), [S036](#s036).

### 3.6 Discovery, economics, collective governance, and delivery gates

<a id="rw-050"></a>
#### RW-050 | P1 | Separate sovereign registration from discovery and resolution

**Surface:** Registry / Composer / VNS and vams:// planning  
**Classification:** Direct architectural separation; no central root required

**Importance / architectural relevance.** Registration authority, capability search, ranking, and trust evaluation should not collapse into one service. Scalable discovery is compatible with sovereign namespaces only if a resolver cannot invent identity or grant authority.

**Minimum implementable output.** Keep signed/versioned agent and Service Block commitments authoritative in their selected domains. Permit replaceable indexes/resolvers to return capability metadata, manifest roots, freshness, and revocation references. Verify the selected record against its sovereign root before activation. Support multiple roots, resolver choice, caching with bounds, and direct self-hosted resolution. A URI or naming scheme alone provides no post-quantum, privacy, or availability guarantee.

**Acceptance tests.** A malicious resolver returns a forged, stale, censored, or substituted record; authority verification rejects it or an alternative resolver can be used. Taking one discovery operator offline does not invalidate identities or force a global re-registration.

**Evidence to retain:** Registry/resolver separation ADR, signed discovery record, multi-root resolver prototype, and substitution/failover tests.  
**Dependencies:** [RW-005](#rw-005), [RW-011](#rw-011)  
**Research lineage:** [S006](#s006), [S032](#s032), [S055](#s055), [S077](#s077).

<a id="rw-051"></a>
#### RW-051 | P1 | Metadata-only discovery and least-privilege capability activation

**Surface:** Composer / registry client / credential broker  
**Classification:** Direct usability and least-privilege improvement

**Importance / architectural relevance.** Knowing that a Service Block exists must not imply possession of its credentials or authority. Distinguish discoverable metadata, activated interfaces, and effective permission while reducing unnecessary tool/context exposure.

**Minimum implementable output.** Expose a searchable catalog first, then activate a narrow interface only after trusted authorization. Issue short-lived CapabilityLeases bound to task, principal, target/version, argument/resource limits, budget, and expiry. Revocation and implementation changes invalidate the lease. Learned roles or skills may propose activation but cannot define the authority ceiling.

**Acceptance tests.** An agent can discover thousands of services while possessing no invocation authority. An expired lease, fabricated role, changed implementation, or over-budget request fails. Activation cannot leak broader provider credentials into model context.

**Evidence to retain:** CapabilityLease schema, progressive-discovery adapter, and discovery-without-authority tests.  
**Dependencies:** [RW-004](#rw-004), [RW-005](#rw-005), [RW-011](#rw-011), [RW-050](#rw-050)  
**Research lineage:** [S023](#s023), [S039](#s039), [S043](#s043), [S051](#s051), [S077](#s077).

<a id="rw-052"></a>
#### RW-052 | P1 | Separate service quality, model identity, proof validity, and economic claims

**Surface:** Agentic Economy / provider qualification / pricing  
**Classification:** Direct economic-model clarification

**Importance / architectural relevance.** A valid proof establishes its stated computation, not useful output quality, advertised model scale, or physical effort. Prevent provider rewards from relying on unsupported claims such as a nominal parameter count.

**Minimum implementable output.** Define distinct ExecutionEvidence, ModelQualification, ServiceQuality, ResourceMeasurement, and PricingBasis fields. Bind approved weights and numerical semantics when a specific model is contracted. Decide whether payment is for a result, reserved resources, or measured work; do not penalize legitimate efficiency in result-priced jobs. Require independently qualified measurement only when billing actually depends on resources or effort. Make assurance class visible to buyers.

**Acceptance tests.** A trivial substituted model with a valid proof cannot satisfy a contract for different approved weights. An optimized implementation meeting a result contract remains eligible. Sampled assurance cannot earn a full-proof premium without explicit buyer policy.

**Evidence to retain:** Qualification/pricing schema, model-substitution tests, and proof-versus-economic-claim acceptance rules.  
**Dependencies:** [RW-031](#rw-031), [RW-034](#rw-034), [RW-035](#rw-035)  
**Research lineage:** [S003](#s003), [S034](#s034), [S065](#s065), [S067](#s067), [S088](#s088).

<a id="rw-053"></a>
#### RW-053 | P2 | Optional evidence-quorum authorization for high-consequence actions

**Surface:** Heart authorization / governance / critical VDSO lanes  
**Classification:** Bounded high-assurance prototype; no change to state authority

**Importance / architectural relevance.** Multiple policy authorities may reduce reliance on one decision service, but only under a defined fault, independence, and quorum model. Quorum approval and canonical state writing are separate roles.

**Minimum implementable output.** Define AuthorizationEvidenceSet binding exact request/formation, policy version, contextual evidence, authority-node identity, decision, expiry, and policy epoch. Specify permit/deny combination, quorum intersection, tolerated failures, policy-update activation, and availability tradeoffs. Verify the set before one authoritative state transition. Use a principal/domain-selected authority set, not a universal VAMS approval council.

**Acceptance tests.** Compromise the declared tolerated subset, partition nodes, present conflicting policy epochs, and replay old signatures. Unauthorized or ambiguous permits fail under the declared model. Lack of quorum fails closed; ordinary low-risk work is not forced through this path.

**Evidence to retain:** Quorum-policy ADR, signed evidence-set prototype, fault-model tests, and availability/cost evaluation.  
**Dependencies:** [RW-004](#rw-004), [RW-005](#rw-005), [RW-006](#rw-006), [RW-025](#rw-025)  
**Research lineage:** [S008](#s008), [S012](#s012), [S072](#s072), [S084](#s084), [S085](#s085).

<a id="rw-054"></a>
#### RW-054 | P1 | Principal-controlled payment policy across execution providers

**Surface:** Payment Service Blocks / wallets / Agentic Economy  
**Classification:** Direct payment-adapter control; cross-rail unification remains optional

**Importance / architectural relevance.** Delegating payment execution must not transfer the principal's spending authority to a processor, model, or credential intermediary. Reuse the shared budget/effect contracts instead of inventing a separate payment trust model.

**Minimum implementable output.** Bind a PaymentAuthorization to principal/issuer policy, exact merchant or recipient, asset/currency, amount and fees, recurrence, budget, expiry, operation identity, and provider contract. Revalidate at the final wallet/issuer sink. Keep wallet keys and bank credentials out of model context. Cross-rail adapters declare their own settlement, cancellation, chargeback, and identity assumptions.

**Acceptance tests.** A legitimate payment to one counterparty cannot be redirected or increased by the provider. Retries cannot exceed reserved exposure. Merchant, fee, currency, or recurrence changes require new authorization; a processor's own credentials do not enlarge the grant.

**Evidence to retain:** Payment authorization profile, one adapter integration, and recipient/amount/retry substitution tests.  
**Dependencies:** [RW-004](#rw-004), [RW-008](#rw-008), [RW-009](#rw-009)  
**Research lineage:** [S023](#s023), [S060](#s060), [S064](#s064).

<a id="rw-055"></a>
#### RW-055 | P2 | Counterfactual and negative-twin review as advisory verification

**Surface:** Sentinel review Service Blocks  
**Classification:** Bounded model-assisted experiment; not an authorization root

**Importance / architectural relevance.** Automated correction can introduce new errors and new effects. Counterfactual action comparisons may help reviewers, but a preferred alternative remains an untrusted new proposal.

**Minimum implementable output.** Prototype evidence-grounded alternative-action review using trusted user intent and trace evidence, isolated from attacker-controlled conclusions where possible. Compare original and proposed actions in both presentation orders, track uncertainty, and retain no-change as an option. Route every substituted action through fresh formation, authorization, budget, and effect checks. Keep model preference outside consensus and slashing.

**Acceptance tests.** Test correct originals, malicious alternatives, ambiguous evidence, and ordering bias. Measure success-to-failure regressions as well as repairs. No reviewer can execute a replacement directly or reuse an approval for a materially different action.

**Evidence to retain:** Review experiment harness, decision/evidence schema, regression measurements, and strict reauthorization integration.  
**Dependencies:** [RW-003](#rw-003), [RW-004](#rw-004), [RW-024](#rw-024)  
**Research lineage:** [S030](#s030), [S066](#s066), [S094](#s094).

<a id="rw-056"></a>
#### RW-056 | P1 | Typed multi-principal coordination and evidence-based consequences

**Surface:** Agentic Economy / agent interaction protocols / Sentinel  
**Classification:** Direct protocol improvement; autonomous reputation markets are deferred

**Importance / architectural relevance.** Connectivity does not establish legitimate coordination across independent principals. Formalize offers, acceptance, duties, cancellation, review, and disputes while preventing natural-language judgments from becoming automatic punitive authority.

**Minimum implementable output.** Define a bounded interaction protocol with principal/delegation identity, typed commitments, deadlines, state transitions, artifacts, evidence requirements, and dispute/appeal paths. Link accepted duties to the durable task ledger and monetary limits. Distinguish provable violations from low-confidence quality judgments. Keep reputation and any penalties proportional to agreed policy and independently verifiable evidence.

**Acceptance tests.** A malicious participant cannot fabricate another principal's acceptance, force an unauthorized duty, obtain reward from an unverified completion, or cause slashing with a persuasive accusation. Timeouts, abstentions, contradictory evidence, and appeals have explicit outcomes.

**Evidence to retain:** Multi-principal interaction schema, a small coordination canary, and false-acceptance/false-accusation tests.  
**Dependencies:** [RW-004](#rw-004), [RW-005](#rw-005), [RW-013](#rw-013), [RW-025](#rw-025)  
**Research lineage:** [S006](#s006), [S013](#s013), [S045](#s045), [S067](#s067), [S085](#s085), [S089](#s089), [S095](#s095).

<a id="rw-057"></a>
#### RW-057 | P0 | A consolidated adversarial conformance and fault-injection suite

**Surface:** Repository testing / Phase-6 evidence generation  
**Classification:** Direct delivery requirement; coverage follows enabled capabilities

**Importance / architectural relevance.** Turn recurring research recommendations into reproducible failure tests rather than another collection of security diagrams. IntentFuzz/LIMBO-style methodology is useful even before any particular upstream research implementation is adopted.

**Minimum implementable output.** Create deterministic fixtures and property tests for approval substitution, stale authority, delegation amplification, budget races, late/duplicate effects, malformed cross-domain semantics, proof-profile downgrade, quote mix-and-match, hidden communication, context poisoning, and trace deletion. Use isolated local services or approved testnets, canary assets, and no real secrets. Pin seeds/configuration and retain machine-readable results. Map each test to a work item and declared guarantee.

**Acceptance tests.** Each enabled P0 guarantee has a failing-negative and a valid-positive case. Fault injection actually reaches the target boundary. Flaky or unexecuted tests cannot appear as passing evidence; results identify the exact commit, environment, and dependencies.

**Evidence to retain:** Adversarial test catalog, runnable fixtures, invariant/property tests, and machine-readable evidence bundle.  
**Dependencies:** None; may begin independently.  
**Research lineage:** [S032](#s032), [S044](#s044), [S049](#s049), [S052](#s052), [S069](#s069), [S074](#s074), [S075](#s075), [S076](#s076), [S081](#s081), [S082](#s082), [S086](#s086), [S087](#s087), [S093](#s093).

<a id="rw-058"></a>
#### RW-058 | P0 | Evidence-based admission, quarantine, and release claims

**Surface:** Service Block admission / deployment governance  
**Classification:** Direct release gate; no unsupported readiness claims

**Importance / architectural relevance.** The chat's earlier statements about current VAMS implementation are not a verified code audit. Before implementing, locate the actual primitives; before promoting, require evidence for enabled paths. Keep incomplete integrations explicitly disabled rather than widening Phase-6 scope.

**Minimum implementable output.** For every capability, record implementation/version, status, authority owner, evidence profile, tests, dependencies, limitations, and enable/disable decision. Distinguish proposed, prototype, qualified, enabled, quarantined, and retired. Use local/domain-authorized quarantine and recovery; no central universal kill switch. Require independent review for high-consequence changes and requalification after material policy, runtime, model, verifier, or adapter updates.

**Acceptance tests.** An unimplemented, mocked, stale, or failed adapter cannot become eligible through configuration alone. Missing optional P1/P2 work does not block a disabled capability; enabled P0 claims must have evidence. Quarantine fences new effects without erasing history or pretending to undo committed actions.

**Evidence to retain:** Capability readiness matrix, conditional release checklist, evidence bundle manifest, and scoped quarantine/recovery runbook.  
**Dependencies:** [RW-001](#rw-001), [RW-057](#rw-057)  
**Research lineage:** [S023](#s023), [S027](#s027), [S033](#s033), [S039](#s039), [S043](#s043), [S063](#s063), [S075](#s075), [S086](#s086), [S087](#s087).

<a id="research-update"></a>
### 3.7 Requested research update: September 29-October 4, 2026

**Added:** October 5, 2026. These four work packages extend the original consolidation; they do not constitute a fresh audit of VAMS or revalidation of S001-S096. All version mappings below are **proposed engineering implications** using Section 1.2's design framing, not verified claims about code in v0.4 or v0.8. The new names are conceptual profiles of existing records, not four mandatory new subsystems.

| Priority | Work | What it changes for VAMS |
|---|---|---|
| **P0** | [Autonomous Agent Certification Protocol (AACP) - Oct 4](#rw-059) | Separate *demonstrated capability* from *authorization* and bind certification to the exact runtime configuration. |
| **P0** | [GitLab AI Gateway sandbox escape CVE-2026-90970](#rw-060) | Treat prompts, templates, and flow definitions as hostile configuration; prevent their conversion into ambient execution authority. |
| **P1** | [Bits Under ZK-LLM - Sep 29](#rw-061) | Make quantization and arithmetic semantics part of the ZK proof identity. |
| **P0/P1** | [NEAR Intents Omni exploit - Oct 1](#rw-062) | Evaluate cross-chain route health independently from chain health and application health. |

**Priority boundary.** RW-059 is P0 for certification-gated or certification-backed admission claims; adopting AACP itself is optional. RW-060 is P0 wherever attacker-influenced configuration reaches rendering or execution. RW-061 is P1 for numerical qualification and optimization; refusing the wrong proof identity remains the existing P0 requirement in RW-034. RW-062 contains a P0 effect-admission gate for enabled cross-domain routes and a P1 improvement to independent monitoring and recovery. Count it once as a mixed-priority package.

<a id="rw-059"></a>
#### RW-059 | P0 | Configuration-bound capability certification without authority amplification

**Surface:** Service Block qualification / Heart policy / Sentinel / runtime admission  
**Classification:** Direct admission control; optional interoperability with an experimental draft

**Core finding.** Nitzan Levi and Oren Yeger's AACP draft-00, submitted October 4, separates evaluated capability from permission. A signed Agent Certification Credential (ACC) binds an evaluation profile to an agent configuration. It can be an input to authorization, but cannot grant access by itself. The draft also requires trusted evidence connecting the running configuration to the evaluated one; agent-only assertions are insufficient for high-risk capabilities. It is an individual Internet-Draft with intended Experimental status, not an adopted standard. [Primary draft, Sections 3-5 and 8](https://datatracker.ietf.org/doc/html/draft-levi-agent-certification-00); [submission history](https://datatracker.ietf.org/doc/draft-levi-agent-certification/history/).

**Importance / architectural relevance.** A driving test demonstrates skill; it does not give the driver permission to take someone else's car. Likewise, a qualified Service Block should not gain new resources, spending limits, or delegation rights from its certificate. Heart decides whether this principal may perform this effect now; Sentinel assesses the evidence behind the qualification. Composer may use a qualification to select a service, but selection cannot bypass the effect gate.

**Actionable VAMS v0.4-v0.8 implications / minimum implementable output.**

- **v0.4-facing Service Block contract:** add a `CapabilityQualification` profile to the existing provider record. Bind a capability identifier, qualification profile/version, evaluation-artifact commitment, evaluated configuration commitment, issuer identity, validity interval, and evidence reference. Display the scope of the qualification rather than a universal safe-agent badge.
- **v0.8-facing evidence and Heart contract:** carry qualification evidence separately from the principal's current capability grant. Require both only when local policy demands qualification. Link the runtime configuration commitment to the resolved Service Block implementation, model, instructions, tools, relevant policies, sandbox, and effect adapters. Obtain the running commitment from an independently trusted deployment/enforcement source with a declared freshness bound.
- **Lifecycle:** invalidate qualification after changes to its bound elements; re-evaluate the affected capability. Keep certificate revocation and authority revocation separate. Persist the qualification's provenance across restart, then recheck configuration and current authority before new effects.
- **Sovereign trust policy:** let each principal/domain choose accepted issuers and evaluation profiles. Do not introduce a compulsory global certifier. Encrypted evidence storage and access-controlled commitments should protect sensitive evaluation material.

**Acceptance tests.** Present a valid certificate without a current grant: deny. Present a current grant without a certificate where policy requires one: deny. Add a privileged tool or replace the runtime after evaluation: deny use of the old qualification. Reject wrong issuer, audience, expired/revoked evidence, stale runtime evidence, and the wrong capability/profile. Restart a certified agent after authority revocation: retain its history but deny the effect. A failed mandatory safety test cannot be averaged away by a strong aggregate score.

**Challenges / invalidations.** Certification covers defined evaluation conditions, not every future input. Eval overfitting, compromised issuers, runtime substitution, and prompt injection remain concerns identified by the draft's security section. [AACP, Sections 9-11](https://datatracker.ietf.org/doc/html/draft-levi-agent-certification-00). For VAMS, this challenges any equation of registration, benchmark success, or certification with permission. The proposal is invalidated operationally if the runtime evidence producer shares the compromised agent's authority or cannot establish which implementation actually runs. In that case the qualification must remain advisory for consequential effects.

**Speculative implications - not a release requirement.** Portable qualification could support an Agentic Economy market for independently evaluated Service Blocks. Competing certifiers might reduce single-provider dependence, but issuer correlation, test gaming, privacy, and appeals need separate study. Certification should not automatically trigger rewards, slashing, or a safety guarantee.

**Evidence to retain:** Qualification schema, configuration-binding specification, issuer/profile trust policy, signed evaluation record, runtime evidence, and mismatch/revocation results.  
**Dependencies:** [RW-001](#rw-001), [RW-004](#rw-004), [RW-006](#rw-006), [RW-011](#rw-011), [RW-026](#rw-026), [RW-058](#rw-058).  
**Research lineage / primary references:** [S097](#s097), AACP draft-00, especially Sections 3-5, 8-11; no upstream implementation or VAMS integration has been reproduced here.

<a id="rw-060"></a>
#### RW-060 | P0 | Contain hostile prompt templates and flow configuration before execution

**Surface:** Service Block gateway / workflow loader / template renderer / sandbox / credential broker  
**Classification:** Direct configuration-to-execution safety control

**Core finding.** GitLab's advisory says an authenticated Duo Agent Platform user could, under certain conditions, escape the AI Gateway's prompt-template sandbox through crafted flow configuration and execute commands. Affected Gateway ranges are 18.1.6 to before 19.2.4, 19.3 to before 19.3.2, and 19.4 to before 19.4.1; those upper endpoints are fixed releases. GitLab assigns CVSS 9.9 and says its hosted gateways are patched. This is a template/runtime vulnerability, not evidence that an LLM merely followed malicious prose. [GitLab critical patch advisory](https://docs.gitlab.com/releases/patches/other-patches/patch-release-gitlab-ai-gateway-19-4-1-released/); [GitLab CNA record via NVD](https://nvd.nist.gov/vuln/detail/CVE-2026-90970).

**Importance / architectural relevance.** A signed recipe can still contain dangerous instructions; the kitchen must control which appliances it can operate. VAMS must protect the machinery that loads, renders, compiles, and dispatches Service Block configuration as well as the final model tool call. A reference monitor at one advertised tool endpoint cannot protect credentials or host resources already exposed to a vulnerable renderer.

**Actionable VAMS v0.4-v0.8 implications / minimum implementable output.**

- **v0.4-facing configuration inventory:** classify manifests, prompts, templates, workflow definitions, tool schemas, retrieved snippets, and plugin assets by origin and parser. Trace their paths into template expressions, dynamic imports, process creation, filesystem access, network access, and credential handling. An authenticated author or signed package supplies provenance, not exemption from containment.
- **Rendering contract:** accept a bounded declarative grammar; reject unknown fields, ambiguous encodings, uncontrolled expression evaluation, and configuration-driven imports. Prefer literal substitution where expressive templates are unnecessary. Treat escaping as one layer; isolate any remaining executable rendering in a worker with resource limits and narrow interfaces.
- **v0.8-facing enforcement contract:** keep render workers outside Heart, signing, budget, and credential authority. Deny undeclared process, file, network, and metadata-service access. Route every proposed external mutation through the same exact-formation and current-authority gate. Bind the configuration, parser, renderer, dependencies, and sandbox policy to qualification evidence.
- **Operational admission:** inventory actual Gateway/renderer dependencies and running image versions. If GitLab Self-Hosted AI Gateway is used, apply the vendor's supported fixed release and requalify that deployment; do not infer that updating GitLab core patched a separate Gateway. Patching and credential review follow confirmed deployment scope.

**Acceptance tests.** Supply malicious but authenticated/signed flow definitions to each configuration ingestion path. Use inert canary resources to test attempts at template introspection, forbidden imports, command execution, file traversal, network access, and secret retrieval. Verify rejection or containment before effects, with independent evidence. Also test nesting, oversized input, parser disagreement, configuration changes after approval, and a deliberately compromised render worker. Valid benign templates must continue to work within the declared grammar.

**Challenges / invalidations.** No VAMS exposure to this specific CVE is established here. The vendor notice does not provide enough detail to claim an exact exploit reproduction, affected parser internals, or active exploitation. An analogous canary is not a CVE regression proof. The incident challenges the assumption that natural-language safety checks or a template sandbox alone form a sufficient security boundary. The VAMS control fails if configuration can execute before containment, access ambient credentials, or reach an unmediated mutation sink.

**Speculative implications - not a release requirement.** A configuration dependency graph could allow selective requalification when a renderer, template, tool, or policy changes. A small verified configuration interpreter may eventually reduce the trusted code base. Neither follows automatically from the advisory, and neither replaces patching or host isolation.

**Evidence to retain:** Configuration source-to-sink inventory, pinned parser/renderer versions, accepted grammar, sandbox policy, canary fixtures, independent effect observations, and applicable patch/requalification record.  
**Dependencies:** [RW-010](#rw-010), [RW-011](#rw-011), [RW-017](#rw-017), [RW-021](#rw-021), [RW-022](#rw-022), [RW-023](#rw-023), [RW-026](#rw-026).  
**Research lineage / primary references:** [S098](#s098), GitLab vendor advisory and GitLab-authored CVE description; NVD lists October 2, 2026 as the publication date.

<a id="rw-061"></a>
#### RW-061 | P1 | Quantization-bound proof identity and operator-aware numerical qualification

**Surface:** ZKML build pipeline / inference Service Blocks / proof admission / Composer pricing  
**Classification:** Direct numerical qualification; optimization remains measurement-led

**Core finding.** Taeung Yoon, Yupeng Zhang, and Xiaojing Liao's September 29 preprint studies quantization across nine models. Activations are more precision-sensitive than weights; nonlinear lookup approximation can dominate quality loss, with RMSNorm inverse-square-root lookup precision a recurring bottleneck. Smaller bit widths or lookup tables do not consistently yield proportional proving savings. Its formalization includes numerical formats, rescaling, approximation ranges, and lookup tables in the quantized computation. [Paper v1, Sections 3-5](https://arxiv.org/html/2609.36437v1); [bibliographic record](https://arxiv.org/abs/2609.36437v1).

**Importance / architectural relevance.** A proof is like a receipt for a particular recipe. It can confirm that the recipe was followed while leaving open whether a substituted ingredient changed the meal. VAMS should distinguish a valid proof of quantized inference from faithful behavior relative to the requested reference model. A model hash alone does not identify that recipe. Composer must also price actual proving work rather than infer cost from a label such as INT8.

**Actionable VAMS v0.4-v0.8 implications / minimum implementable output.**

- **v0.4-facing inference contract:** extend the existing numerical profile with reference-model and quantized-artifact commitments; tokenizer; weight/activation formats; scale and zero-point rules; calibration provenance; rounding, clipping, and rescaling; nonlinear approximation and lookup commitments; accumulator bounds; field encoding; and supported sequence lengths. Define signedness, overflow, saturation, and field-wrap behavior explicitly for VAMS's chosen implementation.
- **v0.8-facing proof contract:** bind that profile to circuit/relation, verifier identity, public input/output commitments, build provenance, and coverage. Changes to numerical semantics create a new computation identity and require qualification. Keep `PROOF_VALID`, numerical equivalence to the declared relation, measured fidelity to the reference, and task quality as separate claims.
- **Qualification experiment:** compare one candidate model under a reference profile, a uniform quantized profile, and an operator-specific profile. Use VAMS-representative tasks and held-out adversarial cases. Measure output/logit divergence, task failure, prover latency, memory, proof size, and verifier cost. Set task-specific tolerances before selecting a profile.
- **Boundary validation:** compare actual integer/reference execution with the compiled relation on rounding ties, clipping limits, accumulator extremes, and lookup endpoints. Do not accept a GPU utility simulation as evidence of full circuit coverage. Retain calibration and measurement environments with the qualified build.

**Acceptance tests.** Submit a valid proof with the wrong calibration, scale rule, lookup commitment, numerical profile, or circuit: reject the requested identity. A profile change cannot retain an old qualification simply because the model weights match. Exercise integer/field boundary vectors and operator-specific substitutions. A profile that meets proving-cost goals but exceeds the declared fidelity tolerance fails qualification. Unsupported operators or weaker proof coverage remain explicit rather than becoming full-inference verification.

**Challenges / invalidations.** The study uses GPU quantize-dequantize utility simulation and selected direct proof-system measurements; it does not establish identical proof coverage for every evaluated configuration. [Methods, Sections 4 and 5.2](https://arxiv.org/html/2609.36437v1). For VAMS, the findings challenge both “fewer bits means proportionately cheaper proofs” and “a valid quantized proof establishes equivalence to the original model.” Results must be remeasured on the actual model, workload, hardware, and proof stack. Profile identity enforcement inherits RW-034's P0 gate whenever proof-backed inference is enabled; the new fidelity/cost qualification work is P1.

**Speculative implications - not a release requirement.** Composer could offer qualified profiles along a measured fidelity/cost frontier, allowing principals to select a cheaper computation within explicit tolerances. This could support a market for proof-compatible inference, but automatic profile selection must not silently change authorized semantics or assurance coverage.

**Evidence to retain:** Versioned numerical manifest, quantized-model and lookup commitments, reference/circuit vectors, held-out fidelity report, measured proof costs, and coverage statement.  
**Dependencies:** [RW-034](#rw-034), [RW-035](#rw-035), [RW-036](#rw-036), [RW-052](#rw-052).  
**Research lineage / primary references:** [S099](#s099), arXiv:2609.36437v1, September 29, 2026; Sections 3-5 and Appendices A-C. Upstream results have been read, not independently reproduced.

<a id="rw-062"></a>
#### RW-062 | P0/P1 | Independent cross-chain route admission, health, and staged recovery

**Surface:** VDSO / cross-chain Service Blocks / route admission / Sentinel / settlement reconciliation  
**Classification:** P0 for enabled value/state routes; P1 for monitoring and operational recovery

**Core finding / evidence boundary.** The October 1 NEAR Intents notice reportedly attributed a service pause to interaction between Omni deposit/withdrawal infrastructure and the Intents contract, with different recovery schedules for core service and some cross-chain rails. The [original operator post](https://x.com/near_intents/status/2105642219357241796) was located but returned HTTP 403 during this update; the incident summary is therefore **reported, not independently primary-source verified**. [Contemporaneous relay linking the original notice](https://cryptomode.com/news/near-intents-exploit-3-8-million/). No code-level root cause, precise losses, or current restoration claim is adopted here.

**Primary technical context.** NEAR documents Omni as a bridge with chain-specific verification paths. Its Intents deposit documentation separately describes asset admission and execution behavior, including detached intent execution when `refund_if_fails` is false. These establish distinct integration surfaces; they do not establish the exploit mechanism. [Omni overview](https://docs.near.org/chain-abstraction/omnibridge/overview); [Intents deposits](https://docs.near-intents.org/integration/verifier-contract/deposits-and-withdrawals/deposits).

**Importance / architectural relevance.** A railway station can be open while a bridge on one route is closed. Likewise, block production, a working application, a responsive API, a valid quote, or a cryptographic signature does not establish that a specific deposit/withdrawal route is safe and settleable. VAMS's exact lane policy must decide whether the requested effect can proceed, and uncertain earlier effects must survive a pause without being retried blindly.

**Actionable VAMS v0.4-v0.8 implications / minimum implementable output.**

- **v0.4-facing Service Block contract:** identify routes by source/destination domains, asset identity, direction, bridge/provider, verifier, semantic adapter/version, and settlement contract. Expose deposit, internal application execution, and withdrawal availability separately. Chain uptime alone cannot set a route to healthy.
- **v0.8-facing P0 gate:** extend the existing lane policy with a `RouteAdmissionProfile`: required finality and proof evidence, verifier/adapter versions, freshness bounds, incident/quarantine epoch, principal-owned exposure limits, and readiness conditions at each relevant hop. Recheck at effect admission and before authorizing a new withdrawal. An unqualified, stale, or paused route fails closed; an app restart cannot implicitly reopen it.
- **State and budgets:** distinguish proposed, reserved, submitted, source-final, destination-observed, settled, indeterminate, and reconciled operations. Fence new admissions during quarantine while collecting evidence on existing operations. Keep unresolved exposure reserved until provider-specific reconciliation establishes its outcome. Never turn a timeout into an automatic reroute that could double-spend.
- **P1 monitoring/recovery:** collect chain, application, bridge, deposit, withdrawal, verifier, and destination observations independently where feasible. Include observer identity, freshness, and uncertainty. Use a scoped pause, evidence review, patched-version qualification, reconciliation, bounded canary, and authorized staged reopening. Reset health evidence when relevant implementation or incident epochs change.

**Acceptance tests.** Keep chain and application healthy while the withdrawal rail is paused: deny new route effects. Make deposits succeed while destination execution or withdrawals fail: retain the distinct state and uncertainty. Pause after reservation but before submission; deliver callbacks after pause; duplicate settlement evidence; restart stale workers; and attempt alternate-provider rerouting while the original outcome is unknown. No duplicate liability or silent budget release is allowed. A paused route cannot reopen through an API heartbeat, quoted price, or unrelated chain recovery; unaffected routes remain independently evaluable.

**Challenges / invalidations.** The incident does not establish that NEAR consensus failed, that MPC or a particular verifier was broken, or that VAMS would have prevented the exploit. The primary incident post was inaccessible and no detailed primary post-mortem was retrieved. The generic VAMS lesson is an inference about admission and failure domains, not an attribution of the exploit to a guessed bug. Independent observers may still share an RPC, provider, signer, or indexer; record common dependencies and abstain when evidence is inadequate. Local quarantine also cannot cancel effects already committed at an external provider.

**Speculative implications - not a release requirement.** Independent Sentinel route observations might support route assurance pricing or principal-approved selection among alternatives. Automated failover, insurance, or route-security scores require explicit settlement equivalence, correlated-failure analysis, and economic limits. A favorable score cannot override the P0 route gate or unresolved effects.

**Evidence to retain:** Route dependency/failure-domain map, typed admission policy, per-direction health evidence, pause/recovery runbook, exposure ledger, and partial-outage/late-callback/reroute tests.  
**Dependencies:** [RW-007](#rw-007), [RW-008](#rw-008), [RW-009](#rw-009), [RW-041](#rw-041), [RW-042](#rw-042), [RW-044](#rw-044), [RW-045](#rw-045), [RW-058](#rw-058).  
**Research lineage / primary references:** [S100](#s100), original NEAR Intents incident notice (retrieval blocked), NEAR Omni documentation, and Intents integration documentation. Operator reports, documentation, and VAMS design inferences have distinct evidentiary status.


<a id="schema-families"></a>
## 4. Shared schema families: avoid building disconnected modules

The backlog intentionally consolidates repeated suggestions into shared records. These are **candidate schema families**, to be mapped onto existing VAMS structures rather than automatically creating new contracts or services.

| Schema family | Core content | Principal work items |
|---|---|---|
| Authority and identity | Principal/agent/operator identity; delegation provenance; capability scope; key/suite version; policy and authority epochs; revocation. | RW-002, RW-005, RW-006, RW-007, RW-051 |
| Formation and approval | Original typed request; canonical action; intent; exact target/schema/implementation/effect profile; approval and freshness bindings. | RW-003, RW-004, RW-010, RW-011 |
| Effects and economics | Provider EffectContract; operation/idempotency identity; reservation; pending/committed/indeterminate outcome; distinct settlement. | RW-008, RW-009, RW-044, RW-054 |
| Evidence and observation | Statement type; subject/producer; policy/dependency versions; observation provenance; uncertainty; independently collected receipts. | RW-001, RW-023, RW-024, RW-025 |
| Durable task state | TaskBlueprint; obligations; admissible transitions; accepted milestones; pending effects; checkpoint and authority lineage. | RW-012, RW-013, RW-014 |
| Memory and context | Memory/artifact provenance; derivations; allowed sinks; freshness/revocation; context/budget admission; ownership. | RW-015 through RW-019 |
| Runtime and confidentiality | Reachability/isolation profile; component identities; composite attestation; build provenance; state-key and output-release policy. | RW-020 through RW-022, RW-027 through RW-033 |
| Proof qualification | Exact statement/numerical model; build/verifier identity; proof scheme; assumptions; coverage; model and service qualification. | RW-034 through RW-040, RW-052 |
| Cross-domain evidence | Typed messages; source semantics/authority/finality; lane policy; replay state; observation; optional delivery/checkpoint aggregation. | RW-041 through RW-047 |
| Data availability | Content and publication commitment; independent verification/retrieval; sampling/encoding assumptions; retention scope. | RW-048, RW-049 |
| Discovery and collective policy | Signed manifests; sovereign roots; replaceable resolvers; activation; verifier selection; optional quorum; disputes. | RW-025, RW-050, RW-051, RW-053, RW-056 |
| Qualification and release | Versioned conformance results; evidence manifest; enabled capabilities; exceptions; quarantine and requalification. | RW-026, RW-057, RW-058 |

**October 5 extensions.** Reuse qualification/release records for RW-059's configuration-bound evaluation evidence; implementation/effect records for RW-060's configuration/parser/renderer bindings; compute assurance records for RW-061's quantization and arithmetic identity; and lane/settlement records for RW-062's directional admission, health, pause epoch, and unresolved exposure. These are profiles of shared records, not four new mandatory modules.

### Common encoding and lifecycle rules

Every security-relevant schema should have an explicit version, domain/namespace, canonical encoding, unambiguous units and integer ranges, identity and operation bindings, and a policy for unknown fields or versions. Signed statements require domain separation. Hashes do not excuse lossy normalization or unclear semantics.

Freshness is not just a timestamp. It may depend on a nonce, state version, key/authority epoch, policy revision, finalized chain state, or transparency-log view. Define which is authoritative and how clock skew, offline operation, rollback, and expiry are handled.

Keep **data**, **claims**, **authority**, and **observed effects** distinct in both types and storage. Link them through commitments and references. Do not overload one status field to mean all of authorized, attested, available, correct, completed, and settled.

<a id="acceptance"></a>
## 5. Acceptance suites and conditional release gates

These are suggested suite identifiers, not claims that tests already exist. Use harmless fixtures, simulated compromised components, local services, or explicitly approved testnets. Each suite needs both positive and negative cases, a pinned commit/configuration, and actual retained results.

| Suite | Adversarial scenario and required result | Work items | Applies when |
|---|---|---|---|
| G01 - exact-action binding | Change arguments, units, scope, tool, delegate, epoch, implementation, or normalization after approval. No materially substituted effect is admitted. | RW-001, 003, 004, 010, 011 | Any consequential Service Block operation. |
| G02 - authority attenuation | Widen a child grant, lose the origin principal, replay old consent, rotate a key, or use a provenance-only chain. No authority expansion or stale authorization. | RW-002, 005, 006, 026 | Delegation or durable credentials. |
| G03 - revocation frontier | Revoke with queued/in-flight work, restart stale workers, and deliver callbacks late. Protected sinks fence old authority; unknown paths stay indeterminate. | RW-006, 007, 009 | Asynchronous/delegated external effects. |
| G04 - economic and retry safety | Race replicas against one budget; lose acknowledgements; duplicate transport; allow late commits. No excess exposure or unsafe retry under the declared provider contract. | RW-008, 009, 044, 054 | Paid calls, writes, deployment, payment, bridge, or settlement. |
| G05 - durable continuity | Crash before/after milestone or effect recording and, for P1 qualification, replace the model/runtime. Obligations and accepted history survive without stale authority or duplicate acceptance. | RW-012, 013, 014 | Immortal/durable-agent claim. |
| G06 - context and skill hostility | Split injections across channels, retain oversized tool state, poison artifacts, and install malicious signed skills. Budget and authority boundaries still hold. | RW-015, 016, 017, 026 | External content or model-visible Service Blocks. |
| G07 - containment and evidence | Assume inference-process compromise; attempt undeclared IPC/network/storage access; erase local traces. Forbidden effects remain blocked and protected evidence survives or records a gap. | RW-021, 022, 023, 057 | Agent sandbox and independent-audit claims. |
| G08 - confidential execution | Mix CPU/GPU quotes, replay a stale quote, change a workload, use an unreviewed build, or request disallowed key/output release. Reject profiles whose required bindings fail. | RW-027 through RW-030 | TEE/confidential-compute or sovereign-state claims. |
| G09 - proof identity and assurance | Substitute model, circuit, verifier, numeric profile, or sampled coverage. A valid proof of the wrong statement or weaker guarantee cannot satisfy the request. | RW-034, 035, 036, 039, 052 | Any proof-backed compute qualification. |
| G10 - cross-domain validity | Use a valid signature for a forbidden mint/export, malformed foreign semantics, stale authority, nonfinal root, duplicate message, or correlated signers. Required source/lane policies reject. | RW-041 through RW-045 | Cross-domain writes or value movement. |
| G11 - availability evidence | Supply a fabricated receipt, wrong/missing bytes, stale retention claim, or unavailable independent observer. Do not report stronger DA evidence than was obtained. | RW-048, 049 | DA-backed checkpoint, dispute, or settlement evidence. |
| G12 - discovery and collective trust | Forge a resolver response, activate beyond a grant, make correlated reviewers look independent, or present an unsupported accusation. No authority from discovery or unsupported consensus. | RW-025, 050, 051, 053, 056 | Relevant discovery, quorum, or economic workflows. |

### Added acceptance coverage for RW-059-RW-062

| Existing suite | Added negative cases | Work items |
|---|---|---|
| G01/G03/G12 - identity, authority, admission | Valid certification with no grant; revoked/expired qualification; running configuration differs from evaluated configuration. | RW-059 |
| G06/G07 - hostile inputs and isolation | Authenticated malicious template/flow, configuration-to-process path, credential access, and compromised renderer cannot create forbidden effects. | RW-060 |
| G09 - proof identity and assurance | Wrong numerical/calibration/lookup commitment, arithmetic-boundary mismatch, unsupported coverage, and a cheap profile that fails the declared fidelity tolerance. | RW-061 |
| G05/G10 - uncertain effects and cross-domain validity | Healthy chain/application with paused withdrawal route, stale pause epoch, late callbacks, premature budget release, and reroute while the original outcome is unknown. | RW-062 |

These cases extend the existing 12 suites. A researched recommendation is not a passing test result; enabled capabilities need actual repository evidence.

### Evidence bundle required to close a work item

Retain a concise threat/assumption statement, exact repository commit and relevant versions, runnable test or benchmark commands, fixtures/seeds, machine-readable pass/fail results, and a human-readable explanation of guarantees and limits. Include a known failure case and the expected denial/indeterminate behavior. A documentation assertion, mock-only result, passing happy path, or LLM-generated review is not sufficient by itself.

For research-specific adoption, add a **source verification record**: confirmed title/authors/version/primary URL, accessible implementation, license, reproduction results, and deviations from the published threat model. Do not promote the copied lead in the appendix directly into an approved dependency.

### Conditional Phase-6 decision rule

An internal testnet may proceed with a narrow enabled scope when its applicable P0 controls and existing repository gates are demonstrated. Disabled or research-only routes stay disabled. A missing optional GPU snapshot, proof DAG, DPU observer, new interoperability transport, or speculative economic mechanism is not by itself a blocker.

Conversely, enabling a feature activates its relevant requirements: claiming confidential-GPU execution activates G08; claiming proof-backed inference activates G09; exporting state/value activates G10; relying on DA for evidence activates G11. Existing project deployment, audit, and governance gates remain authoritative and must be inspected, not replaced by this report.

<a id="sequence"></a>
## 6. Recommended implementation sequence

This sequence is a proposal for small, reviewable engineering slices. It is not a delivery-time estimate, evidence that work has started, or an instruction to implement all optional capabilities.

### Slice 0 - establish repository reality and enabled scope

Open a baseline/qualification record for the actual branch and commit. Inventory existing authority, VIR, Service Block, DBOS, VDSO, proof, TEE, DA, and bridge primitives. Map every work item to **already implemented / partial / absent / disabled / research only**, with file/test references. Confirm which features the internal testnet genuinely needs. Validate external source leads only when an implementation would depend on their specific technique or library.

Start [RW-057](#rw-057) and [RW-058](#rw-058) as the test/evidence framework. Do not open independent feature PRs for every work item or create duplicate schemas because the reports used different names.

### Slice 1 - one fully bound, authorized operation

Implement or verify the common evidence model, cryptosuite/identity metadata, typed action formation, delegation, bounded authority, provider effect contract, reference monitor, transitive restrictions, and closed-world resolution: **RW-001 through RW-006, RW-009 through RW-011**. Use a small real test service whose side effects can be observed independently; a filesystem or controlled object-store mutation is sufficient before financial rails.

**Exit criterion:** the operation succeeds only under a current grant for the exact resolved implementation and effect. Argument, tool, version, context, and policy substitution fail. Unknown provider outcomes remain explicit.

### Slice 2 - durable economics, recovery, and revocation

Add **RW-007, RW-008, RW-013, and RW-016** to that same operation. Exercise shared-budget races, lost acknowledgements, late commits, crash/restart, stale workers, and queued-work revocation. Use provider-enforced idempotency/fencing where available; document where it is not.

**Exit criterion:** accepted state and obligations survive restart, authority does not silently persist beyond its scope, uncertain effects do not create duplicate spending, and authority cuts do not overclaim quiescence.

### Slice 3 - hostile model/runtime and independent evidence

Add **RW-017, RW-021, RW-022, RW-023, and RW-026**. Assume the model and inference process can be malicious. Introduce poisoned skill content, cross-channel injections, hidden shared channels, and local trace deletion. Extend Sentinel review through RW-024 as needed.

**Exit criterion:** the runtime cannot expand its own authority, bypass declared sinks, or erase the evidence required to support an enabled guarantee. Collector gaps and unsupported isolation claims are visible.

### Slice 4 - qualify only the infrastructure routes being enabled

For confidential compute, start with **RW-027** and bring **RW-028 through RW-030** forward whenever source provenance, sovereign state, or controlled disclosure is claimed. For proof-backed computation, enforce **RW-034** and qualify the relevant **RW-035/RW-036** statement and build. For cross-domain operations, implement **RW-041 through RW-044** and add **RW-045** when independent observation is part of the lane policy. For DA-backed evidence, enforce **RW-048**.

**Exit criterion:** each enabled adapter has a pinned implementation, explicit assurance/authority assumptions, applicable negative tests, independently checkable evidence, and a scoped disable/quarantine path. No mock or unverified route is eligible by configuration alone.

### Slice 5 - P1 modularity and operating improvements

Prioritize according to actual usage: task state machines and model/runtime replacement; memory provenance/replay/curation; reproducible builds and sovereign key custody; confidential-performance qualification; verifier independence; DA profiles; multi-root discovery and capability activation; and economic/service-quality contracts.

**Exit criterion:** improvements are supported by before/after measurements and do not bypass established P0 controls or introduce a mandatory centralized dependency.

**Placement of the four added packages.** Bring RW-059 into Slices 1/3 when qualification is an admission condition, and RW-060 into Slice 3 wherever configuration is rendered or executed. Apply RW-061 in Slices 4/5 when enabling or optimizing proof-backed inference. Put RW-062's P0 route gate in Slice 4 for enabled cross-domain effects, and its P1 independent monitoring/recovery in Slice 5. None requires a new chain, a central certifier, or all-route deployment.

### Slice 6 - isolated P2 experiments with explicit adoption decisions

Evaluate accelerator snapshots, narrow-TCB controllers, host-independent observers, segmented/sampled/optimized/PQ proving, multi-hop transport, aggregate checkpoints, quorum policy, and counterfactual review only in dedicated experiments. Define a concrete comparison baseline and rejection criterion before investing in each.

**Exit criterion:** a written adopt / defer / reject decision reports security assumptions, reproducibility, cost, performance, interoperability, operational burden, and remaining evidence gaps. No research prototype changes protocol guarantees automatically.

### First three experiments to schedule within the engineering backlog

**1. Effect-contract and authority canary.** Combine RW-003/004/006/008/009/013: one real mutation, two replicas, a shared budget, delayed acknowledgements, restart, and revocation. This closes the largest repeated gap in the reports: durable workflow execution versus authorized, nonduplicated external consequences.

**2. Untrusted Service Block and independent-evidence canary.** Combine RW-010/011/017/021/022/023/026: malicious but signed content, version swap, transitive effect attempt, and trace deletion. The test should remain meaningful even when the model fully follows the malicious instruction.

**3. Assurance-separation canary for the first enabled infrastructure route.** Choose TEE, proof-backed compute, cross-domain, or DA according to actual deployment scope. Deliberately provide valid evidence for the wrong statement, weaker coverage, stale state, or mismatched implementation. The system must refuse to upgrade that evidence into the requested guarantee.

<a id="non-goals"></a>
## 7. Deferred claims and non-goals

**Not imported as facts:** benchmark percentages, reported incident losses, claims of solved scientific problems, vendor release readiness, future quantum-computer dates, or current VAMS implementation/readiness assertions. These need primary-source or repository verification when they matter to a decision.

**Not adopted as standards:** an Internet-Draft or conceptual paper named in the reports is not automatically an approved interoperability or cryptographic profile. Borrow useful semantics only after checking compatibility and maturity.

**Not universal guarantees:** durable workflows do not imply exactly-once effects at arbitrary providers; TEE quotes do not imply authorized or leakage-free output; a valid proof does not imply useful work, all-layer coverage, or correct model identity; DA publication does not imply permanent retention; finality does not prove every source-domain invariant; multiple signatures do not prove operational independence.

**Not a centralized control plane:** no single global root, compulsory VAMS resolver, universal kill switch, central key custodian, mandatory vendor hardware, or required external coordination chain is introduced. Quarantine, revocation, evidence disclosure, and recovery must have explicit sovereign ownership and scope.

**Not a memory-engineering mandate:** memory algorithms, curation strategies, and representations remain Service Block concerns. The protocol-facing contract concerns provenance, authorization, ownership, evidence, and recovery.

**Not immediate production scope:** distributed prover markets, automatic economic rewards for inferred independence, learned-policy activation, semantic slashing, automatic compatible-upgrade proofs, and broad multi-provider confidential migration need separate evidence and governance. The P2 backlog provides bounded experiments, not an instruction to ship these features.

**Not a new DA or cross-chain protocol:** the reports repeatedly found no additional high-signal item in those categories. The useful engineering outputs are still qualification, semantic binding, availability evidence, and replaceable adapters; absence of a fresh paper is not absence of implementation work.

<a id="sources"></a>
## 8. Research/source traceability

### 8.1 Report coverage

The entry labels below cover the Research Watch reports supplied in the conversation. Windows reproduce the report bodies where available; they are not independent message timestamps. Every lead listed below maps to at least one consolidated work item. A lead can be retained for threat-model context without its incident narrative or benchmark claim being adopted as fact.

| Entry | Scope identification from the conversation | Source leads |
|---|---|---|
| R01 | Opening shortlist; report timestamp not stated in its body | [S001](#s001), [S002](#s002), [S003](#s003), [S004](#s004), [S005](#s005) |
| R02 | Early shortlist; report timestamp not stated in its body | [S006](#s006), [S007](#s007), [S008](#s008), [S009](#s009), [S010](#s010), [S011](#s011) |
| R03 | Early September source set; report timestamp not stated in its body | [S012](#s012), [S013](#s013), [S014](#s014), [S015](#s015), [S016](#s016) |
| R04 | Cycle centered on September 8 developments | [S017](#s017), [S018](#s018), [S019](#s019), [S020](#s020), [S021](#s021), [S022](#s022) |
| R05 | Cycle centered on September 9-10 developments | [S023](#s023), [S024](#s024), [S025](#s025), [S026](#s026), [S027](#s027) |
| R06 | September 5-10 search window stated in the report | [S025](#s025), [S028](#s028), [S029](#s029), [S030](#s030), [S031](#s031) |
| R07 | Cycle centered on September 9-10 sources | [S032](#s032), [S033](#s033), [S034](#s034), [S035](#s035), [S036](#s036) |
| R08 | Cycle centered on September 11-15 sources | [S037](#s037), [S038](#s038), [S039](#s039), [S040](#s040), [S041](#s041) |
| R09 | Cycle centered on September 11-16 sources | [S042](#s042), [S043](#s043), [S044](#s044), [S045](#s045), [S046](#s046) |
| R10 | September 16-18 window stated in the report | [S047](#s047), [S048](#s048), [S049](#s049), [S050](#s050), [S051](#s051) |
| R11 | Through September 21, as stated in the report | [S052](#s052), [S053](#s053), [S054](#s054), [S055](#s055), [S056](#s056) |
| R12 | Cycle covering September 19-22 developments | [S057](#s057), [S058](#s058), [S059](#s059), [S060](#s060), [S061](#s061), [S062](#s062) |
| R13 | September 21-23 sources; September 22-24 search window stated | [S063](#s063), [S064](#s064), [S065](#s065), [S066](#s066), [S067](#s067) |
| R14 | September 23-24 sources; September 24-25 search window stated | [S068](#s068), [S069](#s069), [S070](#s070), [S071](#s071), [S072](#s072), [S073](#s073) |
| R15 | Through September 28, as stated in the report | [S074](#s074), [S075](#s075), [S076](#s076), [S077](#s077), [S078](#s078), [S079](#s079) |
| R16 | Through September 30, as stated in the report | [S080](#s080), [S081](#s081), [S082](#s082), [S083](#s083), [S084](#s084), [S085](#s085) |
| R17 | Through October 2, as stated in the report; Approval/CATP/SLP/Cogentic/FCC | [S086](#s086), [S087](#s087), [S088](#s088), [S089](#s089), [S090](#s090) |
| R18 | Through October 2, as stated in the report; Vosti/XIM/TrustProbe/RankEvolve/TME | [S091](#s091), [S092](#s092), [S093](#s093), [S094](#s094), [S095](#s095), [S096](#s096) |

### 8.2 Source-lead register

**Verification status for S001-S096 in this table: not independently revalidated in the original consolidation or this update.** Dates/types are transcribed labels, not confirmed bibliographic facts. A copied URL is a retrieval lead only. Where the original response had only an opaque citation or generic homepage, no precise link has been invented.

| ID | Title or identifiable source label from the reports | Date/version as reported | Type as reported | Copied retrieval lead | Report entry |
|---|---|---|---|---|---|
| <a id="s001"></a>S001 | Concordia: JIT-Compiled Persistent-Kernel Checkpointing for Fault-Tolerant LLM Inference | 2026-06-22 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2606.23521) | R01 |
| <a id="s002"></a>S002 | EnclaveX: End-to-End Confidential AI with CPU/GPU TEEs | 2026-06-30 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2606.31408) | R01 |
| <a id="s003"></a>S003 | zkComposer: Decomposing Proof Construction to Scale zkML | 2026-07-09 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2607.08095) | R01 |
| <a id="s004"></a>S004 | Efficient Data Availability Sampling via Coded Distributed Arrays | 2026-06-15 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2606.16200) | R01 |
| <a id="s005"></a>S005 | Hacken Q2 2026 Security & Compliance Report: Architecture of Trust | 2026 Q2 | Industry report | No precise URL visible in chat | R01 |
| <a id="s006"></a>S006 | InterSAGE: Secure and Verifiable Interoperability Protocol for an Internet of Agents | 2026-08-14 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2608.13030) | R02 |
| <a id="s007"></a>S007 | Agent-to-Agent Trust Internet-Draft | 2026-08-28 | Internet-Draft | No precise URL visible in chat | R02 |
| <a id="s008"></a>S008 | Cryptographically Verifiable Authorization for Autonomous AI Agents | 2026-08-12, v2 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2607.21325) | R02 |
| <a id="s009"></a>S009 | cMCP / Attested Isolated Runtime | 2026-08 | Technical specification | [URL](https://cmcp.agentrust-io.com/) | R02 |
| <a id="s010"></a>S010 | State-Aware Runtime for Long-Horizon LLM Agents | 2026-08-17, v4 | Conceptual working paper | [URL](https://www.cambridge.org/engage/coe/article-details/6a80ae6b810b9dcc821646ae) | R02 |
| <a id="s011"></a>S011 | VeriMesh: Trust-Adaptive Multi-Path Relay Framework for Cross-Chain Interoperability | 2026-08-07 | Journal paper, as described in chat | [URL](https://www.nature.com/articles/s41598-026-66025-y) | R02 |
| <a id="s012"></a>S012 | Attestation-Bound Execution Finality for AI Accelerators and Confidential Workloads | 2026-09 | Internet-Draft | No precise URL visible in chat | R03 |
| <a id="s013"></a>S013 | SoK: When Safe Agents Fail Together | 2026-09-01 | Survey / systematization | No precise URL visible in chat | R03 |
| <a id="s014"></a>S014 | TAC Cosmos-EVM Exploit Post-Mortem | 2026-09-02 | Incident analysis | No precise URL visible in chat | R03 |
| <a id="s015"></a>S015 | Longfellow ZK | 2026-09-03 revision | Internet-Draft | No precise URL visible in chat | R03 |
| <a id="s016"></a>S016 | A Black Box for Agentic Processes | 2026-09-03 | Position / architecture paper | No precise URL visible in chat | R03 |
| <a id="s017"></a>S017 | IonQ: resource estimate for 256-bit elliptic-curve discrete logarithms | 2026-09-08 | Vendor technical estimate | [URL](https://www.ionq.com/blog/the-first-full-stack-blueprint-for-breaking-256-bit-elliptic-curve-signatures) | R04 |
| <a id="s018"></a>S018 | Liquid Network exploit: TRM Labs technical reconstruction | 2026-09-08 | Preliminary incident analysis | [URL](https://www.trmlabs.com/resources/blog/2026s-biggest-hack-to-date-attackers-drained-usd-319-million-in-bitcoin-from-liquid-network-then-returned-85-of-funds) | R04 |
| <a id="s019"></a>S019 | Where Reliability Lives: Experimental Localisation of Behavioural Properties in an Agent System | 2026-09-02 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.03192) | R04 |
| <a id="s020"></a>S020 | If Agents Were Angels, No Governance Would Be Necessary: Out-of-Band Policy Enforcement | 2026-08-27 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2608.27646) | R04 |
| <a id="s021"></a>S021 | Pillar Security: Grafana MCP service-account / SSRF analysis | 2026-09-02 | Security analysis | No precise URL visible in chat | R04 |
| <a id="s022"></a>S022 | NACRE: native confidential containers | 2026-09-03 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.03849) | R04 |
| <a id="s023"></a>S023 | Bounded Capability Receipts and Durable Spend Control for Agent Actions | 2026-09-09, draft-06 | Internet-Draft | No precise URL visible in chat | R05 |
| <a id="s024"></a>S024 | Independent Determinability of Agent Actions | 2026-09-10, draft-00 | Internet-Draft | No precise URL visible in chat | R05 |
| <a id="s025"></a>S025 | Sound Debloating of Redundant Checks in Zero-Knowledge Machine-Learning Circuits | 2026-09-09 | Paper / research prototype | No precise URL visible in chat | R05; R06 |
| <a id="s026"></a>S026 | Akita: A High-Performance Lattice-Based Polynomial Commitment Scheme | 2026-09-09 | Technical paper | No precise URL visible in chat | R05 |
| <a id="s027"></a>S027 | Benchmarking Confidential Computing Performance on NVIDIA Blackwell GPUs | 2026-08-27; revised early September | Benchmark paper | No precise URL visible in chat | R05 |
| <a id="s028"></a>S028 | Beyond Agent Harnesses: Cross-Substrate Authority for Multi-Agent Systems | 2026-09-08 | Paper | No precise URL visible in chat | R06 |
| <a id="s029"></a>S029 | Substrate-Portable Execution for Production LLM Workflows | 2026-09-05 | Production systems paper | No precise URL visible in chat | R06 |
| <a id="s030"></a>S030 | Audit Without Verification | 2026-09-07 | Experimental paper | No precise URL visible in chat | R06 |
| <a id="s031"></a>S031 | Two Proofs, Zero Trust: Intel TDX + NVIDIA H200 | 2026-09-10 | VoltageGPU field report | No precise URL visible in chat | R06 |
| <a id="s032"></a>S032 | A2ABreak: Systematic Security Analysis of the A2A Protocol | 2026-09-09 | Protocol security paper | No precise URL visible in chat | R07 |
| <a id="s033"></a>S033 | They do not care about this: A Systematic Study of TEE Build Reproducibility in the Wild | 2026-09-10 | Empirical research paper | No precise URL visible in chat | R07 |
| <a id="s034"></a>S034 | Hollow-LLM Attack: Computationally Trivial Weights in Zero-Knowledge Verification of LLM Inference | 2026-07-30 | Security paper | No precise URL visible in chat | R07 |
| <a id="s035"></a>S035 | Grounding Agent Memory: Environment-Probing Curation for Enterprise Agents | 2026-09-10 | Experimental paper | No precise URL visible in chat | R07 |
| <a id="s036"></a>S036 | SolTracer: Heterogeneous Cross-Chain Transaction Tracing for Solana Bridges | 2026-09-10 | Cross-chain analysis paper | No precise URL visible in chat | R07 |
| <a id="s037"></a>S037 | Authorization Architectures for Tool-Using AI Agents | 2026-09-14 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.15906) | R08 |
| <a id="s038"></a>S038 | Human Delegation Provenance Protocol (HDP) | 2026-09-11, draft-02 | Internet-Draft | No precise URL visible in chat | R08 |
| <a id="s039"></a>S039 | NIST IR 8587: Protecting Tokens and Assertions from Forgery, Theft, and Misuse | 2026-09-15, stated final | Government report, status unverified | No precise URL visible in chat | R08 |
| <a id="s040"></a>S040 | LGT4CG: Lightweight GPU-TEE for Cloud GPUs | 2026-09 | Journal paper, as described in chat | No precise URL visible in chat | R08 |
| <a id="s041"></a>S041 | Symbiosis Bitcoin Bridge post-mortem / technical reconstruction | 2026-09-11 incident; 2026-09-15 analysis | Incident analysis | No precise URL visible in chat | R08 |
| <a id="s042"></a>S042 | CaMeLoT: static verification and temporal logic for agent plans | 2026-09-16 | Formal-methods paper | No precise URL visible in chat | R09 |
| <a id="s043"></a>S043 | Agent Trust Profile | 2026-09-16 | Internet-Draft | No precise URL visible in chat | R09 |
| <a id="s044"></a>S044 | IntentFuzz | 2026-09-11 | Cross-chain fuzzing paper | No precise URL visible in chat | R09 |
| <a id="s045"></a>S045 | Agentic Societies Need a Social Harness | 2026-09-15 | Multi-agent systems paper | No precise URL visible in chat | R09 |
| <a id="s046"></a>S046 | Forgetting Without Restarting | 2026-09-04 / 2026-09-07 | Execution-state unlearning paper | No precise URL visible in chat | R09 |
| <a id="s047"></a>S047 | An Architecture for Long-Horizon Agents | 2026-09-17 | Agent architecture paper | No precise URL visible in chat | R10 |
| <a id="s048"></a>S048 | XIR: Verifiable Intermediate Representation for Cross-Chain Protocols | 2026-09-17 | Cross-chain systems paper | No precise URL visible in chat | R10 |
| <a id="s049"></a>S049 | Reachability, Not Observation | 2026-09-17 | Security architecture paper | No precise URL visible in chat | R10 |
| <a id="s050"></a>S050 | Towards TEE-Certified DP | 2026-09-17 | Property-specific confidential-compute paper | No precise URL visible in chat | R10 |
| <a id="s051"></a>S051 | Closed-World Resolution Against Tool Hallucination | 2026-09-16 | Tool-resolution paper | No precise URL visible in chat | R10 |
| <a id="s052"></a>S052 | Measuring and Exploiting Implicit Trust in LLM Tool-Calling Pipelines | 2026-09-16 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.18217) | R11 |
| <a id="s053"></a>S053 | Inference-Engine Fingerprinting Attacks are Practical | 2026-09-17 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.20614) | R11 |
| <a id="s054"></a>S054 | Long-horizon autoformalization of a core theorem underlying MIP*=RE / FormalFlow | 2026-09-17 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.19814) | R11 |
| <a id="s055"></a>S055 | A Scalable Trust Discovery Architecture for the Internet of Agents | 2026-09-17 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.20095) | R11 |
| <a id="s056"></a>S056 | Optimism Upgrade 20: Super Root Dispute Games | 2026-09 rollout, as described | Protocol proposal / deployment report | No precise URL visible in chat | R11 |
| <a id="s057"></a>S057 | Authorization Revocation for Long-Running AI Agents | 2026-09-18 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.21284) | R12 |
| <a id="s058"></a>S058 | SingularityNET Ethereum-Cardano bridge compromise and preliminary analyses | 2026-09-19 incident; 2026-09-22 reporting | Preliminary incident analysis | No precise URL visible in chat | R12 |
| <a id="s059"></a>S059 | ActGov: Governing LLM Agent Actions via Policy-Constrained Validation | 2026-09-21 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.24446) | R12 |
| <a id="s060"></a>S060 | Verifiable Computation with Trusted Execution Environments and On-Chain Digital Rights Tokens | 2026-09-18 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.21728) | R12 |
| <a id="s061"></a>S061 | Feedback Coding Enables Inference-Time Covert Agentic Communication / BAM | 2026-09-21 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.24994) | R12 |
| <a id="s062"></a>S062 | UN thematic brief on AI agents and loss-of-control risks | 2026-09-21 | Report named in chat; incident assertions unverified | No precise URL visible in chat | R12 |
| <a id="s063"></a>S063 | From Agent Output to Authorized Transition | 2026-09-23 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.28216) | R13 |
| <a id="s064"></a>S064 | Issuer-Sovereign Agentic Payments | 2026-09-23 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.27452) | R13 |
| <a id="s065"></a>S065 | NVIDIA: Private High-Performance Production AI Inference with Confidential Computing | 2026-09-22 | Vendor engineering report | No precise URL visible in chat | R13 |
| <a id="s066"></a>S066 | TwinCheck: Evidence-Grounded Negative-Twin Verification for Stateful Tool Agents | 2026-09-22 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.26911) | R13 |
| <a id="s067"></a>S067 | Emergent Collusion in Long-Horizon LLM Agent Interaction | 2026-09-21 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.24967) | R13 |
| <a id="s068"></a>S068 | Persistent Billable State: Denial-of-Wallet Attacks and Defenses in Tool-Calling LLM Agents | 2026-09-23 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.28585) | R14 |
| <a id="s069"></a>S069 | Agent Approval Laundering: Transitive Effects Beyond the Approved Invocation | 2026-09-23 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.28586) | R14 |
| <a id="s070"></a>S070 | Meta Private Processing for stateful AI / AI glasses | 2026-09-23 | Vendor engineering report | No precise URL visible in chat | R14 |
| <a id="s071"></a>S071 | On the Effectiveness of Kernel-Level Evidence for Agent Security | 2026-09-24 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.28915) | R14 |
| <a id="s072"></a>S072 | Beyond Centralized Policy Decision Points: Decentralized Sticky Policy Authorization through Evidence Quorums / SPEAR-Q | 2026-09-24 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.29308) | R14 |
| <a id="s073"></a>S073 | Codetta: asymmetric covert multi-agent communication | 2026-09-24 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.28900) | R14 |
| <a id="s074"></a>S074 | Where Does Exactly-Once Live? Model, Harness, and Tool-Contract Effects on Duplicate Side Effects in LLM Agents / LIMBO | 2026-09-24 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.29095) | R15 |
| <a id="s075"></a>S075 | LLM Agents Can Easily Tamper With Their Own Traces | 2026-09-24 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.30266) | R15 |
| <a id="s076"></a>S076 | Instrumental Monitor Evasion Emerges Under Ordinary Task Pressure / EvasionBench | 2026-09-24 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.30217) | R15 |
| <a id="s077"></a>S077 | Progressive Skill Discovery as Access Control for Tool-Using LLM Agents / skilder | 2026-09-23 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.28693) | R15 |
| <a id="s078"></a>S078 | Google Private AI Compute: secure server-side memory | 2026-09-23 | Vendor engineering report | No precise URL visible in chat | R15 |
| <a id="s079"></a>S079 | CLPR: Cross-Ledger Protocol / LF Decentralized Trust lab | 2026-09-24 | Open-source protocol specification / launch report | No precise URL visible in chat | R15 |
| <a id="s080"></a>S080 | Share-Borne AI Virus: Memory-Hopping Attacks Across LLM Agents | 2026-09-28 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.35576) | R16 |
| <a id="s081"></a>S081 | When Consent Outlives Context: Residual Authority Replay in Long-Lived Agents | 2026-09-27 / 2026-09-29 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.33910) | R16 |
| <a id="s082"></a>S082 | When Valid Tool Calls Change Meaning: Formation-Consistent Dispatch for LLM Agents | 2026-09-28 / 2026-09-29 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.35088) | R16 |
| <a id="s083"></a>S083 | NVIDIA Open Agent Safety Platform / OpenShell / Sentry | 2026-09-28 | Vendor platform / reference architecture report | No precise URL visible in chat | R16 |
| <a id="s084"></a>S084 | Chainlink CCIP 2.0 | 2026-09-28 | Protocol release / technical documentation | No precise URL visible in chat | R16 |
| <a id="s085"></a>S085 | Certified Multi-Source Integrity for Structured Agent Actions | Late September, exact date not stated | Formal assurance paper | No precise URL visible in chat | R16 |
| <a id="s086"></a>S086 | Approval Laundering: Systematizing Approval-Execution Binding Failures in AI Coding-Agent Harnesses | 2026-09-30 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.38983) | R17 |
| <a id="s087"></a>S087 | CATP: Design and Evaluation of Local Agent Authorization and Audit Evidence | 2026-09-28; updated 2026-10-01 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.38223) | R17 |
| <a id="s088"></a>S088 | Seal, Then Sample: Sampled Layerwise Proofs for Verifiable LLM Inference from GPT-2 to 70B | 2026-09-23 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.27367) | R17 |
| <a id="s089"></a>S089 | Cogentic: Multi-Agent Orchestration for Automated Proof Discovery | 2026-09-30 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.40324) | R17 |
| <a id="s090"></a>S090 | Flare Confidential Compute on Songbird | 2026-10-01 | Canary deployment report | No precise URL visible in chat | R17 |
| <a id="s091"></a>S091 | Vosti: Specifying, Implementing, and Verifying Deterministic LLM Inference | 2026-09-30 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.38981) | R18 |
| <a id="s092"></a>S092 | XIM: The XDC Interledger Messaging Protocol | 2026-09-30 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.39310) | R18 |
| <a id="s093"></a>S093 | Can Agents Trust Their Skills? / TrustProbe | 2026-09-30 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.39065) | R18 |
| <a id="s094"></a>S094 | ActionGuard | 2026-09-30 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.39450) | R18 |
| <a id="s095"></a>S095 | RankEvolve: A Reliable Multi-Agent Auto-Research Harness | 2026-09-30 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.39551) | R18 |
| <a id="s096"></a>S096 | Trusted Model Environment for Private Semantic Computations | 2026-09-24 | Paper/preprint, as described in chat | [URL](https://arxiv.org/abs/2609.30032) | R18 |

### 8.3 Coverage and completion criteria for this consolidation

Repeated proposals were merged into shared work packages: execution-finality/authorized-transition/CATP into the evidence and effect path; delegated trust/consent/revocation into the authority lifecycle; long-horizon agent papers into durable task semantics; CPU/GPU and build reports into confidential-execution qualification; proof proposals into statement-specific assurance; and cross-chain proposals into lane semantics, authority, finality, and optional transport research.

The original result was **58 implementation work items, not 96 mandatory dependencies**. The requested update adds four linked packages and source bundles S097-S100, bringing the total to 62 work items; the source bundles are not mandatory dependencies. Every item has a priority, architectural relevance, minimum output, acceptance conditions, evidence artifact, dependency list, and source lineage. All implementation statuses remain unassessed until repository inspection and testing.

<a id="update-sources"></a>
### 8.4 Primary references and scoped verification record for the October 5 update

The four IDs below identify source bundles for the requested additions, not four newly validated VAMS dependencies. Access/review date: **October 5, 2026**. Original sources S001-S096 retain their previous status. None of the new research experiments, exploit mechanics, or VAMS implementation claims was independently reproduced.

| ID | Source and exact version/date | Primary reference and useful location | Verification status | Work package |
|---|---|---|---|---|
| <a id="s097"></a>S097 | Nitzan Levi and Oren Yeger, *Autonomous Agent Certification Protocol (AACP)*, draft-levi-agent-certification-00; October 4, 2026; intended Experimental status | [Primary draft](https://datatracker.ietf.org/doc/html/draft-levi-agent-certification-00), Sections 3-5 (separation/configuration), 8 (authorization), 9-11 (lifecycle/security/privacy); [dated submission history](https://datatracker.ietf.org/doc/draft-levi-agent-certification/history/) | Primary text and submission history reviewed. Individual Internet-Draft / work in progress; no standards adoption or runtime implementation asserted. | RW-059 |
| <a id="s098"></a>S098 | GitLab, AI Gateway critical patch release; CVE-2026-90970; CNA record published October 2, 2026 | [Vendor advisory](https://docs.gitlab.com/releases/patches/other-patches/patch-release-gitlab-ai-gateway-19-4-1-released/), CVE section and affected/fixed versions; [GitLab-authored CNA description and publication metadata via NVD](https://nvd.nist.gov/vuln/detail/CVE-2026-90970) | Vendor statement and CNA record reviewed. Specific exploit not reproduced; VAMS use/exposure and active exploitation are unassessed. | RW-060 |
| <a id="s099"></a>S099 | Taeung Yoon, Yupeng Zhang, Xiaojing Liao, *Bits Under ZK-LLM: Evaluating Zero-Knowledge-Friendly Quantization for Verifiable Private LLM Inference*; arXiv:2609.36437v1; September 29, 2026 | [Versioned record](https://arxiv.org/abs/2609.36437v1); [full paper](https://arxiv.org/html/2609.36437v1), Sections 3-5 and Appendices A-C | Primary preprint reviewed; author-reported evaluation, not reproduced. Utility simulation and direct proving measurements must remain distinguished. | RW-061 |
| <a id="s100"></a>S100 | NEAR Intents, October 1, 2026 incident notice; NEAR/Intents current integration documentation | [Original operator post](https://x.com/near_intents/status/2105642219357241796); [Omni overview](https://docs.near.org/chain-abstraction/omnibridge/overview); [Intents deposits](https://docs.near-intents.org/integration/verifier-contract/deposits-and-withdrawals/deposits); [official status page](https://status.near-intents.org/) | Original incident URL located through source links but returned HTTP 403; post body not directly verified. Primary technical documentation reviewed; status page returned no readable incident history. No primary detailed post-mortem retrieved. | RW-062 |

**NEAR incident retrieval limitation.** The [October 1 CryptoMode relay](https://cryptomode.com/news/near-intents-exploit-3-8-million/) links the original operator notice and reports a staged recovery. It is retained solely as an explicitly secondary account of the notice, not a technical root-cause reference. The original post and any subsequent primary post-mortem should be archived and reviewed before an incident-specific regression is claimed. RW-062's generic route-admission requirements can be evaluated against VAMS directly without relying on a particular reported loss, recovery time, or guessed exploit.

**Source facts versus VAMS proposals.** Each new package's core finding and technical-context paragraphs describe its evidence. The implementation profiles, tests, version mapping, and priorities are this report's proposed VAMS design response. Every speculative paragraph is optional research. Source availability, paper publication, or an operator's statement does not establish VAMS readiness or prove an upstream result independently.

## Final recommendation

Start with the **smallest fully mediated, independently observed, durably recoverable external effect**. Make that vertical slice handle current authority, exact semantics, bounded exposure, provider uncertainty, restart, revocation, and hostile content. Then qualify additional infrastructure through explicit assurance profiles. This is the most direct way to convert the September 4-October 2 Research Watch into implementable VAMS hardening without expanding the architecture indiscriminately.
