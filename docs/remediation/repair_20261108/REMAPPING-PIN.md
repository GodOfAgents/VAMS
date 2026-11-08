# Explicit Foundry remappings for reproducible runtime identity — 2026-11-08

## Defect

`contracts/remappings.txt` pinned only `@openzeppelin/contracts/` and
`@openzeppelin/contracts-upgradeable/`. Foundry auto-detected the remaining
remappings. `forge-std`, `erc4626-tests` and `halmos-cheatcodes` each exist in
several nested submodules, so the chosen path depends on directory layout.
Remappings are part of solc metadata, so the CBOR metadata hash, and with it
the runtime `extcodehash`, changed between checkouts.

## Reproduction (BEFORE)

Fresh `git archive` export of backup commit `6ab8c8f` plus recursively exported
submodules, on the new WSL D1 runner (Foundry 1.7.1, solc 0.8.24 binary sha256
`fb03a29a…0d5f`, both equal to the pins in `RestrictedPolicyRuntimeV1.sol`):
`forge test -vvv` → 1118 passed, 5 failed, 0 skipped (1123). All failures were
`PolicyRuntimeMismatch()` in setUp or the captured-runtime assertion in
`RestrictedPolicyRuntimeV1.t.sol` and `GovernedHeartbeatPrincipalRegistryV1.t.sol`.

Diagnosis: compared with the captured artifact
`VAMS-implementation-20261029/policy-runtime-artifact67/RestrictedTestnetPolicyV1.json`
(sha256 `263d0efb…5b6c`, the pinned value), every source keccak and every other
compiler setting matched; only `settings.remappings` differed, and the runtime
bytecode was identical except for the trailing metadata.

## Repair

Append the six auto-detected remappings to `contracts/remappings.txt`, choosing
exactly the paths recorded in the captured artifact's metadata. No Solidity
source, compiler setting, pin or test changed.

## Result (AFTER)

Same export and runner with the repaired file: `forge test` → 1141 passed,
0 failed, 0 skipped across 71 suites, matching the CHECKPOINT83 record.
Raw streams: `~/vams-baseline-logs/forge-test.stdout` (before) and
`forge-test-fix.stdout` (after) on the runner.

## Scope and limits

Local owner-workstation evidence only (not independent CI, not non-author
reviewed yet). Improves T09/T11 reproducibility and future deployed-bytecode
verification (F16); closes no finding or track. Readiness remains NOT READY:
13 findings open, 0 of 36 tracks verified.
