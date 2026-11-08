# F05.1-R4 — cross-chain authority, finality, replay, and wrapped-VAMS design

Status: **testnet-only design freeze; no production implementation**  
Supersedes the conflicting R2 contract details after the independent R3 review.  
Specification: `F05.1-R4`; wire/schema version: `4`; protocol domain: `VAMS-F05-R4-V4`.  
Scope: Polygon Amoy (`chainId=80002`) ↔ Cardano Preprod (`network magic=1`, address `network_id=0`).

## Frozen values and versioning

`CONTRACT.json` is the machine-readable normative artifact. Its schemas and
security values are closed; `validate_design.py` rejects any changed value,
missing or unknown key, duplicate JSON key, bool-as-integer, reordered ordered
field array, malformed domain bytes, or unsupported version. The overall R4
contract and rotation-barrier schema is V4; previously frozen V3 action,
certificate, authority, and settlement-ACK messages remain byte-for-byte
unchanged. A change to a hashed/security field requires a new schema/domain
version. The validator's public entry point for an isolated package is:

```bash
python3 validate_design.py --dir /path/to/isolated/design-copy
```

`--contract-only` validates the frozen contract before the R4 vectors are
available. JSON/CBOR serialization is never used as a signed message.

Every cryptographic domain is explicit lowercase `domain_hex` bytes. Existing
V3 certificate, payload, action-ID, authority-state, authority-sync,
destination-effect, settlement-receipt and replay-state prefixes
include their terminal NUL in those bytes. The encoder prepends exactly those
bytes and never appends an implicit terminator. Human-readable labels are
commentary, not hashed data. Action codes are the closed non-boolean integer
enum: 1 `WRAPPED_CREDIT`, 2 `WRAPPED_RELEASE`, 3 `SLASH_AGENT`, 4
`EXECUTE_INTENT`.

R4 supersedes the prior V3 design fingerprint with a new V4 fingerprint and
domain-separated rotation-barrier messages. No V3 state, certificate, or
barrier encoding is reinterpreted as V4.

The source VAMS supply remains `10^27` base units at 18 decimals. Wrapped VAMS
uses 10 decimals and scale `10^8`, so total wrapped supply is `10^19`. Each
mint or burn is positive and no greater than `2^63-1` wrapped units; every
conversion is exactly divisible by the scale. Cumulative `minted`, `burned`,
and `outstanding` counters are checked unsigned 64-bit values, each capped at
`10^19`, with `burned <= minted` and `outstanding = minted - burned`.
Current source escrow balance and each pending source amount are unsigned
128-bit values capped by source supply `10^27`; no lifetime gross counter is
used. No Polygon VAMS quantity is converted to lovelace; `Deposit` remains
disabled.

Because the bridge spans two ledgers, source lock/burn and destination
mint/release cannot be one atomic transaction. For each of exactly four
deployment-bound source streams (Polygon escrow address, Cardano wrapped
policy, Polygon slash emitter, Cardano timelock script hash), at most one
action may be outstanding; callers cannot create stream identities. A pending
record has fixed fields for action ID, serialized stream key, source action
nonce, action kind, source amount, wrapped amount, source transaction ID, a
bounded source-time authority snapshot (epoch, state hash and five ordered
committee public keys), and a closed status (`PENDING_CREDIT`, `PENDING_RELEASE`, `PENDING_SLASH`,
`PENDING_EXECUTE_INTENT`, or derived `DESTINATION_FINALIZED`). State vectors
carry up to four pending records sorted by source-stream key, at most one per
fixed stream, plus one latest-settled action ID per stream. The source-chain
record remains pending until ACK; `DESTINATION_FINALIZED` is only a derived
cross-chain projection when the exact stream/nonce/action/effect tombstone and
finalized receipt match, never an assertion that the source outbox changed. The
source datum's effect commitment is zero; the projection adds the commitment
only by exact join to the destination replay tombstone and signed receipt.
Its stream
key is `chain_code:u8 || chain_id:u64 || network_magic:u32 ||
endpoint_length:u8 || endpoint_bytes`, with 20-byte EVM addresses and 28-byte
Cardano policy/script hashes. Opening is idempotent by action ID after source
finality. The same action alone may retry. Source effect, pending outbox, source
nonce and source event commit atomically; the source transaction does not
advance a finality cursor for its own not-yet-included block. Finality cursors
are replicated by receiving-ledger ownership, not one cross-chain physical
singleton: Cardano stores one cursor for remote Polygon finality and Polygon
stores one cursor for remote Cardano finality. Each receiving-ledger cursor is
shared across its fixed endpoint streams and action directions. The destination
transaction verifies the source-chain certificate and commits the exact
destination effect, replay tombstone, and that ledger's remote-source cursor
atomically. It never writes a cursor for its own included block and never
creates or commits a receipt attesting its own finality. Only after the
destination transaction is included in a finalized destination checkpoint does
the 3-of-5 committee issue the signed receipt outside either chain transaction.
The source ACK verifies that receipt and atomically advances the source ledger's
remote-destination cursor, clears only the matching source outbox, and advances
that stream's bounded last-settled action ID. A failure leaves that stage
unchanged; prior committed stages remain pending and retryable. No cross-chain
rollback or atomicity is claimed. Destination replay retains only the latest
action/effect tombstone per fixed source stream (four maximum); exact next nonce
replaces the prior tombstone atomically with the next destination effect.

