# Retained authority generations and explicit renewal

Effect persistence uniqueness guard27, 2026-10-31: the V3provider, V3authority
and storage4authority now inspect required primary/unique keys before transaction
bodies. Matching migration metadata alone is insufficient. The local before
regression has10tests/110failing subchecks,0errors: invalid or absent catalog
responses were ignored and bodies entered. These are controlled driver results,
not a native PostgreSQL duplicate-effect demonstration. The repaired full selected
suite passes166tests,0failures/errors/skips, including11new guard tests and12live-
mode containment tests. Windows3.12/real ECDSA fixture keys/queued driver evidence
remains distinct from authentic host policy, native PostgreSQL or live assurance.

Acquire literal table locks before the first schema SELECT freezes a serializable
snapshot; inspect required key columns/types/non-nullability, primary/unique kind,
immediate/nondeferrable/validated constraints and live/ready/valid unique B-tree
indexes with expected built-in operator classes. Reject partial/expression indexes,
inheritance/partition/unlogged tables, malformed responses, missing/extra/duplicate
keys and inspection/lock errors before yielding a protected body. Key declarations
cannot be rebound after database construction. No cache, fallback, automatic
schema repair or execution retry. Native lock/DDL-race semantics remain untested.

This checks uniqueness prerequisites only. It does not attest the whole schema,
foreign/check constraints, server integrity, privileges, triggers, RLS, backups,
WAL, TLS, storage durability or operator custody. Approved server/driver/role and
current-host manifests remain UNKNOWN. SQL parsing/execution and constraint/DDL-
race/concurrency/crash/restart/unknown-commit acceptance on real PG are NOT_RUN.
New table locks/catalog reads add operational work requiring native measurement.

DDL/migration checksums/storage versions, protocol wire/goldens, logical operation
identity, budgets and historical reconciliation semantics remain unchanged.
Only3persistence modules and test/doc files changed; no new persistent fields.
Prior privacy20source identities for affected modules need refresh/review; old
inputs/results remain historical.212field rows plus7earned-record entries remain
UNREVIEWED. No actual database, provider, key or private record was accessed.
Live constructors still reject. All restricted economics/48hours/disabled
Deposit/Slash activation/ExecuteIntent/fiat/yield remain. INV-1throughINV-10
executable controls outside persistence are untouched; uniqueness supports the
effect/budget boundary without proving token backing or external exactly-once.
F12/F13/F16and T04/T09/T15/T29/T33retain dispositions. Full A--G/BOTH chains,
13open findings/0of36verified remain. No new provider/runner input question.


Date: 2026-10-30. Status: integrated, unactivated; 135 copied-source local tests pass; native/authentic/live qualification pending.

## Design basis and observed gap

The owner's Stage D/F plan requires current approval before resumed effects and
separate earned-completion/refund paths after authority changes. This extends
AUTHORITY-V3.md, ASYMMETRIC-OBJECT-V3.md, GCA_ACCEPTANCE, ADR-VDSO-001 and the
common action/receipt contract. Capability enforcement follows the previously
reviewed CaMeL mechanism; external effects still require provider cooperation as
in the previously reviewed Apiary mechanism. Neither paper proves VAMS behavior.

V3 intentionally rejects implicit scope reissue. Replacing its one scope row would
also prevent old operations from verifying against their original grant. The
retained before03 probe has two failures: missing explicit renewal and a controlled
overwrite counterexample. It does not claim V3 automatically overwrites history.

## Storage and lifecycle

Fresh storage revision4 has explicit meta, generation, stable-head and operation
tables. A generation ID commits exact ObjectAuthorityScopeV3 bytes under the new
VAMS:AUTHORITY-GENERATION:v4 domain. Generation records bind predecessor, ordinal,
grant, current/final fence and acknowledgement, plus closure spending. The stable
head references the current generation and holds cumulative budget accounting.
Operations reference their original generation, with globally unique stable
logical operation IDs. New Python-only golden vectors freeze generation IDs;
native cross-language conformance remains pending. No old wire bytes change.

