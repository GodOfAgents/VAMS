# Callback/lifecycle regressions and checkpoint repair

**Date:** 2026-11-14  
**Status:** Locally implemented/tested; bounded non-author source review; NOT READY

This supporting record follows the existing repair program. No authoritative
track, release gate, chain scope, owner decision or readiness status is promoted.

## Defect and design

Old StateCheckpointRegistryV2 (SHA-256
`5eeeccf789af16fd5e5608f22314e7fb507ffb5255ff8e195967c719b72f190f`)
left challenger-win disputes challenged and unfinalized after payout. An authorized
arbitrator could repeat resolution and drain bonds for two unrelated checkpoints.
The test funds both unrelated 50,000-token roots so insufficient balance cannot
mask replay. Each remains refundable after the rejected second payout.

Submission and challenge wrote their slot state after external ERC20 deposits.
A conventional local ERC20 with a one-shot callback could deposit twice into the
same logical slot, stranding an extra operator/challenger bond. No callback is
added to VAMSToken or any live path; this is an adversarial dependency test.

The repair consumes a separate per-root `disputeResolved` flag before either
payout. Invalidity remains distinct from successful finalization. SafeERC20
failure rolls consumption and validity back. A shared guard protects submit,
challenge, finalize and resolve; deposit effects precede interaction. The
50,000-token bond, two-bond payout, seven-day challenge window, inclusive challenge
deadline/strictly-later finalize, role policy and checkpoint tuple are preserved.
New source SHA-256:
`2f28a830e29d072480d33878354ae23b6ee58e8442534c0b0870d4a4249af852`.
The token is immutable; fee-on-transfer/malicious-token deployment is unqualified.

This source is not selected by the restricted deployment scripts. No existing
immutable deployment is upgraded, funded, enabled or repaired by the file change.
No economic feature, real slashing or arbitrator role is activated. INV-1 through
INV-10 enforcement is preserved; the additional local invariant is exact-once
bond settlement with remaining liabilities covered by retained balances.

## Requirement-to-evidence coverage

| Component | New methods | Proven local boundary |
| --- | ---: | --- |
| TwoPhaseCommitManager | 4 | Partial getters at each escrow call; nested initiation denial; current/prior service authorization; authorized callback abort compared with immediate abort; callback preparation followed by later failure/rollback; later commit or expiry/refund once |
| ComposedSettlement | 6 | Real ERC20 balance/allowance callbacks and bond acceptance/cancellation callbacks; actual-agent refund reentry; consumed-row visibility; second-row failures roll balances, liabilities and counters back; successful retry |
| Heartbeat V3 | 2 | Exact nested relay denial during active real timelock execution; caught normal commit once; uncaught recovery rollback/same signed proof retry; selector-sensitive inverse fixture oracle |
| StateCheckpointRegistryV2 | 13 | Missing/duplicate roots, deadlines, authorization, both arbitration outcomes, unrelated bond conservation, transfer failure/rollback/retry, same-root deposits and privileged payout callbacks |

Fixtures replace only external token/escrow/bond/custody/challenge boundaries.
Production contracts, timelocks, signatures, frames and getters under test are real.
Public fixture keys and balances are not custody or authentic provider evidence.
The authorized workflow-agent callback may abort during construction: all escrows
still register and refund after expiry, matching ordinary abort. No source change
was justified for that behavior; it is explicitly characterized rather than hidden
behind an unauthorized-caller assertion. Actual X402 escrow custody remains untested.

## Exact candidate and execution

Evidence directories under `C:/Users/aseem/VAMS-mono/`:

- E5 `VAMS-callback-lifecycle-20261113-05`: baseline, preimages, early tests/reviews,
  publisher, integration plan/receipt/journal and final local checks.
- E6/E7/E8 `VAMS-callback-lifecycle-20261113-06`, `-07`, `-08`: separate retained
  corrected baseline and test/compiler failures, never relabeled as passes.
- E9 `VAMS-callback-lifecycle-20261114-09`: final 242-file archive, offline native
  runner, actual gate/negative streams and final non-author source review.
- E10 `VAMS-callback-lifecycle-20261114-10`: same source archive, scanner runner,
  pinned inventory, raw scanner streams and JSON.
- E11 `VAMS-callback-lifecycle-20261114-11`: same source with corrected negative-test
  selector only; its runner SHA is distinct and source file map is unchanged.

| Binding | SHA-256 |
| --- | --- |
| E5 baseline (243 pre-change inputs/docs reconciled) | `0ec6cc92a334cdc0fd0ec356330683ef62b66d4a33ce3b2b45d16a0e8ff0a7b5` |
| E9 candidate manifest | `a9f7ece14346246a25ed36af50b8043bf3dfbf4c504638b5544bfe85fdd81416` |
| E9 source archive | `a263bbdb7fdf0fe78ec44c7404f1591353de3a09a9400e10531d1c8f5af6ac59` |
| E10 scanner manifest | `c2d7fc8758d75fe2703ccad287e1dea9bee3a30b78fd60e733e8b91f708f4202` |
| Fresh Slither report | `5b87d719566c1bda9764bca2a987715d48cc761701372c7f8b01293ecaa5ada5` |
| E5 regression coverage/review/gate map | `24959ba21f090f46d7540742bca073de9bf4977d42a8ce28c8adc5c1a426b09d` |

