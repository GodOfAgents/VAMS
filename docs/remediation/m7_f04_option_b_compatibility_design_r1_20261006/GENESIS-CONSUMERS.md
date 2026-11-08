# F04 Option B: V2 genesis and credential-epoch compatibility

Status: design only, pending exact-artifact independent review. No compiled execution, ledger admission, live-network or compatibility acceptance. The owner accepts per-bootstrap policy IDs and multiple prior quorum anchors. This does not establish global DID uniqueness. Standalone agent_nft is normative and registry-side mint must reject.

## Source reality and historical boundary

Current cardano/lib/vams/types.ak:182-228 has AgentDatumV1 and no recovery/controller/guardian epochs. Current agent_registry.ak:145-181 registers a V1 output, conserves ADA plus the minted NFT, initializes reputation5000/status0 and uses legacy action authority. Its former registry-mint route is superseded. The 2026-10-04 recovery design remains the normative recovery contract, particularly sections3/3a/4 and68/83; its older source description is historical.

The preflight ASSESSMENT.md and CAPTURE-CONTEXT.md limitations remain: incomplete retained captures for earlier API/name searches and outer launcher, 35-file before/after scope,73 compilation-manifest entries matched once, cached dependency/history lock gaps not repaired. This design supplies no retroactive capture or compilation credit.

## Exact V2 genesis

CONSUMER-CONTRACT.json freezes constructor tags, ordered fields, bounds, possession requirements and target API contracts. V1 Constr0 is not reinterpreted. V2 state is Constr1; PreGenesisV2 is Constr2. Both new constructors use explicit schema_version2 and exact field counts; malformed extra/missing fields, coercion or alternate version reject.

PreGenesisV2 commits DID/founder/initialcontroller/operator/sorted5 guardians/metadata/stake at the fixed registry payment script address with no staking credential. It has exact ADA-only value equal to initial_stake_lovelace >=1000000000. bootstrap_ref is that input's actual OutputReference; it is absent from the creating seed datum. Neither the seed's own future transaction ID nor a policy/name derived from it is embedded in the seed, avoiding a transaction-ID self-reference.

A subsequent anchor issuance references that actual seed, consumes a distinct anchor_seed, and commits the exact fields. Registration consumes the same bootstrap seed exactly once, references exactly one matching immutable anchor, and creates exactly one V2 state carrying exact seed ADA plus the sole +1 identity NFT. Both standalone mint and RegisterAgent independently require this binding; all ledger inputs must conserve value and have valid witnesses. Anchor quantity is not counted as registration stake.

The genesis state has state_nonce/control_epoch/guardian_epoch=0, frozen=False, pending=None, reputation5000, status0, authorized_slashers=[], action_epoch0. registered_at_ms equals the finite inclusive lower bound of the registration interval; both bounds are u64, lower<=upper and width<=300000ms. Slash remains unavailable pending separately reviewed F05-compatible activation; action_epoch0 supplies neither F04 recovery authority nor F05 committee authority. Later recovery preserves economic/reputation/action fields and cannot create slash rights.

Founding owner and initial controller may be the same key, otherwise both must sign registration. All five canonical distinct guardians must sign registration as proof of possession even though anchor issuance needs founder plus3of5. Guardians must be disjoint from founder/currentcontroller/operator. Transaction-body ledger signatories establish possession; they do not establish separate real-world custody or compiler provenance.

The immutable anchor retains initial controller/operator/guardian/metadata fields; after authorized rotation, validation compares immutable identity policy/name/DID/founder/bootstrap and independently checks anchor genesis validity. It does not force mutable current controller/guardian/operator/metadata back to genesis. Current state is the sole recovery authorization source, never the historical anchor initial key list.

Multiple distinct anchor seeds can commit the same bootstrap. Each anchor may be referenced repeatedly. Exactly one matching anchor reference per transaction is an ambiguity guard, not a global anchor count. Ledger consumption of the same bootstrap limits registration to one, including alternative candidate policy attempts; a synthetic script evaluation alone does not prove this ledger property. Different bootstrap references can register the same DID. No cross-bootstrap uniqueness claim or stateful DID registry is introduced.

## Explicit V1 handling

V2 entrypoints reject both14-field V1 and older8-field datums, including conversion by schema defaults. V1 may remain a read-only legacy view with original address/policy semantics, but has no V2 guardian/controller recovery or epoch0 authority. No V1 migration, token remint, burn, authority transfer or asset/value relaxation is authorized. Existing V1 state cannot enter V2 transition branches; any migration needs a separate owner-reviewed contract and implementation authorization.

## Recovery continuity

All prior thresholds/delays remain: routine controller+2 guardians+newcontroller possession/48h; recovery3 guardians+newcontroller possession/immediate freeze/7d without oldcontroller veto; guardian rotation3old+all5new possession/14d; unfreeze3guardians/48h; voluntary deregistration controller+3guardians/48h; freeze/cancel3guardians. Request expiry window30d, finite inclusive transaction width<=5min, nonce/epoch checkedu64 increments and domain-bound pending requests remain exactly as the prior DESIGN sections3/3a/4. Only executed controller change increments control_epoch; only executed guardian change increments guardian_epoch. Slash cannot reset pending state, epochs or freeze and remains separately disabled.

