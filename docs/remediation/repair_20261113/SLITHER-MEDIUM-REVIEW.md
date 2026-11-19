# Remaining Medium Slither review — 2026-11-13

This is supporting engineering evidence for the existing remediation program,
not a new acceptance ledger. Readiness remains **NOT READY**. No authoritative
audit-track status, both-chain scope or owner decision is changed.

## Scope and source

The Windows working mirror and canonical WSL checkout were compared against the
prior economic repair's 237 selected inputs before this slice. All matched.
Canonical checkout: `/home/GodOfAgents/code/VAMS-testnet`, branch
`remediation/phase1`, dirty, HEAD
`4f0f7887efb384e883b9de4d7c56387479e471a5`.

Evidence directories below are retained under `C:/Users/aseem/VAMS-mono/`:

- `VAMS-slither-medium-20261113-01/` (E1): baseline, frozen 239-file candidate,
  offline test/size runner, source review, integration plan/preimages/receipt.
- `VAMS-slither-medium-20261113-02/` (E2): same candidate archive and source map,
  pinned scanner inventory, runner, raw scanner streams and JSON report.

| Binding | SHA-256 |
| --- | --- |
| E1 `BASELINE.json` | `21b93e933c370ac04e063372ee98029b15b2389d3c9a0f9c158940d3ec973c54` |
| E1 `CANDIDATE.json` | `938ee1157ad1034ab37c3724d1c4a36c9d5b51b6193394b854ad9e43f7417631` |
| Candidate archive | `2663e638235a3f3b2da3af3433e8b593be0ca795759ad65ce093fcde0de5219c` |
| E2 `CANDIDATE.json` | `881b9ec38adbc430990231a89b18c3728fdafb3216c1de0fcbbdfd62a51a98c3` |
| E2 `slither-report.json` | `cfef7904096846ea43ef4c6830d36737501829010ce8cedf8601c315d9779233` |
| E1 `PRIMARY-SOURCE-REVIEW.json` | `fbd7f0317cdbfafe1b151dbc96563004570dfcbb3562ed8a3227a6b1f079f930` |

The source manifest includes all Solidity source/test/script files, Foundry and
Slither configuration, accepted owner decisions and restricted profile inputs.
There are 2,697 pinned dependency files. The scanner inventory binds 2,701
installed toolchain files. No tool was acquired or installed for this slice.
Each execution receipt separately binds tool and dependency hashes, command,
environment, timeout, Git context, raw stdout/stderr and exit status.

## Repair and invariant impact

The owner-tuple warning in `VAMSERC8004Adapter.verifyAndRegister` prompted review
of the following trust assignment. The adapter accepted `success` and
`report.mrenclave` without a qualified binding of report data to root EOA, agent,
action or freshness. A local adversarial verifier fixture can approve a quote
for another root and the pre-fix adapter records it. This is a genuine INV-6 gap,
not a defect in selecting only the owner from the registry tuple.

The entrypoint now always reverts `LegacyAttestationDisabled()` before any
external call. No replacement evidence format is invented. The ABI selector,
getters and admin configuration API remain, but cannot enable acceptance.
Existing immutable deployments need separately reviewed retirement/migration;
editing source does not change them. The independently versioned action-bound
DCAP verifier is untouched; authentic verifier/collateral and root-control
qualification remain required before live use.

Eleven additional test methods exercise the legacy disablement, privileged
cross-index callbacks, retry rollback after four dependency failure forms, and
well-formed wrong-signer completion/absence receipts through production verifier
and settlement code. Test keys 1/2/3, fixture roles and the synthetic slasher are
local evidence, not custody, authentic TEE or live operational evidence.

INV-6 is narrowed to fail closed. INV-1 through INV-5 and INV-7 through INV-10
retain their enforcement; no reward, fee, emission, cap, escrow, slashing or
governance parameter changes. Owner decision 4 remains: zero emissions/rewards,
no staking minter, vesting/buyback/reward distribution/delegation/slashing/token
governor inactive, and DEC floor/decay/tail frozen-unset.

## Executed gates

The bounded runners reconstruct the exact archive and dependencies in a private
temporary directory inside a network-isolated `bwrap` namespace. Canonical
source is read-only during tests. They use two threads, a 600-second deadline,
256 fuzz cases per fuzz method, seed `0x20261113`, offline compilation and no FFI.
Heavy jobs were serialized. Retained BEFORE failures were followed by a distinct
AFTER run; no uncertain one-shot submission was retried.

