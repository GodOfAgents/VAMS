# VAMS restricted-testnet open-gate map — 2026-10-18

Status: **working reconciliation only; no gate is promoted by this document.**
This map records current open requirements, sources, evidence gaps, and the
authority or reviewer needed to close them. It does not authorize tests, host
work, installations, network activity, collection, qualification, or release.

## Snapshot and scope

- Repository: `/home/GodOfAgents/code/VAMS-testnet`, branch
  `testnet/remediation-20260907`, HEAD
  `829ab544571f12efe50ecb5740f129c8acb3e16f`. The worktree has extensive
  pre-existing modified and untracked work. It is preserved; HEAD is not a
  clean release snapshot. Any later evidence must bind the exact final tree.
- Approved profile: restricted faucet-only Polygon Amoy plus Cardano Pre-Prod.
  The checked-in profile disables staking rewards, real fiat, real yield
  capital, and VDSO. This profile does not convert disabled or mock-only
  features into verified implementations.
- Current matrix: 3 implemented, 29 partial, 4 blocked. Blocked tracks are
  T16, T21, T30, and T33.
- Current findings: F01–F03, F05–F07, and F10–F16 are `REVALIDATED_OPEN`.
  F04, F08, F09, F17, and F18 are `REMEDIATED` only within their recorded
  scopes.
- `docs/audit/evidence/` currently contains only
  `vdso-review-evidence.json`. The aggregate assurance manifest/index, both
  chain rehearsal records, runtime-integration report, and privacy review are
  not present there. Historical remediation packages do not substitute for
  exact-final-tree release evidence.

Inputs read for this snapshot:

| Record | SHA-256 |
|---|---|
| `docs/audit/control-matrix.json` | `28b9146bb2ace970c19441ab4cd8ee4f91937d56acf4f178b3639f5b4f493cf4` |
| `docs/remediation/FINDINGS.json` | `b62253b4b0c7d88355e04eeff3f51c06d6e15c462f083a7224e99f3a6b44dc35` |
| `docs/audit/testnet-profile.json` | `67136081adf06054b9385db7fe94987744529ed5a5f221ffb6ada0f5057153db` |
| `docs/audit/AUDIT_PROGRAM.md` | `75dd1c14c2852ad964d4b70d9905980dcbf7b98f27e10d3cfa11668b085f1784` |
| `docs/audit/INVARIANT_CONTROL_INDEX.md` | `315236c492566c0aa0cc14182ef8e3b35e50ff81dace57e86f8466115e0b5348` |
| `docs/remediation/READINESS_EXECUTION_LEDGER_20261008.md` | `7fbf9ed47cdb645e6f645f62f93c1f21451e6463f269a2cf9ba510f02c7dd803` |

The execution-ledger hash above is the exact pre-crosslink version read while
preparing this map. The ledger was subsequently append-linked to this map; the
link does not change the source statuses or evidence snapshot recorded here.

## Open protocol findings

For every row, acceptance requires the finding-specific adversarial cases,
current source/build binding, retained raw evidence, and independent review.
No test or compilation was run for this reconciliation.

