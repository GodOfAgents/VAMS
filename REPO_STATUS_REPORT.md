# VAMS Repository Status Report And Public Testnet Roadmap

**Date:** 2026-07-17
**Last verified:** 2026-07-17 (implementation in progress; exact-tree gates pending)
**Stage:** Hardened Pre-Testnet Candidate
**Current Priority:** Phase 6: Closed Public-Testnet Baseline + Private VDSO Shadow Hardening
**Public Testnet Target:** July 2026 launch window
**Architecture Baseline:** v0.8.0 cognitive/composer layer + v1.3.0-oms runtime + June gateway hardening
**Branch Baseline:** Architect-bootstrap working tree based on
`a7671eec30d0c56bb46eb67dea31affb1998294d`, itself descended from `main` at
`31929a24419a9b7b9d8954cbea2df9fe1cb77a68`; signed post-history-rewrite
release evidence is absent

---

## 1. Source Of Truth

This report is a technical public status document. It is intended to replace stale roadmap language with repository-backed implementation reality.

Interpretation rules:

- Commit history is the chronology source.
- `AGENTS.md`, `docs/CHANGELOG.md`, `audit.md`, executable tests, and current source code override stale roadmap claims.
- Historical test totals are not current facts unless rerun against the current tree.
- VAMS is pre-testnet. This report does not claim mainnet, production, or fully audited readiness.
- Public testnet is a July 2026 launch window gated by security, verification, deployment artifacts, and operator readiness.

No deployment statement in this document should be read as a mainnet claim.

---

## 2. Executive Status

VAMS is a hardened pre-testnet candidate. The repository contains implemented Solidity contracts, Aiken validators, Neuron runtime modules, Gateway services, Composer scoring, frontend assets, and a security/build workflow foundation.

The system is not mainnet-ready. It is not yet a public testnet deployment. The remaining work is no longer abstract architecture; it is concrete verification, deployment ceremony, live configuration, and operational hardening.

Bootstrap governance is Architect-led and team-controlled by four humans. It
must not be described as decentralized community governance or externally
audited. The faucet-only `bootstrap-public` stage accepts six explicit
Architect-bootstrap dossiers; the later `public` stage remains blocked pending
independent review and governance migration.

Current blockers before public testnet:

- Readiness is fail-closed at 3 implemented, 29 partial, 4 blocked, and 0
  verified tracks. No track may advance until every applicable gate reruns
  against the exact final post-history-rewrite SHA in CI and the complete
  stage-plus-operational evidence manifest is signed.
- Current working-tree verification passes full Python (774 passed, one
  intentional skip, 23 subtests), the pinned PostgreSQL six-figure atomicity
  test, Foundry 709/709, Aiken 77/77, Rust format/check/deny-warnings Clippy,
  frontend build/audit, Bandit, pip-audit, Semgrep, Slither fail-high, Caddy,
  and first-party structural gates. Rust linked tests remain unavailable on
  this Windows host because MSVC `link.exe` is absent. These results are not
  signed post-history-rewrite release evidence.
- The previous branch Semgrep scan recorded zero findings; its three initial
  timeout paths were rerun with a longer per-rule budget and completed with
  zero findings. It must rerun against the final patch and post-rewrite SHA.
  Historical Gitleaks remains blocking on committed PEM private-key paths and
  legacy provider helpers. PR CI run `29413794423` verified one Infura finding;
  later run `29416245559` reported the same 20 sanitized detector events as
  unverified. That change is consistent with invalidation but is not provider
  revocation or impact proof. Owner attestations now report no active provider
  credential, unexpected activity, or unexpected billing and describe three
  PEM occurrences resolving to two unique keys, but they lack the independent
  artifacts required for closure. History cleanup, signed evidence, and clean
  rescans remain promotion gates.
