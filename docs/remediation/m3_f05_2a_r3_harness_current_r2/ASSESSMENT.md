# F05 public-harness R3 canary revalidation

Date: 2026-10-03
Status: PASS for the two synthetic canaries only; independent review PASS.

## Scope and result

Revalidated the current public harness source and its existing `--tx-sim-r3-canaries` mode using the pinned Aiken 1.1.21+42babe5 binary and the current frozen manifest, applied-policy artifact, and transaction vectors. The exact network-isolated command and source/fixture digests are in `RUN.json`; raw stdout, stderr, process exit, and parsed result are adjacent.

The valid fixture reached the exact applied policy at Mint[0], was accepted (simulator child exit 0), and cleaned up. The invalid-signature fixture also reached that policy, was rejected by compiled evaluation (simulator child exit 1), and cleaned up. Both wrapper exits were 0.

## Evidence boundary

This confirms that the current local harness mode correctly routes these two exact frozen transactions through the R3 snapshot runner and classifies the outcomes. This is synthetic local transaction-simulator evidence only. It adds no registered F05 negative-case or mutation credit; the full `unconditional_success` criterion requiring the baseline positive plus every negative remains pending. It establishes no ledger admission or live-network behavior. Counts remain 45/55 negative cases and 18/21 mutations. No source, validator, fixture, contract, credential, ledger, or network state was changed.
