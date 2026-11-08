# F05.2a Amendment R2 — Acyclic validator binding and genesis key possession

Status: proposed owner-directed contract amendment; independent semantic review required before candidate source transfer.
Scope: only the Cardano authority singleton bootstrap. R4 and Amendment R1 remain in force except where this text is more specific.

## 1. Fixed bootstrap output value (R1 retained)

The unique authority-state output contains exactly 10,000,000 lovelace and
exactly one authority singleton NFT, and no other native asset or token. The
authority output's lovelace cannot fund transaction fees, collateral, or
change. Those are funded by separate inputs and outputs. The amount is a fixed
testnet contract value, not insurance capital and not a VAMS conversion.
No later-transition value rule is inferred. If a provenance-bound current
Pre-Prod parameter snapshot shows the serialized output requires more than
10,000,000 lovelace, stop and obtain another versioned amendment; do not change
the amount implicitly. Until that snapshot is available, Pre-Prod minimum-ADA
admission is INCONCLUSIVE, while offline tests may proceed.

## 2. One-way applied state-validator binding

The F05.2a state validator is the reviewed bootstrap-era validator whose spend
entrypoint unconditionally rejects. It has **no applied parameters**. Its
exact Plutus V3 bytes and 28-byte Cardano ScriptHash are derived using the
pinned Aiken compiler, canonical project source, and locked dependencies. The
empty parameter list is part of this contract, not an omitted deployment
choice.

The bootstrap policy must not accept a caller-provided state credential. Its
reviewed source contains the expected state-validator ScriptHash as a
generated, forward-provenance-bound constant. The minting policy requires the
sole authority-state output's payment credential to equal that exact hash and
requires no stake credential. Before the policy source constant is finalized,
the exact state validator must be compiled and applied with the empty parameter
list; the resulting program bytes and hash are recorded. After inserting that
hash, compile the full project again and prove the state validator bytes/hash
are unchanged. A mismatch stops the build.

The allowed dependency graph is strictly:

```text
canonical state-validator source + pinned Aiken + aiken.lock
    -> state-validator Plutus V3 program bytes (zero parameters)
    -> state-validator ScriptHash (28 bytes)
    -> generated expected-hash constant in bootstrap-policy source
    -> bootstrap-policy program
    -> policy parameters (genesis OutputReference, ordered five keys)
    -> applied policy hash / singleton asset policy ID
    -> genesis output carrying that singleton at the state-validator address
```

There is no edge from policy source, policy parameters, policy ID, singleton
asset name, or genesis output back into the state validator. The policy MUST
not be a state-validator parameter; the state-validator hash MUST NOT be
caller-supplied as a policy parameter; and the policy ID MUST NOT enter the
state-validator source or parameters. This is the required acyclic resolution
of the policy/validator hash relationship.

Forward provenance records, at minimum: canonical source file hashes,
Aiken/compiler identity, lock hash, complete applied-parameter bytes (empty
for the state validator and exact seed/key CBOR for the policy), unparameterized
and applied state-validator program bytes/hash, generated source constant,
policy program bytes/hash, applied policy parameters/hash, singleton asset
name, and final output payment credential/address. Hash computations and
parameter application are independently reproduced by the reviewer. No
private key is included in source or evidence.

The mint policy is parameterized by the deployment's canonical seed reference
and ordered public-key set. Aiken cannot introspect an externally declared
canonical parameter manifest, so a different seed/key application is a
different policy instance that may be constructible on-chain. This contract
does not claim global exclusivity across arbitrary script applications. The
deployment's one accepted authority is the exact policy ID derived from the
canonical R4 seed/key CBOR recorded in forward provenance; every off-chain
consumer and future validator must pin that policy ID and reject a singleton
under any other policy. A self-consistent alternate policy application is not
the accepted deployment instance. The reviewer must independently re-encode
the canonical policy parameters and reproduce its policy ID before any
deployment admission.

## 3. Five bootstrap proofs of possession