- Avail and EigenDA remain structured stubs and must stay blocked from live environments.
- Deployment artifacts are incomplete: chain IDs, addresses, transaction hashes, verification status, multisig owners, and timelock ownership.
- Live DA, identity, Trails, TEE, and gateway configuration need testnet evidence.
- Continual-learning telemetry still needs calibration and independent review; Service Block memory policy, authorized persistent mutation, deterministic S-MMU reset, and telemetry-only reward isolation are now enforced in source.
- Frontend browser hardening remains pending: CSP/XSS runtime checks, phishing/accessibility review, and any future wallet workflow.
- VDSO remains a side-by-side canary foundation, not a deployed protocol. Its
  evidence-hardened ADR/review, VIR-Core reference, Polygon contracts,
  Neuron/Gateway boundary, PostgreSQL-backed private-shadow replay/nonce stores,
  and Cardano conformance checks now exist. Public VDSO remains off; the private
  lane is read-only, non-value-bearing, and not authoritative. Real proof and
  recovery backends, reviewed HPKE and ML-DSA paths, live adapter evidence,
  deployment rehearsal, independent review, and deployment evidence remain
  blocking.

---

## 3. Development Timeline From Commit History

| Period | Development Reality |
| --- | --- |
| January 2026 | Architecture, authorship, and IP documentation were consolidated. The project pivoted toward a dual-chain architecture with Polygon CDK as primary. Phase 1 token infrastructure landed, including token, vesting, and staking. The frontend migrated to Vite and React. |
| February 2026 | Phase 3 contracts and documentation expanded. Polygon Amoy deployment documentation was added, including an earlier documented VAMSToken address. Trust Aggregator and Quantum DePIN narrative work landed. Tests and repository structure were expanded and professionalized. |
| March 2026 | Core smart contracts for staking, governance, tokenomics, and infrastructure landed with tests. CLR v3.1 documentation was updated. Security audit findings C-01 through M-08 were remediated. A Cardano proposal was added. |
| April 2026 | Phase 2 Sentinel network and hardware collateralization were implemented. ICN modular architecture upgraded to v1.0.0-icn. Audit remediation sprints 0-5 prepared the codebase for testnet hardening. AUTOSKILL intelligence layer and documentation landed. |
| May 2026 | DBOS workflow engine migration and OMS integration landed. Sequence session keys, Trails transport, Coinme fiat rails, stablecoin payouts, OMS identity, insurance yield, TEE/trust plugin hardening, and documentation alignment to v1.3.0-oms were added. |
| June 2026 | Documentation and research sync continued. x402 interrupt recovery, gateway security hardening, cognitive layer integrations, CHC dynamic scoring, 6-axis composer scoring, and gateway tests landed through commit `113544e`. On 2026-06-28, local CI hardening work addressed Bandit, frontend audit, Node/Aiken workflow mismatches, and missing Python intelligence dependencies. |

---

## 4. Current Component Maturity Matrix

Status labels:

- `Implemented`
- `Implemented, Mock-Dependent`
- `Implemented, Needs Full Verification`
- `Stub / Blocked From Live`
- `Planned`

