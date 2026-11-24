# Verifiable Memory Module (VMM) interface specification

**Status:** DRAFT design proposal, version 0.1. Not implemented. No code,
schema, test vector or deployment exists for anything in this document.
Readiness is NOT READY.
**Last verified:** 2026-11-24 against `neuron/sdk/semantic_mmu.py`,
`neuron/services/registry_client.py`, `neuron/composer/models.py`,
`neuron/payments/intent_v1.py`, `neuron/object_grant_v1.py` and
`neuron/da_router.py` at commit `63b717c`
**Implements the direction of:** [GCA_ACCEPTANCE.md](../remediation/GCA_ACCEPTANCE.md)
("Modularity and memory boundary") and research-watch items RW-015, RW-017,
RW-018 and RW-019 in
[RESEARCH_WATCH_UPDATE_20261005.md](../remediation/RESEARCH_WATCH_UPDATE_20261005.md).

## 1. Principle

**VAMS standardizes and economically coordinates verifiable memory services.
It does not dictate memory engineering.**

The VMM is the common envelope through which any memory provider takes part in
VAMS: **store → retrieve → verify → compose → pay**. It fixes what can be
checked about a memory (origin, integrity, permissions, processing, freshness,
lineage, payment). It never fixes how a provider represents, indexes,
retrieves, compresses or evolves memory.

**Verifiable is not true.** A VMM check establishes that bytes and declared
lineage match their commitments and that the right authority produced them. It
does not establish that the content is true, relevant, well retrieved or
aligned. Truthfulness and retrieval quality are evaluated separately (section
9).

## 2. Responsibilities

| Layer | Owns | Must not |
|---|---|---|
| VAMS core | Identity, authorization (grants), settlement, canonical protocol state (authority, policy versions, nonces, obligations, evidence roots, receipts) | Store cognitive memory content |
| Neuron / DBOS Heart | Durable execution of every VMM operation as a workflow step, idempotency, checkpoint and recovery, duplicate-effect prevention | Treat memory content as authorization input |
| Memory Service Blocks | Working, episodic, semantic, graph and procedural memory; retrieval, compression, folding, evolution | Mutate protocol state, grants, nonces or evidence roots |
| VMM (this spec) | The envelopes, receipts, verification levels and conformance tests that bind the three layers | Mandate an algorithm, storage layout or embedding model |

Protocol safety state and cognitive memory stay separate. A memory record, a
summary of memory, or a service output can never grant, widen or renew
authority (GCA_ACCEPTANCE negative case "Malicious memory or service output").

## 3. Actors

- **Memory principal:** the root identity that owns the memory (actor root,
  the same root that INV-6 binds TEE attestations to).
- **Agent workflow:** a Neuron workflow acting for the principal under a grant.
- **Memory provider:** a registered Service Block that stores and serves
  memory and signs receipts.
- **Curator:** an optional Service Block with read-only, resource-scoped
  probing rights that proposes updates (RW-019). It never commits directly.
- **Verifier:** any party checking a receipt or record. A verifier assigned
  for payment or dispute purposes must be independent of the provider.
- **GCA policy engine, Sentinel, Composer, x402 facilitator:** see section 7.

## 4. Data model

All digests are 32-byte SHA-256 values with a domain-separation prefix, in the
style already used by `neuron/object_grant_v1.py`
(`b'VAMS:OBJECT-GRANT:v1\0'`) and `neuron/payments/intent_v1.py`. All-zero
digests are rejected, as `hash32` does in `neuron/effect_protocol_v3.py`.
Canonical encoding is fixed-order 32-byte words, never JSON, so Python,
Solidity, Rust and Aiken can reproduce the same digest from published vectors.

Proposed domains:

| Domain tag | Object |
|---|---|
| `VAMS:MEMORY-RECORD:v1\0` | `MemoryRecordV1` |
| `VAMS:MEMORY-CONTENT:v1\0` | content commitment |
| `VAMS:MEMORY-RECEIPT:v1\0` | `MemoryReceiptV1` |
| `VAMS:MEMORY-DERIVATION:v1\0` | derivation edge |
| `VAMS:MEMORY-REVOCATION:v1\0` | `RevocationReceiptV1` |

