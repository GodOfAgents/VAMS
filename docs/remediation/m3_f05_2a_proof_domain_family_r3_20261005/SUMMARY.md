# F05.2a proof-domain other-epoch candidate pair r3

Status: **candidate bytes generated; independent byte review required; tx-sim not run; no case credit**.

This package preserves the original case ID r2_signature_for_other_epoch, its assertion sign_tuple_with_nonzero_epoch, and R4.1 proof-domain decision B. Both fixtures use the same test-only alternate applied policy, seed reference, ordered five-key committee, datum, body, and outputs. The positive proofs sign the exact R2 279-byte message with epoch 0. The negative proofs sign the same message with only the four-byte epoch field changed to 0. Both transactions retain epoch 0 in their applied message domain and transaction semantics.

The package contains public parameter CBOR, exact positive/negative proof-message bytes, compiled applied policy, transaction CBOR, resolved inputs/outputs, and validation evidence. Policy ID, mint entry, and Plutus V3 script witness bind exactly. Five valid Ed25519 proofs bind each message; funding witnesses sign each final body. ADA conservation is 17,000,000 = 10,000,000 + 6,000,000 + 1,000,000, and exactly one authority NFT is minted and preserved. Private keys were generated ephemerally in process memory/anonymous memfds and were not persisted.

No tx-sim or applied-case suite ran. Both controls remain PENDING. This is synthetic alternate-applied-policy evidence only; it grants no original-policy, full-ledger-admission, Cardano Pre-Prod, or live-network credit. The validator, registry, status, and handoff records were not changed. Independent exact-byte review is required before any simulator run.
