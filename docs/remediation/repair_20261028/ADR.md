# Authenticated Cardano governance v2 candidate

Governance remainder source campaign26, 2026-10-31: propose concrete refinements
for the26previously unnamed parent rows. Preserve all81frozen records and original
IDs/actions/references, including recorded ambiguities. Every parent row now has
representative names; this does not establish complete coverage or acceptance.
Add435source cases:31valid shared-caller controls,275expected rejections (including
two disabled-execution controls),84fixture-construction checks and45resource-only
at-limit controls. Total724prepared:68expected-accept,500expected-reject and156
reference/fixture checks. All native, applied-wrapper, ledger and budget runs are
NOT_RUN. No Aiken/Slot08 invocation. Earlier289test/helper bodies are preserved;
only three explicit import edits precede the appended cases. Older campaigns keep
their original source hashes; never relabel old blueprints as current source.

The proposed topology definitions distinguish exact protocol counts from global
16input/16output/16asset/896datum-byte/5signer bounds. Extra inputs use unique
references; extra outputs have explicit2million-lovelace matched funding. Each
malformed fixture has a separate positive construction/value check; every enabled
shared caller has a valid baseline. Resource controls check only envelope bounds,
not full permitted transactions. Opaque datums and surplus assets may trigger
other guards; no isolated reason-code or ledger-validity claim is made.

Eight local Python resource/value/byte tests pass, with lexical metadata checks.
The modeled866/867-byte raw payloads serialize to896/897bytes using the public
Plutus Data encoder rule; prepared native controls must independently confirm
actual serialized sizes. This unpinned reference is not runner qualification.
An eighth-vote fixture preserves seven prior locks, adds100real fixture tokens,
and retains eight distinct receipts. These are synthetic values, not actual funds.

Vote/Cancel have no v2start boundary: the proposed time_before cases use a negative
unsigned interval; Finalize cases use a premature deadline window. CancelIntent
adds no new maturity rule: its proposed boundary rejects an empty interval. Frozen
intent datum rows retain their proposal-reference discrepancy while proposed v2
cases target IntentDatumV2. These interpretations require independent review.
ExecuteIntent remains disabled; all its cases show containment only, not native
verification or destination, datum or timing validation for enabled execution.

Production validators, insurance custody,48hours, all encodings/goldens/locks and
restricted activation remain unchanged. INV-1throughINV-10have no executable
change; adjacent custody/supply/bridge controls INV-2/8/10remain unqualified.
F02/F03source coverage preparation and F16evidence work; related T04/T09/T12/T16/
T21remain at their recorded statuses. No finding/track promotion, review acceptance
or milestone entry follows. Full A--G/BOTH chains:13open findings/0of36verified.


Asset-boundary source campaign, 2026-10-31: the25generic historical labels now
have explicit PROPOSED v2 refinements preserving each parent ID, Vote/Queue action
and original intent/proposal fixture reference. Frozen parent artifacts are intact;
these definitions do not claim to recover unrecorded historical semantics.
The source adds148cases:114expected rejections across shared transaction/caller
functions,9valid caller controls and25fixture construction/value controls. The
original141test source prefix is byte-for-byte preserved. Total289prepared cases:
37expected-accept,225expected-reject,27reference/fixture checks; ZERO native runs.
No Aiken parser/compiler/evaluator, applied wrapper, signature, ledger or budget
result is inferred. ExecuteIntent remains disabled and48hours remains unchanged.

Eight local Python byte/value tests pass for25distinct malformed identifiers and
25synthetic conserving flows, including deficit detection. Source-name/status/
parent/caller metadata checks agree. These tests do not execute Aiken predicates.
Forged proposal identifiers in synthetic input state have no reachable-history
provenance; actual signed ledger fixtures, applied identities and budgets remain
required. Construction controls must pass before expected-failure tests receive
credit, so an accidental fixture-construction failure cannot qualify a rejection.