| Component | Current Status | Reality Notes | Public Testnet Gate |
| --- | --- | --- | --- |
| Solidity contracts (`contracts/src/`) | Implemented, Working-Tree Verification Clean | The Architect enum migration and full Foundry tree pass 709/709 tests across 40 suites; build and formatting checks pass. These dirty-tree results are not signed exact-commit evidence. | Rerun against the clean release commit in CI, complete the six Architect-bootstrap dossiers for faucet-only deployment, then retain independent review as a later public/mainnet gate. |
| Cardano validators (`cardano/validators/`) | Schema-v2 State Machines Implemented, Working-Tree Verification Clean | Four persistent validators preserve explicit authentication asset classes and exact datum/value transitions. Three seed/bootstrap policies are auxiliary templates. Bridge execution, cross-chain deposits, and slashing fail closed; local timelock targets are allowlisted. Seeded Aiken verification passes 71 unit tests and 6 properties (77/77), with 250 successful cases per property, and the blueprint rebuild succeeds. `cardano/lib/vams/vdso.ak` remains conformance-only. | Apply reviewed public parameters, independently verify final hashes, rerun on the exact clean post-rewrite SHA in CI, and retain signed rehearsal evidence. |
| Neuron runtime (`neuron/`) | Implemented, Working-Tree Verification Clean, Live Routes Restricted | Mock clients remain available locally but are blocked from live profiles. The non-PostgreSQL aggregate passes 774 tests with one intentional skip and 23 subtests. The pinned PostgreSQL multi-process atomicity/restart gate passes beyond $1 \times 10^5$ records. | Rerun all Python tests in exact-commit CI and collect live integration evidence for every enabled route. |
| Data availability | Implemented, Live Evidence Pending | Celestia live failures no longer fall back to mock receipts and exact retrieval is required. Near non-mock submission is disabled until signed submission and retrieval exist. Mock receipts are never verified; Avail, EigenDA, and current VDSO DA paths remain release-ineligible. | Record real Celestia Mocha and Near Testnet submission, inclusion, independently observed retrieval, and payload-match artifacts before enabling either route. |
| Gateway (`gateway/server.py`) | Implemented, Needs Live Verification | Gateway requires DID auth, replay protection, proxy-verified mTLS, explicit live CORS origins, bounded methods/headers, request limits, rate limiting, loopback binding, and Caddy TLS. Public instances do not mount VDSO routes with `VDSO_MODE=off`; private shadow startup requires PostgreSQL atomic stores, trusted heights, and deployment verification. | Certificate allowlist, live route/size/rate smoke tests, Gateway aggregate pytest evidence, external TLS scan, and multi-process shadow soak evidence. |
| Composer and cognitive layer | Implemented | CHC 10-axis cognitive profiles and 6-axis composer scoring exist. Cognitive score: $$S_{cog}=1.0-\frac{1}{|D_{req}|}\sum_{d \in D_{req}}\max(0.0, Req_d-Profile_d)$$ | Keep scorer tests passing; verify real node telemetry maps correctly into candidate ranking. |
| Economics and regional incentives | Implemented, Synthetic Campaign Clean | Regional/yield caps and hybrid thin-liquidity pricing exist. The seeded 100,000-epoch campaign detected all injected linked-reward, linked-capacity, regional-capture, thin-liquidity, and wash-return attacks with zero misses or baseline false positives. | Run the analyzer against live beneficial-owner attestations and add governance/settlement state-machine simulations. |
| Frontend (`frontend-vite/`) | Read-Only Testnet Profile, Build Clean | Gateway origin is environment-bound and HTTPS-only in production. CSP removes inline scripts and external fonts. Vite production build and npm audit pass. Wallet transactions, real fiat, real yield, and staking rewards are disabled for the first testnet profile. | CI Node 22 evidence, browser CSP verification, phishing review, and accessibility review. |
| CI/CD (`.github/workflows/security-gates.yml`) | Implemented, Needs CI Evidence | The branch restructures promotion to collect raw gate/stage artifacts before building and Cosign-signing a non-self-referential manifest bound to a target SHA and immutable evidence-run IDs. No GitHub Actions run or signed bundle is claimed. | Run on the clean target commit, verify complete non-null artifact hashes/signatures, and configure branch protection for the Security Evidence Gate. |
| Deployment artifacts | Identity-Bound Ceremony and Fail-Closed Cardano Application Tooling Implemented, Runtime Evidence Pending | Polygon controls retain the Safe/timelock checks. Cardano template extraction is explicitly non-deployable; a separate tool applies reviewed CBOR parameters for four persistent validators and the canonical fund bootstrap, while optional agent/proposal policy instances require real creation transactions. It rejects unapplied values and records policy templates separately. No applied parameter manifest or real authority instance is present. | Pin an audited Safe release; supply complete setup and `ApproveHash` history; supply Cardano public parameters and seed UTxOs; rehearse both hosts; independently verify bytecode/script hashes; and record role transfers, addresses, transactions, and rollback evidence. |
| VDSO deterministic state-object canary | Canary Foundation Implemented, Deployment Blocked | `vams-vm/`, `contracts/src/vdso/`, `neuron/vdso/`, `gateway/vdso.py`, and conformance-only `cardano/lib/vams/vdso.ak` implement a side-by-side foundation. PostgreSQL-backed atomic replay/nonce stores and a private read-only shadow composition now exist. Public VDSO remains `off`; no VDSO deployment, Cardano VDSO validator, value-bearing route, or authoritative migration is claimed. | Complete real proof/recovery verification, reviewed HPKE and ML-DSA backends, immutable adapter/verifier identity, live DA evidence, at least two independent execution backends, shadow/canary evidence, independent review, deployment rehearsal, and a governance-approved migration before promotion. |

---

## 5. Invariant And Security Posture

VAMS has ten core invariants that must remain intact across public testnet and any future mainnet launch.

