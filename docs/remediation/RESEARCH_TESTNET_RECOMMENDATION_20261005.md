# VAMS Research Watch: decision for the current testnet path

**Reviewed:** October 5, 2026  
**Input:** research_report.md, 62 proposed research work packages  
**Current implementation:** /home/GodOfAgents/code/VAMS-testnet, branch testnet/remediation-20260907, HEAD 829ab544571f12efe50ecb5740f129c8acb3e16f, with existing uncommitted work  
**Verdict:** Add applicable acceptance conditions to the existing remediation milestones. Keep the existing dual-host testnet scope and mandatory release gates. Do not promote the entire research backlog into new launch prerequisites.

## Evidence basis and limits

Read the latest completed turns in the Codex chat **Harden VAMS testnet readiness**, current canonical AGENTS.md, MISSION.md, PLAN.md, STATUS.md, SESSION_HANDOFF.md, the prior Research Watch qualification assessment, selected enforcement/runtime source, and the updated research report. Current canonical HEAD was read directly. This is a scoped read-only roadmap assessment, not a full source audit of all 62 packages. No tests, scanners, services, transactions, or deployment ceremonies were run in this assessment. Test totals below are recorded results, not newly executed checks.

The current records say **NOT READY**, with deployment, Deposit, Slash activation, and ExecuteIntent disabled. Recorded progress includes strict Aiken 124/124 scenarios; F05.2a 53/55 negative cases, 49/51 transaction-simulator cases, and 21/21 mutations. Two malformed applied-key cases remain pending. The synthetic alternate-policy and economic evidence does not establish original-policy, full-ledger, Solidity runtime, or live-network acceptance.

The original 58-item Research Watch was already imported on October 3 under docs/remediation/research_watch_20261003/. Its qualification ledger explicitly leaves implementation status unassessed. The four new items need a versioned supplemental mapping; the older input/evidence package should remain immutable.

## Preserve the immediate critical path

1. Resolve **F04's policy-anchor model** and its reviewed design before the dependent validator implementation. If selecting the per-identity model, also decide multiple-anchor acceptance versus stateful uniqueness.
2. Establish **M0.4 first-party finding disposition authority and evidence rules**. The latest record contains 638 first-party Gitleaks findings; that is a scan count, not proof that 638 live credentials exist. Findings still require justified disposition, and incident handling where applicable.
3. Close the two pending **F05 malformed applied-key attribution** cases with the required exact evidence; retain pending status if that evidence cannot be obtained.
4. Complete mandatory source/runtime, compiler, security, dependency, provenance, reproducibility, governance, and **T06/history** evidence. Acquire missing prerequisites only through the authorized workflow.
5. Complete **Cardano Pre-Prod and Polygon Amoy** prerequisites, role/Safe evidence, and the separately authorized rehearsal, followed by the existing actual-observation/soak gate.

The research update does not resolve these blockers, authorize a narrower single-chain release, or replace any documented required gate.

## Decisions on the four new items

| Item | Decision | Existing milestone | Minimum necessary testnet change |
|---|---|---|---|
| RW-059: AACP | Adopt the separation principle now; defer full protocol integration unless certification is explicitly part of admission. | M6/M7, with M2 request binding | Registration or evaluation success cannot grant authority. Bind a qualification relied on by admission to the current implementation/configuration. Reject stale or substituted configurations. |
| RW-060: hostile templates/flows | Add a configuration-ingestion review and applicable adversarial cases now. | M1/M2/M6/M7 | Identify every enabled configuration-to-execution path; prove it cannot access signing/credential authority or bypass the effect gate. Patching GitLab is relevant only if that component is actually used. |
| RW-061: ZK quantization identity | Make identity binding an activation condition for real ZK inference. Keep broad quantization optimization in P1. | M4/M7 | Pin model, quantized artifact, arithmetic/lookup/calibration profile, circuit and verifier. Reject valid evidence for a different computation. First qualify a real verifier; metadata cannot rehabilitate a placeholder. |
| RW-062: independent route health | Add per-route admission/recovery tests before any relevant cross-domain route is enabled. | M4/M5/M6/M8 | A healthy chain or application cannot reopen a paused deposit/withdrawal route. Preserve uncertain exposure and forbid blind retry/reroute. Independent monitoring improvements follow the selected route. |