The bounded source-backing equation is:

`current_locked_source_balance = (minted - burned) * 10^8 + pending_credit_base + pending_release_base`

The aggregate fields equal the sum of all fixed-stream records still in
`PENDING_CREDIT` or `PENDING_RELEASE`; destination-finalized projections no
longer count because their mint/release effect has committed. The aggregates
must match those records, and every intermediate
operation is checked within the declared u128/counter bounds. This is a
current-balance equation, not lifetime gross accounting. Each chain-local
transition is atomic; no simultaneous cross-chain atomicity is claimed.

`current_locked_source_balance` is the protocol-accounted locked liability,
not raw ERC-20 `balanceOf`. The actual escrow token balance must remain at least
the tracked liability. Unsolicited transfers are surplus: they cannot be
credited, released, or counted as backing without a valid action. The slash
reserve is one deployment-bound ADA-only singleton with checked u64 balance;
overflow rejects, it cannot be withdrawn or rotated in place, and cap exhaustion
requires a separately versioned migration. Every successful Cardano script
transaction also has one ADA-only fee-sponsor input disjoint from protocol state
and collateral. Only its own-address change is returned; the sponsor funds fees,
minimum-UTxO outputs and state top-ups. ADA fees never change wrapped-token
accounting, escrow backing, or slash accounting.

## Authority, finality and replay

The active authority is one authenticated singleton NFT minted from a
deployment-bound genesis reference. Its state has five unique ordered 32-byte
Ed25519 keys, a 3-of-5 certificate threshold, version 3 and monotonic epoch.
Certificate signatures are exactly three distinct current members sorted by
raw public-key bytes. Emergency pause/unpause requires four of five. Rotation
requires three current members, a different five-key set, epoch `+1`, and 48
hours' delay; there is no key-set overlap. Pause increments the authority epoch
immediately, clears only a pending governance transition, and rejects new
economic actions. It does not clear pending bridge outbox/action records, replay
state, or a rotation barrier; those remain frozen and recoverable under the
barrier rules below. Unpause is a separately delayed, four-signature transition
bound to its exact pending hash. Consumed replay state
survives every authority transition. Actual public keys come from separately
controlled testnet custody setup; no keys are fabricated here.

`AuthorityStateV3` has explicit fixed-width big-endian bootstrap, state,
pending-transition and pause preimages, each with a V3 domain prefix and no
implicit terminator. The normative artifact freezes field order, byte lengths,
hash prefixes, status/kind tags and canonical all-zero `NONE` encoding. Rotation
and unpause pending records bind from/to epochs, authorization and activation
times; both activation times are exactly authorization time plus 48 hours.
Pause binds the current state hash/epoch, increments the epoch once and clears
pending transition to the canonical `NONE` encoding. Key order is five distinct
raw keys in lexical byte order; the threshold is three.

The five-member committee is the **finality authority** for this testnet design.
Its 3-of-5 honesty is an explicit trust assumption. This is not trustless
Polygon finality, Mithril verification, or a mainnet bridge. A certificate
states that an event is finalized at a checkpoint and binds that event to a
strictly linked checkpoint cursor. Each source endpoint stream starts at nonce
zero; each receiving ledger has one remote-chain-domain checkpoint cursor,
initialized at height zero with all-zero hashes and shared across every action
endpoint and direction on that ledger. Polygon stores the remote Cardano cursor;
Cardano stores the remote Polygon cursor. No ledger advances a cursor for its
own not-yet-finalized block. The first certified checkpoint has
positive height and zero predecessor. Later heights may skip, but each higher
checkpoint must name the current certified hash as predecessor; same-height
replay is accepted only for identical hash/predecessor, and lower/conflicting
checkpoints reject. The event block cannot exceed the signed checkpoint. The
per-source-stream action nonce is exactly previous `+1`; nonce gaps reject and the
nonce never resets on pause or rotation.

