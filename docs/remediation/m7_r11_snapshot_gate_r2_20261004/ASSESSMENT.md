# M7 R11 current-source provenance refresh - 2026-10-04

Status: ACCEPTED for scoped local source-to-blueprint reproducibility.

The v7 current-forward manifest now binds 16 Cardano source files, three project inputs, two cached dependency trees, and the generated 26-program Plutus blueprint. The two independently run, network-isolated Aiken builds produced byte-identical blueprint bytes. The integrated current-forward verifier passed twice, and the focused R11 suite passed.

The refresh changes the compiled identity for the registry mint, spend, and else programs. This updates source/build provenance only; it does not accept the F04 identity anchor design, demonstrate ledger admission, or authorize deployment.

The separate strict Aiken warning gate using `aiken check --deny` remains unverified. Readiness is NOT READY. Deposit, Slash activation, ExecuteIntent, and deployment remain disabled.
