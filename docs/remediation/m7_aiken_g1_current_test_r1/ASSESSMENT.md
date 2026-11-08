# M7 current-input Aiken G1 rerun with F05 native tests   2026-10-03

Status: independent read-only review PASS as a diagnostic capture; required G1 command failed.

## Scope and exact result

The unchanged command from .github/workflows/security-gates.yml was run against an isolated copy of the current Cardano tree with network access disabled:

    aiken check --deny --seed 20260711 --max-success 250

Pinned runtime: aiken v1.1.21+42babe5, executable SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79. The copied tree included the final F05 test file (SHA-256 a3bc9ccafa26ae4219207a620940ca7da3296608d576725c325a4558b958336d).

The process exited 1. Structured output reports 122/122 scenarios passed (115 unit, 7 property), zero failed scenarios, across seven modules; the F05 native module reports 2/2. The exact output and stderr are in verification.json and verification.stderr. No explicit warning/error explains the nonzero exit in captured stderr. A control with the same pinned binary, seed and max-success but without --deny exited 0 with the same 122/122 result. This associates the failing result with the deny flag, but does not identify a specific denied warning or prove its cause. G1 therefore remains failed and receives no pass credit.

The snapshot preflight matched all 73 selected current Cardano inputs; the snapshot input hashes and canonical input hashes remained stable through the run. The map covers all 49 .ak files, every file under cardano/build/packages, and aiken.toml, aiken.lock, and aiken-dependency-manifest.json. Exact per-path digests and pre/post comparisons are in INPUTS.json. The test module is present in the 122-case output.

## Evidence files

- RUN.json   exact command, tool/workflow/test hashes, counts, exit and output digests; SHA-256 1f7280be3755099bc75e6bab566b28a1437156db9ac624d73e46fee15e0173ea.
- INPUTS.json   73 input path hashes and pre/post comparisons; SHA-256 983405323bfa6907eeb9b01e8fbbdfc0ca4a6dc62026a549265a71820f8a63c1.
- verification.json   full structured test output; SHA-256 33b4f396b899731c82dbedcd03d0d77a93e533470796c6ce3ffc9961db590084.
- verification.stderr   captured compiler/resolver output; SHA-256 d41cb0d124b5eeaf2aca5364610ad8856c8d73a3da95d805c141a1d82dc6fd2f.

Aiken reported resolving two packages from the local cache. The run used bubblewrap with --unshare-net. No tool or dependency was installed or fetched from the network. The canonical checkout was not modified by the test run.

## Evidence limits

This is current local native test and input-capture evidence only. It is not a passing G1 command, hosted CI, ledger admission, Cardano Pre-Prod rehearsal, or live-network result. It does not grant an F05 registry-case or mutation count. The test-only module and prior applied-policy identity record remain separate evidence: identity is anchored to the prior independently accepted pinned 1.1.21 application record; this G1 run does not recompute identity.

## Independent review

Independent read-only review by /root/epoch_guard_independent_review: PASS for evidence integrity and diagnostic classification. The reviewer verified all 73 input hashes match between canonical and isolated snapshot, input pre/post equality, the current test source hash, the exact workflow command and pinned executable identity, the 2/2 F05 module within 122/122, and output-file digests. Reviewer did not rerun Aiken. The exit-1 G1 classification remains unchanged; the --deny comparison supports association only and does not identify the cause.

The accepted current ledger is docs/remediation/m3_f05_2a_evidence_classification_r1/CASE-STATUS.json at 45/55 negatives and 18/21 mutations. The older docs/remediation/m3_f05_2a_status_r1/CASE-STATUS.json is stale at 42/55 and 12/21; it remains historical and is not rewritten. The newest accepted per-slice overlays support the current counts. The Oct 3 native-handler diagnostic grants no additional count. Next single slice: r2_signature_for_other_seed, using the existing runner's ephemeral test-only committee and synthetic compiled-context evidence; no applied-parameter variants or original/live keys are required.


## Post-run blocker reassessment - 2026-10-03

The separately captured --deny tty run reports 32 compiler warnings, including a single-clause warning in validators/f05_authority_policy.ak:32; the original non-TTY test transcript did not include this diagnostic. F05 proof-domain case r2_signature_for_other_seed is blocked under the frozen ledger_tx_sim contract and exact applied-policy ID; see docs/remediation/m3_f05_2a_signature_other_seed_r1/ASSESSMENT.md. Next safe slice: change only the F05 single-clause syntax and verify unchanged applied policy identity. Other warnings remain in dirty Cardano files; this slice cannot make full G1 pass.


