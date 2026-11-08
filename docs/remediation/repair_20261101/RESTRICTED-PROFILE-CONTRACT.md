# Selected testnet profile contract — source 41

This repair binds the existing restricted profile's configuration identity through
its audit and economic evidence consumers. It does not enforce deployed controls,
authenticate operators or accept any finding/track/readiness stage. Full A--G and
both Polygon Amoy/Cardano Pre-Prod remain required and NOT READY.

## Current source and defect

Baseline checkpoint40: HEAD829ab544571f12efe50ecb5740f129c8acb3e16f,
manifest e115e9a3c22fbbca4d4f5925838ec5e0ce577968e571ac4c0b2e4aa7a8ebf507,
6,728paths; PROFILE-INPUTS-41.json captures39 current inputs. Independent
remainder39 ABCG and source41 design review identified incomplete configuration
checks in audit_program.validate_program. Several selected profile restrictions
could change without error. Malformed checked sections could raise attribute/type
errors instead of returning diagnostics. economic_concentration.evaluate and the
synthetic campaign trusted caller-supplied profile thresholds directly.

## Repair and compatibility

restricted_profile_v1.validate_testnet_profile is one pure, dependency-free typed
contract for the selected profile_version1.0.0. It requires every selected field,
exact object keys/JSON types and current values: faucet-only, zero rewards/fiat/
yield, VDSO off, exposure100/1000bps, linked/top-four/HHI/regional2000/5000/.25/3000,
five-provider hardware-floor protection,3of5/48h governance and separate2of3
pause-only council,7closed/14public days. The expected nested mapping is immutable;
the caller's object is never mutated. Unknown/missing fields and bool/int/float/
string/null coercions reject. Diagnostics do not echo supplied values/unknown keys.

No profile JSON bytes, selected limit, formula, status or version is changed.
Some normative requirements are caps/minima. A stricter alternative (lower
exposure, longer timelock, more providers) can satisfy those general policies;
it is still not this selected v1 profile. Such a change requires an explicit
reviewed version, not silent reinterpretation of1.0.0 or a declaration it is unsafe.

audit_program delegates its profile branch to the shared contract. The direct
economic evaluator validates before snapshot access; the campaign validates before
RNG creation, profile serialization/hash or snapshot construction. Both package
and direct-script import forms are retained. Existing operators remain: linked
and top-four shares stop strictly above20%/50%, HHI stops at or above.25, and
regional rewards stop strictly above30%. No economic threshold is relaxed.

## Retained execution/review evidence

The first baseline5method run had an incorrect publisher-inventory data binding;
its missing-fixture diagnostic masked selected-profile mutation assertions. The
worker was corrected to use actual canonical inventory data. PROFILE-41-BEFORE-02
then demonstrated30 failed subresults and20 malformed-section errors, with the
unchanged profile's positive control passing. Before01/02workers/tests/results are
retained; no source repair is inferred from the flawed first baseline.

Candidate01:92PASS. Added four metric-boundary checks gave Candidate02:96PASS,
0fail/errors/skips. Twenty new methods include table-driven mutations across all
24leaves/30fields/seven object shapes, each wrong scalar type/value, missing and
unknown keys, malformed roots/sections, nonfinite HHI, direct audit/evaluator/
campaign callers, pre-access/pre-RNG rejection, unchanged profile hash and current
metric boundaries.76existing methods INCLUDED:45audit+21canary+8concentration+
2campaign. Existing assertions/fixtures and selected profile remain unchanged.

Approved LinuxPython3.14.4/bwrap, netoff/rootRO/privateTMP/45s campaign timeout;
0network/unapproved process attempts,8exact read-only Git calls from existing
audit tests. Full source/tool/loaded-module/command/stream hashes and before/after
checks retained. No explicit CPU/memory quota is proven. Synthetic snapshots and
10/100epoch unit campaigns are not the required100,000epoch acceptance campaign,
authentic beneficial-owner attestations, deployed safeguards or actual canary time.

Non-author implementation/result review, focused unchanged-rule scan, guarded
integration and fresh canonical checks remain separately recorded. This prepared
note does not itself establish those results. No required gate is weakened or
marked passed. Independent Linux3.12/full frozenCI/native qualification remains open.

## Traceability and invariant impact

Applies to G2 economic/control evidence (T17--T20/T22), G4 governance (T21), and G6 exposure/
rollout configuration consistency, plus cross-cutting release evidence controls.
It cannot close F01--F03/F13 governance/custody/settlement or source41's other
F12/F15/runtime/provider gaps. Actual applied controls and human review remain
required. No track status/owner decision or stage-applicability rule changes.

INV-1's30%profile value is bound; no emissions source/enforcement changes.
INV-2--INV-10 enforcement sources/values/encodings unchanged. No token liability,
reward, insurance exposure, authority, cryptographic proof or bridge is created.
Restricted activation/48h/registry-authoritative economics and current disabled
Deposit/Slash activation/ExecuteIntent/rewards/fiat/yield/minter/governor/vesting/
buyback/delegation remain. No R28/Slot08/Aiken/acquisition/provider contact/signing/
funding/deployment/live roles or human appointments. Actual closed7/public14days
and all unknown reviewed runner/provider/observer/custody/privacy inputs remain.
