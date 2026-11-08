# F04 registry-side mint rejection

The agent_registry mint dispatcher now rejects MintIdentity unconditionally. The legacy BurnIdentity branch and registry spend policy-ID guard remain unchanged. The private mint-output helper that became unreachable was removed to satisfy the strict warning gate.

The new tests use valid-shaped synthetic transaction contexts to verify mint rejection and retained legacy burn acceptance. They do not establish standalone agent_nft mint, registration success, paired ledger admission, chain execution, or live-network evidence. INV-1 through INV-10 are unaffected by the dispatch change and remain subject to separate gates.

Readiness remains NOT READY. The canonical policy anchor and registration binding remain unresolved. F05 is 45/55 negative cases and 18/21 mutations. T06/history, M0.4/Gitleaks, security/dependency/invariant checks, and Cardano Pre-Prod / Polygon Amoy prerequisites remain open. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