## Actual consumer map and target contract

sequence_wallet.py:20-85 currently constrains expiry<=24h, configured whitelist and value, but no identity/controller/epoch tuple. active_sessions is its concrete observed cache, keyed only by session address. A future grant must bind exact NFT/bootstrap/network/currentcontroller/control_epoch/guardian_epoch/association commitment and verify current authority immediately before use. Old or held grants must deny after epoch change, freeze or uncertain state. Grant renewal is fresh authorization, not automatic recovery.

tee_plugin.py:131-170 generates service/delivery/root20 binding and checks live provider provenance; verify_proof:230-247 extracts root from supplied proof and checks report consistency. This is not an external current-controller check. Future authority validation must obtain expected root from independently authenticated identity association and compare it to proof/report; never derive expected authority from the proof itself. Fresh epoch-bound credential context must be checked independently without claiming current provider report includes Cardano epochs. phala_tee.py exposes provider attested_root_eoa/report_data; no epoch resolver is present. trust_aggregator.py:104-127 forwards kwargs and its bundle provenance guard does not supply controller authority.

oms_identity.py:97-143 checks provider address subject and live/non-authoritative provenance with sanitized failure paths; no F04 epoch and no identity-result cache were observed there. clr_router.py:468-493 requires loaded OMS service block and live compliance result. Future institutional routing requires authenticated current subject AND live OMS result; offline/malformed/stale/mismatched or mock evidence denies, preserving INV5.

Cardano controller hashes are28 bytes; root EVM EOAs are20 bytes. No equality/truncation/padding/hash conversion is valid. An association interface requires schema/network/fullidentity/controller/bothepochs/root/bindingnonce/expiry/verifier/config identifiers and dual possession of current Cardano controller and specified EVM root over the same complete domain commitment. The proof algorithm/serialization, authoritative resolver backend and chain finality qualification remain a separate reviewed activation gate. This design chooses no provider, oracle or new trust model. Until that gate passes, V2 EVM current-owner TEE/session/OMS use is disabled/failclosed. Existing local/mock tests earn no consumer compatibility credit.

Authenticated resolver results must identify exact current stateUTxO, canonical chain point/finality evidence/schema/verifier/config plus current datum. Unknown/offline/stale/ambiguous/reorg uncertainty denies. Caches are keyed by full identity and both authority epochs plus association commitment; identical DID is insufficient. Every use and immediately pre-effect must verify current state; held grants cannot survive recovery/freeze/reorg/guardian rotation. A cached success never substitutes for fresh current-state authorization. External effect atomicity needs separate integration review.

## Verification and invariants

GENESIS-CASES.json freezes39 independently derived cases, all PENDING/NOT_RUN. Compiled paired-entrypoint, anchor, recovery, consumer and ledger admission requirements are separate. At worst-state use DID256bytes/fiveguardians/maxbounds/maxpending, record node cost model/CPU/memory/fees; no budget pass is awarded here. Guard-removal mutations, stale epoch and externally mismatched root must fail their named oracle; actual implementation source/build/provenance/witness bindings are required later.

INV1/2/7/8/9/10 are not touched. Future consumer integration affects INV3/4/5/6 and preserves24h expiry, whitelist/value limits, failclosed OMS and expectedroot EOA binding. Design does not repair INV9, qualify M5 or explain historicalM2. Mock mode remains local/non-authoritative and prohibited for live authority.

Readiness NOT READY; deployment, Deposit, Slash activation and ExecuteIntent disabled. No production source or credentials changed.

## Exact wire and pending payload completion

V1 Constr0 has exactly14 frozen fields; V2 Constr1 exactly21 and seed Constr2 exactly8. These are deliberate wire tags implemented by a tagged union/exact decoder, not inferred from separate record declarations. Bool False=Constr0[]/True=Constr1[]; Option Some=Constr0[payload]/None=Constr1[]. Actual compiled CBOR vectors must independently qualify all encodings. Status is exactly0(active) or1(suspended), matching current valid_datum:445;2 and unknown statuses reject.

CONSUMER-CONTRACT.json pending_wire freezes tags0..4, exactarity10 for controller/recovery/guardian variants and9 for unfreeze/deregister; destination fields precede the ordered common controller/commitment/request/baseepochs/time/authorization fields. Selected scheduling authorizers are canonical distinct minimal role witnesses, maximum8 allowing disjoint3old+5new guardian rotation; actual scheduling ledger signatures must verify every role. Unfreeze uses32zero destination commitment; deregistration uses the prior controller-destination hash over schedulingcontroller, committing fixedpayout. Actiontags1..5 and prior request serialization/domains remain unchanged. Controller and guardian no-op rotation reject; epochs increment only real changes. Fresh session grant duration<=24h, now>=expires_at rejects, uncertain/rollback clock denies, and existing expiry is never extended implicitly.