Renewal is explicit: previous generation revoked, exact provider acknowledgement,
zero reserved and zero pending operations, including zero-cost ones. New epoch
and token exceed the acknowledged cutover; policy cannot roll back, changed roots
require an increased version, units stay fixed and responsible host policy must
authenticate the successor. The identity/domain/actor scope stays fixed. A new
generation begins installing and needs a fresh exact provider acknowledgement.
Unreachable old writers and unresolved obligations prevent unsafe renewal.

Budget_limit is an absolute cumulative ceiling. A ceiling of 10 after spending 3
permits only 7 further units. Renewal does not reset cumulative spend, erase
obligations, rewrite old grants, authorize a duplicate operation or forgive spend.
Historical completed/rejected operations verify with their original grant and
cannot charge/refund again. V3's committed dispatch claim, lookup-only uncertainty,
exact signature checks and no-timeout-refund rules are reused via small extension
seams. A V3 coordinator/database/policy cannot silently compose as V4.

Storage4 is not receipt version4. Provider wire/storage and ReceiptV3 stay V3.
Fresh migration has a separate checksum/configuration identity. No automatic
legacy state adoption, provider/host migration, key rotation, downgrade or drain
is implemented. A reviewed explicit migration or drain is a future entry input.

## Invariant and privacy impact

INV-1/2: no emissions or insurance-yield changes. INV-3/4: existing session lifetime
and whitelists unchanged. INV-5: OMS fail-closed controls unchanged. INV-6: actor
binding is retained; this is not authentic TEE verification. INV-7/8: oracle and
supply controls unchanged. INV-9: cumulative execution-budget accounting is not
reward backing; token/reward contracts unchanged. INV-10: native bridge evidence
remains separate from payload commitments; no bridge acceptance is added.

No deposits, Slash activation, ExecuteIntent, fiat, yield, rewards, staking minter,
ordinary governor, vesting, buyback or delegation is enabled. Permanent grant and
actor/workflow/intent/resource links, closure budgets, signatures, DB/WAL/backups
and observer access require the outstanding privacy review. No secret is embedded.

## Evidence boundaries

The first two before probes failed during fresh-process Windows cryptographic
initialization. A bounded diagnostic isolated removal of SystemRoot by test setup;
preserving OS roots restored entropy initialization. Before03 then produced the
two intended capability/counterexample failures, without production changes.
Candidate01 had 134 tests and one fixture-path error; copying the unchanged
authority-scope vector fixed the path. Candidate02 has 135 passes, no skips.
Exact passing source/helper/result bytes are retained in the attempt02 archive;
earlier failed command/output/source hashes remain historical evidence. The
changed local Python executable's hash is recorded, not approved by inference.

These tests use real ECDSA fixture keys and controlled queued database calls. They
do not execute native SQL constraints, transactions, TLS, concurrency, durability,
crashes, restore or real services. Host policy/custody/finality remain abstract;
direct transport is a trusted-process seam. Approved independent Linux3.12/PG,
remote identity/key isolation, authentic proofs/DA/checkpoints/settlement and full
frozen CI, privacy and independent assurance remain required. Official 13 open
findings and zero of 36 verified tracks are unchanged. No readiness claim follows.


### Explicit renewable authority with retained history — 2026-10-30

The unactivated storage4 authority candidate retains each exact grant, predecessor,
final fence/acknowledgement and cumulative spending snapshot. A stable scope head
holds cumulative reserved/spent amounts; each operation records its original
generation. Renewal requires a revoked, acknowledged predecessor, zero reserved
budget and zero pending operations, including zero-cost operations. The successor
must advance beyond the acknowledged cutover epoch/token, preserve units/domain/
actor/provider, satisfy current host policy, and receive its own exact provider
acknowledgement before admission. No timeout or expiry alone renews authority.

