# Independent exact-byte review: applied_genesis_parameter mutant R2

Date: 2026-10-05

## Verdict

**PASS for fixture-byte acceptance before mutant execution.** The candidate is bound to the retained R5 applied-parameter negative case and its R6/R7 normal-policy controls. The fixture may proceed to the separately controlled local synthetic mutant simulation. This review grants no case, mutation, original-policy, ledger-admission, or live-network credit. Keep the case and mutation PENDING until execution and independent execution-record review.

## Scope and method

Reviewed candidate directory `docs/remediation/m3_f05_2a_applied_genesis_mutant_r2_20261005/`, the R5 `applied_genesis_parameter` manifest and bytes, R6 positive and R7 negative run records, the candidate builder and focused structural test, and the current authority-policy source. No simulator, network, installation, or compiler was invoked. The fixture's focused test independently verifies transaction encoding, signatures, policy binding, and conservation.

## Exact-byte findings

- The R2 manifest is strict JSON without duplicate keys. All seven entries in the candidate `SHA256SUMS` verify; manifest-declared byte lengths and SHA-256 values match each listed artifact.
- R5 seed reference and initial-key CBOR are unchanged: `51f08c55f440a2116b42e5283fc76d8be4d707788d3bc765023620199af45c75` and `9b604d528d46f510b808d00ad985e498522a7d60595823ce016adb647ff9556f`. R5's negative transaction is `67a3a40a149c5972720b23c18d37bb65f4ead04f0eaae421c3f3aa6440cb1e6b`; its applied policy code hash and ID are `66d372129d322008e8b095f87b0b7726d3020868954361578a774f4afe8e6c5d` and `fc305fd82585607dc1998425cbe3bce8f43667e1ac161c448098c058`. The candidate's normal-policy recompilation record matches both R5 values.
- The candidate preserves the exact R5 Mint[0] proof redeemer and ExUnits (`R5-exact-negative-redeemer.cbor`, SHA-256 `10165e48a2b777b856c31d815fdcea91d2d5786740b5157271e74a998fc051d4`). All five 32-byte initial keys remain ordered and unique; the focused test cryptographically verifies each retained Ed25519 PoP against the R5 applied-parameter message.
- The source patch changes only `expect count_seed_input(tx.inputs, genesis_ref) == 1` to `expect True`. In-memory reconstruction from the current source matched both recorded original and mutant source hashes (`e9d3ac9cbb14b9e7693dc12430234694c82eb52e61d176e1e39992fb9cbeafa8` and `ade9f13f6fa321d9c40df3395f5afe358312151647d7f9ce073ed77f81b2ad86`). The inspected builder applies that named mutation to a disposable Aiken project copy before compilation. The mutant program hash is `bcb691e487db3b30b0d25167d514e2f65f31de08d73b5f4aee0c29dd05da8fec`; its policy ID is derived from those bytes as `1d20d3c373cd806fbbf9634a4840ce2cfcbeccd1ae9fd89a8ccbee83`, distinct from the exact R5 normal policy ID.
- The mutant transaction retains the R5 negative body semantics and raw input references. It rebinds the minted singleton `VAMS-F05-AUTH-V3`, the output NFT, and the Plutus V3 script witness to the mutant policy. The raw resolved outputs contain only funding addresses corresponding to the transaction's two ephemeral witness keys; the focused test verifies both body-bound signatures. No private key material is present in the package. ADA conservation is 17,000,000 input lovelace = 16,000,000 output lovelace + 1,000,000 fee. The output singleton NFT equals the minted singleton NFT.
- The target is the intended `f05_authority_policy.f05_authority_policy.mint / Mint[0]` entrypoint. R6 positive reference hash `457cb0ec423477df1d232501506e713f3ce7800210635b35535abff0b2417c8e` records `script_accepted`; R7 negative reference hash `651fc64426b0968828a597564b48ae4a6dbba68b0f5d516d37f28b8bc5924d7e` records `compiled_evaluation` rejection. Both records identify the exact R5 case, policy, and target invocation. Their capture notes disclose that raw simulator stdout/stderr and external attestation are not retained.
- Candidate credit flags for case, mutation, original policy, ledger admission, and live network are all false. Scope is explicitly the synthetic alternate applied policy only.

## Verification performed

1. `/home/GodOfAgents/vams-evidence/toolchains/python/bin/python3.12 -m py_compile scripts/remediation/build_f05_2a_applied_genesis_mutant_r2.py scripts/remediation/test_f05_2a_applied_genesis_mutant_r2.py` — PASS.
2. `/home/GodOfAgents/vams-evidence/toolchains/python/bin/python3.12 -c "import runpy; d=runpy.run_path(\"scripts/remediation/test_f05_2a_applied_genesis_mutant_r2.py\"); d[\"test_r2_exact_r5_bound_mutant_candidate\"]()"` — PASS; no simulator invoked.
3. Strict `json.loads(..., object_pairs_hook=...)` duplicate-key check on `FIXTURE-MANIFEST.json` — PASS (`applied_genesis_parameter`).
4. `cd docs/remediation/m3_f05_2a_applied_genesis_mutant_r2_20261005 && sha256sum -c SHA256SUMS` — PASS (all seven entries).
5. In-memory source-hash reconstruction — PASS for the exact one-line mutation and both recorded source hashes.

Candidate artifact hashes reviewed: manifest `02f8dca9edac5a8bb52f39fcc9deabdfc6cf93e447a0bf170403c4ef95af61fd`; patch `fd6f06b112efebd2b63833d84d77b5611534fd1ef3268886859f3122e2e5ca23`; mutant program `bcb691e487db3b30b0d25167d514e2f65f31de08d73b5f4aee0c29dd05da8fec`; mutant transaction `7a590ae68203a4cbc0cddf3959c645d5bbd6e56a1c523b2949e05838008f06e0`; raw inputs `4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe`; raw outputs `7816fe012b4c206ed7cdbace0c8eaded68becf9e035d44906612b14ca39fbf03`.

## Limits

This is a byte and structural review, not an execution review. The recorded compiled artifact was not independently rebuilt in this review, and the R6/R7 simulator records remain local structured captures without retained raw simulator output or external attestation. Therefore, after any mutant simulation, obtain independent review of the exact new attempt record before awarding case or mutation credit. This result establishes no original-policy behavior, full ledger admission, Cardano Pre-Prod, or live-network behavior. F05/M3 remains open; readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
