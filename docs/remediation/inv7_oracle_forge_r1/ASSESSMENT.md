# INV-7 Foundry gate availability diagnosis

Date: 2026-10-03
Disposition: not executed; required compiler unavailable offline.

## Observed state

The current CommitRevealOracle source exposes a deployment-fixed stale fallback and rejects requests that are not yet expired or already resolved. Its targeted Foundry tests cover fallback selection, rejection before expiry, and replay rejection.

Foundry 1.7.1 is available in the local toolchain store, but the project requires solc 0.8.24 and no compatible local compiler was found. The network-isolated command below exited 1 before test execution:

`forge test --offline --match-path test/oracle/CommitRevealOracle.t.sol --out /home/GodOfAgents/code/VAMS-testnet/docs/remediation/inv7_oracle_forge_r1/out --cache-path /home/GodOfAgents/code/VAMS-testnet/docs/remediation/inv7_oracle_forge_r1/cache -vvv`

Output: `Error: can't install missing solc 0.8.24 in offline mode`.

No contract test ran, so this is an unavailable-toolchain result, not a test failure or an INV-7 pass. No install, fetch, source edit, or network action occurred. Exact command, tool hash, and current source/test hashes are in RUN.json.

## Scope and next action

INV-7 runtime verification remains open. The independent Python runtime-mode containment gate is the next safe slice while this Solidity compiler remains unavailable.
