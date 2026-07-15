# VAMS Repository Status Report And Public Testnet Roadmap

**Date:** 2026-07-15
**Last verified:** 2026-07-15 (partial working-tree gates only)
**Stage:** Hardened Pre-Testnet Candidate
**Current Priority:** Phase 6: Closed Public-Testnet Baseline + Private VDSO Shadow Hardening
**Public Testnet Target:** July 2026 launch window
**Architecture Baseline:** v0.8.0 cognitive/composer layer + v1.3.0-oms runtime + June gateway hardening
**Branch Baseline:** last clean commit `9a5ef63cd76327a3c226b3249fb4138691789512`, based on `main` at `31929a24419a9b7b9d8954cbea2df9fe1cb77a68`; Cardano/evidence hardening is currently uncommitted and signed aggregate release evidence is absent

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

Current blockers before public testnet:

- Readiness is fail-closed at 3 implemented, 29 partial, 4 blocked, and 0 verified tracks. The current hardening changes are not yet committed, and no track may advance until every gate reruns against the exact final post-history-rewrite SHA in CI and the complete manifest is signed.
- Current working-tree verification passes full Python, Foundry, Aiken,
  Rust format/check/deny-warnings Clippy, frontend build/audit, Bandit,
  pip-audit, Semgrep, Slither fail-high, and first-party structural gates.
  The focused credential/deployment/audit set passes 41/41. PostgreSQL remains
  unavailable and Rust linked tests remain environment-blocked because this
  Windows host lacks MSVC `link.exe`. Local results are not signed
  exact-commit evidence while the tree remains uncommitted.
- The full Semgrep scan has zero findings; its three initial timeout paths were
  rerun with a longer per-rule budget and completed with zero findings.
  Historical
  Gitleaks is blocking on three committed PEM private keys. TruffleHog,
  SBOM/signing, and aggregate CI evidence remain promotion gates.
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
| Solidity contracts (`contracts/src/`) | Implemented, Working-Tree Verification Clean | Full Foundry passes 709/709 across 40 suites after the Safe/VDSO changes. Whole-tree `forge fmt --check` passes after deterministic formatter cleanup. | Rerun against the clean release commit in CI, then complete independent review, deployment rehearsal, role ownership review, and deployment address registry. |
| Cardano validators (`cardano/validators/`) | Schema-v2 State Machines Implemented, Working-Tree Verification Clean | Four persistent validators preserve explicit authentication asset classes and exact datum/value transitions. Three seed/bootstrap policies are auxiliary templates. Bridge execution, cross-chain deposits, and slashing fail closed; local timelock targets are allowlisted. Seeded Aiken verification passes 71 unit tests and 6 properties (77/77), with 250 successful cases per property, and the blueprint rebuild succeeds. `cardano/lib/vams/vdso.ak` remains conformance-only. | Apply reviewed public parameters, independently verify final hashes, rerun on the exact clean post-rewrite SHA in CI, and retain signed rehearsal evidence. |
| Neuron runtime (`neuron/`) | Implemented, Working-Tree Verification Clean, Live Routes Restricted | Mock clients remain available locally but are blocked from live profiles. The non-PostgreSQL Python aggregate passes 753 tests with one intentional Rust-binary environment skip. The real PostgreSQL atomicity/restart gate was not run on this tree because no service is available. | Run the PostgreSQL gate, rerun all Python tests in exact-commit CI, and collect live integration evidence for every enabled route. |
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

Current working-tree results are explicitly marked below. They are local
verification, not signed exact-commit evidence, because the tree is uncommitted
and credential history remediation must precede the release SHA. The branch
started from `main` at
`31929a24419a9b7b9d8954cbea2df9fe1cb77a68`:

