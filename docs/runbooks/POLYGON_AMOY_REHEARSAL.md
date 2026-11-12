# Polygon Amoy restricted-testnet rehearsal

**Network:** Polygon Amoy, chain ID `80002`
**Release profile:** `restricted-testnet-v1`
**Posture:** local rehearsal only. Live RPC reads, simulation against Amoy,
signing, funding and broadcast each need the owner's specific authorization.
**Last verified:** 2026-11-13 against `contracts/script/DeployRestrictedTestnet.s.sol`
and `docs/audit/schemas/deployment-manifest.schema.json` (schema 2.0.0)

Ported from PR #4 (`docs/runbooks/POLYGON_AMOY_REHEARSAL.md`, July 2026) and
rewritten for the current restricted producer. The July draft targeted
`DeployTestnet` plus the VDSO canary and manifest schema v4; both are
superseded. Readiness is NOT READY: this runbook is a procedure, not evidence.

## What the producer deploys

`DeployRestrictedTestnet.runRestricted(ServiceConfiguration)` creates eleven
contracts: token, staking, timelock, sentinel, service registry, provider bond
registry, restricted policy, SGX action verifier, EZKL action verifier,
delivery verifier and composed settlement. `run()` and the inherited core-only
`rehearse()` revert with `ExplicitRestrictedConfigurationRequired`, so a
core-only deployment cannot be run from this target by mistake.

Postconditions checked by the script and by
`contracts/test/deployment/RestrictedTestnetDeployment.t.sol`:

- the chain is Amoy (`InvalidChain` otherwise), checked before any creation;
- governance and treasury are distinct 3-of-5 Safes, emergency is a distinct
  2-of-3 Safe, all on the approved Safe proxy and singleton code hashes;
- the timelock delay is 48 hours and governance is its only proposer;
- registry and settlement roles belong to the timelock; deployer roles are
  removed;
- the restricted policy starts with no protected-effect authority;
- the reward rate stays zero and supply is unchanged (owner decision 4);
- dependency code hashes (insurance recipient, DCAP backend and collateral
  router, EZKL backend) must match before creation.

The settlement dispute resolver is the governance timelock (owner decision
10, P2). VDSO is not part of this profile: `DeployVDSOCanary.s.sol` stays out
of the ceremony until the VDSO shadow slice is ported and reviewed.

## Inputs

All values below are public except `PRIVATE_KEY`. Provide them through the
local environment or a secret manager, never chat or a committed file.

| Input | Status on 2026-11-13 |
|---|---|
| `VAMS_GOVERNANCE_SAFE`, `VAMS_TREASURY_SAFE` (3-of-5) | UNKNOWN: Safes not created; seat holders A–C not named |
| `VAMS_EMERGENCY_COUNCIL` (2-of-3, pause only) | UNKNOWN: same |
| `VAMS_SAFE_PROXY_RUNTIME_CODE_HASH`, `VAMS_SAFE_SINGLETON`, `VAMS_SAFE_SINGLETON_RUNTIME_CODE_HASH` | UNKNOWN: approved Safe release not chosen |
| `ServiceConfiguration`: host domain, budget unit, insurance recipient and code hash | UNKNOWN |
| `ServiceConfiguration.sgx`: DCAP backend, collateral router, measurements, runtime ID, SVN, TCB evaluation | UNKNOWN (D3). TEE routes stay disabled without authentic DCAP evidence (owner decision 3) |
| `ServiceConfiguration.ezkl`: backend, code hash, model hash, circuit manifest hash | UNKNOWN (D3) |
| `PRIVATE_KEY` (faucet-only deployer) | Secret. Read only after the public preflight passes; never needed for local rehearsal |

Signer model: team-controlled bootstrap (owner decision 12). Seats, Safe
membership, consent, rehearsals and the overlap disclosure are in
[TEAM_SIGNER_GOVERNANCE.md](TEAM_SIGNER_GOVERNANCE.md). No Safe is created
until its seat holders are named, have consented and have rehearsed.

## Step 1: local rehearsal (no network, no key)

Runs the same creation, handoff and postconditions in the local VM through
`rehearseRestricted`, with Safes and dependencies the test creates locally:

```bash
cd ~/code/VAMS-testnet/contracts
~/.vams-tools/bin/forge build --sizes
~/.vams-tools/bin/forge test --match-path test/deployment/RestrictedTestnetDeployment.t.sol -vvv
~/.vams-tools/bin/forge test --match-path test/deployment/DeployTestnetAuthority.t.sol -vvv
```

Expected: every test passes with zero skips. Any failure stops the ceremony.
Record the commit, Forge version, exact command, raw output and counts. This
is synthetic local evidence; it says nothing about real Safes or backends.

## Step 2: public preflight against Amoy (needs a grant)

Not runnable yet: every input above is UNKNOWN. When they exist, and the owner
has granted read-only Amoy RPC access, the preflight calls
`validateServiceConfiguration(configuration)` and checks each Safe's owners,
threshold, nonce, modules, guards, fallback handler and singleton. A current
state query does not prove a Safe was never used; its full setup and
`ApproveHash` history must be recorded independently. The exact command is
written only once the reviewed values exist; this runbook does not supply a
placeholder.

## Step 3: simulation and broadcast (needs separate grants)

A `forge script` simulation without `--broadcast` comes first, then owner
review of the full transaction sequence. `--broadcast` needs the owner's
explicit approval of that exact sequence. After any approved broadcast, query
every receipt and postcondition independently before writing a deployment
manifest. If a postcondition fails: stop, keep the receipts, keep protected
operations paused through the emergency Safe, and do not retry with changed
parameters outside a new ceremony. No automatic retry after an uncertain
submission.

## Manifest

A deployment manifest uses `deployment-manifest.schema.json` 2.0.0 with
`network: polygon-amoy`, `chain_identifier: "80002"`,
`release_profile: restricted-testnet-v1` and a `restricted_evm` package. It is
checked by `python scripts/audit/audit_program.py readiness --stage canary
--deployment-manifest <file>` together with the other canary inputs. A
rehearsal record must never enter the deployment register.
