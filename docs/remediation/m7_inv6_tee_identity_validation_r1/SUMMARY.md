# INV-6 TEE root-identity validation

Date: 2026-10-04

## Result

The five focused tests passed in both executions. The primary run exited 0 (5 passed in 1.35s). The independent rerun exited 0 with exact output:

```text
..... [100%]
5 passed in 1.39s
```

The cases require an explicit nonzero 20-byte root EOA, bind service and delivery report data to the root address, reject root/session-key substitution, reject a mismatched provider root, and reject simulated non-authoritative evidence at the live verification boundary.

## Exact command

```text
bwrap --unshare-net --ro-bind / / --tmpfs /tmp --dev-bind /dev /dev --proc /proc --chdir /home/GodOfAgents/code/VAMS-testnet /usr/bin/env -i HOME=/tmp TMPDIR=/tmp VAMS_ENV=test PATH=/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin:/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 TZ=UTC PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python -B -m pytest -q --tb=short -p no:cacheprovider neuron/tests/test_m1_2a_identity_tee_runtime.py::test_tee_plugin_accepts_live_report_bound_to_root_eoa neuron/tests/test_m1_2a_identity_tee_runtime.py::test_tee_plugin_rejects_session_key_substitution neuron/tests/test_m1_2a_identity_tee_runtime.py::test_tee_plugin_rejects_wrong_provider_root_binding neuron/tests/test_m1_2a_identity_tee_runtime.py::test_non_live_simulated_proof_cannot_cross_live_verification_boundary neuron/tests/test_trust_plugins.py::TestTEEPlugin::test_requires_explicit_root_eoa
```

Pinned Python 3.12.14 and pytest 9.1.1. Network was disabled, the checkout was read-only, writes were confined to tmpfs `/tmp`, and bytecode and pytest cache were disabled.

## Scope and limits

These tests use synthetic local reports and a `FakePhalaClient`; they establish local contract behavior only. They are not live TEE or provider evidence. No source changed. F05 remains 45/55 negative cases and 18/21 mutations. Readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
