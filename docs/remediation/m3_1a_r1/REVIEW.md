# M3.1a Aiken recovery and F01 design-baseline review

Date: 2026-09-25
Disposition: local design baseline complete; F01 and M3 remain open
Repository HEAD: `829ab544571f12efe50ecb5740f129c8acb3e16f`

## Scope and outcome

This slice recovered and authenticated the pinned Aiken 1.1.21 toolchain,
executed the current Cardano tree from an exact external copy, mapped the
implemented insurance validator and its consumers, and froze the custody
state-machine contract in `ADR.md`. It did not edit any Aiken source, shared
type, lockfile, blueprint, deployment material, or off-chain implementation.

The current validator is not sufficient to close F01. It has no authenticated
singleton fund state, continuing-output rule, complete value/datum
conservation, persisted claim/approval state, payout binding, expiry, or replay
identity. `ClaimDatum` is unused, and the current bridge verifier authenticates
only byte lengths. F01 therefore remains `REVALIDATED_OPEN`; M3 remains open.

## Repository and source provenance

- Origin: `https://github.com/GodOfAgents/VAMS.git`
- Branch: `testnet/remediation-20260907`
- HEAD: `829ab544571f12efe50ecb5740f129c8acb3e16f`
- Recursive submodules: 14 recorded entries; no submodule was modified.
- Exact copied source: `/home/GodOfAgents/vams-evidence/m3-1a-r1-20260925-829ab544571f/source/cardano`
- `cardano/aiken.toml`: `55984b24927897c47dbf45933911b804047d0200bdf9a47942efded8b6ed4683`
- `cardano/aiken.lock`: `3e3bd23551639f83c6c4315b60d4752276345fa2b991ffc88668eebba60d3749`
- `cardano/plutus.json`: `fc6d925c6af7ceefe0311a309fd319e46b476471f291b08879bbffe50cde5e96`
- Pre-slice dirty-path inventory SHA-256: `f47b5d1156b5737b481355964dce9b04a33e4e03fb454b7f52af71892bfe0a85`

No repository deployment record supplies a deployed insurance script, initial
datum, funded insurance UTXO, or deployment transaction. The values below are
build-derived identities only and are not deployment evidence:

- insurance script hash: `0899534920979a746f7c5676af32406bab6ccdb14fc77b560f4cf2fb`
- testnet address: `addr_test1wqyfj56fyzte5ar003t8dtejgp46kmxdk98uw76kpax097ch9vcht`

## Toolchain acquisition and verification

The existing external runtime was used from
`/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/`; nothing was
installed or added to repository or global `PATH`.

- Official release archive:
  `https://github.com/aiken-lang/aiken/releases/download/v1.1.21/aiken-x86_64-unknown-linux-musl.tar.gz`
- Official checksum asset:
  `https://github.com/aiken-lang/aiken/releases/download/v1.1.21/aiken-x86_64-unknown-linux-musl.tar.gz.sha256`
- Published and observed archive SHA-256:
  `9fe0bb94efbb79f4d351664def3da0d58c7e30716fcb65590ff9b6c6b0ffb715`
- Checksum-asset SHA-256:
  `f811384c921c59231a2334040a4b6b77f9987a8a65f9ad703e032cca78937d3c`
- Executable SHA-256:
  `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`
- Version output: `aiken v1.1.21+42babe5` (release core 1.1.21 with official
  commit metadata)
- Checksum acquisition command:
  `curl --fail --location --proto '=https' --tlsv1.2 --output /home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken-x86_64-unknown-linux-musl.tar.gz.sha256 https://github.com/aiken-lang/aiken/releases/download/v1.1.21/aiken-x86_64-unknown-linux-musl.tar.gz.sha256`

Only the official checksum asset was acquired during this slice. The existing
archive and extracted executable matched it before execution.

## Fresh native baseline

