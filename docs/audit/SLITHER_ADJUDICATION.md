# Slither Finding Adjudication

**Scan date:** 2026-07-11  
**Scope:** `contracts/src/`, excluding vendored dependencies  
**Command:** `slither . --exclude-dependencies --filter-paths lib --exclude-low --exclude-informational --fail-high`

The high-impact gate passes. The medium/high-only scan reports 18 results after
remediation, reduced from 42. This document records why the residual results do
not represent unresolved exploitable paths. Any material code or trust-boundary
change invalidates this adjudication and requires a fresh scan.

## Remediated Findings

- `WorldIDPlugin` no longer accepts structurally valid placeholder proofs. It
  calls the configured verifier and binds the proof to the VAMS action and the
  service/delivery signal.
- `ServiceBlockRegistry.registerServiceBlock`, `SLAEnforcer.retryPendingSlash`,
  and `SecurityBudgetEnforcer.updateSecurityStatus` now use `nonReentrant`.
- Batch claims, x402 claims, staking compounding, hardware commitments, Service
  Block registration, Sentinel TVL updates, and security-level transitions now
  apply state effects before external interactions.
- Voting-power multipliers use one `Math.mulDiv` operation, avoiding
  divide-before-multiply precision loss.
- Constructor-only state was made immutable where deployment semantics permit.
- The SLA node lookup, provider rejection reason, and storage-array length
  findings were resolved directly.

## Residual Findings

### Incorrect Equality: 14 Results, False Positive

These checks intentionally require exact equality. None compares a market
price, ratio, timestamp target, or other continuously varying value.

- Zero-value existence sentinels: pending timelock, active hardware commitment,
  hardware registration timestamp, checkpoint existence, fee total, stake
  total, reward amount, and releasable vesting amount.
- Exact enum membership: pending compensation claims.
- Exact zero guards: reward claim, compound, mint, and budget validation.

Changing these checks to inequalities would weaken existence and state-machine
invariants. Existing Forge tests cover duplicate registration/checkpoint paths,
empty rewards, staking pool updates, and vesting release behavior.

### Reentrancy Without ETH: 2 Results, Guarded and Accepted

1. `TwoPhaseCommitManager.initiateWorkflow` is `nonReentrant`. The external
   escrow manager must return each generated escrow ID before that ID can be
   appended to `_workflowEscrows`. A callback can only observe the already
   initialized workflow through view functions; it cannot enter a mutating
   workflow path. Any failed escrow call reverts the complete transaction.
2. `SLAEnforcer.retryPendingSlash` is `nonReentrant` and sets `retried = true`
   before calling the slasher. It resets the flag only when the slash fails so
   governance can retry. A callback can transiently observe the flag but cannot
   mutate the pending-slash queue or obtain value from that observation.

These are read-only intermediate-state observations, not unguarded economic
reentrancy. Reassess if a future contract consumes either view during a callback
to authorize value transfer.

### Unused Return: 1 Result, False Positive

`VAMSERC8004Adapter.verifyAndRegister` intentionally reads only the owner from
`getAgent`. The remaining tuple fields are not authorization inputs for this
adapter. TEE attestation validity comes from the configured ERC-8004 verifier,
and ownership is independently enforced against `msg.sender`.

### Immutable State: 1 Result, Not Applicable

`VAMSToken.antiWhaleEndTimestamp` is assigned in the proxy initializer. Solidity
immutables are embedded in implementation bytecode and cannot hold per-proxy
initializer state, so converting this field would break upgradeable deployment
semantics.

## Gate Decision

- High-impact findings: **0 unresolved**.
- Medium scan results: **18 adjudicated**.
- Low/informational/optimization findings remain visible in the complete report
  and are not promoted to security closure without manual review.
- This adjudication does not replace external review, invariant fuzzing, or the
  exact-commit CI evidence manifest required for testnet.
