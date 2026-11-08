# Composer simulation boundary — source 40

This repair addresses a representation/containment defect within **F12/F15**.
Both findings remain REVALIDATED_OPEN; no audit track or stage is accepted.
Full A--G, Polygon Amoy and Cardano Pre-Prod remain required and NOT READY.

## Defect and source identity

The original Composer scored/allocated candidates and cached an ACTIVE instance
without executing a provider operation, acquiring a receipt or creating escrow.
ServiceBlockClient returned hardcoded declarations and locally computed hashes;
its optional contract client was unused. Gateway returned `provisioned` and
`deprovisioned` despite having no provider execution/release/payment path. Existing
M2 route authentication was already present and is preserved.

The actual allocator produces AllocationPlan.assignments/allocated_units, while
the price helper read plan.nodes/capacity_units. A real allocator plan could not
reach the quote helper. Float quotes remain estimates and cannot become settlement
calldata. Registry-authoritative integer-unit settlement interfaces are unchanged.

Baseline: checkpoint39, HEAD829ab544571f12efe50ecb5740f129c8acb3e16f,
manifest2cce0ca75bf079e2288f5c7164306b76381833ec59fd0846a8dd27d69f58bbc9,
6,725 paths. COMPOSER-INPUTS-40.json binds71 captured inputs. Historical evidence
retains its exact original source identity; this note does not refresh it.

## Implemented behavior

- Composer and ServiceBlockClient require keyword-only `simulation=True` for
  synthetic operations under an exact current non-live RuntimePolicy. Default
  false is inert/import-safe and cannot be armed later. Supplying a contract
  object does not qualify registry access. Constructors bind only the real process
  environment; there is no caller-supplied environment override. A supplied policy
  must equal that real process policy. Every catalogue/resolution/provisioning
  entrypoint checks current mode and registered mock flags before work; callbacks
  are rechecked before generating an ID or publishing a plan. Composer/client
  selection and policy must agree. Their effective configuration is immutable.
- New SIMULATED and SIMULATION_REMOVED strings extend, rather than reinterpret,
  existing status encodings. Returned records explicitly mark simulation and
  non-authoritative evidence, with no escrow transaction. Real provisioning,
  deprovisioning and active counters stay zero; separate counters track local
  simulations. ACTIVE-only listing is preserved; all-record inspection is added.
- Inspection and removal of simulated local records remain possible after policy
  drift. Removal has no provider release or payment effect. A cached ACTIVE record
  cannot be passed off as successful local deprovisioning. New work still rejects.
- Gateway binds from validated lifespan policy and opts in only for demo. It
  returns simulated/simulation_removed, gates both Service Block and macro routes,
  and labels public blueprints as static planning templates. Unrelated Gateway
  features and existing route security classifications are unchanged. This does
  not implement an authenticated provider endpoint.
- Pure quotes accept actual allocation assignments and allocated units. Legacy
  nodes/capacity inputs remain quote-only compatibility. Quotes retain
  authoritative:false and transactionReady:false; retired escrow parameters and
  untyped transaction builders still reject.

## Verification and review scope

COMPOSER-40-BEFORE:3 original-API regressions,2 failures and1 AttributeError,
demonstrating both false success paths and the real-plan quote defect.
Candidate01:44 checks,1 new-fixture failure (expected EXTERNAL_READONLY where the
unchanged llama declaration is STATELESS). The interrupted Luna test author left
its file before credit exhaustion; original candidate01 bytes/results are retained.
Root corrected this fixture; no product policy changed. Candidate02:44PASS.
Candidate03:46PASS,0 failures/errors/skips, including22 existing declaration/version
checks with explicit non-live opt-in and unchanged assertions. Existing canonical
JSON hashes/versions and local catalogue declaration ordering remain tested.

Independent R1 review found that the initial constructor `environ` argument could
override a real production process with a supplied demo mapping. R1 is rejected
and preserved. COMPOSER-40-REVIEW-DEFECT demonstrated2 failed component subcases
among47 tests. The new public override was removed entirely; tests now control
the actual process environment. Candidate04:47PASS,0 failures/errors/skips. Pure
policy parsing remains a utility; a synthetic supplied RuntimePolicy must still
match the real process configuration. No other module's API was changed. Failed
preparation assertions occurred before their helper wrote any tests; the retained
R1 freeze/review-defect snapshot and all execution records preserve those states.

Direct ServiceBlockManifest hash/serialization helpers remain local declarations,
not provenance; their canonical encoding is preserved. A failed macro may leave
earlier local simulated records available for inspection/removal; no provider
effect, payment or atomic external-provisioning guarantee follows from them.

All executions use approved Linux Python3.14.4 and bwrap, root read-only, private
temporary storage and no network/process creation in unit code. Exact commands,
streams, source/tool hashes and before/after checks are retained in the named JSON
records. Explicit CPU/memory quotas are not established. Tests use synthetic node
inputs, real scoring/allocation/quote code and actual extracted Gateway handler
bodies with request/HTTPException fixtures. They do not import FastAPI or exercise
ASGI routing, middleware, HTTP schemas, full lifespan or startup cleanup. Some
handler response branches use an existing local-record stub; those prove response
shape only. No real credentials, signatures, provider, RPC or payment is used.

Pytest/FastAPI/Starlette/httpx/uvicorn are unavailable in the retained inspected
environments. Existing pytest service/scoring/allocator/settlement and full Gateway
HTTP suites are NOT_RUN here, not waived. No dependencies were installed/acquired.
Independent Linux3.12/frozenCI/native/live qualification remains required. A focused
Gitleaks scan using unchanged rules is a separate check, not the full source/history
gate. Non-author source/result review and canonical integration/fresh checks must
be retained separately; this prepared note alone is not acceptance evidence.

## Invariant and migration impact

INV-1/2/3/4/5/6/7/8/9/10 enforcement sources, thresholds and encoded proof domains
are unchanged. No reward, emission, supply, unbonding, insurance, oracle, OMS,
session-key, root-identity or bridge behavior changes. Estimates create no
liability or reward credit. Registered fees and authentic receipt requirements
are not bypassed. Restricted economics and all current live disablements persist.

This intentional availability/API correction makes formerly implicit local users
opt in. Static declarations, manifest hashes and simulated status never establish
provider admission or settlement entitlement. No receipt/schema migration,
initializer, storage layout, deployed contract or chain state changes. Runtime
policy selection is not governance authentication or bounded Heart completion.

## Remaining full-program work

F15 still needs distinct real provider admission/qualification/execution states,
an authenticated current chain registry reader, a real allowlisted provider
adapter, signed benchmark/model/runtime provenance, action/capability/budget,
cancellation/result/proof binding and real caller-to-settlement tests. F12 still
needs durable provider-cooperative execution, fencing/operation identity, current
authority/policy and authentic receipt reconciliation through crashes/restarts.
These are source implementation gaps as well as qualification dependencies.

Provider/observer/hardware/DCAP/fixed ONNX/EZKL identities, independent Linux3.12/
PostgreSQL runner and human custody/privacy/security assurance remain UNKNOWN
unless reviewed records establish them. This containment does not close those
requirements or substitute fixtures for authentic proofs/live observation. No
R28, Slot08, Aiken, acquisition, signing, deployment or actual canary time is used.
