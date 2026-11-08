# M3.2a-R11 remediation of R10

Date: 2026-09-26
Scope: local remediation only; no M3.2b implementation.

R10 reproduction confirmed the address formula mismatch, malformed target-domain oracle fixture, equation-preserving topology mutation, mutable execute_pre_f05 matrix semantics, incomplete oracle typing/lifecycle coverage, and reserve-input error leak.

R11 changes:

- corrected the enterprise address formula and added machine-checked network 0, 1 and 15 key/script vectors;
- enforced target-domain length-prefix equality and independent corrected digest tests;
- bound exact frozen SHA-256 digests for all five normative R7 JSON artifacts while retaining an enforce_frozen=False semantic seam for mutation tests;
- bound complete topology and acceptance-matrix semantic digests and explicit ExecuteIntent pre-F05 rejection semantics;
- expanded the independent oracle with strict schemas, full topology records, value-flow checks, address boundaries, target-domain parsing, lifecycle weighting/quorum/timing, and sanitized OracleError failures;
- added mutation-sensitive regressions for all R10 finding classes.

Verification:

- governance validator CLI: pass, 4 assets, 7 datums, 9 topology rows, 81 matrix rows;
- governance tests: 12/12 pass;
- independent oracle tests: 7/7 pass;
- provenance implementation and manifest-v3 are intentionally unchanged by R11;
- aiken.lock and all Cardano sources remain unchanged;
- F01-F05 remain open, F02/F03 remain open, Deposit and Execute remain disabled, M3 remains OPEN, Pre-Prod admission is INCONCLUSIVE, and promotion is NOT READY.

INV-1 through INV-10, mock behavior, deployment state, credentials and production validators are unchanged. Min-ADA, applied budgets and M3.2b remain outside this slice and are not authorized.
