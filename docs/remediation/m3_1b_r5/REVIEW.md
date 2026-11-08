# M3.1b-R5 scoped remediation review

Date: 2026-09-25
Scope: remediation of independent M3.1b-R4 findings only
Baseline: /home/GodOfAgents/vams-evidence/m3-1b-r4-review-20260925-829ab544571f
R4 SHA256SUMS: 854dc461194a388b76379b1d1be2679d8cc1c82bccd0b7551eccec88dc9848fe

## Disposition

R4 was verified before editing (sha256sum -c SHA256SUMS passed). The scoped
changes address H1, H2, M1, M2 and related public-boundary gaps. This is not
independent acceptance; the next slice is M3.1b-R6 review.

- H1: one finite interval contract is enforced at every enabled transition.
- H2: the compiled public harness includes independently attributable Deposit,
  schema, metadata/identity, key/evidence, asset, policy, claimant-auth,
  payout-removal, duplicate-approver and interval cases.
- M1: rebuilt maximum contexts use 16 inputs and 16 outputs, 16 fund assets,
  five guardians, two pending claims, six signers where applicable, and an
  accepted 896-byte datum boundary.
- M2: INV-10 uses structured source validation; bridge proof and payload hash
  remain separate, Deposit remains unconditionally rejected, and no structural
  bridge helper is accepted as custody authority.
- L1: repository-wide Aiken formatting remains a separate pre-existing issue;
  changed insurance source is checked independently.

## Source changes

- cardano/validators/insurance_fund.ak: shared finite intervals, explicit
  six-signer/duplicate boundary, and native signer regressions.
- scripts/remediation/test_m3_1b_public_validator.py: strict blueprint
  provenance/schema/parameter/compiled-byte checks, 83 compiled cases, exact
  maximum contexts and sanitized metrics.
- scripts/remediation/test_m3_1b_r5_mutations.py: temporary-copy compiled
  mutation sweep for every R5 control.
- scripts/audit/validate_traceability.py,
  scripts/audit/test_traceability.py, docs/audit/invariant-controls.json:
  structured INV-10 contract and mutation tests.
- This record and ADR_AMENDMENT.md.

## Fresh evidence

Verified toolchain: Aiken 1.1.21 at
/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken;
binary SHA-256 remains
07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79.
Regenerated insurance compiled bytes are 7,112 bytes,
SHA-256 4bdefcf0731c54e39b1cf97d29c06d465cd7e503a6f524f4d486dcd5309f0e38.
The selected blueprint schema digest is
c78bc241904d20320b9ce74bbbdcd0892f7da0c905e1b5a68373a78508b3f251.

The public harness passed 83/83 expected outcomes. Maximum accepted applied
costs and context sizes were:

| transition | CPU | memory | context bytes | inputs | outputs | signers |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Genesis | 445484044 | 1309134 | 3201 | 16 | 16 | 0 |
| Submit | 1123719037 | 2884662 | 5069 | 16 | 16 | 6 |
| Approve | 1296038054 | 3315744 | 5573 | 16 | 16 | 1 |
| Payout | 1306354288 | 3275481 | 5282 | 16 | 16 | 0 |
| Cancel | 1111936283 | 2888751 | 5313 | 16 | 16 | 1 |
| Expire | 1105431591 | 2867354 | 5282 | 16 | 16 | 0 |

Datum boundary cases are 895 accepted, 896 accepted and 897 rejected bytes.
The sanitized checksum-verified package is at
/home/GodOfAgents/vams-evidence/m3-1b-r5-remediation-20260926-829ab544571f; its
SHA256SUMS digest is 622237242572efea84d2bbdbbae1bafe9e121291495bcd9991f1566ebe7842a8.
The package records the 16/16 mutation result and sanitized maximum metrics.
The compiled mutation sweep reports 16/16 controls detected, including all
transition interval controls, schema/identity/hash/asset/policy controls,
Deposit, signer cap, payout removal and duplicate approver state. Traceability
tests cover merged/removed fields, Deposit acceptance and structural-authorizer
mutations.

## Status and impact

F01 = REVALIDATED_OPEN; F02-F05 unchanged; M3 = OPEN; promotion remains
NOT READY. Deposit is disabled pending F05. INV-2 and INV-1, INV-3 through
INV-9 are unchanged. INV-10 is synchronized to structured validation only.
M1 containment, mock-mode behavior, Gateway/M2, frontend, vendors, credentials,
deployment and submodules are untouched.

Next: independent M3.1b-R6 review of R5.