| Scope | Command | Result |
| --- | --- | --- |
| Solidity verification | `forge build --sizes`; `forge test -vvv`; `forge fmt --check` | Current working tree passed: 709/709 tests across 40 suites, zero failures/skips; build and whole-tree formatting pass. Compiler warnings remain recorded for cleanup/review. |
| Aiken verification | `aiken fmt --check`; `aiken check --deny --seed 20260713 --max-success 250`; `aiken build` | Current working tree passed: 71 unit tests and 6 properties, 77/77 total, with 250 successful cases per property; the parameterized `plutus.json` blueprint was regenerated. |
| Credential/deployment/audit regressions | Focused pytest for credential incident, Cardano artifact/application tooling, audit program, and workflow security | Current working tree passed 41/41 on 2026-07-15. This focused result does not replace the full protocol gates. |
| Python current tree | `python -m pytest -q --tb=short --ignore=neuron/tests/test_vdso_postgres_integration.py` | Passed: 753 tests, 1 intentional Rust-binary environment skip, and one upstream `websockets.legacy` deprecation warning. The separate PostgreSQL gate is environment-blocked on this host and is not claimed. |
| Python security lint | `bandit -r neuron gateway -ll -ii -q` | Passed with no qualifying medium/high-severity, medium/high-confidence finding. |
| Python dependency audit | `pip-audit -r gateway/requirements.txt` and `pip-audit -r neuron/requirements.txt` | Passed: no known vulnerabilities in either resolved requirement set. The unpatched `python-ecdsa` package was removed from production requirements. |
| VIR-Core current branch | `cargo fmt --all --check`; `cargo check --workspace --all-targets --locked`; `cargo clippy --workspace --all-targets --locked -- -D warnings`; `cargo test --workspace --all-targets --locked` | Format, check, and deny-warnings Clippy pass. Linked tests are unavailable because MSVC `link.exe` is not installed; run them on Linux CI or install the Visual Studio C++ workload. |
| Semgrep | Exact workflow scan command | Passed: zero findings across 464 tracked files/520 rules, with 99.9% parsed. Exact-commit CI and independent adjudication remain required. |
| Slither | `slither . --exclude-dependencies --exclude-low --exclude-informational --fail-high` | Passed fail-high: 181 contracts, 63 detectors, 0 high findings; 19 residual results are locally adjudicated in `docs/audit/SLITHER_ADJUDICATION.md` and still require independent acceptance. |
| Gitleaks history | Gitleaks v8.30.1 `git --log-opts=--all` with fully redacted reporting | Failed: 1,740 matches (1,737 generic-key and 3 private-key findings) across 15 finding-bearing commits, including the three historical PEM files. Classification and mandatory closure are in `docs/audit/GITLEAKS_ADJUDICATION.md`. |
| Frontend install | `npm ci` | Passed: 176 packages installed/audited, 0 vulnerabilities. |
| Frontend audit | `npm audit --audit-level=high` | Passed: 0 vulnerabilities. |
| Frontend build | `npm run build` | Passed with Vite 7.3.6. |
| Report/diff hygiene | `git diff --check` | Pending final documentation reconciliation and commit preparation. |
| Gateway/runtime/VDSO focused tests | Focused pytest selection covering Gateway auth/lifecycle, VDSO semantics, PostgreSQL stores, runtime safety, and the private shadow worker | Passed: 134 with one intentional skip for the real Rust binary that cannot be linked on this Windows host. The real Aiken exported UPLC integration passed. |
| Phase 6 security scripts | `default_credential_scan.py`, `public_content_policy_scan.py`, `mock_mode_promotion_scan.py` | Passed on the current tree on 2026-07-14. |
| Python syntax check | `compileall` on the VDSO/Gateway modules | Passed on the current tree on 2026-07-13. |
| VDSO evidence/docs | `validate_vdso_evidence.py`, its five tests, `validate_docs.py`, and audit-program validation | Passed on the current tree. |
| R10 world-state and SkillOps hardening | `WorldStateFidelitySentinel`, Service Block EIP-712 manifests, and verifier quarantine | Implemented as a pre-testnet hardening addition; current local aggregates pass, while exact-commit CI and independent review remain required. |
| Audit controls | `audit_program.py`, `deployment_readiness.py`, `economic_concentration.py`, `run_economic_adversarial.py`, `validate_agent_red_team.py` | Structural validation passed; audit/economic regressions, the seeded 100,000-epoch economic campaign, deployment checks, and 12-class agent corpus validation passed. Readiness remains fail-closed. |
| Runtime syntax and direct safety checks | `py_compile` plus direct S-MMU/proof assertions | Passed for changed gateway/runtime/audit modules; S-MMU traversal/reset and TEE/ZK fail-closed assertions passed directly. |

