# M3.2a-R21 FIFO probe-harness remediation

Date: 2026-09-27
Branch: testnet/remediation-20260907
HEAD: 829ab544571f12efe50ecb5740f129c8acb3e16f
Origin: https://github.com/GodOfAgents/VAMS.git

## Scope and prerequisite

R21 remediates only the independent R20 test-boundary defect. The R20
SHA256SUMS manifest was verified as
7aa2e8bab8b50495bd9db825ec9a4892b634ae80669c19af6c2c0408109d6ad3 and every
listed file passed sha256sum -c. Origin, branch, HEAD, recursive submodules and
the existing 114 dirty paths were recorded before editing. No network,
installation, fetch, deployment, credential, vendor, dependency, or Git
history operation was used.

## Pre-fix reproduction

A disposable pathname-reopen mutation replaced the fixed descriptor loader
with Path.read_bytes() and was exercised against a no-writer FIFO. The
independent outer timeout returned PRE_FIX_PATHNAME_REOPEN_EXIT:124 after
three seconds. This reproduces R20's unbounded direct-parent-loop defect
without changing the authoritative source or artifacts.

## Remediation

docs/remediation/m3_2a_r19/test_r19_oracle.py now uses one reusable
_run_fifo_probe harness for every repeated FIFO failure-path and mutation.
Each probe starts a fresh process group, creates its own temporary tree and
FIFO in the child, invokes exactly one selected source or mutation, and emits
only structured status (oracle_error, success, exception, or parent timeout); controlled rejection exits nonzero and regular success exits zero.
A one-second hard deadline is enforced by the parent. Timeout cleanup sends
SIGTERM, waits 0.5 seconds, sends SIGKILL if required, reaps the child, checks
ps for remaining process-group/session members, removes the parent-owned
temporary tree, and compares parent descriptor counts before and after.

The harness runs three fresh iterations for each control: fixed no-writer
FIFO rejection, writer-present FIFO rejection with sentinel bytes remaining
unconsumed, regular-file success, removal of O_NONBLOCK (detected timeout),
and pathname-reopen (detected timeout). A timeout is a successful mutation
detection but a fixed implementation timeout, unexpected mutation success,
cleanup failure, remaining process, descriptor growth, or undeleted temporary
path fails the test. The harness does not use production registry/FIFO
helpers to classify the outcome.

## Verification

- Focused R21/R19 oracle harness: 10/10, exit 0.
- R19 mutation harness: 1/1, exit 0.
- R17 suite: 6/6, exit 0.
- Complete oracle suite: 10/10, exit 0.
- Governance suite: 12/12, exit 0.
- Provenance suite: 20/20, exit 0.
- Repeated child/process cleanup probes: included in the 10 focused tests;
  all iterations reported zero remaining processes, removed temporary paths,
  and unchanged parent descriptor counts.
- Two isolated offline Aiken 1.1.21 verifier runs: both ok=true,
  check_exit=0, build_exit=0, source manifest
  d255e13f04d2e27b595430cc2decf532c38e0444c01488dbfb7f312edc3afa55, and
  blueprint 7b39b883cdc7b55aef08554e92cb089a4b3a91a6250138c4f0b181b37cfd0a80.
- In-memory Python compilation: IN_MEMORY_COMPILE_OK.
- JSON validation and documentation reads: passed.
- git diff --check: exit 0.
- Recursive submodule status and final dirty-path continuity: unchanged,
  114 paths.

## Continuity and status

Production oracle hash is unchanged:
docs/remediation/m3_2a_r9/address_value_oracle.py =
50211e76db54ceafd303f63d83c8aabfc914e0b98d2aef56cb5558e1a88bb95b.

Frozen inputs remain unchanged:

- cardano/aiken-dependency-manifest.json =
  2a3c6f6ce22607d3db5ef9a60f0e6b1423179f4d31e37361fc3682547e635b
- cardano/aiken.lock =
  bc314b0be1b25c2fe370bed39e0ecde3b15642f67614253a4b01cf2db746a15c
- cardano/plutus.json =
  7b39b883cdc7b55aef08554e92cb089a4b3a91a6250138c4f0b181b37cfd0a80
- cardano/validators/insurance_fund.ak =
  3762236d38359a75f45f7a1b2c5f16843fbd0b95ecdf478aa8e8f8c8511e0930
- cardano/lib/vams/types.ak =
  a963255e8227557a0a232aad153a41b658cbc9a3c80ce56bb65d4755c2ab9d34

F01-F05 remain open, Deposit remains disabled pending F05, M3 remains OPEN,
Pre-Prod admission remains INCONCLUSIVE, promotion remains NOT READY, and
M3.2b is not authorized. INV-1 through INV-10, production oracle behavior,
mock mode, manifest/provenance, Cardano sources, dependencies, deployment
state, credentials, vendors and Git history are unchanged.

This is local remediation evidence only. Next single slice: independent
M3.2a-R22 test-harness delta review.
