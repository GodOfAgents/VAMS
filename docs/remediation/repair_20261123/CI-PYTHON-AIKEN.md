# Portable native compiler dependency for Python CI

**PRE-PUBLICATION QUALIFICATION RECORD; NOT READY.** Non-author review
accepted the native-compiler repair and focused native evidence. The final clean-source metadata correction below was independently
accepted by the fresh GPT-6.2 Astra High reviewer.
This record was
prepared locally before fresh publication authority; final-commit scans and
hosted verification are separate evidence. The previous task's single push
was consumed. Local qualification grants no additional publication authority.

## Established defect

Hosted run [45124771304](https://github.com/GodOfAgents/VAMS/actions/runs/45124771304)
on `01c7d5962c98330595a7f90226c0c642c88dba5a` fixed the earlier audit,
credential and Python-collection blockers. Python then executed 3,604
selected tests: 3,601 passed, two failed, one existing skip, nine existing
deselections and 5,603 subtests. The separate design command did not execute
after the first command failed.

Both new failures occur when active historical tests spawn the workstation
path `/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken`:

- `docs/remediation/m3_2b_r4/test_mutation_harness.py::MutationHarnessTests::test_binding_guard_removal_is_rejected`
- `docs/remediation/m3_2b_r6/test_binding_guard.py::BindingGuardTests::test_guard_removal_mutation_fails_closed`

They call the real compiled-mutation harness. Their assertions are still
applicable and remain active. The local broad run had that approved tool
installed, which masked the undeclared hosted-job dependency. This is not a
new historical-test retirement and does not justify mocking native results.

## Small compatible repair

The Python job uses the same existing commit-pinned Aiken setup action and
release `v1.1.21` as the Cardano job. Before pytest, Bash requires a successful
tool lookup and absolute executable file, verifies the reviewed SHA-256
before executing it, checks the exact version, and exports the selected
`VAMS_AIKEN_BIN`. Both pytest commands remain unchanged. The two test modules
use that explicit path, preserving the approved local default only if the
variable is unset. Empty and relative explicit paths fail rather than fall
back. The native compiler/evaluator calls and every original test assertion
remain unchanged.

The existing pinned [setup action source](https://github.com/aiken-lang/setup-aiken/blob/1728a4be43be099752e22d8b841706caaa6fdd88/src/main.js)
selects `aiken-x86_64-unknown-linux-musl.tar.gz` on x64 Linux. The retained
[release verification](../m3_1a_r1/REVIEW.md) binds the official archive
SHA-256 `9fe0bb94efbb79f4d351664def3da0d58c7e30716fcb65590ff9b6c6b0ffb715`
to executable SHA-256
`07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`
and version `aiken v1.1.21+42babe5`. The already installed approved executable
was independently hashed and queried for `--version`, matching that record.
No new provider or tool version is introduced. The checksum is enforced,
not merely logged.

Native regression builds operate on fresh tracked `cardano/` source with
no copied ignored package cache. Their ordinary dependency resolution must
obtain the two official dependencies at the commits pinned in `aiken.toml`
and `aiken.lock`, through the already authorized setup/cache policy. The
separate Aiken job does not prove that the Python job has those dependencies.
The actual two cases passed on fresh tracked project inputs as recorded
below. The runner inherited its user home, so this is a clean project cache,
not proof of cold global-cache retrieval or GitHub network behavior.

## Review and verification bindings

Parent: `01c7d5962c98330595a7f90226c0c642c88dba5a`.
Accepted six-code-file tree: `d12f3c8a07fc0faa02c2cce57269cef07b58c760`.
Exact source hashes and separate raw streams are retained in
`.tmp-history-tests/ci-python-aiken-20261123-01/CANDIDATE.json` and
`source-reviewed-checks.json`.

`python -m pytest -q --tb=short scripts/audit/test_workflow_security.py
scripts/audit/test_ci_entrypoints.py` passed **36 tests and 78 subtests**
on Python 3.12.16. Configuration imports exercise explicit absolute paths
with spaces, unset defaults, and invalid explicit values in clean processes.
Those tests do not execute the placeholder compiler path.

The workflow regressions reject removed/mutable/skipped/nonblocking setup,
reordered dependencies, altered digests/version checks, masked lookup exits,
lost exports, skipped tests and swallowed test failures. Two actual Bash
negative probes prove that a wrong-hash executable is rejected without
invocation and that a missing compiler cannot use an inherited override.
They produce no synthetic native acceptance evidence.

GPT-6.2 Astra High, the same independent non-author reviewer, matched all
six hashes and the staged tree and accepted the source for local integration.
Its review is source evidence, not human/operator or native qualification.

The existing hosted Aiken batch finished first, passing all 904 native tests
on the published parent (897 unit, seven property, zero failures). The local
follow-up batch then executed both unchanged cases with the exact approved
compiler selected through `/tmp/vams reviewed native compiler 30ltdje1/aiken`.
It passed **2/2 in 34.37s**, exit 0, empty stderr, with no project-local
`build/packages` at launch. TOML SHA-256 was
`0520b42b48f051b1850f8143cdb9d2a7e7532d88ebac3c1b2ae7073332bac23a`;
lock SHA-256 was
`7c69f0a484d3b42862dc0ab0773cf6b3edf72709c921b2ad3648a0753af8cafc`.
The non-author reviewer independently matched those inputs, all six source
hashes, the staged tree, raw native output and successful actual workflow
bootstrap. Its focused native evidence decision was ACCEPT. The combined
full profile separately passed **3,609 tests and 5,625 subtests**, with one
existing skip, nine existing deselections and one TLS-version deprecation
warning. The separate design command passed **ten tests**. The exact original
CI pytest commands were retained, using pytest 9.1.1, pytest-asyncio 1.4.0,
anyio 4.14.2, the approved Aiken compiler and checksum-verified Envoy 1.39.1.
The literal workflow bootstrap was executed successfully against the verified
compiler through a path with spaces before that full run. No counts are
combined across runs. The full audit unittest suite separately passed
**247 tests**, exit 0. Raw stdout, stderr, exits and the six-file source
binding are retained in `combined-profile.json` and its per-command files.
There was no automatic native retry and no new push authorization.

## Gate and invariant impact

The completed run's uploaded audit manifest also records `dirty: true`.
Its current-commit binding is `01c7d5962c98330595a7f90226c0c642c88dba5a`;
artifact `14796218359` is retained locally under the first execution record.
No signed artifact or failing job is relabelled as accepted evidence.

Two clean-source defects require correction before another hosted run:

- Four retained F05 Python evidence tools have an LF/CRLF trailing blank
  line in their committed blobs. Their working bytes match those blobs
  exactly, yet the blanket `*.py text eol=lf` policy reports them modified.
  Four exact `-text diff` entries preserve their bytes and textual patches.
  No historical script, scanner rule or ignore entry is changed. Git's
  [attribute documentation](https://git-scm.com/docs/gitattributes) distinguishes
  line-ending conversion from textual diff generation; these settings retain
  the latter and disable only conversion for those four paths.
- Readiness downloaded generated signed evidence into the source checkout,
  although the gate correctly rejects untracked files. The download now
  targets the runner temporary directory. Cosign and readiness consume the
  identical explicit files there, with the same issuer/identity checks.
  The source-cleanliness check, signatures and all stage requirements remain
  mandatory. No generated-evidence directory is ignored to hide source state.

The unmodified manifest generator is exercised against private real Git
repositories. Old policy reproduces the false dirty flag; the corrected
policy produces a clean fresh clone with identical source bytes. Byte and
line-ending edits remain dirty and produce text patches, untracked source
and in-checkout evidence remain visible, and other Python files retain LF
normalization. External generated evidence does not hide actual source edits.
Workflow mutations reject in-checkout downloads, skipped signature checks,
or mismatched verification/consumption paths. The first metadata check passed
**39 tests and 91 subtests**; full final-source qualification is recorded
separately when complete.

The earlier native repair was committed locally as
`c47b9cfe5f35638e4606f80266879da94fc82a29`, tree
`0c6b9db4b54cc2053cf1e337e5a769767709b749`. It remains unpublished. Its
post-commit guard caught Git's filter-only status differences; raw-byte
comparison established that no historical source bytes had changed, and
the attempted cleanup stopped before writing anything. There is no amend,
reset, rebase or history rewrite: the metadata correction is a separate
normal local commit after qualification. The earlier review worker exhausted credits before this correction. The
owner then confirmed restored credits and explicitly authorized one fresh
GPT-6.2 Astra High review. That reviewer independently matched all ten source
hashes, the staged tree, historical bytes, real Git regressions and artifact
bindings, and accepted tree `41af541dbefbb6207311310836f5fd2e251066bd` for local
commit/integration. No exhausted worker was retried without instruction;
source review grants no additional publication or deployment authority.

INV-1 through INV-10 enforcement, production validators and the compiled
mutation harness remain unchanged. The production provenance verifier and
all nine exact pytest deselections remain unchanged. No runtime mock mode,
skip, xfail, compiler/evaluator stub or acceptance-policy exception is added.
The existing script-mode dashboard AST skip remains visible.

This repairs a CI dependency while retaining its native security tests.
It does not accept testnet admission, close an audit finding, authorize
R28/Slot 08 qualification, establish privacy/custody/provider evidence,
or grant deployment authority. Both-chain readiness remains NOT READY.


## Final combined-source qualification

The final combined profile on source tree `41af541dbefbb6207311310836f5fd2e251066bd` passed **3,616 tests and 5,646 subtests**, with 1 existing skip and 9 existing deselections. The separate design command passed **10 tests**, and the audit unittest command passed **254 tests**. All four commands, including the literal compiler bootstrap, exited 0. These are separate runs; their counts are not added.

The final functional source matches the reviewed eight code/configuration paths. This documentation update records the observed results; final policy checks and exact-commit secret scans remain separate receipts. The actual clean-source emitter and all signature/stage checks remain unchanged. Hosted verification still requires a fresh authorized publication; both-chain readiness remains NOT READY.
