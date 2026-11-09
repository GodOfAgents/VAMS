# Stage D current-host policy reader: parked (2026-11-09)

Status: **PARKED, missing external inputs.** No code change. T15 and T23–T25
are unchanged. Readiness: 13 findings open, 0 of 36 tracks verified, NOT
READY.

## What exists

- `neuron/effect_provider_v3.py` `CurrentActionPolicyV1` and
  `neuron/effect_authority_v3.py` `CurrentAuthorityPolicyV1` are abstract
  interfaces. Only test fixtures implement them. The V3 effect candidates
  refuse live modes (`EFFECT-CANDIDATE-LIVE-GUARD.md`), and the F12 campaign
  ran them with a fixture policy.
- `neuron/object_policy_calls_v1.py` builds calldata for two read-only
  methods of `RestrictedTestnetPolicyV1`. Nothing sends that calldata or
  consumes the response.

## Why a simple RPC reader is not acceptable

`docs/remediation/repair_20261101/OBJECT-POLICY-CALLS-V1.md` sets the
acceptance bar:

> "No raw RPC Boolean, fixture callback, score or unsigned bytes may supply
> that authority."

The same document requires native current/finalized host state, exact
deployed code and configuration, and an authenticated policy root, version,
epoch and revocation set. An `eth_call` answered by an RPC endpoint is an
unauthenticated Boolean from whoever runs that endpoint. Building that
would produce a component the acceptance criteria already reject.

## What a qualifying reader needs, and what is missing

| Input | Status |
|---|---|
| Deployed `RestrictedTestnetPolicyV1` on Polygon Amoy: address, deploy transaction, runtime code hash | UNKNOWN. Nothing is deployed; deployment needs separate authorization and signers (D2) |
| Finality model and trust anchor for Amoy headers (which source attests a finalized header, and how it is authenticated) | UNKNOWN. Needs a reviewed host and finality manifest |
| Reviewed RPC provider and independent observer identities | UNKNOWN. Same gap as F10 (data availability observer) |
| Governance custody for the policy's timelock (who can change root, version, epoch) | UNKNOWN. Signers (D2) |
| Privacy acceptance for the actor/provider/resource linkage that every policy query sends to an RPC provider | BLOCKED on T33 reviewer |
| Cardano-side policy domain | Separate. No committee may stand in for native verification |

## Possible local work once a direction is chosen

This needs an owner or reviewer decision; it is not started:

- A proof-verifying core. Given a trusted finalized header, check
  `eth_getProof` storage proofs for the policy contract's root, version,
  epoch, eligibility and revocation slots, then evaluate the policy
  off-chain over the proven values. It can be tested against a local Anvil
  chain.
- The trust anchor stays an input. This core removes trust in the RPC
  endpoint, not in the finality source.
- Size: re-implementing the `authorizesObjectV1` and
  `authorizesObjectScopeV1` logic over proven storage is a multi-session
  slice with its own review.

## Decision needed

Choose the Amoy finality and trust-anchor model and the RPC provider and
observer. Or decide that the restricted canary runs with effects disabled
until those exist. Until then this item stays parked, and the V3 effect
path stays fixture-only and refuses live modes.
