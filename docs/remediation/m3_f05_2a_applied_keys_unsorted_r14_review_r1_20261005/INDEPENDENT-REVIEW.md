# Independent review: applied_keys_unsorted R14 positive control

Decision: PASS for the recorded synthetic positive-control execution only.

Reviewed without executing the simulator or changing case status/classification.

## Exact evidence identities

- Attempt: docs/remediation/m3_f05_2a_applied_parameter_sim_attempt_r14_20261005/RUN.json
- Attempt SHA-256: 9d40df445cca42f37aab07bb221cc54535b95d70d79e6c64a236def6c2ea6aa1
- R5 family manifest SHA-256: 3d43acdc634f700c3bc709bae03a7869f26c35cd59941d4be0d94a89ca5c094e
- Case manifest SHA-256: bf84b96865bb89860a25f1cbf6a9799419a17b7b71bf6249c21fabe128a27c96
- R5 family and case SHA256SUMS verification: PASS.
- Immutable runner SHA-256: 3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c.

## Findings

The R14 argv selects the R5 applied_keys_unsorted positive-control transaction and matching raw inputs/outputs, with applied policy ID 0be38709988ea180df3b89c467e7606350038b19bcc2113164d90ae6. Exact fixture hashes agree between RUN.json and the checksummed case manifest:

- transaction: 4e941601f87f2ffd61a2895af5abff51a386349fff1576b2cca0c2619c9ea942
- raw inputs: 4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe
- raw outputs: 5197dd961bfb903bfa4cac0a59c5453d2b73620e96a26a85afdba94198388c46

The case manifest positive-control applied policy ID is the same 0be387...d90ae6 identity. R14 reports that identity in all three target-binding fields: expected policy, compiled script hash, and the sole mint policy ID. It records script_accepted, target script invoked, zero wrapper/child exits, and clean cleanup (child reaped, process group empty, snapshot descriptors closed). This is a positive acceptance control at the intended Mint[0] entrypoint.

The case manifest records five PoP proofs, two valid body-bound ephemeral funding signatures, ADA and native-asset conservation, and private_keys_persisted false. Conservation values balance: 17,000,000 input lovelace equals 10,000,000 authority output + 1,000,000 fee + 6,000,000 sponsor change. The positive parameter vector is five unique 32-byte keys in strictly increasing order and matches the parameter-bound datum. The case remains explicitly synthetic.

## Scope and limits

This review supports only the R14 local synthetic positive-control result. R14 contains no negative execution and no mutation execution; neither is credited. It provides no original-policy, full-ledger-admission, Cardano Pre-Prod, or live-network evidence. Raw simulator stdout/stderr and external attestation are not retained, as the attempt record states. The case remains PENDING until the remaining required case evidence and acceptance review are complete. No status or classification was changed by this review.
