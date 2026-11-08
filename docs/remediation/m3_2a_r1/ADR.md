# ADR M3.2a - authenticated bounded governance baseline

Status: **R5-remediated design baseline; pending independent R6 review**  
Date: 2026-09-26  
Scope: F02 timelock authority and F03 governor state machine only. This is a design contract; current Aiken validators remain unchanged and do not yet implement it.

## Decision and evidence

The independent R2 review package
/home/GodOfAgents/vams-evidence/m3-2a-r2-review-20260926-829ab544571f
has SHA256SUMS digest
9dd4a9729213af10617008d0591fe31aae5fa92124e3ba145098bfc26469b3f5.
R2 found that the prior frozen text lacked authenticated nonce allocation,
feasible lock/refund representation, complete lifecycle boundaries, and an
executable public-handler acceptance matrix. This R3 amendment resolves those
design defects only. It does not claim F02/F03 implementation or F01/F05
closure. M3 remains open, Deposit and Execute remain disabled, and promotion is
not ready.

## 1. Canonical authority singleton

governance_authority_policy_v1 is parameterized by exactly one configured seed
OutputReference. Genesis consumes that exact seed once and mints exactly one
quantity of authority_state_asset_v1 at the canonical authority UTxO. After
genesis, every counter-changing action consumes and continues the same policy
ID, asset name and quantity one. No update may mint a replacement or successor
authority asset; burning, duplicating, reminting, or creating a second configured
authority instance is invalid.

M3.2b does not implement member or configuration changes. policy_epoch is fixed
after genesis. Only authenticated proposal and intent counters change.
Counter-changing actions consume the authority asset and emit exactly one
successor authority output with the same asset and authenticated datum
transition. Read-only actions use the exact authority asset as a reference
input and bind its datum hash and fixed epoch. A datum integer, script hash,
address, or signer count alone is never authority.

AuthorityDatumV1 contains exactly the versioned schema, fixed policy epoch,
five unique sorted member verification-key hashes, threshold three, normal
delay, emergency-disabled flag, next_proposal_nonce, next_intent_nonce,
finite caps, and a nonempty allowlisted target-domain set. Member hashes use
the exact Cardano verification-key-hash length.

## 2. Authenticated nonces and policy domains

CreateProposal consumes the authority datum with proposal nonce N, rejects
skip/reuse/decrement/overflow and attacker-selected values, mints only the
proposal asset derived from the versioned proposal domain, fixed epoch, N,
proposer, action hash and target domain, and continues authority with exactly
N+1. Queue consumes the authority datum with intent nonce M, mints only the
intent asset derived from the versioned intent domain, proposal asset, proposal
ID, action hash, fixed epoch, M and target domain, and continues authority with
exactly M+1. The old/new authority datums and exact asset quantity are checked
by the spend and policy boundaries; a copied datum is not sufficient.

Authority, proposal, receipt and intent assets use distinct versioned domain
separators and policy IDs. No nonce wraps. The proposal policy and intent policy
must inspect authenticated authority/proposal state, exact redeemer, mint
quantities, names, output datum/value and continuation. A script hash or datum
integer alone cannot authorize minting or burning.

## 3. Versioned policy responsibilities

governance_proposal_policy_v1 authorizes exactly one proposal NFT on Create from
the authenticated authority counter and burns it only on Finalize-Rejected,
Cancel, or Queue. It validates the exact proposal datum, one canonical output,
finite validity and proposer signature.

governance_receipt_policy_v1 authorizes one receipt per Vote. The receipt name
is a domain-separated hash of the proposal asset and voter verification-key
hash. The policy inspects the exact Vote redeemer, proposal asset, voter
signature, receipt name and quantity, proposal output datum/value, and rejects
transfer, substitution, duplicate mint, or burn outside a terminal transition.
Every receipt stays in the proposal output until Finalize-Rejected, Cancel or
Queue, when every receipt is burned exactly once.

governance_intent_policy_v1 authorizes exactly one intent NFT only from Queue of
the exact Passed proposal. It validates the authority counter transition,
proposal asset, exact intent datum/output/value and one mint quantity. It burns
that intent only on authenticated CancelIntent or ExpireIntent. All policies
must inspect authenticated spend/reference state and exact output cardinality;
no policy may trust a bare integer, script hash or datum shape.