| Finding | Affected source and requirement | Missing evidence and authorized next work | Acceptance and dependency |
|---|---|---|---|
| F01 | `cardano/validators/insurance_fund.ak`, `cardano/lib/vams/types.ak`, `cardano/plutus.json`; custody-preserving authenticated state, continuation, conservation, claims, and replay. | Deposit remains disabled; F05 authority/finality/replay is unresolved. Freeze the approved proof and state model before any separately authorized compiled transaction-context work. | Redirected value, missing/altered continuation, guardian changes, inflated balance, replay, wrong recipient/amount, and arbitrary proof bytes reject; inspect exact compiled script hash and datum. Cardano security and bridge reviewers; no funding/deployment authority. |
| F02 | `cardano/validators/timelock.ak`; authenticate DAO membership and bind cancel/queue to action, epoch, state, delay, and emergency scope. | Authenticated membership/state and exact action/epoch binding are absent. Owner/governance decision precedes separately authorized compiled transaction tests. | Arbitrary or duplicate signers, wrong action/epoch, missing state transition, normal use of emergency delay, and repeated execution reject. Cardano governance/security review. |
| F03 | `cardano/validators/governor.ak`, `cardano/validators/timelock.ak`; preserve unique voter state and exact intent/action binding. | No accepted state-asset continuity or voting-power snapshot/lock model. Resolve governance model, then authorize transaction-level tests. | Dropped/replaced/duplicated voters, repeated votes, wrong datum/action, asset substitution, and multiple continuations reject. Governance owner and Cardano security review. |
| F05 | `cardano/lib/vams/icb.ak`, `neuron/bridge_executor.py`, and consuming validators; verify real certificate/signature chains, domains, payload, epoch, finality, and replay. | Current ICB/Mithril checks are structural; live bridge effect remains disabled. Owner must select a real trust model/provider or explicitly keep the route disabled. | Forged length-correct proof, wrong domain/payload/epoch/finality, and concurrent/restarted replay reject; valid controls and durable replay evidence pass. Cryptography/bridge owner and independent reviewer. |
| F06 | `contracts/src/trust/plugins/TEEProofPlugin.sol`, `neuron/trust_plugins/tee_plugin.py`, and `neuron/sdk/phala_tee.py`; verify authenticated hardware quote, measurement, root/workload, challenge, freshness, TCB, and revocation. | No accepted real quote-verifier binding or hardware evidence. Do not treat the commitment check as TEE verification; keep TEE-dependent routes disabled pending owner trust-model selection and separately authorized verifier work. | Forged commitment and arbitrary bytes reject; authentic and wrong-root/workload/nonce/expired/revoked cases are distinguished. TEE owner, platform verifier, and independent security review. |
| F07 | `contracts/src/trust/plugins/ZKMLProofPlugin.sol`; call an approved verifier and bind proof to exact model/circuit/public inputs. | The configured backend is not called; current code returns the disabled result. Owner must select verifier, circuit, interface, and code identity. | Valid control accepted; false/reverting/malformed backend, tampered proof, swapped inputs, and unauthorized backend replacement reject. Cryptography owner and independent verifier. |
| F10 | `neuron/da/models.py`, `neuron/da/performance_audit.py`, DA adapters, and SDKs; canonical receipts, complete route coverage, submission and independent retrieval. | The source-only revalidation in `M5_DA_SOURCE_REVALIDATION_20261018.md` confirms Celestia submit/retrieval code is not release-evidence eligible and its light-client does not verify DAS; Near live submission/retrieval is blocked; Avail/EigenDA remain stubs; and the legacy Polygon DAC check is a placeholder. No independent exact-byte read-back/finality package exists. Select the real allowlisted routes and separate observer before external integration work. | Receipt swaps reject; `mock_mode=false`; distinct submitter/retriever; native inclusion evidence; retrieved bytes hash equals submitted bytes. Avail/EigenDA and other incomplete routes stay excluded. DA owner and separate observer/reviewer. |
| F11 | `neuron/sdk/cognitive_drift.py`, `neuron/sdk/interrupt_handler.py`, `neuron/neuron.py`; authenticated durable reconciliation and anchor state. | Current sync lacks authenticated quorum, finalized durable anchoring, and demonstrated reconciliation. Keep simulation explicitly non-authoritative. | Multi-process agreement, forged/stale-vote rejection, partition-safe behavior, epoch-preserving recovery, and real state update; stop effects when anchor evidence is absent. AI-safety owner and independent review. |
| F12 | `neuron/sdk/interrupt_handler.py`, `neuron/sdk/x402_recovery.py`, `neuron/payments/`, `neuron/anchoring.py`; durable effect identity, pre-effect policy, restart recovery, compensation. | Real interrupt/payment/provider recovery is not established; live paths are rejected by current containment. A real provider and isolated recovery environment are external prerequisites. | Crash at each effect/checkpoint boundary, recover on a second worker, prove one authorized logical effect/payment, preserve policy epoch, and refund/compensate correctly. Runtime/payment owner and separate effect observer. |
| F13 | `contracts/src/economic/ComposedSettlement.sol`; bind proof to allocation, provider, amount, result, domain, policy, nonce, and refund/dispute lifecycle. | `verifyProviderProof` is role-authorized approval without proof payload binding. Owner must select proof/evidence contract before implementation. | Wrong/stale/wrong-intent/provider/amount/domain proof rejects; valid delivery pays once; unauthorized verifier rejects; expiry preserves refund. Economics/proof owner and independent reviewer. |
| F14 | `neuron/intelligence/anomaly_detector.py` and related cognitive scoring; calibrate model/version thresholds, uncertainty/OOD, provenance, and hard-policy separation. | Fixed heuristic lacks held-out calibration and cannot support an authoritative conscience claim. Keep it telemetry-only. | Report held-out false-positive/negative distributions and confidence; test nonfinite/dimension/unseen/missing inputs; uncalibrated output cannot authorize. AI-safety and privacy review. |
| F15 | Provider registry/health and `neuron/composer/`; distinguish reachable, authenticated, qualified, attested, executing, and independently verified. | No real task execution commitment or independent admission evidence. Select one allowlisted provider and observer before a real vertical slice. | Bind task, model/runtime, budget, measured inputs/outputs, and result evidence; a website, benchmark declaration, or passport alone does not qualify. Provider owner and separate observer. |
| F16 | Exact source commit, CI/security workflow, `docs/audit/evidence/`, deployment/rehearsal records. | No final-commit signed assurance index, complete final-tree evidence, both chain rehearsals, privacy/backup/drill records, or deployed code/role/datum observations. | Closed-canary readiness gate passes against exact commit without placeholders or manual status inflation; independent reviews and signed hashes bind all applicable records. Audit lead, DevSecOps, chain operators, and privacy reviewer. |

