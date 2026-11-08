# Legacy gateway request and direct-handler mode boundary

The exported `neuron.gateway.server.app` previously refused live operation only
in its lifespan and `start_server` entrypoints. An HTTP host can omit lifespan;
embedded callers can invoke its handlers directly. Neither path then consulted
runtime policy before registration, heartbeat changes, task deletion, or limiter
accounting. This is a source-bound bypass of the intended non-live boundary, not
evidence that this legacy service was actually deployed or exploited.

The shared request guard now reparses the effective strict `VAMS_ENV` and every
registered mock flag. It rejects missing, malformed, unknown and live modes and
compares both existing startup and runtime policy bindings against the effective
policy. Middleware calls it before reading request client data or touching the
limiter. All five handlers also call it before state/request access, including
direct calls outside middleware. HTTP refusal is a constant 503 response with no
configuration or exception reflection. Direct calls raise `LiveModeSafetyError`
(including its configuration subtype). No override, stale-policy fallback or
new live authentication route is provided.

Strict test/local/demo use retains the existing registration, heartbeat, task
and sanitized home behavior. The home classification is derived from the same
validated effective policy even when a non-live embedded host omitted lifespan.
The legacy heartbeat signature remains a stub in this non-live service. The
separate root `gateway.server` M2 application and its consent/current-native
reader gaps are unchanged. This repair does not implement node enrollment,
replay protection, M2, mTLS, persistence, production rate limiting or privacy
acceptance for the legacy application.

## Source and evidence

Baseline: checkpoint74 manifest
`55caaf971d05a2c64bf39ca55835e17aaf281cf963e6e55a5225408fa32af784`.
The original server digest is
`ea9e4e2388e1bbf2ff2ac62e8afbf66a97f69821da0b1f47c90feb8584704f66`.
The prepared source and shared runtime copies were checked against that manifest
before use. The initial insurance audit was withdrawn after discovering it used
an older Windows tree; the canonical insurance guard was already repaired. Its
original review and explicit correction remain retained, with no duplicate fix.

The same 11 unittest methods use AST-extracted complete actual functions, the
actual strict runtime module, and local request/response/limiter/state fixtures.
Before repair: 34 failed assertions (including subtests), 0 errors/skips. After:
11 methods pass, 0 failures/errors/skips. Both runs report zero protected I/O
attempts. They test live/invalid/malformed/mock/drift refusal, unchanged denied
state/logs/limiter, early poison-input refusal, direct calls, local behavior and
same-process mode changes. Tests strip framework registration decorators and
avoid package initialization; they are not FastAPI/ASGI execution evidence.

Separate `test_legacy_gateway_asgi_boundary.py` provides five real-framework
methods over the exported app with HTTP scopes and no lifespan scope, including
all routes, local classification and direct-handler poison arguments. These are
NOT RUN in this dependency-limited lane. Required full framework/pytest gates
remain blocking. No listener, HTTP client or external provider is needed by those
tests; authentic ingress and operational qualification remain additional gates.

Retained runs are `LEGACY-REQUEST-75-LINUX-BEFORE-01` and
`LEGACY-REQUEST-75-LINUX-AFTER-01` under the existing evidence workspace. Exact
commands, tool/source/worker/runner hashes, fixed minimal environment, raw streams,
terminal exits and unchanged-input checks are bound in their JSON receipts.
Approved existing Linux Python3.14/bwrap run read-only with private network/PID
namespaces and private temporary storage; this is not independent Linux3.12 or
full frozen-CI parity. A Windows launch stopped before target submission because
its interpreter hash changed. The separate tool-identity observation preserves
that limitation; historical Python evidence is not rebound to the new executable.

## Traceability and remaining acceptance

F09/M1 and T07/T31/T35: closes a local runtime-containment defect only. F08 node
consent/current-authority and M2/ingress work remains independent. INV-1 through
INV-10 enforcement and all restricted economic/activation disablements are
unchanged; no new identity, proof, token or governance authority is created.
Non-author source/evidence review, focused scan, canonical integration and fresh
combined checks are separate records; this candidate note does not establish them.

Full A--G for Polygon Amoy AND Cardano Pre-Prod remains 13 open findings,
0 of 36 tracks verified, NOT READY. Approved runner/PostgreSQL/provider/observer/
hardware/model/custody/privacy/human-review inputs stay UNKNOWN where not reviewed.
Both-chain rehearsals, independent assurance, seven actual closed-canary days and
the subsequent 14 public observation days remain due. No R28/Slot08/Aiken,
installation/acquisition, provider contact, real signing/funding/roles or deployment
is authorized or performed by this slice.
