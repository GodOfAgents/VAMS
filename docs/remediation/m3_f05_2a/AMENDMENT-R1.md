# F05.2a Amendment R1 — Authority Genesis Output Value

Status: owner-authorized implementation clarification; pending independent review.
Applies only to the Cardano authority singleton bootstrap defined by F05.1-R4.

## Normative bootstrap value

The unique initial authority-state output must contain exactly 10,000,000
lovelace and exactly one authority singleton NFT. It must contain no other
native assets or tokens. The authority-state output's lovelace may not be
diverted to transaction fees, collateral, or change. Bootstrap fees,
collateral, and change must be funded by separate inputs and outputs. This
fixed testnet value is not insurance capital and has no VAMS conversion
meaning.

The bootstrap transaction must conserve this output value exactly. There is
no implication here for ADA values or value-conservation rules in later
authority transitions; those transitions remain disabled in F05.2a.

## Minimum-UTxO deployment condition

Cardano minimum ADA is determined from the serialized output and active ledger
parameters. Before Pre-Prod admission, the exact serialized authority output
must be checked against a provenance-bound current Pre-Prod protocol-parameter
snapshot. If 10,000,000 lovelace is insufficient, stop and obtain a separately
versioned design amendment; do not adjust the bootstrap amount implicitly.
Without that parameter snapshot, network admission remains inconclusive. This
condition does not prevent offline implementation tests.

## Scope and precedence

This amendment fills only the genesis authority-output value rule omitted by
F05.1-R4. R4 continues to govern the authority singleton policy, seed binding,
canonical initial datum, key order, thresholds, status, and pending state.
Every later transition and every other F05.1 rule remains unchanged.

Owner decision recorded 2026-09-30. Independent review is required before
implementation proceeds.
