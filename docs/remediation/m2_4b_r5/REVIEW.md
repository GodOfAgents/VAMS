# M2.4b-R5 — Envoy ingress and semantic acceptance contract

Date: 2026-09-24
Scope: M2.4b-R5 only
Verdict: locally implemented and verified; F08 and M2 remain open

## Standards disposition

The R4 qualification rejected Envoy only because its decision rule required
all obsolete line folding to be rejected. RFC 9112 permits a recipient to
replace obsolete folding with spaces before interpretation or reject the
message. R5 replaces the earlier stricter rule with a security-equivalence
rule: normalization is acceptable only when method, target, security-header
meaning, body bytes, request count, and replay identity are unchanged and the
result is exactly one unambiguous semantic request.

This is not a lenient-parser exception. Framing that can change boundaries or
produce another upstream request rejects. The qualified VAMS profile also
rejects duplicate-identical and comma-equivalent Content-Length forms before
upstream rather than normalizing them.

## Qualified ingress

`gateway/envoy.testnet.yaml` makes Envoy 1.39.1 the sole supported public live
Gateway listener. The exact official release binary is pinned by SHA-256
`002c6e1c69ed0fa0ea381887247cadadfaec9481375fa8d8d2b1731eeabf40b8`.
The checked-in configuration and a temporary certificate rendering both pass
the binary's configuration validator.

The configuration requires TLS 1.2–1.3 and verified client certificates,
uses the supported strict built-in HTTP/1 validator, leaves simultaneous
length/transfer framing disabled, normalizes paths, rejects escaped path
separators and underscore headers, limits methods, headers, bodies, and
timeouts, and contains only a `127.0.0.1:8000` Uvicorn upstream.

Client-supplied forwarding, ingress, and certificate-assertion headers are
removed. Envoy regenerates the reviewed forwarding metadata, verified client
certificate fields, and the fixed `envoy-1.39.1-v1` marker. The marker is not
a credential and does not replace M2 authentication.

`gateway/route_security.py` now requires every live HTTP request to have both
a loopback proxy peer and exactly one matching marker before route
classification, authentication, nonce reservation, request-triggered work, or
handler execution.
Non-live test/local/demo requests retain explicit direct access. Live
heartbeat routes additionally retain their certificate fingerprint allowlist.

The Caddy template is retained only as clearly marked historical context. It
is unsupported for M2 or any live Gateway environment and is removed from the
active security workflow and deployment instructions.

## Executable evidence

The pre-existing R4 package under
`/home/GodOfAgents/vams-evidence/m2_4b_r4/` was reused without changing its raw
fixture sources. Its verified Envoy run established canonical semantic
preservation, deterministic trust-header replacement, mandatory mTLS, empty
upstream residual buffers, and rejection of the prior Caddy extra-request
case with zero target, suffix, or unexplained upstream requests on fresh and
reused connections. Its single former failure was the generic obs-fold case,
which produced exactly one normalized request and no second execution; that
behavior satisfies the corrected RFC 9112 contract.

The repository R5 suite exercises the actual pinned Envoy-to-loopback-Uvicorn
to FastAPI boundary. It proves canonical signed mTLS execution once, replay
denial after server restart, rejection of the prior extra-request case with a
subsequent same-nonce canonical success, harmless fold normalization to the
same replay identity, authentication failure when folding changes a security
header, equivalent OWS preservation, duplicate M2-header rejection, trusted
header overwrite, verified mTLS identity delivery, and direct live boundary
denial before downstream execution. Duplicate-identical and comma-equivalent
lengths reject before upstream and do not consume a nonce.

No raw request, body, signature, credential, signer, nonce, certificate,
fingerprint, or parser corpus is persisted as evidence by the new tests.

## Verification

- Envoy artifact: SHA-256 and version verified; checked-in configuration
  validation passed.
- Focused R5 real-ingress suite: 10 passed.
- Envoy contract and mutation suite: 10 passed.
- M2.1–M2.4b combined regression set: 231 passed.
- Gateway, M1, and F17 affected set: 413 passed, 6 subtests passed.
- Workflow-security set: 12 passed.
- The broader remediation unittest set ran 88 tests with two unrelated known
  failures: the history-rewrite test could not locate its required Python
  command, and the existing INV-5 traceability anchor remains unsynchronized.
  Neither was changed or suppressed; INV-5 synchronization is the next slice.
- Compilation, JSON/workflow syntax validation, scoped security searches, and
  `git diff --check`: passed.

No dependency was installed and no download, credential/vendor modification,
deployment, commit, push, or fetch occurred in this slice.

## Invariant and mock-mode impact

| Invariant | Impact |
| --- | --- |
| INV-1 | Unchanged; regional emissions were not touched. |
| INV-2 | Unchanged; insurance yield was not touched. |
| INV-3 | Unchanged; session-key lifetime was not touched. |
| INV-4 | Unchanged; session-key scope was not touched. |
| INV-5 | Runtime behavior unchanged; the known documentation/source traceability mismatch remains open for the next slice. |
| INV-6 | Unchanged; TEE/root-EOA binding was not touched. |
| INV-7 | Unchanged; oracle freshness was not touched. |
| INV-8 | Unchanged; token supply was not touched. |
| INV-9 | Unchanged; reward solvency was not touched. |
| INV-10 | Unchanged; bridge proof and payload hash remain separate. |

Mock-mode selection and M1 containment are unchanged. R5 changes only the
live transport/proxy provenance boundary and does not claim deployment proof.

## Milestone status

F08 and M2 remain `REVALIDATED_OPEN`. INV-5 traceability and frontend `/nodes`
were not modified. The next slice is **INV-5 traceability-control
synchronization**.