| ID | Invariant | Current Enforcement Focus |
| --- | --- | --- |
| INV-1 | Regional emissions per geographic region must stay <= 30%. | `RegionAwareDEC.sol` and regional economics tests. |
| INV-2 | Insurance idle capital deployed to yield must stay <= 30%. | `VAMSInsuranceFund.sol` and yield manager paths. |
| INV-3 | ERC-4337 session keys must expire within <= 24 hours. | `neuron/sdk/sequence_wallet.py`. |
| INV-4 | Session keys must be restricted to whitelisted VAMS contracts. | `neuron/sdk/sequence_wallet.py`. |
| INV-5 | Institutional P3 compliance must fail closed on OMS identity failure. | `neuron/clr_router.py`, `neuron/sdk/oms_identity.py`. |
| INV-6 | TEE attestations must bind to root EOA, not session keys. | `neuron/trust_plugins/tee_plugin.py`, `neuron/sdk/phala_tee.py`. |
| INV-7 | Stale oracle data must trigger fallback and never be used silently. | `CommitRevealOracle.sol`, `neuron/chain_oracle.py`. |
| INV-8 | Max VAMS supply is capped at $1 \times 10^9$. | `VAMSToken.sol`. |
| INV-9 | Reward pools must cover pending rewards. | `VAMSStaking.sol`, reward contracts. |
| INV-10 | Cross-chain bridge proofs must stay separate from payload hashes. | `neuron/bridge_executor.py`. |

June hardening materially improved INV-5, INV-6, and INV-10 by blocking live mock identity, mock TEE, and mock bridge execution paths. Gateway hardening also improved control-plane posture by removing Basic Auth from live routes and requiring proxy-verified client certificates for live telemetry.

---

## 6. Verification Status

Do not preserve historical aggregate totals as current evidence unless the full
suite has been rerun on the current tree and bound to its commit.

Current local results are explicitly marked below. This working tree is based
on `a7671eec30d0c56bb46eb67dea31affb1998294d`, but the results are not signed
release evidence and credential history remediation must precede the release
SHA. The branch started from `main` at
`31929a24419a9b7b9d8954cbea2df9fe1cb77a68`:

