# M2.2 local implementation review

Date: 2026-09-23

Scope: durable atomic replay reservation, signer revocation, expiry, restart,
and parallel-worker correctness on one deployment host. This is local
implementation evidence, not independent M2 review, protected-route migration,
multi-host coordination, deployment approval, or F08 closure.

## Backend and deployment boundary

`gateway/replay_store.py` adds a typed `DurableReplayStore` contract and a
standard-library SQLite implementation. Live gateway startup requires an exact
absolute `GATEWAY_AUTH_REPLAY_DB` path ending in `.sqlite3`; no live
process-local fallback exists. The parent must already exist, be owned by the
effective user, and not be group/world writable. Symlink components, a symlink
or hard-linked database, ambiguous relative/file-URI paths, unsafe ownership or
mode, missing/read-only/corrupt files, incompatible schemas, and bounded lock
timeouts fail closed with sanitized errors. The database is created mode 0600,
uses WAL with `synchronous=FULL`, persists schema/backend identity, and opens
subsequently with `mode=rw` so a missing file cannot be silently recreated.

The guarantee is deliberately host-local: separate gateway processes are
coordinated only when they share this exact local filesystem database on one
deployment host. It is not a distributed or network-filesystem guarantee.
Configuration, path, policy, clock, and deterministic path-bound backend
identity are
immutable after construction.

## Atomicity, revocation, and retention

Every reservation runs under one `BEGIN IMMEDIATE` transaction. Its primary
key is the complete v1 namespace: authentication version, audience, SHA-256
signer/key identity digest, and nonce. Canonicalization, audience, time,
signer/key, and signature validation remain ahead of the reservation call. The
database stores only the namespace digests/bytes and timestamps; it never
stores request bodies, signatures, credentials, headers, or raw signer values.

The same write-serialization boundary checks durable signer revocation before
insert and immediately before commit. If a revocation transaction commits
first, reservation observes it and rejects; if reservation already owns the
write transaction, a later revocation cannot commit first. Revocation is
idempotent, retains the earliest effective time, survives restarts, and never
deletes replay reservations. A storage error or expiry at either transaction
boundary rolls back and rejects.

Reservations are retained through signed expiry plus the 300-second M2.1 skew
bound and a 60-second safety margin. Cleanup deletes at most 256 expired rows
per transaction. A durable high-watermark permits at most the documented
300-second rollback tolerance and prevents cleanup followed by a larger clock
rollback from reopening a request window. Expiry is checked independently of
cleanup.

## Gateway, lifecycle, and open boundary

The root gateway initializes the replay backend after runtime/live
prerequisites and before DA-audit construction, keeper startup, or cleanup-task
creation. Failed initialization leaves no owned background activity. Existing
F17 deterministic cleanup/keeper ownership remains intact. Test/local/demo may
retain the bounded process-local double; staging/testnet/production require the
durable store.

M2.2 does not attach the M2.1 dependency to legacy protected routes. F08 and M2
remain `REVALIDATED_OPEN`: M2.3 must migrate every protected/effectful route,
prove real HTTP replay/authentication enforcement, and receive independent
review. The existing `GATEWAY_ADMIN_DID` raw secp256k1/ECDSA-SHA256 trust model
is unchanged.

## Verification

- Focused real-SQLite durability, restart, multiprocessing races, revocation,
  expiry/cleanup/rollback, unsafe storage, sanitization, and lifespan suite:
  29 passed.
- Combined M2.1 and M2.2 envelope/replay suite: 125 passed.
- Affected gateway, F17 lifecycle, runtime-policy, and M1 containment suite:
  361 passed plus 6 subtests.
- Relevant root gateway client, secp256k1, workflow, and remediation/workflow
  suite: 44 passed plus 4 subtests.
- Python compilation, remediation JSON parsing, workflow/static validation,
  scoped security searches, and `git diff --check`: passed.

All multiprocessing assertions use deterministic coordination primitives and
bounded joins; no sleep-based race assertion is used. No dependency was
installed and no provider, network, deployment, credential, vendor, commit,
push, or fetch operation occurred.

## Invariants and mock impact

INV-1 through INV-10 are unchanged: this slice changes no economics, session
keys, OMS, TEE, oracle, supply, rewards, or bridge proof/payload handling. Mock
selection is unchanged; M1 live-mode containment is strengthened only by
requiring durable replay storage at the live gateway startup boundary.

Next slice: **M2.3 — protected route migration and real HTTP authentication
enforcement**.
