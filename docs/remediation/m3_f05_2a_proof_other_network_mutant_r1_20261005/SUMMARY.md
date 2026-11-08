# F05.2a network-magic one-guard mutant candidate r1

Status: **candidate; independent byte review required; tx-sim not run; no credit**.

This package preserves case r2_signature_for_other_network and the reviewed R21 negative proof-message and five proof signatures. A disposable source copy changes only the expected four-byte network_magic constant in authority_genesis_pop_preimage from 1 to 0. The validator source in the canonical checkout is unchanged. The mutant is recompiled and its new policy ID, mint entry, and Plutus V3 witness are rebound into a synthetic transaction; funding keys are ephemeral, and their signatures bind the final transaction body.

All five message-bound proof signatures are the exact R21 negative signatures. This candidate is pending independent review. It has not been executed. It grants no original-policy, full-ledger-admission, Pre-Prod, or live-network credit; F05/M3 remains open and deployment and gated activations remain disabled.
