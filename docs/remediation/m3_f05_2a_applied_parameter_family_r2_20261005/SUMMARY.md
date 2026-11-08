# F05.2a applied-parameter CBOR candidate family r2

Status: **candidate bytes generated; independent byte review required; tx-sim not run; no case credit**.

This package implements owner-authorized R4.1 choice C and preserves the six original registry IDs and assertions. Every feasible negative is rebound to its own alternate applied Plutus V3 policy. Mint policy ID, compiled program hash, authority NFT policy, and V3 witness are tied together. Each has valid ephemeral funding signatures over the final transaction body, a bound input vector, and conserved ADA/native assets. Private key material is held only in process memory or anonymous memfds and was never serialized.

The synthetic transaction conserves 17,000,000 lovelace as a 10,000,000-lovelace authority output, 6,000,000-lovelace sponsor/change output, and 1,000,000-lovelace fee. There are no collateral inputs or collateral return fields; collateral consumed and returned are explicitly zero. The authority singleton NFT is conserved.

For applied_genesis_parameter, the datum and PoPs bind to the alternate seed; only the corresponding seed input is omitted in the negative transaction. For applied_keys_parameter, the datum retains the original key vector, while PoPs bind to the alternate applied parameter vector; the intended mismatch remains the datum-to-applied-key binding. Duplicate and unsorted parameter, datum, and PoP vectors match; each includes a separately compiled and rebound one-guard mutant control.

The malformed cases stay PENDING with an explicit limitation. Current policy source requires exactly five 32-byte keys in valid_ordered_keys; valid_bootstrap_proofs also pattern-matches exactly five keys and five proofs. A six-key vector cannot have verifier-accepted PoPs under this implementation, and a 31-byte key cannot have a valid Ed25519 public-key proof. Their candidate signatures therefore do not establish an isolated negative. No first-failure evidence at Mint[0] was collected. Do not claim these cases isolate the named malformed-key guard.

No transaction simulator or applied-case suite was run. Positive controls are candidates only; they still require independent byte review and bounded execution. Evidence is synthetic and limited to parameter-bound local compiled-policy/simulator artifacts. No original-policy, ledger-admission, or live-network credit is claimed. Case-status and readiness records were not modified. Deployment and gated activations remain disabled.

| Original case ID | Alternate applied policy ID | Negative tx SHA-256 | Credit |
|---|---|---|---|
| applied_genesis_parameter | 42dabc381328b04583c018473d93020c0204d271300225c87b66564c | c300dfab155376ae746dd41135b043c16d7da95d005eeff3e22de3e3c263f0c6 | PENDING |
| applied_keys_parameter | cb7cea1fcfcf5b2e7cb7e157cd2a4790682107b7f648592f51e9cf3f | 8ee7a9f2c735c64579188b0417db686966b51cc421ef2d1d662e334589d37b58 | PENDING |
| applied_keys_bad_count | 184b8080cfc02f6309bbc51ba060de3850372ff990a77e931bdb2027 | 08e5e21a80b4fb04e580c18a51bd62edd23df4889497fe3a4969b082657d7593 | PENDING |
| applied_keys_bad_length | 0f7791c9e3f40cd59162fcb61f8a37c7a6cd99fcf4175cb3e1579c7b | 6d792dd8de4f29b2ea994506d80eaf53022f912e9054f21a9adea6e8f9e99ab4 | PENDING |
| applied_keys_duplicate | 55a33fda3aa2ba9fd2cf2d9c29e44c7d5632a21720a1349d88c9f7e6 | 9b71091bee2b2a8b901986b7ed3b7d1176fac2e748c2dbc43d31feb85f79f757 | PENDING |
| applied_keys_unsorted | 08906082a748632b3a854fc52a7a63efc3c914f7f0fb3d373240dd47 | 58402e4fabe851df33c828d7076a1fee227c4448c2cf0da7c5fcf9b0a0e30074 | PENDING |

Pinned local toolchain: Python 3.12.14 at /home/GodOfAgents/vams-evidence/toolchains/python/bin/python3.12; Aiken 1.1.21+42babe5, SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79; OpenSSL 3.5.5. No tool/dependency install or fetch was performed.

Each case was generated with its own command (replace CASE_ID with each table ID):

    /home/GodOfAgents/vams-evidence/toolchains/python/bin/python3.12 scripts/remediation/build_f05_2a_applied_parameter_tx_family.py --case-id CASE_ID --aiken /home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken

All six returned exit 0. Each output bundle is explicitly marked candidate-awaiting-independent-byte-review, simulator not run, and no credit.

Focused verification used the following command:

    /home/GodOfAgents/vams-evidence/toolchains/python/bin/python3.12 -m py_compile scripts/remediation/build_f05_2a_applied_parameter_tx_family.py scripts/remediation/test_f05_2a_applied_parameter_tx_family.py
    /home/GodOfAgents/vams-evidence/toolchains/python/bin/python3.12 - <<'PY'
    import runpy
    suite = runpy.run_path("scripts/remediation/test_f05_2a_applied_parameter_tx_family.py")
    for name, test in sorted(suite.items()):
        if name.startswith("test_"):
            test()
            print(name + ": PASS")
    PY

Final verification result will be recorded after the package-root manifest and tests pass. Pytest is unavailable in the pinned Python runtime and was not installed.

Independent review of the amendment and every generated byte/binding is required before any simulator execution.
