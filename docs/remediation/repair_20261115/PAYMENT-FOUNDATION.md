# Payment foundation and corrected implementation sequence

Date: 15 November 2026. Scope: corrected payment plan Slice 0 and the initial
payment-ledger/policy binding. Local engineering candidate; NOT READY.

## Source and preserved work

SLICE0-SOURCE.json under VAMS-payment-foundation-20261115-01 binds 4,199
selected Windows/WSL paths at dirty remediation/phase1 HEAD
4f0f7887efb384e883b9de4d7c56387479e471a5. Its SHA-256 is
a418fcd62d7b140a3c4d813d132dd3827d3a7f106f0b65ca7ae15d2a77788a22.
It preserves the 21 newer modified paths and 13 added tests/docs, with exact
AGENTS/platform/cache/vendor exclusions. The audit-catalog/dispute candidate
and other retained preparation are separate; none is silently integrated here.
Historical results retain their own identities, including the 14 November
242-path contract campaign. This is not a clean release commit.

## Implemented boundary

- intent_v1.py defines exact canonical version-1 intent, capability and payment
  approval bytes. Intents bind the existing ObjectAttemptV5 operation, attempt,
  proposal, admission and authority context rather than creating replacement
  effect IDs. Amounts are integer uint256 atomic units, never float quotes or
  implicit conversions from V5 execution-cost units.
- PaymentPolicyBindingV1 authenticates the current asymmetric V3 admission,
  verifies a separate-domain low-S secp256k1 payment approval and compares a
  responsible-host-configured current source before and after validation. No
  caller-supplied Boolean or policy state authorizes spending. Public verifier
  keys cannot sign. The ledger rejects a provider key used as payment authority.
- The configured capability binds actor, provider, host, chain, asset, token
  domain/decimals, payer, escrow payee, facilitator, validity and registry
  terms. The intent and payment approval additionally bind the transfer nonce. The EVM actor root must be canonical and scheme 1. Protocol fee remains
  5bps; builder metadata cannot exceed 5,000bps. These are approved metadata
  commitments, not authenticated registry reads or token-transfer verification.
- ledger_v1.py adds monetary reservations to retained V5 operations/attempts.
  New tables reference actual V5 keys. The real journal verifies retained signed
  facts, active/current generation and a reserved effect obligation. Its existing
  BIGINT execution budget is not debited again. New monetary columns use
  NUMERIC(78,0) with explicit uint256 checks. Scoped HTTP idempotency, one intent
  per operation/attempt and chain/asset/payer-scoped token-nonce uniqueness prevent
  accidental replacement. Different intentional purchases need distinct V5
  logical intent/operation identities as well as different HTTP keys.
- A stable monetary budget identity binds denomination and principal across
  policy versions. Reservations check the cumulative cap under locks and
  compare-and-set; retained rows must sum to the head. One monetary budget is
  bounded to 256 retained intents in this version, and event histories to 32.
  Reaching a bound fails closed; history is never erased or automatically reset.
- Returned records grant no signing authority and report no native payment
  verification. Before possible credential release, the ledger revalidates
  policy/admission and durably records a credential digest. It stores no raw
  token authorization. Unknown outcomes preserve the original exposure digest
  and reservation. Clock rollback rejects new reservation/exposure. Lookup and
  uncertainty recording remain available after policy denial or expiry.
- There is no pay, fund, confirm, dispatch, refund or release API in this slice.
  Provider absence, timeout, policy revocation and expiry cannot release money.
  Authentic chain resolution and compensation are required in the next slices.

## Storage and verification limits

The add-on uses the exact configured V5 database/journal, explicit migration and
runtime roles and a separately reviewed PG18 compiler/provenance/constraint
manifest. Migration is explicit, transactional and refuses existing/partial
payment-schema adoption. It creates no roles, changes no V5 schema and retries
no uncertain result. Catalog validation checks exact columns, compiled key/FK/
CHECK definitions, ownership, ACLs, trigger enforcement and relation properties.
SHARE UPDATE EXCLUSIVE table locks and narrow MAINTAIN privileges protect the
inspection through the transaction. Runtime updates cover only monetary heads
and exposure state; no DELETE or broad UPDATE privilege is granted.