From Windows PowerShell, the common invocation was:

```powershell
wsl -d Ubuntu -u GodOfAgents -- /usr/bin/python3.14 -I -S -B /mnt/c/Users/aseem/VAMS-mono/VAMS-slither-medium-20261113-01/run_native.py full MEDIUM-FULL-01 938ee1157ad1034ab37c3724d1c4a36c9d5b51b6193394b854ad9e43f7417631
```

The other executed E1 phase/label pairs were `before MEDIUM-BEFORE-01`,
`focused MEDIUM-FOCUSED-01` and `sizes MEDIUM-SIZES-01`, with the same manifest
pin. Labels are single-use evidence identities; these are records of executed
commands, not instructions to resubmit them. Inner command prefixes and results:

| Gate | Command and result |
| --- | --- |
| BEFORE | `forge test -vvv --match-contract ^SlitherMediumLegacyAdapterTest$`; exit 1, 0 passed, 4 failed. Traces show wrong-root acceptance and failure to stop before dependency calls. Expected pre-fix regression failures. |
| Focused | `forge test -vvv` selecting adapter, retry and object-settlement suites; exit 0, 30 passed, 0 failed/skipped. |
| Full | `forge test -vvv`; exit 0, 1,242 passed in 83 suites, 0 failed/skipped. |
| Size | `forge build --sizes`; exit 0. Compiler/lint warnings retained. Adapter runtime 1,463 bytes. Unchanged ComposedSettlement runtime 24,401 bytes, only 175 bytes below EIP-170. |
| Slither | `slither . --config-file slither.config.json --exclude-dependencies --exclude-informational --exclude-low --fail-high --json /tmp/slither-report.json --compile-force-framework foundry`; exit 0, 0 High, 61 Medium, 28 Optimization. |

All Forge commands also use the exact pinned solc path, `--offline`, private
output/cache paths and `--threads 2`; the `actual_argv` line in each raw stdout
records the complete command. The E2 outer command uses its runner with
`slither MEDIUM-SLITHER-01` and the E2 manifest hash in the binding table.

Every label has separate `.intent.json`, `.json`, `.stdout` and `.stderr` files.
The E2 scanner payload was decoded without altering its bytes into
`scanner.stdout`, `scanner.stderr` and `slither-report.json`; its embedded report
hash was checked. `SCAN-RECONCILIATION.json` proves no new Medium identity:
the only removal is
`e23cc5ab05194f1562da8e6bbb92e12345e59f0423384bf455492e26eb9ae16a`.
The 61 current identities and unchanged source hashes are mapped individually
in `contracts/slither-adjudications.yml`; no detector rule/exclusion changed.

Python, frontend, Cardano and live integration gates were not rerun for this
Solidity-only slice. Their prior statuses and blockers remain separate; no old
pass is added to the current counts.

## Review, integration and acceptance

Primary source review covers all 62 baseline Medium findings: one underlying
trust defect fixed by retirement, 61 residual source dispositions. Optimization
findings remain unadjudicated. The prior grouped record's claim that all
TwoPhaseCommit callbacks are views was too broad and is corrected. Its token
proxy/immutable explanation was incorrect and is withdrawn.

Assigned Luna non-author workers stopped for credits/network permission before
delivering this slice. No retry, replacement model/provider or capacity purchase
was used. The primary authored the repair and regressions; its review is not
fresh independent acceptance. An independent reviewer must assess the repair,
tests and residual conditional trust assumptions before acceptance.

The source-only integration uses an exact eight-file allowlist, retained
canonical preimages, before/after hashes, path/symlink checks and a single-use
hash-bound plan. The resulting `INTEGRATION-RECEIPT.json` and retained journal
record completed integration and 239-file Windows/canonical equality. No Git
mutation, deployment, funding, role assignment or live provider call is part of
this helper. The final check compares the integrated source bytes directly
against the executed candidate; it does not rerun tests on changed bytes.

Both-chain admission, 36 audit tracks, external assurance, authentic custody,
provider/privacy evidence and real observation remain governed by their existing
canonical requirements. No readiness or gate status is promoted by this record.