F04’s planning status is not reopened: it is remediated only for the prior
registry transition finding. The owner-selected Option B is design-only; it
does not establish global DID uniqueness, anchor/compiled-entrypoint behavior,
or downstream identity-epoch integration. F08/F09/F17/F18 likewise retain only
their documented acceptance scopes.

## Open control-matrix tracks

The source of titles, status, owner roles, components, and named evidence below
is the bound `control-matrix.json`. “Missing” means not accepted as complete
current-profile evidence in the assurance index; it does not claim that no
historical artifact exists elsewhere. Track acceptance requires exact final
source/profile/command/tool evidence under the audit program and independent
review where required.

| Track/status | Requirement and source components | Required evidence still missing or incomplete | Owner / next acceptance dependency |
|---|---|---|---|
| T01 implemented (not verified) | Architecture and code traceability; `audit.md`, `docs/team`, `REPO_STATUS_REPORT.md`, and `docs/audit/architecture-traceability.json`. | `validate_traceability.py` passes against the current dirty tree, but the resulting report/output is not in the assurance evidence directory and is not bound to a clean final commit. The current evidence index and named review are absent. | Audit Lead; bind the current architecture report, exact source/validator hashes, command, output, and reviewer to the final commit. Acceptance requires every current architecture claim/component to trace to current implementation and maturity; historical claims remain labeled. |
| T02 implemented (not verified) | Asset, value, data-flow, and trust-boundary threat model; `contracts/src`, `cardano`, `neuron`, and `gateway`. | `docs/audit/THREAT_MODEL.md` exists but says last verified 2026-07-13. Current profile/source coverage and value-flow diagrams are not established by the assurance index; no commit-bound review evidence is present. | Audit Lead; refresh or explicitly revalidate the threat model against the current faucet-only profile and current source, include custody/allocation/evidence/recovery flows and disabled/mock boundaries, then bind the review and artifacts to the final commit. Acceptance requires threat coverage of the matrix's stated attack surfaces, not document presence alone. |
| T03 implemented (not verified) | Core invariant control mapping; `audit.md`, `contracts/src`, and `neuron`, with current anchors in `docs/audit/invariant-controls.json` and `INVARIANT_CONTROL_INDEX.md`. | The static traceability validator passed and confirms source anchors/test identifiers, but it did not run tests or prove invariant behavior. No exact-final-commit property-test evidence, signed manifest, assurance-index entry, or reviewer record is present. The index itself states that a passing anchor does not set a track to `verified`. | Audit Lead and applicable control reviewers; bind the invariant matrix/test index and current source to the final commit, then attach actual authorized property-test and reviewer evidence. Aiken-related evidence remains pending separate Aiken authorization. Acceptance requires explicit mapping for INV-1–INV-10 and evidence for the applicable profile, with disabled features kept scoped. |
| T04 partial | Evidence and release-claim integrity; audit docs, contracts inventory. | Exact-commit evidence manifest and claim-integrity scan. | Audit Lead; bind dirty/final-tree identity and reviewer. |
| T05 partial | CI and developer-tool security; workflows and scripts. | Workflow permission review and branch-protection export. | DevSecOps; final workflow parity and protected-branch evidence. |
| T06 partial | Secrets, credentials, and live configuration; gateway, neuron, security scripts. | Complete-history Gitleaks/TruffleHog closure, default-credential scan, credential incident disposition. | DevSecOps plus credential owners; no unresolved secret/history blocker. |
| T07 partial | Python security; neuron and gateway. | Exact-final-commit pytest, Bandit, Semgrep, and pip-audit evidence. | DevSecOps; retain exact selectors, pins, outputs, skips, and independent review. |
| T08 partial | Frontend security; frontend and scripts. | npm audit, build, and frontend test evidence. | DevSecOps/Frontend Lead; exact lockfile and commit binding. |
| T09 partial | Rust/native/Aiken toolchain, SBOM, provenance; Cardano, frontend, CI. | Native dependency inventory, signed SBOM, and build provenance. | DevSecOps; Aiken/native commands additionally require their own authorization. |
| T10 partial | Solidity manual security; `contracts/src`. | Current manual findings and Slither report. | EVM Security Lead; source-bound finding disposition. |
| T11 partial | Solidity properties, fuzzing, storage/upgrades; contracts and tests. | Foundry invariant results and storage-layout diff. | EVM Security Lead; adversarial invariants and upgrade review. |
| T12 partial | Cardano/Aiken validator security; `cardano`. | Authorized `aiken check` and validator property evidence. | Cardano Security Lead; no Aiken execution is currently authorized. |
| T13 partial | Bridge/proof security; bridge executor, ICB, contracts. | Proof-separation, replay, fallback, and real-verifier evidence. | Cross-chain Security Lead and trust-model owner. |
| T14 partial | Oracle, ordering, MEV; oracle contracts, chain oracle, MEV protection. | Staleness tests and MEV adversarial report. | EVM Security Lead; exact time/fallback and ordering model review. |
| T15 partial | Cryptography, keys, signatures, replay, sessions; gateway, SDK, contracts. | Signature-domain review and nonce/replay tests. F05 R4.1 owner classifications are recorded as C for six applied-parameter cases and B for four proof-domain cases. The reviewed R12 overlay records 53/55 negative cases PASS, 2 pending, 49/51 transaction-simulator cases PASS, and 21/21 mutations PASS. | Cryptography Reviewer; `applied_keys_bad_count` and `applied_keys_bad_length` remain pending under the R4.1 first-failure attribution requirement. Separate live ICB/Mithril trust-model/provider choice remains open. |
| T16 blocked | Deployment scripts, roles, multisig, timelock; scripts/contracts inventory. | Rehearsal and role-transfer manifest. | Deployment Lead and owner-controlled chain/role authority; separate rehearsal authorization. |
| T17 partial | Supply, emissions, reward solvency; token, staking, economic contracts. | Supply invariant tests and solvency simulation. | Economics Lead; TR-01–TR-10 and INV-9 decisions/evidence. Rewards stay disabled. |
| T18 partial | Settlement, fees, escrow, insurance, yield; economic contracts and payments. | Settlement state-machine tests and bank-run scenarios. | Economics Lead; owner-selected fee/settlement policy and funded-liability proof. |
| T19 partial | Sybil, collusion, wash trading, thin liquidity; economic, neuron economics, composer. | Adversarial market simulation and linked-address analysis. | Mechanism Design Lead; real provider/identity assumptions reviewed. |
| T20 partial | Centralization/oligarchy/plutocracy; governance, economics, composer. | HHI, top-share, and Nakamoto-coefficient report. | Mechanism Design Lead and Governance Lead; thresholds and electorate reviewed. |
| T21 blocked | Governance capture, treasury, emergency authority; governance, governor, deploy scripts. | Capture simulations and role/timelock matrix. | Governance Lead and owner-controlled custodians; exact authority/ceremony decision. |
| T22 partial | Regional equality/fairness; `RegionAwareDEC.sol`, composer. | Regional cap tests and fairness metrics. | Fairness Lead; enforce 30% ceiling and five-provider floor. |
| T23 partial | SDK capability security; `neuron/sdk`. | Capability matrix and SDK misuse tests. | SDK Lead; fail-closed authority and least-privilege review. |
| T24 partial | AI/CHC adversarial scoring; intelligence and composer. | CHC spoofing corpus and reward-hacking report. | AI Safety Lead; eligibility checks before scoring and no uncalibrated authority. |
| T25 partial | Agent misbehavior, prompt injection, tool abuse; neuron and gateway. | Red-team corpus and unauthorized-side-effect evidence. | AI Safety Lead; effect observer and pre-effect policy tests. |
| T26 partial | Memory sovereignty/provenance/erasure; semantic MMU, SIRA, intelligence. | Provenance tests, hard-reset tests, redaction evidence. | AI Safety Lead and Privacy Lead; retention/erasure review. |
| T27 partial | Service Block/SkillOps security; registry and neuron services. | Manifest-signature tests, sandbox/quarantine evidence. | SDK Lead; exact artifact identity and quarantine boundary. |
| T28 partial | Sentinel/slashing evidence; sentinel, contracts sentinel/slashing. | Challenge-forgery tests and telemetry integrity report. | Sentinel Lead; independent evidence authenticity and role review. |
| T29 partial | Durable execution/recovery; workflows, interrupt handler, world model. | Crash-recovery and exactly-once side-effect evidence. | Runtime Lead; real second-worker recovery and side-effect observer. |
| T30 blocked | DA receipts/live adapters; DA modules and adapters/SDKs. | The assurance schema requires one Celestia Mocha and one Near Testnet receipt, with distinct submitter and retrieval-observer identities, `mock_mode=false`, provider-native inclusion references, and retrieved bytes matching the submitted payload hash. Source-only revalidation `T30_DA_SOURCE_REVALIDATION_20261019.md` (SHA-256 `e57fbe79c88b21a5af065602c7271fea394b01210b47647e8a3f9c7c7815c98d`) binds current adapter, router, SDK, test, schema, profile, and requirements hashes: Celestia remains release-evidence-ineligible without independent observation; Near live submission/retrieval is unavailable; Avail/EigenDA remain simulated and excluded. `docs/audit/evidence/` has no T30 runtime-integration receipts. | DA Lead and separate operator/observer; select the Near testnet client/contract and signer/observer trust boundary (or submit an in-profile provider change for review), then separately authorize implementation/regression work and any live submission/retrieval. |
| T31 partial | Gateway/API/DID/mTLS/abuse; `gateway/server.py` and ingress. | DAST, external mTLS/replay and rate-limit evidence. | Gateway Lead; live external vantage and approved TLS ingress. |
| T32 partial | Frontend/wallet/CSP/transaction intent; `frontend-vite`. | CSP report, wallet-flow, and Playwright evidence. | Frontend Lead; real wallet/intent boundary and supported browser evidence. |
| T33 blocked | Privacy/PII/telemetry/retention/public content; DA models, Sentinel, publisher inventory, gateway, and scanners. | `privacy-publisher-inventory.json` is a seven-route publisher inventory, not a field-level data-flow/recipient/access/retention inventory. Source-only reviews `T33_PRIVACY_SOURCE_REVALIDATION_20261018.md` (SHA-256 `5422dd9597326cfac11393b78d46f98e5a35fbc401108a4b3cbe33a435dcc505`) and `T33_PRIVACY_FLOW_SOURCE_FOLLOWUP_20261018.md` (SHA-256 `5b67aea9268080c768c157ed26913fb960a82d80dbd150a922ca4c1b02739156`) record raw report paths, identifier-prefix logs, the authenticated `/da/anchors` consumer, unbounded in-memory history, and `limit=0` returning the full list. The route's source-level M2 policy is not a live access observation. Additive source follow-up `T33_LOCAL_STORAGE_SOURCE_FOLLOWUP_20261019.md` (SHA-256 `72a58fc8a1b34724700d42d9ee7961edb8a9f9da53cc26766fce29550c60c0ed`) binds SQLite persistence of raw node IDs, signed heartbeat payloads/signatures, and legacy-gateway raw identifier/error-text logs. These are source observations, not effective deployment, database-access, or retention evidence. No exact-current-source redaction run or schema-compliant privacy review is in `docs/audit/evidence/`; the retained path scanner is not a content/PII review. | Privacy Lead and named human/org approver must approve data categories/fields, identifier linkability, KPI disclosures, recipients, provider/local retention/access, and the complete producer/consumer inventory. Separately authorize any gateway behavior change and regression slice after a bounded change proposal. Then bind redaction results and public-content review to the exact source tree. | Privacy review schema passes for exact commit and artifact hashes, named reviewer/org, approved inventory and retention, redaction tests, public-content review, complete publishers, and zero blockers. T33 remains blocked until this evidence is independently reviewed. |
| T34 partial | User safety/consent/recovery/accessibility/phishing; frontend, gateway, SDK. | Abuse-oriented user journeys and accessibility report. | Product Security Lead; usability/accessibility reviewer. |
| T35 partial | TLS/network/container/resource/DoS; gateway/deploy/CI. | TLS scan, load test, container scan, and effective R28 boundary evidence. | SRE Lead; exact host enforcement and separately authorized boundary validation. |
| T36 partial | Monitoring/incident/backup/recovery; gateway, sentinel, emergency script. | Incident drill, backup-restore, pause, rollback evidence. | SRE Lead and chain operators; real recovery/restore observation. |

