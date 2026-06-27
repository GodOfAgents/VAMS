---
name: vams-invariant-auditor
description: Audit VAMS changes, diffs, PRs, deployment plans, and architecture proposals against the ten core protocol invariants INV-1 through INV-10. Use when reviewing contracts, Cardano validators, Neuron runtime, gateway auth, session keys, cross-chain bridges, rewards, emissions, insurance yield, oracle freshness, or any change that can affect VAMS economic or cryptographic safety.
---

# VAMS Invariant Auditor

Use this skill to produce an invariant-first review. Findings come before summary.

## Workflow

1. Identify changed files or proposed components.
2. Read `AGENTS.md`, `audit.md`, `docs/CHANGELOG.md`, and relevant source files.
3. Map each touched path to INV-1 through INV-10 using `references/invariants.md`.
4. Classify each invariant as `preserved`, `affected`, `violated`, or `not touched`.
5. For affected or violated invariants, cite exact files and lines where possible.
6. Require targeted tests before accepting safety claims.
7. Block deployment if any invariant is violated or unverified in a live path.

## Output Shape

- **Blockers:** invariant violations or missing proof for touched safety paths.
- **Findings:** ordered by severity with file/line citations.
- **Invariant Matrix:** one row per INV-1 through INV-10.
- **Required Verification:** exact commands or tests needed.
- **Residual Risk:** what remains uncertain after review.

## Reference

Read `references/invariants.md` for the canonical invariant map and verification focus.
