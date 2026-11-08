# R11 current-forward source and blueprint rebaseline - 2026-10-04

## Bound inputs and result

The current-forward manifest is `cardano/aiken-dependency-manifest.json`, schema `m7-f05-current-forward-v1`, manifest version 7. It binds 16 current `.ak` sources, three project inputs, and the pinned dependency cache. Source map digest: `4a896a2df8254afc022207fd8477087106cb4ff242d6d1b753026973afb8f960`. Raw lock SHA-256 remains `7c69f0a484d3b42862dc0ab0773cf6b3edf72709c921b2ad3648a0753af8cafc`; historical R1 raw lock continuity remains explicitly unresolved.

Two separate bwrap `--unshare-net` runs used the pinned Aiken 1.1.21 binary and cached dependencies. Each Aiken check passed 124/124 (117 unit and 7 property checks); each build exited 0. Both generated blueprints were byte-identical, SHA-256 `718845f253ebdfb9f1d565e34511534f6b565cf1dd898402b67109180dff6492`.

Compared with the prior canonical blueprint, exactly six JSON leaves changed: `compiledCode` and `hash` for `agent_registry.agent_registry.else`, `.mint`, and `.spend`. The generated script hash for those three programs is `84ddad41e145d37fce9626facbe8b0e7994c1935749ada1ee4dc3cfb`; all other 23 program identities match. The current blueprint and manifest now agree for all 26 programs.

## Integrated verification

- `PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/pytest -v --tb=short scripts/remediation/test_m3_1b_r9_provenance.py`: exit 0; 22 passed, 78 subtests passed, one pytest cache warning.
- Two separate `python -B scripts/remediation/verify_m3_1b_r9.py` runs: exit 0 each; outputs byte-identical, SHA-256 `2bb7bcadc4fc1cd2f2bc26fc90a0123407c9c27144f7fddeb175735809623a98`. Each reports 16 sources, 26 programs, Aiken check/build exit 0, and the current source/blueprint digests.
- `git diff --check`: passed.
- Independent source/artifact review: PASS. Independent verification-capture review: PASS.
- Exact raw captures: `/home/GodOfAgents/vams-evidence/m7-r11-aiken-netns-independent-r1-20261004/` and `/home/GodOfAgents/vams-evidence/m7-r11-integrated-refresh-verification-r1-20261004/`.

The verification capture's pre-run status summarizes six pre-existing untracked directories while its post-run status expands them. Independent review found the tracked status identical and every expanded untracked path present in the earlier full inventory. The capture has no pre-run full file inventory; its exact inputs are hash-bound, canonical checkout was mounted read-only, and the verifier's source-stability checks passed.

## Limits and next blocker

This is local source/build provenance only. The Aiken check was ordinary `aiken check`, not the separate `--deny` gate. There is no ledger admission, Cardano Pre-Prod, Polygon Amoy, or live-network evidence.

F04 remains blocked on the owner choice between shared and per-identity policy IDs/anchor authority in `docs/remediation/m7_f04_policy_anchor_gate_r1_20261004/ANCHOR-DECISION.md`. Current Python workflow run r2 predates this refresh; the full workflow suite must be rerun. F05 ledger totals remain 45/55 negative cases and 18/21 mutations. Readiness remains NOT READY; deployment and gated activations remain disabled.
