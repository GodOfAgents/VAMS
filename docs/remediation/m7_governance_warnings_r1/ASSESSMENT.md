# M7 governance-library warning remediation - 2026-10-03

Status: accepted after independent integrated review. G1 remains failed.

## Scope and changed files

Changed only cardano/lib/vams/governance.ak. Removed the unused dict module, VerificationKey, and seven unused governance type imports; renamed the unused callback argument from output to _output. The callback predicate and all function bodies remain unchanged. Baseline source SHA-256 d6d7c7b6f4da7256218e48cb280a6ee05b07a19aba86e3b4f764f66aaa91380e; candidate SHA-256 b288f800f70d5aae566a745a5853067a173dd5cc8ad3225e7ea8d4bb89d29e55.

Evidence is in docs/remediation/m7_governance_warnings_r1/. No contract economics, authorization checks, or INV-1 through INV-10 enforcement changed.

## Verification

Pinned Aiken: v1.1.21+42babe5, SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79. All runs used existing local binaries/cache and network-disabled bubblewrap snapshots.

- Baseline and candidate aiken build both exited 0. Generated plutus.json is byte-identical, SHA-256 c4230410d0caac45f2c71d36e45a539c78087697128ce1533306d17e96a48008. BUILD-COMPARISON.json SHA-256 d2b271c9c242b082083e023156655528713ccf5d340db7450c88e377dff6d2b7.
- aiken check --deny --skip-tests on the exact candidate copy exited 1 with 0 errors and 22 warnings, down from 31. The warning transcript contains no lib/vams/governance.ak warning. Transcript SHA-256 6df66adbf6fd31bea15f028aa0d7f1ec813f2d2677dada2e5da4dc2b95c1af54.
- CI command aiken check --deny --seed 20260711 --max-success 250 on the exact candidate snapshot exited 1; all 122 scenarios passed (115 unit, 7 property). All 73 inputs matched canonical and snapshot preflight; canonical and snapshot inputs remained unchanged. RUN.json SHA-256 354e5c5cc04bdd2327eda5a77828bc2a10a94ca9a47eda67a6c0c72d5fd37310; INPUTS.json SHA-256 36fed64c0cf8f55df182097b628c2c40408fc7ed416978aa74615f89b35ce35e; verification.json SHA-256 33b4f396b899731c82dbedcd03d0d77a93e533470796c6ce3ffc9961db590084; stderr SHA-256 905b165053cacb443e93b7cae376513c0dc1d317483209637c634c923c4d931a.
- git diff --check: exit 0.

The required G1 gate remains failed due warnings in other Cardano files. No tool was installed or fetched; no key, transaction, or network action was used.

## Independent review

/root/f05_warning_integrated_review: PASS for the exact baseline and candidate source plus evidence snapshot. The reviewer verified every manifest hash, the limited unused-symbol diff, identical pinned build outputs, warning reduction to 22 with this library's warnings absent, and the G1 122/122 test total with exit 1 and unchanged 73-input map. Reviewer did not rerun project tools.

## Evidence limits and remaining blockers

This is local compiler and test evidence only. It grants no F05 case/mutation credit, ledger admission, Pre-Prod, or live-network evidence. F05 remains 45/55 negatives and 18/21 mutations. G1 is still failed; 22 warnings remain. Governance and privileged-role controls, full security and dependency checks, provenance and reproducible builds, Cardano Pre-Prod and Polygon Amoy prerequisites, INV-1 through INV-10, mock containment, and T06/history remain unresolved. The signature-domain case has the owner decision documented in docs/remediation/m3_f05_2a_signature_other_seed_r1/ASSESSMENT.md; six applied-parameter variants retain their A/B/C decision. Readiness is NOT READY. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

## Roadmap reassessment and next slice

M7 remains incomplete. The next single warning slice is the two warnings in cardano/validators/insurance_fund.ak: the single-clause InitializeFund match and the unused after argument in the test helper. Inspect the helper and INV-2-sensitive tests before editing, then prove compiled output and tests remain unchanged. Reassess the full plan after independent review.
