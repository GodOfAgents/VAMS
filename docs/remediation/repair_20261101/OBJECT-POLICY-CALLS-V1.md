# Typed object-policy call boundary

Date:2026-11-01. Prepared source for non-author review and guarded integration.
This is StageD/F interoperability engineering, not current-host qualification.

## Source gap and design

Python had action/grant/effect/scope codecs, but no producer for the separate
Solidity authorizesObjectV1/authorizesObjectScopeV1 call ABI. The public presence
regression failed once; the exact before test is archived. The grant consent
domain, ActionContextV1, ObjectAuthorityScopeV3, ReceiptV3 and storage versions
are unchanged. An initial independent review found no equivalent existing API.

ObjectPolicyCallsV1 takes exact ObjectGrantDomainV1 and ObjectProviderIdentityV3
values. It checks domain/runtime bindings and takes both distinct expected issuer
IDs from configured public verifiers. A witness cannot enroll its own issuers.
It encodes only the two explicit methods, using standard nested ABI offsets,
bounded arrays/integers and canonical65-byte low-S consent shape. Structural
signature checks do not verify actor consent. Matching types/bytes, proof shape
and configured identity do not authenticate chain state, custody or authority.

The selectors c76d3f1f/c6a79e78 came from pinned solc0.8.24 methodIdentifiers,
then actual Solidity abi.encodeCall checks. NIST SHA3 is never substituted for
Keccak. The returned value is an unsigned read-call description, not an approval.
No RPC/Boolean consumer, CurrentActionPolicyV1 implementation, key loading,
signing, provider dispatch, credential release, settlement or live route is added.
Existing constructors continue rejecting unqualified live effect operation.

## Verification and evidence limits

OBJECT-POLICY-36-CODEC-CANDIDATE-03:26WindowsPython3.12local tests pass, zero
failures/errors/skips or observed network/process events.14new producer tests
include the presence regression;12existing grant codec tests are INCLUDED.
They use public verification keys and intentionally invalid actor consent. This
does not demonstrate authentic signing. Earlier failed unittest package lookup
is preserved with its original worker; no dependency was installed/substituted.

OBJECT-POLICY-36-NATIVE-CANDIDATE-03:focused offline Forge/solc VM tests plus15
exact cross-language comparisons:6complete call byte strings and9action/scope/
grant digests. Minimum/nested/64resource-32sibling/maxinteger cases include65-byte
consent padding.3new ABI cases and29existing real-algorithm grant/policy VM tests
overlap prior counts. The existing29use synthetic VM consent/governance, not actual
custody. Dummy ABI-vector consent is explicitly rejected. First fixture compilation
failed stack depth; its source/output are archived. Splitting test helpers fixed
it without compiler-setting or gate changes. The next32native tests passed but
cross-language comparisons exposed a mistyped public fixture point in Solidity;
its source/output are archived. Correcting that fixture makes all15comparisons
pass; no Python vector or on-chain contract logic changed to match it.

The native runner uses read-only canonical copies, a private temporary tree and
unshared network; explicitCPU/memory quotas are not established. It never invokes
scripts/broadcast/FFI/Aiken. Candidate results require fresh combined-source checks
after integration. The historical889Solidity/194runtime/174session results keep
their exact source identities; they are not rerun or added to these counts.

## Traceability, privacy and remaining acceptance

Existing backlog links remain F11/F12/F14/F15 and T04/T07/T15/T25/T27/T29/T33,
with source-only interoperability evidence for the established StageD/F contract.
No official finding or track status is promoted. This encoder does not close R3's
authenticated Service Block manifest/capability -> actual effect/receipt gap.

AllINV1-10 executable controls remain unchanged: no economics/oracle/supply/reward,
session/whitelist/OMS/root-TEE or bridge/proof/payload change. Restricted economics,
48hgovernance and disabled Deposit/Slash activation/ExecuteIntent/fiat/yield/rewards/
minter/ordinary governor/vesting/buyback/delegation remain. No schema migration,
contract storage change, deployed upgrade or authorization transfer is implied.

The new module does not persist/transmit/log call data. Ordinary repr omits consent
and full calldata; this is not debugger/traceback/memory/WAL/backup privacy proof.
Calls still contain existing actor/provider/runtime/workflow/intent/resource,
grant/consent/issuer and budget linkage. Any future RPC or observer transmission
needs actual owner/recipient/retention/operator/privacy acceptance. Prior effect
privacy inventory does not automatically cover this new module or all SDK fields.

Native current/finalized host state, exact deployed code/configuration/governance,
issuer custody/enrollment, authenticated root/version/epoch/revocation, isolated
credentials, real provider/PG/fencing/checkpoint/reconciliation/settlement and
independent zero-effect observation remain. No raw RPC Boolean, fixture callback,
score or unsigned bytes may supply that authority. Cardano-native domains remain
separate; no committee replaces native bridge verification. Reviewed runner,
provider/DCAP/EZKL/observer/custody/privacy/security identifiers stay UNKNOWN.
Both chains, full frozen CI/scanners, independent assurance and actual7closed/
14public observation days remain. Full A-G readiness remains NOT READY.