Polygon maintains one deployment-bound `PolygonAuthorityMirrorV3` initialized
from a deployment-pinned Cardano genesis authority state and ordered key set; the
first sync cannot self-authenticate an untrusted mirror. Each update is signed
by the **pre-update mirror committee** K_E and binds the exact prior mirror state
hash/epoch to the finalized Cardano post-state. A rotation from K_E to K_E+1 is
therefore authorized by K_E, then atomically installs K_E+1; post-state keys may
not authorize their own installation. Sync nonce is exactly previous `+1`; an
authority epoch may remain identical only for an identical state or advance
exactly `+1`, never skip. Polygon actions require an active mirror matching certificate
epoch and state hash, synchronized no more than 300,000 ms earlier. Stale or
uninitialized mirror state fails closed and halts Polygon-side liveness. A pause
becomes effective on Polygon only after the mirror-sync transaction finalizes; no
instantaneous cross-chain pause is claimed. The honest quorum stops old-epoch
signing at pause, and already-issued certificates expire within 300,000 ms.

Certificates use SHA-256 and ordinary Ed25519 (not Ed25519ph) over exactly the
321 bytes defined by the ordered field array in `CONTRACT.json`; the authority
state hash is signed as part of the message. All issued,
expiry and chain-time values are unsigned milliseconds/seconds with no rounding.
For Cardano, `issued_at_ms <= validity_lower_posix_ms <
validity_upper_posix_ms < expires_at_ms`, and the interval is at most 300,000
ms. For EVM, `issued_at_ms <= block.timestamp * 1000 < expires_at_ms`. In
either case expiry is after issue and certificate lifetime is at most 300,000
ms. The `action_id` commits to protocol domain, source/destination chain
identifiers, a chain-typed length-prefixed source endpoint (20-byte EVM or
28-byte Cardano), event transaction/log, action code, nonce and canonical
typed-payload hash; it excludes authority epoch so rotation cannot resurrect
a consumed action.

The 321-byte certificate message is distinct from the wire-envelope bound:
exactly three `(signer_id:u8, Ed25519 signature:64 bytes)` entries add 195
bytes, for a 516-byte maximum message-plus-signature envelope. Committee public
keys are resolved from the current authority state and are not repeated in the
wire envelope.

The v3 settlement receipt uses its own `VAMS-F05-SETTLEMENT-ACK-V3` domain and
the exact ordered field layout in `CONTRACT.json` (351 bytes including the
domain prefix). Its 3-of-5 signatures bind the destination transaction/event,
effect commitment, finalized checkpoint, authority epoch/state hash, source
stream key and action nonce; an ACK clears only that matching outbox record.

## Action payloads and transaction topology

The four payload schemas, fixed widths, length prefixes, domains, ordered
certificate fields and exact chain input/output role lists are in
`CONTRACT.json`; extra, missing, cross-rebound, or malformed fields reject.
`bridge_proof` carries the certificate/signatures and `payload_hash` is the
independent digest of the typed action payload. They are never interchangeable
(INV-10).

- `WRAPPED_CREDIT`: Polygon first locks the exact VAMS amount in the dedicated
  escrow and emits one nonce/action-bound event. The Cardano transaction uses
  the authority reference input and consumes the source replay and wrapped
  reserve state. It continues each singleton once, mints only the exact
  signed-int64-bounded wrapped quantity, and sends that quantity to the
  certificate-bound Cardano address. The reserve state records the certified
  lock and mint transition; no lovelace conversion occurs.
- `WRAPPED_RELEASE`: Cardano first burns the exact wrapped quantity and
  atomically updates its reserve/replay state. The Polygon destination verifies
  the exact originating credit lock, remaining amount and certified burn,
  releases only that amount to the signed recipient, and advances the EVM
  replay/lock state atomically. Another lock cannot fund the release.
- `SLASH_AGENT`: Polygon emits one authorized event bound to identity policy,
  asset name, evidence, nonce and epoch. The Cardano destination consumes the
  exact identity state and replay state, references both registry and bridge
  authority, continues the identity NFT with nonce `+1` and exact reduced
  stake, and pays at least one lovelace to a seeded deployment-bound slash
  reserve singleton whose seed is at least current min-UTxO. The continuation
  retains the same NFT/datum, and the remaining agent stake is at least 1 ADA.
  The Polygon committee certificate proves event finality only; authorization
  separately requires `RegistryAuthorityV1.slash_enabled` and the registered
  authorized-slasher signature. A destination reserve output below current
  min-UTxO rejects until separately topped up. The reserve is not `FundDatumV2`
  and is not an insurance deposit. No wrapped mint/burn occurs.
