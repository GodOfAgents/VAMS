# VAMS Frontend

**Lifecycle:** Read-only pre-testnet frontend
**Last verified:** 2026-07-12

The Vite application displays VAMS registry, composition, and telemetry data.
The first testnet profile disables wallet transactions, staking rewards, real
fiat, and real yield. It must not be presented as a wallet or payment client.

## Local Use

```bash
npm ci
npm audit --audit-level=high
npm run build
npm run dev
```

Configure the Gateway origin through `src/config.js`. Production-like builds
require an HTTPS origin and are designed to run behind the reviewed Gateway
transport profile. Browser CSP, phishing review, and accessibility evidence
remain public-testnet gates.
