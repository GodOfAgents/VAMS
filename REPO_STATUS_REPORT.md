# VAMS Repository Status Report And Public Testnet Roadmap

**Date:** 2026-07-25
**Last verified:** 2026-07-25
**Stage:** Hardened Pre-Testnet Candidate
**Current Priority:** Phase 6: Public Testnet Readiness
**Public Testnet Target:** Gate-driven; no calendar date overrides readiness
**Architecture Baseline:** v0.8.0 cognitive/composer layer + v1.3.0-oms runtime + June gateway hardening
**Commit History Boundary:** `31929a2` plus the uncommitted credential-history
preparation branch; no post-rewrite exact-commit release evidence exists

---

## 1. Source Of Truth

This report is a technical public status document. It is intended to replace stale roadmap language with repository-backed implementation reality.

Interpretation rules:

- Commit history is the chronology source.
- `AGENTS.md`, `docs/CHANGELOG.md`, `audit.md`, executable tests, and current source code override stale roadmap claims.
- Historical test totals are not current facts unless rerun against the current tree.
- VAMS is pre-testnet. This report does not claim mainnet, production, or fully audited readiness.
- Public testnet timing is controlled by security, verification, deployment
  artifacts, governance, and operator-readiness gates.

No deployment statement in this document should be read as a mainnet claim.

---

## 2. Executive Status

VAMS is a hardened pre-testnet candidate. The repository contains implemented Solidity contracts, Aiken validators, Neuron runtime modules, Gateway services, Composer scoring, frontend assets, and a security/build workflow foundation.

The system is not mainnet-ready. It is not yet a public testnet deployment. The remaining work is no longer abstract architecture; it is concrete verification, deployment ceremony, live configuration, and operational hardening.

Current blockers before public testnet:

- Readiness is fail-closed at 3 implemented, 29 partial, 4 blocked, and 0 verified tracks. The worktree is not a release candidate until committed and rerun in CI.
- The current local Python aggregate passes 684/684 in workspace-local,
  componentized runs, including the VDSO Neuron/Gateway boundary. The
  monolithic sandbox run was blocked by temporary-directory ACLs rather than a
  test assertion. An exact-commit CI rerun is still required before this
  becomes release evidence.
- Local Bandit, pip-audit, Slither fail-high, Foundry, Aiken, Linux Rust,
  frontend, and first-party gates pass. Semgrep reports zero findings; all 17
  tracked/supplemental timeout pairs received separate direct source
  adjudication with no confirmed vulnerability. Historical
  PR 4 run `29611633518` is blocking on 869 Gitleaks findings and 20
  unverified TruffleHog findings. Three PEM occurrences map to two
  permanently decommissioned identities; the all-ref rewrite, remote cleanup,
  clean rescans, SBOM/signing, and aggregate evidence remain promotion gates.
