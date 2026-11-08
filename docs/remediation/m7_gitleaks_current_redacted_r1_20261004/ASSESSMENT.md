# M7 redacted local Gitleaks detect run — 2026-10-04

## Result

Pinned Gitleaks 8.30.1 ran once against an exact disposable snapshot of the current 7,626-path checkout. Exact command:
 /home/GodOfAgents/vams-evidence/toolchains/gitleaks-8.30.1/gitleaks detect --source . --redact=100 --report-format json --report-path /home/GodOfAgents/vams-evidence/m7-gitleaks-current-redacted-r1-20261004/gitleaks-report.json

Exit 0; stdout empty; redacted JSON report is []; zero findings and rule types. stderr reports 74 commits scanned. No secret values are included in the report or this record. Network namespace differs from the host, confirming --unshare-net; canonical HEAD, status, refs, submodules and inventory remained unchanged.

Tool SHA-256: 88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509. Workflow SHA-256: baf53503673b70c5185f654f8f694f1feaf98af68ee56e29c83c01ee0cf0593c. Config file SHA-256: 40ddce18233e73c94668ddd47a5abe2a6afa0e9bc4602657dc34ec2b78606ecd. bwrap SHA-256: 0abea81db798ebf6b4742ac0664802d97521547a353c2a0dbdc21d76cbbfd2c0. Native report SHA-256: 37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570.

## Scope and qualification

This is a limited local detect run, not the workflow’s all-ref history scan. Its argv omits --all and an explicit --config; captured stderr reports 74 commits, while the repository has 76 commits on HEAD ancestry and 89 commits across nine refs. The exact workflow/T06 all-ref form is separately recorded as gitleaks git with --log-opts="--all -m". That T06 evidence does not reconcile current-tree ownership or close M0.4.

This empty result is not comparable to the earlier M0.4 current-tree reconciliation, which used 5,197 inputs and reported 385 first-party findings across 31 paths plus 479 vendor-labelled matches. It performed no ownership reconciliation. M0.4 remains unresolved and the 385 first-party findings are not dispositioned.

The evidence package verifies that all 7,626 paths matched the canonical checkout before scan; 7,611 source/Git-object content hashes still match after scan. After post-run Git status/submodule inspection, 15 copied .git/**/index cache files changed; source/object/history files did not. Canonical state did not change. The package does not preserve the outer bwrap argv or mount table, so its read-only mount flags cannot be independently verified from this capture; unchanged canonical inventories/status and exact pre-scan snapshot hashes are supporting evidence, not a substitute for captured mount flags.

Independent review result: integrity PASS with the mount-evidence limit; full-history/workflow equivalence FAIL; M0.4 closure FAIL. Review details are in REVIEW.md.

This run changes no source, credentials, dependencies, toolchain, vendor, or refs. It is local scanner evidence only and does not establish hosted CI, full history, credential rotation, chain behavior, or deployment readiness. Readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
