# M7 Native Aiken G1 Gate (R1)

Status: independent record review PASS; required CI-equivalent command failed; full current-source G1 coverage pending.

Observed date: 2026-10-02
Repository: /home/GodOfAgents/code/VAMS-testnet
Branch: testnet/remediation-20260907
HEAD: 829ab544571f12efe50ecb5740f129c8acb3e16f

## Scope and result

The Cardano G1 command from .github/workflows/security-gates.yml was run against a copied Cardano snapshot using the existing pinned Aiken 1.1.21 binary and the already-present package archive cache. The execution ran in a bubblewrap network namespace with --unshare-net; the canonical checkout was not mounted writable. Build output went to the disposable snapshot. All 68 source/dependency-manifest files represented in the run's recorded hash map matched their preflight hashes and remained unchanged during the run.

The command compiled the project and both cached dependencies, then reported 120/120 scenarios passed (113 unit and 7 property). However, the command returned exit 1 because Aiken could not verify the unpinned v2 Git dependency references without network access. With the CI-required --deny option, its "Using uncertain local version" warnings fail the command. This is not a passing CI-equivalent G1 gate. It is captured native compile/test execution with a failed required command and an environment limitation. No reported test case failed.

The snapshot contained 48 Aiken source files. Three current F05 authority sources were not represented in the 68-file recorded hash map: lib/vams/f05_authority.ak, validators/f05_authority_policy.ak, and validators/f05_authority_state.ak. The structured test output lists agent_nft, agent_registry, insurance_fund, vams/icb, vams/utils, and vams/vdso; it lists no F05 module or F05 test. This evidence therefore does not establish test coverage for those F05 files or complete current-source G1 coverage. A fresh final-tree gate with source hashes covering all current Cardano inputs remains necessary.

A first isolated attempt (R1 harness) stopped during dependency resolution before compilation or testing, so it receives no compile/test credit. Its temporary HOME did not expose the global Aiken cache; attributing the failure to the absent cache mount is an inference from the wrapper setup and the successful cache-mounted retry, not an explicit diagnostic in the R1 transcript. R2 mounted the existing cache read-only and executed the test scenarios, but the required command still exited 1 as described above. No dependency, tool, or source was fetched or installed.

## Exact command and evidence

Required CI command: aiken check --deny --seed 20260711 --max-success 250.

It ran as the final command inside this no-network wrapper, with the existing archive cache mounted read-only at /tmp/aiken-home/.cache/aiken and the disposable snapshot mounted at the canonical cardano path:

```text
bwrap --unshare-net --ro-bind / / --tmpfs /tmp --dir /tmp/aiken-home --dir /tmp/aiken-home/.cache --ro-bind /home/GodOfAgents/.cache/aiken /tmp/aiken-home/.cache/aiken --bind /home/GodOfAgents/vams-evidence/m7-aiken-g1-native-20261002-r2/snapshot/cardano /home/GodOfAgents/code/VAMS-testnet/cardano --chdir /home/GodOfAgents/code/VAMS-testnet/cardano --setenv HOME /tmp/aiken-home --setenv XDG_CACHE_HOME /tmp/aiken-home/.cache /home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/unpacked/aiken-x86_64-unknown-linux-musl/aiken check --deny --seed 20260711 --max-success 250
```

- Exit status: 1.
- Test summary in Aiken's structured output: 120 total, 120 passed, 0 failed; 113 unit and 7 property scenarios.
- Dependency diagnostics: "Using uncertain local version" for aiken-lang/stdlib and aiken-lang/fuzz, because the network is unavailable and declared Git tags are unpinned.
- Pinned Aiken: v1.1.21+42babe5; binary SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79.
- aiken.lock SHA-256 6f3b369ff5e7caf986ddf9b877af8bf1b71679307d90155e59f128313648d60f.
- aiken.toml SHA-256 55984b24927897c47dbf45933911b804047d0200bdf9a47942efded8b6ed4683.
- Dependency-manifest SHA-256 f0f27c4fbc72dffbc51d6baec2056316eefe94eedc75bdf7f9b1190741b732b0; package-index SHA-256 6343ba3b788a2e43f6ac7043aa53c427dcd7190088ea83c14054f2a5dd0417af.
- Captured JSON: /home/GodOfAgents/vams-evidence/m7-aiken-g1-native-20261002-r2/verification.json, SHA-256 d6625aca22ef0e8be37a4f372209ece3f75c3480dfe94a5b586191c4aaad84b1.
- Captured transcript: /home/GodOfAgents/vams-evidence/m7-aiken-g1-native-20261002-r2/verification.txt, SHA-256 43f39b21e26dcd68549e8fe479740ce571f5defcb5b84923bc81c68fa911c958.
- Failed pre-compilation R1 harness transcript: /home/GodOfAgents/vams-evidence/m7-aiken-g1-native-20261002-r1/verification.txt, SHA-256 44820b2286705bb9099e8903e72d418ee0b2fed1a2519e86bcab66818b3198b6.

## Independent review

Independent record review: PASS after source-coverage, R1 attribution, and encoding clarifications. The reviewer verified all 12 packet hashes and sizes, confirmed the command against workflow line 422, parsed the 120/120 result and exit 1, and confirmed the coverage and readiness limits. The reviewer did not replay Aiken or independently verify preservation of the canonical checkout.

## Evidence limits and impact

This is local native Aiken execution evidence only. The 120 successful scenarios do not convert command exit 1 into a passing gate. The run did not provide recorded hash coverage for three F05 Aiken sources and reported no F05 test module. It is not hosted CI evidence, ledger admission, a Cardano Pre-Prod rehearsal, or live-network evidence. No canonical Aiken source, lockfile, generated artifact, workflow, credential, or activation state changed. INV-1 through INV-10 behavior is not changed. No changelog update is required.

F05.2a remains at 45/55 negative cases and 18/21 mutations. Full readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled. The network restriction and user instruction against fetching prevent local resolution of the Git tag-version warning. Reassessment of the full roadmap follows this reviewed record.