Verification still pending or blocked locally:

| Scope | Status |
| --- | --- |
| Exact-commit aggregate rerun | Local Python/Foundry/Aiken/Rust-check/frontend/analyzer/security gates are green where executable, but PostgreSQL and Rust linked tests remain environment-blocked. Clean-tree post-history-rewrite CI and a signed aggregate manifest remain required. |
| Historical secret exposure | Gitleaks reports 1,740 historical matches, including three committed PEM private keys. Rotation/revocation, funded-account and privileged-role impact proof, coordinated history cleanup, collaborator re-cloning, and clean complete-history Gitleaks/TruffleHog rescans are mandatory. |
| Semgrep exact-commit evidence | The three initial timeout paths completed in the longer-timeout supplemental scan with zero findings. Preserve both raw runs and rerun them against the final commit in CI. |
| Aiken transaction properties | Schema-v2 transaction fixtures cover exact creation/successors, duplicate identity/vote rejection, forged and replayed claim/payout rejection, malformed intents, premature execution, unauthorized cancellation, datum/value substitution, and bridge/slashing fail-closed behavior. Independent protocol review and applied-script rehearsal remain required. |
| Slither adjudications | The 19 residual medium-scan results are documented; independent review and the complete low/informational report remain required. |
| TruffleHog | The pinned audit wrapper correctly refused to scan a dirty worktree. Run it only after the final local commit and again after the coordinated all-ref rewrite; historical PEM findings remain blocking. |
| Default credential scan | Represented in the workflow and passed locally; pending CI execution. |
| Mock-mode promotion scan | Represented in the workflow and passed locally; pending CI execution. |
| Public-content policy scan | Represented in the workflow and passed locally; pending CI execution. |

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

1. Rotate/revoke the three historically committed PEM identities, prove they control no funded account or privileged role, coordinate the all-ref rewrite/reclone/fork/cache cleanup, and satisfy the new artifact-bound credential incident report with clean complete-history rescans.
2. Resolve the pinned Aiken packages, execute the schema-v2 transaction suite with seed `20260713`, build and regenerate `cardano/plutus.json`, then add any remaining adversarial transaction regressions found by the run.
3. Freeze the post-history-rewrite commit and run the implemented security workflow against that exact clean SHA; retain the complete signed aggregate evidence manifest.
4. Supply reviewed public Cardano parameter CBOR, apply the four persistent validators and canonical fund bootstrap (plus only real agent/proposal creation instances), independently reproduce final hashes, and construct the unsigned Pre-Prod transaction body.
5. Rehearse `DeployTestnet.s.sol` and the empty paused VDSO suite against real Safe/timelock instances on Polygon Amoy without broadcasting.
6. Record real Celestia Mocha and Near Testnet inclusion/retrieval evidence plus external Gateway TLS/mTLS/rate-limit evidence; keep all VDSO sidecar publication excluded.
7. Complete independent Solidity/governance, Aiken/bridge, economics, Gateway/SDK, privacy, and AI-agent-safety reviews bound to the exact commit.
8. After explicit broadcast approval, run the seven-day faucet-only canary and private read-only shadow lane with at least $1 \times 10^5$ transitions, durable restart/replay, zero divergence, zero writes, and signed privacy evidence.

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
