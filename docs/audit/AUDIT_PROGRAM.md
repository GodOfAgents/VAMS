# VAMS Testnet Audit Program

**Architecture baseline:** v0.8.0 cognitive/composer over v0.6.0 OMS  
**Deployment stage:** Hardened pre-testnet candidate  
**Assurance model:** Closed canary before Architect-reviewed bootstrap public
testnet; independent review remains mandatory for the later public stage

This program treats every VAMS subsystem as economically sensitive. A defect in
identity, routing, telemetry, memory, developer tooling, or data availability can
change who receives work, who receives rewards, whether settlement is valid, or
whether governance can recover the system.

The machine-readable source of truth is `control-matrix.json`. CI validates the
matrix and emits evidence for the exact commit under review. The regular
`Security Evidence Gate` proves the audit pipeline ran; the manually invoked
canary gate requires every G0-G4 track verified. `bootstrap-public` requires all
36 tracks, six explicitly non-independent Architect dossiers, and closed-canary
evidence. The later `public` stage requires all 36 tracks plus independent and
closed-canary evidence.
A document, prior test count, or historical audit verdict is never evidence for
a later commit.

## Finding Policy

Findings move through `open`, `triaged`, `remediated`, `verified`, and `closed`.
`accepted_risk` is permitted only for Low findings or non-custody Medium findings
with two approvers, compensating monitoring, an owner, and an expiry of at most
30 days.

The following cannot be waived:

- A violation or unverified live path for INV-1 through INV-10.
- A Critical or High finding.
- A Medium finding affecting custody, authorization, identity, privacy,
  governance, bridge integrity, or supply/reward solvency.
- Mock or stub evidence accepted by staging, testnet, or production.
- Privileged deployer EOAs remaining after the role-transfer ceremony.

## Audit Phases

| Phase | Tracks | Required outcome |
| --- | --- | --- |
| 0. Audit control | T01-T04 | Architecture, value flows, invariants, claims, and evidence are traceable to the current commit. |
| 1. Developer and supply chain | T05-T09 | CI, secrets, Python, JavaScript, native tools, dependencies, SBOM, and provenance are reviewed. |
| 2. Blockchain and cryptography | T10-T16 | Solidity, Aiken, bridges, oracles, keys, replay boundaries, roles, and deployment scripts pass. |
| 3. Economics and governance | T17-T22 | Solvency, settlement, manipulation, concentration, capture, and equality simulations pass. |
| 4. AI and agent runtime | T23-T29 | SDK, cognition, tools, memory, Service Blocks, Sentinel, and durable execution fail closed. |
| 5. Interfaces and operations | T30-T36 | DA, gateway, frontend, privacy, users, infrastructure, monitoring, and recovery pass. |
| 6. Remediation | T01-T36 | Each finding has a fix, regression test, independent verifier, and current evidence. |
| 7. Deployment rehearsal | Consolidated | Bytecode, configuration, role transfers, addresses, transactions, and rollback are reproducible. |
| 8. Canary and public rollout | Consolidated | Seven-day closed and fourteen-day public soak periods complete without a stop condition. |

## Testnet Gates

### G0 - Evidence integrity

- `control-matrix.json` and all audit schemas validate.
- Evidence identifies the commit, dirty-tree state, command, tool version,
  environment, timestamp, result, artifact hash, and reviewer.
- `audit.md`, `REPO_STATUS_REPORT.md`, and deployment records contain no stale
  current-state test totals or unsupported readiness claims.

### G1 - Build and security verification

- Forge build/tests, Slither, Aiken, pytest, Bandit, pip-audit, Semgrep,
  npm audit/build, Caddy validation, secret scans, SBOM, and signing pass on one
  commit.
- Existing tests and new invariant/property tests have zero failures.

### G2 - Economic and invariant verification

- INV-1 through INV-10 have executable positive, boundary, and adversarial tests.
- Economic simulation includes at least 100,000 adversarial epochs.
- Testnet stop conditions are linked-operator share above 20%, top-four provider
  share above 50%, HHI at or above 0.25, or any regional allocation above 30%.
- A region with fewer than five independent providers cannot use an unbounded
  market-derived floor.

### G3 - Live integration verification

- Testnet uses real, verifiable receipts for enabled DA routes.
- Avail, EigenDA, OMS, Trails, Coinme, TEE, bridge, escrow, storage, and interrupt
  stubs are disabled or excluded from the live route graph.
- Gateway DID authentication, replay rejection, mTLS, TLS, CORS, rate limits,
  input limits, and loopback binding are verified from outside the process.

### G4 - Governance and deployment ceremony

- Admin, upgrader, treasury, and economic parameter roles use a 3-of-5 Safe or
  equivalent multisig behind a minimum 48-hour timelock.
- Emergency pause authority is a separate 2-of-3 pause-only council.
- The deployer holds no privileged role after handoff.
- `contracts/CONTRACTS.md` records chain identifiers, addresses, transaction
  hashes, verified bytecode, role owners, timelocks, and rollback instructions.

### G5 - Independent assurance

- Independent reviews cover Solidity/governance, Aiken/bridge,
  economics/centralization, gateway/Agent SDK, privacy, and AI-agent safety.
- All public-testnet-blocking findings are verified closed.

For the faucet-only `bootstrap-public` profile, six Architect dossiers may
temporarily satisfy G5 only with `review_mode=architect-bootstrap`, the exact
non-independence disclosure, and zero blockers. This exception does not apply
to the later `public` stage, incentives, real assets, wallet writes,
authoritative VDSO, bridge value transfer, or mainnet.

### G6 - Controlled rollout

- Closed canary uses faucet-only assets and no real fiat or yield capital.
- A bridge or settlement operation is capped at 1% of seeded testnet insurance
  reserves; aggregate daily exposure is capped at 10%.
- Pause, key-loss, DA-outage, identity-outage, bridge-replay, and restore drills
  pass before public onboarding.

## Ownership

| Owner role | Tracks |
| --- | --- |
| Architect Audit Lead | T01-T04 and bootstrap finding acceptance |
| DevSecOps | T05-T09, T35-T36 |
| EVM/Cardano Security Leads | T10-T16 |
| Economics and Governance Leads | T17-T22 |
| AI Safety and SDK Leads | T23-T29 |
| DA, Gateway, Frontend, Privacy, and SRE Leads | T30-T36 |
| Architect | Six bootstrap review domains; must disclose non-independence |
| Independent Reviewers | Later independent verification of T10-T34 |

No calendar target overrides G0 through G6. A closed canary may proceed after
G0-G4. Faucet-only bootstrap public access requires the Architect-bootstrap G5
profile and the closed-canary portion of G6. Incentivized or later public
access continues to require independent G5 evidence.

## Promotion Commands

- `python scripts/audit/audit_program.py readiness --stage canary` requires a
  clean commit, signed aggregate evidence, hashed assurance records for every
  G0-G4 track, team-signer governance evidence, and rehearsed Amoy/Cardano
  deployment manifests.
- `python scripts/audit/audit_program.py readiness --stage bootstrap-public`
  requires all 36 tracks verified at `architect-bootstrap`, all six
  content-bound Architect dossiers, deployed manifests, signed seven-day
  canary and VDSO shadow reports, and no pending deployment fields.
- `python scripts/audit/audit_program.py readiness --stage public` additionally
  requires every track verified, independent assurance for T10-T34, deployed
  network manifests, a seven-day stop-condition-free canary, all required
  incident drills, and a deployment register without pending fields.
- Detached canary, shadow, and aggregate evidence signatures are
  cryptographically verified with Cosign in
  the manual GitHub promotion job before either command can return success.
