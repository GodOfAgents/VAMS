# Independent review — redacted local Gitleaks detect — 2026-10-04

Reviewer: /root/gitleaks_scan_review (read-only review of the exact raw evidence package and current workflow/config).

Integrity result: PASS with a mount-evidence limitation. Full-history/workflow equivalence: FAIL. M0.4 closure: FAIL.

All package checksum entries validate. Reviewer independently verified Gitleaks 8.30.1, its binary hash, bwrap hash, workflow hash and config hash. Exact argv includes --redact=100. Native JSON report is exactly [] (3 bytes); exit 0, stdout empty; stderr says 74 commits scanned. Host/child netns are 4026531833 and 4026532231. Canonical HEAD/status/refs/submodules/inventory match before and after. Canonical and snapshot source-only hashes match over 7,611 paths; all 7,626 prescan content-hash rows match; snapshot inventory is stable. The 15 normalized .git/**/index cache paths differ after post-scan inspections; source/object content remains unchanged.

Mount limitation: the package lacks outer bwrap argv and mount table, so strict read-only bind flags are not independently auditable. Unchanged canonical state and exact prescan snapshot hashes support, but do not prove, the mount claim.

Scope limitation: command omits --all and explicit --config; stderr reports 74 commits, fewer than 76 on HEAD ancestry and 89 across nine refs. This is not all-ref history evidence or workflow equivalence. A separate T06 all-ref scan covers nine refs/89 commits but does not adjudicate current-tree ownership.

M0.4 remains open. Its earlier reconciliation scanned 5,197 inputs and reported 385 first-party findings across 31 paths plus 479 vendor-labelled matches. This detect run has different inputs/flags and no ownership reconciliation, so its empty result cannot clear those findings. No secret value was disclosed.
