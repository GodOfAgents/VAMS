# Three CI blocker repairs: candidate evidence

**NOT READY. Source review accepted; final qualification is pending.** This record
supports the existing finding and gate ledgers; it does not replace them or
accept a release milestone.

The owner authorized fixing the three failures in hosted run
[44994918122](https://github.com/GodOfAgents/VAMS/actions/runs/44994918122),
adding regression tests, scanning the exact new commits, then one normal
`remediation/phase1` push and CI rerun if scans pass. Force push, merge and
deployment remain prohibited. The owner selected GPT-6.2 Astra with High
reasoning for independent review. That worker returned an out-of-credits
error before reviewing any source. The owner then confirmed restored credits
and authorized one fresh GPT-6.2 Astra High review. That non-author reviewer
rejected the first candidate, verified the corrections, and accepted the
bounded revised seven-file source identity below for canonical integration.
No provider substitution occurred. That source review is not human/operator
assurance or deployment acceptance. Final scans and hosted CI remain separate.

## Defects and bounded repairs

| Failure | Repair | Regression contract |
| --- | --- | --- |
| Direct audit scripts cannot import the repository's `scripts` package on a clean runner; the job also invokes pytest without installing it. | Bind `PYTHONPATH` to `github.workspace` and install the same `pytest==9.1.1` pin already used by the Python job. Preserve every test command and failure condition. | A clean subprocess executes the two import-dependent audit tests. Workflow mutations removing dependencies, unpinning, reordering installation, redirecting imports, skipping tests or suppressing failure are rejected. |
| The default-credential gate rejects its own deliberate Semgrep negative controls, detector expressions and historical explanation. | Recognize only four exact, existing file identities using SHA-256, token-line sets, exact Git inventory, containment, regular-file and size checks. Test tokens against that same verified buffer. Those four files remain byte-identical to the parent. | Runtime tokens, moved/copied fixtures, benign or malicious fixture edits, missing/unlisted files, inventory aliases, symlinks and oversized files fail. Raw filename bytes are preserved and reviewed evidence is never reopened. No directory exemption, new Gitleaks ignore or runtime credential exception is introduced. |
| Provenance test collection binds to one workstation's absolute checkout; active metadata tests also depend on ignored caches and stale historical source/blueprint bytes. | Resolve the test root from its own file. Build self-contained, explicitly synthetic metadata fixtures for active verifier-boundary tests, requiring a pristine fixture pass before each mutation. | Relocation with spaces, positive metadata validation and targeted source/cache/lock/blueprint mutation rejection execute against the unmodified production verifier. Synthetic metadata cannot satisfy the approved native-tool path check. |

The synthetic provenance fixture is unit-test evidence only. Its source
markers, one-file package trees and one-byte program entries are explicitly
labelled as synthetic; they are neither Aiken programs nor native compilation,
upstream dependency provenance, authentic proof or release evidence. The
production verifier's schema, compiler path/hash pins, CLI and validation
rules remain unchanged. Native R28/Slot 08 qualification was not invoked.

The pre-existing nine exact pytest deselections are unchanged, including the
three retired tests in this provenance module. No new skip, deselection,
xfail, tool suppression, shortened economic run or readiness exception was
added. Tool versions and remaining workflow commands are unchanged.

## Source bindings

Parent: `a2cf353f8762ef151314bbc4dfb9e0b1e10c6e60`.
Revised seven-code-file prospective tree before this documentation:
`d5ea83a6e2cc70ae6d303e5152f29c33c6f61b43`.

| Source | SHA-256 |
| --- | --- |
| `.github/workflows/security-gates.yml` | `30381c8cffee187fb5411b1279c07c68a4b52e1cf21ef44243f06075bc6d33d4` |
| `scripts/audit/validate_workflow_security.py` | `4ff226a0a2907a953553d2a6d1fb13e26a789f1d32b47bc99a6d50b4f366bd25` |
| `scripts/audit/test_workflow_security.py` | `488b0bd7d22779f0490699a0a0e782a5d9ffdffe75e72f267f5783336db69919` |
| `scripts/audit/test_ci_entrypoints.py` | `ac20d960b0fe244c8ecad769861bc31dc69d6187f432fd2a999a0b9d060772df` |
| `scripts/security/default_credential_scan.py` | `9082d40b4d098a22bf63083c39744cc0e50d1421513b448fa2efa7329830b2f8` |
| `scripts/security/test_default_credential_scan.py` | `47e3204bf31205e19df120d92d26deee1077cb4e49a51800b4a1ef94a47f6ddc` |
| `scripts/remediation/test_m3_1b_r9_provenance.py` | `239e8aeb452f4f23ecb2c0c8ab8a5e1ec6a3df6205453d5be60b2490f3efd422` |

Unchanged production verifier SHA-256:
`10cc4605ee5a9b6024956c77f5a8af8044882be3019c30a43e31e22f6416bc89`.
Unchanged `pytest.ini` SHA-256:
`e1e12abd5f6a31a11f641aa9bd47ea3c5d4039662a70cfccdb0eae5327d74010`.

## Executed local verification

Python: 3.12.16. Tests run in an isolated local clone, excluding the owner's
uncommitted payment source/tests, changelog edits and `.codex` files. Raw
stdout, stderr, native exits, commands and source bindings are retained in
`.tmp-history-tests/ci-blocker-fix-20261122-01/`.

| Command | Result |
| --- | --- |
| `python -m pytest -q scripts/audit/test_workflow_security.py scripts/audit/test_ci_entrypoints.py scripts/security/test_default_credential_scan.py scripts/remediation/test_m3_1b_r9_provenance.py` | Revised source: exit 0, 62 passed, 3 pre-existing deselections, 149 subtests passed. |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q scripts/security/test_runtime_mode_preflight.py` | Revised source: exit 0, 27 passed; no unrelated pytest plugin required. |
| `PYTHONPATH="$PWD" python scripts/audit/test_audit_program.py -v` | Exit 0: 45 tests, OK. |
| `PYTHONPATH="$PWD" python -m unittest discover -s scripts/audit -p 'test_*.py'` | Revised source: exit 0, 241 tests, OK. Earlier source: 240 tests, OK. |
| `python scripts/security/default_credential_scan.py` | Exit 0: passed. |
| `python scripts/security/secret_history_prevention_scan.py` | Exit 0: passed. |
| `python scripts/security/gitleaks_ignore_reproof.py` | Exit 0: all 638 accepted entries re-proved. |
| `VAMS_ENV=testnet python scripts/security/runtime_mode_preflight.py --require-live --expected-mode testnet` | Exit 0: runtime-mode-only check, live classification, gateway mock disabled. This does not prove provider integration or deployment readiness. |

The first focused run failed with eleven errors in the new test support
code; its evidence is retained. Those errors were fixed before the passing
focused run above. A broader check interrupted before completion is also
retained and has no accepted result. Counts above are separate runs and
must not be added together.

The first candidate (`5e8fb8334043daeaad264e8b6a27018e26b14516`) also passed
the unchanged full CI Python commands: `pytest -v --tb=short
--ignore=docs/remediation/m3_f05_design_r2/test_design.py` reported 3,599
passed, one existing skip, nine existing deselections and 5,594 subtests;
the separate `pytest -v --tb=short
docs/remediation/m3_f05_design_r2/test_design.py` reported ten passed. The
existing skip is the dashboard AST comparison that requires a pre-repair
BASE file in script mode. Envoy 1.39.1 matched CI SHA-256
`002c6e1c69ed0fa0ea381887247cadadfaec9481375fa8d8d2b1731eeabf40b8`.
These first-candidate results do not cover the later review corrections.

The reviewer rejected that first source identity for the missing audit-job
pytest dependency, inventory aliasing, and reopening reviewed scanner
evidence after hashing. The revised source adds the dependency and its
mutation tests, preserves exact Git path bytes, and checks all tokens in
the authenticated buffer. Focused and affected-audit checks are rerun;
the required hosted workflow will exercise the combined final commit.

Exact-commit scans, review acceptance and publication results are recorded
separately when they exist. Previous Solidity,
Aiken and hosted security passes belong to the parent run and are not fresh
acceptance for this candidate. No full-workflow or readiness PASS is claimed.

## Invariant and authority impact

| Invariant | Impact |
| --- | --- |
| INV-1 regional emissions | Not touched; contract/runtime cap unchanged. |
| INV-2 insurance yield | Not touched; capital cap unchanged. |
| INV-3 session expiry | Not touched; expiry enforcement unchanged. |
| INV-4 session whitelist | Not touched; scope enforcement unchanged. |
| INV-5 OMS fail closed | Not touched; identity routing unchanged. |
| INV-6 TEE root binding | Not touched; attestation validation unchanged. |
| INV-7 oracle freshness | Not touched; fallback enforcement unchanged. |
| INV-8 supply cap | Not touched; token contract unchanged. |
| INV-9 reward solvency | Not touched; settlement/reward implementation unchanged. |
| INV-10 bridge proof separation | Not touched; bridge implementation unchanged. |

No mock client is promoted. Testnet/public admission, human/operator custody,
privacy acceptance, actual provider evidence and both-chain rehearsals remain
subject to the authoritative existing gates. The branch-only normal-push
exception does not authorize deployment or incident closure. Other branches
and all tags remain outside the publication scope.
