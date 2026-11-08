# Supplemental research-to-gate matrix: RW-059–RW-062

**Version:** r1  
**Date:** 2026-10-05  
**Purpose:** Map the October 5 Research Watch additions to existing VAMS controls. This planning artifact does not change a finding disposition, control status, enabled route, or release scope.

## Input and scope binding

Research input: `docs/remediation/RESEARCH_WATCH_UPDATE_20261005.md`, SHA-256 `be597f148c5998b1ff60751fa869174f37a8ffd7e06fc29a93c72e0af8a97e94`.

Plan and control inputs at review time:

- `docs/remediation/PLAN.md`: `33c2e5d1891bb572774998c5026f0b33b9a315d5832e1dad35874a5c0901bfbc`
- `docs/audit/control-matrix.json`: `28b9146bb2ace970c19441ab4cd8ee4f91937d56acf4f178b3639f5b4f493cf4`
- `docs/remediation/STATUS.md`: `92f4b7f18c9c9414d1c0ce4e554f06b697688ac877b83a4fd38f883babd3b61a`
- Baseline HEAD: `829ab544571f12efe50ecb5740f129c8acb3e16f`; checkout is dirty and preserved.

Enabled target scope remains a restricted, faucet-only Polygon Amoy plus Cardano Pre-Prod profile. This matrix does not authorize a deployment, chain operation, credential use, or route activation. AACP integration is optional unless admission relies on a qualification. Real ZK inference remains excluded until its verifier and computation identity are qualified. Cross-domain route controls apply to each route selected for the required dual-host profile; they do not narrow that profile.

Evidence labels used below are deliberately separate: **source-foundation** means source constructs exist; **local-synthetic** means local tests/campaigns ran with synthetic components; **independently-reviewed** applies only to named reviewed artifacts; **ledger-accepted** and **testnet-observed** require direct evidence at those layers. No row is promoted by this matrix.

## Research-to-gate mapping

### RW-059 — Configuration-bound qualification without authority amplification

- **Condition and enabled scope:** Applies whenever VAMS uses evaluation, certification, or qualification as an admission input. No AACP issuer network or full protocol integration is required for the current profile.
- **Existing controls:** M2 request/action binding; M6 pre-effect policy enforcement; M7 evidence integrity. G0, G2, and G3. Tracks T04 (Audit Lead), T15 (Cryptography Reviewer), T23 (SDK Lead), and T29 (Runtime Lead). G5 applies to independent assurance for the public/incentivized stage; G6 applies to controlled rollout and its stop-condition drills.
- **Source paths:** `neuron/effect_canary.py` (ApprovedAction, AttenuatedCapability, PostgresAuthorityRepository, EffectCoordinator); `neuron/runtime_safety.py`. Current source hashes: effect canary `a5ac67887a06d7f747fcfd8fde92e9263ff5b94f569861a4481d301aff973c94`; runtime safety `b39c48ec63f20c34573e11e0a515ef622e3340f76964e1688c2dfa23b29d0079`.
- **Current evidence/status:** The local canary source binds an action to implementation digest, policy revision, authority epoch, expiry, target and content, and fails closed outside local/test/demo. Prior synthetic integration result is recorded in docs/remediation/m7_effect_canary_redirect_r1/ASSESSMENT.md (12/12 focused tests under Python 3.12.14); this is local evidence only. The PostgreSQL path and approved testnet provider/DA path are not qualified. No certification-backed admission is claimed. Status: source-foundation plus the cited local-synthetic result; no ledger-accepted or testnet-observed evidence.
- **Smallest missing negative test:** Present a valid qualification for implementation/configuration A while runtime resolves B (or after revocation/expiry); show admission and every protected effect are denied before reservation/provider invocation, while unchanged A remains the positive control.
- **Owner:** SDK Lead with Runtime Lead; Audit Lead accepts evidence. Activation condition: a specific enabled admission path relies on qualification and its runtime implementation/configuration is independently pinned.

### RW-060 — Hostile prompt, template, and flow configuration containment

- **Condition and enabled scope:** Applies wherever attacker-influenced prompt/template/flow configuration reaches rendering, tool selection, or execution. GitLab-specific remediation applies only if inventory proves that component is used.
- **Existing controls:** M1 runtime/demo containment; M2 request integrity; M6 pre-effect enforcement; M7 source and release evidence. G1 and G3 for closed-canary qualification; G5 and the applicable G6 controls are additional public/incentivized rollout requirements. Tracks T07 (DevSecOps), T25 (AI Safety Lead), T27 (SDK Lead), and T31 (Gateway Lead).
- **Source paths:** Configuration/execution inventory must start from `gateway/server.py`, `neuron/neuron.py`, `neuron/composer/blueprints.py`, `neuron/vdso/workflow.py`, and the effect gate in `neuron/effect_canary.py`. Current effect-gate hash: `a5ac67887a06d7f747fcfd8fde92e9263ff5b94f569861a4481d301aff973c94`.
- **Current evidence/status:** Source presence only: the effect canary has an explicit local/test/demo boundary, and VDSO workflow distinguishes shadow simulation from configured canary steps. No test result is claimed for hostile configuration. A complete current inventory of untrusted configuration-to-execution paths and a live-mode containment verdict have not been recorded. No GitLab exposure is established. Status: partial source-foundation; the broader negative is pending.
- **Smallest missing negative test:** Feed an authenticated hostile flow/template that substitutes effect arguments or implementation identity and attempts credential/signing, process, file, network, or privileged tool access; verify rejection occurs before the side-effect boundary and observe zero protected effects. If no such path is enabled, test the route is non-enableable in the live profile.
- **Owner:** AI Safety Lead with SDK and Gateway Leads; DevSecOps verifies dependency/deployment inventory. Activation condition: only the configuration paths found in the enabled profile.

