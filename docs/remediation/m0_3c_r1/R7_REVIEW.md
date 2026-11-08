# M0.3c-R7 remediation review

Status: locally implemented and verified; independent M0.3c-R8 review required.

Repository: `/home/GodOfAgents/code/VAMS-testnet`

Branch/HEAD: `testnet/remediation-20260907` / `829ab544571f12efe50ecb5740f129c8acb3e16f`

Parent/target pins: `aa677e9d28ed78fc427ec47ba2baef2030c58e7c` / `fcbae5394ae8ad52d8e580a3477db99814b9d565`

## R6 findings reproduced

The R6 package passed strict checksums and its `SHA256SUMS` file hashes to `21d7481c6b0288cab7010fdc9a4cde3e52db2f6349945f23b0854e153369ddd5`. A temporary snapshot reconstructed from the immutable R1/R5 verification copies reproduced the five R1 boundary bypasses, five R5 boundary bypasses, and both same-standard execution-context bypasses. The harness disabled only historical comparisons against repository files that R7 necessarily changes; the vulnerable schema, filesystem, checksum, classifier, and gate logic was preserved. The snapshot was deleted after sanitized results and hashes were recorded.

## Remediation

Evidence-tree validation now walks an exact allowlisted topology with descriptor-relative, no-follow opens. It rejects symlinks, hardlinks, FIFOs and other special files, unknown files or directories, empty directories, noncanonical paths, and inode swaps. JSON loading rejects duplicate keys, non-ASCII or normalized aliases, slash-sensitive metadata, controls, nulls outside declared schemas, floats/non-finite numbers, excessive integers, oversized values, collections, depth, and serialized artifacts. Historical R1 and R5 packages remain content-bound and valid; new R7 timing fields are bounded integers.

Custom-error confirmation no longer uses a repository-wide declaration-name match. The production resolver binds the exact assertion, invoked operation, actual deployed artifact, exact error signature and selector, declaration owner and pinned blob, caller blob, and full inheritance/interface/used-library route. The independent oracle implements a separate parser, graph walk, target catalog, and Keccak implementation. Missing, sibling, unrelated, import-only, ambiguous, wrong-signature, stale, partial, or rebound context remains unresolved and cannot pass the public exact-set gate.

## Observed local result

Fresh independent and production reconciliation agree on 158 findings across 22 paths: 83 exact custom-error execution contexts and 75 public ECDSA DER vectors. Direct ownership remains 821 blobs with three child gitlinks excluded. Dispositions remain 158 `confirmed_noncredential_fixture`, zero `unresolved`, and zero `potential_credential`. These totals were retained from fresh proof, not assumed.

The expanded focused suite passes 47/47, including 8 R7 context/filesystem tests. M0.3a, M0.3b, and existing Gitleaks suites pass 20/20, 16/16, and 11/11. The negative fixture regression, fresh unsuppressed Gitleaks 8.30.1 scan, independent reconciliation, context mutation matrix, separate exact-set gate, legacy evidence validation, checksum validation, and diff checks pass. The scanner still exits 1 with 158 findings; the separate gate exits 0.

Evidence: `/home/GodOfAgents/vams-evidence/m0-20260909/m0-3c-r7-20260920T164522Z-829ab544571f`.

No raw scanner match, credential value, snippet, entropy value, fingerprint, or value-derived digest is retained. No vendor content, `.gitleaks.toml`, production, runtime, gateway, contract, deployment, CI, or mock-mode behavior changed.

## Invariant and mock-mode impact

| Invariant | Impact |
| --- | --- |
| INV-1 | No impact; regional emissions are unchanged. |
| INV-2 | No impact; insurance deployment limits are unchanged. |
| INV-3 | No impact; session-key lifetime is unchanged. |
| INV-4 | No impact; session-key scope is unchanged. |
| INV-5 | No impact; OMS fail-closed routing is unchanged. |
| INV-6 | No impact; TEE identity binding is unchanged. |
| INV-7 | No impact; oracle freshness and fallback are unchanged. |
| INV-8 | No impact; the VAMS supply cap is unchanged. |
| INV-9 | No impact; reward solvency is unchanged. |
| INV-10 | No impact; bridge proof/payload separation is unchanged. |

Mock mode has no impact because this slice changes only local adjudication, evidence validation, tests, and audit records.

M0.3c-R7 is not independent acceptance. M0, M7, T06, F18, and every promotion gate remain open. The next single slice is independent M0.3c-R8 review.