## F05 warning remediation accepted - 2026-10-03

The F05 single-clause warning was removed with a behavior-preserving let destructuring. Two pinned builds match the accepted applied artifact and policy ID; focused F05 tests pass 2/2. A fresh full G1 run against final source still exits 1 with 122/122 tests and 31 warnings. Independent integrated review passed. Exact record and hashes: docs/remediation/m7_f05_warning_identity_r1/ASSESSMENT.md. Next bounded slice: the remaining unused imports and callback parameter in lib/vams/governance.ak.


## Governance warning cleanup accepted - 2026-10-03

Nine unused-symbol warnings were removed from lib/vams/governance.ak. Pinned baseline/candidate builds produce identical plutus.json. The warning-only count fell from 31 to 22. The exact full G1 command still exits 1 with 122/122 tests passed and all 73 inputs unchanged. Independent integrated review passed. Record: docs/remediation/m7_governance_warnings_r1/ASSESSMENT.md. Next slice: inspect and address the two warnings in validators/insurance_fund.ak.


## Insurance warning cleanup accepted - 2026-10-03

The exact current-input G1 rerun after the insurance cleanup remains failed: `aiken check --deny --seed 20260711 --max-success 250` exited 1 with 122/122 test scenarios passed, 1865 checks, 0 errors and 20 warnings. All 73 pre/post input hashes match. Warning-only `aiken check --deny --skip-tests` also exits 1 with 20 warnings and no `validators/insurance_fund.ak` warning. Baseline/candidate builds are byte-identical; independent integrated review PASS. No INV-2 behavior or F05 count changed. Full record: `docs/remediation/m7_insurance_warnings_r1/ASSESSMENT.md` (SHA-256 426e9327f748570809e02d678e93e7c162badfa6ae992acbe304b67d819d0099). The next warning cluster is the four unused imports in `validators/governor.ak`.


## Governor warning cleanup accepted - 2026-10-03

Removed four confirmed-unused imports from `validators/governor.ak`. Network-isolated baseline/candidate builds match across the complete Plutus blueprint and all compiled scripts. The warning-only diagnostic and exact G1 command now report 16 warnings. G1 still exits 1 with 122/122 scenarios passed, 1865 checks and 0 errors; all 73 inputs match and remain unchanged. Independent integrated review PASS. Record: `docs/remediation/m7_governor_warnings_r1/ASSESSMENT.md` (SHA-256 624e3f62153f869ac6b935db158fa16276c38a9e42b03f9586e147ccb12b8ca4). Next warning cluster: the three scoped warnings in `validators/timelock.ak`.


## Timelock warning cleanup accepted - 2026-10-03

Removed two unused imports and renamed one unused callback parameter in `validators/timelock.ak`; the own-input authorization check is unchanged and baseline/candidate compiled outputs match. Warning-only and full G1 now report 13 warnings. G1 exits 1 with 122/122 scenarios passed, 1865 checks, 0 errors, and all 73 input hashes unchanged. Independent integrated review PASS. Record: `docs/remediation/m7_timelock_warnings_r1/ASSESSMENT.md` (SHA-256 6558258c04a1c98f4e3ae68379070fe579dab728186941aa856e1fe183458b32). The next step is an `agent_nft.ak` behavior audit before choosing a warning or validator remediation.


## Governance-policy warning cleanup accepted - 2026-10-03

Removed the scoped unused symbols from `validators/governance_policies.ak`; pinned offline baseline/candidate builds match for the complete blueprint and all scripts. Warning-only and current-input G1 report 7 warnings; G1 exits 1 with 122/122 scenarios, 1865 checks, 0 errors and all 73 inputs unchanged. Independent integrated review PASS. No F05 case/mutation or readiness credit. Record: `docs/remediation/m7_governance_policies_warnings_r1/ASSESSMENT.md`. Next bounded slice: preserve the F04 mismatch evidence and seek the smallest owner decision before changing identity-validator behavior.


## F04 identity-path reconciliation blocker - 2026-10-03

The remaining seven G1 warnings point into `agent_nft.ak`; before any behavior edit, resolve the normative path mismatch: the frozen spec names standalone `agent_nft.agent_nft.mint`, while accepted R6 uses `agent_registry.agent_registry.mint`, and standalone mint currently rejects all redeemers. See `docs/remediation/m7_agent_nft_audit_r1/ASSESSMENT.md`. No F04 evidence or F05 counts transfer across entrypoints.
