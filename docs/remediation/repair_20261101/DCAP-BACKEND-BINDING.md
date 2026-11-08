# DCAP current backend metadata binding

Date:2026-11-01. Prepared source for review and guarded integration.
StageE/F06 and T10/T11/T15, with existing verification/qualification requirements.

## Established defect and correction

The constructor required quoteVersion3 and the exact collateral router, but
verification rechecked only backend/router codehashes. The declared interface
does not require immutable getter state. A same-code fixture can change its
reported router/version while its returned report and all pinned codehashes stay
the same. DCAP-38-BEFORE reproduces acceptance after drift, including through the
actual ActionDeliveryVerifierV1 and 48hour-governed policy:8tests/7fail/1pass.
This is an adapter binding-policy defect, not an authentic Automata quote attack.

Every verification now also requires current quoteVersion==3 and pccsRouter equal
the constructor-bound address. Revert, absent/short/long/noncanonical getter data
or mismatched values returnFalse. A private staticcall helper copies at most32
bytes and requires exactly32bytes returned; canonical numeric/address words must
match exactly. Oversized getter returndata is not allocated/copied in full. It
uses Solidity-compiled interface selectors and memory-safe scratch memory. No
arbitrary fixed gas allowance is invented; actual backend/dependency gas/resource
qualification remains necessary. General verifier returndata/quote verification
cost and transitive graph mutability are not solved by this helper.

Constructor ABI, evidence/ActionContext/root signature/quote/report layout, SGXv3
hardware scope, measurement/SVN/TCB checks and root/output bindings remain. No
TDX/Nitro/committee/hash-only/RPCBoolean fallback, new trust model or route appears.
Matching metadata/codehashes do not authenticate a backend, its collateral, roots,
upgradable dependencies, current TCB/freshness/revocation or real hardware.

## Evidence scope and migration

DCAP-38-CANDIDATE:15focused native VM testsPASS,0fail/skip;8new binding cases+
7existing action-evidence adapter tests INCLUDED. Same-code address/version drift,
getter reverts, empty/31/64/4096byte replies and noncanonical words reject. Positive
matched-metadata control stays valid. The direct and actual policy/delivery-caller
tests use fabricated DCAP output and public VM root signatures. Actual policy
algorithms/48hour scheduling run with a one-member test fixture, not actual custody.
The unused second proof route explicitly rejects; it is not an EZKL implementation.
The new malformed-response fixture reserves its intentional4096byte return region;
before source remains retained. No assertion was relaxed to obtain the pass.

Pinned offline Forge1.7.1/solc0.8.24, unshared network/read-only worker and separate
temp output/cache; commands/raw streams/tool/source/overlay identities retained.
No authentic quote/certificate/proof/collateral/provider or live operation ran.
Earlier892full Solidity result predates this changed contract and retains its
original scope. Full combined-source tests/sizes must run after integration.

The changed non-upgradeable verifier needs a newly authorized instance and new
exact runtime/source/build identity. No deployed instance is patched/upgraded and
no old codehash may stand in for the changed verifier. No storage/initializer,
signature domain, receipt version, policy version semantics or chain role changed.

## Invariants, privacy and remaining blockers

INV6 root-EOA control remains required; the new check preserves the intended DCAP
dependency binding. INV1-5/7-10 executable controls are unchanged. No economics,
supply/oracle/reward/session/OMS or bridge proof/payload change. Restricted48hours
and all Deposit/Slash activation/ExecuteIntent/fiat/yield/rewards/minter/ordinary
governor/vesting/buyback/delegation disablements remain. No key/provider/role/fund/
deployment/Aiken/Slot08/R28/acquisition action or owner appointment occurred.

No new persistent field/event/log/disclosure is introduced. Quotes/root/control/
action/output linkage and existing calldata still require actual privacy review;
source inspection is not approval. Reviewed qualified Automata hardware/backend/
router/dependency/collateral/TCB manifests, authentic positive/adversarial quotes,
fixed ONNX/EZKL circuit/VK, native bridge and DA/observer receipts remainUNKNOWN.
Current-host authority, native PG/effects/recovery/settlement, full CI/scanners,
custody/privacy/security assurance and both-chain rehearsal/7closed/14public
observation remain required. No finding/track promotion; A--G NOT READY.
