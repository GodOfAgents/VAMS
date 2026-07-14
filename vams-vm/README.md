# VAMS VIR-Core reference foundation

This directory contains the additive, pre-testnet reference foundation for the
VAMS Intermediate Representation (VIR-Core). It is not a deployed virtual
machine, settlement system, SP1 integration, or RISC Zero integration.

The current foundation provides:

- dependency-free canonical protocol types;
- restricted deterministic CBOR using positional arrays only;
- domain-separated Keccak-256 identifiers;
- a bounded, integer-only reference interpreter;
- cross-client golden vectors and conformance checks;
- fail-closed SP1 and RISC Zero adapter placeholders.

VIR-Core preserves the Polygon/Cardano dual-host architecture. Every state
domain has one explicit `HostAuthority` and authority epoch at a time. Polygon
Amoy and Cardano Pre-Prod are both supported authorities; neither is a
universal canonical host.

The VIR v1 canary applies authority-specific access rules. Polygon Amoy may
use `READ`, `CONSUME`, `RESERVE`, or `ACCUMULATE`; `RESERVE` still requires a
nonzero fencing token. Cardano Pre-Prod permits only `READ` and `ACCUMULATE`.
Cardano `CONSUME` and `RESERVE` fail with `AccessDenied`. The shared Cardano
golden vector therefore contains one `READ` and one `ACCUMULATE`, both without
fencing tokens.

Semantic receipts intentionally exclude settlement transaction hashes, block
metadata, prover metadata, and bridge proofs. Those values use the separate
`SettlementMetadata` type.

`SettlementMetadata` uses the pre-deployment `vdso-settlement-v2` wire schema,
an exact ten-element restricted-CBOR array. VIR-Core remains v1; only the
unlaunched settlement envelope was version-bumped to prevent v1 payloads from
being accepted under the stronger host-binding semantics:

```text
[
  schemaVersion,
  receiptHash,
  domainAuthorityBinding,
  sourceHost,
  destinationHost,
  sourceChainReference,
  sourceTransactionHash,
  settledAtHeight,
  bridgeProofHash,
  payloadHash
]
```

`sourceHost` and `destinationHost` are explicit and `destinationHost` must equal
the host in `domainAuthorityBinding`. A local/same-host settlement requires the
hosts to be equal and the complete settlement-specific tuple
`[sourceChainReference, sourceTransactionHash, settledAtHeight,
bridgeProofHash, payloadHash]` to be zero. A cross-host settlement requires a
nonzero source-chain reference, source transaction, bridge-proof hash, and
payload hash, a positive finalized height, and distinct source and destination
hosts. The bridge-proof and payload hashes must be distinct, preserving INV-10.
Invalid or partially populated tuples fail with
`InvalidSettlementMetadata` (`44`).

## Canonical signable intent

`UnsignedIntent` is the exact payload covered by an authorization envelope. Its
restricted-CBOR representation is a 16-element positional array in this order:

```text
[
  schemaVersion,
  actorRoot,
  domainAuthorityBinding,
  nonce,
  validUntilHeight,
  programId,
  workflowDefinitionHash,
  accesses,
  inputCommitment,
  expectedOutputCommitment,
  evidenceRoot,
  sidecarRoot,
  signatureSuite,
  executionTier,
  maxExecutionUnits,
  maxSettlementCost
]
```

Hashes are 32-byte byte strings. Heights, limits, and `maxSettlementCost` are
canonical CBOR unsigned `u64` values. `signatureSuite` is `1` for secp256k1 and
`2` for secp256k1 plus ML-DSA-65. `executionTier` is `0`, `1`, or `2`. Every
intent with a nonzero `maxSettlementCost` or a `CONSUME`, `RESERVE`, or
`ACCUMULATE` access requires Tier 2 and suite `2`; a read-only, zero-cost intent
may use a lower tier. The decoder and type constructor reject tier downgrades
with `TierSignatureMismatch`. The runtime also rejects a host gas limit above
`maxExecutionUnits` and rejects an output that does not match
`expectedOutputCommitment`.

This foundation binds the required signature suite but does not yet contain
secp256k1 or ML-DSA signature verifiers. A caller must not treat a decoded
`UnsignedIntent` as authorized; the future authorization-envelope verifier must
validate every signature required by the bound suite before economic execution.

Consensus identifiers use raw concatenation without a NUL terminator or
implicit length prefix. `programId` binds the VIR version as a two-byte
big-endian integer:

```text
programId = Keccak256(
  ASCII("VAMS:PROGRAM:v1") ||
  u16be(virVersion) ||
  Keccak256(rawBytecode) ||
  hostFunctionSetHash ||
  gasScheduleHash ||
  arithmeticPolicyHash
)

intentId = Keccak256(
  ASCII("VAMS:INTENT:v1") || canonicalUnsignedIntentCBOR
)
```

## Supported VIR v1 policies

The reference interpreter has one supported policy triple. Each commitment is
Keccak-256 over the exact ASCII bytes shown below, without a terminator or
length prefix:

```text
hostFunctionSetPolicy = "VAMS:VIR:v1:host-functions:none"
hostFunctionSetHash   = 926aa059fa0db9477ba813b969d5c1dcf92fbcdbf7e00d6ceeec13ceef33e860

gasSchedulePolicy = "VAMS:VIR:v1:gas:push=1,load-input=1,add=2,sub=2,mul=3,div=3,eq=2,dup=1,drop=1,halt=0"
gasScheduleHash   = ea7983ef0e10911d248e354efebafd3b05a479e50ba5f0cfa46890f74034f773

arithmeticPolicy = "VAMS:VIR:v1:arithmetic:u64,checked-overflow,checked-underflow,zero-divisor-reject"
arithmeticPolicyHash = e6231804a0697191feee14abb9b5806f393a2725a10c0fc92f0159ee79c893a5
```

`Program::new` rejects any other policy commitment with
`UnsupportedPolicyCommitment`; callers cannot relabel the hardcoded opcode,
gas, or arithmetic behavior under attacker-selected hashes.

Run the local checks from this directory:

```text
cargo fmt --all -- --check
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
```