## Invariant and release acceptance

The invariant index is an anchor, not proof of live acceptance. Its remaining
requirements are:

| Invariant | Current anchor/profile state | Required remaining evidence |
|---|---|---|
| INV-1 regional emissions | Immutable 30% ceiling. | Adversarial cap tests and live allocation monitoring for admitted routes. |
| INV-2 insurance yield | 30% ceiling; real yield disabled. | Real vault review and redemption evidence before enabling yield; local accounting is not vault redemption. |
| INV-3 session lifetime | 1–24 hour bound. | Live bundler integration evidence. |
| INV-4 session target | Non-empty configured core-contract subset. | Signed deployed address allowlist. |
| INV-5 institutional identity | OMS route is fail-closed. | Live OMS outage and recovery evidence. |
| INV-6 TEE identity | Root EOA required by encoding path. | Real quote verifier and authenticated quote evidence. |
| INV-7 stale oracle | Fixed fallback after expiry. | Keeper/monitoring drill. |
| INV-8 supply | Absolute `$1 \times 10^9` ceiling. | Exact final deployment and explorer supply record. |
| INV-9 rewards | Faucet profile: zero reward rate and no staking minter. | Independently approved funded-liability/solvency design before any activation. |
| INV-10 bridge | Proof/payload separation and nonce ordering anchors. | Real bridge/Mithril verification, finality and replay evidence. |