### 4.1 `MemoryRecordV1`: the envelope around one memory item

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | int | 1 |
| `record_id` | bytes32 | Digest of the canonical encoding of every other field |
| `principal_root` | bytes32 | Owning actor root |
| `provider_id` | bytes32 | Registered provider that holds the content |
| `service_block_id` | bytes32 | Registry entry, links to the declared memory policy |
| `memory_class` | enum | `WORKING`, `EPISODIC`, `SEMANTIC`, `GRAPH`, `PROCEDURAL`, `ARTIFACT`, `OTHER`. A label for policy and matching only; implies no format |
| `content_commitment` | bytes32 | Domain-separated digest of the exact stored bytes (ciphertext if encrypted). Salted when the plaintext is guessable (section 8) |
| `content_size` | int | Bytes, for pricing and limits |
| `schema_id` | bytes32 | Provider-declared content format identifier, opaque to VAMS |
| `source_trust_class` | enum | `PROTOCOL` (from authenticated protocol state), `PRINCIPAL` (authored by the principal), `PROVIDER_DERIVED`, `EXTERNAL_UNTRUSTED`, `MODEL_GENERATED` |
| `taint` | bitset | Labels such as `UNTRUSTED_INPUT`, `PERSONAL_DATA`, `SECRET_ADJACENT`, `REVOKED_ANCESTOR`. Taint is monotone: derived records inherit the union of their parents' taint |
| `parents` | bytes32[] | `record_id`s this record was derived from (empty for originals) |
| `derivation_op` | enum + bytes32 | `ORIGINAL`, `SUMMARY`, `FOLD`, `PATCH`, `MERGE`, `EMBEDDING`, `EXTRACTION`, plus a digest of the operation's declared parameters |
| `write_grant` | bytes32 | Digest of the grant that authorized the write (an `object_grant_v1`-style grant) |
| `policy_root`, `policy_version` | bytes32, int | Policy in force at write time |
| `state_version` | int | Monotone per (principal, provider, logical key); prevents rollback and replay |
| `created_at`, `valid_until`, `revalidate_after` | int | Unix seconds. Freshness bounds |
| `retention_class`, `revocation_epoch` | enum, int | Retention rule and the principal's revocation epoch at write time |
| `workflow_id`, `step_id` | bytes32 | The DBOS workflow and step that performed the write (idempotency) |

The record holds no content and no private provenance text. Content lives with
the provider. Only commitments may ever leave the provider, and only after the
privacy review in section 8.

### 4.2 `MemoryReceiptV1`: one per operation

Every operation in section 5 returns a receipt signed by the provider's
registered key:

| Field | Meaning |
|---|---|
| `operation` | `STORE`, `RETRIEVE`, `VERIFY`, `COMPOSE`, `REVOKE` |
| `request_digest` | Digest of the exact request, including the grant |
| `record_ids` | Records written, read or produced |
| `result_commitment` | Digest of the returned bytes (for `RETRIEVE` and `COMPOSE`) |
| `provider_id`, `provider_key_id` | Signer identity |
| `metering` | Bytes stored, bytes served, compute units, as declared pricing units |
| `idempotency_key` | Derived from `(workflow_id, step_id, attempt)`; the same key never yields two different effects |
| `observed_at` | Provider clock, bounded by the request's validity window |
| `evidence_level` | Highest level in section 6 the provider claims for this operation |
| `signature` | Provider signature over the receipt digest |

A receipt is the unit that verification, Sentinel review, x402 payment and
dispute all refer to. Payment is bound to receipts, never to free-form claims.

## 5. Operations

Each operation is one durable DBOS step. The idempotency key is fixed before
the provider is called, so a crash after the provider acts and before the
checkpoint reconciles to the same receipt instead of a second write or a second
payment (GCA_ACCEPTANCE negative case "Crash after effect, before checkpoint").

| Operation | Pre-checks (fail closed) | Provider does | Returns |
|---|---|---|---|
| **Store** | Valid unexpired write grant for this principal, provider and memory class; GCA allows the write; Service Block memory policy permits persistent writes (`PERSISTENT_MUTATING_REQUIRES_REVIEW` requires an approved review); `state_version` is exactly previous + 1 | Persist bytes in its own format | `MemoryRecordV1` + receipt |
| **Retrieve** | Valid read grant; record not revoked; GCA allows the read and the intended sink; freshness inside bounds, or the result is labelled stale | Run its own retrieval | Records + content + receipt with `result_commitment` |
| **Verify** | None beyond rate limits | Nothing new: the verifier recomputes commitments, checks lineage, signatures and grants (section 6) | Verification report with the level reached |
| **Compose** | Every input record readable under the grant; output class and sink allowed | Summarize, fold, merge, patch or embed | New record whose `parents`, `derivation_op` and inherited `taint` are mandatory |
| **Pay** | Receipt verifies at the level the price was agreed at; amount inside the grant's budget; no prior payment for the same idempotency key | — | x402 payment intent bound to the receipt digest (section 7.4) |
| **Revoke** | Principal or authorized policy action | Block future use; report known dependents | `RevocationReceiptV1` (section 5.1) |

Rules that apply to every operation:

- A deny, unknown or stale-policy answer produces zero effects, checked by an
  observer, not just an error code.
- Composition cannot raise trust. A record derived from any
  `EXTERNAL_UNTRUSTED` or `MODEL_GENERATED` parent cannot be
  `PROTOCOL` or `PRINCIPAL` class, however many times it is summarized or
  persisted (RW-015 acceptance test).