The successor budget is an absolute cumulative ceiling. Spending 3 from a ceiling
of 10 leaves 7 after renewal at the same ceiling. Old completed/rejected operations
remain verifiable against their original grant and cannot charge/refund a new
generation. Logical operation identity cannot be rebound. Closed history is not
overwritten by the source API. ReceiptV3 and ActionContextV1 bytes are unchanged.

This uses explicit fresh authority storage revision4 and distinct migration/config
hashes/types; it never adopts V3/V2/V1/DBOS rows or treats local MACs as production
signatures. A reviewed legacy migration/drain remains required for existing state.
Provider wire/storage remain V3. No live route or implicit provider/host migration.

RENEWAL-V4-CANDIDATE-02 passes 135 tests, zero failures/errors/skips: the earlier
113 tests are INCLUDED with 22 renewal tests. Fresh-process authority53/renewal22
checks also pass and overlap. These are local Windows Python3.12.14, existing
cryptography50.0.2, ECDSA fixture keys and queued driver calls, not native PostgreSQL,
independent Linux3.12, authentic host-policy/custody or multi-host qualification.
The Windows runtime executable now hashes f8b45d63047da9d9adf09892e4cc4317b859e86a93a478cc9616bc69d3b176e5;
it differs from the prior retained binary, with no provenance approval inferred.
Fixture environment isolation now preserves Windows SystemRoot/WINDIR so native
cryptographic entropy initialization works; no production RNG behavior changed.

CurrentRenewalPolicyV1 remains an abstract responsible-host dependency. Actual
policy/finality/consent, remote transport/key isolation, PG constraints/concurrency/
crash/restore/TLS, retrievable checkpoints and effect/proof/settlement/earned-claim/
refund integration remain unqualified. Budget bookkeeping is not token custody.
Privacy review must cover permanent grant lineage, operation links, cumulative
spend/closure snapshots, receipts and database/WAL/backup/observer retention.
The full A–G plan and both-chain gates remain. No finding or track is promoted.


### Canonical renewal verification — 2026-10-30

RENEWAL-V4-INTEGRATION completed 13 guarded paths, 6 new. All 6,668 source paths
were checked before exporting 20 exact test inputs. RENEWAL-V4-CANONICAL-COPY-01
passes 135 tests, zero failures/errors/skips, with no network/process attempt.
Counts: 17 protocol, 36 provider, 7 receipt primitives, 53 authority/coordinator
and 22 renewal. Earlier 113 are included; candidate and isolated runs overlap.
Actual tests use local Windows3.12.14/cryptography50.0.2 with ECDSA fixture keys
and queued driver calls. Linux3.14 only checks source hashes and Python3.12 syntax.
No native PostgreSQL, authentic policy/custody, external service or independent
Linux3.12 qualification occurred. Tool/source/command/output/exit hashes retained.

Before01/02 stopped at crypto initialization. The isolated diagnostic established
that test environment clearing removed Windows SystemRoot; fixtures now preserve
SystemRoot/WINDIR. Before03 then reproduced the intended two capability/history
counterexamples. Candidate01 had one missing unchanged-vector fixture path;
candidate02 and integrated copy pass. These failed outputs remain evidence, not
relabelled success. The local Python executable's changed f8b45d63... hash is
recorded with package hashes; independent runner/tool provenance is still required.

Explicit renewal and retained grant/operation history are implemented in fresh
storage4, with cumulative spending retained and new acknowledgement required.
Existing V3 provider/receipt bytes and protocol-contract/Cardano/workflow sources
are unchanged. Legacy storage adoption, actual authenticated responsible-host
policy, remote identity/key isolation, native PG migration/constraints/concurrency/
crash/restore/TLS, retrievable checkpoints and final effect/proof/settlement remain.
Privacy includes retained lineage, cumulative budgets, receipts and WAL/backups.
No official promotion: 13 findings open, zero of 36 tracks verified. Full A–G,
both chains, custody/independent assurance and actual 7-/14-day observation remain.
