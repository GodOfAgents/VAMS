# F04 production implementation R1

Status: BLOCKED / REVALIDATED_OPEN.

The accepted R5/R6 design requires a 14-field AgentDatumV1, versioned redeemers, exact authority/action/evidence references, seed-bound identity derivation, exact continuation/burn/value topology and closed bounds. Current production Cardano sources remain a legacy 8-field AgentDatum, legacy redeemers, an unparameterized registry validator and an NFT policy that permits arbitrary mint names and unlinked negative burns. plutus.json confirms the legacy constructor surface.

Agent C independently identified the constructor/redeemer incompatibility and NFT policy gap. Agent A made no production edits. Agent B's incomplete pending-interface scaffold was removed. No public handler rows were executed and no compiled mutation, build, provenance or deployment claim is made.

Evidence package: /home/GodOfAgents/vams-evidence/m3-f04-impl-r1-20260928T113454Z-829ab544571f
SHA256SUMS: 229561643e62a24ba780052b6d8877587ca8fbb40daf173aaad70e0ea621a81b

F04 remains REVALIDATED_OPEN; F01-F03/F05 remain REVALIDATED_OPEN; M3 remains OPEN; Deposit and ExecuteIntent remain disabled; Pre-Prod is INCONCLUSIVE; promotion is NOT READY. INV-1 through INV-10 and mock behavior are unchanged.
