# Architect Bootstrap Assurance

**Assurance level:** `architect-bootstrap`
**Review mode:** `architect-bootstrap`
**Public characterization:** Architect-reviewed, not independent or third-party audited
**Last verified:** 2026-07-17

The `bootstrap-public` stage exists for a strict faucet-only public testnet when
external reviewers are unavailable. It does not weaken the later `public`
stage, authorize incentives or real assets, or convert self-review into an
independent audit claim.

The Architect must produce six exact-commit dossiers:

1. Solidity and governance.
2. Aiken and bridge.
3. Economics and centralization.
4. Gateway and SDK.
5. Privacy and data handling.
6. AI-agent safety.

Each dossier must identify the target SHA, reviewer, reviewed invariants, exact
commands, content-bound artifacts, findings and dispositions, explicit
limitations, stop conditions, and zero open blocking findings. Every entry
must contain this unaltered disclosure:

> This assessment is Architect-reviewed and is not an independent or third-party audit.

`architect-reviews.json` binds the six reports and their evidence hashes. The
audit validator rejects a missing domain, duplicate domain, altered disclosure,
independence claim, open blocker, invalid timestamp, unsafe path, or hash
mismatch.

`bootstrap-public` still requires all 36 tracks verified, real deployed
manifests, signed seven-day canary and VDSO shadow reports, no pending
deployment-register fields, and public `VDSO_MODE=off`. The later `public`
stage rejects Architect-bootstrap assurance for independently reviewed tracks
and requires six content-bound independent review reports.
