# Frontend `/nodes` disposition review

Date: 2026-09-24  
Scope: frontend `/nodes` disposition only  
Verdict: locally verified; F08 and M2 remain open

## Reproduced mismatch

Before this slice, `frontend-vite/src/App.jsx` polled the public `/health` route
and then called protected `GET /nodes` without the M2 headers. The real route
ledger classified `/nodes` as `authenticated_read`; the focused real-app test
confirmed an unsigned request safely returned `401` with `missing_version`.
The browser catch path then fabricated three node identities and operational,
economic, identity, TEE, skill, and cognitive fields. That made an expected
authorization denial look like usable telemetry.

Reproduction:

```text
VAMS_ENV=test /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python \
  -m pytest -q \
  neuron/tests/test_m2_3_gateway_routes.py::test_public_routes_remain_reachable_and_sensitive_read_requires_m2
1 passed in 2.28s
```

## Disposition

- `/nodes` remains an M2-authenticated read in `gateway/route_policy.py`.
- The static SPA sends no `/nodes` request and has no M2 signing authority.
- All frontend contexts render: `Live node telemetry requires an authenticated
  server-side session.`
- No `401`, network error, malformed response, absent configuration, local/demo
  label, or other outcome can activate simulated or live-looking telemetry.
- No browser credential, reusable signature, private key, DID signer, bearer
  token, or secret-bearing `VITE_*` variable was added.
- A separately reviewed server-side BFF/session service may eventually hold M2
  authority and return a least-privilege projection. It is not implemented.

## Changed files

- `.gitignore` (vendors the two scoped frontend source inputs)
- `frontend-vite/src/App.jsx`
- `frontend-vite/src/nodeTelemetry.js`
- `frontend-vite/src/nodeTelemetry.test.js`
- `frontend-vite/package.json`
- `frontend-vite/README.md`
- `docs/API_REFERENCE.md`
- `docs/CHANGELOG.md`
- `docs/remediation/FINDINGS.json`
- `docs/remediation/STATUS.md`
- `docs/remediation/SESSION_HANDOFF.md`
- this review

No Gateway runtime, route policy, authentication, replay, ingress, vendor, or
credential file changed.

## Verification

The canonical WSL checkout had no local JS or Python dependency environment.
No dependency was installed. Frontend source was copied to a unique temporary
directory, linked only there to the already-installed dependency cache, tested
and built, then the verified temporary directory was removed.

```text
npm test
4 passed, 0 failed

npm run build
vite v7.3.6; 1712 modules transformed; build passed

eslint --no-warn-ignored src/App.jsx src/nodeTelemetry.js src/nodeTelemetry.test.js
passed

built-bundle scan: 9 files, 7 forbidden route/signing-secret patterns
passed; zero matches
```

```text
VAMS_ENV=test /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python \
  -m pytest -q \
  neuron/tests/test_m2_1_gateway_request_auth.py \
  neuron/tests/test_m2_2_durable_replay.py \
  neuron/tests/test_m2_3_gateway_routes.py \
  neuron/tests/test_m2_4a_replay_schema_integrity.py \
  neuron/tests/test_m2_4b_envoy_ingress.py \
  neuron/tests/test_gateway_runtime_mode.py \
  neuron/tests/test_gateway_shutdown.py \
  neuron/tests/test_m1_3_entrypoint_containment.py
290 passed in 29.12s
```

```text
python3 scripts/security/mock_mode_promotion_scan.py
Mock-mode promotion scan passed.

find docs/remediation -name '*.json' -type f -print0 | \
  xargs -0 -n1 python3 -m json.tool >/dev/null
7 JSON files passed.

git diff --check
passed
```

## Invariant and mock-mode impact

INV-1 through INV-10 enforcement code is untouched. In particular, this slice
does not alter OMS fail-closed behavior (INV-5), TEE root binding (INV-6), or
bridge-proof/payload-hash separation (INV-10). It removes a presentation-layer
mock promotion risk; no runtime mode, provider mock, or local/demo fixture is
added. Gateway M2 authentication, durable replay/revocation, Envoy trust
boundary, M1 containment, and F17 lifecycle ownership remain unchanged.

## Remaining blockers

This is local implementation evidence, not M2 closure. F08 and M2 remain
`REVALIDATED_OPEN` until the independent M2 review and F08 closure decision.
Testnet readiness, deployment, and all unrelated remediation remain outside
this slice.
