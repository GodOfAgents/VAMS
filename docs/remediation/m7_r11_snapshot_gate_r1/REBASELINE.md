# R11 current forward provenance rebaseline - 2026-10-03

Status: scoped provenance rebaseline independently reviewed and accepted.

## Change and binding

The R11 verifier now recognizes manifest version 7 with schema m7-f05-current-forward-v1. This version binds the current 15-file Cardano source set, project inputs, dependency cache, generated blueprint, and all 26 compiled program identities. The exact current lock SHA-256 is acffff4aee9569e1ee1de468839077af467b5e403fd96450290cd367b339c651; the generated blueprint SHA-256 is c4230410d0caac45f2c71d36e45a539c78087697128ce1533306d17e96a48008. Historical F04 baseline attribution is preserved, and raw lock continuity remains explicitly unresolved.

The v7 verifier branch keeps the exact closed program-name/hash checks and requires 26 programs only for v7. Existing v3-v6 manifest shape/count behavior remains versioned. The focused tests cover the new source inventory, current lock binding, F04 historical attribution, schema/baseline/lock mutations, blueprint drift, and mutation detection.

## Verification

- Pinned Python 3.12.14 py_compile: passed.
- python -m unittest -v scripts.remediation.test_m3_1b_r9_provenance: 21/21 passed.
- Two fresh invocations of scripts/remediation/verify_m3_1b_r9.py each ran pinned Aiken 1.1.21 check and build in separate disposable workspaces; both exited 0 and produced identical structured results, source digest, blueprint digest, and 26 program hashes. Full records: current-verifier-run.json and current-verifier-run-b.json.
- Workflow Python root gate: 1575 passed and 441 subtests passed. The workflow's separate F05 design suite: 10/10 passed.
- git diff --check: passed.
- The required Aiken check --deny --seed 20260711 --max-success 250 gate remains failed (122/122 test scenarios, exit 1, seven warnings in the latest captured diagnostic). This slice does not claim G1 acceptance.

The exact commands, exits, pinned tools, hashes, and independent-review result are in REBASELINE_RUN.json. Read-only independent integrated review: PASS; no edits. F05 counts remain 45/55 negative cases and 18/21 mutations, with no new credit.

## Limits and next gate

This is offline compiler/build provenance plus local test evidence. It does not establish ledger admission, Cardano Pre-Prod rehearsal, Polygon Amoy rehearsal, or live-network behavior. Testnet readiness remains NOT READY and deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

The next dependency-ordered blocker is the F04 normative identity-path choice. The frozen design spec names standalone agent_nft.agent_nft.mint, while accepted R6 uses agent_registry.agent_registry.mint; do not change validator behavior until the owner selects the normative path.
