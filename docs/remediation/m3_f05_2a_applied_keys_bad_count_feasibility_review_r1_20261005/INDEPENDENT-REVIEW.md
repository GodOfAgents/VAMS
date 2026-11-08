# Independent feasibility review: applied_keys_bad_count (R1, 2026-10-05)

## Review outcome

**PASS for the narrow design finding; no execution or case credit.** The R5 six-key negative is rejected by two independent exact-five shape checks. No one-guard mutant can make it pass while preserving the other production guard. R5 contains only five proof entries for six applied keys and marks proof-of-possession as infeasible for the malformed parameter. Keep the case PENDING pending a narrowly scoped amendment and newly reviewed fixtures.

This was a read-only source/fixture audit. No tests, transaction simulator, or network execution were run. No status change or mutation, original-policy, ledger-admission, or live-network credit is supported. Readiness remains NOT READY; deployment and gated activations remain disabled.

## Evidence inspected

- R5 family manifest, `docs/remediation/m3_f05_2a_applied_parameter_family_r5_20261005/FAMILY-MANIFEST.json`, SHA-256: `3d43acdc634f700c3bc709bae03a7869f26c35cd59941d4be0d94a89ca5c094e`.
- Case manifest, `docs/remediation/m3_f05_2a_applied_parameter_family_r5_20261005/applied_keys_bad_count/FIXTURE-MANIFEST.json`, SHA-256: `ccb48ebdf61669d2cd07e06ebd62832b72bc4f06f92e5e476c74c7a0479174c3`.
- Negative transaction SHA-256: `b605624a10e16c3047b039ebbe8325c26bf72f2d8a3522f2b4da85b206c8ac76`.
- Negative applied-policy bytes SHA-256: `267881bd77331855ae56cccf4b5a7220072841881bb1d9128fb4eb794543ec67`.

The manifest preserves case ID `applied_keys_bad_count` and assertion `compile_with_six_keys_and_matching_datum`. It records six 32-byte, strictly increasing applied keys and the matching six-key datum (both vector SHA-256 `08124a692a07be0284fe0b9ea33355f17a3642df4d42945b3e23245a2257ffa5`), but the Mint[0] redeemer contains only five proofs. The manifest explicitly marks proof status `infeasible-for-malformed-parameter`, says exactly five 32-byte keys/proofs are required, and has no one-guard mutant control.

R5 records two valid body-bound ephemeral funding signatures, ADA/native-asset conservation, no persisted private keys, and alternate applied policy ID `4fa737ebb0a7133d941fc952c7fdc865272722096943196b2094fbc6`. Its five-key positive-control fixture was not executed; these byte properties do not establish runtime acceptance or rejection.

## Source predicates and one-guard analysis

1. `cardano/lib/vams/f05_authority.ak:76-93`: `valid_initial_authority` calls `valid_ordered_keys(initial_keys)` at line 89 and checks state ordered-key equality at line 90.
2. `cardano/lib/vams/f05_authority.ak:268-282`: `valid_ordered_keys` matches exactly five entries at lines 270-275, checks 32-byte lengths, checks strict order at lines 276-279, and returns False for other shapes at lines 280-281. The six-key vector fails this check despite matching the datum and being sorted.
3. `cardano/lib/vams/f05_authority.ak:135-159`: `valid_bootstrap_proofs` matches exactly five keys at lines 141-143 and exactly five proofs at lines 143-145; other shapes return False at lines 155-157. This independently rejects six keys, regardless of signatures.
4. `cardano/validators/f05_authority_policy.ak:61-69`: Mint[0] calls `valid_initial_authority` before `valid_bootstrap_proofs` (line 69). Both exact-five predicates apply at the intended compiled mint entrypoint.
5. `cardano/lib/vams/f05_authority.ak:119-123,284-295`: `authority_genesis_pop_preimage` invokes `encoded_ordered_keys`; that helper encodes only five entries and returns empty bytes for other list lengths. A six-key signature over this computed message therefore does not show the six keys encoded in the message. Applied parameters bind the vector synthetically, but this helper cannot support a normative six-key PoP claim.

A one-guard accepted mutant is impossible: changing only `valid_ordered_keys` leaves `valid_bootstrap_proofs` rejecting six keys; changing only `valid_bootstrap_proofs` leaves `valid_initial_authority` rejecting through `valid_ordered_keys`. Bypassing either caller-level check alone leaves the other rejection. Five signatures for six keys also cannot establish a complete per-key proof set. This is compound arity rejection, not an isolated one-guard mutation.

## Narrow proposed evidence-contract amendment

If authority retains the applied-parameter C decision, add a versioned, case-specific `compound-arity` path preserving the original case ID and assertion. Do not call it a one-guard mutation or weaken either production predicate. Require:

- independent byte review of exact alternate policy, parameters, Mint[0] transaction, datum, redeemer, and manifests;
- an executed and independently reviewed accepted five-key positive control with correct policy binding;
- a rebuilt six-key negative with six ephemeral signers and six signatures, independently verified against the exact generated case message; explicitly disclose that the helper encodes no ordered key bytes at six keys, so the signatures earn no normative PoP credit;
- body-bound ephemeral funding witnesses, applied-policy/V3/mint binding, and value conservation;
- compiled Mint[0] rejection, with attribution recorded as the conjunction of both exact-five predicates, not an isolated first-failure condition;
- independent review of the exact controls, signatures, bindings, conservation, simulator capture, and source attribution before any synthetic transaction-simulator credit.

If the required standard is a verifier-valid, key-vector-bound PoP under the production helper, it cannot be met for six keys without changing protocol semantics. Do not change production source to force fixture acceptance; keep the original case PENDING/non-creditable. Any eventual credit under this narrow route is synthetic and alternate-policy scoped only, with no original-policy, full-ledger-admission, mutation-suite, or live-network credit by inference.