- `EXECUTE_INTENT`: the Cardano source consumes the exact unconsumed intent and
  governance/replay state after its existing delay, terminally consumes that
  intent, and emits the bound event. The Polygon destination executes only the
  exact chain/domain/action entry in a deployment-bound executor registry.
  There is no wildcard, caller-selected target, selector or calldata, and no
  address inference from `target_domain`; an absent or duplicate registry match
  rejects. The executor derives calldata from the fixed schema and signed
  intent ID, action hash, canonical payload hash, policy epoch and nonce. The
  registry is unpopulated by default, so live ExecuteIntent remains disabled
  until a separately reviewed deployment map and executor bytecode/selector
  verification exist. The one mapping in the design vectors is explicitly a
  synthetic test fixture, not a deployment address. The effect commitment binds
  chain domain, target domain, target, selector, action and those signed intent
  values. EVM replay state and the EVM effect commit atomically. Failed
  destination execution leaves its replay cursor unconsumed for exact retry.

Authority is a reference input, never an action-spend input. Every Cardano
script transaction has exactly one ADA-only collateral input, disjoint from
regular and reference inputs and carrying no protocol NFT/non-ADA asset. It
must cover `ceil(tx_fee * collateral_percentage / 100)` under current protocol
parameters; those parameters must permit at least one collateral input. On
success it is not consumed. Phase-2 failure and collateral-return behavior are
ledger-derived; the design does not invent a fixed lovelace constant. EVM
actions have no Cardano collateral input.

Each consumed singleton state NFT has exactly one continuation with the same
identity where the action is nonterminal; terminal intent consumption has no
same-intent asset continuation. Any incomplete or failed chain-local
transaction commits none of its replay, counter, state,
mint/burn, release, slash, or intent effect.

## V4 rotation barrier and pause/resume

V4 adds a separate durable `RotationBarrierV4` singleton on each ledger; it is
not the ordinary authority state's pending-transition field. Rotation is
rejected while any of the four deployment-bound source streams has an open
outbox record. Cardano first commits a `CARDANO_DRAINING` barrier with finalized
Cardano source/destination cutoffs and all four fixed stream watermarks, then
blocks every new Cardano source action. Polygon accepts only a fresh
prior-mirror committee freeze certificate, atomically stores the matching
barrier and its own finalized cutoffs/watermarks, and blocks every new Polygon
source action. Every signed barrier certificate is checked at the consuming
ledger time (`issued_at_ms <= consume_time_ms <= expires_at_ms`) and its lifetime
is at most 300,000 ms. Both ledgers preserve their exact action IDs, source nonces,
payload hashes, source events, pending records, and replay cursors.

While frozen, only an exact pre-cutoff pending action may drain. Its source
event must be at or before that chain's committed source cutoff, and its stream,
nonce, action ID, payload hash, source transaction/event, and source-time
committee snapshot cannot change. Before destination execution the pending
record has the canonical zero effect commitment; it does not predict or
authorize an effect. The destination derives the effect commitment from the
validated action and actual pre-state and atomically commits the effect,
replay tombstone, and event. A committee receipt may attest to that effect
only after a later finalized destination checkpoint. A subsequent source ACK
clears only the exact pending record. Each chain-local stage rolls back only
itself; already committed earlier stages remain durable and retryable. There
is no cross-chain rollback or atomicity claim.

Rotation follows a bilateral finalized drain handshake: Cardano signs a
`CARDANO_READY` receipt only for its empty outboxes; Polygon signs
`POLYGON_DRAINED` only for its empty outboxes and the finalized Cardano-ready
receipt. Only then does the unchanged old committee sign a separate rotation
authorization certificate binding the barrier ID, target authority state and
ordered-key hash, and exact Polygon-drained receipt hash. A Cardano
`ROTATION_AUTHORIZED` singleton transition validates that certificate in its
own bounded transaction interval and commits its hash, signed target/time
fields, exact drained-receipt hash, transaction/event identity, and finalized
checkpoint. Activation consumes that exact finalized singleton; it carries no
replacement authorization certificate. Its `authorized_at_ms` is the Cardano
validity upper bound committed by the authorization transition. The later
activation transaction has its own bounded validity interval; its lower bound
must be at least the scheduled activation time, its upper bound must be no
earlier than its lower bound, and the trusted current time must be within that
interval. Activation is scheduled at exactly
`authorized_at_ms + 172,800,000 ms`, with checked uint64 arithmetic; early or
unbound times reject. The authorization and activation transactions' validity
upper bounds are distinct and are never equated. Cardano emits a fresh
rotation-ready receipt binding the
authorization hash and times; Polygon installs the new mirror only after
consuming that receipt while it remains fresh. Both action-entry gates stay frozen
through installation, so no action may interleave between drain proof,
activation, and mirror install. Barrier receipts bind the exact barrier ID,
authority state, cutoffs, and fixed-stream outbox commitments.
The new authority epoch must equal the current post-resume epoch plus exactly
one; skipped, repeated, or backward epochs reject.