The81parent rows remain;55now have representative names (30prior+25), which is
not55verified or fully covered obligations. The older29-row count is stale.
The remaining26unnamed rows and all exact parent mutations/callers still require
completion and independent review. All acceptance credit remains false; native,
ledger and budget statuses stay NOT_RUN. Insurance and all production validators,
datum/domain encodings, locks, golden bytes and activation restrictions unchanged.
No Aiken/Slot08/R28/dependency acquisition/provider/live/signing/deployment action.
Full A--G/BOTH chains,13open findings/0of36verified tracks remain.



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


Date: 2026-10-28. Status: **implementation candidate, uncompiled and unreviewed**.
This continues the selected 48-hour, restricted dual-chain repair program. It is
not Aiken/ledger/budget qualification, a finding closure, or deployment authority.

## Source and specification discrepancies

The preserved R7/R9/R11 specification history remains unchanged. Its 24-hour normal
delay conflicts with the selected 48 hours. The active v1 helper was already
amended to 48 hours; historical frozen records retain their original identity.

Current legacy code finds authority from an arbitrary first input/output, infers
a policy from a script credential, preserves only selected authority fields,
permits replacement of previous voters, and accepts Queue without exact passed
proposal/action/nonces/refunds. Its configuration does not authenticate all
proposal/receipt/intent/VAMS policy identities needed to enforce custody.

The historical vote topology adds locked VAMS while permitting only an ADA-only
auxiliary funding input. With no VAMS mint or other token input, that value equation
cannot supply the added stake. The new version explicitly identifies its signed
voter funding input and conserves its actual VAMS and ADA.

One preliminary finding was withdrawn: `bytearray.slice(hash, 0, 31)` in the pinned
library is inclusive and returns 32 bytes. Legacy receipt/intent truncation is
**not** a defect. The data-only inspected library file and its SHA256 are recorded
outside the checkout in `STANDARD-LIBRARY-READ.json`; no Aiken run established this
counterevidence. V2 uses complete BLAKE2b-256 results without an unnecessary slice.

## Version and authenticated authority

New `GovernanceConfigV2`, proposal/lock/intent types and distinct v2 digest domains
leave existing v1 encodings intact. Every mint/spend entrypoint requires an outer
`GovernanceRequestV2` with `version == 2` before decoding the action semantics. Old
constructor numbers cannot silently acquire new meanings at the new boundary.

The authority mint/spend handlers share one applied script hash and policy ID,
following the established insurance singleton pattern. Insurance source is not
changed. This avoids a circular dependency between separate authority-policy and
authority-validator hashes. The script is parameterized by the exact seed,
network identifier, policy epoch and five unique custodians. Three configured
signatures approve the exact genesis transaction and immutable downstream IDs.

Compile order is authority first, then its NFT/anchor, then the five downstream
programs applied to that anchor. The genesis ceremony must independently recompute
every applied script/policy identity before the custodians approve the datum.
Self-declared child hashes alone are not proof that those programs are authentic.
The actual public custodians, hashes and ceremony manifest remain UNKNOWN.

Every authority read checks the pinned NFT, quantity, exact script address/value,
unique input/reference and bounded inline schema. The only continuing transitions
copy the entire configuration and increment exactly one nonce by one, while also
validating the associated complete Create or Queue transaction. Members, epochs,
token identities, destinations, delays, reserves and other policy fields cannot
change incidentally during a nonce update.

The protocol does not enable an authority migration or epoch update. A future
reviewed migration must invalidate pending approvals rather than reinterpret old
roots. Current epoch mismatches reject. No committee bridge fallback is introduced.

## Votes, custody and terminal value

The proposal NFT and exact inline datum identify one state. Existing locks must
remain an identical prefix when one vote is appended. The named voter signs and
funds actual VAMS plus the additional refund reserve; duplicate influence and the
ninth voter reject. Weights and totals are recomputed from backed locks, and each
receipt name binds its policy, proposal, voter, locked units, support and index.
Uniqueness is per voting key; this is not beneficial-owner or Sybil resistance.
Economic concentration/collusion review remains a separate acceptance requirement.

Proposal value is exactly its base ADA, one proposal NFT, one receipt per lock,
the sum of locked VAMS and one refund reserve per voter. The funding input pays
fees and new reserve contributions. Governed ADA/assets cannot become fee change.
Only the vote funding input may contain VAMS; all other funding is ADA-only.
Unused funding returns to the exact input address.