- Avail and EigenDA remain structured stubs and must stay blocked from live environments.
- Deployment artifacts are incomplete: chain IDs, addresses, transaction hashes, verification status, multisig owners, and timelock ownership.
- Live DA, identity, Trails, TEE, and gateway configuration need testnet evidence.
- Continual-learning telemetry still needs calibration and independent review; Service Block memory policy, authorized persistent mutation, deterministic S-MMU reset, and telemetry-only reward isolation are now enforced in source.
- Frontend browser hardening remains pending: CSP/XSS runtime checks, phishing/accessibility review, and any future wallet workflow.
- VDSO remains a side-by-side canary foundation, not a deployed protocol. Its
  evidence-hardened ADR/review, VIR-Core reference, Polygon contracts,
  Neuron/Gateway boundary, and Cardano conformance checks now exist. Real proof
  backends, an audited HPKE and ML-DSA path, live adapter evidence, durable
  stores, dual-host migration rehearsal, independent review, and deployment
  evidence remain blocking.

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
| Solidity contracts (`contracts/src/`) | Implemented, Local Aggregate Clean | Final-tree `forge build --sizes` passes and `forge test -vvv` passes 693/693 tests across 40 suites. `VAMSExecutionKernel` is 10,467 bytes with 14,109 bytes of runtime-size margin. Changed VDSO/deployment paths pass formatting; repository-wide formatting retains unrelated legacy drift. | Bind the run to a clean release commit in CI, then complete independent review, deploy rehearsal, role ownership review, and deployment address registry. |
| Cardano validators (`cardano/validators/`) | Implemented, Unit and Property Suites Clean | `aiken check --deny --seed 20260713 --max-success 250` passes 43 unit tests and 7 properties over 1,750 generated cases; all 50 definitions pass, including 10 VDSO conformance cases. | Expand transaction-level validator properties, retain CI evidence, create the Pre-Prod deployment record, and complete governance/timelock ceremony evidence. |
| Neuron runtime (`neuron/`) | Implemented, Local Aggregate Clean, Live Routes Restricted | Mock clients remain available locally. Testnet rejects mock identity, payment, bridge, TEE, interrupt, and storage paths; incomplete economic interrupts and proof types are excluded. The final local Python aggregate passes 684/684 tests. Gateway clients require HTTPS live and use canonical low-S ECDSA/SHA-256 signatures. | Exact-commit CI evidence and live integration evidence for every enabled route. |
| Data availability | Implemented, Live Evidence Pending | Celestia live failures no longer fall back to mock receipts and exact retrieval is required. Near non-mock submission is disabled until signed submission and retrieval exist. Mock receipts are never verified; Avail, EigenDA, and current VDSO DA paths remain release-ineligible. | Record real Celestia Mocha and Near Testnet submission, inclusion, independently observed retrieval, and payload-match artifacts before enabling either route. |
| Gateway (`gateway/server.py`) | Implemented, Needs Live Verification | Gateway requires DID auth, replay protection, proxy-verified mTLS, explicit live CORS origins, bounded methods/headers, request limits, rate limiting, loopback binding, and Caddy TLS. | Certificate allowlist, live route/size/rate smoke tests, gateway pytest evidence, and external TLS scan. |
| Composer and cognitive layer | Implemented | CHC 10-axis cognitive profiles and 6-axis composer scoring exist. Cognitive score: $$S_{cog}=1.0-\frac{1}{|D_{req}|}\sum_{d \in D_{req}}\max(0.0, Req_d-Profile_d)$$ | Keep scorer tests passing; verify real node telemetry maps correctly into candidate ranking. |
| Economics and regional incentives | Implemented, Synthetic Campaign Clean | Regional/yield caps and hybrid thin-liquidity pricing exist. The seeded 100,000-epoch campaign detected all injected linked-reward, linked-capacity, regional-capture, thin-liquidity, and wash-return attacks with zero misses or baseline false positives. | Run the analyzer against live beneficial-owner attestations and add governance/settlement state-machine simulations. |
| Frontend (`frontend-vite/`) | Read-Only Testnet Profile, Build Clean | Gateway origin is environment-bound and HTTPS-only in production. CSP removes inline scripts and external fonts. Vite production build and npm audit pass. Wallet transactions, real fiat, real yield, and staking rewards are disabled for the first testnet profile. | CI Node 22 evidence, browser CSP verification, phishing review, and accessibility review. |
| CI/CD (`.github/workflows/security-gates.yml`) | Implemented, Needs CI Evidence | Workflow includes all language/security scanners, signed SBOM, signed audit evidence, deployment source checks, economic-control tests, and separate evidence/readiness gates. | Run on the current commit and configure branch protection for the Security Evidence Gate. |
| Deployment artifacts | Identity-Bound Ceremony Implemented, Runtime Evidence Pending | Polygon scripts bind each 3-of-5/3-of-5/2-of-3 Safe to proxy/singleton bytecode, require the exact compiled VAMS timelock runtime and at least 48 hours, disable rewards/minter authority, and remove deployer roles. Manifest validation separately binds Polygon code/roles and Cardano script/multisig evidence. | Supply real authorities, rehearse both hosts, verify bytecode/script hashes, and record role transfers, addresses, transactions, and rollback evidence. |
| VDSO deterministic state-object canary | Canary Foundation Implemented, Deployment Blocked | `vams-vm/`, `contracts/src/vdso/`, `neuron/vdso/`, `gateway/vdso.py`, and `cardano/lib/vams/vdso.ak` implement a side-by-side foundation with Rust/Python/Aiken intent conformance, per-domain host/epoch authority, signed capability derivation, Tier-2 hybrid policy for mutations and every nonzero settlement-cost budget, native Cardano `READ`/`ACCUMULATE` checks, Polygon-side rejection of Cardano writes, fencing/recovery, INV-10 proof separation, signed sidecar-root joins, and fail-closed DA routing. No VDSO deployment or authoritative migration is claimed. | Complete real SP1/RISC Zero verification, reviewed HPKE and ML-DSA backends, persistent replay/nonce stores, immutable direct adapter/verifier assurance, live DA evidence, independent review, deployment rehearsal evidence, and a governance-approved domain migration before promotion. |

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

Latest local evidence:

