# Synchronized repair and local qualification — 2026-11-12/13

The full A–G program still covers Polygon Amoy and Cardano Pre-Prod. This is
engineering evidence, not admission, deployment authorization or independent
assurance. The authoritative finding/control records have not been promoted:
13 findings remain open and 0/36 tracks are verified. Readiness is NOT READY.

## Source reconciliation and repair

The November 11 synchronization retained Windows preimages and separate
unintegrated candidates. On November 12 the canonical WSL branch was
`remediation/phase1` at `0ac74866c841b5eee60e43aaeb9550944a1d1304`.
Its additional review document was copied to Windows. The selected source
manifest has 4,172 paths; Windows AGENTS 3.1, dependency worktrees, generated
caches and archived candidates have explicit separate treatment. This does
not assert that every file in the two workspace directories is identical.

The real Python product run exposed six failures. Two communication tests
used the real AuditLogger against a read-only source-relative audit.log.
Four replay tests failed when spawning a worker after imports inserted the
package directory into sys.path. Correcting twelve legacy test import/patch
targets and giving communication fixtures a private temporary working
directory fixed the logging failures, but the combined suite still found
four spawn failures. The remaining producer was neuron.demo_cli itself.

The demo now uses relative package imports. Direct-script invocation performs
the repository-root PEP 366 bootstrap; ordinary package import leaves the
import path unchanged. Its runtime/demo guards and effect behavior are
unchanged. A real nested-spawn regression observes path, environment, working
directory and package origins. Two real external-directory help invocations
cover module and direct-script execution. No assertion, live guard, test
scope or owner-approved deselection was relaxed.

All fourteen repair files were integrated in both roots with twenty-eight
preimages and a flushed write journal. Independent source review and a
separate integration/evidence review are retained. The source manifest after
integration is SHA-256
`060b143629faf00b1f654d9bcce52f90062df4f15a0888ca191edb2b83f08102`.
The WSL changes are working-tree changes after the stated commit, not a new
committed release. INV-1 through INV-10 enforcement, economic parameters,
wire domains, restricted disablements and live authority remain unchanged.

## Executed evidence

Local receipts are retained under
`VAMS-qualification-20261112-01/` at the Windows workspace root. Receipts bind
commands, source/tool hashes, environment, raw streams, actual exits,
timeouts and before/after hashes. Terminal capture and validation success
alone never mean the application gate passed.

| Receipt | Actual result | Scope and limits |
|---|---|---|
| SOLIDITY-BASELINE-01.json | 1,167 passed; 0 failed/skipped; 73 suites | Synchronized Windows primary source, offline solc 0.8.24, Forge 1.7.1, fuzz runs 256, FFI disabled. 2,697 existing WSL dependency files and three gitlink commits independently bound. These are not the older Windows dependency folders. Contracts were unchanged by the Python repair. |
| PYTHON-PRODUCT-02.json | 2,781 passed; 6 failed; 1 skipped | Original actual-module Python 3.12 product baseline. 4,214 subtests passed separately. |
| PYTHON-PRODUCT-AFTER-01.json | 2,783 passed; 4 failed; 1 skipped | Test-isolation repair alone did not fix demo import pollution. |
| PYTHON-IMPORT-FOCUSED-02.json | 222 passed; 0 failed/skipped | Reviewed fourteen-file candidate, actual spawn, package imports and M1 entrypoint containment. |
| PYTHON-SYNCHRONIZED-01.json | 2,789 passed; 0 failed; 1 skipped; 4,214 subtests passed | Full neuron/tests on integrated, synchronized source, Python 3.12.16/pytest 9.1.1. All 4,172 selected source hashes unchanged before/after. |
| WINDOWS-IGNORE-REPROOF-01.json | exit 0; 638 accepted fingerprints re-proven | Windows Python 3.14.7 source-only reproof; not a fresh secret scan, full-history scan or CI Python 3.12 result. |
| CARDANO-SYNCHRONIZED-01.json | 600-second timeout, exit -9; no completed test result | Pinned Aiken 1.1.21 and 55 cached dependency files. Project/dependencies compiled; output stopped at test-scenario collection. Owned process reaped, source and lock unchanged. This is not an Aiken PASS. |
| FRONTEND-SYNCHRONIZED-01.json and FRONTEND-REVALIDATION-01.json | All four commands exit 0; 4 tests passed; lint/build passed; scan passed over 9 fresh files and 7 patterns | Existing Linux dependency bytes, Node 22.23.4/npm 10.9.9, private copy of 22 source files. Original receipt parser incorrectly expected eight patterns; independent source/raw-stream review and a separate strict revalidation establish the seven-pattern local result. Original invalid receipt is preserved. npm ci, fresh audits and browser/wallet journeys remain unrun. Private dist was not exported as a release artifact. |
| RUST-SYNCHRONIZED-01.json | fmt/check/Clippy exit 0; 69 tests passed in 7 suites; 0 failed/ignored/filtered | Rust 1.92.0, six local workspace crates, --locked and offline checks/tests, private empty Cargo home and target. Source and lock unchanged. Advisory audit and full compiler/sysroot provenance remain separate. |
| CONSENT-RUNTIME-MEASURE-01.json | 4 passed; 0 failed/skipped | Two actual differently configured instances per class; deployed/compiled Keccak and SHA-256 agree. All four existing class pins match the current build; none was changed. |
| CONSENT-FOCUSED-CURRENT-01.json | 28 passed in 3 suites; 0 failed/skipped | Real consumer/producer/policy/timelock/router and full cryptographic signatures; custody/challenge and initial records are synthetic fixtures. |
| CONSENT-COMBINED-CANDIDATE-01.json | 1,199 passed in 77 suites; 0 failed/skipped | Candidate adds the 28 consumer methods and 4 independent runtime measurements to the 1,167-method baseline; counts overlap and are not added again. |
| CONSENT-SIZES-CURRENT-01.json | exit 0; consumer runtime 21,247 bytes / creation 26,090 bytes | Test seed variants are 21,532/26,397 and 22,264/27,129. Existing ComposedSettlement is 24,401/31,165, only 175 bytes below the runtime ceiling. No size limit was changed. |

