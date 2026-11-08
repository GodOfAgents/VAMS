# M3.1b-R3 finite insurance-custody amendment

Date: 2026-09-25
Status: locally implemented; independent R4 review required
Amends: `docs/remediation/m3_1a_r1/ADR.md`

## Decision

The historical M3.1a ADR remains unchanged. This amendment replaces its
64-claim assumption with a finite, jointly enforceable state contract:

| Dimension | Accepted maximum | Product consequence |
| --- | ---: | --- |
| Guardians | 5 | Policy initialization supports at most five custody guardians. |
| Pending claims | 2 | At most two claims may be live concurrently; a third must wait for settlement/removal. |
| Approvers per claim | 5 | Every approver must still be unique and present in the capped guardian set. |
| Transaction inputs | 16 | Larger transactions cannot operate the fund. |
| Transaction outputs | 16 | Larger transactions cannot operate the fund. |
| Non-lovelace assets in each authenticated fund value | 16, including the singleton state asset | A fund carrying more assets is rejected before transition logic. |
| Serialized `FundDatumV2` | 896 bytes | Oversized integer/address/list encodings cannot create an accepted but unbudgetable state. |
| State asset name | 32 bytes, non-empty | Matches the ledger asset-name bound and rejects an empty identity parameter. |
| Claim/evidence/key hashes | 32/32/28 bytes | Existing fixed bounds remain unchanged. |

All state and value caps apply at genesis and to both the consumed and
continuing state. Transaction shape is checked before input/output searches;
serialized state and policy bounds precede claim-wide validation. `Deposit`
continues to reject unconditionally, so its variable proof fields never enter
an accepted state. The prior 64-claim design limit is intentionally
incompatible and is reduced to two after applied-script/state sweeps.

Genesis now uses the existing five-minute bound: both endpoints must be
finite, `upper >= lower`, and `upper - lower <= 300000` milliseconds.
Unbounded, reversed and wider ranges reject.

## Measurement basis

The fully applied Plutus V3 program was evaluated with maximum accepted
guardian/approver state, last-position input, 16 inputs, 16 outputs, 16
non-lovelace fund assets, and the most expensive pending-claim arrangements.
Observed maxima are recorded in `REVIEW.md`. The local evidence inventory has
no provenance-bound Cardano Pre-Prod protocol-parameter snapshot; therefore
this slice records evaluator units and sizes but makes no network-admission,
funding or deployment claim. Independent R4 must retain that limitation.

## Security and invariants

The compiled public mint/spend entrypoint, not a helper surrogate, is exercised
with complete Plutus V3 contexts. Deposit remains disabled pending F05. INV-2
yield enforcement remains separate and unchanged. INV-10 is preserved because
`bridge_proof` and `payload_hash` remain separate fields and authorize nothing.
INV-1 and INV-3 through INV-9, plus mock-mode behavior, are unchanged.
