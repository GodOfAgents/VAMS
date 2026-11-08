# M2.3 local implementation review

Date: 2026-09-23

Scope: migrate the root FastAPI Gateway's protected routes to the M2.1
canonical request envelope and M2.2 durable replay/revocation store, then prove
the integrated boundary over real loopback HTTP. This is local implementation
evidence, not independent M2 closure, deployment approval, or a multi-host
replay guarantee.

## Closed route inventory

`gateway/route_policy.py` contains one explicit immutable ledger for all 32
registered route/method pairs: 8 FastAPI documentation `GET`/`HEAD` pairs, 16
root application pairs, and 8 mounted VDSO pairs. Every entry has exactly one
classification and justification. The reviewed public exceptions are health,
three read-only service/composer catalogs, and the read-only APR estimate.
Administrative/operational reads are `authenticated_read`; every registered
state change is `privileged_state_change`. State-changing methods at a known
path authenticate by default even when the router will later return 405.

Startup compares the live FastAPI route graph, including lazy included routers
and mounts, with the ledger. Missing, duplicate, extra, renamed, or WebSocket
routes fail startup. The application registers no WebSockets and the boundary
denies all WebSocket scopes. Unregistered `HEAD`, unknown paths, encoded or
trailing-slash alternatives, and ambiguous matches do not inherit a policy.
FastAPI documentation aliases are explicitly framework-only; `OPTIONS` is
framework/CORS-only and cannot invoke an application handler.

## Enforcement and ordering

`gateway/route_security.py` is a pure ASGI boundary ahead of the router and
handler. The outer size/framing middleware rejects transfer encoding,
duplicate/malformed/mismatched content length, and oversized bodies. Protected
body methods additionally require one declared-length exact
`application/json` body; streaming, multipart, content encoding, and duplicate
content type reject. The boundary buffers the bounded exact body, runs M2.1
method/raw-path/raw-query/body/audience/signer/nonce/time/algorithm/version
validation, performs key/signature/time checks, and only then atomically
reserves through M2.2. The identical bytes are replayed to FastAPI only after
reservation commits.

Invalid authentication never reserves a nonce. Storage uncertainty returns a
sanitized 503 with no handler execution. A committed nonce remains consumed
when validation inside a handler returns an error. Authentication failures
contain only `gateway_request_denied:<bounded-code>` and do not expose bodies,
signatures, credentials, raw signer identifiers, nonce/revocation state, or
storage details. Audience is explicit and does not trust `Host` or forwarding
headers; raw ASGI path/query bytes are signed.

The former root Basic/legacy DID dependency and process-local legacy replay map
were removed. Mounted VDSO routes now consume the already authenticated root
M2 request and retain their separate intent signer/ownership authorization
afterward. Password, runtime policy, live CORS, heartbeat mTLS, rate limiting,
and deterministic F17 startup/shutdown controls remain in force.

## Verification

Fresh verification used the existing
`/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python` toolchain;
no dependency was installed and no external service was contacted.

- `python -m pytest -q neuron/tests/test_m2_3_gateway_routes.py`:
  40 passed. This includes actual loopback Uvicorn restart and two-process
  shared replay/revocation tests.
- `python -m pytest -q neuron/tests/test_m2_1_gateway_request_auth.py
  neuron/tests/test_m2_2_durable_replay.py
  neuron/tests/test_m2_3_gateway_routes.py
  neuron/tests/test_gateway_auth_hardening.py
  neuron/tests/test_gateway_current.py neuron/tests/test_gateway_root.py
  neuron/tests/test_gateway_runtime_mode.py
  neuron/tests/test_gateway_shutdown.py neuron/tests/test_vdso_gateway.py`:
  216 passed plus 6 subtests.
- The affected M1/runtime/Gateway/F17 set covering
  `test_runtime_mode_contract.py`, `test_runtime_safety.py`, all three M1.2
  suites, M1.3, Gateway runtime/auth/current/root/client/VDSO/shutdown, and the
  economics keeper: 413 passed plus 6 subtests.
- `python -m pytest -q neuron/tests/test_gateway_client_security.py
  neuron/tests/test_secp256k1.py neuron/tests/test_workflows.py
  neuron/tests/test_workflows_isolation.py`: 30 passed.
- `python -m pytest -q scripts/audit/test_deployment_readiness.py
  scripts/audit/test_workflow_security.py scripts/audit/test_audit_program.py
  scripts/security/test_runtime_mode_preflight.py`: 61 passed plus 4
  subtests.
- `python scripts/audit/validate_workflow_security.py`: passed; all 40 workflow
  actions remain commit-pinned.
- Scoped `py_compile`, `python -m json.tool
  docs/remediation/FINDINGS.json`, route-ledger completeness, legacy-auth and
  registered-route/WebSocket searches, and `git diff --check`: passed.

One broader pre-existing traceability check was also attempted and remains
red: `scripts/audit/test_traceability.py` reports that the dirty M1-era
`neuron/clr_router.py` changed the configured INV-5 anchor sentence. The
failure is outside M2.3, predates this slice's files, and was not altered or
suppressed. The scoped workflow/remediation suites above pass.

## Invariants and mock impact

| Invariant | Impact |
| --- | --- |
| INV-1 | Unchanged; no regional emission calculation or contract changed. |
| INV-2 | Unchanged; no insurance capital path changed. |
| INV-3 | Unchanged; no session-key validity changed. |
| INV-4 | Unchanged; no session-key target scope changed. |
| INV-5 | Preserved; OMS fail-closed identity behavior is behind an additional authenticated Gateway boundary. |
| INV-6 | Preserved; TEE root-EOA binding is unchanged. |
| INV-7 | Unchanged; no oracle path changed. |
| INV-8 | Unchanged; no token supply path changed. |
| INV-9 | Unchanged; no reward solvency path changed. |
| INV-10 | Preserved; bridge proof and payload hash remain separate and untouched. |

Mock selection and provider behavior are unchanged. M1 still rejects registered
mock flags in staging, testnet, and production. M2.3 adds no provider fallback
and uses explicit local/test configuration only in tests.

## Disposition

F08 and M2 remain `REVALIDATED_OPEN`. The next and only follow-on slice is
**independent M2-R2 review and F08 closure decision**. No deployment, promotion,
credential/vendor change, commit, push, or fetch is authorized by this record.