| Scope | Command | Result |
| --- | --- | --- |
| Solidity build and tests | `forge build --sizes`; `forge test -vvv`; scoped changed-path `forge fmt --check` | Passed: 693/693 tests across 40 suites. `VAMSExecutionKernel` runtime is 10,467 bytes with 14,109 bytes of EIP-170 margin. |
| Aiken tests | `aiken check --deny --seed 20260713 --max-success 250` | Passed: 43 unit tests and 7 properties over 1,750 generated cases; all 50 definitions passed, including 10 VDSO cases. |
| Python aggregate | `pytest -q --tb=short -p no:cacheprovider` partitioned with workspace-local `--basetemp` paths | Passed: 684/684 tests (236 Neuron group A, 395 Neuron group B excluding the isolated latency case, 52 scripts, and 1 deterministic latency regression). The monolithic sandbox runs encountered temporary-directory ACL errors; exact-commit CI evidence remains pending. |
| Python security lint | `python -m bandit -r neuron gateway -ll -ii` | Passed the configured gate across 28,733 lines: 0 high findings and no reportable medium/high-confidence issue. Raw metrics retained 1 medium low-confidence and 1,078 low-severity results for triage. |
| Python dependency audit | `pip-audit -r gateway/requirements.txt` and `pip-audit -r neuron/requirements.txt` | Passed: no known vulnerabilities in either resolved requirement set. The unpatched `python-ecdsa` package was removed from production requirements. |
| VIR-Core Linux verification | Rust 1.92 Docker: `cargo fmt`, `cargo check --workspace --all-targets --locked`, `cargo clippy ... -D warnings`, `cargo test --workspace --all-targets --locked` | Passed: all 34/34 executable tests, format, check, and Clippy. |
| Semgrep | `semgrep scan --config auto --error` with generated/vendor exclusions plus an explicit untracked VDSO scan | Passed with adjudicated timeouts: zero findings across 444 tracked files/520 rules and 61 untracked VDSO files/314 rules. Seventeen rule/file timeout pairs were directly reviewed with no confirmed vulnerability; details are in `docs/audit/SEMGREP_ADJUDICATION.md`. Exact-commit CI rerun remains required. |
| Slither | `slither . --exclude-dependencies --exclude-low --exclude-informational --fail-high` | Passed configured threshold: 0 high findings; 19 medium results independently classified in `docs/audit/SLITHER_ADJUDICATION.md`. |
| Gitleaks history | PR 4 run `29611633518`; Gitleaks v8.30.1 with complete-history redacted reporting | Failed: 869 findings across 65 scanned commits. The broader earlier local inventory is retained as separate context; mandatory closure is in `docs/audit/GITLEAKS_ADJUDICATION.md`. |
| TruffleHog history | PR 4 run `29611633518`; TruffleHog 3.95.9 with verified, unknown, and unverified results | Failed: 20 unverified findings. Raw candidate values are excluded from committed evidence. |
| Frontend install | `npm ci` | Passed: 176 packages installed/audited, 0 vulnerabilities. |
| Frontend audit | `npm audit --audit-level=high` | Passed: 0 vulnerabilities. |
| Frontend build | `npm run build` | Passed with Vite 7.3.6. |
| Report/diff hygiene | `git diff --check -- ...` | Passed. |
| Gateway/auth/VDSO focused tests | `pytest -q neuron/tests/test_gateway_client_security.py neuron/tests/test_gateway_auth_hardening.py neuron/tests/test_gateway_current.py neuron/tests/test_vdso_gateway.py` | Passed: 37/37 on the current tree. |
| Phase 6 security scripts | `default_credential_scan.py`, `secret_history_prevention_scan.py`, `public_content_policy_scan.py`, `mock_mode_promotion_scan.py` | The new secret-history prevention scan passes on the preparation tree; the complete suite requires exact-commit CI. |
| Python syntax check | `compileall` on the VDSO/Gateway modules | Passed on the current tree on 2026-07-13. |
| VDSO evidence/docs | `validate_vdso_evidence.py`, its five tests, `validate_docs.py`, and audit-program validation | Passed on the current tree. |
| R10 world-state and SkillOps hardening | `WorldStateFidelitySentinel`, Service Block EIP-712 manifests, and verifier quarantine | Implemented as a pre-testnet hardening addition; current local aggregates pass, while exact-commit CI and independent review remain required. |
| Audit controls | `audit_program.py`, `deployment_readiness.py`, `economic_concentration.py`, `run_economic_adversarial.py`, `validate_agent_red_team.py` | Structural validation passed; audit/economic regressions, the seeded 100,000-epoch economic campaign, deployment checks, and 12-class agent corpus validation passed. Readiness remains fail-closed. |
| Runtime syntax and direct safety checks | `py_compile` plus direct S-MMU/proof assertions | Passed for changed gateway/runtime/audit modules; S-MMU traversal/reset and TEE/ZK fail-closed assertions passed directly. |

