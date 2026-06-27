---
name: vams-docs-reality-sync
description: Reconcile VAMS documentation, changelogs, architecture docs, status reports, README claims, API references, and deployment guides with actual source code and tests. Use when docs may be stale, test counts conflict, mock/stub maturity is unclear, gateway/frontend status changed, or a claim needs source-backed correction.
---

# VAMS Docs Reality Sync

Use this skill to eliminate drift between documentation and implementation.

## Workflow

1. Identify the doc claim to verify.
2. Locate source files, tests, configs, and workflow files that prove or disprove it.
3. Classify each claim:
   - `verified`
   - `stale`
   - `overstated`
   - `aspirational`
   - `missing from docs`
4. Patch docs with precise wording and file references.
5. Update `docs/CHANGELOG.md` if behavior, security posture, API, or deployment state changed.
6. Do not change code merely to make docs true unless the user asked for implementation.

## Output Shape

- **Corrected Claims:** what changed and why.
- **Source Evidence:** files and lines inspected.
- **Remaining Drift:** claims that still need verification.
- **Changelog Impact:** whether `docs/CHANGELOG.md` changed.

Read `references/reality-checks.md` for common VAMS drift areas.
