# M3.1b-R11 remediation review

## Scope and disposition

This scoped implementation remediates only the four findings reported by the
independent M3.1b-R10 review: incomplete source binding, incomplete package
resolution binding, unsafe dependency identifiers/path escape, and insufficient
mutation-sensitive coverage. The accepted R10 package was verified before
editing from:

/home/GodOfAgents/vams-evidence/m3-1b-r10-review-20260926-829ab544571f

with SHA256SUMS SHA-256
64503d05d373e452fb036c612032c82fe0b8e6961cc65cfb9a91b1a1435aff6.

The manifest is now closed and versioned. It binds every current Aiken source,
iken.toml, iken.lock, uild/packages/packages.toml, the exact package
directory topology and file digests/types, the pinned compiler, blueprint and
program hashes, plus the two explicitly volatile lock timestamp paths. The
verifier rejects unknown fields, source omission/addition/rebinding, package
index and topology drift, package content drift, unsafe identifiers including
traversal, symlinks/hardlinks/special files, and compiler/network fallback.

## Reproductions and verification

The pre-fix R10 reproductions showed that source omission/addition, a mutated
packages.toml, an extra package directory, and dependency identifier ..
were accepted. R11 focused tests reject each mutation through the public
verifier result. The authoritative workflow is unchanged.

Fresh verification records are external and sanitized:

- /home/GodOfAgents/vams-evidence/m3-r11-smoke.json
- /home/GodOfAgents/vams-evidence/m3-r11-run-2.json
- /home/GodOfAgents/vams-evidence/m3-r11-focused.log
- /home/GodOfAgents/vams-evidence/m3-r11-f01-harness.json
- /home/GodOfAgents/vams-evidence/m3-r11-f01-mutations.json
- /home/GodOfAgents/vams-evidence/m3-r11-traceability.log
- /home/GodOfAgents/vams-evidence/m3-r11-docs.log

The two isolated provenance runs are byte-for-byte equal at the sanitized JSON
result level, both report ok=true, check_exit=0, uild_exit=0, nine
source files, and eleven compiled programs. The focused R11 suite passes all
11 tests. F01 remains a revalidated-open finding; the existing public harness
and mutation suite are verification inputs, not closure evidence.

## Invariants and status

No validator behavior, datum/type, dependency content, deployment state,
credential, vendor, or runtime mock behavior changed. INV-1 through INV-10,
M1 containment, M2/Gateway/Envoy, frontend /nodes, F02-F05 and F09 remain
unchanged. F01 = REVALIDATED_OPEN, M3 = OPEN, Pre-Prod admission is
INCONCLUSIVE, and overall promotion remains NOT READY. Next slice:
independent M3.1b-R12 review.
