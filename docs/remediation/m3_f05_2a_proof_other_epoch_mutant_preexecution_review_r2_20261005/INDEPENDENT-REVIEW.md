# Independent epoch-mutant pre-execution byte review r2

Outcome: **PASS for pre-execution fixture integrity only**.
Case: `r2_signature_for_other_epoch`; preserved assertion: `sign_tuple_with_nonzero_epoch`.
Canonical HEAD: `829ab544571f12efe50ecb5740f129c8acb3e16f`.

No blocking finding remains in the reviewed package. The initial source-line metadata discrepancy was corrected by the designated writer to line 122 and both checksum levels refreshed before the successful verification run. This review inspected the corrected package; it did not edit fixture or canonical validator bytes.

## Exact-byte and cryptographic findings

The patch applies cleanly to a disposable copy of current `cardano/lib/vams/f05_authority.ak`. It changes exactly one expression at line 122 in `authority_genesis_pop_preimage`, `bytearray.from_int_big_endian(0, 8)` to `bytearray.from_int_big_endian(1, 8)`. Source SHA-256 before: `657f30dfc0ecb40f50b2c0442b78f4818de1644f540fb68d76cfb2de72cccdd3`; mutant: `5be58f7b06c1e797571b2ad32d107367fbff59dcaa4ce041654519cbc0946eef`. The canonical state-validator hash remains `b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66`.

Independent builds from canonical source and that patched temporary copy, followed by both exact public CBOR parameter applications, reproduced normal and mutant applied program bytes byte-for-byte. Pinned Aiken binary SHA-256 `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79` matches. Normal policy id `704a7ed54317bfa9c9879a9be02d8ae8859e999ce1a04298697d69ad`; mutant id `6f2cfb8a849311c6e6076b466daafe77ae5a95de9b50c62caecfafa4`. For each of the positive, reviewed negative and mutant transactions, its sole mint policy equals its separately hashed Plutus V3 witness and its compiled applied script. Mint[0] redeemer is constructor 121 with five proofs.

The 279-byte positive and negative messages are identical through byte 270. The final eight bytes encode epoch 0 and epoch 1 respectively. The mutant retains the exact negative message, five committee signatures, public parameters and input references. OpenSSL independently verified all 15 committee signatures and all six funding witnesses against their final-body Blake2b-256 digests. Both resolved input payment credentials in each fixture match verified funding public keys. ADA values are 17,000,000 input, 16,000,000 output, 1,000,000 fee; the sole minted authority NFT is conserved to outputs. No collateral fields exist. Mutant authority output retains the canonical state-validator credential.

All nested and family SHA256SUMS entries and both JSON artifact manifests verify. Reviewed family SHA256SUMS SHA-256: `260b79f564d3a5d4c2552dccc39277c7f54b7eb58687f53c178bcdf2fd564d45`. The copied prior positive/negative run and pre-execution/positive/negative review artifacts exactly match their canonical originals. Positive run/review SHA-256: `932b2a1898482efd7326a667e345e3f129a861bfe2de1218dcdad43fbaae6093` / `24fd754d809519e81601c17ce96cace9d5cb23b9c62e4f4c0f2eb0822a683377`. Negative run/review: `02ac3c54834047e6a0fedb1b107bec7e37539b5b07ad0cd63998f936b1509d01` / `5ce42ff9ba4a020ad4f4a8e8372782ec85d2364241115764d8c40ba8d7d241f0`. No persisted private-key artifact is present in the accounted file set; only public parameters, scripts, signatures, transactions, messages and evidence records are retained.

## Verification record

`VERIFY.py` is the exact verification payload executed through the scoped WSL command `/home/GodOfAgents/vams-evidence/toolchains/python/bin/python3.12 -c "exec(__import__('base64').b64decode(PAYLOAD))"`, with PAYLOAD the base64 encoding of these exact saved bytes. Final exit 0; complete output is `VERIFICATION.json`. It invokes pinned Aiken `build`, two `blueprint apply` calls and `blueprint policy` per disposable project via the inspected existing compile harness; `patch -p2 --input SOURCE-DIFF.patch` and OpenSSL `pkeyutl -verify -rawin -pubin` are the other verification operations. No simulator was invoked. An earlier reviewer-script attempt exited 1 because its absent-collateral check used a strict missing-map-key accessor; correcting that reviewer check to inspect absent keys yielded the recorded successful run. No fixture defect was concealed.

## Invariant and scope assessment

INV-1, INV-2, INV-3, INV-4, INV-5, INV-6, INV-7, INV-8, INV-9 and INV-10: **not touched**. Canonical executable source is unchanged; the weakened epoch expression is confined to disposable synthetic attribution controls. It must not become a deployable artifact.

This review grants pre-execution byte-integrity approval only. Mutant acceptance and named rejection attribution remain pending execution and a separate integrated triad review. No negative-case, mutation-suite, original-policy, full-ledger-admission, Cardano Pre-Prod or live-network credit is granted. Funding and conservation checks establish these synthetic vectors, not real UTxO existence or full ledger admission. F05/M3 stays OPEN; readiness NOT READY. Deployment, Deposit, Slash activation and ExecuteIntent remain disabled. STATUS and SESSION_HANDOFF were not changed by this reviewer.