- Curators emit proposed `PATCH` records; a separate writer policy promotes
  them (RW-019).

### 5.1 Revocation and contamination (RW-018)

Revoking a record raises the principal's `revocation_epoch` for that record and
walks the derivation graph (`parents` edges) to mark known descendants with
`REVOKED_ANCESTOR` taint. Retrieval of a revoked or revoked-ancestor record is
denied or explicitly labelled, depending on policy. Replay restarts from an
authorized checkpoint taken before the contaminated input.

`RevocationReceiptV1` lists the revoked record, known dependents found, caches
or plans invalidated, and dependents that could not be resolved. It
distinguishes access revocation, key destruction and deletion attempts. **None
of these proves deletion from a copy already exported to a malicious party,
and the receipt must say so.**

## 6. Verification levels

| Level | Name | What it establishes | What it does not |
|---|---|---|---|
| V0 | Unverified | Nothing | — |
| V1 | Integrity | Returned bytes match `content_commitment`; record digest matches its fields | Who wrote it; whether the commitment itself was swapped. The current `MemoryPage.verify()` is below V1, because its hash is stored next to the content it checks |
| V2 | Signed provenance | V1 + provider-signed receipt + valid write grant + consistent lineage and `state_version` | That the provider's processing was correct; availability |
| V3 | Anchored | V2 + record digest (or a Merkle root over a batch) committed to an external log: DA layer or settlement chain | Content truth; correct processing |
| V4 | Processing evidence | V3 + TEE attestation (bound to the root identity, INV-6) or a proof covering the declared derivation operation | Truth of the inputs; semantic quality |

A price, a GCA rule or a composer requirement names the minimum level it needs.
A provider may not claim a level its evidence does not support, and a verifier
reports the level actually reached, not the level claimed.

## 7. Integration with surrounding systems

### 7.1 GCA: policy on memory reads, writes and use

Three decision points per operation: **pre-write**, **pre-read** and
**pre-use** (before retrieved content enters a model context or an effect).
Each decision takes only independently authenticated inputs: grant, policy
version, record metadata (class, trust, taint, freshness). It never takes the
memory content that produced the proposal (RW-017). The answer is `ALLOW`,
`DENY` or `UNKNOWN`; only `ALLOW` proceeds. A policy update with pending work
follows explicit revoke, grandfather or re-evaluate semantics.

### 7.2 Sentinel: detection, not authorization

Sentinel consumes receipts and records, never raw private content unless the
principal grants it. Detection signals:

- `state_version` gaps, rollback or forks for one logical key;
- receipts whose commitments do not match a later retrieval (silent mutation);
- writes without a matching grant, or outside the grant's scope;
- trust escalation along a derivation chain;
- sudden taint spread or provider behaviour drift.

Statistical findings are telemetry until calibrated on held-out data. Sentinel
can trigger quarantine or a review; it cannot change a record or a grant.

### 7.3 CHC + Composer: matching agents to memory providers

Add a `MemoryServiceRequirement` alongside the existing `cognitive_requirements`
(`neuron/composer/models.py:170`). It is distinct from today's `MemorySpec`,
which is RAM in GB:

- memory classes needed;
- minimum verification level;
- maximum retrieval latency, retention and residency limits;
- price ceiling per pricing unit.

Providers declare the classes, levels and prices they support. Scoring reuses
the existing $S_{cog}$ shortfall form, applied to declared memory capabilities:

$$S_{mem} = 1.0 - \frac{1}{|D_{req}|}\sum_{d \in D_{req}} \max(0.0,\ Req_d - Profile_d)$$

A provider below a hard requirement (memory class, minimum level, residency) is
excluded, not down-scored. Declared profiles are claims; matching does not
verify them. Conformance results (section 10) and Sentinel history should feed
the profile before it is trusted.

### 7.4 x402: paying providers

Pricing units: bytes stored per period, bytes served, compose compute units,
and verification. A payment intent references the receipt digest it pays for,
using the existing `PaymentIntentV1` fields (`service_block_id`,
`registry_terms_hash`, `operation_id`, `attempt_id`, `nonce`) in
`neuron/payments/intent_v1.py`. One idempotency key settles at most once.
Payment never substitutes for the pre-checks: economic rejection does not
replace pre-effect enforcement.

### 7.5 DA commitments and private audit evidence

Only record digests, or Merkle roots over batches of them, may be published,
through `neuron/da_router.py` or a settlement contract, and only after the
privacy review in section 8. Content, personal provenance and raw memory are
never published. The bridge rule INV-10 applies by analogy: the anchor proof
and the memory payload stay separate fields and are verified separately.

## 8. Privacy