| Scope | Command | Result |
| --- | --- | --- |
| Solidity verification | `forge build --sizes`; `forge test -vvv`; `forge fmt --check` | Current working tree passed: 709/709 tests across 40 suites, zero failures/skips; build and whole-tree formatting pass. Compiler warnings remain recorded for cleanup/review. |
| Aiken verification | `aiken fmt --check`; `aiken check --deny --seed 20260713 --max-success 250`; `aiken build` | Current working tree passed: 71 unit tests and 6 properties, 77/77 total, with 250 successful cases per property; the parameterized `plutus.json` blueprint was regenerated. |
| Evidence-control regressions | `python -m unittest discover -s scripts/audit -p 'test_*.py'` | Current working tree passed 81/81, including Architect-bootstrap assurance, exact team councils, credential evidence, workflow, rewrite safety, and sanitized triage. |
| Python current tree | `python -m pytest -v --tb=short --ignore=neuron/tests/test_vdso_postgres_integration.py` | Passed: 774 tests, one intentional skip, and 23 subtests; one upstream `websockets.legacy` deprecation warning remains. |
| PostgreSQL integration | `python -m pytest -v --tb=short neuron/tests/test_vdso_postgres_integration.py::test_postgres_atomicity_restart_and_six_figure_state` | Passed against the digest-pinned PostgreSQL 16.14 container: one test, multi-process atomicity/restart, and more than $1 \times 10^5$ records. The disposable container was removed. |
| Python security lint | `bandit -r neuron gateway -ll -ii` | Passed with no selected issues: zero High severity findings and no unmitigated selected result. |
| Python dependency audit | `pip-audit -r gateway/requirements.txt` and `pip-audit -r neuron/requirements.txt` | Passed: no known vulnerabilities in either requirement set. |
| VIR-Core current branch | `cargo fmt --all --check`; `cargo check --workspace --all-targets --locked`; `cargo clippy --workspace --all-targets --locked -- -D warnings`; `cargo test --workspace --all-targets --locked` | Format, check, and deny-warnings Clippy pass. Linked tests are unavailable because MSVC `link.exe` is not installed; run them on Linux CI or install the Visual Studio C++ workload. |
| Semgrep | Exact workflow scan command plus targeted `--timeout 300` rerun | Passed after removing one global-`IFS` finding from the rewrite tool: zero findings across 473 tracked files; the one initially timed-out audit-program rule passed against its single target. Candidate exact-commit CI remains required. |
| Slither | `slither . --exclude-dependencies --exclude-low --exclude-informational --fail-high` | Local fail-high passed for 181 contracts and 63 detectors with 19 adjudicated lower-severity results. PR CI run `29413794423` exposed a missing-`forge` workflow dependency; commit `68bbe926315057d5ce5271b1fbef8e084cda2b14` added pinned Foundry v1.7.1 and rerun `29415822350` passed the Slither job. Independent acceptance of the residual adjudications remains required. |
| Gitleaks history | Gitleaks v8.30.1 `git --log-opts=--all` with fully redacted reporting | Blocking. The local inventory reports 1,740 matches across 15 finding-bearing commits. PR CI run `29416245559` reported 869 redacted matches across 27 paths and nine finding-bearing commits: 867 generic-key and two private-key findings. The sanitized inventories require independent reconciliation after rotation and cleanup. |
| Frontend install | `npm ci` | Passed: 176 packages installed/audited, 0 vulnerabilities. |
| Frontend audit | `npm audit --audit-level=high` | Passed: 0 vulnerabilities. |
| Frontend build | `npm run build` | Passed with Vite 7.3.6. |
| Cardano template rehearsal | `cardano_preprod_artifacts.py --commit-sha 202172db...` | Passed at the clean implementation commit: bound four non-deployable persistent validator artifacts and three auxiliary policy templates. `artifacts_applied=false`; no address, transaction, signing credential, or deployment claim was generated. |
| Gateway Caddy profile | Digest-pinned Caddy `validate` and `adapt` | Passed; mTLS client verification, loopback proxy target, request-body limit, and response security headers were present in the adapted configuration. |
| Report/diff hygiene | `git diff --check` | Passed on the current working tree before commit. |
| Gateway/runtime/VDSO focused tests | Focused pytest selection covering Gateway auth/lifecycle, VDSO semantics, PostgreSQL stores, runtime safety, and the private shadow worker | Passed: 134 with one intentional skip for the real Rust binary that cannot be linked on this Windows host. The real Aiken exported UPLC integration passed. |
| Phase 6 security scripts | `default_credential_scan.py`, `public_content_policy_scan.py`, `mock_mode_promotion_scan.py` | Passed on the current tree on 2026-07-15. |
| Python syntax check | `compileall` on the VDSO/Gateway modules | Passed on the current tree on 2026-07-13. |
| VDSO evidence/docs | `validate_vdso_evidence.py`, its five tests, `validate_docs.py`, and audit-program validation | Passed on the current tree. |
| R10 world-state and SkillOps hardening | `WorldStateFidelitySentinel`, Service Block EIP-712 manifests, and verifier quarantine | Implemented as a pre-testnet hardening addition; current local aggregates pass, while exact-commit CI and independent review remain required. |
| Audit controls | `audit_program.py`, `deployment_readiness.py`, `economic_concentration.py`, `run_economic_adversarial.py`, `validate_agent_red_team.py` | Structural validation passed; audit/economic regressions, the seeded 100,000-epoch economic campaign, deployment checks, and 12-class agent corpus validation passed. Readiness remains fail-closed. |
| Runtime syntax and direct safety checks | `py_compile` plus direct S-MMU/proof assertions | Passed for changed gateway/runtime/audit modules; S-MMU traversal/reset and TEE/ZK fail-closed assertions passed directly. |

Verification still pending or blocked locally:

