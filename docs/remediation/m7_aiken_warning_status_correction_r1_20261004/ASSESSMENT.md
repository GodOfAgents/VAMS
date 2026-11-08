# M7 current-source strict Aiken warning status correction — 2026-10-04

## Scope

This is a records-only correction for the warning-specific G1 statement in docs/remediation/m7_agent_nft_audit_r1/ASSESSMENT.md. It does not select or alter the normative F04 identity entrypoint and does not change validator behavior.

## Current-source evidence

The accepted package docs/remediation/m7_aiken_warning_cleanup_r1/ records the pinned strict workflow command aiken check --deny --seed 20260711 --max-success 250 with exit 0, 1,865 checks, zero errors, and zero warnings. Its embedded independent review records a fresh strict check, 122/122 scenarios, provenance build, focused tests, and all 11 package checksum/source-hash checks passing.

A read-only comparison for this correction reproduced the accepted 21-file Cardano inventory digest 437ac6eef5acb1807d8f6a68b47fdff2e9b3fbe7ed7ca3e39715a767edf59f86. Current hashes match the accepted cleanup result for:

- cardano/validators/agent_nft.ak: e28ff520d07f73a622a093b362f66411678d535bbb48cf2aecbcd8011204caba
- cardano/validators/agent_registry.ak: 7655acb5d48cb0abcfe85dadfe9aa9c80046bff3aeeaf0720cb706084adbb5cd
- cardano/aiken.toml: 0520b42b48f051b1850f8143cdb9d2a7e7532d88ebac3c1b2ae7073332bac23a
- cardano/aiken.lock: 7c69f0a484d3b42862dc0ab0773cf6b3edf72709c921b2ad3648a0753af8cafc
- cardano/aiken-dependency-manifest.json: 2eeba62fdf6e3748cd9999b70b95f0f42d49a76151d24e282a0c1a5688bd0022
- cardano/plutus.json: c4230410d0caac45f2c71d36e45a539c78087697128ce1533306d17e96a48008

The current security workflow hash is baf53503673b70c5185f654f8f694f1feaf98af68ee56e29c83c01ee0cf0593c; its Cardano job invokes the same strict check command. The accepted pinned Aiken binary hash is 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79.

No Aiken command or test was rerun for this correction. The earlier hash 7653cd2a9db99a69424f79164c123ce35d274db75f25f74e0a9f4c4c9b9d36bd in the F04 assessment is stale; the current agent_nft.ak hash is e28ff520d07f73a622a093b362f66411678d535bbb48cf2aecbcd8011204caba.

## Correction and limits

The F04 assessment's statement that G1 remains failed with seven warnings is superseded for the warning-specific strict Aiken check by the accepted cleanup evidence above. This does not close broader Cardano validator acceptance, resolve F04's identity-path decision, establish ledger admission or live-network behavior, or change testnet readiness. The F04 A/B decision remains open.

The aiken test spelling recorded in the cleanup RUN has exit 1 because that CLI subcommand is unsupported; it is not counted as a passing command. The accepted strict aiken check runs the validator tests and supplies the relevant warning-gate result.