## 4. Feasible locked-vote representation

Replace an unspecified voter-key list with a bounded list of exactly
VoteLockRecordV1 entries. Each record contains exactly:

- voter_verification_key_hash;
- locked_vams_amount;
- support;
- quadratic_weight;
- receipt_asset_name.

The refund destination is the canonical key-payment credential derived from
the record voter verification-key hash. Script credentials, alternate payment
credentials and network-ambiguous addresses are rejected; the destination is
not an attacker-selected output field. Each Vote requires the voter signature, transfers the exact
locked VAMS amount into the canonical proposal output, mints one receipt,
keeps it in that output, and appends exactly one record. Prior records,
proposal value, authority binding and all assets are preserved. A duplicate
voter or receipt rejects.

Finalize-Rejected, Cancel and Queue are terminal transitions. They burn every
receipt exactly once and create one refund output per record, each controlled by
the corresponding voter payment credential and returning the exact locked
amount. No receipt alone authorizes a refund; the terminal spend must consume
the proposal state and prove the record/output/value correspondence. Queue
also creates the single exact intent after refunds and increments the intent
counter.

The protocol cap is frozen at 8 voters. The disposable pinned Aiken model and
canonical-CBOR feasibility model measured proposal datum sizes of 220, 304, 892
and 976 bytes for 0, 1, 8 and 9 records respectively, using bounded 64-bit
amount/nonce/deadline/tally fields and bounded 32-bit epoch/quorum/weight
fields. Eight records are below the 896-byte datum cap; nine reject it. The
maximum Queue shape has 8 refund outputs + 1 authority continuation + 1 intent
output + 1 required change output = 11 outputs, at most 3 principal inputs
(proposal, authority and one fee/change input), and 12 distinct non-ADA assets
(proposal, authority, intent, VAMS and 8 receipts), all below the frozen 16
limits. Cancel/Finalize-Rejected use at most 2 principal inputs, 9 outputs and
10 distinct non-ADA assets. These are schema/serialization bounds only, not
applied-validator budget proof. M3.2b must measure actual transaction fees,
validity range, witnesses, redeemers, collateral, script sizes and worst-state
budgets.

Integer fields are canonical bounded integers: nonce, locked amount, deadline
and tallies are 0..2^64-1; policy epoch, quorum and quadratic weight are
0..2^32-1. Negative, non-canonical, overflow and out-of-range values reject
before arithmetic or serialization. Quadratic weight is derived from the
bounded locked amount and independently supplied values outside the width
reject.

## 5. Exact proposal lifecycle

The only valid proposal paths are:

- Create: consume authority nonce N, mint one proposal asset, and create one
  Pending proposal with immutable proposal asset, nonce, proposer, description
  hash, action hash, target domain, fixed authority epoch, quorum, deadline,
  tallies and empty lock list.
- Vote: consume the exact proposal asset and authority reference, require one
  voter signature and one new lock record, and emit exactly one proposal
  continuation preserving all prior records, immutable fields, value and assets.
- Finalize-Passed: after the finite deadline, emit exactly one Passed
  continuation, preserving all locks and receipts.
- Finalize-Rejected: after the deadline, burn proposal and every receipt, and
  refund every exact lock to its bound voter credential.
- Cancel: proposer-signed before the deadline; burn proposal and every receipt
  and perform the same exact refunds.
- Queue: consume the exact Passed proposal, burn the proposal and receipts,
  refund every lock, consume/increment intent nonce M, mint one intent asset,
  and create exactly one bound intent output.

No terminal transition permits replay, a second continuation, redirected
refunds, reduced amounts, dropped records or substituted assets.

## 6. Governor-to-timelock binding and pre-F05 lifecycle

Queue is enforced by the governor spend plus governance_intent_policy_v1; it
is not a QueueIntent timelock spend action. The intent datum binds proposal ID,
proposal state asset, action/payload commitment, fixed policy epoch, target
chain/domain, intent nonce, queue time and execute_after = queue_time + 24
hours. The one output is at the exact reviewed timelock address with the exact
intent asset, value and inline datum.

Before F05, timelock redeemers are deliberately restricted:

- CancelIntent: exactly three distinct members of the fixed five-member
  authority, authenticated against the authority datum, burn the intent exactly
  once and return only the permitted value.
