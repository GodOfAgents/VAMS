# VAMS Testnet Deployment Ceremony

Required gates:

- `cd contracts && forge build --sizes && forge test -vvv`
- `cd cardano && aiken check && aiken test`
- `pytest -v --tb=short`
- `bandit -r neuron/ gateway/ -ll -ii`
- `pip-audit`
- `cd frontend-vite && npm ci && npm run build && npm audit --audit-level=high`
- `gitleaks detect --source .`

Block deployment if:

- Any required test or scan fails.
- Any live path uses mock DA, OMS, Trails, TEE, escrow, or bridge evidence.
- `vams2026` appears in accepted credential paths.
- Role owners are EOAs where multisig/timelock is required.
- Contract addresses or deployment txs are not recorded.
- Previous compromised/dead V1 addresses are reused.

Deployment order:

1. Libraries and base dependencies.
2. Token and governance primitives.
3. Registries and hardware/service modules.
4. Economic and settlement modules.
5. Oracle, sentinel, slashing, and DA anchors.
6. Role grants, timelocks, multisig ownership transfer.
7. Gateway live-mode configuration and smoke tests.
