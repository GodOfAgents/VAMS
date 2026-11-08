# M2.1 gateway request-auth public-boundary revalidation

Date: 2026-10-03
Status: PASS for the focused M2.1 public-boundary suite; independent review PASS.

## Verification

The focused neuron/tests/test_m2_1_gateway_request_auth.py suite passed 96/96 under pinned Python 3.12.14 / pytest 9.1.1, with network isolation and a read-only checkout. Exact command, source hashes, and output captures are recorded in this directory.

Coverage includes a frozen canonical-signature vector; binding exact request bytes, path, query, audience, signer, nonce, and finite time; malformed and noncanonical input rejection; fixed-clock expiry bounds; fail-closed key and replay errors; one-use atomicity in the process-local store; and prohibition of that process-local store in live modes. All credentials and keys are synthetic fixtures.

## Limits

These are in-process TestClient and process-local replay tests. They do not establish durable cross-process replay, production DID resolution, restart/revocation persistence, live HTTP/TLS, or deployment readiness. No source, credential, vendor, or deployment state changed.
