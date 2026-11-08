# M3.1b-R1 authenticated insurance-custody implementation review

Date: 2026-09-25
Disposition: locally implemented and tested; independently unaccepted
Repository HEAD: `829ab544571f12efe50ecb5740f129c8acb3e16f`

## Scope and result

The Cardano insurance validator now implements the frozen M3.1a custody
contract. A one-shot mint handler and spend handler share one parameterized
script, so the script hash is also the singleton state-token policy identity.
Genesis consumes one configured output reference, mints exactly one configured
asset, fixes guardian policy parameters into the script, and creates one inline
`FundDatumV2` at that script address.

Normal transitions require one authenticated state input and one state-bearing
continuation at the exact address, prohibit all mint/burn under the state
policy, preserve every non-ADA asset, bind datum balances to actual lovelace,
and keep guardian, threshold, payout-cap and policy-epoch fields immutable.
Claims have a maximum count of 64, monotonic nonces, unique derived identities,
unique authorized persisted approvers, exact recipients and amounts, bounded
time intervals, and removal-based replay resistance.

`Deposit` rejects unconditionally, including a 100-case generated property.
No ICB, Mithril, governance, registry, bridge, deployment, credential, or
submodule code changed. F05 therefore remains unresolved and F01 remains
`REVALIDATED_OPEN`.

## Changed implementation

- `cardano/validators/insurance_fund.ak`
  - one-shot singleton genesis mint handler;
  - authenticated spend/continuation boundary;
  - Submit, Approve, Payout, Cancel and Expire state transitions;
  - unconditional Deposit rejection;
  - canonical claim identity and 59 realistic native tests.
- `cardano/lib/vams/types.ak`
  - versioned `FundDatumV2`, `ClaimRecord`, canonical identity payload,
    initialization redeemer, and complete lifecycle redeemers.
- `cardano/plutus.json`
  - regenerated only after the complete native suite passed.

Relative to the accepted M3.1a blueprint, compiled-code comparison shows only
the insurance spend program changed and the insurance mint program was added;
no other validator's compiled program changed. Pinned-toolchain regeneration
also normalizes unused parameter labels in blueprint metadata without changing
those compiled programs.

No off-chain builder or deployment configuration exists for the new schema.
That work is not implied by this local validator implementation.

## Canonical claim identity

The claim id is `blake2b_256` over ledger-canonical CBOR serialization of the
typed `ClaimIdentityPayload`. The fixed domain is
`VAMS_INSURANCE_CLAIM_V2`. The serialized fields are, in schema order: domain,
state policy id, state asset name, policy epoch, nonce, claimant key hash,
payout address, amount, 32-byte evidence hash, submission time and expiry.
Raw byte concatenation is not used.

An independent CBOR encoder produced the checked vector:

`35d18a32277854e33159c1658a3abfb18661b2d82e9e02b014a69ff6e53e2466`

The native `claim_identity_vector_matches_independent_cbor` test confirms the
on-chain implementation matches it.

## Pre-fix characterization

The untouched M3.1a package was copied into this slice's external evidence
area before instrumentation. Its original insurance source SHA-256 was
`f9751165783a54c80d5bda2bda962f65010eb222954ff9033feef8c3690cc772`.
A test-only characterization reconstructed the old Submit branch's exact
predicates over a transaction with one fully funded insurance input and a
single attacker output. The old predicates passed despite the absence of a
continuing fund output. The isolated test passed 1/1; it is not present in the
repository source.

## Native verification

Only `/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken` was used
for the final verification/build. That requested path is a local symlink to the
previously verified official extracted binary. Its SHA-256 is
`07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`
and its version output is `aiken v1.1.21+42babe5`.

| Command | Exit | Result |
| --- | ---: | --- |
| `aiken fmt --check validators/insurance_fund.ak lib/vams/types.ak` | 0 | both scoped sources formatted |
| `aiken check` | 0 | 104/104: 97 unit and 7 property tests |
| insurance module within that run | 0 | 59/59: 58 unit and 1 property test |
| `aiken build -o ../../plutus.generated.json` | 0 | blueprint regenerated and copied byte-for-byte to `cardano/plutus.json` |

The insurance suite exercises real `Transaction`, `Input`, `Output`, `Value`,
inline datum, mint, signer and validity-range structures. It covers valid
genesis and all enabled transitions, plus state-token substitution/duplication,
mint/burn, continuation, conservation, datum balance, policy mutation, claim
identity/nonce, guardian approval, payout recipient/amount/net-gain, time,
replay, capacity, and every generated Deposit case.

The 64-to-65 capacity rejection fixture reports high total test execution
units because its test program constructs and validates 65 complete claims.
Those figures include fixture execution and are not a deployment budget claim;
independent R2 must assess applied-script cost at the worst accepted state
before any funding or deployment decision.

