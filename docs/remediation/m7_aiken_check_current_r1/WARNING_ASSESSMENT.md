# Strict Aiken gate warning diagnosis

The exact workflow command `aiken check --deny --seed 20260711 --max-success 250` was replayed from a pseudo-terminal in a fresh temporary copy with networking disabled. The canonical Cardano tree was read-only and unchanged: 21 files, digest `7c513c0586cec60d7a030f9d2b453d90a0f4f1b2711c0e5e7c094afb9e43b403`. The pinned Aiken 1.1.21 binary resolved and copied two packages from its existing cache; no network dependency fetch occurred and no tools were installed or fetched.

The command exited 1 with Aiken's terminal summary `1865 checks, 0 errors, 7 warnings`. All seven compiler warnings point to unused symbols in `validators/agent_nft.ak`: unused `bootstrap_ref`, imports `tokens`, `BurnIdentity`, and `MintIdentity`, private function `valid_did`, and modules `list` and `dict`. The CLI suggests renaming the parameter `_bootstrap_ref` and removing unused items. Separate resolver notices state that `aiken-lang/stdlib` and `aiken-lang/fuzz` have uncertain local versions because their versions are unpinned and network is unavailable; the two packages were found in cache. These notices are distinct from the seven compiler warnings reported in the check summary.

This diagnosis does not authorize edits to `agent_nft.ak`: the F04 normative identity entrypoint remains an unresolved owner choice between the frozen standalone path and accepted registry path. Do not silence warnings or alter dependency/vendor pins before that decision. The strict Cardano gate remains failed.

The existing machine-mode run independently reports 122/122 unit/property scenarios passing (115 unit, 7 property); it does not override the strict exit 1 or add F05 ledger credit. Current F05 counts remain 45/55 negative cases and 18/21 mutations. No simulator, ledger, rehearsal, Pre-Prod, or live-network evidence was produced. Readiness remains NOT READY; deployment, Deposit, Slash activation and ExecuteIntent remain disabled. Independent diagnostic review PASS.

See `WARNING_RUN.json`, `WARNING_DIAGNOSTIC.json`, and `WARNING_DIAGNOSTIC.txt` for exact pins and sanitized output.