| Scope | Status |
| --- | --- |
| Exact-commit aggregate rerun | PR merge-SHA CI run `29416245559` passed Python (including pinned PostgreSQL), Forge, Aiken, VIR-Core linked tests, frontend, Bandit/pip-audit, Semgrep, Slither, SBOM, Gateway, audit, and first-party controls. Gitleaks and TruffleHog correctly failed on unresolved history, so the aggregate Security Evidence Gate failed and readiness stayed skipped. Clean post-history-rewrite candidate CI and a signed aggregate manifest remain required. |
| Historical secret exposure | Gitleaks retains three historical PEM finding occurrences representing two unique keys, plus provider-helper findings. Run `29413794423` verified one Infura finding at `simulate-request-v3.mjs`, line 6, commit `1321f91586784d218ebc11126de588fbcf649ec6`; run `29416245559` later classified all 20 sanitized detector events as unverified. The Desktop owner attestations are supporting inputs, not artifact-bound closure evidence. Provider/PEM decommissioning evidence, replacement fingerprints, role and funding impact artifacts, coordinated all-ref cleanup, collaborator re-cloning, and zero-finding rescans are mandatory. |
| Semgrep exact-commit evidence | The three initial timeout paths completed in the longer-timeout supplemental scan with zero findings. Preserve both raw runs and rerun them against the final commit in CI. |
| Aiken transaction properties | Schema-v2 transaction fixtures cover exact creation/successors, duplicate identity/vote rejection, forged and replayed claim/payout rejection, malformed intents, premature execution, unauthorized cancellation, datum/value substitution, and bridge/slashing fail-closed behavior. Independent protocol review and applied-script rehearsal remain required. |
| Slither adjudications | The 19 residual medium-scan results are documented; independent review and the complete low/informational report remain required. |
| TruffleHog | Protected run `29416245559` used `--results=verified,unknown,unverified` and produced sanitized metadata for 20 unverified findings. Earlier run `29413794423` verified one of the Infura events. No raw value is retained. The gate remains blocking pending provider/PEM evidence, candidate adjudication, history cleanup, and a zero-finding rescan. |
| Default credential scan | Passed locally and in PR CI run `29416245559`; rerun on the clean post-history-rewrite candidate SHA remains required. |
| Mock-mode promotion scan | Passed locally and in PR CI run `29416245559`; rerun on the clean post-history-rewrite candidate SHA remains required. |
| Public-content policy scan | Passed locally and in PR CI run `29416245559`; rerun on the clean post-history-rewrite candidate SHA remains required. |

Required full gate set before public testnet:

```bash
cd contracts
forge build --sizes
forge test -vvv
slither . --config-file slither.config.json

cd cardano
aiken check --deny --seed 20260713 --max-success 250

pytest -v --tb=short
bandit -r neuron/ gateway/ -ll -ii
pip-audit

cd frontend-vite
npm ci
npm audit --audit-level=high
npm run build

gitleaks detect --source .
trufflehog filesystem .
semgrep scan
```

---

## 7. July 2026 Public Testnet Roadmap

Public Testnet is targeted for a July 2026 launch window. This is a gated rollout, not a fixed launch date.

### Launch Gates

Public testnet should not open until all of the following are true:

- No live mock-mode paths for DA, identity, Trails, TEE, bridge, or escrow-state clients.
- Live Service Blocks declare a memory policy and do not perform unreviewed autonomous text-memory rewriting.
- Gateway DID auth, mTLS/proxy certificate telemetry gate, Caddy/TLS deployment, loopback live bind, and production CORS review are complete.
- CI security gates include Forge, Aiken, pytest, Bandit, pip-audit, npm audit, frontend build, Gitleaks, SBOM, Cosign, Slither, Semgrep, Trufflehog, default credential scan, and mock-mode promotion scan.
- Current focused Foundry, Aiken, Python, and Rust-check gates pass locally;
  complete current-branch language aggregates and exact-commit analyzer gates
  remain pending. Historical Gitleaks is red; the baseline Semgrep run passed
  with 17 directly adjudicated timeout pairs. TruffleHog,
  signed SBOM, Cosign, and exact-commit CI evidence remain required.
- Gnosis Safe or equivalent multisig roles are documented.
- Timelock and privileged role ownership are documented.
- Polygon Amoy and Cardano Pre-Prod deployment addresses are recorded.
- `contracts/CONTRACTS.md` includes chain IDs, contract addresses, transaction hashes, verification status, role owners, and timelock references.

### July Execution Plan

| Window | Objective | Exit Criteria |
| --- | --- | --- |
| Week 1 | CI/security gates and docs reality sync. | Missing scans added; status report, changelog, API docs, and hardening docs aligned with source reality. |
| Week 2 | Deploy rehearsal and role ownership ceremony. | Dry-run deployment artifacts produced; Safe/timelock owners confirmed; mock-mode scan clean for live configuration. |
| Week 3 | Polygon Amoy and Cardano Pre-Prod public testnet deployment. | Contracts/validators deployed; addresses and tx hashes recorded; gateway connected to testnet endpoints. |
| Week 4 | Public node/operator onboarding, telemetry monitoring, first mission. | Operator guide published; heartbeat telemetry monitored; first builder/operator mission launched with incident response process. |