- Commitments over guessable content (short facts, names, yes/no answers) are
  dictionary-attackable. Salt them with a per-record secret held by the
  principal or provider, and record the salting scheme in `schema_id`.
- Personal data carries the `PERSONAL_DATA` taint and follows the retention
  class. Publishing any commitment derived from personal data needs the
  Privacy Lead's approval, which does not exist yet (T33 is blocked).
- Receipts expose metering and digests, not content.

## 9. Truthfulness and retrieval quality: out of scope, required elsewhere

The VMM proves custody and lineage. It does not score content. Truth,
relevance, retrieval accuracy and staleness of facts need their own evaluation:
curator revalidation against the authorized environment (RW-019), task-level
evaluation suites, and Sentinel quality telemetry. A model's confidence score is
never treated as verification.

## 10. Conformance

A provider conforms when it passes, without revealing its internal algorithm:

1. Cross-language digest vectors for every object in section 4.
2. Store → retrieve round trip reaching V2.
3. Unauthorized write, expired grant and wrong-principal write: zero effects.
4. Rollback and replay attempts with old `state_version`: rejected.
5. Summary of an untrusted record: output keeps `EXTERNAL_UNTRUSTED` lineage
   and taint.
6. Crash between provider effect and checkpoint: one record, one payment.
7. Revocation: known dependents are marked; unresolved dependents are listed.
8. Two different implementations (for example a vector store and a graph
   store) both pass 1–7 with different internal representations (RW-015).

## 11. Current code against this spec

| Spec element | Today | Gap |
|---|---|---|
| `MemoryRecordV1` | `MemoryPage` in `neuron/sdk/semantic_mmu.py:59-80` has address, content, SHA-256, tier, free-text provenance | No principal, grant, trust class, taint, lineage, state version or freshness |
| Integrity | `MemoryPage.verify()` rehashes JSON against a hash stored beside it | Below V1; replace with commitments held outside the content store |
| Receipts | None | Whole section 4.2 |
| Memory policy | `ServiceBlockMemoryPolicy` in `neuron/services/registry_client.py:68-74` | Keep; enforce at Store |
| Durable steps | DBOS config and V5 effect journal exist, not integrated | Wire VMM operations as steps |
| GCA decision points | Comment only (`semantic_mmu.py:278`) | Section 7.1 |
| Sentinel | Hardware memory-bandwidth benchmark only | Section 7.2 |
| Composer | `cognitive_requirements` exists; `MemorySpec` is RAM | Add `MemoryServiceRequirement` |
| x402 | Payment intent and local ledger exist, not wired to memory | Bind intents to receipts |
| Anchoring | L0 anchor never written; DA adapters mock-only | V3 needs a real anchor path and privacy approval |

The existing S-MMU, SIRA, HIPIF, EvoMem and V(m) code becomes one provider
implementation behind the VMM, with its parameters and tests kept. It stops
being "the" memory system.

## 12. Proposed delivery order

Each phase ends with its tests passing and an independent review. No phase
changes INV-1 to INV-10 enforcement.

1. **Envelopes and vectors.** Python codec for sections 4.1, 4.2 and
   revocation, plus JSON Schema under `docs/audit/schemas/` and cross-language
   vectors. No runtime change.
2. **Reference provider.** Wrap the current S-MMU as the first provider,
   reaching V2 locally. Conformance tests 1–6.
3. **GCA and memory-policy gates** at Store, Retrieve and pre-use. Negative
   tests with an effect-count observer.
4. **Second provider** with a different representation, to prove
   interchangeability (conformance test 8).
5. **Composer matching and x402 binding** behind the restricted-profile
   disablements; local only.
6. **Revocation graph and Sentinel signals.**
7. **V3 anchoring**, only after privacy approval and a non-mock DA path.

## 13. Invariant and policy impact

- **INV-5:** if identity verification for an institutional principal fails or
  is offline, Store and Retrieve fail closed.
- **INV-6:** V4 TEE evidence binds to the root identity, never to a session
  key.
- **INV-10:** anchor proofs and memory payloads stay separate.
- **INV-3, INV-4:** grants issued to session keys for memory operations
  inherit the 24-hour limit and the contract whitelist.
- No mock DA, mock TEE or mock provider may serve a VMM operation in staging or
  production; the existing `runtime_safety` mock rules apply.
- AGENTS.md section 5: persistent memory must be deterministic, schema- and
  version-checked infrastructure state; unreviewed autonomous memory rewriting
  stays forbidden.

## 14. Open decisions for the owner

1. Minimum verification level for the restricted testnet: V2 (signed, local)
   or V3 (anchored, needs privacy approval and a live DA path).
2. Which second memory implementation to use for the interchangeability test.
3. Whether memory payment is in the restricted-testnet scope or deferred.
4. Who holds the salt for content commitments: the principal or the provider.