- ExpireIntent: only after execute_after + 7 days, burn the intent exactly once
  and return only the permitted value.
- ExecuteIntent: rejects unconditionally for every input. No proof bytes,
  structural Mithril bytes or mock evidence can release a cross-chain action.
  Successful Execute semantics, finality verification and release remain
  deferred to F05/M4.

## 7. Frozen bounds

M3.2b shall enforce these exact limits: authority members exactly 5 unique
sorted keys; cancellation threshold exactly 3; voters maximum 8; transaction
inputs maximum 16; transaction outputs maximum 16; distinct non-ADA assets
maximum 16; serialized governance datum maximum 896 bytes; unique extra
signers maximum 5; transaction validity interval width maximum 5 minutes;
proposal voting duration finite and at most 30 days; normal timelock delay
exactly 24 hours; intent lifetime after execute_after at most 7 days; action
and description hashes exactly 32 bytes; member/voter hashes exact Cardano
verification-key-hash length; target domains nonempty, at most 32 bytes and
members of the authority allowlist; emergency execution disabled.

## 8. M3.2b acceptance matrix

The public compiled-validator and policy harness must record one row per case
with: public handler/policy boundary, expected accept/reject, unique rejection
reason, mutation control ID, artifact hash and attributable output. Required
cases include:

- authority genesis with wrong seed, duplicate/reminted/burned authority,
  changed epoch, and non-unit quantity;
- proposal/intent nonce reuse, skip, decrement, overflow and attacker-selected
  values;
- receipt transfer/substitution, duplicate receipt, wrong voter, wrong amount,
  wrong refund credential and incomplete terminal burn/refund;
- dropped/replaced/duplicated lock records, wrong value, wrong proposal/action,
  epoch/domain, redirected or reduced refunds, and multiple continuations;
- exact 8-voter acceptance and 9-voter rejection;
- exact 16-input/output/asset/datum limits and one-over-limit contexts,
  including Queue change output;
- duplicate/unauthorized/non-member cancellation signers and emergency-delay
  misuse;
- meaningful CancelIntent and ExpireIntent boundary/replay cases;
- an unconditional ExecuteIntent rejection property/mutation family for every
  timing, proof, payload, domain, epoch and replay input.

All successful and rejecting cases must exercise public compiled handlers or
policies rather than private predicate copies. Full applied script sizes and
worst-accepted-state evaluator budgets remain M3.2b requirements; no schema
model is evidence of budget viability. Pre-Prod comparison remains pending an
authoritative parameter snapshot.

## 9. Status and invariant impact

F01-F05 remain open; Deposit and Execute are disabled; M3 is OPEN; Pre-Prod
admission is INCONCLUSIVE; promotion is NOT READY. This R3 slice changes only
the design ADR and scoped documentation/evidence. INV-1-INV-10, M1/M2
containment, bridge-proof/payload-hash separation, mock behavior, deployment
state, credentials, dependencies, vendors and Git history are unchanged.

## 10. R5 exactness amendment (supersedes underspecified R3 wording)

The independent R4 review identified material design gaps in terminal value
conservation, asset-name canonicalization, counter authorization, lifecycle
boundaries, and transaction feasibility. This section is normative and
supersedes any earlier use of “permitted value”, “canonical output”, or
“after/before the deadline” where those terms were not fully defined. It is
still a design contract; it does not claim that the current validators enforce
these rules.

### 10.1 Value conservation and terminal topology

Every enabled transition has one consumed state value and an exact output
multiset. Value is the Cardano `Value` map, not only lovelace. A transition is
valid only when, for every policy-id/asset-name pair, the sum of consumed
inputs plus explicitly authorised minted quantity equals the sum of outputs
plus the fee and explicitly authorised burned quantity. Fees are paid from the
single declared fee/change input; no fee is charged to a refund output.
Change is exactly one output at the authority address for authority transitions
or at the proposer/refund address selected by the transition contract for a
terminal proposal transition. A second change or unbound top-up output is
invalid. Collateral is a separate ADA-only input and collateral return is
absent unless the ledger-era transaction body requires it; when present it is
one exact return output to the collateral input's payment credential and is
included in the topology count.