**AACP clarification.** AACP is an individual Internet-Draft, not an adopted standard. A signed qualification record can be useful without implementing a new issuer network, ACC integration, or global certification authority. The gate is conditional on reliance on certification. Primary reference: [draft-levi-agent-certification-00](https://datatracker.ietf.org/doc/html/draft-levi-agent-certification-00).

**GitLab clarification.** The vendor advisory concerns command execution through crafted flow configuration escaping the AI Gateway template sandbox. That makes the configuration execution boundary relevant to VAMS, but it does not establish that VAMS is affected by this CVE. The targeted source search did not establish GitLab or an executable template engine in the inspected runtime files; dependency/deployment inventory is still needed. Primary reference: [GitLab advisory](https://docs.gitlab.com/releases/patches/other-patches/patch-release-gitlab-ai-gateway-19-4-1-released/).

**ZK clarification.** The quantization paper motivates explicit computation identity and measured fidelity/cost tradeoffs. It does not require enabling ZK inference for this assessment to pass. Whether an enabled verifier is mandatory remains governed by the approved M4 scope. Primary reference: [Bits Under ZK-LLM](https://arxiv.org/abs/2609.36437).

**NEAR clarification.** The research report already marks the original incident post as inaccessible and its narrative as reported. Route admission can be justified directly from the VAMS threat model without asserting the incident's detailed exploit mechanism. Primary technical references: [Omni documentation](https://docs.near.org/chain-abstraction/omnibridge/overview), [Intents deposits](https://docs.near-intents.org/integration/verifier-contract/deposits-and-withdrawals/deposits).

## Finish the existing effect canary first

Selected canonical source confirms that neuron/effect_canary.py already contains exact-action/implementation commitments, capability scope, budget reservations, policy revision, authority epoch, expiry checks, and uncertain-outcome reconciliation. neuron/effect_provider.py contains atomic local object/idempotency persistence and separately authenticated observation. This substantially overlaps RW-001/003/004/006/008/009/011/023.

However, the current source restricts the coordinator/provider to local/test/demo and the client to loopback. The October 3 assessment records unexecuted PostgreSQL integration, multiworker races, restart recovery, and independent-operator observation. Do not remove the mode restriction to obtain testnet eligibility. Qualify the real approved provider/DA integration under M5 and its trust/deployment boundary.

The minimum useful qualification campaign is:

| Scenario | Required observable result |
|---|---|
| Change arguments or implementation after approval | No changed effect; exact binding mismatch recorded. |
| Revoke authority after reservation, before effect | No newly admitted forbidden effect; reservation state remains explainable. |
| Two workers spend the last allowance | At most the authorized exposure; database behavior demonstrated. |
| Crash before or after provider commit | Recovery uses the same operation identity and reconciles the actual result. |
| Lose the acknowledgement | No blind retry or premature release of uncertain budget. |
| Resume a stale worker | Epoch/fencing prevents stale writes. |
| Poison signed content or configuration | No expanded resources, keys, tool authority, or egress. |
| Disable the observer or pause the selected route | Missing evidence blocks admission or leaves an explicit uncertain outcome. |

Retain exact source/environment identities, positive controls, denial/uncertainty cases, independent effect observations, and separate review. Run the real database/provider campaign on synthetic data; local doubles remain useful but cannot supply live-path evidence.

## Source findings that affect sequencing

- **Existing canary is partial qualification, not absent functionality:** neuron/effect_canary.py lines 151-302 and 367-402; neuron/effect_provider.py lines 70-127; prior research assessment lines 15-17.
- **ZK plugin is a placeholder:** neuron/trust_plugins/zkml_plugin.py lines 55-76 constructs fixed mock proof bytes and reports valid; lines 79-89 accepts proof data based on length. This is insufficient for cryptographic inference assurance. No live reachability or global containment verdict is claimed by this selected-file inspection. M1/M4 must prove exclusion from enabled admission and settlement until a real backend is qualified.
- **Route control already has a useful foundation:** neuron/vdso/routing.py lines 21-51 rejects inactive, quarantined, expired, mock, and stub profiles. neuron/vdso/models.py lines 542-556 has an adapter profile and conformance root. The inspected profile does not expose separate deposit/withdrawal readiness or a configuration-bound certification record. Extend the relevant interface where required, rather than introduce another parallel router.
- **Shadow behavior remains distinct:** neuron/vdso/workflow.py lines 66-99 separates shadow simulation from configured canary external steps and checks signed capability routing before execution. Preserve this distinction while adding route tests.

## Where the complete 62-item report belongs

This is a planning disposition, not an implementation-completeness assessment. Every package is covered below; overlapping obligations should be mapped to existing code and evidence before opening new work.

| Report packages | Testnet treatment |
|---|---|
| RW-001, 003-011, 013, 016-017, 021-023, 026, 057-058 | Map to existing M1/M2/M5/M6/M7 requirements. Mandatory assurance for the consequential operations actually exposed, with bounded implementation and native negative tests. |
| RW-002 | Preserve suite/version/key-rotation identities and honest security labels where used. New PQ algorithms/backends are separately qualified roadmap work. |
| RW-027, 034, 041-044, 048 | M4/M5/M6 conditions for the enabled TEE, proof, cross-domain, and DA paths. Disabled optional integrations need enforceable containment; required dual-host scope cannot be dropped without a reviewed decision. |
| RW-012, 014-015, 018-019, 024-025, 028-031, 035-036, 045, 049-052, 054, 056 | P1 improvements. Bring forward only where the approved testnet's recovery, identity, privacy, numerical, availability, payment, or evidence claims rely on them. Some fields/tests may be needed to discharge existing P0 assurance. |
| RW-020, 032-033, 037-040, 046-047, 053, 055 | P2 research: optional bounded experiments. Specialized observers, accelerator snapshots, new proof families, multi-hop systems, quorum markets, and model-based counterfactual review do not become universal launch dependencies. |
| RW-059-062 | Four targeted supplemental decisions described above; map into existing milestones and keep adoption conditional on enabled scope. |

## Invariant impact of the proposed additions

No executable change was made, so this table identifies required review coverage rather than asserting preserved runtime behavior.

| Invariant | Proposed impact / required treatment |
|---|---|
| INV-1 regional emissions | No new formula proposed; existing runtime evidence still required. |
| INV-2 insurance yield cap | No new formula proposed; route recovery must not expand economic authority. |
| INV-3 session lifetime | A qualification/certificate cannot extend a session grant beyond its allowed lifetime. |
| INV-4 contract whitelist | Qualification, configuration, and rerouting cannot widen allowed targets. |
| INV-5 OMS fail closed | Certification cannot substitute for required institutional identity evidence. |
| INV-6 root-EOA TEE binding | If TEE runtime evidence is used, configuration binding supplements rather than replaces root identity binding. |
| INV-7 oracle freshness | Chain/app health cannot convert stale oracle evidence into acceptable input. |
| INV-8 supply cap | No change proposed; existing contract/ledger verification remains required. |
| INV-9 reward solvency | Uncertain effects and pending liabilities must not be erased through timeout/retry. |
| INV-10 proof/payload separation | New route and numerical commitments must preserve distinct proof and payload semantics. |

## Recommended next step

Create a **supplemental research-to-gate matrix** for RW-059-RW-062, referencing the updated report digest, approved enabled scope, existing finding/control ID, exact source, current evidence, smallest missing negative test, and milestone owner. Keep status distinct as implemented, executed locally, independently reviewed, ledger accepted, or observed on testnet. For a disabled feature, require a tested non-enableable path rather than a paper implementation.

Once the owner-dependent blockers and prerequisites permit progress, finish the existing M5/M6 effect-canary qualification first. Then add configuration substitution/containment and route-partial-outage cases to that same assurance path. Apply quantization identity when a real inference relation is selected under M4. Finish with the already required release gates and separately authorized dual-host rehearsal.

No production files, existing evidence packages, roadmap, or other chat were changed by this recommendation.