Canonical HEAD is `4f0f7887efb384e883b9de4d7c56387479e471a5`, dirty
`remediation/phase1`. Selected source is reconstructed from the archive plus
2,697 pinned dependency files in a private network-isolated bwrap namespace.
Foundry 1.7.1, solc 0.8.24 and installed scanner/tool inventories retain their
previous pinned byte identities. FFI is disabled, two threads, 256 fuzz cases,
seed `0x20261113`, 600-second bounds; only one heavy native job at a time.

| Executed E9 phase/label | Exit and actual result |
| --- | --- |
| `focused CALLBACK-FOCUSED-03` | 0; 38 passed/0 failed/skipped across 4 suites |
| `full CALLBACK-FULL-01` | 0; 1,267 passed/0 failed/skipped across 86 suites |
| `sizes CALLBACK-SIZES-01` | 0; warnings retained; checkpoint runtime 4,224 bytes; ComposedSettlement unchanged at24,401 (175 bytes EIP-170 headroom) |
| `before CALLBACK-BEFORE-03` | 1; 8 passed/5 failed against retained old checkpoint source; expected replay/deposit/payout callback failures |
| E11 `mutant-hb CALLBACK-HB-MUTANT-02` | 1; both new methods fail with only the relay guard removed in a private copy; source/canonical files unchanged |
| E10 `slither CALLBACK-SLITHER-01` | 0; 0 High, 60 Medium, 28 Optimization; unchanged config/exclusions, no new Medium IDs |

For example the completed full gate was invoked from PowerShell as:

```powershell
wsl -d Ubuntu -u GodOfAgents -- /usr/bin/python3.14 -I -S -B /mnt/c/Users/aseem/VAMS-mono/VAMS-callback-lifecycle-20261114-09/run_native.py full CALLBACK-FULL-01 a9f7ece14346246a25ed36af50b8043bf3dfbf4c504638b5544bfe85fdd81416
```

Labels are consumed evidence identities, not instructions to auto-resubmit them.
Every `.json` receipt records complete argv, environment, input/tool/dependency
hashes, deadline/exit, Git context and separate `.stdout`/`.stderr` hashes. Forge
stdout starts with exact inner argv; scanner base64 payload is decoded unchanged
and embedded report hash checked. No old/focused/negative counts are added to the
full count. Negative tests are expected failures, not gate passes.

E5 BEFORE-01 retained 7 passes/5 failures: four genuine failures plus one fixture
ordering mistake that let approve consume expectRevert. E6 BEFORE-02 corrected
that fixture and demonstrated 8 passes/4 genuine failures. E7 FOCUSED-01 executed
zero tests due a nonconstant test error selector. E8 FOCUSED-02 executed zero tests
due test-local stack pressure. Literal ABI selector and shorter local scopes fixed
only test code; no compiler flag, optimizer, limit or expected behavior was weakened.
The first E9 mutation attempt selected no tests because the filter matched bare
names rather than signatures; its exit0 is retained as NO_TESTS, not a pass or
negative-test proof. E11 corrects only that selector and executes both methods.

## Reviews, integration and residual boundaries

The final non-author source review is E9 `reviews/final-source.json`, SHA-256
`15a6dbfe43140a712a26d9aee5c1ed1194c0e9ed17406f7ebda0f1336e35112b`. It reviews the root-authored checkpoint fix and final
workflow tests against E9 hashes; the reviewer authored checkpoint tests and
excluded them. The primary separately inspected those test oracles and executed
BEFORE/AFTER evidence. Composed/Heartbeat tests and the corrected recovery oracle
have non-author review in E5 `reviews/settlement-heartbeat-followup.json`, SHA-256
`3901b894dab3d3bc59646ad144428071ffd320d22022f4b927df821567d0e26a`; those source/test hashes remain unchanged in E9.
Earlier reviewer concerns and compiler failures remain in their original records.
Two reviewers exhausted credits before final closeout; none was retried or replaced.
Requested worker model/effort was Luna/high; actual runtime identities are unexposed.

These are bounded non-author AI reviews, not whole-patch independent human assurance
or independent native execution. Authentic custody/DCAP/providers and real escrow
integration are not demonstrated. Positive transaction timestamps remain an explicit
existence-sentinel assumption; genesis-prepopulated/other deployment profiles are
not qualified. All 28 Optimization findings remain unadjudicated. Independent human
and hosted exact-source CI requirements, both-chain admission and actual observation
time remain governed by the existing authoritative gates.

Integration uses a ten-file allowlist, six retained existing canonical preimages,
four new targets, exact before/after hashes, path/symlink guards and an immutable
hash-bound plan. E5 `INTEGRATION-RECEIPT.json` and final assessment record actual
integration and 242-file candidate equality; the original dirty work is preserved.
Documentation and scoped secret checks are retained separately after integration.
Approved TOKENOMICS.md stays at `c2d9c0021a6548e163007cb57fcefa8416e5573db0f9729c86d17d68669701f8`.
Zero emissions/rewards, no staking minter and all economic/TEE/bridge disablements
are unchanged. No deployment, signature, funding, role, installation, acquisition,
provider call, Git commit/push or authoritative acceptance action occurred.