The network id is a frozen transaction parameter, carried in the reviewed
configuration and never inferred from a caller. A voter refund address is the
network-tagged address containing exactly the voter's 28-byte key-payment
credential and no stake credential. Script credentials, a stake component,
network mismatch, or an address supplied only in the redeemer reject. Every
refund output has the exact locked VAMS quantity and the protocol's fixed
minimum ADA reserve for that output; the reserve is a named ledger parameter
and is included in the pre-transaction balance equation. No unrelated asset
may appear in a refund output.

A proposal continuation contains exactly one proposal NFT, all prior lock
records and receipts, the immutable proposal fields, and the exact ADA/VAMS
reserve required by those records. Vote adds exactly one receipt and exactly
one locked-VAMS quantity. Finalize-Rejected and Cancel consume the proposal
state, burn the proposal NFT and every receipt once, and produce exactly one
refund per record plus at most the one bound change output. Queue consumes the
Passed proposal, performs the same exact refunds and burns, consumes exactly
one authority input and increments the intent counter, then creates exactly
one intent output at the reviewed timelock address. The intent output contains
exactly one intent NFT, its fixed ADA/min-ADA reserve, the bound action and
payload commitment, and no unrelated assets. CancelIntent and ExpireIntent
consume that one intent output, burn exactly one intent NFT, and return the
entire remaining intent value (fixed ADA reserve plus any explicitly bound
assets) to the authority-controlled refund address; they cannot redirect,
reduce, strand, or manufacture value. ExecuteIntent has no valid terminal
value topology before F05 because it is unconditionally rejected.

The Queue, Cancel and Finalize-Rejected topology proofs must enumerate, for
each case, normal/reference/fee/collateral inputs, collateral return, every
output including refunds/change, every non-ADA asset, inline datum and
redeemer, required vkey/script witnesses, fees and min-ADA. The published
maximum Queue model is 3 principal inputs, 11 outputs and 12 non-ADA assets,
but those are only admissible after the full ledger-era topology and budget
measurement fits the frozen limits. Any measured fee, min-ADA, witness,
redeemer, datum, script or evaluator-budget value above its bound is a hard
stop; no off-chain selection or truncation is an acceptable workaround.

### 10.2 Canonical asset names and policy bootstrap

All hashes below are Blake2b-256 over the exact byte string shown. Domain
separators are literal ASCII bytes, including the trailing NUL:
`VAMS/authority/v1\0`, `VAMS/proposal/v1\0`, `VAMS/receipt/v1\0`, and
`VAMS/intent/v1\0`. Integers use unsigned big-endian encoding with fixed
widths: nonce, amount, deadline and tallies are `u64`; policy epoch, quorum
and quadratic weight are `u32`; list lengths and output indices are `u16`.
Byte strings are length-prefixed with a `u16` length, and an OutputReference
is exactly a 32-byte transaction hash followed by a `u16` output index. The
canonical preimage is the domain bytes followed by fields in the order named
in the corresponding datum schema, with no optional fields, map reordering,
text encoding, whitespace, or alternative integer widths. The 32-byte digest
is used in full; no truncation, hex-text encoding, or endian conversion is
permitted. Every policy asset name is exactly the 32-byte digest and therefore
satisfies Cardano's asset-name limit; any other length rejects.

Bootstrap is acyclic and fixed: (1) consume the configured genesis seed and
mint the singleton authority asset under `governance_authority_policy_v1`;
(2) parameterize `governance_proposal_policy_v1`,
`governance_receipt_policy_v1`, and `governance_intent_policy_v1` with the
authority policy id and singleton asset; (3) derive proposal names from the
authority epoch/nonce/proposer/action/domain tuple; (4) derive receipt names
from proposal asset plus voter key hash; and (5) derive intent names from the
Passed proposal asset, proposal id, action/domain and intent nonce. Policies
must reject any parameter set not committed by the singleton authority datum.
The authority NFT is never derived from a later policy id, and no policy may
bootstrap itself from its own output.

### 10.3 Counter preservation and authenticated authority

