# Governance v2: one authoritative check per transaction (2026-11-09)

Status: **IMPLEMENTED IN SOURCE, REVIEW PENDING.** Owner approved the redesign
on 2026-11-09 after the applied rehearsal (`GOVERNANCE-APPLIED-REHEARSAL.md`)
showed Queue and the eight-voter transactions over the per-transaction memory
limit. F02/F03 stay REVALIDATED_OPEN until non-author review accepts this.

## Problem

Every script in a governance transaction re-ran the complete transition
check. A Queue validated the same transaction five times and needed 22.1M
memory with one voter and 41.7M with eight, against a 14M reference limit.

## Design

Each action has exactly one governing validator that runs the complete
check (`governance_v2_transitions.authoritative`):

| Action | Governing validator | Delegating scripts |
|---|---|---|
| Create | authority spend | proposal policy |
| Vote | governor spend | receipt policy |
| FinalizePassed | governor spend | none |
| FinalizeRejected, CancelProposal | governor spend | proposal and receipt policies |
| Queue | authority spend | governor spend, proposal, receipt and intent policies |
| CancelIntent, ExpireIntent | timelock spend | intent policy |
| ExecuteIntent | none (disabled) | none (all reject) |

A delegating script accepts only if:

1. **The governing input is authentic.**
   - For Create and Queue, the governing input is the single input holding
     the anchor's authority token, and it must sit at the authority script
     address.
   - For the other actions, the script reads the sole reference input. It
     must hold the authority token at the authority address. From that input
     the script takes the configured governor or timelock hash, and the
     governing input must be the sole input at that script address.
2. **It runs under the same request.** `tx.redeemers` must map
   `Spend(governing input)` to exactly the same v2 request
   (`GovernanceRequestV2 { version: 2, action }`) as the delegating script's
   own.
3. **The policy is the right one.** Each policy accepts only its own action
   set. Where it reads the config, it also checks its own ID (receipt,
   proposal or intent policy).

### Why no rule is lost

- **The ledger runs the governing check.** The ledger runs the script that
  locks every spent input, with the redeemer the transaction gives for it, and
  Conway rejects transactions with missing or extra redeemers. So when (1) and
  (2) hold, the governing validator runs `authoritative` on the same
  transaction for the same action.
- **The old policy checks were the same functions.** `policy_mint` used to
  call the same transition functions (`create`, `vote`, `terminal_proposal`,
  `queue`, `terminal_intent`) on the same transaction. The governing
  validator now runs them exactly once.
- **Every governing check pins the exact mint.** Each governing transition
  checks `tx.mint` for exact equality with the expected burns and mints. That
  fixes which policy IDs may mint, which is why the authority-governed
  policies need no separate own-ID check.
- **No delegation cycle.** The authority and timelock spends never delegate.
  The governor delegates only Queue, and only to the authority. Policies
  delegate only to spend validators.
- **The light config read is safe.** It is used only to locate the
  governing script. The governing validator runs the full `read_authority`
  on the same input: sole reference input, size bound, `config_valid`, value
  equality.

## Tests

- **Rerouted campaign calls.** The 47 calls in the campaign that went to
  `policy_mint`, and the 5 calls to the governor-Queue path, now go through
  `policy_tx` and `governor_queue_tx`. These helpers add the governing spend
  redeemer, as the ledger would, then require both the delegating check and
  the governing check. Every previous accept and reject expectation is kept,
  and each rejection is now attributed to the validator that enforces it on
  chain.
- **New direct delegation tests (20).** Each delegating caller is rejected
  in all of these cases:
  - with no governing redeemer;
  - under a different action, or the same action with different fields;
  - with the governing input moved to another script;
  - with a forged authority reference;
  - with the authority token at another address;
  - under the wrong own policy ID;
  - with a policy serving another action.

  ExecuteIntent stays disabled.
- **Applied rehearsal cases.** Four new reject cases on the compiled
  programs:
  - a receipt mint with no governor spend;
  - a proposal mint under an authority Queue redeemer;
  - an intent burn with no timelock spend;
  - a governor Queue with no authority spend.

## Results (WSL D1 runner, Aiken v1.1.21)

- Governance tests (`-m "governance_v2.{..}"`): 744 passed, 0 failed. That
  is the 724 prior cases plus the 20 new delegation tests.
- Full suite (`aiken check --deny --seed 20260711 --max-success 250`):
  2647 checks, 0 errors, 0 warnings.
- Applied rehearsal (`governance-v2-applied-rehearsal-delegation-20261109.json`):
  **PASS**, 46/46 cases as expected, every transaction inside the reference
  limits. One case was re-pointed: the 24-hour Queue rejection is now
  evaluated on the authority spend, because the governor spend delegates
  Queue to it. The Queue transaction as a whole is still rejected.

| Transaction | Memory before | Memory after | Share of 14M |
|---|---|---|---|
| Create | 7.23M | 4.10M | 29% |
| Vote (2nd voter) | 8.93M | 4.90M | 35% |
| Finalize rejected (1 voter) | 10.49M | 4.27M | 31% |
| Queue (1 voter) | 22.08M | 5.47M | 39% |
| Eighth vote | 16.83M | 9.35M | 67% |
| Finalize rejected (8 voters) | 22.42M | 9.15M | 65% |
| Queue (8 voters) | 41.65M | 8.85M | 63% |

The highest CPU share is 36%, on the eighth vote. Applied policy scripts
shrank from 13,184 B to 2,289 B each, and the governor from 11,543 B to
10,373 B. That lowers the reference-script fees.

- Python suite: 3437 passed, 1 skipped, 9 deselected. One failure was
  environmental: `test_history_rewrite_script.py` needs `python` on PATH, and
  the file passes 12/12 with the virtual environment on PATH.

## Invariants

INV-1 to INV-10 have no executable change. No economic parameter, timing rule
(48-hour delay, five-minute window), size bound, signer threshold or disabled
action changed.

## Remaining

- Non-author review.
- Ledger-level validation with real fees, min-UTxO and collateral.
- Live Pre-Prod protocol parameters.
- Ceremony custody.
- Insurance (F01) budget rehearsal.