Finalize-Passed preserves complete value. Rejection/cancellation burn the proposal
and all receipts and pay every voter plus the proposer exactly. Queue consumes
the passed proposal and authority state, preserves authority value, refunds all
voters, burns the old tokens and creates the exact intent carrying the proposal
base reserve. Ordered exact outputs prevent a single underfunded payment from
satisfying multiple obligations, including when addresses coincide.

Queue binds immutable proposal terms, payload/destination, full passed-state
commitment, current authority epoch/nonce and finite upper-bound queue time
(timing amendment2026-10-30). Every enabled transaction has a nonempty [L,U)
window; queue_time=U ensures at least48hours after every permitted inclusion.
`execute_after` is exactly 172,800,000ms after U. Three-member cancellation and
post-lifetime expiry burn the exact intent and refund its bound proposer.
ExecuteIntent always rejects until authentic bridge/finality/replay controls qualify.
Liveness remains conditional on chain availability, appropriate keys and resources;
these predicates are not a universal liquidity or disaster-recovery proof.

## Bounds and ledger boundary

Preserved limits include five members/three signatures, eight voters, sixteen
inputs/outputs/assets, 896-byte datums and five-minute validity width. Aggregate
reserve arithmetic must fit its unsigned domain. Target lists and token names
are bounded; extra governance/withdrawal/treasury effects are excluded.

The inspected Plutus transaction/address types do not expose collateral or an
address network nibble. Network/genesis/magic, actual signatures, minimum UTxO/fee,
collateral, script execution and applied budgets require ledger-equivalent checks.
The network field in a datum does not establish actual Pre-Prod admission.

## Evidence, compatibility and remaining acceptance

`GOLDEN-VECTORS.json` freezes seven independent reference preimages/digests.
`DATA-SCHEMA.json` records constructor/field order and nested output references.
Native CBOR, compiled script identities and budgets remain NOT RUN.

The dependency-free Python oracle verifies bytes and value equations only. The
prepared native campaign has289cases:37expected-accept,225expected-reject
and27reference/fixture checks. **Zero native tests have executed.** Reference-width and
timing additions are source-only cases, not observed acceptance or rejection.
Historical integration entries below retain their own source/count identities;
the current timing amendment and changed fixtures are in repair_20261030/CARDANO-TIMING.md.
`R7-ACCEPTANCE-CONTINUITY.json` retains all 81 historical obligations; representative
new tests do not establish complete mutation/caller coverage or replace that matrix.

New source is an explicit candidate. Legacy governance remains inadmissible for
release; no deployment route may silently fall back to it. Applied identities,
native regressions, cross-script signed transactions, budgets, ledger parameter
preflight and independent review are required before switching a deployment to v2.
An old blueprint must never be represented as the new source's compiled output.

Public voter/custodian identities, balances and payload commitments remain linkable;
privacy disposition and current-source inventory review are pending. No real keys,
custody appointment or live governance action is supplied by the synthetic fixtures.

INV-1/2/3/4/5/6/7 are unchanged, including the established insurance custody source.
INV-8's VAMS supply cap is unchanged: governance NFTs are not VAMS emissions.
INV-9-adjacent voting obligations require actual locked custody and exact refunds;
rewards/emissions remain disabled. INV-10 is preserved: payload hashes grant no
bridge authority and ExecuteIntent rejects. Deposit, Slash activation, real fiat
and real yield remain disabled. F02/F03 stay open; no audit track is promoted.

## Research mechanism and limits