Sanitized log SHA-256 values:

- complete check: `a9d6716718baa717e369286c70fbcb0c7ddc08b7e4f86a942d3305eaaee2896c`
- build: `32ed949b18c95d36d627b4dd140124b75d67ff3afc33749075b0b014bb68c852`
- pre-fix characterization: `c3b7ad4f6cd01fd15bc8b6bd5a672929da36daa795716dafbc449bdc3ff6b7fd`

The sanitized external evidence package is
`/home/GodOfAgents/vams-evidence/m3-1b-r1-20260925-829ab544571f`.
Its recursively verified `MANIFEST.sha256` SHA-256 is
`02623ec4e720b57871c5db939c55b7a3c35cba68714390e5edf2b8deef6abc47`.

Repository validation also passed:

| Command/check | Result |
| --- | --- |
| `python3 scripts/docs/validate_docs.py` | passed |
| `PYTHON_BIN=python3 python3 scripts/audit/audit_program.py validate` | 36 tracks and testnet profile valid |
| `python3 -m unittest scripts.docs.test_validate_docs scripts.audit.test_audit_program` | 22/22 passed |
| remediation JSON plus `cardano/plutus.json` parsing | passed |
| checked-in blueprint vs external generated blueprint | byte-for-byte equal |
| recursive submodule status | unchanged; no submodule modification marker |
| `git diff --check` | passed |

## Build identities

These are local build identities, not deployment, funding, applied-parameter,
or Cardano Pre-Prod evidence.

| Identity | Before | After |
| --- | --- | --- |
| Blueprint SHA-256 | `fc6d925c6af7ceefe0311a309fd319e46b476471f291b08879bbffe50cde5e96` | `1cb965882b7bf549513380e07dd26b4b9c4be26df039463751562392eccb76bb` |
| Unapplied insurance blueprint hash | `0899534920979a746f7c5676af32406bab6ccdb14fc77b560f4cf2fb` | `2e252badb182e9bdbd46e399155ff22c436abf222cc7278095b333c7` |
| Build-derived testnet address | `addr_test1wqyfj56fyzte5ar003t8dtejgp46kmxdk98uw76kpax097ch9vcht` | `addr_test1wqhz22adkxpwn0dagm3ej92l7gkyx64lygkvwfuqjken83cckka29` |
| Unapplied state-policy identity | absent | `2e252badb182e9bdbd46e399155ff22c436abf222cc7278095b333c7` |

Final applied script/policy identities depend on the reviewed genesis reference,
asset name, guardian set, threshold, policy epoch and payout cap. None was
selected or deployed in this slice.

Canonical JSON schema digests:

- old `FundDatum`: `e6bf4db08daad8fedd00f55421941e9b9c15ee6d04f09aaa0ee23511c9c77d89`
- old `InsuranceFundRedeemer`: `0d4da0ccb1c727a5c9117b64b3321d8af9549fc6a85caf456b598da637aaaa26`
- new `ClaimRecord`: `b3daf79df20a485db894ab5e450c1748c8108323e944028bf7954c6b0589f8fe`
- new `FundDatumV2`: `5df00c5196aafee9134daee1ce411e28ed294ebab296c5fff195043d41087b04`
- new `InsuranceFundRedeemer`: `47ac80d5fecb8c5b4fcf28b88dbc003be0a2b83f8d5b25f9d4a864587857d0f2`
- new `InsuranceStateRedeemer`: `eabac29136e05c5a1ff9d9e4396cdf27f0094ec7a9ee274990f8025850ed1235`

Final source SHA-256 values:

- validator: `f19b20f8c1479c1dfec49217bded4f79b6044cd19269342f5467dd2ae030e79f`
- shared types: `a963255e8227557a0a232aad153a41b658cbc9a3c80ce56bb65d4755c2ab9d34`

## Invariants and status

INV-2 is unchanged and remains separately enforced by
`contracts/src/economic/VAMSInsuranceFund.sol`; this Cardano custody work does
not claim to implement the 30% yield-deployment cap. INV-10 remains preserved:
`bridge_proof` and `payload_hash` remain separate redeemer fields and authorize
nothing while Deposit is disabled. INV-1 and INV-3 through INV-9 are unchanged.
Mock-mode behavior is unchanged.

F01 remains `REVALIDATED_OPEN` pending F05 deposit authority and independent
M3.1b-R2 review. F02-F05 are unchanged, M3 remains open, M2 remains complete,
and overall promotion readiness remains `NOT READY`. No address was deployed or
funded.

Next slice: **independent M3.1b-R2 review of the F01 custody implementation**.