## Owner and external dependencies

- Tokenomics memo `TOKENOMICS_OWNER_DECISIONS_R1_20261008.md`: TR-01–TR-10
  have no accepted owner dispositions. The owner must choose enabled semantics
  or reviewed enforced-disabled/deferred dispositions; no implementation may
  infer these choices.
- F05 R4.1 owner classifications are recorded: choice C for six
  applied-parameter cases and choice B for four proof-domain cases in
  `m3_f05_2a/tx_sim_evidence_contract_r4_1.json` (SHA-256
  `238b3da9296a6c60699dbc7201759c7e499c63defd932491023b80ec7916a171`). These
  choices did not themselves award evidence credit. The reviewed R12 overlay
  is the current case ledger: `CASE-STATUS.json` SHA-256
  `7f23a3ea4c8f61da2f181bcd1f54cbad68f609a25f2af86ba44427ba065884fc`, review
  `INDEPENDENT-REVIEW.md` SHA-256
  `287402715eb81089736663802d283150c99febfafc0f93d9f6aa59104f61b547`;
  53/55 negative cases PASS, 2 remain pending (`applied_keys_bad_count` and
  `applied_keys_bad_length`), 49/51 transaction-simulator cases PASS, and
  21/21 mutations PASS. Those two negatives remain pending under the exact
  first-failure attribution gate. The review's listed R12 `AMENDMENT.md` hash
  differs from the current file hash; the R12 package's own
  `SHA256SUMS` verifies all four files, and its target `CASE-STATUS.json` hash
  matches. Preserve this review-record discrepancy. Separately, the real
  ICB/Mithril trust-model/provider decision remains open.
