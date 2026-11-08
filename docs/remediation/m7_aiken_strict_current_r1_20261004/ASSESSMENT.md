# M7 current-source strict Aiken gate — 2026-10-04

The pinned strict Aiken gate passed against the current Cardano source snapshot: 124/124 checks, comprising 117 unit and 7 property tests. Property tests ran with --max-success 250. The command used --deny and exited 0.

Exact command: /home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken check --deny --seed 20260711 --max-success 250.

Toolchain: Aiken v1.1.21+42babe5, SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79. Bubblewrap 0.11.1, SHA-256 0abea81db798ebf6b4742ac0664802d97521547a353c2a0dbdc21d76cbbfd2c0.

Execution used bwrap --unshare-net. The canonical checkout was bound read-only at /tmp/canonical; a fresh writable Cardano snapshot was mounted at /tmp/workspace and was the only test working directory. Host network namespace remained 4026531833 and child namespace was 4026532231. Canonical source inventory and Git status matched before/after; the snapshot Cardano inventory remained 78 files before and after.

Independent review PASSed the exact capture and excluded the first setup attempt correctly. Attempt 1 stopped before Python/Aiken execution because bubblewrap could not create /canonical under a read-only root; it is a sandbox setup failure, not a test result. Attempt 2 created mountpoints under /tmp and ran the exact command above.

This is local validator check evidence only. It does not establish ledger admission, Cardano Pre-Prod, or live-network behavior. It does not resolve the separate Python F04 failures or F05 ledger classifications. No canonical source, tests, dependencies, credentials, toolchain, or Git refs changed. Readiness is NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
