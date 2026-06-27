# VAMS Reality Check Areas

Common drift:

- Test counts in README, audit reports, and status reports.
- Claims that CI does or does not exist.
- Gateway hardening state: default password, rate limiting, CORS, DID auth, mTLS, public bind.
- Frontend status: landing page, real wallet connectivity, CSP/security headers, monolithic `App.jsx`.
- DA maturity: Celestia/Near live-capable vs Avail/EigenDA stubs.
- OMS, Trails, Coinme, TEE, and x402 mock defaults.
- Deployed addresses and chain IDs for Polygon Amoy and Cardano Pre-Prod.
- Research claims for SIRA, HORMA, HIPIF, EvoMem, ProPlay, and CHC.

Rules:

- Prefer "implemented", "partial", "stub", "mock-default", or "planned" over vague status words.
- Link claims to source paths.
- Never use docs as the only source for deployed or tested status.