The 222 focused methods overlap the product suite. Counts from different
source states are not added. JUnit's event count includes subtests; it is
not the method count. The single product skip is the existing historical
dashboard AST change-scope comparator requiring an explicit frozen BASE.
No baseline was fabricated and no skip was retired. One TLS 1.1 deprecation
warning comes from an intentional negative ingress test. The private local
Envoy/Uvicorn checks are not independently observed external ingress evidence.

The supplementary original-demo regression captured two failures, but its
receipt metadata became invalid when a review file was moved out of the
candidate directory. It is preserved as a diagnostic and is not an accepted
gate. The runner was corrected to pin the exact fourteen-file manifest and
retain raw application streams even when report validation fails.

Key immutable receipt SHA-256 values:

- SOLIDITY-BASELINE-01.json:
  `41b6fc02086425ba011696f7df23c13fb8762776d372a48d1f87dc38dc1cc1b1`.
- PYTHON-SYNCHRONIZED-01.json:
  `7841d3828e94e89fca4824e62a6767fcfd9a0110b7464ad250c40de1a83e0eac`.
- Non-author implementation review:
  `bb7c567da2db0256f636d3eca61cb4f90707fb648be0be75cce40f2d2e4211ad`.
- Integration/evidence review:
  `bc866fed1ad83fe6aac0820f20993b511d1be96f8bfaf5d09fcfa4956ceb3cd8`.
- CARDANO-SYNCHRONIZED-01.json:
  `d564661345a73153d5719d2356c0bc87ed38f9b2c7485a3e8a9cc199ab440f6a`.
- FRONTEND-REVALIDATION-01.json:
  `66d22c3b9529687501ffb0de8204611a30b12eaae80fb5682542c8bbe72cb83a`.
- RUST-SYNCHRONIZED-01.json:
  `c70a839eb0246d897e42d6f9696c459e9f05ec9dc456c1cc5d3c19b41c4fff32`.
- CONSENT-COMBINED-CANDIDATE-01.json:
  `c577a70992998b330978725029645ac0c8a12fff4265321c6838f563a2226636`.
- Its Windows before/after archive-verification parent:
  `566377f8e520bf52e4c55ad6f92d46a5643ff4c9e5b72610c8ced7599aad8cd4`.
- CONSENT-SIZES-CURRENT-01.json:
  `76c0601e5166398f19a879634c5e742430a9118127dda00e58346a3aeec604d9`.

## Scope still outstanding

The product command is not the two complete repository pytest commands from
CI and does not include native PostgreSQL qualification. Owner-operated WSL
is approved by owner decision D1, but it is not independent hosted CI. D1-A
authorizes canonical Aiken 1.1.21 check/build/test; original R28 and Slot 08
remain excluded. Historical text saying all Aiken use is unauthorized is not
the current authority. No new install or download was used for this repair.

Full pytest preflight located two active native mutation tests. Their helper
compared a current-source mutant against a retained original blueprint, and
the two test methods did not require a valid positive control. A separate
unintegrated repair prepares fresh original/mutant builds, stronger controls,
bounded evaluation and cleanup tests. It is not native evidence or permission
to run noncanonical mutation campaigns. The specific native scope, complete
raw child transcripts and reviewed source/tool/cache bindings must be settled
before the full commands run. No extra deselection or historical retirement
has been added; no original R28/Slot 08 call was established by the bounded
source audit.

The separate V3 consumer preserves V2 consent/V1 principal bytes. It binds
the current authority-source digest to its own registry instance and code,
revalidates authority and policy in the synchronous timelock callback, and
performs generation/nonce compare-and-set atomically. Normal rotation needs
OLD and NEW body keys; recovery needs NEW consent and the observed 48-hour
governance delay. Callback failure rolls back the principal and operation;
cross-version and foreign-registry digests reject. No production enrollment
entrypoint exists: an empty slot rejects, while test-only seed contracts
provide initial records for these local tests. Initial enrollment, authenticated
migration/cutover and the Cardano counterpart remain required.

Authentic DCAP/EZKL identities and evidence, bridge qualification, independent
Mocha/Near exact-byte observers, deployment custody and privacy/security
acceptance are not supplied by these tests. The consumer remains inactive.
Candidate checks do not substitute for the required combined checks after
canonical integration, independent assurance or deployment acceptance.

The Windows-only routed frontend's fifty files were preserved separately,
byte-for-byte, rather than mixed into canonical source. Other local frontend
environment/browser work remains preserved and excluded by the explicit
qualification source manifest. Existing dependency metadata and native files
were inspected; npm ci, fresh dependency audits and actual browser/wallet
journeys remain separate gates. Full final-source scanners, signed release
evidence, both-chain rehearsals and actual seven-/fourteen-day observation
remain required. No repair-stage pass closes a finding or admits a canary.
