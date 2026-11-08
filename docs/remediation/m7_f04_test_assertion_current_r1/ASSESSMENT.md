# F04 legacy mint expectation correction

Date: 2026-10-04
Status: accepted test-only correction

## Change

Changed only the `required_legacy` body token in `docs/remediation/m3_f04_impl_r2/test_interface_migration.py`. The expected substring now includes the current `expect _unused_bootstrap_ref = bootstrap_ref` binding followed by `False`. The current validator at `cardano/validators/agent_nft.ak` still rejects minting unconditionally after the binding.

The frozen identity specification SHA-256 is `eaabb61ef8a4f454ab7bb2f138ea67a767f3effdff917fc95520be7de9c90c80` and still identifies `agent_nft.agent_nft.mint`; accepted implementation evidence describes the registry mint path. This correction does not choose between them. INV-1 through INV-10 enforcement paths are not touched.

## Verification

- Focused pinned pytest command: exit 0, 1 passed (`0.21s`).
- Documentation validation: exit 0, “Documentation validation passed.”
- Documentation validator unit tests: exit 0, 2 passed.
- Python AST parse: exit 0.
- `git diff --check`: exit 0.

Exact commands and machine-readable outputs are in `RUN.json` and `RESULT.json`. Test, validator, and identity-spec hashes are recorded in `RUN.json`; Git HEAD was `829ab544571f12efe50ecb5740f129c8acb3e16f`.

## Independent review and limits

Independent review: PASS with the untracked-test-file caveat in `REVIEW.md`. This is a focused test result only. The full Python workflow suite must be rerun; no F04 owner decision, F05 credit, ledger, rehearsal, live-network, or deployment evidence is gained. Readiness remains NOT READY.