---

## 8. Future Roadmap

| Period | Roadmap |
| --- | --- |
| August 2026 | Incentivized testnet missions, live monitoring dashboards, node operator onboarding, DA adapter hardening, expanded testnet telemetry, and calibrated stateful-vs-stateless gain monitoring. |
| September 2026 | External audit readiness, broader DePIN/provider integrations, frontend wallet workflows, and integration burn-in across Polygon Amoy and Cardano Pre-Prod. |
| Q4 2026 | Guarded mainnet preparation only if public testnet, external audit, multisig/timelock ownership, live integration evidence, and monitoring gates pass. |

Mainnet remains conditional. No mainnet date should be promised until public testnet evidence, audit results, governance readiness, and operational monitoring are complete.

---

## 9. Immediate Engineering Priorities

1. Rotate/decommission both unique key identities represented by the three
   historical PEM finding occurrences, prove they control no funded or
   privileged role, coordinate all-ref
   rewrite/reclone/fork/cache cleanup, and satisfy credential-incident schema
   v3 with zero-finding complete-history Gitleaks and all-category TruffleHog
   scans.
2. Freeze candidate SHA A after the rewrite and run every pinned stage gate,
   including PostgreSQL and Linux Rust tests, without signing an aggregate that
   lacks operational evidence.
3. Provision the distinct real Safes and timelock, apply reviewed Cardano public
   parameters, and produce unsigned Polygon/Cardano rehearsal manifests with
   `deployment_source_sha == commit_sha`.
4. Record real Celestia Mocha and Near Testnet inclusion/retrieval evidence,
   external Gateway evidence, and named privacy acceptance; keep all VDSO
   sidecar publication excluded.
5. Promote only evidence-supported G0-G4 status at SHA B, rerun stage and
   operational workflows, then sign the combined manifest and pass canary
   readiness before requesting deployment approval.
6. After explicit transaction-specific approval, broadcast once and verify
   every identity, code hash, role, paused/empty state, and confirmation through
   independent providers.
7. Run the seven-day faucet-only canary and private read-only shadow lane with
   at least $1 \times 10^5$ transitions, complete six explicitly
   non-independent Architect-bootstrap dossiers, and require all 36 tracks
   verified before `bootstrap-public` promotion with `VDSO_MODE=off`.
8. Keep the later `public` stage blocked until independent reviews and the
   governance migration are available; no lack of funding may be hidden by an
   unsupported assurance claim.

---

## 10. Public Testnet Readiness Summary

| Area | Readiness |
| --- | --- |
| Protocol implementation | Current working-tree Python, Foundry, Aiken, Rust format/check/Clippy, frontend, and analyzer gates pass where executable. PostgreSQL and Rust linked tests remain environment-blocked, and every gate must rerun against the exact clean post-history-rewrite SHA. |
| Gateway security | Live clients require HTTPS, direct server bind is loopback, and DID/mTLS/replay/input gates exist; live deployment config and external route smoke tests still required. |
| Runtime integrations | Incomplete routes now fail closed or are excluded; real enabled-route evidence remains required. |
| Deployment evidence | Safe/timelock identity-bound ceremony, strict manifests, non-deployable Cardano template extraction, and fail-closed parameter application exist; real public parameters, applied hashes, addresses, transactions, ownership observations, rehearsal, and rollback evidence remain incomplete. |
| CI/security posture | Local build/analyzer gates pass, and Semgrep's three initial timeout paths completed cleanly in the supplemental run. Historical Gitleaks is blocking; TruffleHog, signed SBOM/Cosign evidence, external review, and aggregate CI evidence remain required. |
| VDSO posture | Public mode remains `off`. The private lane is read-only shadow only; Cardano `vdso.ak` is conformance-only. No VDSO deployment or authoritative/value-bearing activation is claimed. |
| Public launch status | Readiness remains 0 verified, 3 implemented, 29 partial, and 4 blocked tracks. July 2026 is a gated window, not a guaranteed date. |

---

**Maintainer:** Aseem Chishti
**Repository:** `https://github.com/GodOfAgents/VAMS`
