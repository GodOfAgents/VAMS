# M3.1b-R13 remediation review

R13 remediates only independent R12 finding R12-01. The accepted R12 package was
verified before editing from
/home/GodOfAgents/vams-evidence/m3-1b-r12-review-20260926-829ab544571f
with SHA256SUMS digest
99618903a2ae8702f3bd0b658da446ae56fa36b0b5d35628500788e18f7991aa.

Before R13, disposable manifest mutations reproduced raw KeyError, IndexError,
and TypeError behavior for malformed project_inputs and package_cache/index
containers. R13 now validates container type, exact cardinality, nested closed
keys, strict scalar types, and integer bounds before indexing or dereferencing.
JSON booleans are rejected where integers are required. The callable API raises
VerificationError; the CLI returns a bounded sanitized JSON error with no
traceback. Temporary CLI state is cleaned up.

Fresh verification:

- R13-focused suite: 13 tests passed, including the complete R11 suite and
  table-driven malformed-container coverage.
- Canonical pinned Aiken 1.1.21 isolated run: check/build passed, 9 sources and
  11 programs.
- Five historical R10 mutations: 5/5 rejected.
- Python compilation, JSON validation, documentation validation, recursive
  submodule status, and git diff check: passed.

No manifest, lockfile, Cardano validator, shared type, blueprint, dependency
package, deployment, credential, or unrelated runtime file changed. F01
remains REVALIDATED_OPEN, F02-F05 remain unchanged, Deposit remains disabled
pending F05, M3 remains OPEN, Pre-Prod admission remains INCONCLUSIVE, and
promotion remains NOT READY. INV-1 through INV-10 and mock-mode behavior are
unchanged. This is local remediation only; next slice is independent
M3.1b-R14 focused delta review.
