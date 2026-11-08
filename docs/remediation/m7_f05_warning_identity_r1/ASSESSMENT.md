# M7 F05 single-clause warning remediation - 2026-10-03

Status: accepted as a behavior-preserving source cleanup after independent integrated review. G1 remains failed.

## Scope and changed files

Changed only cardano/validators/f05_authority_policy.ak. Replaced its warned one-clause redeemer match with Aiken's suggested let destructuring, keeping the same BootstrapAuthority proofs binding and validate_bootstrap arguments. The exact source hash is e9d3ac9cbb14b9e7693dc12430234694c82eb52e61d176e1e39992fb9cbeafa8. The reconstructed prior accepted source hashes to 5c01f9556d922a719a7dac348d8b7175d660ef387fdf2005979c27fb2e833b05; the independent reviewer confirmed the integrated diff is one hunk. The change does not alter INV-1 through INV-10 or authorization checks.

Evidence is in docs/remediation/m7_f05_warning_identity_r1/. The prior blocker record for r2_signature_for_other_seed is docs/remediation/m3_f05_2a_signature_other_seed_r1/ASSESSMENT.md. Current status and handoff are summarized in docs/remediation/STATUS.md and docs/remediation/SESSION_HANDOFF.md.

## Verification

Pinned Aiken: v1.1.21+42babe5, SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79. All runs used existing local binaries and package cache with network disabled.

- PYTHONDONTWRITEBYTECODE=1 bwrap --unshare-net --ro-bind / / --dev /dev --proc /proc --bind /tmp /tmp --bind /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m7_f05_warning_identity_r1 /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m7_f05_warning_identity_r1 --chdir /home/GodOfAgents/code/VAMS-testnet /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-identity-gate-20261002-r1/identity_probe.py --evidence /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m7_f05_warning_identity_r1/identity-run-c: exit 0. Two independent pinned builds match the prior applied artifact and transaction witness byte-for-byte: 3,467-byte compiledCode, SHA-256 fc8726cff89172d4944e257a2eb2659d35363c8e5a4d423ed8a2112eb5af7e59; blueprint SHA-256 c4230410d0caac45f2c71d36e45a539c78087697128ce1533306d17e96a48008; applied policy ID 9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731. RESULT.json SHA-256 68dcd9958abe28955255e049ed12090faddb3b60df089dfe9b226761f41af0af.
- aiken check --debug --trace-level silent --match-tests 'f05_authority_policy.{..}': exit 0; 2/2 focused F05 native tests passed on pinned Aiken 1.1.21.
- CI command aiken check --deny --seed 20260711 --max-success 250, on an isolated snapshot of the exact final source: exit 1; 122/122 scenarios passed (115 unit, 7 property), including F05 2/2. All 73 input hashes matched canonical preflight and snapshot preflight; snapshot and canonical inputs were unchanged. RUN.json SHA-256 bfdd974961b9d8406b9d5ac8e32f673c68ad5864137f6ac636b7576aeb4e3873; INPUTS.json SHA-256 9a75958ac1bef19f2d9849604894549485c9f4f5c8255152a61506a2804e9e09; verification.json SHA-256 33b4f396b899731c82dbedcd03d0d77a93e533470796c6ce3ffc9961db590084; stderr SHA-256 b55c3f5d58179e8c198d322c97972c9355651ea2174e1bff3942984b4e537df7.
- aiken check --deny --skip-tests, in a PTY on a fresh copy of the exact final source: exit 1; 0 errors and 31 warnings, down from the captured 32. The warning in f05_authority_policy.ak is gone; remaining warnings are in other Cardano files. Transcript SHA-256 df9ac7d3b1f3b42b1b9f9d6cc730a76d4ea6ccb1f5d865f3cac9619979141c30.
- aiken fmt --check validators/f05_authority_policy.ak: exit 1 because the whole file has formatting differences outside this warning fix. Only the changed expression was aligned with the formatter; unrelated layout changes were not applied.
- git diff --check: exit 0.

No tool or dependency was installed or fetched. No key, credential, transaction, or live-network action was used.

## Independent review

/root/f05_warning_integrated_review: PASS for the exact final source and evidence snapshot. The reviewer verified every snapshot manifest hash, the one-hunk diff, matching applied artifact and policy identity, G1 input/output classification, 122/122 tests with required command exit 1, and 31 remaining warnings with the F05 warning removed. Reviewer did not rerun project tools.

## Evidence limits and remaining blockers

This slice is source cleanup and local compiler/test evidence. It grants no negative-case or mutation credit, ledger admission, Cardano Pre-Prod, or live-network evidence. The accepted F05 ledger remains 45/55 negatives and 18/21 mutations. G1 remains failed; full security, governance, provenance, reproducible-build, Polygon Amoy and Cardano Pre-Prod prerequisites, invariants INV-1 through INV-10, mock containment, and T06/history remain open. F05 proof-domain evidence still requires an owner choice recorded in docs/remediation/m3_f05_2a_signature_other_seed_r1/ASSESSMENT.md; six applied-parameter variants retain their separate A/B/C decision. Readiness is NOT READY. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

## Roadmap reassessment and next slice

M7 remains incomplete. The final pinned command is blocked by 31 warnings across other dirty Cardano files; the next bounded slice is the unused imports and unused callback parameter in cardano/lib/vams/governance.ak, whose warning cluster is isolated to that one library file. After its targeted checks and independent review, reassess the full plan again.