- F04 Option B is selected for design only: per-bootstrap IDs are allowed, but
  no global DID uniqueness is promised and compiled anchor/consumer evidence is
  still missing.
- Packet 05 owner choices remain pending: accept or reject the whole
  `runs/**` write scope; accept or reject transient `setpriv` launcher
  credentials; accept the stated shared-file-backed-memory/reclaim caveats or
  require a different reviewed resource boundary. Rejection means revise and
  review the packet; it does not authorize weakening a limit.
- The historical M2.4b ingress anomaly remains inconclusive; its original
  cause is not attributed to collector loss or SQLite timeout.
- M5 durable integration also requires an owner-approved disposable isolated
  PostgreSQL environment without production/user data, plus a separate worker
  and side-effect observer for crash/restart recovery. That environment is not
  available or authorized in this worktree.
- R28 fixture execution 02 is accepted only for fixture validation. The
  ordinary-host runtime digest and ELF closure, effective enforcement,
  collector review, boundary validation, and Slot 08 approvals remain separate
  gates.

## Release dependencies and authority

1. Complete R28 ordinary-host helper/resolver/loader readbacks, finish the
   bounded full runtime-audit procedure, obtain independent review, then obtain
   separate owner authorization for one read-only audit. Do not install a
   resolver or execute inspected runtime ELF objects.
