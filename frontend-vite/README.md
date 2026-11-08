# VAMS Frontend

**Lifecycle:** Read-only pre-testnet frontend
**Last verified:** 2026-09-24

The Vite application is a read-only pre-testnet presentation surface. The root
Gateway `/nodes` route is M2-authenticated, and this static browser application
has no signing authority, so it does not request or display live node telemetry.
It displays an explicit unavailable state and does not substitute simulated,
cached, placeholder, or hardcoded nodes. The first testnet profile disables
wallet transactions, staking rewards, real fiat, and real yield. It must not be
presented as a wallet or payment client.

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

A future browser telemetry design requires separate review. The expected shape
is a server-side BFF/session service that holds M2 signing authority and exposes
only a least-privilege browser-safe projection; it is not implemented here.