Both policy and ledger constructors/runtime checks reject staging, testnet and
production. They are not wired into a gateway or signer. A direct ERC-3009
transfer to ComposedSettlement does not identify or credit an allocation: current
creation uses safeTransferFrom. No working funding adapter or token deployment
is asserted. Current VAMSToken supports ERC-2612, not established ERC-3009.

The focused PAYMENT-FOUNDATION-FOCUSED-01 run executed 35 methods and 182
subtests, zero failures/skips, on the exact five-file overlay of the 4,199-path
base with installed Python 3.12.16. It uses genuine synthetic-key signatures and
the actual V5 journal history verifier. Database transport and catalog/schema
oracles are explicit doubles: this is not native PostgreSQL, concurrency, ACL,
crash recovery, custody, finality or authentic payment evidence. JUnit's 217
event count must not be reported as 217 methods. Raw streams, tool/source hashes,
application/validation exits and Windows parent receipts remain in the evidence
directory. Post-integration combined checks are separately required.

The initial root draft's unknown-credential and backwards-clock defects were
identified in non-author review and corrected. The exact original draft
6621170f87a6a00b3f8dac2ee2f25912b29fdc35f34997e768ed85149b0d614c
is reconstructed and hash-checked separately for regression proof; it is never
integrated. A third review fix strengthens the schema lock. Its actual two-session
DDL-race behavior remains a native-PG qualification requirement.

## Remaining corrected payment sequence

1. Complete the public capability inputs in payment-capability-inputs-v1.json;
   freeze reviewed token/domain, payer, facilitator/signer and compensation facts.
   UNKNOWN values never become defaults. Freeze the upstream SDK artifact and
   dependencies before any separately authorized acquisition. Existing x402.py is
   legacy simulated VAMS code, not a deployed upstream SDK awaiting an upgrade.
2. Qualify explicit PG18 DDL/catalog/ACL/migration compilation; then multiworker
   reservation/idempotency/nonce races, serialization/commit/close uncertainty,
   DDL races, database restart and restore on an approved disposable runner.
   Historical postgres:18 evidence is not current availability. The fresh local
   preflight found no docker CLI on the inspected WSL PATH and no qualified
   current payment database was established. No service was started.
3. Add authenticated gateway admission/status/result lookup around these existing
   IDs, a protected signing broker and the pinned exact-payment adapter. Revalidate
   immediately before credential release, signing, dispatch and settlement.
4. Prove escrow funding separately from earned provider payout. Preserve registry-
   authoritative fee snapshots, reserve-until-authenticated-resolution, the
   approved 72-hour earned hold, 5% dispute bond, 14-day resolution deadline and
   48-hour governed resolution. Upfront payment requires compensation in P0.
5. Add authentic transaction/finality reconciliation and compensation before any
   live pilot. A released bearer authorization cannot be canceled by local policy
   alone. Preserve original attempts across lost responses, provider/facilitator
   outages and reorganizations; never infer safe repayment from provider absence.
6. Run complete producer/consumer fault suites, privacy review, operating controls
   and authorized chain evidence. Metering/Permit2, MCP, batching and Solana are
   subsequent independent gates. An Amoy-first component campaign does not remove
   mandatory Cardano Pre-Prod or the full A-G readiness program.

No INV-1--INV-10 implementation, tokenomics, role, wire V1/V2/V3/V5 encoding or
restricted deployment setting changes. Root identity and monetary backing gain
local checks; reward solvency and authentic verification are not newly qualified.
Deposit, Slash activation, ExecuteIntent, real fiat/yield, rewards/emissions,
vesting, buyback/delegation and ordinary governor remain disabled as before.
13 findings remain open, 0/36 tracks verified, no admission/promotion. Both chains,
independent assurance and actual 7-/14-day observation requirements remain.
