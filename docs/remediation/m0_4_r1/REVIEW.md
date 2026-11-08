# M0.4-R1 implementation and M0.4-R2 independent reconstruction

Date: 2026-09-21  
Branch: `testnet/remediation-20260907`  
Superproject HEAD: `829ab544571f12efe50ecb5740f129c8acb3e16f`

## Verdict

**PASS for M0.4 only.** The aggregate current-tree gate independently
reconciles **0 first-party + 161 M0.3a + 160 M0.3b + 158 M0.3c = 479 vendor
identities**, with zero unknown ownership. M0.4 closes only the current-tree
aggregate vendor-baseline gap. It does not close M0, T06, M7, F01-F18, or any
promotion gate.

The custom R9 durable-package validator remains auxiliary, is not invoked by
this gate or CI, and is permanently outside promotion trust. R10's substantive
158-record reconstruction is used only as a reviewed sanitized identity source;
R10's FAIL verdict on the R9 validator remains unchanged.

## Implementation

- `scripts/security/m0_4_vendor_baseline.json` is the deterministic minimal
  479-record baseline. It stores only ownership scope, owner commit, canonical
  path, rule, line range, file SHA-256, stable sanitized identity digest, and
  compact reviewed-source provenance. Its SHA-256 is
  `3a4526acf33ab4adeff87da1553cb5e4493799c3696664c2d60a126a9aa086f4`.
- `scripts/security/m0_4_vendor_baseline_gate.py` pins Gitleaks 8.30.1 and
  binary SHA-256
  `88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509`.
  It derives recursive Git ownership, selects the deepest gitlink, rejects
  dirty or drifting vendor worktrees, verifies pinned blob hashes, stages the
  current tracked and non-ignored untracked tree, and reconciles the exact set.
- The raw scanner report exists only in a mode-private temporary directory and
  is deleted in the gate's `finally` path. Only a sanitized aggregate summary
  may be written.
- Four pre-existing first-party synthetic fixtures now assemble the same public
  vendor assertion at runtime across source lines. This removes static
  key/value candidates without changing fixture semantics, scanner
  configuration, vendor content, or an allowlist.
- `.github/workflows/security-gates.yml` checks out submodules recursively and
  runs the gate inside the existing checksum-verified Gitleaks job. Complete-
  history Gitleaks, TruffleHog, default-credential checks, the narrow allowlist
  regression, F18 audits, and every other security job are unchanged.

## Independent reconstruction

A separate no-import verifier rebuilt all identities directly from the accepted
M0.3a and M0.3b decision files and R10-reviewed M0.3c R9 decision file. It then
re-enumerated Git trees, verified all vendor blobs, staged the current tree,
ran an unsuppressed pinned scan, and compared its independently computed set to
the baseline. It reported:

```text
first_party=0 m0_3a=161 m0_3b=160 m0_3c=158 vendor=479 unknown=0
baseline_sha256=3a4526acf33ab4adeff87da1553cb5e4493799c3696664c2d60a126a9aa086f4
source_manifest_sha256=6c995f8cdf1b3c1c93c10a93ea39062d27411d6d6a565df842bb6d94f3a90cba
```

That digest is the independent reconstruction snapshot before this review text
was added. The final post-documentation gate record, including its current-tree
source-manifest digest, is written once to
`/home/GodOfAgents/vams-evidence/m0-20260909/m0-4-r1-final-20260921T111959Z-829ab544571f/current-tree-summary.json`.

No raw match, secret, snippet, entropy, fingerprint, or raw report was retained.

## Verification

| Check | Result |
| --- | --- |
| Focused M0.4 tests | PASS, 10/10 |
| Existing Gitleaks configuration tests | PASS, 4/4 |
| Existing working-tree inventory tests | PASS, 7/7 |
| Existing narrow allowlist regression | PASS |
| Baseline count, uniqueness, provenance and reviewed-source equality | PASS, 479/479 |
| Fresh real-tree gate, pinned Gitleaks 8.30.1 | PASS, exact `0 + 161 + 160 + 158` |
| Separate unsuppressed no-import reconstruction | PASS, exact same set and digests |
| Workflow supply-chain validator | PASS, 40/40 action references pinned |
| Workflow YAML parse | PASS |
| `git diff --check` | PASS after documentation update |

The focused mutations cover first-party findings; added, omitted, and duplicate
vendor identities; moved paths; changed rules, line ranges, and hashes; wrong
owners and commits; pin drift; dirty vendors; unknown ownership; nested-parent
misattribution; scanner drift; and malformed or duplicate baseline records.

## Security and roadmap impact

INV-1 through INV-10 are untouched. No DA, OMS, Trails, TEE, escrow, bridge,
gateway, runtime, deployment, or mock-mode behavior changed. T06 history and
credential-incident closure is unchanged. F01-F16 revalidation, F17, final F18
disposition, M7, M0, and every promotion gate remain open for the subsequent M0
slices.