Verification still pending or blocked locally:

| Scope | Status |
| --- | --- |
| Exact-commit aggregate rerun | Local language gates pass on the dirty implementation tree; CI must rerun them against the final clean commit and sign the aggregate manifest. |
| Historical secret exposure | PR 4 run `29611633518` reports 869 Gitleaks findings and 20 unverified TruffleHog findings. Three PEM occurrences represent two decommissioned identities. The coordinated all-ref rewrite, GitHub cache/PR cleanup, collaborator reclones, and zero-finding rescans are mandatory. |
| Semgrep timeout closure | Seventeen rule/file timeout pairs were directly adjudicated as non-findings after both scans exited zero. Preserve the adjudication, rerun after the post-scan workflow edit, and obtain external reviewer acceptance with exact-commit evidence. |
| Aiken transaction properties | Pure-function properties now cover quadratic bounds, basis-point safety, range semantics, nonce replay/order, and insurance payout caps. Transaction-level datum/value/state-machine properties remain required. |
| Slither adjudications | The 19 residual medium-scan results are documented; independent review and the complete low/informational report remain required. |
| TruffleHog | Executed in PR 4 and failed on 20 unverified historical findings; the preparation workflow expands enforcement to verified, unknown, and unverified results with sanitized artifacts. |
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
aiken check

pytest -v --tb=short
bandit -r neuron/ gateway/ -ll -ii
pip-audit

cd frontend-vite
npm ci
npm audit --audit-level=high
npm run build

gitleaks git . --redact=100 --report-format json --log-opts=--all
trufflehog git "file://$PWD" --json --fail --no-update --results=verified,unknown,unverified
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
- Foundry, Aiken, full pytest, Bandit, pip-audit, Linux Rust, frontend,
  Slither fail-high, and first-party policy gates pass locally. Historical
  Gitleaks is red; Semgrep passes with 17 directly adjudicated timeout pairs;
  TruffleHog,
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

1. Run the implemented security workflow on the current commit and retain the aggregate audit-gate evidence manifest.
2. Land the incident-only preparation PR, then rewrite all affected refs for
   the three PEM occurrences/two permanently decommissioned identities and
   obtain zero-finding Gitleaks and all-category TruffleHog rescans.
3. Independently review the 19 residual Slither findings and the 17 Semgrep timeout adjudications against the exact release commit.
4. Expand Aiken properties to transaction-level state machines and complete the signed SBOM and aggregate evidence in CI.
5. Rehearse `DeployTestnet.s.sol` against deployed Safe contracts and complete Polygon Amoy evidence.
6. Replace the current ineligible Near/Celestia VDSO adapters with retrieval-bound evidence implementations, then record real receipts and external gateway TLS/mTLS/rate-limit evidence.
7. Complete the public-content/privacy review and current Python/Aiken security suites.
8. Run external contract, bridge, economic, gateway/SDK, and AI-agent reviews before public onboarding.

---

## 10. Public Testnet Readiness Summary

| Area | Readiness |
| --- | --- |
| Protocol implementation | Python passes 684/684, Aiken passes all 50 definitions with 1,750 property iterations, Foundry passes 693/693, and Linux Rust passes 34/34. Exact-commit CI evidence remains required. |
| Gateway security | Live clients require HTTPS, direct server bind is loopback, and DID/mTLS/replay/input gates exist; live deployment config and external route smoke tests still required. |
| Runtime integrations | Incomplete routes now fail closed or are excluded; real enabled-route evidence remains required. |
| Deployment evidence | Safe/timelock identity-bound ceremony and strict Polygon/Cardano manifest validators exist; addresses, transactions, ownership observations, rehearsal, and rollback evidence remain incomplete. |
| CI/security posture | Most local build/analyzer gates pass, including Semgrep with 17 separately adjudicated timeout pairs. Historical Gitleaks (869) and TruffleHog (20 unverified) findings are blocking; signed SBOM/Cosign and aggregate CI evidence remain required. |
| Public launch status | NO-GO until the gate-driven closure and deployment evidence are complete. |

---

**Architect:** Aseem Chishti
**Repository:** `https://github.com/GodOfAgents/VAMS`
