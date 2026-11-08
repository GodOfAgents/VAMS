# F05.2a validator-hash one-guard mutant candidate r1

Status: **candidate; independent byte review required; tx-sim not run; no credit**.

The disposable policy source changes only the bootstrap-message validator-hash argument from the canonical state-validator hash to the R4.1 alternate hash cd repeated 28 bytes. The canonical state-validator constant and output-address guards remain unchanged. The mutant is separately compiled, and its policy ID, mint, and Plutus V3 witness are rebound.

The mutant transaction reuses the exact reviewed negative PoP message, signatures, public parameters, and raw input references. Its authority output remains at the canonical state-validator address; only the proof-domain argument changes in the source. Fresh ephemeral funding keys sign the final rebound body. The previously accepted synthetic positive control and its run/review records are copied byte-identically. No private key material is persisted.

All mutant evidence remains PENDING until independent exact-byte review and authorized execution. There is no original-policy, full-ledger-admission, Pre-Prod, or live-network credit. F05/M3 remains open.
