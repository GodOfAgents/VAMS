# Cardano Pre-Prod restricted-testnet rehearsal

**Network:** Cardano Pre-Prod, network magic `1`
**Posture:** local and offline only. `cardano-cli` 11.2.3.0 is installed for
offline use (owner decision 11). Live Pre-Prod queries, signing, funding and
submission each need the owner's specific authorization.
**Last verified:** 2026-11-13 against `cardano/plutus.json`,
`cardano/validators/governance_v2.ak` and
`docs/audit/schemas/deployment-manifest.schema.json` (schema 2.0.0)

Ported from PR #4 (`docs/runbooks/CARDANO_PREPROD_REHEARSAL.md`, July 2026)
and rewritten. The July draft deployed `governor.ak`, `timelock.ak`, the
`fund_nft`/`proposal_nft` policies and used `cardano_preprod_apply.py` with
manifest schema v4. Governance has since moved to `governance_v2`, the
insurance validator was rewritten, and none of those scripts exist in the
canonical tree. Only the approach (apply parameters, derive hashes twice,
compare independently) is kept. Readiness is NOT READY.

## Deployment set

`deployment-manifest.schema.json` requires exactly eight Cardano artifacts:

| Artifact | Blueprint entry | Parameters |
|---|---|---|
| `governance_authority_v2` | `governance_v2.governance_authority_v2` (mint + spend) | `bootstrap` |
| `governor_v2` | `governance_v2.governor_v2` | `anchor` |
| `timelock_v2` | `governance_v2.timelock_v2` | `anchor` |
| `proposal_policy_v2` | `governance_v2.proposal_policy_v2` | `anchor` |
| `receipt_policy_v2` | `governance_v2.receipt_policy_v2` | `anchor` |
| `intent_policy_v2` | `governance_v2.intent_policy_v2` | `anchor` |
| `insurance_fund.ak` | `insurance_fund.insurance_fund` (mint + spend) | genesis reference, state asset name, guardians, threshold, policy epoch, payout cap (bps) |
| `agent_registry.ak` | `agent_registry.agent_registry` (mint + spend) | bootstrap reference, trusted authority script hash, policy ID, asset name, state lovelace, reserve credential, datum commitment |

The authority hash depends only on the bootstrap; the other five governance
scripts depend only on the anchor, so there is no hash cycle
(`docs/remediation/repair_20261109/GOVERNANCE-APPLIED-REHEARSAL.md`).

Not deployed: the legacy `governor.ak`, `timelock.ak` and
`governance_policies.ak`; `agent_nft.ak`; the F04 anchor and F05 authority
validators (the bridge / ExecuteIntent route stays disabled, owner decision
3); and `cardano/lib/vams/vdso.ak`, which is a library. Insurance Deposit stays
disabled pending F05. ExecuteIntent stays disabled in governance v2.

## Step 1: source checks (local)

CI runs `aiken check --deny --seed 20260711 --max-success 250` (owner decision
2 authorizes the same flags locally with pinned Aiken 1.1.21). Note: the
2026-11-12 local run reached its 600-second deadline during test collection
with no result (`docs/remediation/repair_20261112/SYNCHRONIZED-QUALIFICATION.md`).
That is not a pass; a completed run is still needed.

```bash
cd ~/code/VAMS-testnet/cardano
~/.vams-tools/bin/aiken check --deny --seed 20260711 --max-success 250
~/.vams-tools/bin/aiken build
git diff --exit-code plutus.json
```

`aiken build` must reproduce the committed `plutus.json` byte for byte.

## Step 2: applied-identity rehearsals (local, synthetic)

These apply the real parameters with `aiken blueprint apply` in a temporary
copy, evaluate the applied validators on ledger-shaped contexts with
`aiken uplc eval`, and record CPU and memory:

```bash
cd ~/code/VAMS-testnet
~/.vams-tools/venv312/bin/python scripts/cardano/governance_v2_applied_rehearsal.py --out /tmp/governance-v2-rehearsal.json
~/.vams-tools/venv312/bin/python scripts/cardano/insurance_applied_rehearsal.py --out /tmp/insurance-rehearsal.json
```

Last recorded results (2026-11-09): governance 46/46 after the one-check-per-
transaction redesign, review pending (`GOVERNANCE-DELEGATION.md`); insurance
17/17 (`INSURANCE-APPLIED-REHEARSAL.md`). Keys, seeds and amounts are
synthetic; contexts are not ledger-validated (fees, min-UTxO, collateral,
balance, signatures); costs use the evaluator's model, not live Pre-Prod
parameters. No applied-identity rehearsal exists yet for `agent_registry.ak`.

## Step 3: offline ledger checks (local, offline cardano-cli)

Available now, not yet run: use `cardano-cli` 11.2.3.0 offline with the
Pre-Prod genesis files shipped in the cardano-node 11.1.3 release
(`~/.vams-tools/dl/cardano-node-11.1.3/x/share/preprod/`) to estimate fees,
minimum UTxO and collateral for each rehearsal transaction shape, and to
derive each applied script hash independently of Aiken. Mismatched hashes stop
the ceremony. Results must be labelled "offline, genesis parameters": live
protocol parameters may differ.

## Step 4: real parameters (needs owner inputs)

UNKNOWN on 2026-11-13: the governance bootstrap (seed UTxO, custodian keys,
thresholds), insurance guardians and threshold, agent-registry trust anchors,
and the Cardano key hashes of the five governance seats (layout in
[TEAM_SIGNER_GOVERNANCE.md](TEAM_SIGNER_GOVERNANCE.md), owner decision 12;
holders A–C not yet named). Real seed UTxOs
need a funded faucet address and a live query, which needs a grant. Apply the
real parameters into a new empty directory twice and require identical
output; record every applied hash.

## Step 5: construct, sign, submit (needs separate grants)

Construction against live protocol parameters needs a live-query grant.
Signing happens only in an isolated signer; a signing-key file's contents
never enter evidence, chat or Git. Stop before `transaction submit`:
submission needs the owner's explicit approval of the exact signed body.
After an approved submission, confirm independently and check every script
output before writing a deployment manifest. If confirmation or state is
wrong, do not resubmit blindly: keep the signed body and logs, halt dependent
steps and use the reviewed recovery or cancellation path.

## Manifest

A deployment manifest uses `deployment-manifest.schema.json` 2.0.0 with
`network: cardano-preprod`, the eight artifacts above with compiled scripts,
and a `cardano_build` record. It is checked by
`python scripts/audit/audit_program.py readiness --stage canary
--deployment-manifest <file>` with the other canary inputs. A rehearsal record
must never enter the deployment register.