If a pause or mirror revision makes the Cardano prepare certificate stale before
Polygon freezes, recovery reauthorizes only the identical barrier ID, target
key set, Cardano source/destination cutoffs, four stream watermarks and outbox
commitment under the unchanged current committee. The stale certificate is
rejected. Cardano's original snapshot cannot change; Polygon captures its own
cutoffs exactly once on the first successful resumed freeze. Duplicate or old
freeze certificates cannot overwrite state or rewind cutoffs. Source and
destination economic actions remain blocked until that resumed Polygon freeze
has finalized.

Emergency pause suspends but never clears the separate barrier, barrier ID,
cutoffs, watermarks, outboxes, or replay state. While paused, no new source or
destination economic effect is permitted. Only a non-economic ACK for an
effect and finality checkpoint at or before that destination's stored cutoff
may proceed. After unpause and finalized mirror synchronization, the same
barrier remains frozen; the same target committee must be reauthorized under
current authority and the full delay restarts. Only the exact unsettled
pre-barrier action may be re-certified under the unchanged committee and
current authority revision, with a V4 resumed-action certificate binding the
barrier, source cutoff, action-certificate digest, nonce, payload and event.
Repeated pause/unpause cannot rewind a cutoff, reset a nonce, mutate a pending
record, reopen a stream, or resurrect a settled action. Source-time keys remain
the ACK snapshot; execution after resume cannot alter them.

Finalized checkpoints and authority receipts are 3-of-5 committee attestations
under the explicitly centralized testnet committee trust assumption. They are
not trustless light-client proofs or consensus-finality verification. A quorum
can stall progress; the design limits damage through fixed stream bounds,
per-ledger cutoffs, durable freeze and replay, and fail-closed receipt checks,
but does not claim safety against a malicious threshold committee or
cross-chain reorganization beyond that assumption.

## Trust boundary, limitations and gates

Committee certificates are not proof-verifier output, and mock/demo providers
cannot authorize an accepted action. This design is not an implementation or
deployment claim. Current Cardano `Deposit`, registry `SlashAgent`, and
timelock `ExecuteIntent` branches remain disabled/fail-closed pending their
separately scoped implementation and native adversarial transaction tests.
Wrapped escrow, reserve, EVM replay, executor configuration and committee
custody are design requirements only. No transaction, contract funding, role
change, or testnet activation is authorized.

R4 requires exact positive vectors for all four actions and executable,
mutation-sensitive rejection cases. The independent R3 review found the R2 validator
did not close nested schemas/security values and treated named mutations as
references rather than executable tests. R4 closes the design contract only;
F05.2 implementation remains unauthorized until the coordinator’s test,
independent-review, evidence and explicit gate conditions pass.

The V4 vector contract now freezes separate required inventories for action
semantics, authority rotation, and the bilateral rotation barrier. The action
inventory covers quorum and ordered-field/domain integrity; non-boolean action
codes; each action payload schema; chain and proof/payload binding; scale,
decimal, cap, dust, int64/u64 and cumulative arithmetic bounds; epoch
transitions; replay non-resurrection; reserve accounting; cross-action
rebinding; and unknown/duplicate keys. Mutations against immutable
`CONTRACT.json` fields are recorded as contract-fingerprint/tamper checks and
are not represented as semantic-path coverage. Barrier outbox mutations target
the final drain/activation gates, not merely valid pending states during the
drain phase. The public validator requires exactly one case per category at its
closed artifact path; the focused test harness must execute each mutation in a
temporary package through the public CLI and verify rejection.

F05/F01–F03 remain `REVALIDATED_OPEN`; F04 remains `REMEDIATED`; Deposit,
Slash activation and ExecuteIntent remain disabled; M3 is `OPEN`; Pre-Prod is
`INCONCLUSIVE`; promotion is `NOT_READY`. INV-1–INV-10 and mock behavior are
unchanged.