| Command | Exit | Result |
| --- | ---: | --- |
| pinned `aiken check` in the exact copied tree | 0 | 50/50 pass: 43 unit and 7 property tests; seed `1749241864` |
| pinned `aiken test` in the exact copied tree | 2 | expected CLI rejection: Aiken 1.1.21 has no `test` subcommand; `check` is its native type-check/test runner |
| pinned `aiken build -o ../../plutus.generated.json` | 0 | complete blueprint generated successfully |

The generated blueprint SHA-256 is
`f07ae23bde44cb0e7ec8e226c9f6a47549a7b2e802b0a8fb464b9c1511d58c35`.
It contains the same definitions, ten validators, compiled programs, insurance
entrypoints, insurance script hash, and derived testnet address as the checked-in
blueprint. Its raw file hash differs because Aiken renamed two unused governor
and timelock parameter labels with leading underscores; no compiled-program or
insurance difference was found.

Sanitized log hashes:

- `aiken check`: `46cc8197b2ee98310a8e1f1b36efe44b38d350b44c37b8ff6ab5fd43375ba2c0`
- unsupported `aiken test`: `b16e123481691119c633165951c30f8fd2aa3a1a2e3b830c0e3ddc795deed6f8`
- `aiken build`: `1eae95d8fabf922ce192b08d360a0f61b49aab690f814414a38f98f8d62815a5`

The 76-file external evidence manifest verifies successfully. Its path is
`/home/GodOfAgents/vams-evidence/m3-1a-r1-20260925-829ab544571f/MANIFEST.sha256`
and its SHA-256 is
`dd8bfdb4debc6980feeb48ecbd5f06ca18de36593c8b0bf6673631038d5e5dbc`.

## Source-reality map

| Concern | Current source reality | M3.1b consequence |
| --- | --- | --- |
| Insurance validator | `cardano/validators/insurance_fund.ak` contains four local-predicate branches | Replace with the frozen authenticated transition contract |
| Shared data | `cardano/lib/vams/types.ak` defines an unused `ClaimDatum` | Introduce versioned fund and claim data; CBOR changes are explicit |
| Bridge evidence | `cardano/lib/vams/icb.ak` validates structural lengths only | Deposit remains fail-closed; do not promote bytes to authority |
| Utility helpers | `cardano/lib/vams/utils.ak` provides general helpers, not custody | Add only validator-facing helpers backed by public-context tests |
| State asset | No singleton insurance-state minting policy exists | Add a one-shot policy and enforce one canonical continuing state |
| Off-chain consumers | No Cardano insurance transaction builder/consumer was found | Add typed builders only after the on-chain contract exists |
| Deployment | Cardano insurance identity, transaction, roles, and funded UTXO are pending | Build identities must not be represented as deployed state |
| Blueprint | Checked-in insurance CBOR builds reproducibly under the pinned compiler | M3.1b must regenerate and rebind every changed identity |

## F01/F05 dependency and next slice

The local custody and claim state machine can proceed independently, but an
authorized cross-chain deposit cannot. M3.1b must implement the singleton state,
conservation rules, bounded durable claim lifecycle, exact payout, and replay
controls while rejecting `Deposit` unconditionally. F01 cannot close until F05
provides a separately reviewed bridge authority/finality/replay contract or a
new owner-approved trust ADR replaces that dependency.

Next slice: **M3.1b — implement the authenticated insurance-custody state
machine and native tests under the frozen contract**.

## Invariants, mocks, and readiness

This documentation/design slice changes no executable invariant enforcement.
INV-1 and INV-3 through INV-9 are unchanged. INV-2 remains open for executable
insurance yield-cap enforcement. INV-10 remains preserved because
`bridge_proof` and `payload_hash` stay distinct and structural bytes do not gain
authority. Mock-mode behavior is unchanged.

F01 is `REVALIDATED_OPEN`; F02-F05 are unchanged. M3 is open. M2 remains
`COMPLETE`, F08/F09/F17 remain `REMEDIATED`, and overall promotion readiness is
`NOT READY`. T06/history and M3-M9 remain open.
