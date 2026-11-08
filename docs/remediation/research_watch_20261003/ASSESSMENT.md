# Research Watch qualification dossier - 2026-10-03

## Authority and source

The attached report is preserved byte-for-byte as input evidence. It labels its 58 items a proposed backlog with implementation status unassessed. Its recommendations and imperative prose were treated as material to evaluate, not governing instructions.

The JSON ledger maps RW-001-RW-058 to reported priority, surface, dependency and source leads. Implementation remains UNASSESSED until current source and test evidence is reviewed.

Three primary arXiv landing pages were checked: S074 (LIMBO), S087 (CATP), S091 (Vosti). Listed title/date match; this is bibliographic checking only. Claims were not reproduced and no dependency or technique was adopted. The other 93 source leads remain unverified, including those without a precise URL.

## Baseline and implementation

Active checkout: /home/GodOfAgents/code/VAMS-testnet; branch testnet/remediation-20260907; HEAD 829ab544571f12efe50ecb5740f129c8acb3e16f. The checkout was already extensively dirty. The stored pre-edit digest hashes Git status text only, not source file contents.

Added neuron/effect_canary.py with typed action binding and PostgreSQL authority, budget, effect, and observation tables separate from DBOS system tables. Reservation and provider commit recheck the exact action, scope, budget, policy revision, epoch and expiry. Added neuron/effect_provider.py with a loopback provider that atomically writes immutable object bytes and its idempotency ledger to SQLite, checks the pinned target/implementation, validates principal-scoped keys, supports lookup, and exposes a separately authenticated observation endpoint.

Eleven standard-library HTTP and coordinator tests pass against this provider. PostgreSQL server/client and pinned Python 3.12 are absent; this runtime has Python 3.14.4 and lacks project Python test dependencies. PostgreSQL SQL, multiworker races, restart recovery, and uncertain-outcome reconciliation were not run. The observer endpoint uses separate credentials but the same provider process, so independent operator observation is not established.

## Open work and readiness

The other 57 roadmap items, all G01-G12 suites, source-claim reproduction, full source/test mapping, invariant matrix, CI/security gates, and independent review remain open. Existing F04/F05 owner decisions, strict Aiken failure, F05 negative/mutation gaps, security/dependency gates, credential-history disposition, missing qualification artifacts, and testnet prerequisites remain blockers.

Readiness remains NOT READY. No chain, deployment, funding, or role changes were performed.


Final local verification output and the final working-tree content digest are recorded in /home/GodOfAgents/vams-evidence/research-watch-20261003/RUN.json; raw test output is unittest-final.log.
