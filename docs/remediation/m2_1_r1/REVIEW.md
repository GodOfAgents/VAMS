# M2.1 local implementation review

Date: 2026-09-23

Scope: canonical versioned gateway request-authentication envelope and its
minimal replay-store interface only. This is local implementation evidence,
not independent M2 closure, durable replay evidence, full route migration, or
deployment approval.

## Preserved trust model

- Authorization identity remains the single exact `GATEWAY_ADMIN_DID`
  configured by the root gateway.
- `did:key:` continues to contain the existing raw 64-byte secp256k1 public
  key. Signatures remain raw 64-byte low-S ECDSA with SHA-256 through
  `neuron/secp256k1.py`.
- The new key-resolver interface models available, unknown, revoked, and
  unavailable results but does not invent a registry or revocation authority.
- The VDSO canary authentication protocol remains separate and is not treated
  as repair evidence for legacy gateway authorization.

## Canonical contract

Only version `1` and algorithm `secp256k1-ecdsa-sha256` are accepted. The
message begins with `VAMS:GATEWAY:REQUEST-AUTH:v1` plus a NUL byte, followed by
an exact field count and ordered one-byte tags with unsigned four-byte lengths.
It binds version, algorithm, uppercase method, raw canonical path, raw canonical
query, exact-body SHA-256, configured audience, signer DID, a nonzero 16-byte
nonce, and unsigned 64-bit issue/expiry values.

Paths must be origin-form, single-slash, ASCII wire representations whose
percent escapes use uppercase hex and decode as UTF-8. Encoded separators,
encoded unreserved characters, dot traversal, repeated slashes, fragments,
query delimiters, backslashes, controls, invalid UTF-8, and absolute-form
confusion are rejected; decoded Unicode must already be NFC. Queries preserve exact pair order, duplicate names,
`name` versus `name=`, empty values, reserved-character escapes, and Unicode
UTF-8 escapes. Empty pairs/names, semicolon separators, fragments, lowercase or
invalid escapes, and escaped unreserved characters are rejected; no sorting or
parse/re-serialization occurs.

The auth header schema is closed. Duplicate required headers, unknown
`X-VAMS-Auth-*` extensions, and simultaneous legacy DID/signature/timestamp
headers reject rather than creating negotiation or compatibility ambiguity.

Audience is an injected/configured lowercase service/deployment identifier and
is never derived from `Host`. Nonces are exact lowercase 32-hex-character,
nonzero values. Timestamps are canonical decimal headers parsed to real Python
integers; booleans, floats, leading zeroes, negative values, overflow, inverted
windows, expiry at/before now, future issue times beyond 300 seconds, and
lifetimes over 300 seconds reject. The 300-second bounds reuse the root
gateway's existing finite authentication window rather than adding a permissive
default.

## Replay and integration boundary

The interface reserves and consumes an audience/signer-digest/nonce namespace
atomically through one call with expiry and closed outcomes: accepted,
duplicate, revoked, unavailable, and storage failure. The bounded lock-protected
implementation is a deterministic process-local test double only. It reparses
the effective runtime environment, rejects injected-policy rebinding, and
cannot construct in staging, testnet, or production.

`gateway_auth_dependency()` is the stable FastAPI seam exercised through real
ASGI requests. It reads `Request.body()` exactly once through Starlette's cache,
signs its exact digest, and downstream observes identical bytes. No current
production route uses this seam yet because live route migration without M2.2's
durable replay store would be unsafe.

## Verification

- Focused M2.1 canonicalization/signature/ASGI/malformed-input/size suite:
  96 passed.
- Integrated M2.1, existing gateway authentication/lifecycle, M1 runtime,
  M1.2a–M1.3, and F17 regression set: 480 passed with one dependency
  deprecation warning.
- Complete relevant root gateway-client/server and secp256k1 subset: 146
  passed.
- Python compilation, remediation JSON parsing, scoped source searches, and
  `git diff --check`: passed. The searches show the deliberately untouched
  legacy `VAMS_ADMIN_AUTH` route dependency and separate VDSO canary scheme;
  neither is an alternate path into the new dependency.

The fixed expected canonical bytes and fixed valid signature are checked-in
literals generated once from a scalar-one public test key. Tests do not ask the
production canonicalizer to construct the expected bytes.

## Open work and impact

F08 remains `REVALIDATED_OPEN`. M2.2 must supply durable shared atomic storage,
restart persistence, parallel-worker correctness, expiry handling, and actual
revocation enforcement. M2.3 must migrate every protected/effectful route to
one policy and prove real HTTP enforcement. No unsigned fallback, algorithm
negotiation, or live process-local replay path was added.

INV-1–INV-10 are unchanged. The slice does not alter mocks; its only
environment-sensitive implementation is more restrictive and preserves M1.
