# Sentinel local publication and runtime continuity

Date:2026-11-01. Prepared source, pending guarded integration/canonical checks.
Existing R3/F09/F15/T04/T15/T28/T33/T35 delivery links; no gate promotion.

## Defect and repair

The prior _submit_sla_report read registry.web3, logged completion and returned
normally despite all transaction code being comments. audit_node then returned
True. Exception paths could returnNone and a truthy string/integer DA success
could be accepted. Runtime was checked only at construction, allowing a local
node to probe/publish/schedule after its effective mode/mock configuration changed.

The placeholder now raises a fixed unavailable error before SDK/key/signing/
broadcast access. Requested or partial SLA config returnsFalse through audit_node;
no SLA config preserves explicitTrue local-publication status. Publication is no
longer called a blockchain anchor. Strict `is True` rejects truthy non-booleans;
ordinary failure paths returnFalse, including malformed node input. Probe/DA
exception diagnostics omit raw backend payloads; this is not full log privacy.

The same source Mapping passed to the constructor is retained by reference
(default os.environ) as an immutable configuration field. Current policy and mock
selection must equal startup values before probe/publication/scheduling and after
awaited work. The scheduler stops on continuity failure. Explicit custom mappings
keep their injection semantics; no unrelated global mapping silently replaces
them. This does not authenticate native host policy/root/epoch/issuer custody.

Publication may already exist before a laterFalse result. This bool proves neither
native receipt nor absence and authorizes no automatic retry. No reconciliation,
exactly-once, chain finality or operator independence is claimed. The README now
describes local benchmark algorithms, simulated latency and unavailable slashing.

## Source evidence

SENTINEL-37-BEFORE-LINUX:15tests,12failures/2errors/1pass against old source;
regressions expose false success, missing guards and failure-return problems.
Original tests/source/outputs remain; the scheduler fixture was subsequently
completed with its local random source and task close guard. Candidate02passes
19tests,0fail/error/skip under pinned Linux Python 3.14.4.
The prior 15 candidate cases are
INCLUDED;4additional constructor/immutable/publication-drift tests. Actual Sentinel
methods run against7closed SDK/DA/challenge import seams and explicit AsyncMock
counters.38LinuxAF_UNIX event-loop socket objects are permitted;0other network,
process or forbidden-dependency construction events. No provider/hardware work,
actual SDK, signing, broadcasting or authentic DA receipt was executed.

The Windows before attempt failed during asyncio event-loop setup (15socket audit
events blocked). It is not defect reproduction or external provider evidence.
Its original worker/runner are archived. Linux uses an unshared network, read-only
worker root and private temp space, with45s parent timeout. ExplicitCPU/memory
quotas are not established. Existing12Sentinel pytest cases were NOT_RUN in these
controlled-import campaigns; real dependency-complete/full frozen CI remains.

Fresh separate full Solidity source results:892tests/53suites,0fail/skip; full
offline build--sizes exits0. ComposedSettlement16880runtime/18169init bytes;
RestrictedTestnetPolicyV1 9982runtime/17322init bytes. Source/tool/raw commands and
hashes retained as OBJECT-GRANT-CURRENT-FULL-37 and CURRENT-SIZES-37. These tests
include3new ABI cases and prior889, not892+889. This Sentinel slice changes no
contract bytes; final capture must verify those bindings still match. Not full CI,
authentic proof qualification or independent custody/security assurance.

## Invariants, privacy and uncompleted objective

All INV1-10 economic/oracle/supply/reward/session/OMS/root-TEE/bridge controls stay.
Scores remain observational. No slashing/reward activation, new minter, governance
role, change to48hours, storage migration, contract deployment or live factory.
Deposit/Slash activation/ExecuteIntent/fiat/yield/rewards/minter/ordinary governor/
vesting/buyback/delegation restrictions remain. This repairs an existing disabled
placeholder's misleading outcome; it does not implement the required authentic
Sentinel/SLA transaction and independent operational proof path.

No environment values are copied, serialized or logged by the new retained
Mapping field, but the reference can expose the same ambient configuration in
memory/debuggers. Existing registry/operator/key/address/report/DA fields and
other debug/scheduler/telemetry logs remain subject to the pending complete
privacy review. The15source/214slot/16flow effect inventory is not complete
Sentinel/SDK/project privacy coverage or approval.

The fixed hardware/verifier/workload/provider/observer/native runner/custody/
privacy/security identifiers remainUNKNOWN. Authenticated native current policy,
real PG/fencing/recovery/effect/settlement, DCAP/EZKL/bridge/DA retrieval, full
scanners/frontend/ingress/wallet, human assurance/rehearsals and both-chain gates
remain.724governance/35Rust/36Aiken cases stayNOT_RUN. No R28/Slot08/Aiken,
install/acquisition/provider contact/deploy/sign/fund/role action occurred. Actual
7closed-canary and14public observation days remain required. A--G NOT READY.
