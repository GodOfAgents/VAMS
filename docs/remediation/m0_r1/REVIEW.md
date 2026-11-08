# M0-R1 local closure review

Date: 2026-09-22  
Branch: `testnet/remediation-20260907`  
Superproject HEAD: `829ab544571f12efe50ecb5740f129c8acb3e16f`  
Decision: **M0 COMPLETE LOCALLY; INDEPENDENT M0-R2 REVIEW PASSED**

## Superseded evidence-test retirement boundary

The first independent M0-R2 pass found that unfiltered root pytest still
collected seven historical M0.3/R7/R9 evidence-package test modules. Their
source-snapshot assertions are intentionally stale after the approved fixture
hygiene and final-tree documentation changes, producing 11 failures and 9
setup errors despite the replacement M0.4 property passing.

Root `conftest.py` now retires exactly those seven modules from default
product/CI collection. The boundary contains no glob or directory exclusion,
and a focused regression requires the exact list, requires every retired file
to remain present, and requires the M0.4 gate test to remain active. Historical
packages are preserved for audit traceability; none is repaired, promoted, or
trusted by CI. This is the permanent stop boundary for the auxiliary R9 stack.

The corrected collection audit found 760 active tests, zero nodes from every
retired module, ten active M0.4 nodes, and three active boundary-regression
nodes. The corrected full root run passed **760/760 plus 37 subtests** in
129.33 seconds:

- record:
  `20260921T210511Z-12eecd1c-m0-r2-python-root-baseline-corrected/record.json`
- record SHA-256:
  `f985816aca373ed144eb2af6f8dd5384a23c91eaedea819b064f95258a0f59fa`
- log SHA-256:
  `855310c1de2a4c998628da0145771840d216bf3b03728a5d666719eae2a76325`

The independent corrected-state review accepted the exact retirement boundary,
the current source classifications, F17/F18 dispositions, and M0.4 design.
Final acceptance is bound to a last-operation M0.4 summary at
`/home/GodOfAgents/vams-evidence/m0-20260909/m0-r2-final/current-tree-summary.json`.
That summary must report `status=pass`, zero first-party/unknown findings and
the exact 161/160/158 vendor counts; no repository edit may follow it.

## Exit-criterion decision

| M0 exit condition | Evidence | Decision |
|---|---|---|
| Current commit/toolchain inventory | Recursive submodule pins recorded; exact superproject HEAD recorded; installed and missing tools distinguished in `ENVIRONMENT.md` and this review. | Pass for discovery. Missing native tools remain NOT_RUN, not green. |
| Native baseline | Corrected current root Python baseline: 760/760 plus 37 subtests; focused F06-F15: 174/174; F17 gateway/keeper and F18 dependency evidence pass. Forge/Aiken/Rust/frontend cannot run without prohibited installation. | Pass for available local Python; unavailable native toolchains remain assigned to M7. |
| Source-linked F01-F16 revalidation | `M0_SOURCE_REVALIDATION.md`, exact file hashes, and ledger rationales bind each finding to current source. | Pass: 16/16 `REVALIDATED_OPEN`. |
| Actual current controls | Active workflow jobs and command validators were inspected; M0.4 is integrated without weakening existing controls. | Pass for inventory; no hosted-CI or release-readiness claim. |
| F17/F18 dispositions | Dedicated reviews and durable records. | Pass: both `REMEDIATED`. |
| Current-tree secret baseline | Pinned Gitleaks 8.30.1 exact-set gate. | Pass only at 0 first-party + 479 reviewed vendor identities. |
| Invariants and mock mode | No invariant implementation or mock-mode behavior changed. | INV-1-INV-10 and mock mode untouched. |

## Finding inventory

The machine-readable ledger contains exactly:

- 16 `REVALIDATED_OPEN`: F01-F16;
- 2 `REMEDIATED`: F17-F18;
- 0 `NOT_REVALIDATED`.

Open classifications are deliberate outcomes of M0. They are not waivers:
their existing M1-M9 acceptance criteria remain binding.

## Current control inventory

The workflow retains the following independent jobs: change detection,
audit-program integrity, documentation verification, public-content policy,
default-credential scan, mock-mode promotion scan, secret scanning
(complete-history Gitleaks plus the aggregate current-tree baseline),
TruffleHog, Forge, Slither, Aiken, VIR-Core, Python security/tests, Semgrep,
frontend verification, Caddy configuration, SBOM/signing, aggregate security
evidence, and stage-specific readiness.

No vendor/path/regex/rule/global allowlist was added to `.gitleaks.toml`.
Complete-history Gitleaks, TruffleHog, default-credential checks, the existing
narrow allowlist regression, dependency audits, and all other jobs remain
enabled.

## Evidence boundary

M0 closure means the discovery baseline is trustworthy enough to start ordered
remediation. It does not make VAMS testnet-ready and does not close:

- T06 credential/history cleanup;
- F01-F16 or M1-M9;
- M7 reproducibility and final-commit full-gate execution;
- mock-mode promotion gates;
- governance-role or deployment ceremony evidence;
- any canary/public promotion decision.

The custom M0.3c R9 validator remains auxiliary, frozen, retired from default
pytest collection, and outside CI/promotion trust. Independent M0-R2 review
passed. The next implementation milestone is M1.
