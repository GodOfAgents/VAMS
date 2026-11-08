# V3 authority reservations and lookup-only recovery

Date:2026-10-30. Status:integrated, unactivated;113copied-source local tests pass; authentic/native/live qualification pending.

## Design basis and discrepancy

This follows the owner's StageD/F plan, GCA_ACCEPTANCE, the action/receipt ADR,
SIGNER-CONTAINMENT, ADR-VDSO-001 and the integrated ASYMMETRIC-OBJECT-V3 provider.
The old LOCALV2 authority can return a retained pending admission before checking
the draining scope/current authority; a retained controlled-row probe reproduces
that qualification gap. Local protocols remain local. New V3 authority does not
copy that early return or reinterpret its MAC records as production signatures.

## Authority, operations and bounded accounting

ObjectAuthorityScopeV3 binds the common template, exact sorted unique resource
allowlist (1–64), provider/runtime/target/host/chain/actor/workflow/logical intent,
policy/epoch, integer shared budget/per-action ceiling and fence. The initial
scope is intentionally one bounded intent; it is not universal authority or a
general renewal/migration design. New scope bytes have their own V3 domain and
Python-only frozen vector; existing consensus/action/receipt encodings are unchanged.

Authority scope lifecycle:installing -> active -> draining -> revoked; interrupted
installation may drain for authenticated cancellation. Operation lifecycle:
reserved -> dispatched/indeterminate -> committed or rejected. The accounting
invariant is0<=reserved,spent and reserved<=limit-spent. Reserving adds exact cost;
valid completion moves it from reserved to spent; valid fenced absence removes
it from reserved. No timeout, expiry or acknowledgement alone releases exposure.
The PG schema constrains bounds and result/status agreement; actual native database
enforcement still requires qualification. Budget units do not establish token backing.

Admission/fence signatures persist and commit before returning. Current scope and
policy are checked before returning any pending admission and before dispatch.
Dispatch is claimed once in a committed transaction before a provider invocation.
Unknown commit never triggers a new operation or automatic callback. Historical
reconciliation validates both issuers and exact retained proposal/admission; earned
completion can reconcile under newer policy without granting new dispatch authority.

Cutover must advance the same provider's epoch/token and nondecrease policy;
changed roots require a new policy version. Provider ack must match the retained
signed update. Every pending operation must close as actual completion or fenced
absence before revocation completes. An unacknowledged cutover can be explicitly
advanced to a strictly stronger fresh update; acknowledged history cannot be
overwritten. Unreachable old providers and unresolved zero-cost operations block
completion. No implicit reissue, new grant after revocation, provider/host migration
or old-record adoption exists; versioned grant history and reviewed reauthorization
remain necessary before sustained qualification.

## Connection and research basis

The transactional provider/authority split follows the previously reviewed Apiary
mechanism inference; capability checks follow CaMeL. Those papers do not prove
VAMS durability or alignment. PostgreSQL documents that verify-full checks the CA
and requested hostname, but Unix sockets ignore sslmode and GSS can take precedence.
Psycopg documents keyword arguments overriding DSN values. The connector therefore
forces canonical single TCP host/port, verify-full and gssencmode=disable in live
modes, with a pg_catalog search path; local fixture mode is explicit. Reviewed CA/
server/client/role manifests and actual handshake/negative tests are still required.
Sources:https://www.psycopg.org/docs/module.html and
https://www.postgresql.org/docs/current/libpq-connect.html.

## Invariants, privacy and unqualified boundaries

INV1/2/7/8/9 economic/oracle implementations are unchanged. INV3/4 session bounds
and whitelist, INV5 fail-closed OMS, INV6 root-identity proof requirements and
INV10 bridge proof/payload separation are unchanged. No hardware proof, native
bridge, Deposit/Slash/ExecuteIntent, fiat/yield/reward/minter/governor activation.

CurrentAuthorityPolicyV1 requires an authenticated responsible-host scope/action/
fence source; no such backend or custody manifest is qualified by fixture subclasses.
Direct transport is explicitly trusted-process and has no public route. Add actual
inter-host identity/mTLS, key isolation, privacy approval, PG/native campaigns,
versioned renewal/history, checkpoints and final settlement before broader claims.
Privacy review must include authority template/resource/intent/operation linkage,
admission/fence/result receipts, budgets and database/WAL/backups/retention. No
private key or external credential is embedded or logged by this implementation.


### V3 authority reservations, cutover and reconciliation — 2026-10-30

An unactivated authority/coordinator candidate now connects the V3 provider to
explicit new authorityPG schema, bounded actor/workflow/intent/resource grants,
integer shared-budget reservations and persisted exact signed admissions. Scope
installation and activation are separate; the exact provider fence acknowledgement
is required before admission. Reserved approvals revalidate current policy/scope/
expiry before return or dispatch. A dispatch claim commits once before the provider
call; dispatched/indeterminate/terminal operations cannot silently return new
dispatch authority. Uncertain provider outcomes use lookup, never resend.

