# Independent review - F04 canonical identity-policy anchor gate

Source review result: BLOCKED. Registry spend trusts the policy ID supplied in the datum; it has no canonical policy ID anchor. An alternate mint policy can satisfy generic mint/datum/output predicates. The prior policy-ID-equals-registry-hash rule is the rejected Option-B coupling.

F05 authority inspection found no F04 policy ID in its state, disabled F05 state spends, and accepted F05 evidence limited to its own singleton. No F04 anchor can be inferred from F05.

Candidate architecture review result: FAIL as specified. A global immutable singleton holding one identity policy ID is incompatible with the approved `agent_nft(bootstrap_ref)` parameterization. Each consumed bootstrap ref yields a different applied policy ID; a single fixed policy instance also consumes its seed for one mint only. The owner must choose a revised identity model: shared policy ID with per-identity seed in the redeemer, or per-identity authority anchors/lifecycle. See ANCHOR-DECISION.md.

The pinned Aiken binary was present outside default PATH. Its network-isolated current-source baseline exited 0 with 122/122 Aiken tests (115 unit, 7 property). No paired evaluator, ledger, or live evidence is accepted.

Record-integrity review: PASS. The corrected toolchain, source hashes, current-source test scope, latest STATUS/HANDOFF, and readiness boundary were independently checked; SHA256SUMS verified. This record review does not accept implementation. F04 implementation remains blocked pending the owner’s model decision and a separately reviewed design.


## Refined per-identity candidate review

Conditional security review: the dependency graph is acyclic only if shared anchor scripts/policy IDs are fixed independently, the registry pins those stable IDs, and registry hash is applied to the per-identity identity policy before an anchor datum commits that resulting ID. Conditions and remaining owner decisions are recorded in ANCHOR-DECISION.md. The two earlier model alternatives remain unapproved; no code/tests/evaluator/ledger/live evidence follows.


## Independent uniqueness/signature clarification

Final wording distinguishes: (a) reissue of the same seed-bound anchor token is rejected because its seed input has already been consumed; (b) a different seed can create a distinct pre-registration anchor for the same identity tuple unless stateful uniqueness is added; and (c) exactly one matching anchor reference is required per mint/registration transaction, not globally. Anchor issuance uses owner+3-of-5 committed guardian signatures; RegisterAgent independently uses five transaction-bound guardian signatures plus required owner/controller signers.


## Decision-memo consistency correction

Option B now states that anchor references may be reused across transactions while the immutable anchor UTxO cannot be spent or mutated; different anchor seeds may create distinct pre-registration anchors for one identity tuple. The anchor token name includes its consumed seed, so only reissue of that same token is forbidden. The owner’s duplicate-anchor choice and the shared anchor policy/lifecycle remain design gates.
