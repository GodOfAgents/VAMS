# Polygon Amoy Deployment Rehearsal

**Network:** Polygon Amoy, chain ID `80002`

**Posture:** Faucet-only, unsigned rehearsal until explicit broadcast approval
**Last verified:** 2026-07-14

This ceremony deploys the baseline contracts first and the seven empty VDSO
modules second. It does not activate VDSO, rewards, value transfer, adapters,
programs, verifiers, domains, recovery, reservations, or execution routes.
The exact four-person owner design, recovery custody, consent, and rehearsal
requirements are defined in [TEAM_SIGNER_GOVERNANCE.md](TEAM_SIGNER_GOVERNANCE.md).

## Required external inputs

Provide values through a secret manager or local environment, never chat or a
committed file:

- `POLYGON_AMOY_RPC_URL`: trusted chain-ID `80002` endpoint; sensitive if it
  embeds a provider token.
- `PRIVATE_KEY`: funded faucet-only deployer key; secret. It is required only
  by Foundry simulation or an explicitly approved broadcast.
- `VAMS_GOVERNANCE_SAFE`, `VAMS_TREASURY_SAFE`: distinct 3-of-5 Safe proxies.
- `VAMS_EMERGENCY_COUNCIL`: distinct pause-only 2-of-3 Safe proxy.
- `VAMS_VDSO_GOVERNANCE_SAFE`, `VAMS_VDSO_TIMELOCK`,
  `VAMS_VDSO_PAUSE_COUNCIL`, `VAMS_VDSO_GUARDIAN`, and
  `VAMS_VDSO_RECOVERY_AUTHORITY`: the verified governance/timelock and three
  distinct 2-of-3 Safe proxies required by the VDSO ceremony.
- `VAMS_SAFE_PROXY_RUNTIME_CODE_HASH`, `VAMS_SAFE_SINGLETON`, and
  `VAMS_SAFE_SINGLETON_RUNTIME_CODE_HASH`; supply the same approved release
  under the `VAMS_VDSO_SAFE_*` names.

Addresses and code hashes are public. Safe owner membership follows the
`ARCHITECT` and `SIGNER_A`-`SIGNER_C` design in the team-signer runbook. Complete setup
transactions, enabled-module/guard/fallback state, nonce, and `ApproveHash`
history must be independently recorded. Current-state queries do not prove a
historically pristine Safe.

## Deterministic local and fork rehearsal

```bash
cd contracts
forge build --sizes
forge test --match-path test/deployment/DeployTestnetAuthority.t.sol -vvv
forge test --match-path test/vdso/DeployVDSOCanary.t.sol -vvv
forge test --match-path test/vdso/VDSOCanaryFoundation.t.sol -vvv
cast chain-id --rpc-url "$POLYGON_AMOY_RPC_URL"
test "$(cast chain-id --rpc-url "$POLYGON_AMOY_RPC_URL")" = "80002"
forge script script/DeployTestnet.s.sol:DeployTestnet \
  --rpc-url "$POLYGON_AMOY_RPC_URL" -vvvv
forge script script/DeployVDSOCanary.s.sol:DeployVDSOCanary \
  --rpc-url "$POLYGON_AMOY_RPC_URL" -vvvv
```

The two `forge script` commands omit `--broadcast`; they simulate and must
succeed against the exact authority instances. Stop if the chain ID, Safe
identity, owner set, threshold, nonce, module pagination, guards, fallback,
singleton, timelock, or role postconditions differ.

## Required rehearsal artifact

Create unsigned `polygon-amoy-rehearsal.json` only from captured simulation and
read-only RPC observations. Validate it with deployment-manifest schema v4 and
`audit_program.py operational --stage canary`. For rehearsal, `commit_sha` and
`deployment_source_sha` must equal the exact checked-out commit. It must bind:

- the exact commit, chain ID, Safe release and runtime identities;
- governance 3-of-5, treasury 3-of-5, emergency 2-of-3 pause-only, distinct
  guardian/quarantine 2-of-3, and distinct recovery 2-of-3 authorities;
- a VAMS timelock delay of at least 172800 seconds and exact role holders;
- zero staking rewards and no staking minter authority;
- every baseline and all seven VDSO addresses, creation transaction, runtime
  code hash, deployer-role removal, and rollback instruction;
- `paused=true` and `empty=true` for every VDSO module, with zero active
  domains, adapters, programs, verifiers, recovery verifier, reservations,
  capabilities, and execution routes.

## Broadcast stop

Do not append `--broadcast` until the user has reviewed the complete simulation
bundle and explicitly approved that specific transaction sequence. After any
approved broadcast, independently query every receipt and postcondition before
recording a deployment manifest. A later public evidence/register commit may
differ from `deployment_source_sha` only when the source commit is its ancestor
and all protected executable and deployment-configuration paths are unchanged.
A failed postcondition triggers the rollback plan: stop, preserve receipts, use
the emergency Safe to keep modules paused, and do not activate or retry with
changed parameters outside a new ceremony.
