# Local scan and non-author review record (2026-11-25)

Status: **LOCAL ENGINEERING EVIDENCE ONLY. F13 REVALIDATED_OPEN; NOT READY.**
No deployment, funding, live probe, parameter change, push or hosted-CI dispatch.
Thirteen findings remain open; zero of 36 tracks accepted.

## Scope and reviewer

The original scope is `d0bb4c513553f8869473cc8c11bca16b91c5cc88..685b289c8d75099db7f3145bfc0e6384f57ab5bc`:
`aaebb25`, `f91a933`, `b631f67`, `5ccc5ed`, `685b289` (18 changed paths).
The separate GPT-6 Luna High agent `/root/review_five_commits` reviewed committed
blobs read-only, then the bounded replacements. It did not author these changes
or run the checks. Its full report and follow-ups are retained at
`C:/Users/aseem/VAMS-mono/.tmp-history-tests/f13-local-scan-review-20261125-01/NON-AUTHOR-REVIEW.md`; final report/source/commit hashes are in the external
`FINAL.json` receipt. This is non-author AI source review, not authenticated
human custody, cryptographic, privacy, operator or release assurance.

No contract defect was confirmed. Review exposed stale acceptance wording,
missing failure/interleaving coverage, and ambiguities in the draft memory
specification. The follow-up adds three local fault-injection tests, strengthens
slot reuse and mixed-operation fuzz, records criterion coverage/limits, and
clarifies existing memory-policy, consolidation, restart and observer duties.
The wire codec remains an explicitly incomplete proposal requiring a separate
review before protocol use. No new codec or memory runtime was implemented.

## Source and configuration binding

Committed source was exported independently of the dirty canonical checkout.
`SNAPSHOT.json`, `source-manifest.json`, `NATIVE-SNAPSHOT.json` and
`native-dependency-manifest.json` retain exact commits, source and 2,697 dependency
file hashes. The fixed native checks use that baseline plus the explicit
replacement hashes in `FIXED-GATES.json`. Production dispute-contract SHA-256:
`15f7a070095659093b18c9d27fce70b520fd59b888756e20ea30cd1b4bda2fa5`.
Strengthened test-file SHA-256: `f6efe8dcffaee02bccf21557703b48bd31da27040c122badebcac0a26df9dda0`.

The final local integration verifies unchanged production/compiler inputs and
rechecks the final documentation/math/links. At preparation time, history secret scans for the post-integration commit are
PENDING; their later results belong in the external FINAL.json receipt. No final-range
PASS is claimed by this preparation record. Do not
relabel baseline counts as new final-commit executions or combine test totals.

## Executed local checks

Exact arguments, working directories, raw stream hashes and exits are in
`NATIVE-GATES.json`, `FIXED-GATES.json`, `FIXED-AUDIT.json`, `GITLEAKS.json`, and
the final receipt under `C:/Users/aseem/VAMS-mono/.tmp-history-tests/f13-local-scan-review-20261125-01/`. All heavy checks were serialized.

| Check | Actual result and scope |
|---|---|
| Gitleaks 8.30.1 | Five original commit patches, 5 observed commits / 104,305 bytes, exit 0, 0 findings; redaction enabled; post-integration scan PENDING at preparation |
| TruffleHog 3.95.9 | Local Git range, all result categories, verification/update disabled, exit 0, 0 findings, 0 malformed events; raw candidate values never retained |
| Slither 0.11.5 | CI severity flags, exit 0; 88 results: 60 Medium, 28 Optimization, 0 High, none in DeliveryDisputeV1; zero normalized differences between original and fixed-source reports |
| Semgrep 1.169.0 | Reviewed local rules, metrics/version checks off, exit 0, 0 findings/errors; rule fixtures 12/12 pass |
| Bandit 1.9.4 | CI neuron/gateway scope and the new math verifier, -ll -ii, each exit 0 / no findings |
| Foundry 1.7.1 | Original committed source: 1,287 passes; fixed contract/test inputs: 1,290 passes in 89 suites, 0 failures/skips; the earlier count is included, not added |
| Focused floor/cap suite | 11 methods pass at 2,000 fuzz runs, 0 failures/skips; bounded synthetic fixtures only |
| Sizes | ComposedSettlement runtime/initcode 24,401/31,499 B; DeliveryDisputeV1 5,192/5,625 B; settlement runtime margin 175 B |
| Python/documentation | Seven offline mathematical/source groups, two documentation tests and 257 audit tests pass; these unit tests do not accept audit tracks |

The exact size output requested by design criterion 7 is
`C:/Users/aseem/VAMS-mono/.tmp-history-tests/f13-local-scan-review-20261125-01/fixed-sizes.stdout`, SHA-256 `bf81924c67c8ddd5d44b44fbc56fe6269756dfd006d623462ee17166c32ee058`.
Its command is `/home/GodOfAgents/.vams-tools/bin/forge build --sizes --offline`
in `/home/GodOfAgents/vams-local-review-20261125-01/scan-source/contracts`.
The source/overlay/dependency identities and output hash are recorded above;
this is local compiler evidence, not deployment qualification.

Existing Slither Medium/Optimization results are not newly adjudicated by an
exit-0 result. The full release workflow, authenticated evidence and all stage
acceptance remain pending. No Aiken/frontend/dependency changes were made;
Aiken, frontend and online dependency feeds were not rerun. Offline Semgrep
discovery and complete pre-baseline Git history were not rescanned here.

## Failed harness attempts retained

- Initial Windows Gitleaks exited 0 but scanned 0 commits because its Git child
  failed. That result is **rejected**. The accepted invocation uses isolated
  process-only Git configuration and proves 5-commit coverage; no global Git
  configuration or scanner allowlist was changed.
- The initial Semgrep fixture invocation exited 127 because its binary was
  missing from PATH. The explicit pinned binary invocation passed 12/12.
- Audit tests in the plain compiler copy failed without Git metadata. A rerun
  with Git but a different PATH failed Python lookup in a fixture. With both
  required Git context and the original installed Python PATH, all 257 passed.
  Every failure remains retained, with no skip, assertion or threshold changes.
- Final compiler/scanner runs use a plain local source copy with Git network
  transports disabled. The earlier Git-clone harness emitted missing-submodule
  auto-install warnings; they are retained and are not acquisition evidence.

## Invariants, limits and next work

INV-1 through INV-8 and INV-10 enforcement is unchanged. INV-9-adjacent escrow
and bond accounting has stronger synthetic rollback/interleaving coverage;
neither that nor a source review proves authentic proof settlement or custody.
The approved 72-hour/14-day windows, 500 bps, 1-VAMS floor and 20-open cap are
unchanged. Original dirty changelog/payment-ledger/.codex work is preserved.

Authentic F06/F07 evidence, real resolver custody, authorized measurement with
reviewed operating limits, independent release assurance, both-chain gates and
actual observation time remain required. F13 stays **REVALIDATED_OPEN** and
readiness **NOT READY**. No local PASS in this record promotes a track or stage.