Genesis minting requires exactly five 64-byte ordinary Ed25519 signatures.
Signature item `i` is verified by the corresponding key item `i` in the
strictly increasing, raw-byte-lexicographic five-key set; signatures are not
independently sorted or re-associated. All five checks must succeed at the
public mint-policy entrypoint. A missing, extra, malformed, reordered, or
invalid proof rejects. This bootstrap-only 5-of-5 proof-of-possession
requirement does not change R4's later certificate threshold of exactly
3-of-5, nor its separate 4-of-5 emergency threshold. Later transitions remain
disabled.

Each signature is over this exact 279-byte message, with fixed-width unsigned
big-endian numeric fields and no implicit terminator beyond the explicit NUL
already included in the domain prefix:

| Order | Field | Width | Value/encoding |
|---|---|---:|---|
| 1 | Domain | 34 bytes | ASCII `VAMS-F05-AUTHORITY-GENESIS-POP-V1` followed by `00`; hex `56414d532d4630352d415554484f524954592d47454e455349532d504f502d563100` |
| 2 | Chain code | 1 byte | `02` (Cardano, per R4) |
| 3 | Chain ID | 8 bytes | unsigned BE zero |
| 4 | Network magic | 4 bytes | unsigned BE `1` (Pre-Prod, per R4) |
| 5 | Address network ID | 1 byte | `00` (per R4) |
| 6 | Seed transaction ID | 32 bytes | exact `OutputReference.transaction_id` bytes |
| 7 | Seed output index | 2 bytes | unsigned BE, exact R4-bounded `OutputReference.output_index` |
| 8 | Applied state-validator ScriptHash | 28 bytes | exact result in §2 |
| 9 | Key count | 1 byte | `05` |
| 10 | Ordered committee keys | 160 bytes | concatenation of the five exact 32-byte R4 keys |
| 11 | Initial authority epoch | 8 bytes | unsigned BE zero |

The message is the concatenation of these fields. It is passed directly to
ordinary Ed25519 verification (not Ed25519ph, not a prehash, and no implicit
hash). The pinned Plutus V3 stdlib exposes
`aiken/crypto.verify_ed25519_signature`; implementation must use the audited
builtin and prove all five verifier calls in compiled-entrypoint tests.

### Network-interface limitation

The pinned Plutus V3 `Transaction` and `Address` context types expose neither
the executing ledger's network magic nor the address header's network ID.
Accordingly, on-chain code can bind the proofs to the fixed R4 Pre-Prod network
tuple above but cannot independently establish which ledger is executing the
policy. The policy/seed/key deployment identity must therefore be pinned by
forward provenance and externally admitted only on Pre-Prod. This amendment
does not claim that the validator context itself can distinguish Cardano
networks. If F05.1-R4 requires on-chain rejection based on the actual executing
network, this amendment is insufficient and implementation must stop for an
interface/design correction; it must not invent a context field.

## 4. Preserved R4 decisions and F05.2a boundary

The seed OutputReference and exact policy parameters remain deployment-bound.
The initial datum stays the R4 canonical version-3 state at epoch zero, with
the five distinct ordered keys, 3-of-5 normal threshold, active status, and
canonical empty pending rotation. Exactly one policy singleton is minted and
exactly one state output is created at the derived state-validator credential.
All other assets are absent. This amendment enables no spend, rotation, pause,
certificate acceptance, replay/outbox, wrapped mint/burn, Polygon, or off-chain
behavior. Insurance Deposit, Slash activation, and ExecuteIntent remain
disabled.

## 5. Review and implementation gates

An independent reviewer must PASS the graph, field encoding, Plutus crypto
availability, and the network-interface limitation before any candidate
source is transferred to the canonical checkout. Implementation then requires
compiled Plutus V3 public-entrypoint success and isolated mutations for every
message field, each key/signature pairing, missing/invalid proofs, credential
rebinding, policy/hash drift, and exact-value/cardinality constraints. No
staged AST, JSON, or structural check is compiled proof. Two pinned isolated
builds must produce identical blueprint and program hashes; canonical
`aiken.lock` and unrelated dirty files remain byte-identical.

This amendment does not close F05 or F01-F03. F04 remains remediated, M3
remains open, Pre-Prod admission remains inconclusive pending its parameter
snapshot, and promotion remains NOT READY.
