# F04 Invariant and Threat Analysis â€” Design Draft

Status: design proposal; no source code or test behavior changed.

## INV-1 through INV-10

| Invariant | Impact | Design constraint |
|---|---|---|
| INV-1 regional emissions <=30% | Not touched | Recovery cannot alter DEC allocation or emission parameters. |
| INV-2 insurance yield <=30% | Not touched | Identity transition cannot alter insurance policy/capital. |
| INV-3 session key <=24h | Not touched | Controller is a root identity key, not a wallet session key; do not extend session validity. |
| INV-4 session contracts whitelisted | Not touched | Recovery grants no session-key scope or whitelist bypass. |
| INV-5 OMS P3 fail-closed | Not touched | Recovery does not bypass OMS identity verification. |
| INV-6 TEE binds root EOA | Not touched | Any downstream TEE identity binding must use the current authorized root with explicit epoch handling; never rebind to an operator/session key. |
| INV-7 stale oracle fallback | Not touched | Recovery does not consume oracle data or bypass freshness checks. |
| INV-8 max supply 1e9 | Not touched | Identity NFT recovery mints/burns nothing; only terminal authorized deregistration burns the exact identity NFT, not VAMS supply. |
| INV-9 pending rewards solvent | Not touched | Recovery preserves economic value and reward accounting; no reward release/claim occurs. |
| INV-10 bridge proof/payload separation | Preserved | Request ID is identity-control authorization context, not a bridge proof or payload hash. Do not reuse, merge, or substitute bridge-proof fields. |

Additional F04 properties: no unilateral administrator takeover; identity-token uniqueness; immutable DID/founding-owner/bootstrap/token lineage; exact value continuity during control changes; quorum separation; delay enforcement; finite request replay domain; freeze does not move value or suppress an independently authorized slash after its separate activation gate passes; recovery does not grant slash/action authority.

## Threat analysis

| Threat | Control | Residual risk / test |
|---|---|---|
| Lost controller | 3-of-5 guardian recovery, new-key PoP, 7-day delay | Liveness depends on three available guardians; test missing guardian and recovery completion. |
| Compromised controller | Immediate quorum freeze on recovery request; old controller cannot veto | If no 3 guardians are available before an attacker acts, existing controller authority remains exposed; test race and terminal path. |
| One or two compromised guardians | Fixed 3-of-5 quorum and distinct signer checks | Custodian loss may halt recovery; test threshold, duplicate signatures and stale keys. |
| Three or more compromised guardians | Quorum can freeze/recover/replace guardians after delay | No protocol can distinguish honest quorum from collusion; fail closed, no hidden admin override. |
| Malicious administrator | No administrator authority in recovery state machine | Review all registry/parameter/admin paths to ensure no alternate owner mutation. |
| Malicious new controller | Proof of possession, immediate freeze, delay, guardian cancellation | PoP proves key control only, not human/organizational identity; test wrong and substituted destination. |
| Replay/race | Domain-separated request ID, current UTxO, nonce/epochs, bounded range, one continuing NFT | Ledger context semantics must be verified; test same UTxO competing spends, replay after every terminal state. |
| Freeze abuse | 3-of-5 immediate freeze; unfreeze 3-of-5 + 48h; freeze has no custody effect and preserves a separately authorized slash transition | Quorum can deny ordinary service; it must not suppress slash enforcement or rewrite pending recovery. Test control-state preservation, pending request ID, and monotonic nonce. |
| Guardian-set capture | 3-of-5 old set, all-new-set PoP, 14-day delay, fixed threshold | Initial guardians are chosen at enrollment; on-chain cannot prove independence. Document separate custodians and audit concentration. |
| Identity loss / silent replacement | Immutable DID/founding owner/bootstrap/token, exact continuation, no V1-to-V2 implicit decode | Migration/genesis compatibility remains a separate gate; test wrong token and V1 datum. |
| Recovery during suspension/slash | Recovery only changes control fields | It cannot unsuspend/reverse slash/activate slash; prove by full datum transition and gate checks. |
| Deregistration as compromise escape | Controller + guardian quorum + 48h delay; payout to current controller | Adds friction to voluntary exit and requires UTXO/time-context tests; no administrator terminal authority. |

## State-machine and identity dependencies

Guardian VKHs remain pairwise distinct and disjoint from founding owner/controller/operator after every transition; proposed controllers/operators remain disjoint from the guardian set. Controller/operator may coincide with each other or the founding-owner anchor. Only one tagged pending action may exist: controller rotation, controller recovery, guardian rotation, unfreeze, or deregistration. Pending state blocks ordinary transitions, but a separately authorized slash may proceed after its independent activation gate passes while preserving every pending field and authority key/epoch; it increments only slash-authorized fields and `state_nonce`. Guardian-quorum cancellation clears pending; expiry clears it without transfer; an emergency quorum freeze clears pending and leaves the identity frozen. Every state continuation increments `state_nonce` once. Scheduling stores base N and writes N+1; execute/cancel/expiry verifies exact pending bytes/request ID and unchanged authority epochs, requires current nonce >=N+1, and writes current nonce+1. Terminal deregistration has no continuation. Controller and guardian epochs change only when their corresponding keys actually change. This is the replay basis and must be consistent in validator and policy contexts.

After controller-epoch change, existing TEE attestations and off-chain capabilities bound to the former root are stale. They require re-attestation or re-enrollment under existing fail-closed identity rules; stable DID/NFT continuity does not imply credential continuity. These cross-layer invalidation tests are a blocking implementation dependency.

## Readiness boundary

No tests were executed for this design. Design review does not establish implementation correctness, ledger admission, live Cardano Pre-Prod evidence, or testnet readiness. Keep readiness NOT READY and deployment, Deposit, Slash activation, and ExecuteIntent disabled pending all documented gates.
