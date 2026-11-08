# M7 Complete Current-Input Aiken Capture (R1)

Status: independent review PASS as a diagnostic capture; required CI-equivalent command failed; full current-source G1 gate remains open.

Observed date: 2026-10-02
Repository: /home/GodOfAgents/code/VAMS-testnet
Branch: testnet/remediation-20260907
HEAD: 829ab544571f12efe50ecb5740f129c8acb3e16f

## Scope and result

This bounded evidence-integrity slice reran the unchanged Cardano G1 Aiken command using a new isolated snapshot and a complete input capture. The run record reports that canonical Cardano inputs and the disposable snapshot matched before execution for all 72 enumerated source/configuration/vendor inputs. This covered all 48 current project .ak files, all files under cardano/build/packages, and aiken.toml, aiken.lock, and aiken-dependency-manifest.json. The capture separately recorded both existing global Aiken package archives, the pinned Aiken executable, and the current CI workflow.

The full snapshot included and hash-bound the three current F05 sources:
- lib/vams/f05_authority.ak: SHA-256 657f30dfc0ecb40f50b2c0442b78f4818de1644f540fb68d76cfb2de72cccdd3
- validators/f05_authority_policy.ak: SHA-256 5c01f9556d922a719a7dac348d8b7175d660ef387fdf2005979c27fb2e833b05
- validators/f05_authority_state.ak: SHA-256 ad15a7416d2069127138d8817b41a920223bbd3d875fdb7b0c9fc3bb60944774

The run record's postflight comparisons report that canonical inputs, snapshot inputs, both global cache archives, and the workflow retained their preflight hashes. The independent reviewer verified all 72 recorded Cardano input hashes against the packaged snapshot. The reviewer could not independently recompute canonical-side pre/post comparisons because those are represented by booleans without canonical-side digest maps. The packet also omits the raw Aiken binary and global cache archives, so their captured hashes were not independently recomputed. These are explicit limits of this diagnostic evidence.

The unchanged CI command compiled the project and cached dependencies and reported 120/120 scenarios passed (113 unit, 7 property). It returned exit 1. Stderr reports both unpinned v2 Git dependency references as "uncertain local version" because network access was unavailable. The command includes the required --deny flag, so attribution of the nonzero result to warning denial is consistent with the output, but Aiken did not print an explicit final "warning denied" diagnostic. The G1 command is failed regardless of that causal interpretation and receives no pass credit.

The structured test output lists agent_nft, agent_registry, insurance_fund, vams/icb, vams/utils, and vams/vdso; it lists no F05 test module. Complete input identity is captured, but F05 behavior coverage and a passing CI-equivalent command remain open.

No tools or packages were installed or fetched from the network. Aiken loaded the two archives from the existing read-only cache. The earlier M7 Aiken record remains a historical account of its narrower 68-file hash map; this record supplements it with complete current-input identity and a fresh run.

## Exact command and evidence

The required command from .github/workflows/security-gates.yml:422 was:
```bash
aiken check --deny --seed 20260711 --max-success 250
```

It ran as the final command inside a bubblewrap --unshare-net namespace with the existing cache read-only and the disposable Cardano snapshot bound at the canonical path. Exit status: 1. Structured result: 120 total, 120 passed, 0 failed; 113 unit and 7 property.

- Pinned Aiken: v1.1.21+42babe5; executable SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79.
- Current workflow SHA-256 7ddeb89794f498393e9c3bb460ca1aaa74dde7b9637c590d76cdae3bbc3ec83a.
- aiken.toml SHA-256 55984b24927897c47dbf45933911b804047d0200bdf9a47942efded8b6ed4683.
- aiken.lock SHA-256 6f3b369ff5e7caf986ddf9b877af8bf1b71679307d90155e59f128313648d60f.
- Dependency manifest SHA-256 f0f27c4fbc72dffbc51d6baec2056316eefe94eedc75bdf7f9b1190741b732b0; vendored package index SHA-256 6343ba3b788a2e43f6ac7043aa53c427dcd7190088ea83c14054f2a5dd0417af.
- Verification JSON: /home/GodOfAgents/vams-evidence/m7-aiken-g1-native-20261002-r3/verification.json; SHA-256 bee9da2836cfa7ce5945098a4e250b95894bfd2eef725ddc559f44803c3e8e16.
- Transcript: /home/GodOfAgents/vams-evidence/m7-aiken-g1-native-20261002-r3/verification.txt; SHA-256 27053b690e8c68e75c9eebf947b865c83bfe0c4ed459de79359f49065a802899.

## Independent review

Independent record review: PASS as a diagnostic capture only. The reviewer verified all 83 packet manifest entries, all 72 Cardano input hashes against the packaged snapshot, the F05 source paths, workflow command, test totals, exit status, offline diagnostics, and readiness classification. The reviewer did not replay Aiken and could not independently recompute canonical-side comparisons or raw tool/cache hashes from the packet. The reviewer also noted that Aiken did not explicitly state that --deny caused exit 1. This record preserves those limits; the required G1 command remains failed and receives no pass credit.

## Evidence limits and impact

This is local native execution and input-capture evidence only. It is not a passing required G1 command, hosted CI, ledger admission, a Cardano Pre-Prod rehearsal, or live-network evidence. The run lists no F05 test module, so it does not establish F05 behavior acceptance. No canonical source, lockfile, workflow, credential, activation state, or deployment state changed. INV-1 through INV-10 behavior is unaffected; no changelog update is required.

F05.2a remains 45/55 negative cases and 18/21 mutations. Full readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled. Reassess the full roadmap after final review of this diagnostic record.
