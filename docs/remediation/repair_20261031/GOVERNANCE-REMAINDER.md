# Proposed remaining governance acceptance definitions

Status: SOURCE PREPARATION ONLY. Native/ledger/budget/independent review NOT_RUN.

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

The established authenticated-singleton and backed-vote design is retained. This
campaign fills previously unnamed acceptance labels with explicit source cases;
it does not amend production policy or claim historical intent was recovered.

| Frozen parent ID | Proposed action/mutation scenarios | Shared caller rejection cases |
| --- | --- | --- |
| maximum_width_datum | eighth_vote:maximum_width | 3 |
| time_before | vote:negative_window, cancel:negative_window, finalize_passed:before_deadline, finalize_rejected:before_deadline | 13 |
| time_after | vote:after_deadline, cancel:after_deadline | 7 |
| create_topology_one_over | create:inputs_exact, create:inputs_global, create:outputs_exact, create:outputs_global, create:assets, create:datum_bytes, create:signers | 21 |
| create_datum_mutation | create:datum_version | 3 |
| create_timing_boundary | create:create_at_deadline | 3 |
| vote_topology_one_over | vote:inputs_exact, vote:inputs_global, vote:outputs_exact, vote:outputs_global, vote:assets, vote:datum_bytes, vote:signers | 21 |
| vote_datum_mutation | vote:datum_version | 3 |
| finalize-passed_destination | finalize_passed:destination | 2 |
| finalize-passed_topology_one_over | finalize_passed:inputs_exact, finalize_passed:inputs_global, finalize_passed:outputs_exact, finalize_passed:outputs_global, finalize_passed:assets, finalize_passed:datum_bytes, finalize_passed:signers | 14 |
| finalize-passed_datum_mutation | finalize_passed:datum_version | 2 |
| finalize-rejected_topology_one_over | finalize_rejected:inputs_exact, finalize_rejected:inputs_global, finalize_rejected:outputs_exact, finalize_rejected:outputs_global, finalize_rejected:assets, finalize_rejected:datum_bytes, finalize_rejected:signers | 28 |
| finalize-rejected_datum_mutation | finalize_rejected:datum_version | 4 |
| finalize-rejected_timing_boundary | finalize_rejected:before_deadline | 4 |
| cancel_topology_one_over | cancel:inputs_exact, cancel:inputs_global, cancel:outputs_exact, cancel:outputs_global, cancel:assets, cancel:datum_bytes, cancel:signers | 28 |
| cancel_datum_mutation | cancel:datum_version | 4 |
| queue_topology_one_over | queue:inputs_exact, queue:inputs_global, queue:outputs_exact, queue:outputs_global, queue:assets, queue:datum_bytes, queue:signers | 42 |
| cancelintent_topology_one_over | cancelintent:inputs_exact, cancelintent:inputs_global, cancelintent:outputs_exact, cancelintent:outputs_global, cancelintent:assets, cancelintent:datum_bytes, cancelintent:signers | 21 |
| cancelintent_datum_mutation | cancelintent:datum_version | 3 |
| cancelintent_timing_boundary | cancelintent:empty_window | 3 |
| expireintent_topology_one_over | expireintent:inputs_exact, expireintent:inputs_global, expireintent:outputs_exact, expireintent:outputs_global, expireintent:assets, expireintent:datum_bytes, expireintent:signers | 21 |
| expireintent_datum_mutation | expireintent:datum_version | 3 |
| executeintent_destination | executeintent:destination | 2 |
| executeintent_topology_one_over | executeintent:inputs_exact, executeintent:inputs_global, executeintent:outputs_exact, executeintent:outputs_global, executeintent:assets, executeintent:datum_bytes, executeintent:signers | 14 |
| executeintent_datum_mutation | executeintent:datum_version | 2 |
| executeintent_timing_boundary | executeintent:before_execute | 2 |

Byte-profile basis: the official [Plutus Data encoder source](https://plutus.cardano.intersectmbo.org/haddock/latest/plutus-core/src/PlutusCore.Data.html)
uses64-byte chunks for longer byte strings. The local reference models that rule;
native construction tests must measure the actual approved runner's output.
No native byte count or applied cost is inferred from this source reference.
Shared-caller preparation follows existing v2 transaction predicates; the public
[Aiken pattern matching documentation](https://aiken-lang.org/language-tour/custom-types)
describes alternative patterns used by the test helpers. It is language reference,
not evidence that this file parses or compiles with the pinned approved toolchain.

Acceptance prerequisites

1. Review each proposed interpretation against the frozen parent requirement;
   retain discrepancies and refine cases without rewriting historical evidence.
2. On a specifically authorized runner, compile every changed source and pass
   ordinary construction, valid-caller and resource-byte controls before crediting
   any expected-failure case. Unexpected control failure blocks the campaign.
3. Test the actual applied validator wrappers/policy identities, authentic custody
   signatures and valid current Pre-Prod protocol/genesis/resource parameters.
4. Demonstrate reachable prestates, exact conservation, minimum UTxO, fees,
   collateral and full ledger equivalence; measure applied CPU/memory/size limits.
5. Revalidate insurance custody separately; obtain independent native governance
   and security review. No supplied named case alone closes a parent obligation.

No installs/downloads, dependencies, R28, Aiken/Slot08, providers, external
qualification services, real keys/signing/funds/roles or deployments were used.
Only public synthetic fixture identifiers and local source/reference checks.
All required broader CI/scanner/privacy/operations and dual-chain evidence remain.
