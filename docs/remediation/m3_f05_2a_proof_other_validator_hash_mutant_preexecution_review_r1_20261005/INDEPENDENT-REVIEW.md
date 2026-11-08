# Independent pre-execution review: validator-hash one-guard mutant

Review status: PASS for byte integrity and pre-execution mutant control. This does not establish that the mutant accepts in tx-sim; no simulator was run. Mutant acceptance and the negative case remain PENDING until execution and result review.

Reviewed package: docs/remediation/m3_f05_2a_proof_other_validator_hash_mutant_r1_20261005/r2_signature_for_other_validator_hash/

## Source mutation and build

All case and family SHA256SUMS entries pass. The exact source diff is one expression in f05_authority_policy.mint: the state-validator-hash argument to authority_genesis_pop_preimage changes from state_validator_script_hash to the 28-byte cd literal. The canonical state-validator constant and every output credential/address guard remain unchanged. Canonical source SHA-256 is e9d3ac9cbb14b9e7693dc12430234694c82eb52e61d176e1e39992fb9cbeafa8; patched source SHA-256 is e3d83c99174f0380c61374695209d0ac83ed8f07ed5cb673675a337494be0f23.

The focused test command was:

    bwrap --unshare-net --ro-bind / / --dev-bind /dev /dev --proc /proc --tmpfs /tmp --setenv PYTHONDONTWRITEBYTECODE 1 --setenv PYTHONHASHSEED 0 --chdir /home/GodOfAgents/code/VAMS-testnet /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python -B -m pytest -p no:cacheprovider -v --tb=short scripts/remediation/test_f05_2a_proof_other_validator_hash_mutant_r1.py

Result: 5 passed in 0.27s on Python 3.12.14 / pytest 9.1.1. Test code inspects and verifies bytes/signatures; it does not invoke tx-sim.

I independently compiled the exact one-expression patched source in a temporary copy using pinned Aiken v1.1.21+42babe5 (SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79), with network isolation and the canonical tree read-only. Reconstructed applied parameter CBOR is the same seed and five committee keys as the reviewed negative. Compiled bytes match mutant.applied-policy.cbor exactly, SHA-256 e8da6de647840db9fa387e045b7d3403a4690165dcc00766109fad0ff684a8a1. Derived Plutus V3 policy ID is f69665acd72650e6789b38151419ac429ae83782cfffe45d91496f7b. The compiled state-validator hash remains canonical: b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66.

## Proof, transaction, and controls

- The mutant uses the exact reviewed negative 279-byte proof message and five proof signatures. The message contains cd repeated 28 bytes at offsets 82-109; all five signatures verify against the same ordered, distinct committee public keys. Seed reference and initial-key parameter CBOR match the reviewed negative.
- The mutant transaction mint map uses only the mutant policy ID; the single Plutus V3 witness contains the exact independently recompiled mutant bytes; hashing that witness with the V3 prefix produces the same mutant policy ID.
- The canonical authority output address and datum/state are preserved. Transaction input references, fee, output count, ADA output amounts, authority output lovelace, and state datum remain the reviewed values.
- Policy rebinding necessarily changes the mint/native NFT policy ID, the V3 witness, and the transaction body hash; funding witnesses are freshly generated for the final body. The resolved input-output vector hash also changes because the new funding keys have fresh ephemeral input credentials. The fixture and tests preserve raw input references and verify each credential against its corresponding body-bound funding witness.
- Two final-body funding signatures verify. ADA conservation is 17,000,000 = 10,000,000 + 6,000,000 + 1,000,000 lovelace. Exactly one authority NFT under the mutant policy is minted and preserved in the authority output. No collateral is present.
- Committee and funding private keys are not included in the package. The helper source creates test keys in anonymous memfds and closes them. The previous negative PoP signatures are reused exactly; only funding keys are fresh.
- The copied positive transaction and its accepted run/review records are byte-identical to the prior accepted synthetic positive control under the original applied policy ID 409712d7175aa2f7d372364919d50f55a048b83c7770a646826a1df4. They validate the original positive setup only and do not count as mutant acceptance.

## Boundary and next evidence

The package records tx-sim NOT RUN, status PENDING, mutant_acceptance null, negative_case null, and no original-policy, ledger-admission, Pre-Prod, or live-network credit. This pre-execution review passes the required byte gate and allows the separate mutant execution attempt. Only a successful script_accepted result for this exact mutant transaction, independently tied to its policy ID and V3 witness, can establish this causal control. The negative row remains PENDING until that result is independently reviewed and the one-guard mutant accepts.

No fixture, STATUS, HANDOFF, or classification files were changed by this review.
