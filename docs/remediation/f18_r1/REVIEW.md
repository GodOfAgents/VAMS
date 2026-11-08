# F18-R1 final dependency-audit disposition

Date: 2026-09-22  
Superproject HEAD: `829ab544571f12efe50ecb5740f129c8acb3e16f`  
Disposition: **REMEDIATED**

## Acceptance review

F18 required fixed CI pins for bootstrap pip and the alternate `httpx2` /
`httpcore2` stack, both requirement-file audits, and an explicit unsuppressed
installed-environment audit in a clean CI-equivalent environment.

The active `python-gate` now installs `pip==26.2` and `httpx2==2.12.0`;
the reviewed package metadata resolved `httpcore2==2.12.0`. It retains:

```text
pip-audit -r gateway/requirements.txt
pip-audit -r neuron/requirements.txt
pip-audit --local --vulnerability-service pypi
```

No `--ignore-vuln`, `--fix`, `--exit-zero`, `|| true`, or equivalent
suppression is present. The workflow validator fails on lower/retired pins,
vulnerable direct `httpcore2`, missing requirement or installed audits,
ambiguous installed coverage, and suppression flags.

## Evidence reviewed

- Clean CI-equivalent sequential install retained pip 26.2, httpx2 2.12.0,
  and httpcore2 2.12.0 with a passing `pip check` and stable inventory.
- Gateway compatibility: 39/39 tests plus 6 subtests passed; record SHA-256
  `13f49d3056a518e1bfcc7b0588ec1e67d8079cc527712ae059078d474864ad45`.
- Full Python compatibility: 732/732 tests plus 19 subtests passed; record
  SHA-256
  `da21f770f91ebb9830f5c8f6b8b2a449bb899aa3357c952d379ad0544a09af5f`.
- Gateway requirements audit: exit 0 and exact success log; record SHA-256
  `a4917ebcff85533f578a9d0e29300bb162215043a4d30c8c136c2efd2c6012cc`.
- Neuron requirements audit: exit 0 and exact success log; record SHA-256
  `b22eecefcdbdb65ce68bac4f15febcd451592eb9b650c8033082cd45c3d01ccb`.
- Installed-environment audit: exit 0 and exact success log; record SHA-256
  `58463dffffe0abae648b2b073985f48f1f7d1797e343c1e8876ded9b818bcf2e`.
- Current workflow-security regression: 11/11 passed; repository-native
  workflow validation passed with all 40 action references pinned.

The earlier combined wrapper record with an empty outer log is not relied upon
as audit-result evidence. The three later direct records provide the required
command, exit, duration, source-before/source-after, and exact nonempty audit
result independently.

## Scope

The missing hashed CI requirements lockfile is a reproducibility gap assigned
to M7, not an F18 acceptance condition. The evidence is local CI-equivalent,
not an observed GitHub Actions run; F18 does not require a hosted run. These
limitations remain recorded without holding F18 open.

INV-1 through INV-10 and mock-mode behavior are untouched. This disposition
does not close M0, M7, T06, or any promotion gate.
