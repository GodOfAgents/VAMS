# Disabled yield signing boundary — source 42

The selected restricted profile keeps real yield disabled. Both old YieldManager
write entrypoints nevertheless built a transaction and called the supplied signer
in every environment, then returned a constant fabricated hash. Neither method
broadcast nor confirmed a transaction. That implementation could release a real
signature while presenting a mock success. The only captured callers are two old
unit tests which expected these fabricated hashes; no qualified recovery caller
was established by the current first-party source audit.

## Repair

deploy_capital and withdraw_capital now unconditionally raise LiveModeSafetyError
before fund/signer/address/amount access, transaction construction, logging the
request or signing. Their public call signatures remain. No environment override,
new flag, simulation hash or automatic fallback is introduced. Restricted testnet
does not acquire a yield write route through direct SDK access.

get_deployed_balance remains a pass-through read using the supplied contract. It
does not authenticate custody or qualify that contract/deployment. Read failures
propagate rather than manufacturing a balance. This slice changes no Solidity
insurance design, governance role, timelock or on-chain withdrawal path. It does
not implement real withdrawal/recovery. If an actual deployed position needs
recovery, its owner-authorized chain-bound design and execution remain separate
required work; this unsupported SDK must not fabricate that recovery.

## Source/evidence/review

Baseline checkpoint41: HEAD829ab544571f12efe50ecb5740f129c8acb3e16f,
manifest b0163509f405fb8d997e5c067dcc726e430f166ec7bad058fd5f205c70533390,
6,731paths. RUNTIME-INPUTS-42 binds130 source/doc inputs; YIELD-INPUTS-42 binds10
focused inputs. The independent runtime42 audit records this as READY_SOURCE_REPAIR
and found no higher-priority uncontained defect in its assigned SDK/proof/payment
slice. That bounded audit is not proof of full A--G completeness.

YIELD-42-BEFORE:2actual-method regressions failed against original code. The exact
original test bytes are retained by their recorded hash under history/yield42-before.
Candidate01:6PASS/0fail/error/skip, actual YieldManager/runtime-safety modules with
in-memory/poison fund and signer doubles;0network/process attempts. New tests cover
both write APIs, test/local/demo/staging/testnet/production/missing/unknown mode,
malformed/extreme/poison arguments, no transaction building/signing/request logging,
and unchanged successful/failing read-only behavior. The old2pytest fake-hash tests
are corrected to require refusal and zero collaborator calls; the full fiat/pytest
module is NOT_RUN in this dependency-limited lane. Its other3fiat tests are unchanged.

Approved LinuxPython3.14.4/bwrap, network unshared/rootread-only/privateTMP/45s
timeout. Exact commands, streams, tool/source/loaded-module hashes and complete
source before/after checks retained. Explicit CPU/memory quotas are not proven.
This is controlled local effect observation, not genuine signing/RPC/funding,
independent Linux3.12, native integration, human custody or live recovery evidence.
Non-author implementation review, focused scan, guarded integration and fresh
canonical results are separate records; this prepared note is not their acceptance.

## Traceability and limits

F01/T18/INV-2: enforces the selected zero-yield SDK boundary without changing the
30% on-chain maximum or replacing the established insurance custody repair.
No other INV1--10 enforcement source/limit/encoding changes; no liability, reward,
allowance, capital transfer, proof or authority is created. Full F01 custody and
actual applied controls/independent assurance remain open. Both-chain A--G and all
13open/0of36verified statuses remain unchanged. No realyield is enabled.

No R28/Slot08/Aiken/install/download/provider contact/credential/signing/funding/
deployment/live roles or human appointments. Unknown reviewed runner/provider/
observer/hardware/fixedworkload/custody/privacy inputs stay consolidated; no false
hash, fixture pass or source review supplies those missing acceptance inputs.