AuthorityDatumV1 is immutable in every field except the selected counter. A
CreateProposal transition proves `new.next_proposal_nonce = old + 1` and
byte-for-byte equality for `next_intent_nonce`, member set, threshold,
policy epoch, delays, caps, emergency flag and target allowlist. Queue proves
the inverse: only `next_intent_nonce` increments and every proposal counter
and immutable field is unchanged. Both counters reject skip, reuse, decrement,
wrap and attacker-selected values before arithmetic. Counter-changing spends
require signatures from at least 3 of the exact 5 distinct sorted member key
hashes; a non-member, duplicate signer, more than five unique signers, or a
missing authority-state input rejects. Read-only reference use does not mutate
counters and still binds the singleton asset, datum hash and fixed epoch.

### 10.4 Deterministic weights, quorum and time

`quadratic_weight` is `floor_sqrt(locked_vams_amount)` in the smallest VAMS
unit, computed with a bounded u64 integer square-root algorithm. Any supplied
weight that differs from the deterministic result, any intermediate overflow,
or any value outside the declared u64/u32 width rejects before comparison,
addition or serialization. Tally additions are checked and the sum of yes/no
weights is the exact record sum. A proposal reaches quorum exactly when
`yes_weight + no_weight >= quorum_weight`; it passes exactly when quorum is
reached and `yes_weight > no_weight`. A tie is rejected. The validity interval
uses a lower-inclusive/upper-exclusive convention: Vote and proposer Cancel
require `t < deadline`; Finalize-Passed and Finalize-Rejected require
`t >= deadline`; Queue is valid only for Passed; normal intent execution time
is `t >= execute_after`; CancelIntent is valid only while
`t < execute_after + lifetime`; ExpireIntent is valid only at
`t >= execute_after + lifetime`. All additions use checked bounded arithmetic
and a finite validity interval no wider than five minutes.

### 10.5 Source-reality and implementation stop rule

The current checked-in `cardano/validators/governor.ak`,
`cardano/validators/timelock.ak`, and `cardano/lib/vams/types.ak` are the
legacy implementation and do not yet implement this amendment. In particular,
the current timelock still has an ExecuteIntent path that can accept structural
proof bytes and the governor still has its legacy Execute path. This is an
explicit source-reality boundary, not an acceptance claim. M3.2b must first
replace both paths and add public compiled-handler tests proving unconditional
pre-F05 ExecuteIntent rejection. If any required field, topology, policy
parameter, ledger-era budget or authoritative parameter snapshot cannot be
measured and bound, implementation stops and M3 remains OPEN; no design-only
fixture, nominal size model or simulated timestamp can authorize funding,
Deposit, Execute or Pre-Prod admission.

### 10.6 R5 acceptance-matrix additions

The M3.2b matrix in Section 8 is extended with mutation IDs for: each exact
refund address/network/min-ADA/value equation; fee/change/collateral and
collateral-return cardinality; every non-ADA asset and 32-byte canonical name;
policy bootstrap order and wrong-domain/hash encodings; untouched-counter
preservation and 3-of-5 signer membership; square-root rounding, overflow,
quorum tie and every inclusive/exclusive time boundary; and one-over-limit
witness, datum, fee, min-ADA and evaluator-budget contexts. Each row must cite
an applied public handler/policy artifact, not this ADR or a private predicate
copy. Until those artifacts exist, F02/F03 stay `REVALIDATED_OPEN`, F01-F05
stay open, Deposit and Execute stay disabled, M3 stays OPEN, Pre-Prod remains
INCONCLUSIVE, and promotion remains NOT READY.

## 11. R7 machine-readable specification closure

R7 freezes the remaining design-level ambiguity in the following normative,
closed artifacts. They are the specification for M3.2b and are not evidence
that the current legacy validators enforce them:

- `docs/remediation/m3_2a_r7/GOVERNANCE_SPEC.json`
- `docs/remediation/m3_2a_r7/ASSET_VECTORS.json`
- `docs/remediation/m3_2a_r7/DATUM_VECTORS.json`
- `docs/remediation/m3_2a_r7/TRANSITION_TOPOLOGY.json`
- `docs/remediation/m3_2a_r7/ACCEPTANCE_MATRIX.json`
- `docs/remediation/m3_2a_r7/governance_spec.py`
- `docs/remediation/m3_2a_r7/test_governance_spec.py`

These artifacts supersede any earlier underspecified R3/R5 wording, including
the earlier u16 output-reference index and implicit schema-dependent asset
encoding. R7 uses `tx_id[32] || output_index[u32be]`, explicit ordered fields,
explicit domain bytes, fixed-width integers, a u8 target-domain length, and
untruncated BLAKE2b-256 names. The authority NFT preimage is explicitly
specified rather than inferred from a datum schema.

