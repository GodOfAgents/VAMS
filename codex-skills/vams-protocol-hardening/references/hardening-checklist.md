# VAMS Hardening Checklist

Gateway:

- Require environment-injected admin secret; reject retired default passwords.
- Add DID signature verification for admin/state-changing routes.
- Add mTLS or equivalent client auth for telemetry endpoints.
- Use strict Pydantic models for request bodies.
- Bind Uvicorn to loopback behind Caddy/TLS for live deployments.
- Configure production CORS explicitly.
- Avoid logging secrets, bearer tokens, raw private identifiers, and full signatures.

Runtime:

- Reject mock mode in staging/testnet/production.
- Keep OMS identity fail-closed.
- Keep bridge proof and payload hash separate.
- Keep session keys short-lived, scoped, value-limited, and whitelisted.

Contracts:

- Preserve caps, solvency checks, staleness guards, pausable hooks, and timelocks.
- Require Foundry tests for every economic or access-control change.
- Do not add deploy scripts that embed private keys.

CI and supply chain:

- Run Forge, Aiken, pytest, Bandit, pip-audit, npm audit, Gitleaks, and SBOM gates.
- Treat CI existence as insufficient unless the relevant job actually covers the change.
