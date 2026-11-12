# Operator runbooks

**Last verified:** 2026-11-13

Procedures for the restricted dual-chain testnet. A runbook is not evidence
and grants no authority: live network access, signing, funding, role changes
and broadcast each need the owner's specific authorization. Readiness is NOT
READY (13 findings open, 0 of 36 tracks verified).

| Runbook | Scope |
|---|---|
| [POLYGON_AMOY_REHEARSAL.md](POLYGON_AMOY_REHEARSAL.md) | `DeployRestrictedTestnet` on Amoy (chain 80002) |
| [CARDANO_PREPROD_REHEARSAL.md](CARDANO_PREPROD_REHEARSAL.md) | Governance v2, insurance fund and agent registry on Pre-Prod (magic 1) |
| [TEAM_SIGNER_GOVERNANCE.md](TEAM_SIGNER_GOVERNANCE.md) | Team-controlled bootstrap seats and authorities on both chains (owner decision 12) |

## Ported from PR #4 and held back

PR #4 (`GodOfAgents/phase-6-vdso-shadow-hardening`, July 2026) also carried
the items below. They stay on that branch until their blocker clears
(review: `docs/remediation/repair_20261112/UNMERGED-PR-REVIEW.md`).

| Item | Blocker |
|---|---|
| `architect-reviews.schema.json` | Records architect self-review (`independent: false`), which does not meet the independent-review domains in `scripts/audit/audit_program.py`. Owner decision 12 chose the team signer model, not self-review in place of independent review |
| `VDSO_SHADOW_WORKER.md`, `vdso-shadow-report.schema.json` | Port with the VDSO shadow lane as its own slice |
| `cardano-preprod-parameters.schema.json` | Names the superseded `governor`/`timelock` validators; rewrite for the eight-artifact set when the real-parameter step is built |