GovernanceConfigV1 is an immutable genesis datum. It contains the explicit
network id, authority/proposal/refund lovelace parameters, one-shot seed
OutputReference, compiled authority/governor/timelock identities, exactly five
fixed authorizers and threshold three. Runtime environment variables, redeemer
values, alternate networks, stake credentials in enterprise outputs, alternate
payment credentials, additional governed destinations, and non-ADA auxiliary
funding all reject. Authority, proposal and intent outputs are enterprise
script addresses with no stake credential; voter and proposer refunds are
enterprise key addresses using the immutable network id and exact configured
verification-key hash; fee/change is only the exact address of the one ADA-only
auxiliary funding input.

The machine-readable value equations require authority NFT plus
`authority_state_lovelace`, proposal NFT plus `proposal_base_lovelace`, one
receipt/locked amount/reserve per Vote, complete preservation on
Finalize-Passed, exact voter and proposer refunds on rejection/cancel, exact
Queue transfer into one intent output, and exact proposer return on
CancelIntent/ExpireIntent. Fees and optional single change are ADA-only and
funded only by the auxiliary input; governed ADA and native assets cannot pay
fees or enter change. Min-ADA is evaluated only by an authoritative ledger
parameter snapshot and ledger-equivalent minimum-UTxO calculation, so
Pre-Prod remains INCONCLUSIVE until that snapshot exists.

`TRANSITION_TOPOLOGY.json` gives finite exact regular/reference/collateral
inputs, outputs with and without change, assets, datums, redeemers, signers and
script witnesses for Genesis, Create, Vote, both finalizations, Cancel, Queue,
CancelIntent and ExpireIntent, plus one-over-limit mutation references.
`DATUM_VECTORS.json` contains dependency-free canonical Plutus-data bytes for
AuthorityDatumV1, ProposalDatumV1 with 0/1/8/9 records, IntentDatumV1 and
VoteLockRecordV1; every accepted datum is at most 896 bytes and the ninth voter
is rejected by the voter cap. `ACCEPTANCE_MATRIX.json` is closed, uniquely
identified, mutation-attributable, topology/vector-referenced and every R7
row has `evidence_status: pending`. A compiled governance harness is required
only in M3.2b.

R7 does not change the current source-reality boundary: the checked-in
`governor.ak`, `timelock.ak` and `types.ak` remain legacy, current Execute and
ExecuteIntent paths remain implementation blockers, and no funding, Deposit,
Execute or Pre-Prod admission is authorized. The existing R6 provenance review
also identified that the legacy isolated verifier accepts a nonvolatile
trailing lock-byte mutation because it excludes `aiken.lock` from its temporary
snapshot comparison. R7 does not silently claim that defect fixed; it remains a
separate provenance blocker for review/remediation.



## 12. R9 closed machine and provenance enforcement

R9 is a local remediation of the independent R8 findings. The R7 artifacts
now enforce exact nested schemas, strict scalar types, canonical widths and
reference resolution, while pre-F05 ExecuteIntent rows remain reject-only and
reference the implementation boundary rather than a fabricated topology.
Manifest version 3 binds the raw authoritative lock hash and a normalized
nonvolatile digest; only the two approved decimal etag timestamp lexemes may
vary in isolated Aiken runs. An independent address/value/topology oracle and
fail-closed ledger-parameter preflight are recorded under
docs/remediation/m3_2a_r9/. This remains design evidence: current Cardano
validators are unchanged, min-ADA and applied budgets remain pending, F01-F05
remain open, M3 remains OPEN and M3.2b is not authorized. Independent
M3.2a-R10 review is required.


## 13. M3.2a-R11 closed-contract remediation

R11 corrects only the R10 design-contract findings. Enterprise address headers are low-nibble network formulas with explicit boundary vectors; target-domain prefixes are length-derived; all normative R7 artifacts have frozen raw digests and direct semantic-validation seams; topology and acceptance rows are semantically frozen with pre-F05 ExecuteIntent rejection; and the independent oracle has strict schemas and lifecycle/value/address coverage. This remains design-only and does not authorize M3.2b or alter Cardano validators, sources, provenance, deployment or production behavior.