2. Resolve owner-controlled trust, tokenomics, and Packet 05 decisions before
   any design-dependent implementation or provisioning request.
3. After R28 prerequisites pass, request separate authority for staging only
   the 13 manifest-listed candidate files, installing/loading only the exact
   bound profile/unit, and leaving the service disabled and stopped.
4. Boundary validation, output collection, and Slot 08 each require their own
   reviewed exact-byte plan and owner authorization. Repeat enforcement
   readbacks immediately before validation/start. No current evidence approves
   these actions.
5. G0–G4 require current exact-commit evidence and rehearsed Amoy/Pre-Prod
   manifests. Public promotion additionally requires all applicable tracks,
   independent assurance, the seven-day closed canary and required drills;
   the profile's 14-day public-soak gate applies before increased exposure.

No step above grants execution authority. Slot accounting remains 2 granted,
1 consumed, 1 remaining; Slot 08 is NOT RUN. Slot 07 remains unsuccessful,
cleanup-incomplete, and `OWNERSHIP_UNCERTAIN`. No Aiken command is authorized.
Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
Overall readiness remains **NOT READY**.

## Current crosswalk coverage check — 2026-10-18

A read-only comparison against current canonical JSON found 36/36 matrix tracks are nonverified and each has exactly one map row; there are no missing or extra track rows. All 13 findings with status `REVALIDATED_OPEN` have map rows with no omissions. F04, F08, F09, F17, and F18 remain called out as remediated only within their recorded scopes. This check validates map coverage, not gate completion. It binds `docs/audit/control-matrix.json` SHA-256 `28b9146bb2ace970c19441ab4cd8ee4f91937d56acf4f178b3639f5b4f493cf4` and `docs/remediation/FINDINGS.json` SHA-256 `b62253b4b0c7d88355e04eeff3f51c06d6e15c462f083a7224e99f3a6b44dc35`.

## Additive T33 schema-to-evidence crosswalk — 2026-10-19

The T33 row above is supplemented by `docs/remediation/T33_PRIVACY_SCHEMA_EVIDENCE_CROSSWALK_20261019.md`, SHA-256 `7ea96d341e4204cd7d07ad7dbb9daf92239a423f1a8a723be6231422a05aa352`. The crosswalk revalidates its bound publisher/review schemas, inventory, source notes, and producer/consumer source hashes. It maps each schema-required evidence category to current source evidence and missing acceptance evidence. `docs/audit/evidence/` contains only `vdso-review-evidence.json`; no T33 privacy-review record or complete schema-required privacy evidence bundle is present.

This is source-only planning evidence. It does not approve data categories, linkability, recipients, access, retention, publication, or redaction; it does not satisfy the schema or promote T33. T33 remains BLOCKED pending Privacy Lead decisions, exact-tree inventory/redaction/public-content evidence, and named independent privacy approval.