### RW-061 — Numerical and proof identity for real ZK inference

- **Condition and enabled scope:** Conditional on selecting real proof-backed inference under M4. Keep placeholder/mock ZK outside admission and settlement while the capability is excluded. This does not require broad quantization optimization or enabling ZK for testnet.
- **Existing controls:** M4 verifier and settlement binding; M7 provenance and release evidence. G1 and G2 for qualification; G3 before a live testnet route; G5 for independent public/incentivized promotion. Tracks T07 (DevSecOps), T13 (Cross-chain Security Lead when used across domains), T15 (Cryptography Reviewer), and T23 (SDK Lead).
- **Source paths:** `neuron/trust_plugins/zkml_plugin.py`, `neuron/trust_plugins/__init__.py`, `neuron/sdk/trust_aggregator.py`, and the enabled admission/settlement call path. Current plugin hash: `b29501798efd0b98ef23fbfe06c19a6ef35ed9f863d51d3f2fea09906b91c9fb`.
- **Current evidence/status:** The inspected plugin constructs fixed placeholder proof bytes, returns `valid=True`, and accepts proof data by length; it is not a cryptographic verifier. Reachability/containment across every enabled admission and settlement path remains to be established. Status: placeholder source identified; no real verifier, numerical-identity qualification, ledger acceptance, or testnet observation.
- **Smallest missing negative test:** In the exact live admission/settlement entrypoint, provide the placeholder proof and a proof valid for a different model/artifact or arithmetic profile; both must be rejected before settlement. Keep a real-verifier positive control pending until a selected verifier/relation and all model, quantized artifact, arithmetic, lookup, calibration, circuit, and verifier identities are approved and bound.
- **Owner:** Cryptography Reviewer with SDK Lead; Cross-chain Security Lead if a cross-domain path consumes the proof. Activation condition: only after a real verifier/relation is selected and approved; until then prove the placeholder path cannot be enabled.

### RW-062 — Directional route admission, health, and staged recovery

- **Condition and enabled scope:** Applies independently to every enabled cross-domain deposit, withdrawal, bridge, or settlement route in the required Polygon Amoy plus Cardano Pre-Prod profile. Chain or application health cannot reopen a paused direction.
- **Existing controls:** M4 proof/settlement binding; M5 recoverable provider/DA effects; M6 policy and authority epochs; M8 human-approved rehearsal. G2 and G3 before closed-canary admission; G4 before deployment rehearsal; G5 and applicable G6 stop-condition/soak controls before public or incentivized rollout. Tracks T13 (Cross-chain Security Lead), T29 (Runtime Lead), T30 (DA Lead), T35 and T36 (SRE Lead).
- **Source paths:** `neuron/vdso/models.py` (AdapterProfile and requirements), `neuron/vdso/routing.py` (`_eligible` and selection), `neuron/vdso/workflow.py`, plus each selected bridge/DA adapter and settlement entrypoint. Current hashes: models `78a540284827c9a40c759662c565effe40be23c6c5760d8ba15d576530cf1586`; routing `e6fb8ea06d58dcaecd6e0d10145bb693dcc667d3a046674bcaffdfd6c291de38`; workflow `a34b00d530b6a92ab70c4cfc12ab13d03cdd778cbb82d3ec425461d4ed5b681a`.
- **Current evidence/status:** The router rejects inactive, quarantined, expired, mock, stub, incompatible-authority, and unsupported-capability profiles. Test source is present at neuron/tests/test_vdso_canary.py for fail-closed selection and quarantine; this matrix does not claim that suite was executed during this slice. Separate deposit/withdrawal readiness, pause epochs, late callback handling, and unresolved-exposure behavior are not evidenced by that test file. T30 is currently blocked; no live DA receipt is credited here. Status: source-foundation and test presence only; no newly executed result, live route admission, or testnet observation.
- **Smallest missing negative test:** Keep chain and application healthy while marking only the withdrawal direction paused/stale; inject a late success callback and verify it cannot reopen the route, release uncertain budget, or trigger reroute/duplicate effect. Repeat with partial deposit/withdrawal outage and stale pause epoch; observe both route-specific denial and preserved exposure.
- **Owner:** Cross-chain Security Lead with DA and SRE Leads. Activation condition: before any affected direction is enabled; require exact route identity, independently observed health/pause evidence, and rehearsal approval for network effects.

## Evidence and change boundary

This matrix adds four conditional acceptance mappings to existing M1–M8 and G0–G6 controls. It does not create a new roadmap, relax required milestones, promote all 62 research packages to launch dependencies, revise any control status, or grant implementation/test/ledger/testnet credit. The original October 3 research package remains unchanged.

Current source hashes and control definitions are listed for traceability. Their presence is not proof that their behavior was re-executed during this documentation slice. F04 owner choice, M0.4 first-party finding authority/disposition, the two pending F05 malformed-applied-key cases, T06/history, missing runtime/security/dependency/provenance/reproducibility/invariant evidence, governance/Safe controls, both chain prerequisites, approved rehearsal, and actual observation/soak remain open.
