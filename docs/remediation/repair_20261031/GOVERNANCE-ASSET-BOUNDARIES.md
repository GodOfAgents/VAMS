# Proposed Cardano governance asset-boundary cases

Status: SOURCE PREPARATION ONLY. No Aiken or ledger execution; no acceptance credit.

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

The selected design authenticates exact asset identities, immutable proposal terms
and current authority nonces. The frozen matrix's ASSET_ENCODING labels omitted
individual mutation definitions. These proposed refinements test malformed domain,
identity, width, endian, field-order and truncation encodings against the existing
v2 byte contract. One case targets the Queue intent;24target proposal identifiers.

| Parent ID | Action | Proposed malformed identifier | Shared callers |
| --- | --- | --- | --- |
| asset_boundary_00 | Queue | intent_legacy_domain | 6 |
| asset_boundary_01 | Vote | proposal_legacy_domain | 3 |
| asset_boundary_02 | Queue | proposal_domain_without_nul | 6 |
| asset_boundary_03 | Vote | proposal_authority_policy_substitution | 3 |
| asset_boundary_04 | Queue | proposal_authority_asset_substitution | 6 |
| asset_boundary_05 | Vote | proposal_policy_substitution | 3 |
| asset_boundary_06 | Queue | proposal_epoch_little_endian | 6 |
| asset_boundary_07 | Vote | proposal_epoch_width8 | 3 |
| asset_boundary_08 | Queue | proposal_nonce_width4 | 6 |
| asset_boundary_09 | Vote | proposal_nonce_substitution | 3 |
| asset_boundary_10 | Queue | proposal_proposer_substitution | 6 |
| asset_boundary_11 | Vote | proposal_description_substitution | 3 |
| asset_boundary_12 | Queue | proposal_action_substitution | 6 |
| asset_boundary_13 | Vote | proposal_payload_substitution | 3 |
| asset_boundary_14 | Queue | proposal_target_substitution | 6 |
| asset_boundary_15 | Vote | proposal_target_without_length | 3 |
| asset_boundary_16 | Queue | proposal_target_wrong_length | 6 |
| asset_boundary_17 | Vote | proposal_quorum_width4 | 3 |
| asset_boundary_18 | Queue | proposal_quorum_little_endian | 6 |
| asset_boundary_19 | Vote | proposal_deadline_little_endian | 3 |
| asset_boundary_20 | Queue | proposal_deadline_width4 | 6 |
| asset_boundary_21 | Vote | proposal_action_payload_swapped | 3 |
| asset_boundary_22 | Queue | proposal_authority_asset_omitted | 6 |
| asset_boundary_23 | Vote | proposal_epoch_omitted | 3 |
| asset_boundary_24 | Queue | proposal_digest_truncated31 | 6 |

Caller and fixture boundaries

Queue checks cover queue, authority_spend, governor_spend and proposal/receipt/
intent policy_mint helpers. Vote checks cover vote, governor_spend and receipt
policy_mint. These are shared source function calls with literal caller arguments;
they are not compiled/applied validator wrappers or cross-script ledger results.
Every caller has an unchanged valid control. Each mutant has an ordinary positive
construction/conservation test in addition to its expected-failure tests.

Mutants rebind receipt names, proposal-state commitments, intent names, mint/burn
and held assets consistently to avoid manufacturing value deficits as the reason
for rejection. Python arithmetic and native source construction checks do not
establish ledger-valid history, actual signatures, minimum UTxO, collateral,
current network/genesis, budgets or native expected behavior. The31byte malformed
proposal name remains within the ledger token-name limit but violates this v2
identifier contract. The longest fixture names remain32bytes; no33byte ledger-
invalid name is substituted for testing the protocol's binding checks.

Frozen v1/v2 encodings, seven original vectors, amended upper-bound time vector,
production Aiken sources, insurance custody repair and package locks are unchanged.
Older width/timing campaign hashes retain their earlier source identity. Their
test prefix is preserved; a new full source hash identifies this extended campaign.
Do not relabel old blueprints or infer compiled identities from source hashes.

Qualification still requires exact remaining81-obligation/caller coverage, actual
Aiken1.1.21 compilation/tests, independently recomputed applied programs/policies,
signed ledger-equivalent transactions under current Pre-Prod parameters, resource
budgets, actual3-of-5custody/48hours and independent review. No authority migration,
new bridge trust model, ordinary economics activation or deployment is introduced.
