# Invariant and mock boundary analysis

This is design evidence only; enforcement point source was not changed.
- INV-1 regional emissions, INV-2 accepted insurance cap and INV-7 oracle freshness: untouched.
- INV-3 session validity remains at most 24 hours and rejects at exact expiry. INV-4 whitelist and value restrictions remain required.
- INV-5 institutional P3 remains failclosed on unavailable, stale or mismatched OMS/current authority.
- INV-6 TEE checks the externally authenticated current root EOA, never a session key or proof-derived authority. Cardano/EVM association remains separately gated.
- INV-8 supply cap and INV-9 reward backing: unchanged; INV-9 remains OPEN. No reward economics or mint authority is selected.
- INV-10 bridge proof/payload separation remains unchanged.
No administrator takeover, F05 singleton/committee/genesis authority, implicit V1 migration, or cached-authority bypass is introduced. Existing guardian thresholds, delays, genesis PoP and five-guardian structure remain mandatory.
Synthetic fixtures and structural design checks give no live provider, DA, attestation, ledger-admission or deployment credit. Mock modes remain local-only.
M5 and historical M2 anomaly remain OPEN. Readiness is NOT READY; deployment, Deposit, Slash activation and ExecuteIntent remain disabled.