Authenticated completed effects retain a separate historical path that moves
reserved budget to spent after policy/authority changes. Timeout/expiry/ack alone
does not refund. Authenticated fenced absence releases the exact reserved cost;
terminal results cannot double-charge/refund. Revocation stops new work, retains
obligations and requires exact provider acknowledgement plus zero unresolved
operations, including zero-cost ones. An interrupted installation may cancel only
through a newer fence. An unacknowledged expired cutover may get a strictly stronger
new update; an acknowledged cutover/history cannot be replaced. No implicit grant
renewal, provider/host migration or legacy record adoption is implemented.

The shared V3 PG connector now forces one explicit TCP endpoint, verify-full TLS
and disabled GSS encryption in live modes, overriding unsafe DSN/environment
settings; missing/encoded-Unix/multihost endpoints reject. Search path is fixed to
pg_catalog, SQL table names remain qualified and authority/provider application
labels differ. Actual server/CA/certificate/role/libpq configuration and TLS
handshakes remain unqualified. These are constructor/connector controls, not a
reviewed runner or new permission to connect to a service.

Candidate113tests pass,0fail/error/skip:53new authority/coordinator tests plus60
existing V3 tests. They use real ECDSA fixture keys and queued driver rows. Composed
tests exercise fresh admission -> committed dispatch claim -> actual provider
algorithm -> authority reconciliation, lost acknowledgement lookup and actual
fence/absence signatures. They do NOT establish native PG constraints/isolation/
concurrency/crashes/durability, independentLinux3.12, authentic policy/custody/
observer, inter-host transport or final settlement. Real PG driver/service and
approved runner remain UNKNOWN/unavailable here. No dependency was acquired.

The current-policy and grant/fence source remains abstract, requiring responsible
host governance/finality/custody. Direct transport is a trusted-process seam;
remote authenticated transport/key isolation/privacy/independent observation,
versioned grant renewal/history, authenticated retrievable checkpoints and final
effect/proof/settlement/earned-claim/refund connection remain unfinished. Budget
bookkeeping is not token custody or proof of funding. No live route is registered.
Existing localV1/V2/VIR/ActionContext/ReceiptV3 bytes and protocol contracts remain.
13findings remain open;0/36tracks verified. Full both-chain A–G scope remains.


### Authority/coordinator integration and copied-source verification — 2026-10-30

AUTHORITY-V3-INTEGRATION completed10guarded paths,6new; prior dirty source/full
manifest retained under history/authority-v3-integration01. The complete integrated
tree was checked before exporting15exact inputs, with the modified shared PG
connector resolving to the tested overlay. Python3.12 syntax parses on Linux;
actual tests run on existing local WindowsPython3.12.14/cryptography50.0.2.
AUTHORITY-V3-CANONICAL-COPY-01:113tests pass,0failure/error/skip.53new authority/
coordinator tests plus60existing V3 tests; counts overlap previous runs. Real
ECDSA uses fixture keys; DB calls use explicit queued rows and parameter spies.
No network/process attempt, actual PG, authentic policy/custody or live service.

The localV2 stale-admission probe reproduces1failure and remains a local-version
characterization. Draft cutover-expiry and missingTLS-override regressions produced
2failures in105tests; TLS socket/GSS-route probes produced3failure instances across
2added methods in109tests. Corrected before integration. Source/tool/commands/raw
outputs and exact candidate attempts103/107/109/113are preserved, not cumulative.
The new authority-scope vector is Python-only, not native cross-language proof.

Source now preserves exact reservations before admission, one committed dispatch
claim before provider invocation, lookup-only indeterminate recovery and separate
authenticated completed-effect/fenced-absence paths. Composed tests connect actual
authority/provider algorithms from a fresh signed reservation through execution,
lost-ack lookup, cutover ack and absence release using controlled driver seams.
They do not prove native SQL constraints/locking/isolation/durability/commit/crash/
multiworker behavior, independently observed effects or real fund conservation.
No token transfer/payment, automatic retry, live route or role activation occurs.

Live DB parameter guards require one TCP host/port, verify-full certificate/
hostname verification, disabled GSS and pg_catalog search path; no Unix/multihost
fallback. Actual PG/libpq build, server/CA/client/role and TLS negative-handshake
qualification remains. The authenticated host grant/action/fence reader is still
abstract; fixture callbacks do not establish authority or atomic chain/PG cutover.
Direct transport is a trusted-process seam, not inter-host identity/mTLS assurance.
Explicit versioned grant renewal/history, provider/host migration, retrievable
authenticated checkpoints and final proof/settlement/earned-claim/refund integration
remain unfinished. Old-provider loss or unresolved obligations still blocks safe
cutover. Prior local protocols and unchanged contracts retain historical evidence.

Privacy review must include authority meta/scopes/operations, actor/workflow/intent/
resource linkage, budgets/admission/fence/result bytes, DB/WAL/backups/retention.
All original A–G/both-chain gates and UNKNOWN inputs remain.13findings stay open,
0/36tracks verified. No Aiken/Slot08/R28, dependency acquisition, provider contact,
external keys/signing/funds/roles/deployment occurred.
