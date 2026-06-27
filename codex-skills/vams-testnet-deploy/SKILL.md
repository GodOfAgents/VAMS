---
name: vams-testnet-deploy
description: Plan, review, and execute VAMS Phase 6 testnet deployment preparation for Polygon Amoy and Cardano Pre-Prod. Use when working on deploy scripts, role setup, Gnosis Safe ownership, timelocks, contract address recording, Aiken validator deployment, gateway live-mode configuration, rollback plans, Tenderly simulation, or deployment evidence.
---

# VAMS Testnet Deploy

Use this skill for deployment ceremony planning and readiness checks. Do not
deploy if any block condition remains unresolved.

## Workflow

1. Read `references/deploy-ceremony.md`.
2. Verify branch state and dirty worktree before deployment work.
3. Run required build, test, scan, and mock-mode checks.
4. Confirm target networks: Polygon Amoy and Cardano Pre-Prod.
5. Confirm deployer keys are fresh and not committed.
6. Confirm role owners use Gnosis Safe or equivalent multisig plus timelocks.
7. Deploy in dependency order only after gates pass.
8. Record chain ID, address, tx hash, role owner, verification status, and rollback plan.
9. Update `contracts/CONTRACTS.md`, `docs/CHANGELOG.md`, and deployment docs.

## Output Shape

- **Readiness:** go/no-go with blockers.
- **Preflight Evidence:** commands and results.
- **Deployment Plan:** ordered steps and dependencies.
- **Role Matrix:** owner, admin, pauser, upgrader, timelock, multisig.
- **Post-Deploy Evidence:** addresses, txs, verification, monitors.
- **Rollback/Recovery:** exact emergency path.