The [UTxO/account comparison](https://arxiv.org/html/2003.14271v4) uses a state token
to distinguish authoritative contract state. VAMS adopts that identity discipline,
with explicit token custody and transitions, rather than trusting a decoded datum.
This is a design adaptation, not a transferred proof.

[Validity, Liquidity, and Fidelity](https://drops.dagstuhl.de/storage/01oasics/oasics-vol129-fmbc2025/OASIcs.FMBC.2025.6/OASIcs.FMBC.2025.6.pdf)
motivates checking transition legality, conditional recovery and agreement between
logical balances and actual value separately. Its verified models do not certify
this Aiken candidate. Exact native and ledger evidence is still required.

### Prepared mutation expansion

The follow-up adds 23 individually asserted rejection cases for cross-counter
mutation, duplicate/nonmember threshold, authority/receipt substitution, governed
fee/change diversion, wrong destinations/refunds, missing burn, exact deadline,
invalid lock size, forged tally and a correctly backed equal-tally proposal.
Each rejection stands alone so an early abort cannot conceal another case.
These are uncompiled source cases, not observed rejection or signature evidence.
The full 81-obligation native/cross-caller campaign and applied budget/ledger
checks remain unfinished. No historical obligation or resource cap is removed.


### Cardano input-reference bounds — source integration candidate,2026-10-30

The shared v2 transaction envelope now explicitly requires32-byte transaction IDs
and unsigned32-bit output indices on every ordinary/reference input. The frozen
encoding already declares that boundary; bootstrap seed checks alone did not cover
every transaction input. This is a source boundary repair, not a claim of a
ledger-admissible exploit or a reproduced native failure. Datum/hash preimages,
48h governance, authority/insurance custody and ExecuteIntent containment stay.

The native source campaign has88prepared cases:61existing cases preserved as exact
bytes plus24negative and3syntheticpositive reference-width cases. Negatives separate
ordinary/reference inputs,31/33-byte IDs,negative/overflow indices and Vote
transition/governor/receipt-policy callers. Matching own_ref prevents a different
governor guard masking the intended test. Positive u32max contexts do not establish
actual ledger reachability. ALL88remain NOT_RUN; no Aiken/Slot08 invocation.

Source SHA/native matrix/R7continuity and a detailed campaign match.29of81parent
rows now have named representatives, not29fullycovered/verified obligations.
Other lifecycles/callers,25underspecified asset-boundary mutations, compiled
entrypoints, actual signatures/applied scripts/ledger/budgets and independent
review remain. Metadata/name checks are not Aiken parsing or behavior evidence.

Credits were restored after the earlier review failure. Fresh all6,676source-path
reconciliation confirmed this candidate's baseline before rebasing these docs.
No native/external action or dependency acquisition occurred. Changed script hashes
must be compiled/applied/reviewed later; old blueprint/output cannot be relabelled.
All A-G/both-chain gates and UNKNOWN qualification inputs stay.13findings remain
open,0of36tracks verified; no official promotion. Existing insurance design remains
unchanged and still needs native/independent revalidation. No restricted activation.


Canonical source/metadata verification,2026-10-30: CARDANO-WIDTH-INTEGRATION completed
10guarded paths,2new; preceding dirty files/fullmanifest retained. All6,678source
paths rechecked. Native source file has88prepared cases;61old bytes are preserved
as a prefix. New27cases include24separate negative and3syntheticpositive cases
across Vote transition/governor/receipt-policy callers. Source SHA, native matrix,
R7continuity, exact caller naming and per-case NOT_RUN flags match. This is metadata
consistency, NOT Aiken parsing/compilation/validator/signature/ledger/budget evidence.
Native/ledger/budget executions remainZERO; specific Aiken/Slot08 authority stays
unestablished. No synthetic max-index fixture implies real ledger reachability.

Insurance source is unchanged. Earlier820Solidity/48suites/sizes,codec12 and143
runtime results retain their exact matching source scope; not rerun or added to
Cardano cases. Current sourced dependency interval module was read only, not run
or acquired; code/lock hashes are recorded separately from tool qualification.
Fresh source accesses resumed after credits restore. The blocked grant evidence
writer completed normally and its3doc outputs exactly match the prepared review.
No uncertain execution, alternate canonical access, install/download, provider,
external service, real keys/signing/funds/roles or deployment occurred.

No acceptance credit or official promotion:13open findings/0of36verified tracks.
Full81-obligation exact mutation/caller coverage, realistic ledger contexts,
applied identities/budgets, actual custody and independent review remain. Source
input-reference checks alone do not establish F01-F03 remediation or admission.
