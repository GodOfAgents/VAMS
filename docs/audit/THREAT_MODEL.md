# VAMS Testnet Threat Model

## Assets And Trust Boundaries

| Boundary | Assets | Principal threats | Required controls |
| --- | --- | --- | --- |
| User/agent to Gateway | DID authority, session scope, request intent | Replay, forged identity, oversized input, credential theft | DID signatures, nonce cache, mTLS, limits, core-contract allowlists |
| Gateway to Neuron runtime | Routing and economic side effects | Prompt injection, duplicate execution, mock substitution | Capability checks, idempotency, live-mode deny rules, audit hashes |
| Runtime to DA/oracles | Evidence used for rewards and disputes | Forged receipt, stale value, outage fallback confusion | Real receipt verification, fixed stale fallback, proof/payload separation |
| Polygon contracts | Supply, escrow, rewards, insurance, roles | Reentrancy, cap bypass, insolvency, admin capture | INV-1..INV-9, CEI/guards, Safe/timelock, invariant tests |
| Cardano validators | Governance, bridge, insurance, identity | Datum substitution, replay, double satisfaction, signer confusion | Continuing-output checks, nonce properties, proof separation, multisig |
| Governance and recovery | Upgrade, treasury, pause authority | Single-key capture, malicious upgrade, permanent pause | Distinct 3-of-5 Safes, 48-hour delay, 2-of-3 pause-only council |
| Telemetry and memory | PII, prompts, cognitive and provider signals | Leakage, poisoning, unauthorized persistence or erasure | Schema allowlists, hashed identifiers, reviewer authorization, hard reset |
| Build and release | Source, dependencies, artifacts, evidence | Supply-chain compromise, stale claims, unsigned promotion | Pinned tools, secret scans, signed SBOM/evidence, commit/hash binding |

## Stop Conditions

Deployment stops on an unmitigated high/critical finding, invariant failure,
mock-backed live evidence, unsigned or commit-mismatched evidence, deployer-held
privilege, missing Safe/timelock proof, regional allocation above 30%, or any
canary exposure and concentration threshold in `testnet-profile.json`.

## Residual Risks

- Celestia/Near receipts, Gateway external tests, and chain deployment evidence
  do not exist until the controlled runtime ceremony is executed.
- Aiken transaction-level state-machine properties and independent reviews are
  still required.
- Staking rewards remain disabled; enabling them requires a separately reviewed
  solvency model rather than relying on the canary profile.
- Structural bridge and TEE tests do not replace production cryptographic
  verifier evidence.
