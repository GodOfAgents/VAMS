# SDK signing containment and remaining governed-broker boundary

Date: 2026-10-28. Status: implemented containment; full broker and qualification
remain pending. No keys, signing, services or deployment are authorized by this ADR.

## Defect and correction

The preserved SDK `EOASigner`, `SessionKeySigner`, `OMSSigner` and factory did not
read the central runtime contract. Direct callers could load a key and sign in
staging/testnet/production without action-policy admission. The session route also
signed a fabricated all-zero UserOperation hash. OMS compliance alone does not
authorize a protected action. Existing Sequence wallet containment did not cover
these separate signer adapters.

The SDK adapters now bind an immutable central runtime snapshot before loading a
key, checksumming a wallet or constructing the OMS verifier. All live modes reject.
Before every transaction/message operation, they read current runtime configuration
again and reject missing, malformed, live or changed configuration before encoding,
compliance access, input mutation or inner signing. The factory rejects first too.
There is no optional bypass flag, supplied mode override or live fallback. Explicit
test/local/demo callers retain their existing local signing/simulation behavior.

Registration, x402 payments and trust-aggregator callers that construct these raw
key adapters must use a qualified governed broker before live admission. Changing
their environment to a non-live mode is not an authorized migration.

## Scope and missing production mechanism

This is SDK API containment in a trusted runtime. It is not an isolation proof
against arbitrary code with direct access to a private key, account object, another
signing library, an unrestricted signing service or an independent network route.
No new live signing path is enabled. Full Stage D requires an external credential/
signing capability boundary under the responsible host governance authority,
authenticated current RestrictedTestnetPolicyV1 and ActionContextV1 binding, exact
transaction/message intent, revalidation on resume and at dispatch, and provider/
settlement enforcement. Delegated issuers must not widen policy. The authenticated
host/operator/key manifest remains UNKNOWN; missing values never authorize use.

Completed-effect reconciliation, earned claims and refunds remain separate from
new protected signing. This repair does not alter or implement their protocols.
Sentinel and OMS identity checks cannot stand in for action-policy authorization.
The policy/authority snapshot required for a live broker is distinct from the
local runtime-mode snapshot used here.

## Evidence and invariants

Sixteen source-bound stdlib unittest fixture tests use spy dependencies for every
crypto/identity boundary: no real key parsing, cryptographic signing or network
client is imported or used. The preserved source produced 32 failing subtests
across 16 test methods, zero errors/skips. The candidate passes all16, zero errors/
failures/skips. These are repeated instances of the same16 methods, not32 distinct
regressions plus16 new passes. They observe zero selected protected callbacks on
rejected SDK routes; they are not an independent provider observation.

Raw records, tool/source hashes, commands, outputs and exits are retained outside
the checkout in VAMS-implementation-20261028/SIGNER-BEFORE-01 and
SIGNER-CANDIDATE-01. A canonical-source run is retained after integration.
Python3.14 fixture execution is not the required independent Linux3.12 full gate.
No dependency, workflow or economic restriction is weakened.

INV-3/4 benefit from containing simulated session signing in live modes; the
24-hour and whitelist requirements are unchanged and a live session broker still
requires verification. INV-5 retains the OMS fail-closed requirement; valid identity
does not grant protected signing authority. INV-1/2/6/7/8/9/10 are unchanged.
No new sensitive field is logged or persisted; actual broker custody, privacy and
independent security review remain outstanding. Findings/tracks are not promoted.
