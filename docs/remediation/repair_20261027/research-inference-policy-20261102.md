# Direct inference policy boundary

Source52 engineering decision, 2026-11-02. NOT READY. This closes an unbound
compatibility route; it neither supplies authentic inference nor removes that
requirement from the full A--G dual-chain program.

## Inspected research

**Defeating Prompt Injections by Design**, Debenedetti, Shumailov, Fan, Hayes,
Carlini, Fabian, Kern, Shi, Terzis and Tramèr; arXiv:2503.18813v1, 24 March 2025.
Inspected sections 3/3.1, 4.2/4.3 and 6 in the
[versioned paper](https://arxiv.org/pdf/2503.18813v1); section 4.2 also in its
[HTML rendering](https://arxiv.org/html/2503.18813v1#S4.SS2).

CaMeL attaches provenance/read permissions to values and checks information-flow
policy when tools execute. Its threat model assumes a trusted user prompt and
uncompromised memory. It excludes some text-only deception and discusses
side-channel limitations. This is a preprint inspected here, not an independently
reproduced VAMS result. No paper benchmark, interpreter or implementation artifact
was installed or executed. A pinned reproduction code artifact is UNKNOWN.

Decision: adopt enforcement placement before input release/tool dispatch; reject
transferring its guarantees to VAMS. Our runtime-mode guard is not CaMeL's
interpreter, provenance graph, authenticated action policy or universal conscience.

## Current VAMS defect and interface limits

The exact source52 baseline has 6,766 paths and manifest SHA-256
`6837abab132169bf006f956119d095d1214f4741a64042ac81303b3f738a6034`.
`neuron/sdk/bittensor_subnet.py:query_miner` can read wallet/provider state and
pass `prompt` to `bt.Synapse`, then `dendrite.query`, without action-bound admission.
The manifest-covered Python/Markdown caller inventory finds only the public
definition and existing tests. This proves a reachable SDK interface, not an
actual deployed application caller or production incident.

`ActionContextV1` validates canonical shape/encoding; constructing a value creates
no authority. Existing effect canary/coordinator/scope/grant protocols target
object effects and retain local/native qualification restrictions. They cannot
be relabeled as inference authorization. No authenticated inference admission
consumer is connected to this SDK method. Reviewed provider/issuer identities,
the fixed qualifying workload and its verification relation remain UNKNOWN.

## Compatible containment and required production implementation

The unbound `query_miner` interface rejects live modes before time, credentials,
provider or prompt access. Missing/invalid runtime modes reject centrally. Caller
booleans or context-shaped dictionaries create no exception. Controlled
test/local/demo calls preserve their existing response/failure interface; read-only
provider observations remain available. During such a non-live call, effective
runtime configuration is rechecked before dendrite creation, prompt release and
dispatch. A changed configuration prevents the next stage; it cannot undo an
already completed locally permitted stage. Arbitrary provider errors, including
errors using public safety exception types, remain bounded provider failures.

This is fail-closed containment pending authentic implementation, not readiness
acceptance or permanent deferral of inference. Production needs a typed consumer
that authenticates actor root, provider/workload/model, host/domain, logical intent,
input/output commitments, integer budget, current governed policy/authority epoch,
nonce and expiry before credentials or input release. It must use authentic
admission, provider cooperation/deduplication and separate effect/settlement receipts;
the selected inference relation must bind the frozen workload and action context.
An unqualified proof/backend remains blocking, without automatic trust fallback.

## Falsifiable acceptance

- Direct live and unknown-mode calls: local observer counters for wallet/provider
  access, metagraph, prompt conversion/release, dendrite and query all stay zero.
- Non-live callback configuration drift: the next protected stage never occurs.
  If Synapse already consumed a locally allowed input, record that fact rather
  than asserting global absence of effects.
- Provider-origin public safety errors: no raw diagnostic escapes and no success
  is fabricated. Local controlled positive calls still dispatch exactly once.
- Authentic positive inference remains a separate required campaign through
  admission, exact fixed proof relation, effect receipts, restart/reconciliation
  and settlement, including all wrong-root/model/domain/epoch/output cases.

The first three checks use local collaborators and are not operationally separate
observation. An actual provider/observer campaign, approved native runner/full CI,
privacy review and both-chain assurance remain required. INV-1--INV-10 enforcement
is unchanged; no supply/reward/fee, session signing, TEE root or bridge trust rule
is weakened. Trace primary F12/F16 and the existing T23/T27/T33 requirements.
