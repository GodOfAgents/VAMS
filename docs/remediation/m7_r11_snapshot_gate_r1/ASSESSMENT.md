# R11 authoritative-source mutation test diagnosis ºw^~)Þt 2026-10-03

## Finding

The isolated test failure is a valid fail-closed response to current Cardano inputs that no longer match the R11 manifest. Do not broaden the accepted error regex or weaken input validation.

The exact workflow-environment invocation

`env PATH=/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin VAMS_ENV=test PYTHONDONTWRITEBYTECODE=1 VAMS_ENVOY_BIN=/home/GodOfAgents/vams-evidence/toolchains/envoy-1.39.1/envoy /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/pytest -vv --tb=long scripts/remediation/test_m3_1b_r9_provenance.py::R11BoundaryTests::test_authoritative_mutation_detected`

failed before the injected mutation with `authoritative project hash mismatch`. Current `cardano/aiken.lock` SHA-256 is `acffff4aee9569e1ee1de468839077af467b5e403fd96450290cd367b339c651`; the manifest binds `6f3b369ff5e7caf986ddf9b877af8bf1b71679307d90155e59f128313648d60f`. The timestamp-normalized lock digest still matches `f90d45886ca23d8661ae9973940ec03d9496ffc4e8caa9abe32fea69e938835a`.

A disposable diagnostic changed only those manifest lock anchors temporarily, then reran the test. Validation advanced and failed with `compilation source set or digest mismatch`. That temporary change was reverted. Current source inventory is 15 files against 11 manifest entries: extra files are `lib/vams/f05_authority.ak`, `validators/f05_authority_policy.ak`, `validators/f05_authority_policy.test.ak`, and `validators/f05_authority_state.ak`. Five shared source digests differ: `lib/vams/governance.ak`, `validators/governance_policies.ak`, `validators/governor.ak`, `validators/insurance_fund.ak`, and `validators/timelock.ak`. The current root also has dirty changes to shared Cardano types and validators. No source or applied validator was changed in this diagnosis.

## Independent review

Read-only independent diagnosis review PASS. Reviewer independently confirmed the raw/normalized lock hashes, 11-versus-15 source inventory, four additional F05 files, five digest drifts, and that the test fixture copies current canonical bytes before injecting the mutation. The reviewer found no valid test-only adjustment without a verified immutable baseline snapshot. The inspected R6 evidence package contains hashes, commands, and reviews, but no source snapshot. Reviewer did not edit files or run tests.

The reviewer also noted a separate policy inconsistency: `docs/remediation/m3_1b_r11/DEPENDENCY_PROVENANCE.md` describes timestamp-only lock etag changes as allowable, while the verifier still binds the exact raw lock hash. This does not explain or resolve the source inventory and source digest drift; address it as a separate bounded slice if the owner confirms that documented allowance is normative.

## Decision required and current state

Before this test can pass meaningfully, the owner must choose the provenance subject:

1. Authorize the complete current dirty Cardano input tree as a new forward-only R11 baseline, followed by isolated pinned Aiken check/build, updated exact source/lock/project/blueprint bindings, targeted tests, and independent review; or
2. Preserve the accepted R6 baseline and recover its exact immutable inputs before exercising the mutation test.

No F05 negative/mutation counts changed. This diagnosis grants no ledger admission or live-network evidence. Testnet readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
