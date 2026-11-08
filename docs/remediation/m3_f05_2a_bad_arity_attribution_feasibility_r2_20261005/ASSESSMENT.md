# F05.2a malformed applied-key attribution feasibility reassessment R2

Status: **blocked; read-only reassessment; no fixture execution; no credit**.

This reassessment follows R9 acceptance and checks whether the local pinned toolchains now provide the R4.1 first-failure attribution required for `applied_keys_bad_count` and `applied_keys_bad_length`. The authoritative R4.1 contract remains unchanged: the exact unmodified compiled target at Mint[0], tied to its exact compiled bytes and input, must identify the named key-count/key-length guard as the first rejecting condition. A guard-removal mutant is explicitly insufficient because independent production checks reject these malformed inputs.

Current source order remains:

* `valid_initial_authority` calls `valid_ordered_keys(initial_keys)` before `valid_bootstrap_proofs` (`cardano/lib/vams/f05_authority.ak`, lines 76-93).
* `valid_ordered_keys` requires exactly five keys and each key length 32 bytes (`cardano/lib/vams/f05_authority.ak`, lines 268-282).
* `valid_bootstrap_proofs` separately pattern-matches exactly five keys and five signatures, then verifies five Ed25519 signatures (`cardano/lib/vams/f05_authority.ak`, lines 135-159).
* The policy invokes these checks at `f05_authority_policy.mint` / Mint[0] (`cardano/validators/f05_authority_policy.ak`, lines 61-69).

Read-only toolchain results:

* Aiken 1.1.21+42babe5: `/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken`, exit 0; SHA-256 `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`.
* Aiken 1.1.23+8949565: `/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.23-f05-qualification-20260930/aiken-x86_64-unknown-linux-musl/aiken`, exit 0; SHA-256 `748b9d45785fbded901ed87475072b6d20ee259bb4588c72428c12a19e8902d3`.
* Both `aiken tx simulate --help` outputs expose only CBOR, slot/time, blueprint, and script-override options; neither exposes a source map, internal-step, or first-failure trace.
* `uplc eval --help` exposes only `--flat`, `--cbor`, and `--debug`; no qualified exact-context first-failure trace is available.
* Aiken 1.1.21 `check --debug` reports failed-test UPLC and build trace levels change compiled artifacts; neither supplies an unchanged-byte exact-Mint[0] trace.
* Installed command lookup still finds no `cardano-cli`, `uplc`, or `aiken` outside the pinned toolchains. Scoped searches found no standalone evaluator/source-map artifact under `docs/remediation`, `cardano`, `scripts`, or toolchain/site-package locations.

The public harness now includes reviewed legacy `verifySignature` to canonical `verifyEd25519Signature` alias normalization (the Aiken source helper is `verify_ed25519_signature`). It checks alias counts and requires normalized re-encoding to equal the original CBOR before context application. Harness SHA-256 is `1db507fe0559216a28d3768deaf12e1d56ecb76f51ef8cad1c5cec1f4449550b`; retained alias assessment SHA-256 is `4c6b57ceac2a6fbab630146469e075b6c8329259b43aedc4d8d3ad9b437a10a`. The retained adapter/diagnostic evidence reports 24/24 tests and a public positive exit 1 after the equality gate, with no malformed-case result. This corrects the earlier shorthand that described the direct route solely as a `verifySignature` blocker; the current blocker is the absence of a qualified unchanged-byte exact-context first-failure attribution result.

The R5 malformed packages remain checksum-valid (13/13 entries each). No malformed negative, mutant, build, or simulator execution ran in this reassessment. Both original IDs and assertions remain PENDING; R9 totals remain 53/55 negatives, 49/51 transaction_simulator, and 18/21 mutations. No original-policy, ledger-admission, Cardano Pre-Prod, live-network, or deployment-readiness credit is granted. F05/M3 remains OPEN; readiness NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Decision: retain both cases PENDING under R4.1. The smallest next decision is whether the owner will authorize a versioned compound-arity evidence-contract amendment with explicit first-failure limits, or retain the current exact first-failure requirement until a qualified evaluator/source-map capability exists. No source or registry assertion changed.
