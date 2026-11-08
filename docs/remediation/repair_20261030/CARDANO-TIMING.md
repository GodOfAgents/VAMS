# Cardano governance timing amendment

Date: 2026-10-30. Status: integrated uncompiled source; reference checks pass; native, ledger and budget checks NOT_RUN.
Timing revision: `upper-bound-v1` within the still unqualified governance-v2 candidate.

The previous Queue predicate set `queue_time` to the transaction validity lower
bound and added 172,800,000ms. That is a nominal 48-hour delay from a declared
bound. It does not ensure 48 hours after every permitted inclusion time. For
`[2000,2100)` and inclusion at 2099, the old deadline allows only 172,799,901ms.
The retained source arithmetic probe records this and the five-minute example.
These are arithmetic counterexamples, not observed Aiken or live executions.
ExecuteIntent remains unconditionally rejected.

The amended shared envelope supports finite, unsigned-64-bit millisecond bounds,
with lower inclusive, upper exclusive, positive width and width <=300,000ms.
The repository targets Plutus v3. Its current
[primary interval documentation](https://aiken-lang.github.io/stdlib/aiken/interval.html) describes semi-open
transaction validity ranges; the already cached pinned generic `between` helper
creates closed intervals. The valid fixtures now explicitly construct `[L,U)`.
Closed, open-lower, empty, inverted and out-of-domain fixtures are separate
negative cases. This normal-form decision still requires exact native and actual
Pre-Prod ledger/era/slot-to-POSIX validation; documentation is not ledger evidence.

Queue still requires the entire interval after the passed proposal's deadline:
`L >= deadline`. It now stores `queue_time = U`, `execute_after = U + D`, and
requires `U + D + lifetime` to fit uint64. For any permitted inclusion time
$t \in [L,U)$,

$$ (U + D) - t = D + (U-t) \ge D, \quad D=172{,}800{,}000\text{ms}. $$

The conservative extra wait is at most the validity-window width. There is no
claim of an on-chain wall clock. Before-deadline actions require `U <= deadline`
and `L < deadline`, so an upper-exclusive endpoint equal to the deadline is safe.
Finalize and expiry require `L >= threshold`, which covers the whole interval.
Cancellation retains its authenticated three-member refund path immediately;
it does not wait for the conservative queue timestamp or execution deadline.

The datum fields, explicit version2 envelope, hash domains and field order stay
unchanged. The original seven vectors, scalar byte/value oracle, schema and
legacy v1 source are preserved. A separate timing vector freezes the new Queue
fixture (upper2100 instead of lower2000), including full preimage and digest.
The old vector remains an encoding test and a backdated-Queue negative fixture.
It is not relabelled as a valid new Queue. Old88-case source is retained before
the fixture edits; earlier byte-prefix preservation claims apply to their old
source snapshots. All88 test names remain, with53 additional cases (141prepared).
The fixture changes deliberately update expiry thresholds by100ms and preserve
the existing exact24-hour and deadline-negative tests' intended targets.

New cases separate Queue transition, authority, governor and three mint-policy
callers for upper-anchor acceptance, consistently named lower-anchor rejection
and lifetime overflow. Vote transition/governor/receipt callers separate interval
mutations and upper-at-deadline acceptance. Additional cases cover one-ms/full
five-minute windows, latest safe uint64 arithmetic and exact/straddling expiry.
Synthetic extreme timestamps test an encoding boundary, not actual ledger
reachability. The case inventory and its source hash are bookkeeping only.
All141 native cases have NOT_RUN status; no parser/compiler/evaluator was invoked.

Local Python reference checks cover these arithmetic rules and2,000 seeded
windows, each at three inclusion positions. Ten timing tests plus15 preserved
byte/value tests pass in the local candidate. They neither execute Aiken nor
establish signatures, applied identities, ledger admissibility or budgets.
The existing81 parent obligations are retained. Named representatives do not
establish complete mutation/caller coverage; underspecified asset mutations
remain unresolved. No independent review is claimed.

Changed validator and policy scripts require newly compiled/applied identities,
reviewed genesis, actual custody and native/ledger/budget acceptance. Do not
automatically adopt old lower-anchor states or old compiled blueprints. The
unqualified candidate has no deployed migration. Any future migration must be
explicitly reviewed; changing the interpretation of old live state is forbidden.
The existing insurance custody repair remains unchanged and needs revalidation.

This slice directly supports F02/F03 and tracksT12/T16/T21, without closure
or promotion. INV-1 throughINV-8 underlying controls are unchanged; in particular
insuranceINV-2 and the supply capINV-8 are untouched. INV-9-adjacent locked-value
and exact-refund rules remain; this is not reward-solvency qualification. INV-10
is preserved by separate bridge requirements and disabled ExecuteIntent. No
Deposit, Slash activation, ordinary rewards/emissions, real fiat/yield, roles or
deployment is enabled. AllA-G gates and both host chains remain required.

No Aiken/Slot08, R28, dependency install/download, provider contact, external
service, real signing/key/custody action or deployment is authorized by this
amendment. Required failures and missing evidence remain blockers:13open findings,
0of36verified tracks. Authentic proofs, independent exact-byte DA, native database
durability, current host policy readers, privacy/custody/review and actual
dual-chain rehearsals/observation remain separate outstanding qualifications.


Canonical verification recorded2026-10-30: timing integration completed17guarded
paths (5new), with predecessor files/fullmanifest retained. Read-only capture
rechecked all6,683paths and bound26inputs. The captured integrated source passed
25local Python reference tests (10timing+15preserved byte/value); zero failures,
errors/skips, exit0. The timing property campaign includes2000seeded windows at
three permitted inclusion positions. Exact commands, tool/source hashes, output,
exits and limits are retained in CARDANO-TIMING-MODELS-CANONICAL-01.json/stdout/
stderr outside the checkout. These are arithmetic/byte tests, not Aiken behavior.

All141native cases remain NOT_RUN:28expected-accept,111expected-reject,2reference
matches. Case names/source SHA/status flags agree; no parser/compiler/evaluator,
signature/ledger/budget evidence is inferred. Focused Gitleaks8.30.1, matching
the approved binary hash, scanned27exact current inputs in a network-isolated
temporary copy, exit0 and empty report. It is not the whole-source/history gate,
Slither/Bandit/other scanner evidence or frozen workflow parity. The scanner's
source identities precede this documentation-only evidence publication.

The intermediate approval review failed for workspace credits and expressly did
not execute the read-only capture. Its absent result/directory/process state was
checked; after the owner restored credits, normal review completed the pending
check. No uncertain execution retry, approval bypass or repeated native job.
Insurance source, v1 layouts, v2 datum schema and seven original vectors remain
unchanged. Other tested Solidity/runtime scopes were not rerun or added to these
counts. Existing source-policy/current-chain, real PostgreSQL, authentic proof/
bridge/DA and independent observer/privacy/custody/review qualification remains.
No Aiken/Slot08/R28/install/download/provider/external service/real signing/role/
deployment action occurred. No official promotion:13open findings/0of36verified.

Track-label correction2026-10-30: T28 is Sentinel challenge/telemetry/slashing,
not Cardano test coverage. Cardano width/timing case preparation gives T28 no
verification credit. Historical wrapper trace records retain their original
hashes; TRACEABILITY-CORRECTIONS-18.json records the corrected interpretation.
The official36-track ledger/statuses and all findings remain unchanged.
