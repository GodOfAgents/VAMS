## 2026-11-09: anomaly detector fails closed; gateway stops inventing node claims (F14, F15)

- **Anomaly detector (F14).** `neuron/intelligence/anomaly_detector.py` used to classify a NaN or infinite activation as "not adversarial", because `NaN > threshold` is false. Every entry point now rejects nonfinite or empty input and nonfinite thresholds with `ValueError` instead of producing a classification.
- **Gateway node defaults (F15).** `gateway/server.py` no longer invents profile values for a node whose signed heartbeat omits them. Previously it recorded passport "ERC-8004 Phala TEE", credit score 750, two skills, a high cognitive profile, region us-east-1, price 0.15 and network mocha-4. Undeclared fields now get neutral defaults. Node views include `"verification": "unverified-self-declared"` and the list of self-declared fields.
- **Privacy inventory.** Re-bound with a dated revalidation entry. No new field was added; T33 remains BLOCKED.
- **Containment map.** `docs/remediation/repair_20261109/F11-F14-F15-ADVISORY-CONTAINMENT.md` shows that none of these signals authorizes an action or payment on the restricted profile.
- **F12.** The native PostgreSQL crash/restart campaign, `scripts/remediation/effect_v3_native_pg_campaign.py`, covers seven kill points with two worker processes. It is written but not yet run. The effect stores require PostgreSQL 18 (`pg_constraint.conenforced`); on 17 they fail closed. See `docs/remediation/repair_20261109/F12-NATIVE-PG-CAMPAIGN.md`.

F11, F12, F14 and F15 stay open. Status unchanged: 13 open, 0 of 36 verified, NOT READY.

## 2026-11-09: composed settlement dispute window (F13, owner decision 10)

Earned composed-settlement payments are now held for 72 hours, during which the allocation's agent can dispute a delivery by posting a bond of 5% of the row amount, rounded up. The resolver, the governance timelock, either upholds the dispute or rejects it. Uphold refunds the full row and returns the bond, and the row can never be paid. Reject releases normal payment with the recorded fees and pays the bond to the provider. If the resolver has not decided within 14 days, anyone can finalize: the provider is paid and the bond goes back to the agent. There is no slashing, and outcomes are binary.

The dispute state machine lives in the new `contracts/src/economic/DeliveryDisputeV1.sol`, which `ComposedSettlement` deploys in its constructor so the two are permanently bound. `ComposedSettlement` gains a seventh constructor argument (the resolver), a hold check before every earned payment, including object-V3 completions, and `refundUpheldDispute`, which only the dispute contract can call. The atomic `claimProviderShareV2` now reverts with `LegacyInterfaceDisabled`, because instant payment cannot coexist with the hold. Providers record with `recordEarnedDeliveryV3` and claim with `claimEarnedProviderShareV3` after the window. `DeployRestrictedTestnet.s.sol` passes the timelock as resolver.

Results:

- Foundry: 1167/1167. That is the previous 1150 plus 17 new dispute acceptance tests, including a conservation fuzz test. 52 existing tests were adapted to record, wait out the window and claim, with their expectations unchanged.
- Slither (CI flags): 0 High, 62 Medium, none in the new code.
- `ComposedSettlement` runtime size is 24,401 B, leaving 175 B of EIP-170 margin.

Design: `docs/remediation/repair_20261109/F13-DISPUTE-WINDOW-DESIGN.md`. Implementation record: `docs/remediation/repair_20261109/F13-DISPUTE-WINDOW-IMPLEMENTATION.md`. Non-author review is pending. F13 stays open, and status is unchanged: 13 open, 0 of 36 verified, NOT READY.

## 2026-11-08: current-tree secret gate passes

Owner decision 9 accepted all 638 first-party current-tree Gitleaks findings as non-credential (validator hashes, file digests, ephemeral test-committee Ed25519 public keys and lists, derived digests, asset names, policy IDs, identifier strings; see `docs/remediation/repair_20261108/SECRET-SCAN-DISPOSITIONS.md`). Their exact fingerprints are in `.gitleaksignore`, and the new CI step runs `scripts/security/gitleaks_ignore_reproof.py`, which fails unless every entry maps to an accepted manifest record in `docs/remediation/repair_20261108/secret-scan-dispositions.json` whose file is unchanged, inside `docs/remediation/` or `scripts/remediation/`, under `generic-api-key`. No rule, path or regex allowlist was widened. `m0_4_vendor_baseline_gate.py` now passes (first-party 0, vendor 479, unknown 0). Complete-history Gitleaks and TruffleHog still fail pending the separately authorized history rewrite. Status unchanged: 13 open, 0 of 36 verified, NOT READY.

## 2026-11-08: all locally runnable CI gates pass

Owner decision 8 approved npm registry and Rust toolchain downloads. Solidity, Aiken, Python, Bandit, pip-audit, VIR Rust, frontend, Semgrep reviewed gate, Slither and the Envoy gateway config gate all pass on the owner-operated runner. Changes: `cargo fmt` of `vams-vm/crates/vir-codec/src/action_context.rs`, and an in-range `frontend-vite/package-lock.json` update of vite 7.3.7, zod 4.6.7 and source-map-js 1.2.2 for newly published high advisories in build/dev tooling. Still outstanding: secret scanning dispositions, the networked Semgrep discovery scan, adjudication of 63 Slither medium results, and hosted exact-commit CI with SBOM/signing. Details: `docs/remediation/repair_20261108/GATES-20261108.md`. Status unchanged: 13 open, 0 of 36 verified, NOT READY.

## 2026-11-08: Bandit and Python gates green

Owner decision 7. Bandit (`bandit -r neuron/ gateway/ -ll -ii`) now exits 0 with no reportable issues, without any change to its scope or thresholds. All 74 B608 findings were string-built SQL in `neuron/effect_*` where every interpolated value is a fixed `public.vams_effect_*` table constant, a class attribute bound to one, a `table` name checked against a fixed set or strict regex, or a constant `FOR UPDATE` suffix; values were already driver parameters. Each is suppressed on its own line with a recorded reason, and the new `neuron/tests/test_effect_sql_identifier_guard.py` fails if any executed SQL f-string interpolates anything else or if a `nosec B608` appears outside a verified statement. The 14 B102 findings are test-only `exec` of AST-extracted repository source, suppressed per line.

The semantic-MMU privacy inventory (`docs/remediation/privacy-field-inventory-20261020.json`, still UNAPPROVED; T33 BLOCKED) was re-bound: nine digests refreshed, twelve anchors re-located, and two refactored flows (node ID derivation, heartbeat body) confirmed to carry the same fields. A dated revalidation entry records the check. Three R11 provenance tests pinned to the September Cardano digest are retired as historical.

Full Linux Python 3.12 suite: 3,419 passed, 0 failed, 1 visible skip, 9 owner-retired tests deselected. Status unchanged: 13 open, 0 of 36 verified, NOT READY.

## 2026-11-08: Python suite repairs on Linux 3.12

Full suite moves from 3,369 pass / 72 fail to 3,416 pass / 22 fail (1 visible skip, 6 owner-retired historical tests deselected by exact ID; see `docs/remediation/HISTORICAL_TESTS.md`). Repairs are test-side; no product behavior changed:

- `pytest.ini` adds the repository root to `pythonpath`; gateway route tests no longer depend on another module mutating `sys.path`.
- Gateway route/replay fixtures (`test_m2_3_gateway_routes.py`, `test_m2_4a_replay_schema_integrity.py`) stop startup from rebinding the demo-only Composer over their recording handler; a new test proves the real local-mode Composer gate returns 503 without calling the handler.
- `test_gateway_current.py` dashboard tests use a fresh nonce per signed request (durable replay protection correctly rejected reuse).
- `test_gateway_constructor_log_privacy.py` follows the hardened client: supplied environment must match process policy (new rejection test) and live modes are refused before transport or logging.
- `test_gateway_root.py` mocks the Composer with `spec=True` (Python 3.12 rejects `assert_*` attributes on bare mocks) and asserts the non-authoritative simulation label.
- `test_gateway_dashboard_boundary.py` tests the real `gateway/server.py` under pytest; its pre-repair scope comparison skips visibly unless a base file is supplied.
- `test_gitleaks_configuration.py` follows the refactored scanner API, pins the tightened address exception, and adds checks that a clean scan exit and a missing explicit scanner path are rejected.
- `test_effect_canary_postgres_transactions.py` sets its own runtime mode, models the advisory lock and V2-authority guard, and adds regressions for lock-first ordering and V1/V2 writer exclusion.

Remaining: one semantic-MMU inventory test (19 subtests) and three R11 provenance tests pin stale source hashes/anchors; Bandit still fails. Status unchanged: 13 open, 0 of 36 verified, NOT READY.

## 2026-11-08: Cardano source compiles; blueprint regenerated

Type-level repairs in `validators/f04_anchor_policy.ak` and `validators/governance_v2.test.ak` let native Aiken 1.1.21 compile the integrated source for the first time. No validator rule changed; a missing guardian index now fails explicitly. `aiken check --deny --seed 20260711 --max-success 250` passes: 2,627 checks, 884 tests, 0 errors, 0 warnings, including all 724 prepared governance v2 cases. The stale `cardano/plutus.json` (eight validators missing, five hashes outdated) is replaced with fresh `aiken build` output. Six historical harness tests (`docs/remediation/m3_2b_r4`, `m3_2b_r6`, `m3_f04_impl_r2`, `m3_f04_impl_r4`) now run but fail because they encode superseded designs such as registry-side minting; their disposition needs an owner decision. F01–F03 remain open. Details: `docs/remediation/repair_20261108/CARDANO-COMPILE.md`.

## 2026-11-08: D1 runner baseline, reproducible remappings, test-collection repairs

Owner decisions of 2026-11-08 are recorded in `docs/remediation/OWNER_DECISIONS_20261108.md` (D1 runner, native Aiken, first-canary route scope, TR-01–TR-10, secret-scan disposition authority). A WSL2 Python 3.12.16 / Foundry 1.7.1 / Aiken 1.1.21 / Node 22.23.4 / PostgreSQL 17.11 runner was assembled from checksum-verified official sources; it is owner-operated, not independent CI.

`contracts/remappings.txt` now pins every remapping Foundry previously auto-detected. Auto-detection chose among duplicate nested `forge-std`/`erc4626-tests`/`halmos-cheatcodes` copies by directory layout, which changed solc metadata and the pinned policy runtime hash (fresh export: 1118 pass/5 fail; repaired: 1141/1141). Two Python test modules failed at collection, so pytest executed no tests: the Gitleaks configuration test did not register its spec-loaded module before execution, and the TEE promotion-scan test imported a sibling script that is not on the import path. Both now use the existing spec-loading pattern. Details: `docs/remediation/repair_20261108/REMAPPING-PIN.md`.

Baseline observations, not repairs: native `aiken check` fails to compile the current `cardano/` source (first errors in `validators/f04_anchor_policy.ak`), whereas committed `829ab54` passes 50 tests; Bandit reports 99 medium/medium findings in the new `effect_*` PostgreSQL modules (B608) and tests (B102). No finding or track status changes: 13 open, 0 of 36 verified, NOT READY.

## 2026-11-05: inactive V3 heartbeat authority producer

The new non-upgradeable V3 source reads the pinned timelock generation/commitment, policy projection and mandatory custody adapter. Policy configuration computes its digest from those current reads and rolls back on failure. The source checks an explicit expected chain ID at construction and every read. One-time policy binding checks the source's actual policy and timelock instances. Custody reads have a fixed 50,000-gas cap, copy only 96 bytes, require exactly 96 returned bytes, and reject noncanonical integer words. A real custody implementation and its gas envelope remain UNKNOWN; synthetic fixtures supply no custody authority.

The exact isolated M82-plus-four-file R6 candidate passed 1,141 Solidity methods in 71 suites, including 24 focused methods, with zero failures/skips. Source runtime/creation sizes are 19,657/34,182 bytes; policy sizes are 4,944/13,879. Three unchanged-source BEFORE regressions reproduced wrong-chain reads, wrong-policy source binding and trailing custody data acceptance. Two earlier baseline fixture failures were corrected by placing revert expectations at execute; original receipts remain. Independent manual Python ABI vectors agree with Solidity for all three new digest domains. Combined canonical checks follow integration separately.

The original source-only design's keccak256 wording is superseded for this NEW V3 family by SHA-256 over fixed bytes32 ASCII domains and ordered static ABI words. Existing V1/V2 source and wire bytes are unchanged. Profile/config/snapshot preimages contain 25/19/23 words respectively; the profile excludes its stored digest, and configuration commits policy root/version/epoch through the profile projection. The first native JSON comparison failed solely on preserved Windows CRLF versus Linux LF transport; the separately frozen LF copy then reproduced byte-for-byte. No digest/preimage content changed.

The producer remains inactive, with no V3 consumer or live profile. A future consumer must independently pin the actual source/policy classes AND reviewed instances, revalidate current digest, and bind its own registry identity. Actual custody/challenge/finality, enrollment/migration, gateway/client and Cardano-native authority remain unfinished. The M82 full-tree secret gate is FAIL; focused scanning does not replace full source/history/TruffleHog. No finding or track is closed. INV-1--INV-10 enforcement and restricted disablements are unchanged. Full A-G, both chains, 13 open findings, 0/36 verified tracks and actual seven-/fourteen-day observation remain: NOT READY. Details: docs/remediation/repair_20261105/HEARTBEAT-AUTHORITY-PRODUCER-V3.md. Historical content follows unchanged.

## 2026-11-05: inactive timelock authority-generation prerequisite

The separate V3 operation-aware timelock records a monotonic generation and chained commitment for effective role membership, role-admin and minimum-delay changes. Restoring earlier permissions or delay does not restore the old generation. No-op or failed changes and ordinary schedule/cancel/execute lifecycle do not advance this global generation; per-operation epochs remain separate. Frozen VAMS/V1/V2 sources and existing wire encodings are unchanged.

The 48-hour floor and self-call restriction remain inherited. V3 observes delay changes through the pinned OpenZeppelin execution hook because the VAMS updateDelay implementation is non-virtual. Each batch target records its transition before the next target executes, and a later failure rolls back the batch. The constructor commitment includes the actual controller self-admin member; it is instance-specific.

The exact isolated M81-plus-V3 candidate passed 1,117 Solidity tests in 70 suites, zero failures/skips, including 17 focused cases. V3 measures 8,473 runtime and 11,830 creation bytes. A separately retained source-factory probe reproduces the V2 missing-generation failure and passes against V3; it is not included in the 1,117 and is not a readiness gate. Prior two compiler failures executed zero tests and remain preserved. Local fixtures and AI source review do not supply authentic custody or live authority.

V3 is not configured into the existing V2 registry/policy, whose runtime pins must continue rejecting it. Authentic authority/custody/challenge/finality producers, reviewed rebinding, enrollment/migration, gateway/client wiring and the Cardano-native counterpart remain unfinished. No profile, role or route is activated. The M81 full secret gate remains FAIL; structural artifact checks clear no findings. Full A-G, both chains, independent assurance and actual seven-/fourteen-day observation remain required. Thirteen findings remain open, zero tracks verified, zero promotions: NOT READY. Details: docs/remediation/repair_20261105/HEARTBEAT-AUTHORITY-GENERATION.md. Historical content follows unchanged.

## 2026-11-05: inactive atomic heartbeat consent consumer

The separate, non-upgradeable schema-2 EVM prototype relays bounded canonical bytes through the exact singleton Timelock operation. Normal replacement requires OLD+NEW body-key consent; lost-key recovery requires observed governance delay of at least 48 hours plus NEW-key consent. The callback revalidates current policy/authority/challenge facts, operation epoch and exact calldata, then applies principal generation/nonce compare-and-set atomically. Queue cancellation and identical requeue invalidate prior challenge epochs. Existing V1 encodings and code remain unchanged.

The repair pins the known policy implementation, bounds signed principal duration from notBefore to expiresAt, and supports only an explicitly configured zero-grace profile. A stateless pinned router shares canonical codec logic without granting authority. No profile is configured by default. Production enrollment/migration, authenticated current-state and challenge/finality producers, gateway/client wiring and the Cardano counterpart remain required; test-only seeding and synthetic providers supply local fixtures only.

Exact isolated source80-plus-component checks passed the unchanged EVM size limits, 20 focused methods and 1,100 full Solidity methods in 69 suites; the 20 are included. The registry measures 19,070 runtime/47,768 creation bytes, and the test seed harness 19,743/48,459. These are local native results, with synthetic authority and no accepted per-operation gas budget, authentic authority, live proof or operational qualification. Combined canonical checks follow integration separately. The full current-tree secret gate remains failed; scanner findings, history/TruffleHog and the full frozen workflow remain outstanding.

No live profile, authority, role, route, economic parameter or deployment is activated. Full A-G, both Polygon Amoy and Cardano Pre-Prod, 13 open findings, zero verified tracks, independent assurance and actual seven-/fourteen-day observations remain: NOT READY. Details: docs/remediation/repair_20261105/HEARTBEAT-ATOMIC-CONSUMER.md. Historical content follows unchanged.
## 2026-11-05: complete-secret address exception

The generic-api-key exception now applies to a complete captured 20-byte EVM address on the same four approved paths. A longer secret containing an address-shaped prefix remains detectable. Default detectors, the rule selector and AND condition remain. The M0.4 gate changes only its configuration-hash pin; first-party findings still fail.

The bounded fixture regression demonstrated the old configuration mismatch, then passed with the exact corrected candidate. Its strict paired oracle covers 97 baseline and 67 configured observations across 11 generated files; these are source-oracle cardinalities matched by the CLI, not test-method counts or retained raw-report counts. The scanner source, report schema/redaction/columns, binary and raw main streams are bound in the retained evidence. Original failures and historical source identities remain.

This repair does not adjudicate the prior M78 full-tree FAIL (638 first-party matches across 68 files), scan source history, cover TruffleHog or establish full CI. Full current-source gates must run after integration; readiness remains NOT READY, 13 findings open and 0/36 tracks verified. Runtime authority, role grants and both-chain deployment remain unchanged. Details: docs/remediation/repair_20261105/SCANNER-ADDRESS-CAPTURE.md. Historical content follows unchanged.

## 2026-11-05: normal-rotation body-key pair component

`verify_normal_rotation_signature_pair` (Python) and `verifyNormalRotationSignaturePair` (Solidity) require OLD and NEW body-key signatures over the identical canonical base intent and witness. Missing, malformed, swapped, wrong-key and split-witness signatures reject; enrollment and lost-key recovery reject through this normal-only API. Existing one-role APIs, digest domains and encodings remain unchanged.

The isolated M78-plus-payload candidate passed 1,080 Solidity tests across 67 suites (including 17 focused signature methods), the size check, and 16 actual-module Python cryptography methods. Counts overlap and are not added. These are local synthetic-key tests; Python uses the installed Ubuntu 3.14 snapshot with package initialization bypassed, not the independent Python 3.12/full-framework gate. Earlier compiler and unbound-runtime failures remain retained. Combined-source checks follow integration separately.

This component grants no authority and changes no registry or live route. Atomic consent use, current authority/policy readers, challenge/freshness/lifecycle policy, node-scoped gateway/client enforcement, Cardano-native acceptance and full qualification remain pending. The full A-G/both-chain objective, restricted disablements, 13 open findings and 0/36 verified tracks remain: NOT READY. Details: `docs/remediation/repair_20261105/HEARTBEAT-NORMAL-CONSENT-PAIR.md`. Historical text follows unchanged.

## Composer provision error mapping (2026-11-04)

`VAMSResourceComposer.provision()` now maps a `ValueError` raised by the
scorer to the fixed `ComposerError` message `Invalid scoring input or
configuration`. The catch is limited to the scorer call. The existing outer
`ComposerError` handler increments `failed_simulations` once; allocator,
policy-guard, result-construction and cause-chaining behavior are otherwise
unchanged. This is diagnostic boundary handling: it does not change scoring,
allocation policy, transaction values, provider dispatch, or settlement.

The accompanying isolated standard-library fixture has five methods. Against
the M77 composer baseline plus the M77 scorer, models and allocator, BEFORE
recorded five methods, zero assertion failures, two errors, zero skips, native
test exit 1 and evidence-validation exit 0. AFTER recorded five passes with
zero failures, errors, skips or protected I/O. The fixture AST-extracts the
provision method and `ComposerError`; it stubs the runtime policy guard and
instance ID generation. These results are not full Composer imports,
ASGI/framework/provider tests, or live qualification. Counts are not combined
with the separate canonical 18-method campaign.

This documentation records the source change and the preparation-time evidence
identity. Current integration and gate status is recorded by the exact source
manifest and checkpoint; this note does not replace them. The separate source
and test package contains two new paths and awaits integration/evidence
reconciliation. INV-1 through INV-10 enforcement remains unchanged. F11/F14
prerequisites and tracks T07/T22/T24 remain; all A–G work and both chains stay
in scope. There remain 13 open findings and 0 of 36 verified tracks; readiness
remains NOT READY. No deployment, key release, signing, funding, provider or
chain action is authorized by this source change.
## Prepared repair77 — finite scorer configuration (2026-11-04)

The isolated repair rejects negative, NaN/infinite, boolean and nonnumeric
configuration weights. It validates all six fields before summing, safely rejects
oversized integers, and revalidates mutable configuration at every public score
entry, including empty candidate input. Invalid configuration raises ValueError;
valid nonnegative configurations retain the existing 0.001 sum tolerance,
fixed 0.10 requested alignment budgets, ratio-first normalization, subnormal
handling and static zero-base behavior. These are off-chain ranking weights;
integer transaction amounts, registry terms and protocol economics are unchanged.

On identical isolated test modules, the retained source76 scorer produced 31
assertion failures and 13 errors across 18 methods. Its native exit remains 1;
the separate capture validator's zero exit means valid evidence, not a passing
suite. The repaired source passed 18 methods (10 retained requirement methods and
8 validation methods), with zero failures, errors, skips or protected I/O.
Package initializers were bypassed. These results are neither canonical repair77
results nor full pytest/framework/provider/ASGI/live qualification. Counts from
different source campaigns are not added together.

This package is prepared and unintegrated. Source76 remains canonical until the
owner integrates and verifies the complete package. All 18 findings, 13 open
findings and 36 tracks with zero verified remain; full A--G and both chains stay
in scope and readiness remains NOT READY. No invariant enforcement, live role,
restricted-profile disablement or external execution authority changes.

The caller audit found no unsafe allocation/dispatch fallthrough. The separate
ComposerError mapping/failure-counter follow-up is outstanding and is outside
this package. Independent runner, authentic proof, provider/observer, custody,
privacy/security assurance, full gates and real observation evidence remain due.

Historical documentation follows unchanged.

## Unreleased — composer requirement weights (2026-11-04)

Present nonempty skill/cognitive requirements select fixed 0.10 alignment
budgets regardless of prefilled custom alignment weights. Absent axes receive
zero during dynamic scoring; the four base dimensions retain their proportions.
Proportions are divided by the positive base sum before multiplication, avoiding
overflow for valid tiny finite base weights. Nonpositive base sum rejects.
Static no-requirement behavior and configured objects remain unchanged. Ten
actual-module unit methods pass locally; earlier nine-method R1 evidence remains
separate and is not added to that count. Full pytest/composer/provider qualification
is unrun. Scoring confers no admission, effect, proof or payment authority.

See docs/remediation/repair_20261104/COMPOSER-REQUIREMENT-WEIGHTS.md.

## Unreleased — legacy gateway request containment (2026-11-04)

The separate legacy Neuron gateway now refuses live/invalid/drifted runtime
configuration before limiter accounting and every HTTP/direct handler effect,
including hosts that omit ASGI lifespan. HTTP refusal is a fixed503 response;
strict test/local/demo behavior remains non-authoritative. Eleven actual-function
fixture methods pass after reproducing34failed assertions; five real-ASGI methods
and full framework gates remain NOT RUN. Source integration/review/acceptance are
separate; no live route is enabled. See repair_20261104/LEGACY-GATEWAY-REQUEST-BOUNDARY.md.

## Inactive per-role heartbeat signature checks — 2026-11-04

Added Python and Solidity checks for raw64 low-S secp256k1 body-key signatures
bound to canonical consent data and the exact proposed/predecessor principal.
Normal rotation needs separate old and new role statements; recovery/enrollment
select new role. These helpers check one role per call and grant no authority.
No consent store, native reader, challenge, issuer, M2-key possession or gateway
activation is established. The new statement remains proposed; existing wire
encodings and live paths are unchanged. Target crypto/human assurance remains.

## Unactivated consent data codecs — 2026-11-04

Added purpose-separated immutable intent and witness data formats for the future
consent protocol, with Python/Solidity exact-byte conformance. The base excludes
its derived timelock operation and ETA, avoiding a hash cycle. The witness commits
to the base digest, operation, ETA, challenge and selected key-role mask. Parsing
creates no rights and verifies no signer, challenge, current state or authority.
Existing encodings and live paths are unchanged; the new formats are not a full
cross-language wire acceptance or permission to enroll or deploy.

## Inactive operation-aware timelock variant — 2026-11-04

Added a separate non-upgradeable timelock variant exposing the exact active
operation ID and single/batch mode to target contracts. It preserves the48hour
floor and inherited roles/readiness/predecessor semantics, rejects nested
execution, and clears or rolls back context. Existing timelock and deployment
bytes are unchanged. This is an unactivated primitive, not consent enrollment.

## Exact raw secp256k1 verification primitive — 2026-11-03

Added a new full-public-key secp256k1 arithmetic implementation for the existing
64-byte x||y keys and low-S r||s signatures over SHA256digests. It preserves
overflow-coordinate cases and rejects malformed keys/signatures or unavailable
MODEXP. Public cross-language vectors accompany the new primitive. This new
arithmetic remains unqualified for live use pending independent crypto assurance,
target-chain review and real caller/context integration; it creates no authority.

## Inactive governed heartbeat data registry — 2026-11-03

Added a non-upgradeable EVM registry prototype for exact PrincipalV1 data, current
policy snapshots, monotonic generations and permanent revocation tombstones.
It binds the pinned policy implementation and a minimum48h timelock, starts
paused, and separates emergency pause from delayed governance writes/unpause.
It remains unactivated: consent, approved custody/profile, authenticated native
state readers, node routes/client and Cardano support are separate requirements.

## Unsigned heartbeat authority and payload codecs — 2026-11-03

Added versioned, bounded unsigned data codecs for EVM authority-source descriptors
and heartbeat payloads that commit to principal generation, policy snapshot and
the outer M2 nonce/timestamps. Added a literal independent synthetic byte vector.
These APIs do not verify signatures/current state or authorize a heartbeat. No
gateway route, M2 v1 bytes, client, registry or runtime activation changes here.

## Gateway populated-dashboard repair — 2026-11-03

Fixed populated gateway dashboards failing on a missing NodeInfo presentation
property. The property and JSON view share the existing timestamp formatter.
Both online and offline row branches escape node-supplied text as HTML text.
Routes, authentication, signed payloads, node storage fields and numeric display
formats are unchanged. This repairs display behavior without qualifying ingress.

## Pinned policy runtime identity helper — 2026-11-03

Added an inactive RestrictedPolicyRuntimeV1 helper for the governed heartbeat
registry program. It checks the exact captured policy runtime after patching
the three expected immutables; matching getter results alone are insufficient.
The helper does not approve configuration, enroll nodes, verify consent, or
activate any runtime/deployment. Existing enforcement and wire bytes are unchanged.

## Solidity heartbeat principal data codec — 2026-11-03

Added the pure HeartbeatPrincipalV1 Solidity library as a dependency for governed
gateway enrollment. It preserves the Python V1 bytes and SHA-256 digest, with
strict ordered decoding, a bounded calldata entry and typed u64 fields. This is
unsigned data only. Existing runtime, M2, action/receipt bytes, policy, authority,
fees and deployments are unchanged. Registry and node authorization remain open.

## Unsigned heartbeat-principal data contract — 2026-11-03

Added a separate HeartbeatPrincipalV1 canonical data codec for the scoped-node
authorization program. It commits the node slot, signer, certificate, body key,
host/service, audience, heartbeat-only route and policy/generation/time fields.
The codec creates no authority. Governed enrollment, authenticated current-state
resolution, route authorization and the distinct M2 client remain required work.
Existing M2, action-context and receipt bytes and runtime behavior are unchanged.

## Heartbeat node-signature validation — 2026-11-03

The root heartbeat handler rejects an empty or non-string selected node key and
requires successful node-signature verification before node state changes. This
closes a falsey-key path that skipped the body signature. Cached-key priority,
wire encodings and independent M2/client-certificate checks remain unchanged.
Local actual-crypto handler checks passed; full HTTP/ASGI and live qualification
remain required. This does not implement scoped node enrollment or the M2 client.

## SDK diagnostic runtime-denial propagation — 2026-11-03

The Phala diagnostic reader now preserves its private runtime-denial signal from
header and raw-reader accessors. Response cleanup still runs once; multi-provider
diagnostics stop after that denial. Ordinary accessor failures retain the bounded
provider_error report. This corrects custom-transport control flow; reports remain
non-authoritative and this supplies no authentic hardware/quote verification.

## Legacy GatewayClient process binding — 2026-11-03

The standalone legacy client now uses actual process runtime policy. Caller
policy/maps assert consistency and cannot override live or missing process mode.
The legacy server already refuses live startup; its old client now refuses live
construction too, before creating a session. Five operations recheck policy at
entry, before dispatch and before response/state adoption. Matching non-live
routes, payloads, timeouts and no-redirect behavior remain. A separately reviewed
M2-authenticated client and native/live qualification are still required.

## Neuron lifecycle policy checks and identity continuity — 2026-11-03

Neuron identity loading, key creation, telemetry signing, heartbeat dispatch,
workflow demo and run loop now recheck actual process policy and effective mock
selection. Runtime drift stops these paths instead of falling into retry or
fallback. Invalid/unreadable existing identity files reject without replacement;
first-time creation requires an absent file and exclusive creation. A failed or
partial creation is left for explicit recovery and never adopted automatically.
Local fixture checks exercise these boundaries; native filesystem, full workflow,
independent runner and live service qualification remain required.

## Neuron constructor process-policy binding — 2026-11-03

VamsNeuron now derives runtime authority from actual os.environ. Supplied policy
and complete environment maps must match it; they cannot mask live or missing
process mode. The actual policy and effective mock choice are rechecked directly
before storage initialization. Matching local/test/demo fixtures and their ordinary
configuration values remain available. The existing live-startup ban remains;
this is constructor containment, not qualification of later methods or effects.

## Legacy trust diagnostic body limits — 2026-11-03

Legacy TrustProvider calls now stream without redirects. Phala/Marlin and all
non-200 responses consume no body; Automata's chain-ID JSON uses a 65,536-byte
identity-only raw-body budget with reads requested at most8,192bytes. Exact EOF
is required; no eager JSON/content fallback or Content-Length trust. Any failed
pass discards its parsed observation after cleanup. These remain unverified
diagnostics, not provider/TEE evidence or full resource qualification.

## Legacy TrustManager simulation and proof boundary — 2026-11-03

The standalone Layer-4 manager/providers now bind their effective configuration to
the actual process runtime policy. Mock selection is a strict boolean governed by
the existing NEURON_MOCK_MODE flag; policy drift rejects and clears manager cache.
Local healthy fixtures remain available with explicit simulated/non-authoritative
provenance. Provider observations cannot certify capacity or TEE eligibility;
get_healthy_providers() intentionally returns no names. The Layer-4 CLI labels
these observations unverified. The parameterless fabricated Phala proof API now
rejects with authentic_verifier_unavailable. The separate SDK/plugin fixture and
live-startup blocks remain. Authentic verifier, native/full CI and operational
qualification are still required. See the repair ADR; readiness remains NOT READY.

## TEE target HTTP reachability probes — 2026-11-03

Engineering resource/privacy/claim correction; NOT READY. Phala, standalone Marlin and
Automata SDK health methods request streamed, no-redirect responses and inspect only
status. They do not read JSON/content/text/raw bodies or iterators. Each acquired response
gets one cleanup attempt before result adoption; a request failing before acquisition
has no returned response to close. Ordinary request/status/close errors are fixed
offline/provider_error output, without provider exception text or repr. Local control
events propagate after cleanup. Phala retains current actual-runtime checks and private
drift precedence over cleanup failures; the standalone clients gain no new policy claim.

Exact integer statuses100--599 are required before formatting. Phala/Marlin2xx means
healthy HTTP reachability;1xx/3xx/4xx/5xx is degraded. Automata retains its exact200 rule;
its JSON-RPC body is not interpreted. Redirect-dependent endpoints may now show degraded.
URLs, RPC request payload, timeouts, constructors and target technology descriptors are
preserved. latency_ms uses monotonic request-to-status time, excluding body and cleanup.
Every result adds verification_scope=http_reachability and
evidence_classification=non-authoritative; legacy result keys remain.

The actual Neuron SDK panel labels endpoint observations as unverified and the TEE
section as HTTP reachability only. Technology is a target description. Missing/mismatched
provenance produces unknown/unverified display rather than a green legacy status. Both
Celestia and TEE panel exception handlers use fixed messages; Bittensor's prior bounded
handler remains. No website status can admit work, establish capacity, certify an enclave,
authenticate a verifier/chain, or close a release gate. No guessed verifier endpoint or
stronger health protocol is introduced.

Caller-owned session defaults may still attach their own Authorization/cookies/proxy
configuration to public health endpoints. This repair does not inspect or strip those
settings and makes no general credential-isolation claim. SDK-owned Phala bearer scope
from source55 remains unchanged. Avoiding unused body consumption does not qualify HTTP
headers, DNS, socket/lower-layer buffering, deadlines, CPU or total peak memory. Real
Requests/urllib3, endpoint identity/redirect behavior, custody/privacy and operational
availability remain unqualified; existing package/native-runner gaps remain.

Synthetic tests exercise actual producers through check_all_tee_health into the extracted
actual Neuron panel with local transport and fake unrelated providers. They do not import
the full Neuron package or establish a deployed caller graph/independent observer. The
prior provider/wallet campaign must be rebound to the changed Neuron source; historical
passes alone do not cover this display. Legacy standalone SDK structure tests now use
local transports with their existing assertions unchanged. Full pytest/native CI remains
pending. Source56 diagnostic body limits/helpers, source54/55 policy/credential/report
controls, root/quorum/layout and all other Neuron behavior remain.

INV-1--INV-10 executable controls unchanged; authentic INV-6 qualification remains open.
Primary F12/F16,T04/T05/T23/T27/T33; native proof/provider/operational tracks retain full
criteria. Economic/48hgovernance/restricted-profile controls unchanged. Full A--G and BOTH
Polygon Amoy/Cardano Pre-Prod retained;13open/0of36verified,NOT READY. Actual tools,
verifier/hardware/fixed workload,DA/observer,custody/privacy/security,dual-chain rehearsals
and7closed/14public actual-day evidence remain required. No acquisition/provider contact/
real credentials/signing/funding/roles/deployment/R28/Slot08/Aiken action occurred.
Historical evidence retains its own exact source/time/scope and counts are not added.

## Legacy TEE diagnostic response-body budget — 2026-11-02

Engineering resource repair; NOT READY. SGX/Nitro diagnostic POSTs request a streamed,
identity-encoded response and disable redirects. Non-200 status, including redirects,
returns provider_status without reading the body. The consumer accepts at most65,536
raw body octets after transfer framing and before content decoding, using read requests
of at most8,192bytes with decode_content=False. It observes EOF before accepting an
exact-limit body and rejects the first over-limit byte without appending it. It does
not trust Content-Length or use response.json/content/text/iter_content as a fallback.
Nonidentity or malformed Content-Encoding is rejected before body reads. Bounded bytes
are decoded as strict UTF-8 and parsed only after EOF; prior response shape checks stay.

These fixed values are a local diagnostic compatibility restriction, not a provider,
hardware, quote or workload maximum. They do not qualify complete process peak memory,
HTTP headers, DNS, deadlines, CPU or lower-layer buffering. Quote inputs, non-live Phat
business outputs, public metadata and health calls retain their separate unresolved
resource requirements. Caller timeouts, real dependencies and provider behavior still
require native qualification; this guard supplies no authenticated verifier or trust.

Every acquired diagnostic response enters cleanup before the first post-return runtime
check, gets one close attempt before claim adoption, and is followed by a fresh runtime
check. Checks after reads precede buffer appends. Local control/cancellation is preserved
and propagates after cleanup; private runtime drift takes precedence over cleanup
failures. Close failure prevents claim adoption but does not prove connection release. Oversize/unsupported encoding
and malformed responses produce fixed bounded errors; provider details, body content,
URLs and credentials are not included. Source55 request-local credential scope and
caller-owned session defaults remain; source54 live-dispatch refusal, ambient policy,
report non-authority, plugin rejection, fixture root checks/quorum/layout are preserved.

Focused tests use synthetic raw-byte streams and local close/read counters. Existing
34test assertion bodies remain unchanged; response fixtures gained raw/header/close
interfaces. These fixtures are not Requests/urllib3/native HTTP or an independent
operational observer. Legacy full pytest/vendor runs remain pending. Design references:
https://requests.readthedocs.io/en/latest/user/advanced/#body-content-workflow
https://requests.readthedocs.io/en/latest/api/#requests.Response.raw
https://urllib3.readthedocs.io/en/stable/reference/urllib3.response.html
Documentation page versions are not installed-version or provenance evidence.

INV-1--INV-10 enforcement unchanged; authentic INV-6 acceptance remains unqualified.
Primary F06/F12/F16 and T04/T05/T23/T27/T33; related authentic proof/manual/formal tracks
retain all requirements. Economic/48hgovernance/restricted controls are unchanged.
Full A--G and BOTH Polygon Amoy/Cardano Pre-Prod retained;13open/0of36verified,NOT READY.
Native/authentic verifier, hardware, fixed workload, DA/observer, custody/privacy/security,
both-chain rehearsals and7closed/14public actual-day evidence remain required. No provider
contact, package acquisition, credentials, signing, funding, roles, deployment or reserved
R28/Slot08/Aiken use occurred. Historical results retain their original source/scope.

## Phala SDK credential request scope — 2026-11-02

Engineering credential-disclosure repair; NOT READY. The SDK no longer installs
its Phala API key on the shared HTTP session. It supplies a request-local Bearer
header only on the configured Phala SGX claim POST and permitted non-live Phat
contract POST. Marlin/Nitro POST, public metadata GET and health GET receive no
SDK-owned Phala credential. Reusing a transport across new client instances does
not overwrite either client's selected key. Non-secret content headers remain.
Both Phala POST routes disable redirects; a3xx response remains an explicit failed
provider result. This changes redirect-dependent compatibility and requires real
provider testing before qualification. No alternative provider or trust fallback.

Caller-owned transport defaults are left untouched. This repair does not certify
custom transports, pre-existing session credentials/cookies, netrc/proxies, endpoint
trust or the real HTTP library. Construct fresh clients/transports after updating;
old objects are not retroactively revoked or sanitized. Provider identities and
credential custody/handling still require reviewed operator/privacy evidence.
Never treat endpoint configuration or an API key as action authorization.

Source54 ambient policy/current-runtime checks, live/mock direct-dispatch refusal,
RPC report non-authority, plugin fail-closed behavior, root/session fixture checks
and exact quorum remain. New tests model session/request header merging using
synthetic tokens and local transports; they observe the explicit redirect option,
not a live server or real redirect-chain behavior. Full vendor/pytest/native gates,
authentic verifier/hardware/workload and current action binding remain unqualified.
Response/input resource limits are a separate unresolved requirement; no provider
size or latency bound is invented by this credential fix.

INV-1--INV-10 controls are unchanged; INV-6 authentic qualification remains open.
F06/F12/F16 and privacy/security tracks require their full existing acceptance.
All economic and48-hour governance/restricted-profile controls remain. Full A--G
and BOTH Polygon Amoy/Cardano Pre-Prod retained;13open/0of36verified, NOT READY.
No real credential, provider contact, acquisition, R28/Slot08/Aiken, signing,
funding, role or deployment action occurred. Earlier evidence retains its original
source/time/scope and is not added to new test counts.

## Legacy Python TEE authentication and action boundary — 2026-11-02

Engineering containment repair; NOT READY. `PhalaTEE.call_phat_contract` and
`execute_python_in_enclave` reject live modes before protected argument reads,
serialization or dispatch. A runtime address and API key do not authorize an
action. Direct mock contract calls also reject without HTTP. Explicit local
script simulation and non-live real-transport compatibility remain non-authoritative.
The old ECDH/confidentiality description is withdrawn: this client implements no
such protocol. An actual application caller for these methods remains unestablished.

Actual process `os.environ` supplies mode and registered mock policy. A supplied
policy/configuration mapping must match it. Supplied `environ` maps deliberately
require valid `VAMS_ENV` and the same enabled registered mock flags; partial
endpoint-only maps reject (use typed endpoint arguments or actual environment).
This is a documented legacy constructor compatibility restriction. Neither can grant local authority to
a live process, and explicit mock selection must match the ambient flag. Effective
policy/mock references are immutable. Fresh checks precede inputs, transport and
result adoption. Checks can reject subsequent work but cannot undo a prior locally
permitted effect or provide atomic fencing against concurrent environment changes.

Legacy SGX/Nitro RPC responses never establish validity or live evidence, even
with HTTP200, `valid:true`, matching root/report data and measurements. A parsed
Boolean is exposed separately as `provider_claim_valid`; malformed/missing binding
fields remain malformed. `usable_as_live_evidence` is always false for this report
protocol, including caller-created objects. Non-mock `TEEProofPlugin` generation
returns invalid/empty rejected output before quote/client/ABI callbacks; verification
returns false before proof inspection. An injected client's claimed trust cannot
authorize it. Local fixtures preserve proof type/layout, SHA3 binding and root-EOA/
session-key checks; their validity remains simulation only. The legacy multi-TEE
helper requires exact integer threshold2 and cannot promote real provider claims.
This does not change the separate Automata DCAP plus EZKL-first backend decision.

Focused SDK/plugin/collector tests use explicit local transports and vendor-symbol,
Keccak and versioned encoding fixtures. They are not native EVM ABI/Keccak, authentic
quotes, hardware, signatures, or independent operational observations. Legacy tests
now select actual ambient fixture policy and reject fabricated live reports. Full
pytest/vendor imports and the frozen native workflow remain pending. The scanner's
TEE oracle must reject unsafe variants; no unrelated guards or workflow are relaxed.

INV-6 is affected: unauthenticated root acceptance is removed, but authentic current
root/action/workload verification still requires qualification. INV-1--5/7--10 and
all economic,48-hour governance and restricted activation controls are unchanged.
F06/F07/F12/F16; T04/T05/T10/T11/T15/T23/T27/T33 remain subject to their full criteria.
Qualified Automata hardware/verifier/collateral/TCB, fixed ONNX/EZKL model/VK, native
bridge, DA/observer, approved runner, custody and human privacy/security manifests
remain UNKNOWN. No fallback, provider contact, credential/signing/funding/deployment,
acquisition or R28/Slot08/Aiken action is authorized by this source repair. Preserve
full A--G and BOTH Polygon Amoy/Cardano Pre-Prod,13open/0of36verified,7actual closed
and14public observation days. Historical evidence retains its original source/scope.

## Named Bittensor wallet setup boundary — 2026-11-02

Engineering containment repair; NOT READY. The constructor binds its optional
wallet name/hotkey selection. When the SDK is available, named-wallet setup rejects
live mode before provider or wallet construction; missing/invalid mode fails through
central policy. Direct _init_subtensor calls use the same boundary. Selection and
effective runtime configuration are checked again before wallet creation and before
adopting its returned object. Setup rejects selector drift; assigning public
fields alone is not a supported identity reconfiguration. Health reports the bound
adopted-wallet label or none, not a changed public label. Construct a new client
for another explicit selection.

No-wallet read-only setup is preserved and cannot promote a callback-injected wallet
name into wallet creation. The unavailable-SDK constructor remains harmless and
constructs no wallet. Controlled test/local/demo setup retains explicit selection
and existing hotkey behavior. Prior wallet references are not implicitly cleared or
revoked. Only the method-private bounded drift rejection escapes the provider catch;
provider public safety/configuration errors retain fixed-warning/disconnected results.
The source52 inference guard is unchanged; the health wallet label is corrected.

Local82cases PASS:11new wallet-boundary cases +71prior INCLUDED. Final before
control82tests/24failedsubcases/0errors retained separately. Actual constructors,
setup/query methods and existing SDK/Sentinel behavior use local vendor/provider/
account/DA/challenge collaborators.0network/process/uncontrolleddependency events;
56AF_UNIX event-loop sockets counted separately. A callback may already construct
a locally permitted wallet object before a later check rejects adoption; tests
record that event instead of claiming it never occurred. These process reads do
not provide atomic fencing against concurrent environment changes.

Source demonstrates a wallet factory call, not whether the real vendor eagerly or
lazily reads key material. No real key, signature, vendor wallet/provider operation,
custody or authentic action approval was exercised. Full vendor imports, approved
independent Linux312/full CI and authentic inference remain required. No new ambient
secret load, signing backend, operator or trust fallback was added. The existing
research mapping remains source52 evidence, not a reproduced security guarantee.

F12/F16 primary; T04/T05/T23/T27/T33. INV-1--INV-10 enforcement unchanged; no economic,
session, proof-root or bridge-control change. Full A--G/BOTH Polygon Amoy and Cardano
Pre-Prod retained:13open/0of36verified,0stagepromotions/actualdays. UNKNOWN native/
provider/observer/workload/custody/privacy/security inputs and all R28/Slot08/Aiken,
acquisition/service/signing/funding/deployment limits remain. Earlier entries retain
their original source/time scope; local passes do not establish release acceptance.

## Direct inference admission boundary — 2026-11-02

Engineering containment repair; NOT READY. Bittensor query_miner now rejects live
modes before time, prompt, wallet, metagraph or transport access. Missing/invalid
modes fail centrally. This corrects the earlier retained-connected-inference
description for the unbound public entrypoint: observations remain read-only, but
live inference needs an authenticated action-bound backend and qualifying workload.
No actual application caller was established by the manifest-covered text inventory.
The public compatibility method cannot accept caller ALLOW metadata as authority.

Controlled test/local/demo behavior remains. Effective runtime configuration is
rechecked before dendrite creation, Synapse prompt release and query dispatch.
A changed configuration stops the next stage; prior locally permitted activity
cannot be undone. Only the method-private bounded drift error escapes the provider
catch. A provider raising public safety/configuration errors retains a bounded
failed InferenceResult. Method signature and read-only methods are unchanged.
This checks runtime configuration, not authenticated governed policy epochs.

Local71cases PASS:10new direct-route/drift cases plus61prior cases INCLUDED.
Final before control71tests/24subcase failures/0errors is retained. Earlier69-case
controls retain their own source/test identities; the initial four harness errors
were missing adjacent unchanged Neuron source, supplied without weakening tests.
Actual SDK/Sentinel classes and extracted Neuron health use controlled vendor,
account/provider/DA/challenge collaborators.0network/process/uncontrolled-dependency
events;56AF_UNIX event-loop sockets counted separately. Local effect counters prove
the denied-entry boundary, not independent operational observation or real inference.
Full SDK imports/pytest, approved independent Linux312/native gates remain pending.

The research decision is recorded once in repair_20261027/
research-inference-policy-20261102.md. It adopts control placement, not a paper's
guarantees or a completed capability interpreter. Common action codecs and local
object protocols are not repurposed as inference authority. Authentic fixed ONNX/
EZKL, provider/admission/current-policy, protected effects, receipts/recovery and
settlement remain required, with no automatic trust fallback or milestone exclusion.

F12/F16 primary; F06/F07/F13 authentic proof/action acceptance remains open.
T04/T05/T23/T27/T33;INV-1--INV-10 enforcement unchanged. Full A--G and BOTH Polygon
Amoy/Cardano Pre-Prod retained:13open/0of36verified, no stage promotion or real days.
All provider/custody/privacy/assurance UNKNOWN inputs and R28/Slot08/Aiken,
acquisition/service/signing/funding/deployment limits remain. Earlier entries retain
their original source/time scope and are not fresh release acceptance.

## Sentinel selected-account identity repair — 2026-11-02

Engineering source; NOT READY. HardwareRegistryClient initializes its selected
account to None and exposes a read-only account_address. A local Sentinel supplied
with signing material uses that selected account address for operator_address and
report sentinelId; it never uses Web3's unrelated default account. Missing, malformed
or zero identity fails explicitly before DA/challenge construction. No supplied
material retains the existing zero placeholder without reading account_address.
Live Sentinel construction still rejects before registry/provider setup. SLA
submission remains unavailable and a requested SLA still makes audit_node false.

This corrects the former registry.web3 attribute mismatch without creating a signer
fallback, setting a default account or authenticating ownership/custody. An address
parsed by a local package does not prove provider, operator or governance identity.
The SDK account_address is None when parsing/configuration is unavailable; Sentinel
does not turn that absence into a different account. Existing contract/read and
local-publication interfaces remain; no wire/signature/proof version changes.

Local61cases PASS:9new selected-identity cases,19existing Sentinel publication cases
and33provider/research cases INCLUDED. Before control61cases had13errors at the
missing property/interface paths; preserved separately. Actual SDK/Sentinel classes
use controlled vendor, account, DA and challenge collaborators. Network/process and
uncontrolled dependency construction events are zero;56local AF_UNIX event-loop
wakeup sockets are separately counted. No real account parsing, credential, signature,
provider/DA publication, native chain, full runtime import or custody proof occurred.
The hash helper remains a fixed lookup and full required pytest/CI remains pending.

F09/F12/F16 and T04/T05/T23/T27/T33 retain acceptance limits; real operator identity,
proof/effect/settlement and privacy assurance remain required. INV-1--INV-10 controls,
restricted disablements and full A--G/BOTH Polygon Amoy and Cardano Pre-Prod scope
remain unchanged.13open/0of36verified, no gate promotion or observation days.
All acquisition/service/signing/funding/deployment/R28/Slot08/Aiken limits remain.
Earlier source/evidence entries retain original time and scope.

## Provider fallback and plugin diagnostics repair — 2026-11-02

Engineering source; NOT READY. Disconnected or failed Bittensor subnet/miner reads
and the offline hardware catalogue authorize their fixture producers through the
central runtime policy. Staging/testnet/production and missing/unknown modes reject
instead of returning fabricated capacity. Local/test/demo fixtures remain available
and carry simulated=true/non-authoritative provenance in records, dictionaries and
hardware summaries. Connected reads remain provider observations, not verified proof.

Hardware fixture IDs now use the same Keccak helper as the SDK's on-chain lookup;
SHA3-256 is not a substitute. The eleven class names match HardwareClasses.sol.
Collateral conversion uses integer multiplication by 10**18 with unchanged nominal
amounts. Display floats remain display-only. No registry terms, fees, rewards,
settlement, supply, staking or custody behavior changes in this slice.

Bittensor health now reports a failed block read as degraded rather than healthy
with zero. The compatibility get_block_number() zero-on-error behavior remains.
The actual Neuron health panel requests counts only after healthy status and labels
them as a simulation or an unverified provider observation. Bittensor caught-error
diagnostics are fixed text. The plugin collector's failure handler neither formats
the exception nor invokes a failed plugin's name callback, and continues collection.
Successful result/proof/metadata and plugin collection/submission separation remain.

Fresh local33tests PASS,0fail/error/skip/network/process:18provider/caller cases plus
15research/trust cases (the prior13 INCLUDED). Before control33tests produced
51subcase failures and1error for the targeted defects; retained separately. Actual
SDK methods and the extracted actual Neuron health method use controlled provider
and vendor symbols. Native Cast produced11class vectors plus the known empty-hash
control in13offline calls; the SDK test uses those fixed values as an explicit
eth_utils symbol fixture. This is not actual eth_utils/Web3/Bittensor import/ABI,
provider/chain/finality qualification, native runner acceptance or full pytest/CI.

Connected inference dispatch is preserved. Protected effects still require
authenticated admission under policy, provider cooperation and valid receipts.
This local campaign establishes no live execution or deployment qualification.
Human review, privacy acceptance and the outstanding external qualification inputs
remain required.

Primary F09/F16 containment/privacy repairs; F12 actual admission/effect evidence
remains open. T04/T05/T23/T27/T33 retain their required qualification boundaries.
INV-1--INV-10 controls unchanged; INV-6 root identity and INV-10 proof/payload
separation remain required. Full A--G/Polygon Amoy AND Cardano Pre-Prod retained:
13open/0of36verified. R28/Slot08/Aiken, acquisition, services, signing, funding and
deployment limits unchanged. Earlier entries retain original source/time scope.

## Research fixtures and unavailable trust submission — 2026-11-02

Integrated engineering source; NOT READY. Parallel search and fixture serialization
now authorize mock use through the central runtime policy at method entry. The
legacy collector has the same outer guard, so its placeholder SGX/identity bytes
cannot escape in staging/testnet/production. Missing/unknown runtime modes reject.
The separate plugin collection method is unchanged; no constructor-wide ban added.

Local result metadata identifies simulation, non-authoritative evidence and the
fixed confidence as fixture-only. The new local envelope discriminator is
vams.parallel-research-simulation.v1; its result_count/fixture_digest/created_at
fields describe a fixture. Old unversioned JSON is not reinterpreted as this
format or as a signed proof/receipt. Raw query text is no longer printed.

Both public submission stubs now raise bounded unavailable failures instead of
printing completion. Existing ZKML and non-authoritative TEE denials remain; all
remaining bundles also reject before signer/RPC/transaction activity. The collection
constructor no longer reads VAMS_PRIVATE_KEY or creates an ambient signer/account;
legacy attributes remain None. Provider-specific initialization remains separate.
An authentic typed action/actor-root-bound backend and finality receipt are still
unimplemented/unqualified; no signer or trust-model fallback was introduced.

Final13focused cases PASS/0fail/error/skip/network/process. They execute actual
client code with explicit vendor/Web3/Phala/plugin symbol fixtures; neither full
vendor imports nor authentic proofs, real provider initialization or transactions
were exercised. Constructor tests use vendor fixtures and an ambient-key-read
tripwire, not actual credentials. Before control13tests/44subcase failures/12errors
is retained; prototype12-case results retain their own source/test identities.
Existing full SDK pytest and actual provider/chain/custody qualification remain.

F09/F12/F16 and T04/T05/T23/T27/T33 trace this SDK/evidence repair; F06/F07/F13
authentic proof/action-binding acceptance remains open. INV-1--INV-10 underlying
controls unchanged, including INV-6 root identity and INV-10 proof/payload separation.
Full A--G/Polygon Amoy AND Cardano Pre-Prod retained:13open/0of36verified.
No custody/provider/privacy/assurance, native runner or readiness gate is cleared.
R28/Slot08/Aiken/acquisition/services/signing/funding/deployment limits unchanged.
Earlier entries retain their original source/time and evidence scope.

## Gateway revocation and SDK error boundaries — 2026-11-02

Integrated engineering source; NOT READY. Gateway replay decisions now use the
maximum of request time, wall time and the durable clock watermark inside the
existing write transaction. Tolerated clock rollback cannot undo an effective
signer revocation or extend expiry. Excess rollback and malformed stored time
still fail closed. Scheduled revocation, skew/retention limits, schema, namespace,
wire format and custody policy are unchanged. Connections explicitly close after
their existing transaction context and if connection setup fails.

The X402 retry and outer interrupt exception boundaries emit fixed safe failure
text. Arbitrary exception/failed-result detail is not logged or returned there;
known local expiry/dispute text, retry/status behavior and successful business
result/proof/provider/cost fields are preserved. Live X402 remains disabled.

Non-author source reviews accept both repairs with limits. Focused local checks:
5SDK cases and7gateway cases PASS, separately bound and not added to historical
counts. Gateway checks use real local WindowsSQLite/signature/auth code with a
synthetic Request/FastAPI import symbols; SDK uses synthetic MMU/provider objects.
These do not qualify full ASGI/ingress, Linux, PostgreSQL, provider effects, log
destinations or privacy approval. Required full gates remain outstanding.

INV-1--INV-10 underlying controls and restricted disablements remain; no economic
activation, new role, service restart, signing/funding or deployment occurred.
Privacy inventory remains unapproved, including pending wider SDK field/sink
review. Cardano upper-bound-v1 timing is already integrated source; native/ledger
qualification is still missing, not a newly unresolved source decision.
Full A--G/Polygon Amoy AND Cardano Pre-Prod retained:13open/0of36verified.
Earlier entries retain their original source/time and evidence scope.

## PG5 replication-role source correction — 2026-11-02

Integrated as inactive/unqualified engineering source; NOT READY. Both the
runtime full-schema guard and explicit migration preflight require the selected
runtime and migration principals to have NOREPLICATION, alongside their prior
forbidden elevated attributes. Missing/malformed values reject as bounded errors.
The shared membership guard preserves denial of all runtime memberships and
rejects a replication-capable role anywhere in either principal's conservative
membership traversal. It does not rely on rolinherit or grant-option assumptions.
No role, grant, table, DDL, live factory or migration was created or altered.

The privilege profile explicitly binds forbidden attributes and migration-role
replication membership denial into MIGRATION5. Prior META/CHECK manifests reject
under the changed profile; no old schema/receipt/state adoption is performed.
The source46 snapshot/session protocol, TLS, role/schema/owner/key/CHECK/ACL/FK/
trigger/RLS controls and bounded UNKNOWN/no retry remain intact. V3/V4 unchanged.

Final combined110local fixture tests PASS/0fail/error/skip/network/process, with
98prior checks INCLUDED. Same-test before control110tests/41subtest failures/
4errors; the errors are old malformed-membership IndexErrors, preserved as
failure evidence. Original108/27failure and108PASS campaigns retain their
earlier test/source identities. Controlled catalogs/driver doubles are not real
PG18 role graphs, replication exposure, MVCC, native integration or qualification.

Actual runtime/migration role and membership manifests, HBA/replication/publication/
slot/cluster configuration, session affinity, server/driver/CA identities and
approved PG18 role mutation/concurrency/restart/WAL/restore campaigns remain
UNKNOWN/unqualified. Source review cannot prove what privileges exist on a host.
No authentic funding/proof/provider/custody/privacy/assurance or readiness gate
is cleared. Full A--G/Polygon Amoy AND Cardano Pre-Prod retained;13open/0of36
verified. R28/Slot08/Aiken/acquisition/service/signing/funding/deployment limits
unchanged. Earlier entries retain original source/time and evidence scope.

## PG5 snapshot-order source correction — 2026-11-02

Integrated as inactive/unqualified engineering source; NOT READY. Runtime schema
verification acquires all eight fixed SUE relation locks before its first SELECT,
including role-only queries. Migration uses a dedicated direct connection and
autocommit session serialization; the blocking lock statement's snapshot ends
before fresh inspection and a new protected SERIALIZABLE transaction.

Existing schemas lock before transactional PID/role/catalog reads. Empty schemas
validate the principal/backend and create all eight tables atomically without
IF NOT EXISTS or partial adoption; own DDL remains visible, and collisions reject.
Backend identity is checked after the wait and before commit. The session lock
spans commit and is released only by closing that dedicated connection. Timeout,
commit or close uncertainty produces bounded UNKNOWN/no retry. No grants, table
lock strength, protected isolation or role/schema controls were weakened.

MIGRATION5 now binds this versioned session/snapshot protocol. An old META profile
rejects rather than being silently adopted. Preserve old schemas, data, encodings,
receipts and source evidence; any actual state migration requires its own reviewed
protocol. This source change executes no database migration or privilege change.

Runtime before-control:86tests/1failure. Migration before-control:94tests/5failures.
Final combined local checks:98PASS/0fail/error/skip/IO (prior86/85 INCLUDED).
These use controlled driver/cursor doubles, not PostgreSQL MVCC or a live race.
Non-author review accepts the named source repair only. Original owner-authorized
findings/reports remain unchanged, with their historical source bindings.

PID equality cannot prove a direct dedicated session or rule out a proxy/pool.
Actual approved PG18 two-session runtime-DDL and fresh/existing migration tests,
correct changed-control rejection/post-lock visibility, session affinity, role/
schema/query-plan/contention/restart/WAL/UNKNOWN behavior and privacy acceptance
remain unqualified. Server/driver/CA/operator/role manifests remain UNKNOWN. The
replication-role profile follow-up remains separate; no extra privileges granted.
No native funding/provider/proof/custody/assurance or readiness gate is cleared.
Full A--G scope for Polygon Amoy AND Cardano Pre-Prod is retained,13open findings/
0of36verified. Live constructors, factory/route/startup exclusions and existing
R28/Slot08/Aiken/acquisition/service/signing/funding/deployment limits remain.
Earlier snapshot-open entries below retain their original source/time scope.

## Current engineering source integration — 2026-11-02

Integrated engineering component: inactive and unqualified; NOT READY.
The integration journal and current source manifest identify this exact source
and the post-integration combined checks. No live factory, route registration,
database migration, chain deployment, role grant, funding or operator approval is
created by source integration. V5 runtime constructors continue to reject live
mode, and existing local V3/V4 protocols and deployed instances are untouched.

Component evidence:930local Solidity tests/58suites and85supplemental Windows312
signature/catalog/transaction-double checks; earlier927/69 are INCLUDED, not added.
Native retry policy version/root floors, bounded256attempt lifecycle and indexed
closure/budget projection are repaired locally. Fresh immutable settlement/verifier
instances together are required for the extended internal/getter ABI; signed V3
wire and logical-work/attempt domains are unchanged. No old-state adoption.

Authentic current-host/native funding-finality, native-gated same-ID successors/
renewal, paid coordinator AND direct-provider effects, actual PG18/query plans/
roles/concurrency/restart/WAL, proof/provider/DA/custody/privacy/human assurance,
both-chain rehearsals and actual observation days remain unresolved. Local terminal
states are not native financial resolution. All A--G scope for Polygon Amoy AND
Cardano Pre-Prod is retained,13findings open/0of36verified; no stage promotion.
Historical entries below retain their original source/time and pre-integration
labels. Current source integration supersedes those old integration labels only.

## 2026-11-02 - Preserve acknowledged policy across native object retries

The native candidate now persists the policy version/root acknowledged during
fenced absence. A same-operation retry must preserve that floor: no lower version,
and no changed root at an equal version. Current governed policy, actor consent,
strict epoch/fence advance and immutable logical work still independently apply.
AdmissionFacts carries the exact proposal policy fields from the stateless verifier.
This matches the retained Python successor rule; an issuer cannot drop an
acknowledged future policy merely because on-chain epoch advanced independently.

Two actual-policy VM regressions fail before repair by accepting incompatible
retries. The repaired full campaign passes930tests/58suites,0fail/skip (prior927
INCLUDED); a positive equal-version/same-root retry passes. Offline sizes PASS:
ComposedSettlement23689bytes,ActionDeliveryVerifierV118126bytes under unchanged
24576EIP-170limit. Exact commands/source/tool bindings and raw outputs:
LATE-44-RETRY-POLICY-BEFORE-01.json,LATE-44-FULL-05.json,LATE-44-SIZES-08.json.
Non-author source/result review accepts this named local defect repair only.

ObjectOperationV3 getter and internal AdmissionFacts return layouts are extended.
Deploy a fresh immutable settlement/verifier pair together with newly bound code/
ABI identities; no old-state upgrade/adoption or existing deployed ABI compatibility
is claimed. Signed V3 receipt bytes/domains, native attempt/logical-work digests,
integer registry fees, original actor/payee, backing and terminal semantics remain.
No new native funding/finality, physical storage truth, provider custody or live
authorization follows. The85local Python lifecycle checks retain their unchanged
R9 source scope. Current source remains unintegrated and NOT READY; all A--G scope
for Polygon Amoy AND Cardano Pre-Prod is retained,13open findings/0of36verified.
Earlier entries below retain original source/time scopes and historical counts.

## 2026-11-02 - Local authority5 lifecycle candidate

Source45/R9 now implements fresh scope installation, exact provider-acknowledged
activation, policy revalidation, cutover/refresh, acknowledged revocation and
same-host renewal. Each closure authenticates every bounded current-generation
attempt history and its exact cumulative budget projection. Renewal preserves
spent budget and all prior work/attempt/event/completion records.

The source supports at most256attempts per generation, including zero-cost work;
later generations retain the logical-work mission and cumulative spend. The new
required UNIQUE(scope_id,generation_id,operation_id,attempt_id) index supplies the
capacity-query prefix and closure ordering. Exact catalog enforcement and revised
MIGRATION5 bind that access path and the limit. Eight table/column sets and signed
V3 receipt bytes remain unchanged. Existing candidate manifests are not adopted.
Actual PG18 schema/role/query-plan/contention/performance/restart/WAL qualification
and independently compiled CHECK provenance remain UNKNOWN/unqualified.

85supplemental local Windows312 signature/catalog/transaction-double tests PASS,
0fail/error/skip and0network/process events (prior69 INCLUDED). Exact source,
commands, failed iterations, raw streams and snapshots: FUNDED-ATTEMPTS-45-19.json
and LIFECYCLE-SOURCE-REVIEW-45-R9.json in the retained implementation workspace.
Independent source review accepts local preparation only. Solidity bytes remain
those of the927-test/58-suite VM candidate; no new native test count is inferred.

Local revoked/absent/completed states do NOT establish native funding or financial
resolution. Native-funding-gated renewal/same-ID successor admission, actual paid
coordinator AND every direct-provider effect route, authentic current host policy,
native finality, migrations and settlement remain unfinished/unqualified. These
classes cannot run in live mode. No production effects, payment/refund, scope
custody, dual-chain operations or real observation days are established here.
Full A--G scope for Polygon Amoy AND Cardano Pre-Prod is retained; NOT READY,
unintegrated,13open findings and0of36verified. No R28/Slot08/Aiken/acquisition/
service/signing/funding/deployment authority changes. Earlier entries below keep
their original source/time evidence scope; R7 lifecycle-pending descriptions are
superseded by this local component, without clearing their native/backend gaps.

## 2026-11-02 - Prepare funded object reservation and durable attempt history

Implement admitted-fund reservation until authenticated completion or acknowledged
fenced absence. Exact signed receipts preserve original root/payee/workload terms;
policy versions cannot regress or rebind roots at the same version. Native attempts
append exact predecessor/work links; completion is permanently terminal.

Fresh storage5 keeps scope, work, attempt, event, completion and settlement records
distinct. Initial local reservation atomically persists immutable facts and budget
debit before returning an admission; unknown funding is lookup-only. Historical
completion remains recordable if local funding observation is missing. A closed
old generation cannot spend a successor's reservations. Native money/finality and
provider effects are not inferred from local budget facts or signatures.

Current candidate:927Solidity tests/58suites PASS,0fail/skip (900prior INCLUDED),
offline size gate PASS:ComposedSettlement23,429bytes,ActionDeliveryVerifierV1
18,067bytes under unchanged24576EIP-170limit. Bindings/raw streams:
LATE-44-FULL-04.json and LATE-44-SIZES-07.json in the retained source44 workspace.
Source45:69supplemental Windows3.12 tests PASS,0fail/error/skip, catalog and
transaction doubles with actual public-fixture signature verification; zero
network/process events. Not independent Linux3.12 or real PostgreSQL evidence.
FUNDED-ATTEMPTS-45-11.json / FUNDED-SOURCE-REVIEW-45-R7.json bind exact source.

Source preparation only; NOT integrated, deployed, activated or accepted.
Canonical43 remains 6,735 paths / manifest5a56888dc13d6b0b254c6e8aa9be6f0dbb26a7b55b9f3d75796c974c59e84759.
Full A--G / Polygon Amoy AND Cardano Pre-Prod remains NOT READY;13findings open,
0of36tracks verified. Existing profile,48hgovernance, INV1--10 and restricted
economic disablements remain. Local fixtures are not authentic/live assurance.

Still implement scope5 installation/renewal/cutover and native-resolved successor
admission, paid coordinator and direct-provider enforcement, and authentic host/
native funding-finality backends. Qualify real PG18 schema/roles/locking/concurrency/
restart/WAL; provider effects and retention; all required CI/scans, authentic DCAP/
EZKL/bridge and DA independent retrieval. Custody, observers, providers, approved
runners and independent privacy/security assurance remain UNKNOWN/unqualified.
R28/Slot08/Aiken/acquisition/service/deployment authority is unchanged. Source44/45
integration remains held for the linked runtime repair and combined checks.

## 2026-11-01 - Prepare local memory failure/privacy repair

Remove stable IDs/paths/hash prefixes/raw errors from S-MMU diagnostics. Local L3
pages use file-fsync+atomic replacement; failed persistence rejects before cache
publication/HIPIF trace deletion.19local testsPASS, including inventory hash/anchor
checks; no remote/power-loss/fullpytest qualification. Update existing unapproved
privacy inventory with S-MMU/calldata flows;21otherSDK modules remain pending.
Record user-selected admitted-fund hold until authenticated resolution as required
future settlement behavior, not implemented. Full A--G/both chains stay open. See
repair_20261101/MEMORY-BOUNDARY-AND-PRIVACY.md.

## 2026-11-01 - Prepare disabled-yield signing boundary

YieldManager's unsupported deployment/withdrawal methods reject before fund or
signer access in every mode; fabricated transaction hashes are retired. Read-only
query behavior remains, without an authenticated custody claim.6local controlled
testsPASS; existing2pytest fake-hash tests now require denial/zero calls but full
pytest remainsNOT_RUN. Real yield stays disabled; no recovery route is implemented.
Review/integration/freshchecks remain separate; full A--G/both-chain readiness stays
open. See repair_20261101/YIELD-DISABLED-BOUNDARY.md.

## 2026-11-01 - Prepare selected-profile configuration contract

Bind all selected profile1.0.0 keys/types/values through one pure validator reused
by audit and direct economic/campaign consumers. Reject altered restrictions before
snapshot/RNG/hash work; preserve current profile bytes and concentration boundary
operators.96local synthetic testsPASS(76existing INCLUDED). Alternate stricter
profiles require reviewed versioning; this is config identity, not deployed control
or live ownership evidence. Review/integration/fresh checks remain separately
required. Full A--G/both-chain readiness unchanged. See
repair_20261101/RESTRICTED-PROFILE-CONTRACT.md.

## 2026-11-01 - Prepare explicit Composer simulation boundary

Require explicit current non-live simulation in Composer/ServiceBlockClient;
Gateway opts in only for demo. Plans report SIMULATED/non-authoritative, never
provider activation or settlement. Catalogue/macro routes and runtime drift fail
closed; local inspection/removal and simulation counters stay separate. Actual
allocator assignments reach non-transaction-ready quotes.47local SDK/handler-body
unitsPASS, including22existing declaration/version checks; full ASGI/pytest,
independentLinux3.12 and authenticated registry/provider/receipt paths remain open.
This prepared bundle requires non-author review, guarded integration/fresh checks;
F12/F15 and both-chain A--G readiness remain open. See
repair_20261101/COMPOSER-SIMULATION-BOUNDARY.md and qualification checklist.

## 2026-11-01 - Prepare closed-canary time-contract enforcement

Require existing schema/version/start/end fields and integer day counts in the
public-stage report consumer. Reject missing/short/future intervals and inflated
counts with exact fractional-time comparisons; preserve required/extra boolean
drill semantics.66source-only testsPASS, including45existing audit regressions.
Synthetic timestamps supply no actual days or signatures. This prepared bundle
requires reviewed integration/fresh checks; full A--G/both-chain gates stay open.
See repair_20261101/CANARY-TIME-CONTRACT.md and actual qualification checklist.

## 2026-11-01 - Prepare current DCAP backend metadata checks

Revalidate the pinned SGX quote-version/collateral-router link on each proof,
rejecting mismatched/reverting/malformed getter data with bounded return copying.
15focused native VM testsPASS (8new+7existing INCLUDED), using fabricated backend
reports and VM root signatures. Authentic DCAP/collateral/TCB/hardware qualification
is stillUNKNOWN. This prepared source needs reviewed integration and full combined
Solidity/sizes checks; no gate promotion or deployed upgrade. See DCAP binding note.

## 2026-11-01 - Prepare truthful Sentinel publication and continuity

Reject unavailable SLA submission before SDK/signing/broadcast; return explicit
failure for requested/partial chain stages. Preserve explicit boolean local DA
publication when no SLA stage is requested, and reject runtime/mock drift around
probe/publication/scheduler work.19controlled-import testsPASS; authentic hardware/
DA/chain/old12pytest/fullCI remain unqualified. Correct README/anchor wording.
This prepared bundle requires guarded integration and fresh combined-source checks;
no finding/track promotion. See repair_20261101/SENTINEL-PUBLICATION-BOUNDARY.md.

## 2026-11-01 - Prepare typed object-policy call interoperability

Add a typed local calldata producer for the existing object/scope policy views;
configured runtime verifiers supply issuer IDs.26local Python checks pass;
offline native VM checks match6full call bytes and9digests across languages.
No policy reader/RPC response consumer, live route, signing or contract logic is
added. Dummy consent is not authority. Existing wire/schema/economic/48h controls
stay. This is a prepared reviewed-integration candidate; canonical checks follow
the guarded journal. Full native/authentic/operator/privacy/CI/both-chain gates
remain open. See repair_20261101/OBJECT-POLICY-CALLS-V1.md and checkpoint36evidence.

## 2026-11-01 - Deny unqualified live session credentials

- Gate session-key creation before inputs/key operations/cache-release; reject
  live or invalid runtime and unqualified manager parents. Cached local scopes
  cannot authorize live use. Keep local 24-hour/expiry/whitelist behavior.
-174unchanged local Linux3.14 session tests pass with real pre-existing Requests
  imports and non-signing Account fixtures. Three socket audit events were blocked;
  no independent3.12/fullCI, genuine Account, live wallet or readiness claim.
- Preserve failed Windows evidence and separately integrated persistence repairs.
  Non-author source/result review accepts guarded local integration only; fresh
  canonical-copy checks remain required after integration.
- Clarify local SDK usage and registry-snapshotted builder fees in the guide.
## 2026-10-31 - Require effect-store table behavior prerequisites

- Reject RLS, user triggers and rewrite rules before protected bodies.
- Strengthen table locks to conflict with trigger creation; guarded transactions
  sharing a table serialize. Native permissions/contention/DDL races remain pending.
- Bind internal triggers to all6migration-declared foreign keys and exact RI checks;
  reject unexpected incoming/outgoing references and altered referential actions.
-194selected local controlled-response tests pass (previous184 INCLUDED); no native
  PostgreSQL or readiness acceptance. Non-author review accepts local source
  integration only; combined-source checks remain required after integration.
- Preserve DDL, storage/wire versions, UNKNOWN recovery and live restrictions.
## 2026-10-31 - Bound effect-store driver error disclosure

- Replace raw database-driver failures with a bounded stage and UNKNOWN outcome
  at connection/transaction boundaries; omit backend details from ordinary errors.
- Preserve indeterminate recovery, operation identity, no retries/refunds, domain
  errors and interrupts. DDL, storage/wire versions and live restrictions stay.
-177selected local runtime tests and6source-inventory parser tests pass. Privacy
 214slots remain unreviewed; native PostgreSQL and independent qualification pending.

## 2026-10-31 - Require effect-store uniqueness before transaction entry

- Inspect required primary/unique keys and usable indexes in V3provider/authority
  and storage4authority instead of relying on migration metadata alone.
- Reject unavailable or incompatible catalog/lock responses before transaction
  bodies; preserve DDL, storage/wire versions and historical recovery semantics.
-166selected local fixture tests pass. Native PostgreSQL/DDL-race/concurrency and
  current host-policy qualification remain pending; live candidates stay blocked.

## 2026-10-31 - Prepare remaining Cardano governance acceptance definitions

- Define proposed timing, datum, destination and resource probes for26remaining
  parent labels while preserving the frozen81records and production validators.
- Add435source cases with valid caller, construction and resource controls;
 724prepared native cases remain uncompiled/NOT_RUN. Eight local model tests pass.
- Preserve48hours, custody and disabled ExecuteIntent. Case names establish no
  ledger, budget, assurance or readiness acceptance.

## 2026-10-31 - Prepare explicit Cardano asset-binding adversarial cases

- Propose concrete v2 definitions for25historical generic labels without changing
  frozen parent records; preserve exact transition/reference identities.
- Add148source cases, including valid callers and value-conserving construction
  controls.289cases remain uncompiled/NOT_RUN;8local byte/value checks pass.
- Preserve production validators,48hours, custody and ExecuteIntent rejection.
  Full parent/caller, native/ledger/budget and independent acceptance remain pending.

## 2026-10-31 - Reject unknown allocation completion status

- Require an existing composed allocation before isFullyClaimed can return true.
  Earned but unpaid, refunded and partially paid allocations remain incomplete.
- Preserve the Boolean ABI, fee/proof/payment semantics, pause and restricted
  economics. Changed non-upgradeable runtime identities need fresh release evidence.

## 2026-10-31 - Preserve recognized delivery claims across policy changes

- Add separate action-bound delivery recognition and earned-share payment calls.
  Pending evidence still needs current policy; payouts use fixed earned terms.
- Reserve earned unpaid funds during expiry refunds; release each delivery bond
  once and preserve backing when a later payment fails.
- Keep protocol pause, legacy rejection and restricted economics. New instances,
  authentic proofs, recovery qualification and independent review remain required.

## 2026-10-31 - Record current-tree scan blockers and explicit evidence digests

- Preserve the failing unchanged current-tree gate and sanitized640-match inventory;
  the479vendor identities match the existing baseline. Independent triage remains.
- Express the latest decoder report as an explicit public SHA-256 artifact record;
  unchanged-rule regression reproduces the original match and clears that record.
- Preserve historical evidence, scanner/workflow rules, product semantics and all
  readiness dispositions. Complete history scanning and credential closure remain.

## 2026-10-31 - Add strict common-action frame decoding

- Add exact695-byte v1receive boundaries to Solidity/Rust/Aiken, preserving all
  existing domains, encoder layouts, signature/proof and live policy requirements.
- Freeze33shared vectors.7local Python checks and35focused/full855candidate native
  Solidity tests pass; nativeRust/Aiken and full qualification remain pending.
- No new live route or authorization. New artifacts require source-bound rebuilds;
  old addresses/blueprints cannot be relabelled as this source.

## 2026-10-30 - Reject unqualified effect-candidate live startup

- Reject staging/testnet/production construction for the unactivated V3 object
  provider and V3/storage4 authority before callbacks or database work.
- Preserve test/local/demo and existing receipt/schema/accounting/recovery rules.
  Add12startup tests;155local crypto/controlled-driver tests pass,143prior included.
- Authentic current-host policy, remote credentials, native PG and live assurance
  remain pending. No live override, protocol promotion or deployment is enabled.

## 2026-10-30 - Anchor Cardano queue delay conservatively

- Require finite nonempty PlutusV3 [lower,upper) validity intervals and anchor
  Queue at upper so every permitted inclusion retains at least48hours of delay.
- Preserve historical bytes; freeze the amended Queue preimage/digest separately.
  Normalize valid fixtures and prepare53additional caller/timing cases,141total.
- Local reference arithmetic/byte checks pass25tests; all141Aiken cases remain
  NOT_RUN. Fresh compiled/applied identities, ledger/budgets and review are needed.
  ExecuteIntent and restricted activations remain disabled; no deployment occurred.

## 2026-10-30 - Validate Cardano input-reference encoding bounds

- Add explicit32-byte transaction-ID/u32-index checks to the governance-v2 input
  envelope. Datum/identifier formats,48h delay and insurance custody stay unchanged.
- Prepare27separate reference-width cases;88total native source cases remain
  uncompiled/NOT_RUN. Metadata consistency is not native or ledger acceptance.
- Require fresh compiled/applied identities,budgets,ledger checks and independent
  review before admission. No Aiken/Slot08,live role change or deployment was run.

## 2026-10-30 - Bind object eligibility to governed actor grants

- Add typed object/scope policy views requiring root-EOA consent and a bounded
  grant committed by the existing48h-governed policy root; bind issuer roles,
  resources, workflow/intent, cumulative ceilings and current action context.
- Let each actor permanently revoke only its own exact consent; keep unrelated
  policy generations unchanged and reject reuse even under a later governed root.
- Restrict generic context authorization to settlement capability4. Object callers
  must use the new grant path; unqualified signing capability2 remains denied.
- Add29native grant tests and12Python public codec checks, with Python/Solidity
  grant/Merkle and existing scopeV3 conformance. Actual custody/current-chain reader,
  native/live/full qualification and final effect/settlement remain pending.
- Preserve current receipt/scope bytes; add owner-only permanent grant revocation.
  Changed non-upgradeable
  policy requires a new instance in a separately authorized deployment ceremony.

## 2026-10-30 - Revalidate effect expiry after policy reads

- Reject expired proposals/scopes and backward time after a successful policy
  callback; use a fresh timestamp when signing admissions and effect receipts.
- Recheck admission after the provider's final retained-object lookup before a
  new effect; keep historical completion/absence reconciliation separate.
- Add8 timing regressions;143local crypto/queued-driver tests pass, previous135
  included. Native PG, authentic policy/clock/custody, remote and full qualification
  remain pending. No contract, wire, storage schema or activation change.

## 2026-10-30 - Preserve authority history across explicit renewal

- Add unactivated authority storage4 with retained grant generations and original
  operation bindings; keep V3 provider and receipt encodings unchanged.
- Require acknowledged closure, zero pending exposure and current host approval
  before a separately acknowledged successor; carry cumulative spending forward.
- Keep historical completion and fenced absence separate from new dispatch.
- Add 22 renewal tests; 135 local cryptographic/controlled-driver tests pass,
  including the previous 113. Native PostgreSQL, authentic policy/custody, remote
  execution, legacy migration and live qualification remain pending.

## 2026-10-30 - Connect unactivated V3 authority and provider recovery

- Add bounded authority grants, explicit PostgreSQL reservation schema, persisted
  admissions, single dispatch claims and lookup-only indeterminate recovery.
- Preserve completed-effect reconciliation; require acknowledged newer fencing and
  authenticated absence before releasing unresolved budget or completing cutover.
- Require explicit TCP/TLS certificate verification for live V3 database connections
  and exclude Unix/GSS/multihost downgrades; retain explicit local fixture behavior.
- Add53 tests and a Python-only scope vector;113local crypto/queued-driver tests
  pass. Authentic policy/PG/transport/custody/checkpoint/settlement and full gates
  remain pending. No live route, actual service use or economic activation.

## 2026-10-29 - Add an unactivated asymmetric V3 object-provider candidate

- Bind immutable-object actions to the common context and publicly verifiable
  admission/fence/effect evidence with distinct authority and provider issuers.
- Add explicit new PostgreSQL provider migration and transactional write/dedup/
  fencing code; preserve separate historical lookup and fenced-absence recovery.
- Add53 tests and a Python-only wire vector.60 local crypto/controlled-driver
  tests pass; real PostgreSQL/current-policy/authority integration remains pending.
  No live route or existing local receipt version is promoted.

## 2026-10-29 - Contain local effect helpers at direct runtime boundaries

- Reject live, unknown or changed runtime configuration before local provider,
  HTTP client or PostgreSQL helper effects, credentials, requests or connections.
- Preserve explicit local/test/demo fixtures and existing receipt/database formats.
  Add40 boundary-spy tests; production V3, real PostgreSQL and independent live
  qualification remain outstanding. No live effect backend is enabled.

## 2026-10-29 - Construct the restricted Amoy service stack

- Add an explicit-input full-service producer with preflight backend/code identities,
  atomic fresh bond initialization, exact settlement escrow authority and governance
  handoff postconditions. Preserve the historical core-only producer behavior.
- Keep initial policy inactive and rewards/minter/ordinary-governor/vesting excluded.
  Default entry points on the new producer reject missing typed configuration.
- Add24 local native fixture tests. Authentic backend/custody qualification, native
  full gates, independent review and separately authorized ceremonies remain required.

## 2026-10-29 - Bind the restricted Polygon release profile

- Require Polygon deployment schema2.0.0 and restricted-testnet-v1, restricted
  staking, and registry/policy/proof/settlement artifacts for canary admission.
- Reject ordinary governor/vesting artifacts and the ordinary-governor proposer
  grant. Bind constructor/configuration identities, exact escrow-role membership,
  zero emissions and disabled economic/action routes to explicit evidence records.
- Bind direct build/readback/activation/DCAP/EZKL/insurance references into aggregate
  evidence. Preserve public-stage requirements and Cardano governance-v2 checks.
- Package metadata is not proof of compilation, authentic proofs, on-chain state,
  custody or independent review. Integration/native/full/live gates remain required.

## 2026-10-29 - Reserve provider backing for composed settlement

- Reserve actual provider bond capacity per allocation and stable provider request,
  and pin the registry for existing claims/refunds across administrative changes.
- Bind request IDs permanently to their creating escrow. Reject reuse and foreign
  completion; release expiry reservations without recording delivery earnings.
- Preserve bounded owned cleanup after admission-role revocation/pause, all fee
  rules and disabled reward/slash activation. Add19 focused native regressions.
- Preserve initializer/storage shape; legacy request/proxy migration remains
  unqualified. Full release/independent/live gates and profile migration remain.

## 2026-10-28 - Bind Cardano governance release packages

- Require Cardano deployment metadata2.0.0 for authenticated governance-v2 artifacts,
 48-hour Queue and three-of-five cancellation. Preserve the historical v1 schema.
- Bind current native source/dependency inputs and exact applied-script bytes,
  and include direct build/test/ledger/budget/parameter/review references in the
  aggregate evidence. Package consistency does not establish native qualification.
- Retain the separate unresolved Polygon restricted-profile migration. No required
  workflow command, audit gate, custody or observation requirement is waived.

## 2026-10-28 - Contain direct SDK signing in live modes

- Reject raw-key, simulated session, OMS-wrapper and factory signing routes in
  staging/testnet/production before credential access. Recheck immutable runtime
  configuration before every signing operation, including retained direct callers.
- Preserve explicit non-live behavior. A qualified governed signing broker remains
  required; this control does not enable live signing or complete Stage D.
- Add16 spy-only regression methods; no real keys, signatures or services used.
  Correct Cardano governance/blueprint lifecycle labels; no readiness promotion.

## 2026-10-28 - Authenticated Cardano governance v2 candidate (unqualified)

- Add explicit v2 schemas/request envelope, pinned authority/role identities,
  backed voting custody, exact state/nonce continuity, bound48-hour intents and
  terminal burns/refunds. Preserve legacy bytes and established insurance source.
- Supply seven reference byte vectors,15 passing byte/value oracle tests and61
  prepared native cases, including23 separate follow-up rejection mutations. Preserve all81 historical acceptance obligations. Native
  Aiken, ledger, budgets, custody and independent review remain pending; no route
  or deployment is activated and F02/F03 remain open.
- Record the withdrawn receipt-width suspicion: inclusive0..31 already returns
  32bytes. See the review-draft ADR and source observations in
  `docs/remediation/repair_20261028/`. No release gate promotion.

## 2026-10-27 - Registry accounting, bound delivery and restricted activation repairs

- Read and snapshot actual Service Block registry terms for V2 escrow creation;
  cap builder fees at 5,000bps, retain the 5bps protocol fee, require exact funding
  and integer transaction units, and reject retired unbound creation/proof/claim APIs.
- Fund reward credits before accrual, expose pending liabilities and limit emergency
  recovery to surplus. Require matured normal/crisis unbonding on both exit paths.
  Restricted staking enforces zero emissions/budget; restricted deployment omits
  the ordinary governor/vesting and its proposer grant.
- Add canonical action-context bytes, governed current-policy admission/challenges,
  root/workload/output-bound delivery adapters and atomic payment replay handling.
  Reject SGX DEBUG quotes and noncanonical proof envelopes. Retire hash-only TEE
  success; provider-root settled evidence grants no unqualified score.
- Add separate v3 asymmetric receipt primitives and a 48-hour active Cardano delay
  amendment. Full authenticated Cardano governance and production PG/provider
  migration remain unfinished. Authentic DCAP/model/EZKL/bridge/DA qualification
  remains required; synthetic verifier fixtures are local boundary evidence only.
- Current local Solidity result: 748 tests / 45 suites, zero failures/skips;
  offline size build passes. Compiled storage comparison preserves prior aggregator
  fields, with initializer/upgrade/state checks. Independent review and other full
  gates remain pending. See `docs/remediation/repair_20261027/ADR.md`.

## 2026-10-24 - Isolated local object-effect v2 protocol preparation

- Add exact versioned proposal, admission, fencing and immutable-object receipts with explicit local-only coordinator/provider composition. Preserve v1 proposal bytes and live-mode denial; use shared principal locking to prevent v1 provisioning from reopening migrated v2 authority.
- Check new object and fence expiry after acquiring the SQLite write lock. Preserve reconciliation of historical committed effects and support legacy UTF-8 v1 principal lock values while retaining strict v2 scope validation.
- Independently reviewed source preparation with SQLite/DBAPI synthetic tests only. Real PostgreSQL durability/concurrency, independent operators, runtime containment, DA/settlement assurance and release qualification remain pending. No endpoint, live route or deployment is activated.

## 2026-10-21 - Isolated cached session allowlist shape validation (independently reviewed local repair)

- Reject missing/non-list/empty cached contract allowlists, invalid entries and malformed requested targets before exact membership checks. Prevent substring or mapping/set membership from authorizing malformed cached state; preserve issued-list normalization, expiry, value limits and existing PLATINUM semantics. Keyless synthetic regressions only; no live wallet, issuance or release approval.

## 2026-10-21 - Isolated GatewayClient constructor-log redaction (independently reviewed local repair)

- Emit a fixed constructor diagnostic without the configured URL, preventing endpoint path/query/fragment and embedded-newline reflection in that one INFO record. Preserve runtime/TLS/URL/transport behavior and other logs. Synthetic mocked-Session tests only; source draft inventory remains UNAPPROVED, with no privacy or release approval.

## Gateway evidence command parity (independently reviewed local repair)

- Label gateway audit results with the static contract check and rendered Envoy validation actually run by CI. Reject retired Caddy command labels under the existing strict catalog check; retain every gate/status, dirty-tree and provenance denial. Historical signed manifests are unchanged and require fresh approved CI evidence rather than editing signed bytes. No proxy configuration, deployment or release approval changes.

## 2026-10-20 - Isolated cached session transaction-cap validation

- Reject missing, malformed, boolean, NaN and negative cached transaction caps before scope effects. Preserve valid limits and the existing PLATINUM positive-infinity sentinel, expiry and allowlist checks. No issuance, cryptographic or live-session assurance; privacy draft candidate metadata only.

## 2026-10-20 - Isolated cached session-expiry validation

- Fail closed for malformed cached expiry metadata before clock/scope checks. Preserve valid timestamp, value/contract, creation and mock policy; no new duration/custody/live-session assurance. Privacy candidate metadata only; no release approval.

## 2026-10-20 - Isolated CLR timing-input validation

- Reject malformed timing budgets before routing effects. Preserve valid zero/fractional/finite/large values, amount-guard precedence and current access/route/SLA/finality policy. Privacy draft candidate metadata only; no release approval.

## 2026-10-20 - Isolated CLR risk-value validation

- Reject malformed, nonfinite, negative or boolean risk values before routing effects. Preserve valid numerical precision, existing access/threshold/priority/OMS behavior and all economic rules. Refresh only selected privacy draft candidate metadata; no privacy/release approval.

## 2026-10-20 - Isolated GatewayClient redirect containment

- Disable automatic redirects on five canonical requests so 3xx cannot forward payloads through an additional dispatch. Preserve normal statuses/runtime/log behavior; strengthen request expectations and refresh unapproved source facts/bindings. No TLS/auth/privacy or deployment gate closure.

## 2026-10-20 - Isolated GatewayClient runtime-context containment

- Apply existing strict runtime policy before Session construction, freeze captured policy/base URL and forward parent context. Preserve valid HTTPS/local-loopback and all transport/log behavior; refresh unapproved source facts/bindings. Redirect containment remains a separate pending repair.

## 2026-10-20 - Isolated GatewayClient failure-log sanitization

- Replace five body/exception-dependent client failure logs with fixed messages; preserve transport/state/return/TLS/auth semantics. Refresh unapproved privacy source facts and anchor without owner-policy approval.

## 2026-10-20 — Isolated publisher rejection sanitization

- Replace caught pre-submit publisher exception/input reflection with bounded fixed error/log messages and canonical known-or-unknown protocol labels. Preserve failure/routing/history/mock/eligibility behavior; strengthen the two affected legacy assertion cases. Refresh unapproved inventory source facts/bindings without privacy-policy or approval changes.

## 2026-10-20 — Isolated manifest version type validation

- Reject boolean, non-integer and nonpositive SkillOps manifest versions before hashing while preserving existing valid metadata hashes and resolution controls. Refresh the affected unapproved privacy source binding; no supported-version/trust policy or release gate changes.

## 2026-10-20 — Isolated Service Block resolution validation

- Reuse existing memory/permission declaration validation before single/macro blueprint resolution; preserve valid policy declarations and catalogue behavior. Refresh the affected unapproved privacy source binding. No signature/quarantine/runtime approval or gate promotion follows from these local checks.

## 2026-10-20 — Isolated privacy source-binding refresh

- Refresh the existing unapproved field inventory for the wallet constructor edit; preserve field classifications and UNKNOWN owner decisions. Source hashes/anchors are consistency checks only; T33 remains blocked.

## 2026-10-20 — Isolated wallet-facade containment candidate

- Require strict immutable runtime policy for SequenceWalletManager and explicit non-live mock selection for its three simulation-only wallet methods; reject non-mock fake success while preserving session-key controls. Forward existing VamsNeuron startup policy and clarify the legacy local mock test.
- Local synthetic evidence only; real Sequence/bundler, legacy crypto, supported full/security gates and canonical integration remain pending. No deployment or gate promotion.

### Fleet isolated secret-scanner enforcement checker - 2026-10-20

- Require the existing workflow checker to retain unique always-running Gitleaks/TruffleHog result guards, bound to the matching scan outcome, and evidence upload before enforcement.
- Bind each named scan step to its existing unsuppressed run body and shell/properties so a no-op, disabled scanner branch or ignored failure cannot masquerade as the reviewed scan in this checker. The workflow, scanners, pins and allowlists are unchanged.
- An initial independent review rejected the first patch for missing scan-body binding; the revised local mutation suite covers that gap. Final combined test and engineering review records are under fleet evidence/integration-r4. Static checks do not establish complete YAML/GitHub semantics or hosted-CI/scanner execution, and no gate is promoted.

### Fleet isolated session-value repair and privacy review draft - 2026-10-20

- Reject nonnumeric, boolean, negative and nonfinite session transaction values before spending-cap comparison. Existing cap values, units, expiry and contract allowlists remain unchanged; finite inputs remain governed by the configured cap.
- Add an unapproved source-backed privacy inventory covering seven publisher records and eleven flow groups, with explicit unknown recipients, access and retention. It grants no disclosure approval or runtime/deployment evidence.
- Combined local checks and independent engineering review are recorded in fleet evidence/integration-r3. Full dependency, signing/bundler, HTTP, security and release checks remain pending; no gate is promoted.

### Fleet isolated numeric and log privacy repairs - 2026-10-20

- Omit exception values from Celestia retrieval warnings while preserving False/None failure behavior, mock containment and release ineligibility. Controlled transport doubles do not establish HTTP or native DA proof.
- Validate DA telemetry/duration bounds before float conversion to prevent oversized-integer overflow. Compare original integers to configured limits, rejecting just-outside values previously admitted by float rounding; limits and disclosure policy remain unchanged.
- Local synthetic checks and independent review records are retained under fleet evidence/integration-r2. Canonical application, HTTP/Python3.12 integration/security checks and release approval remain pending; T30/T33 stay blocked.

### Fleet isolated local hardening candidate - 2026-10-20

- Reject nonpositive and noninteger audit-history limits and declare a positive query bound for `/da/anchors`; six focused public-method regressions pass locally. FastAPI HTTP and supported Python 3.12 integration checks remain pending.
- Clarify interchangeable/hybrid verifiable memory, preserve GCA capabilities and selected-algorithm parameters/tests, and correct checkpoint/IVT/Sentinel source-status claims.
- This isolated candidate is independently reviewed local work only; no canonical integration, deployment, gate promotion, GCA enforcement, privacy approval, or retention policy is claimed.

### M7 evidence artifact naming alignment - 2026-10-18

- Align evidence filenames with current workflow behavior: CI creates and uploads `audit-evidence.sigstore.json`, while public-stage verification expects `closed-canary-report.sigstore.json`; separate `.sig` and `.pem` paths are not used by that workflow.
- This corrects evidence documentation only. It does not create evidence, change workflow behavior, or close the T05 certificate-identity review; no tests or CI jobs ran.

### M5 DA documentation reality correction - 2026-10-18

- Clarify that Celestia has submission/retrieval code paths but no VAMS DAS or release-evidence implementation; Near live submission/retrieval is blocked; Avail and EigenDA remain simulated stubs; and the legacy Polygon DAC signature count is not cryptographic verification.
- This corrects current-state documentation only. No code, runtime behavior, network evidence, or gate status changed; T30 remains blocked and no tests or provider calls ran.

### M7 INV-2 post-payout insurance cap containment - 2026-10-06

- Reject an approved insurance payout before finalization if the payout would leave deployed capital above 30% of the post-payout total; keep the approved claim retryable after capital or funding restores the cap.
- Accept possible payout delay. No automatic vault unwind, vault redemption, claim reduction/forgiveness, or new expiry/queue behavior is introduced or verified.
- Local synthetic validation: 11 insurance tests, 30 provider-bond regressions, and 8 settlement integration tests passed offline; evidence is retained under /home/GodOfAgents/vams-evidence/m7_inv2_payout_cap_r1_20261006/.

### RW-061 placeholder containment verification - 2026-10-06

- Ran test/ZKMLProofContainment.t.sol offline with the existing pinned Forge runtime and the checksum-verified official Solidity 0.8.24 compiler. Result: 1 passed, 0 failed, 0 skipped; the exact artifact and independent review are retained in docs/remediation/rw061_zk_placeholder_containment_r2_20261006/.
- This verifies placeholder containment only. M4, real verifier/circuit qualification, ledger admission, and testnet readiness remain open; deployment and gated activations remain disabled.

### RW-061 placeholder ZK proof containment - 2026-10-05

- Disabled placeholder ZK proof generation and verification in Python and Solidity, excluded it from automatic discovery, rejected manually supplied SDK bundles, and removed ZK deployment/registration from the standard plugin script.
- Added regressions for fabricated proof bytes at the Python SDK and Solidity aggregator boundaries. This does not qualify a real verifier or circuit and grants no ledger, live-network, or deployment credit.

### F04 registry identity mint rejection - 2026-10-04

- Registry-side MintIdentity now fails closed. Legacy registry burn validation remains available pending the separately designed migration. Standalone mint and registration are not enabled; canonical policy anchoring remains unresolved.

### M7 sanitized pytest failure identity diagnostic - 2026-10-04

- Reproduce the 10 root-suite and 1 design-suite failures, retaining only normalized test identifiers and safe outcomes while deleting temporary JUnit and raw pytest output.
- Source review points to read-only sandbox write failures for ten cases and one stale F04 test expectation. Keep these provisional until a disposable writable-overlay rerun.

### M7 current-source Python workflow test gate - 2026-10-04

- Re-run the current Python workflow split offline with pinned Python, pytest, and Envoy. Collection finds 1,693; root suite reports 1,683 passed, 10 failed, and 444 subtests passed; separate design suite reports 9 passed and 1 failed.
- Keep the Python gate failed pending exact failure identification and remediation; no hosted CI or deployment credit follows.

### M7 current-source Bandit scan - 2026-10-04

- Run pinned Bandit 1.9.4 on current 
euron/` and `gateway/` Python sources with workflow thresholds `-ll -ii`; the offline local scan exits 0 with zero findings and zero errors across 190 files.
- Keep this as local static-analysis evidence only. It does not establish hosted CI parity, runtime behavior, or deployment readiness.

### M7 current workflow/toolchain inventory - 2026-10-04

- Reconcile current workflow pins with available local binaries and record exact version checks. Forge, Aiken, pytest, Bandit, pip-audit, Gitleaks, and Node are present at pinned versions; Node is off PATH and npm is a Windows launcher.
- Keep gates pending when tools or prerequisites are unavailable: no solc in PATH/preserved toolchains, no frontend node_modules, and no Slither, Semgrep, or TruffleHog. No tests, builds, audits, or scans ran; no tool was installed or fetched.

### F05.2a current-source R3 signature canaries - 2026-10-04

- Re-run only the frozen valid and invalid-signature fixtures through the snapshot-bound R3 simulator against the current harness. The valid transaction accepts, the invalid-signature transaction rejects, and both runs bind the exact Mint[0] policy with clean teardown.
- Keep F05 at 45/55 negative cases and 18/21 mutations; these two synthetic canaries add no ledger, Pre-Prod, or live-network credit. Full-suite R3 transaction materialization remains unproven.

### M7 T06 available-local-history scan - 2026-10-04

- Capture a fully redacted, network-isolated Gitleaks 8.30.1 scan of the 9 locally available refs and 89 reachable commits. The scan exited 0 with 0 findings; independent review passes and package checksums verify.
- Keep T06 and testnet readiness blocked: four protected commits are absent locally, and hosted refs, credential/provider impact and revocation, TruffleHog, rewrite authorization, and post-rewrite scans remain outstanding.

### F05.2a synthetic mutation provenance - 2026-10-03

- Capture exact offline compiled policy bytes, applied parameters, submitted UPLC programs and contexts, child verdicts, and input/tool hashes for the F05 public harness. Independent review verifies 35 policy IDs and 134 evaluations.
- Keep F05 ledger counts and deployment gates unchanged; this evidence uses ephemeral synthetic committee keys and does not establish transaction or network admission.

### F05.2a unconditional-success synthetic context alignment - 2026-10-03

- Rebind each negative to its unconditional-success mutant policy ID, compiling separate mutants for six applied-parameter variants. The offline focused suite passes 99/99 and the full synthetic harness records 55/55 accepted subcases.
- Keep accepted F05 counts unchanged pending individual mutant provenance, owner evidence classification and ledger admission.

### F05.2a disposable inline-datum mutant Datum type - 2026-10-03

- Use the pinned Aiken `Datum` type in the disposable guard-removal mutant. Focused tests pass 38/38 and the full synthetic public harness now exits 0.
- Keep F05 case and mutation ledger counts unchanged until owner evidence classification, unconditional-success coverage, and provenance review are complete.

### F05.2a inline-datum mutant import anchor - 2026-10-03

- Match the current validator import when constructing the disposable inline-datum guard mutant. Focused tests pass 38/38.
- The mutant build still exits 1; the harness has no complete result or new F05 acceptance credit.

### F05.2a synthetic policy-ID rebinding order - 2026-10-03

- Sort test-harness mint and output asset-policy maps after mutant policy-ID substitution so Aiken dictionary lookups retain canonical order. Focused tests pass 31/31; the full harness reaches a separate stale inline-datum mutation anchor.
- No F05 case/mutation count, ledger-admission, or activation credit follows.

### F05.2a synthetic address Option correction - 2026-10-03

- Correct test-harness stake Option constructors and use the supplied stake hash for present stake credentials. Focused offline tests pass 27/27, and the compiled synthetic positive control accepts.
- The full harness still stops at an extra-asset guard-removal mutation; no F05 ledger-count, ledger-admission, or activation credit follows.

### F05.2a UPLC text-alias diagnostic - 2026-10-03

- Normalize only Aiken's legacy Ed25519 builtin name in decoded test-harness UPLC, then require byte-identical re-encoding before evaluation. The compiled policy and fixtures are unchanged.
- The public positive control now reaches evaluator execution but still exits with a validator-crash verdict; no F05 case or mutation credit, ledger admission, or activation follows.

### M7 strict Aiken warning cleanup - 2026-10-03

- Remove seven unused-source warnings in the disabled standalone agent_nft validator without changing its parameter schema, blueprint bytes, or any of 26 compiled program hashes.
- Rebind source provenance and keep F04 normative identity, ledger admission, and testnet activation as separate gates.

### M7 exact Aiken dependency provenance - 2026-10-03

- Pin stdlib and fuzz to the exact upstream commits whose bytes match the accepted local dependency manifest. Preserve the compiled validator blueprint identity in two network-denied isolated builds.
- Keep strict Aiken warning cleanup, F04 authority, and testnet deployment acceptance as separate gates.

### M7 local effect-provider redirect containment - 2026-10-03

- Prevent the loopback effect-canary client from following HTTP redirects, so
  signed requests and payloads cannot be forwarded to a redirect target.
- Add a local redirect regression and keep integration-test HTTP calls on
  explicit loopback connections. This remains local synthetic evidence only.

### F05.2a sealed-snapshot test compatibility — 2026-10-02

- Support Linux Python builds without exported fcntl sealing symbols using
  fixed Linux UAPI values, retaining kernel enforcement and pre-spawn readback.
- Kernel-adversarial and existing runner tests pass 20/20 on Python 3.12.14
  and 3.14.4; independent review accepted the exact change. This is simulator
  infrastructure only; no ledger admission or activation is enabled.

### F05.1-R4 design-contract remediation - 2026-09-30

- Added a closed, versioned cross-chain authority/finality/replay contract,
  canonical byte vectors and an independent encoder, plus public-validator
  mutations for semantic trust, accounting, topology, replay and signature
  failures. The scoped suite passes 26/26; independent review accepted the
  manifest-bound snapshot (digest cd99178b4224e6662774877cd5a3f6671ccce40bd3447204054e4d1ca0dd4edc; snapshot-only access).
- This design-only evidence is not F05 closure or deployment authorization.
  F01-F03/F05 remain open, F04 is remediated, M3 is open, Pre-Prod is
  inconclusive and promotion is not ready. F05.2 remains unauthorized.

### M3 F04-R3 production identity remediation - 2026-09-28

- Remediated the accepted R2 Cardano identity-policy, value-topology, authority-exactness and canonical-DID findings in the parameterized multipurpose registry boundary and regenerated the pinned-Aiken blueprint/provenance.
- This remains local implementation evidence only: the compiled 49-row public-handler evaluator is unavailable (0/49 executed), so F04/M3 remain open and promotion is not ready.

### M3 F04 interface migration R1  2026-09-28

- Replaced the pre-deployment legacy Cardano AgentDatum/registry/NFT interface with the accepted versioned identity contract and regenerated the pinned Aiken blueprint.
- This is local implementation evidence only; F04 remains open pending compiled transition acceptance and independent R2 review. F01-F05, M3, deployment, Pre-Prod admission and promotion remain open/not ready.

### Security

### M3 F04 documentation-only closure - 2026-09-30

- Recorded the independent R6 acceptance of the bounded Option-B registry
  implementation and reconciled current F04 status to REMEDIATED. The
  evidence chain records 49/49 rows, 67/67 evaluations, zero pending,
  supplemental 28/28, migration 15/15, fixture 14/14, provenance 21/21 and
  two identical pinned Aiken 120/120 runs.
- The earlier failed compiled review remains unchanged historical evidence;
  forward provenance is explicitly reset to the current lock because historical
  lock bytes are unavailable. F01-F03/F05 and M3 remain open, Deposit and
  ExecuteIntent remain disabled, post-F05 SlashAgent remains blocked, Pre-Prod
  is inconclusive and promotion is not ready. INV-1-INV-10, M1/M2 containment
  and mock behavior are unchanged.

- **F04 production implementation R1 blocked fail-closed**: The accepted design is not compatible with the current legacy Cardano constructor, redeemer, validator, NFT-policy and blueprint surface. No production source changed; F04 remains REVALIDATED_OPEN pending an explicitly authorized interface/blueprint migration.

- **M3 F04 design R5/R6**: Closed the design-only authority/action/replay/reserve contract with exact policy, token, quantity, value, datum and address bindings, a one-time action-token burn rule, a 49-row acceptance matrix and deterministic import-boundary tests. Independent R6 review accepted only the next scoped production implementation slice; F01-F05, M3 and promotion remain open.


- **M3.2b closure**: Independently accepted the frozen governor/timelock
  compiled-handler and mutation-harness assurance through R11. The candidate
  classifier now has an exact 13-row closed contract with one positive and
  twelve negative rows, including unknown-field and boolean-integer cases,
  plus candidate path/hash isolation and row-schema mutation regressions.
  M3.2b is locally accepted, but F01-F05 remain open, Deposit/Execute remain
  disabled, M3 remains open, Pre-Prod admission is inconclusive and promotion
  is not ready. INV-1–INV-10, M1/M2 containment and mock behavior are
  unchanged. Next: M3.2b closure reconciliation, then F04 work.

### M3.2b-R4 mutation-harness remediation — 2026-09-28

- Corrected the compiled timelock mutation fixture to use the reviewed V3 ScriptContext boundary and valid authority/intent inputs.
- Added deterministic three-way, ten-repetition and adversarial mutation checks. This is local remediation only; independent R5 review is next and F01-F05/M3 remain open.

### M3.2b-R3 governance evaluator/provenance remediation — 2026-09-28

- Added forward-versioned governance dependency provenance and regenerated the checked-in blueprint from isolated pinned Aiken 1.1.21 sources.
- Added compiled execution coverage for all 36 frozen public-handler rows.
- R3 remains local and incomplete because the required mutation-sensitive compiled probe has not yet detected the unconditional-spend mutation; F01-F05, M3 and promotion gates remain open.

# Changelog

All notable changes to the VAMS project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Local effect qualification canary**: Added a PostgreSQL-backed authority and
  budget coordinator, operator CLI, and loopback-only immutable object provider
  with atomic SQLite object/idempotency records, request replay protection,
  operation lookup, and a separately credentialed observation route. This is
  local qualification code; PostgreSQL integration and independent observation
  are not yet verified and no deployment capability is enabled.

### Security — frontend dependency audit

- Pin the five transitive frontend dependencies to upstream patched versions identified by the October 2026 npm audit. Full-tree and production-only lockfile audits report zero vulnerabilities across 257 dependency entries, and frontend telemetry/security tests pass 4/4. Clean-install workflow, lint, build, and production-bundle scan remain pending because dependencies were not installed.

### Security

### M3 F04 Option-B implementation — 2026-09-29

- Implemented raw-UTF-8 DID identity semantics with strict 32–256-byte bounds,
  froze 49 serialized ScriptContext fixtures, and added a compiled 49-row
  evaluator with nine mutation controls and fixture-isolation assertions.
- Rebased forward provenance on current lock `6f3b369f...`; historical lock
  bytes remain unavailable and are not claimed continuous. Focused fixture,
  provenance, isolated Aiken and mutation checks pass locally.
- This is implementation evidence only: F04/F01-F05 and M3 remain open,
  Deposit/ExecuteIntent remain disabled, Pre-Prod is inconclusive and promotion
  is not ready. INV-1–INV-10, M1/M2 containment and mock behavior are unchanged.
### M3 F04 design R5/R6 - 2026-09-28

- Closed the design-only authority/action/replay/reserve contract with exact policy, token, quantity, value, datum and address bindings, a one-time action-token burn rule, a 49-row acceptance matrix and deterministic import-boundary tests.
- Independent R6 review accepted the design-only delta and authorizes only the next scoped production implementation slice. F01-F05, M3 and promotion remain open.

- **M3.2b-R1 frozen governor/timelock implementation**: Added the versioned
  governance types, bounded helper rules, governor/timelock validators and
  authority/proposal/receipt/intent policies, then regenerated the pinned Aiken
  blueprint. Structural frozen-vector and matrix checks pass; the qualified
  transaction evaluator for 36 public-handler acceptance rows remains pending.
  F01-F05, Deposit/Execute, M3 and promotion remain open; INV-1 through INV-10,
  M1/M2 containment and mock behavior are unchanged. Next: independent
  M3.2b-R2 review.

- **M3.2a-R21 FIFO harness remediation**: Replaced the unbounded parent
  FIFO mutation loop with a reusable isolated child/process-group probe that
  enforces hard deadlines, bounded termination/reaping, process cleanup,
  temporary-path cleanup and descriptor continuity. Fixed controls and both
  required blocking mutations are covered by fresh repeated tests; production
  oracle, Cardano/provenance inputs, invariants and mock mode are unchanged.
  F01-F05 and M3 remain open, Deposit remains disabled, and M3.2b is not
  authorized. Next: independent M3.2a-R22 test-harness delta review.
- **M3.2a-R17 oracle remediation**: added descriptor-bound no-follow registry loading, canonical CBOR re-encoding/equality, frozen authority-successor derivation and mandatory transition topology checks with six focused regressions. Frozen R7 artifacts, Cardano/provenance inputs, production behavior, invariants and mock mode remain unchanged; F01-F05 and M3 remain open and M3.2b is not authorized. Next: independent M3.2a-R18 review.
- **M3.2a-R13 oracle-defect remediation**: Closed the R12 independent-oracle gaps with versioned snapshot validation, strict bounded arithmetic, exact topology reference checks, canonical target encoding, concrete reserve destinations and frozen datum/vector validation. Focused oracle tests pass 9/9. Frozen R7 artifacts, Cardano/provenance inputs, production behavior, invariants and mock mode remain unchanged; F01-F05 and M3 remain open and M3.2b is not authorized. Next: independent M3.2a-R14 review.

- **M3.2a-R11 remediation of R10**: Corrected the design-only enterprise address and target-domain contracts, froze normative artifact and topology/matrix semantics, and expanded the independent value/lifecycle oracle. No Cardano, provenance, deployment, credential, invariant or mock behavior changed. F01-F05 and M3 remain open; next is independent M3.2a-R12 review.

### Security
- **M3.2a-R9 remediation of R8 findings**: Closed the R7 machine-spec schema
  and reference graph, bound raw and normalized manifest-v3 lock provenance,
  and added an independent address/value/topology oracle with fail-closed
  ledger-parameter preflight. Nine machine-spec tests, six oracle tests, twenty
  provenance tests and two pinned Aiken isolated check/build runs pass. This is
  local remediation only; F01-F05, M3, Deposit/Execute, min-ADA/budget
  evidence and promotion remain open. Cardano sources, lockfile, dependencies,
  invariants, mock behavior and deployment state are unchanged. Next:
  independent M3.2a-R10 final specification/provenance review.

### Security
- **M3.2a-R7 machine-readable specification closure**: Added the normative
  GovernanceConfigV1, exact destination/value/topology rules, canonical asset and
  datum vectors, and a closed pending acceptance matrix with dependency-free
  validation. This remains design-only; current Cardano validators, provenance
  inputs, M3, F01-F05 and deployment state are unchanged. The known R6
  nonvolatile temporary-lock-byte verifier defect remains explicitly open.
  Next: independent M3.2a-R8 specification review.

### Security
- **M3.2a-R5 design and forward provenance**: Added the normative design
  exactness amendment for terminal value conservation, canonical asset/policy
  serialization, counter/authentication, deterministic lifecycle boundaries and
  topology stop rules. Forward-versioned the dependency manifest only after
  proving the current lock differs semantically only in approved etag
  timestamps; the lockfile and all Cardano/runtime behavior remain unchanged.
  Focused provenance tests pass 18/18 and the pinned Aiken isolated run passes.
  F01-F05/M3 remain open and the next slice is independent M3.2a-R6 review.

### Security
- **M3.2a-R3 ADR remediation**: Amended the design-only governance contract after
  independent R2 findings. The ADR now specifies immutable authority genesis,
  authenticated proposal/intent counters, receipt-policy and exact lock-refund
  semantics, an eight-voter serialization-feasible bound, complete proposal and
  pre-F05 timelock lifecycle, and a public mutation-linked acceptance matrix.
  This changed documentation only; F01-F05, M3, Deposit/Execute, invariants,
  mock behavior, Cardano sources, dependencies and deployment state are unchanged.
  Next: independent M3.2a-R4 design-feasibility review.

### Security
- **M3.2a authenticated governance baseline**: Recorded independent R16
  acceptance of M3.1b custody and forward dependency provenance, while keeping
  F01 open for F05 authority/finality/replay and Deposit disabled. Froze the
  bounded authority/proposal/intent asset model, locked voting receipts, exact
  governor-to-timelock binding, normal-delay-only policy, finite contexts and
  fail-closed execution boundary for M3.2b. F02/F03 remain open; no validator,
  deployment, credential, invariant or mock behavior changed. Next: M3.2b.
- **M3.1b-R15 strict timestamp and package-index parser remediation**: Remediated
  only R14-01 by rejecting TOML booleans in both lock timestamp components with
  the existing strict integer predicate and adding direct parser-level package
  index tests that bypass outer manifest-hash checks. The focused provenance
  suite passes 16/16, the pinned Aiken 1.1.21 isolated check/build passes, and
  five historical R10 mutations remain rejected. F01/M3 remain open, Deposit
  remains disabled pending F05, and invariant, mock-mode, dependency, Cardano,
  deployment and credential behavior are unchanged; next is independent
  M3.1b-R16 micro-review.
- **M3.1b-R13 manifest validation boundary remediation**: Closed the R12-01
  malformed-container error boundary only. Project inputs, package-cache/index
  containers, nested records, cardinality and strict integer types are checked
  before access; malformed manifests now fail with bounded VerificationError
  and CLI JSON without tracebacks. R11 provenance semantics and all Cardano,
  invariant, mock-mode and deployment behavior remain unchanged. F01/M3 remain
  open; next is independent M3.1b-R14 review.
- **M3.1b-R11 deterministic Aiken dependency provenance remediation**: Closed
  the independent R10 findings by binding the complete current source set,
  project inputs, canonical package index, exact cache topology and files,
  pinned compiler, blueprint and compiled programs. Unsafe identifiers,
  traversal, links/special files, drift and network fallback now fail closed;
  two identical isolated runs and 11 mutation-sensitive tests pass. F01/M3
  remain open, Deposit remains disabled pending F05, and no validator,
  invariant, mock-mode or deployment behavior changed. Next: independent
  M3.1b-R12 review.
- **M3.1b-R9 deterministic Aiken dependency provenance**: Added a closed
  current Cardano dependency manifest and an isolated pinned-Aiken verifier.
  Only the two observed etag timestamp fields are excluded from semantic lock
  comparison; dependency identity, revision tag, integrity, resolved package
  content, source hashes, blueprint and every compiled program remain bound.
  R4 raw lock bytes are permanently unavailable and no historical equivalence
  is claimed. F01/M3 remain open, Deposit remains disabled, and no invariant,
  runtime, mock-mode or deployment behavior changed.
- M3.1b-R5 bounded custody remediation: applied the independent R4 findings only. Every enabled insurance transition now enforces the shared finite five-minute interval, unique six-signer boundary, exact 16-input/16-output maximum fixtures, 896-byte datum boundary, strict compiled-blueprint provenance, and structured INV-10 traceability. F01/M3 remain open pending independent R6; Deposit remains disabled pending F05 and promotion is not ready.
- **M3.1b-R3 bounded public Cardano custody**: Remediated the independent R2 findings with a finite five-guardian/two-claim state contract, 16-input/output/asset transaction bounds, an 896-byte datum ceiling, finite five-minute genesis intervals, mutation-sensitive lifecycle tests, and a standard-library compiled Plutus V3 public-entrypoint harness. Maximum local evaluator cases remain below 1.29 billion CPU and 3.26 million memory, but no Pre-Prod admission claim is made without a provenance-bound parameter snapshot. F01 and M3 remain open pending independent R4 and F05; other invariants and mock behavior are unchanged.
- **M3.1b-R1 authenticated Cardano insurance custody**: Implemented the frozen M3.1a singleton-state custody contract with exact continuing value/datum conservation, bounded canonical claim identities and approvals, exact payout binding, finite expiry, and removal-based replay resistance. Deposit rejects unconditionally pending F05. The pinned Aiken 1.1.21 suite passes 104/104, including 59 insurance tests; regenerated identities are unapplied build evidence only. F01 and M3 remain open pending independent M3.1b-R2 and applied-script budget review; invariants and mock-mode behavior are unchanged.
- **M3.1a Aiken recovery and F01 custody design baseline**: Recovered checksum-verified Aiken 1.1.21 outside the repository, passed all 50 native `aiken check` tests and a fresh blueprint build, mapped the current unauthenticated insurance validator, and froze a singleton-state, value-conserving, replay-safe claim lifecycle for M3.1b. Deposit remains fail-closed pending F05 authority/finality/replay design; F01 and M3 remain open, executable invariants and mock behavior are unchanged, and no deployment claim is made.
- **Independent M2 closure and F08 disposition**: Recorded the checksum-verified M2-R5 acceptance of the complete M2.1-M2.4b, INV-5, frontend `/nodes`, and frontend CI chain. M2R4-01 and F08 are `REMEDIATED`; M2 is `COMPLETE`. Historical review verdicts remain unchanged. Overall promotion readiness remains `NOT READY`, with T06/history and M3-M9 open; INV-1-INV-10, F17, F09, M1 containment, and mock-mode behavior are unchanged.
- **M2R4-01 closed frontend command contract**: Replaced permissive command-line presence checks with exact structural contracts for the frontend install, telemetry test, production build, and bundle scan steps. Unique reviewed step names, sole `run` properties, exact two-line bodies, command uniqueness, and fixed ordering now reject extra shell commands, `set +e`, terminal-success substitutions, conditions, ignored failures, duplication, removal, and reordering. Runtime behavior is unchanged; F08 and M2 remain open pending independent M2-R5 review.
- **M2 frontend CI enforcement remediation**: Made the existing `/nodes` telemetry/security tests and the reviewed production-bundle credential-pattern scan mandatory in `frontend-gate`. A shared deterministic scan runs only after the production build, while structural workflow regressions reject removal, reordering, ignored failures, or conditional execution. Runtime behavior is unchanged; F08 and M2 remain open pending independent M2-R4 delta review.
- **Frontend `/nodes` disposition**: Kept root Gateway `/nodes` classified as an M2-authenticated read and removed the static SPA's unsigned polling and fabricated node fallback. The UI now reports that live node telemetry requires an authenticated server-side session, sends no node request, and cannot promote `401`, network, or malformed outcomes into telemetry. No browser credential, signing authority, local/demo substitute, BFF, or authentication protocol was added. F08 and M2 remain open pending independent review.
- **INV-5 traceability-control synchronization**: Replaced the stale prose-only OMS anchor with schema-versioned AST controls over the institutional P3 denial guard, live-provider result provenance, provider failure outcomes, and OMS signer guards, plus exact regression-test identifiers. Temporary-copy mutations now reject guard removal, permissive fallback, test removal, and malformed or duplicate metadata while tolerating harmless prose changes. Runtime behavior, F09's `REMEDIATED` disposition, mock-mode containment, and INV-1–INV-4/INV-6–INV-10 remain unchanged.
- **M2.4b-R5 Envoy ingress and RFC 9112 acceptance contract**: Replaced Caddy as the live Gateway boundary with checksum-pinned Envoy 1.39.1 and a reviewed TLS/mTLS configuration that rejects mixed length/transfer framing, escaped separators, underscore headers, unsupported methods, and oversized requests while stripping and regenerating forwarding, ingress, and certificate assertions. Live Gateway traffic now requires a loopback proxy peer plus the exact versioned Envoy marker before M2 authentication. The signed request is the trusted ingress-normalized semantic request; RFC 9112 obs-fold replacement is accepted only when authenticated meaning, body bytes, request count, and replay identity are unchanged. Caddy is retained only as an unsupported historical template. F08 and M2 remain open; INV-5 traceability and frontend `/nodes` are unchanged.
- **M2.4a fail-closed durable replay schema integrity**: Remediated M2-R2 Finding 1 by requiring the exact executable SQLite replay/revocation schema at startup and again under the same immediate transaction as every security operation. Exact objects, columns, composite keys, WITHOUT ROWID, indexes, collations, checks, and rollback-probed constraints are enforced; triggers, views, virtual/extra tables, semantic index substitutes, and post-start schema drift deny without handler execution. Replay now uses a normal insert and classifies only the exact primary-key collision as a duplicate. F08 and M2 remain open; raw-wire ingress, INV-5 traceability, and frontend /nodes are unchanged.
- **M2.3 protected Gateway route enforcement**: Added a closed 32-entry route/method ledger covering the root application, generated documentation aliases, and mounted VDSO router. Sensitive reads and all state-changing methods now authenticate through the M2.1 canonical envelope and reserve through the M2.2 durable store before handlers run; unknown routes, slash aliases, WebSockets, ambiguous framing, unsupported streaming/multipart, and legacy root/VDSO auth alternatives fail closed with sanitized errors. Real loopback restart and two-process tests prove durable replay, single execution, and cross-worker revocation on the documented host-local boundary. F08 and M2 remain open pending independent M2-R2 review.
- **M2.2 durable replay and revocation boundary**: Added an explicitly configured host-local SQLite backend for live gateway replay reservation and signer revocation. One immediate transaction serializes revocation checks with the version/audience/signer-digest/nonce reservation and rechecks before commit; WAL/full-sync state survives workers and restarts. Expiry retention includes the M2.1 skew bound plus a safety margin, cleanup is bounded and rollback-defended, unsafe/unavailable storage fails closed, and raw requests/signatures/credentials/signers are not persisted. Gateway initialization occurs before owned activity and preserves F17. F08/M2 remain open until M2.3 migrates protected routes and proves real HTTP enforcement.
- **M2.1 canonical gateway request-authentication envelope**: Added a closed v1 request envelope with tagged length-prefixed domain separation over method, raw path/query, exact body digest, fixed configured audience, existing admin DID signer, bounded nonce, and strict integer issue/expiry times. The FastAPI dependency seam preserves exact body bytes and rejects unsupported algorithms, ambiguous targets, duplicate headers, malformed keys/signatures, and every unavailable key or replay outcome. A bounded process-local atomic replay store exists only as a `RuntimePolicy`-bound non-live test double. F08 remains open: durable shared replay, restart/multi-worker correctness, revocation enforcement, and protected-route migration belong to M2.2/M2.3.
- **M1 independent closure**: Corrected-state independent review accepted the strict runtime-mode and simulation-containment milestone and closed F09 as remediated. All 25 registered mock flags fail closed in live modes, injected policies cannot rebind the process environment, aggregate live preflight rejects component mocks, and every reviewed gateway, Neuron, demo, anchor, identity, TEE, DA, Trails, payment, bridge, escrow, recovery, and provider boundary is either live-capable under its explicit contract or blocked before effects. F10, F11, and F12 remain open for M5/M6 real integration work; this is not deployment or testnet-readiness evidence.
- **M1.3 executable-boundary and deployment-mode preflight**: Added a repository-native runtime preflight that parses the same immutable `VAMS_ENV` policy, supports exact expected-mode/live checks, and emits only sanitized classification. The central contract now validates all 25 registered M1 mock flags, rejects every enabled flag in live modes, and prevents a supplied policy from rebinding a conflicting process environment. CI declares `VAMS_ENV=test`, exercises an exact `testnet` deployment preflight, and retains every existing security job. The primary Neuron constructor and its communications/routing/payment branches reject incomplete live execution before effects; the legacy Neuron gateway is non-live only. The standalone demo requires exact demo mode and emits only `simulated:` identifiers and non-authoritative claims; anchoring cannot attempt a provider and silently fall back. The former CDK mock-success shell is a fail-closed scaffold and cannot claim a running network.
- **M1.2c payment, bridge, escrow, recovery, and remaining mock containment**: Migrated Coinme, x402 channels, in-memory escrow recovery, interrupt handlers, bridge/ICB/Multi-ISM, MEV simulation, Iagon, Akash, Sentinel, legacy DA routing, and the legacy Celestia sampler to the central strict runtime policy. Mock flags default off, malformed/conflicting values fail, live modes reject before external or owned effects, and explicit non-live results carry simulated/non-authoritative markers. Coinme no longer substitutes fixed rates after provider failure; structural bridge proofs, synthetic transaction hashes, mock signatures, in-memory escrow state, network-head-only availability, unconfirmed Akash submission, and unauthenticated Iagon durability cannot be promoted as live evidence. INV-10 remains preserved: bridge proof bytes and payload hashes remain separate inputs and values. F10 remains assigned to M5; no DA/provider/payment/bridge/recovery integration was built.
- **M1.2b Avail, EigenDA, and Trails live-mode enforcement**: Migrated the separate Avail/EigenDA adapter and SDK flags plus Trails to the central immutable runtime policy. Structured stub adapters and the Avail SDK are restricted to explicit non-live simulation with visibly non-authoritative identifiers; EigenDA proxy and Trails provider paths require explicit configuration, validate provider responses, sanitize failures, and never fall back to synthetic success. Effective component mode, endpoint, credential/transport choice, timeout, polling, and DA routing configuration are locked after construction. Live DA consumers reject simulated receipts, mock Trails status cannot satisfy the public live-result boundary, and missing dependencies, authentication failures, or failed live DA routes cannot select a stub fallback. This slice does not close M1, F09, or F10; payment, bridge, escrow, interrupt/recovery, deployment preflight, and remaining client migrations are still pending.
- **M1.2a OMS identity and Phala TEE live-mode enforcement**: Migrated OMS and Phala/TEE selection to the central immutable runtime policy. Component mocks now require exact explicit flags and are rejected in staging, testnet, and production; provider failures and malformed responses fail closed without simulation fallback. OMS compliance consumers require live-provider provenance, and TEE proof generation/verification binds live attestation data to the root EOA plus service/delivery commitment. Simulated TEE proofs are labeled non-authoritative and rejected at submission. This slice strengthens INV-5 and INV-6 but does not close F09, F06, or M1; DA, Trails, payment, bridge, escrow, and remaining provider migrations are still pending.
- **M1.1 strict runtime mode and gateway demo containment**: Replaced permissive `VAMS_ENV` fallback parsing with one frozen, typed contract for `test`, `local`, `demo`, `staging`, `testnet`, and `production`. Missing, malformed, mixed-case, unknown, and live-plus-gateway-mock configurations fail closed. The gateway parses the policy before DA-audit construction or owned background startup, defaults its mock flag off, labels every response with sanitized runtime/evidence classification, and preserves deterministic F17 shutdown. High-risk provider/client migration remains scoped to M1.2; this slice does not claim full mock containment.
- **M0 discovery baseline closure**: Completed current-source classification of F01-F18. F17/F18 are remediated; F01-F16 are explicitly `REVALIDATED_OPEN` and remain assigned to M1-M9. The current-tree Gitleaks gate is exact at 0 first-party plus 479 reviewed vendor identities. Seven superseded M0.3/R7/R9 evidence-package test modules are retired through an exact no-glob pytest boundary while M0.4 remains active; the corrected root Python baseline passes 760 tests plus 37 subtests. This closes M0 only; T06, M1-M9, mock-mode promotion, governance/deployment ceremony, and every release gate remain open.
- **F17 gateway lifecycle closure**: FastAPI lifespan now deterministically owns offline-node cleanup and economics-keeper startup/shutdown; keeper waits are interruptible and the named worker is joined. Repeated TestClient lifecycles, the 39-test gateway suite, and the 8-test keeper suite pass with no surviving owned background activity.
- **F18 dependency-audit closure**: Final review accepted the fixed `pip==26.2` and `httpx2`/`httpcore2==2.12.0` CI path, retained both requirement audits, and confirmed the explicit unsuppressed installed-environment audit plus clean compatibility evidence. F18 is `REMEDIATED`; the missing hashed dependency lock remains an M7 reproducibility gap.
- **M0.4 aggregate current-tree vendor gate**: Added a pinned Gitleaks 8.30.1 CI gate and deterministic 479-record sanitized baseline covering the three independently reviewed OpenZeppelin ownership scopes. Git-tree provenance, deepest-child attribution, clean pins, blob hashes, identity bindings, and exact `0 + 161 + 160 + 158` counts fail closed; raw scanner payloads remain temporary. The auxiliary R9 validator stays outside CI and promotion trust.
- **M0.3c-R7 context and evidence-boundary hardening**: Added exact no-follow evidence topology validation and bound each custom-error fixture to its assertion, operation, deployed artifact, exact signature/selector, pinned declaration and caller blobs, and reachable inheritance/interface/library chain. Separate implementations agree on 158 findings; independent R8 review and all promotion gates remain open.
- **M0.3c-R5 adjudication hardening**: Closed the checksum-rebuilt schema bypasses and required content-addressed independent semantic attestation for every confirmed nested OpenZeppelin identity. Local verification retains 158 unsuppressed findings across 22 paths; independent M0.3c-R6 review and all promotion gates remain open.
- **M0.3c-R1 nested OpenZeppelin adjudication**: Added a Git-object-owned, content-addressed tranche for 158 findings across 22 paths in the nested OpenZeppelin submodule, excluding all three child gitlinks. Exact source review confirmed 83 expected-error assertions and 75 public ECDSA DER vectors. The unsuppressed scanner still reports every finding; no allowlist or vendor change was made. Independent review and all promotion gates remain open.
- **M0.3b-R1 direct upgradeable adjudication**: Added a provenance-owned, content-addressed adjudication tranche for 160 direct OpenZeppelin upgradeable findings across 24 paths, explicitly excluding nested gitlinks. Exact source review confirmed 83 expected-error assertions, 75 public ECDSA DER vectors, and 2 deterministic ERC-7201 storage constants. The unsuppressed scanner continues to report all findings; no allowlist or vendor change was made. Independent review and all promotion gates remain open.
- **M0.3a-R1 adjudication repair**: Replaced the placeholder OpenZeppelin scaffold with separate source-bound decisions, disposition-specific validation, sanitized blocker publication, and a content-addressed exact-set gate. Locally reviewed 161 findings across 23 paths as noncredential fixtures (86 error assertions; 75 public DER vectors). Pinned Gitleaks still reports 161 findings; no suppression was added. Focused tests passed 20/20 and existing Gitleaks tests 11/11. Independent review and M0/M7/T06/F18/promotion gates remain open; see `docs/remediation/m0_3a_r1/REVIEW.md`.
- **Working-tree inventory evidence**: Restored pinned Gitleaks 8.30.1 and completed the M0.2 staged inventory. The real tree yielded 479 redacted vendor findings; generated bytecode was excluded by construction. Findings remain unresolved.
- **Working-tree inventory path**: Added the M0.1 repository-native, redacted Gitleaks inventory and focused validation tests; generated bytecode and ignored build artifacts are excluded by construction, with checksum-verified staging and submodule provenance. The live scan remains pending when pinned Gitleaks is unavailable.
- **Complete-history secret coverage**: Updated the pinned Gitleaks gate to pass
  `--log-opts="--all -m"` before the repository target, covering every fetched
  ref and each merge-parent diff; workflow validation now rejects argument-order,
  ref, merge, duplicate-command, and target drift.

### Added
- **Deployment identity evidence**: Added `contracts/script/utils/AuthorityIdentityValidator.sol`
  and network-specific deployment-manifest validation. Polygon evidence binds
  each Safe proxy and singleton runtime code hash, exact owners/thresholds,
  timelock bytecode and roles, transfers, and deployer-role removal. Cardano
  evidence binds multisig credentials, validator CBOR/script hashes, governor
  and timelock scripts, and control handoffs without applying EVM Safe fields.
- **Runtime/privacy evidence inventory**: Added an AST-derived publisher
  inventory and artifact-bound v2 runtime/privacy schemas so new DA, Sentinel,
  or VDSO publication sinks cannot bypass review by omission.
- **VDSO evidence hardening**: Added `docs/adr/ADR-VDSO-001.md`, corrected
  review artifacts under `docs/team/vdso/`, and a provenance-bound evidence
  manifest/schema. The ADR is `Proposed` and authorizes only side-by-side
  canary implementation work; it is not deployment or testnet-readiness
  evidence.
- **`vams-vm/`**: Added the Rust 1.92 VIR-Core v1 reference foundation with
  restricted positional CBOR, raw domain-prefixed Keccak identifiers, explicit
  Polygon/Cardano authority epochs, bounded checked-integer execution, semantic
  receipts, shared golden vectors, and fail-closed SP1/RISC Zero placeholders.
- **`contracts/src/vdso/`**: Added side-by-side object, reservation, adapter,
  program, proof, capability-routing, and execution-kernel modules. The canary
  binds host and authority epoch, uses compare-and-swap object versions and
  fencing tokens, separates semantic transitions from settlement, and keeps
  ambiguous recovery locked unless execution or non-execution is verified.
- **
euron/vdso/` and `gateway/vdso.py`**: Added exact VIR intent encoding,
  height-aware expiry, body-bound secp256k1 requests, nonce/replay policy,
  deterministic capability routing, encrypted witness-sidecar handling,
  a ciphertext-only DA publication boundary, and shadow/canary workflow
  orchestration. Current Celestia/Near adapters are ineligible for VDSO live
  evidence; authoritative mode and unconfigured live cryptography fail closed.
- **`cardano/lib/vams/vdso.ak`**: Added the Cardano read/conformance boundary,
  shared intent vector, Polygon/Cardano wire mapping, and executable bridge
  proof/payload separation checks. Value-bearing `CONSUME` and `RESERVE` remain
  disabled for the initial Cardano canary.
- **`contracts/script/DeployVDSOCanary.s.sol`**: Added a Polygon Amoy-locked,
  empty-state deployment rehearsal that validates distinct Safe/timelock roles,
  performs role handoff, activates no adapter/verifier/program/domain, and
  leaves recovery abort disabled until a real non-execution verifier exists.
- **Documentation reality sync**: Added a canonical documentation index,
  current v0.8.0 architecture reference, versioning policy, machine-readable
  documentation manifest, and CI-checkable documentation validator.
- **`contracts/script/DeployTestnet.s.sol`**: Added the Polygon Amoy ceremony with on-chain Safe threshold validation, 48-hour timelock, treasury-only initial allocation, distinct emergency council, role handoff, and deployer postcondition checks.
- **`contracts/script/DeployTestnet.s.sol`** and **`docs/audit/testnet-profile.json`**: Disabled staking rewards for the first public-testnet profile and withheld staking minter authority, preventing reward accrual against a fully allocated fixed supply.
- **`scripts/audit/deployment_readiness.py`** and **`scripts/audit/economic_concentration.py`**: Added source-level ceremony enforcement and linked-owner, HHI, top-four, regional, thin-liquidity, and seven-day reward-return analysis.
- **`scripts/audit/run_economic_adversarial.py`** and **`docs/audit/economic-adversarial-report.json`**: Added a profile-bound, seeded 100,000-epoch campaign across five concentration and reward-loop attack classes.
- **Architecture and invariant evidence**: Added machine-readable v0.3.0-to-v0.8.0 traceability, a ten-invariant source/test index, a cross-boundary threat model, strict runtime/privacy/independent-review schemas, and CI validators.
- **`frontend-vite/src/config.js`**: Added an environment-bound, HTTPS-only production gateway origin and an explicit read-only testnet capability profile.
- **
euron/tests/test_delivery_proof_fail_closed.py`**: Added regression coverage requiring real TEE and ZK proof verifiers.
- **`docs/audit/`** and **`scripts/audit/audit_program.py`**: Added the 36-track testnet audit program, machine-readable control matrix, risk register, testnet profile, finding/evidence/deployment schemas, commit-bound evidence generation, structural regression tests, and a fail-closed readiness command.
- **`scripts/audit/audit_program.py`** and **`.github/workflows/security-gates.yml`**: Split promotion into `canary` and `public` readiness, require a clean commit, signed aggregate evidence, commit-bound artifact hashes, stage-specific deployment manifests, and cryptographic Cosign verification in the manual promotion job.
- **`docs/audit/INCIDENT_RESPONSE.md`**: Added severity definitions, first-15-minute containment, domain-specific recovery gates, and mandatory pre-testnet incident drills.
- **`docs/audit/agent-red-team-corpus.json`** and **`scripts/audit/validate_agent_red_team.py`**: Added 12 mandatory deny-class attacks covering prompt injection, capability escalation, identity/TEE failures, memory poisoning, reward hacking, bridge confusion, CHC spoofing, and duplicate side effects.
- **
euron/sentinel/world_state_fidelity.py`** and **
euron/sentinel/sentinel_node.py`**: Added telemetry-only world-state fidelity reporting for long-horizon agent audits, including state hashes, divergence step, invalid-action step, staleness, and false-progress scoring.
- **`contracts/src/registry/ServiceBlockRegistry.sol`** and **`contracts/src/interfaces/IServiceBlockRegistry.sol`**: Added EIP-712 SkillOps manifest metadata, permission bitmaps, verifier quarantine controls, and provisioning rejection for quarantined Service Blocks.
- **
euron/tests/test_world_state_fidelity.py`** and **
euron/tests/test_world_state_phase_boundary.py`**: Added deterministic world-state fidelity and phase-boundary regression coverage.
- **Cardano property tests**: Added seven seeded Aiken properties covering integer-square-root bounds, basis-point safety and monotonicity, inclusive ranges, strict bridge nonce ordering/replay rejection, and insurance payout caps.

### Changed
- **Credential rewrite authorization**: Made the local history-rewrite gate
  validate incident-bound credential-impact and maintenance records before any
  mutation. Placeholder approvals, incomplete identity/provider impact checks,
  freeze evidence bound to another `main`, standing ruleset bypasses, enabled
  Actions, and pre-approved remote force pushes now fail closed. Remote history
  mutation remains a separate explicit execution-time approval.
- **Credential rewrite path coverage**: Corrected the all-ref removal set to
  include the five legacy provider helpers under `scripts/`, and extended the
  narrow Gitleaks public-curve allowlist to its own generated regression
  fixture without weakening forbidden-fixture coverage.
- **Bare-mirror secret verification**: Made the sanitized TruffleHog wrapper
  detect bare repositories and select the scanner's explicit `--bare` mode,
  preventing a zero-event scanner error from being mistaken for a clean scan.
  Explicit repository overrides are limited to credential-free local file
  URIs, allowing encrypted Windows mirrors to be reached through a data-free
  directory junction.
- **Incident-preparation CI reproducibility**: Corrected Gitleaks fixture path
  anchoring, made Forge and Slither checkouts recursive, installed the pinned
  Foundry compiler for Slither, split reviewed Semgrep enforcement from
  non-blocking discovery, refreshed official GitHub Actions to immutable
  Node 24 release SHAs, pinned the Caddy testnet proxy image and client-CA
  validation, installed the pinned history-rewrite helper in every Python test
  context to eliminate environment-dependent skips, and updated vulnerable
  frontend dependencies, including later
  brace-expansion and js-yaml High-severity advisories discovered by a fresh
  audit. Secret scanner wrappers now use scan-root-relative paths and canonical
  file URIs across Linux and Windows; TruffleHog verification is disabled so
  candidate credentials are never sent to provider endpoints. The non-blocking
  discovery scan's Python 3.6 compatibility findings are recorded as not
  applicable to the pinned Python 3.12 runtime. The discovery scan now permits
  Semgrep's required registry metrics and treats operational scan errors as
  failures while keeping discovered findings non-blocking. Aggregate evidence is now
  generated and signed before the expected history-scan failure is enforced.
  SBOM, aggregate, and closed-canary signatures use the current Sigstore bundle
  format so Cosign 3 verification retains the certificate and transparency-log
  proof in one artifact.
  These controls do not waive historical credential findings or constitute
  testnet-readiness evidence.
- **Credential-shaped examples**: Gateway and PostgreSQL fixtures now construct
  URLs from separate fields or environment placeholders. The development DBOS
  setup requires caller-supplied local credentials instead of embedding a
  reusable password-shaped example.
- **Complete-history secret gates**: CI now installs checksum-verified Gitleaks
  8.30.1 and TruffleHog 3.95.9, fetches every branch and tag, runs Gitleaks with
  `--log-opts=--all`, and runs all TruffleHog result classes while retaining
  only sanitized candidate-free evidence.
- **Gateway and Neuron secp256k1**: Replaced the unpatched `python-ecdsa`
  dependency with `cryptography` ECDSA/SHA-256 primitives using the existing
  64-byte public-key and signature encodings, low-S normalization, and
  fail-closed rejection of malformed or high-S signatures.
- **Neuron Gateway transport**: Live Gateway clients now require HTTPS;
  plaintext is allowed only for loopback development. The direct HTTP heartbeat
  fallback was removed, and credential-bearing or ambiguous Gateway URLs are
  rejected.
- **Live DA boundary**: Celestia submission failures no longer fall back to mock
  receipts and exact retrieval is mandatory. Near non-mock submission is
  disabled until signed submission and retrieval exist. Mock, Avail, EigenDA,
  and release-ineligible VDSO receipts never report verified evidence.
- **VDSO Python execution boundary**: Capability requirements are now derived
  only from signed VIR intent fields. Canary orchestration must select eligible
  adapters before external work, rejects Cardano `CONSUME`/`RESERVE`, requires
  Tier 2 hybrid authorization for every non-`READ` access and every nonzero
  settlement-cost budget, and joins every nonzero signed `sidecar_root` to the
  exact uploaded encrypted sidecar content hash.
- **VDSO settlement metadata**: Aligned Python with VIR-Core's eight-field
  settlement encoding and added mandatory, distinct `bridge_proof_hash` and
  `payload_hash` semantics for INV-10.
- **VDSO Solidity admission and topology**: Restricted program activation to
  VIR-Core v1 and the three exact checked-in policy commitments, made the
  Polygon kernel reject all Cardano-authoritative state writes, and required
  an executable governance/open-executor timelock before role handoff. Proof
  configurations that require agreement now reject identical primary and
  secondary verifier addresses.
- **`docs/ARCHITECTURE.md`, `REPO_STATUS_REPORT.md`, and audit documents**:
  Added the proposed VDSO canary boundary while preserving the Polygon–Cardano
  dual-host allocation. Each state domain has one authoritative writer; a
  Cardano read-first integration phase does not demote its governance, identity,
  insurance, or native-validator authority.
- **Repository documentation**: Replaced stale deployment, API, test-count,
  local-path, and mock-integration claims with source-backed pre-testnet
  boundaries; historical version documents now carry lifecycle and verification
  metadata.
- **Nineteen upgradeable Solidity contracts**: Migrated from the removed OpenZeppelin 5.5 `ReentrancyGuardUpgradeable` dependency to the current storage-slot `ReentrancyGuard`, restoring full compilation.
- **`contracts/foundry.lock`**: Reconciled the OpenZeppelin Contracts revision with the parent repository's pinned gitlink (`239795bea728c8dca4deb6c66856dd58a6991112`) so dependency resolution uses the same immutable revision.
- **`contracts/src/token/VAMSToken.sol`**: Enforced the absolute $1 \times 10^9$ supply ceiling; only previously burned supply can be reminted within the annual cap.
- **`contracts/src/governance/VAMSTimelockController.sol`** and **`GovernorExecutor.sol`**: Raised the executable governance floor from 24 to 48 hours.
- **
euron/da/performance_audit.py`**: Restricted default live DA routes to Celestia/Near and made disabled explicit targets fail closed instead of silently rerouting.
- **
euron/sdk/semantic_mmu.py`**: Added safe HORMA paths, bounded hashed access logs, reviewer-authorized EvoMem persistence/L3 erasure, constrained HIPIF deletion, and session hard reset.
- **`frontend-vite/`**, **`gateway/server.py`**, and **`gateway/Caddyfile.testnet.example`**: Added production origin validation, stricter CSP, explicit live CORS configuration, bounded CORS methods/headers, content-length and chunked-body request limits, and browser permission restrictions.
- **`README.md`**: Replaced the stale fixed test-count badge with the 36-track audit-program status and linked the executable testnet assurance program.
- **`audit.md`** and **`REPO_STATUS_REPORT.md`**: Reclassified v0.6.0 test totals as historical evidence, made current CI verification deployment-blocking, and aligned Phase 6 priorities with the 36-track program.
- **`.github/workflows/security-gates.yml`**: Restricted the lightweight `Docs Verification` path to `docs/team/**/*.md` only; funding/proposal material no longer qualifies for docs-only bypass.
- **`.github/workflows/security-gates.yml`**: Added VDSO evidence tests and a
  pinned Rust 1.92 VIR-Core format/check/clippy/test job to the aggregate
  security-evidence and SBOM dependency graph.
- **`contracts/CONTRACTS.md`**: Replaced stale deployed/ready language with a pre-testnet deployment evidence register for Polygon Amoy and Cardano Pre-Prod, including pending fields for addresses, tx hashes, verification status, Safe/multisig ownership, and timelocks.
- **`docs/GATEWAY_HARDENING_BLUEPRINTS.md`** and **`gateway/Caddyfile.testnet.example`**: Added the loopback-Uvicorn-behind-Caddy deployment profile and proxy-set mTLS certificate headers expected by the gateway.
- **`REPO_STATUS_REPORT.md`**: Rewrote the repository status report for the July 2026 public testnet launch window with commit-history chronology, current component maturity, verified blockers, and gated roadmap language.
- **`.github/workflows/security-gates.yml`**: Aligned CI with the current frontend and Cardano toolchains by moving frontend verification to Node.js 22, pinning Aiken to `v1.1.21`, and using `aiken check` as the Aiken verification command.
- **`.github/workflows/security-gates.yml`**: Replaced all mutable GitHub Action refs with exact commits, replaced the removed `txpipe/setup-aiken` action with the official Aiken action, and pinned Foundry and Python security-tool versions.
- **`cardano/aiken.toml`**, **`cardano/aiken.lock`**, and **`.github/workflows/security-gates.yml`**: Pinned the official `aiken-lang/fuzz` v2 package and made the Cardano gate reproducible with seed `20260713` and 250 successful cases per property.
- **
euron/requirements.txt`**: Declared 
umpy` and `scikit-learn` for the intelligence-layer modules and tests that already import vector math and Incremental PCA dependencies.
- **
euron/da/models.py`**: Included Sentinel telemetry extras in deterministic DA audit report serialization so fidelity and SkillOps-related telemetry can be committed in report hashes.
- **
euron/services/registry_client.py`**: Extended Service Block metadata with deterministic SkillOps manifests and fail-closed permission-scope validation.

### Security
- **Credential-history eradication preparation**: Removed the 1,267-file
  tracked `.foundry/` vendor tree, added two exact rule-targeted Gitleaks
  allowlists with negative regressions, added all-ref rewrite safeguards with
  an external hashed replacement map, and upgraded incident evidence to schema
  v4 for two permanently decommissioned PEM identities and bounded Infura
  revocation timing.
- **Secret-history prevention**: Added fail-closed checks rejecting PEM/vendor/
  legacy-helper paths, concrete credential-shaped URI literals, replacement
  maps, and replacement-map directives in tracked content or evidence.
- **Historical secret gate**: A fully redacted Gitleaks v8.30.1 scan of all 82
  reachable commits found 1,734 matches, including two historical PEM
  private-key findings. `docs/audit/GITLEAKS_ADJUDICATION.md` blocks release
  pending rotation, role-impact review, coordinated history cleanup, and clean
  Gitleaks/TruffleHog rescans; no blanket baseline was added.
- **Secret-scanner reproducibility**: Pinned the workflow runtime versions to
  Gitleaks 8.30.1 and TruffleHog 3.95.9 instead of inheriting mutable scanner
  defaults from otherwise commit-pinned actions.
- **Safe/timelock identity**: `DeployTestnet.s.sol` and
  `DeployVDSOCanary.s.sol` now reject interface-shaped impostors by checking
  proxy runtime code, singleton identity/runtime code, exact owner counts and
  thresholds, and the compiled VAMS timelock runtime before rehearsal or role
  handoff.
- **VDSO scanner remediation**: Explicitly initialized recovery-verifier state
  and require the execution kernel to consume a successful proof-router result.
  Slither's configured fail-high gate reports zero high findings; all 19
  residual medium results are documented in `docs/audit/SLITHER_ADJUDICATION.md`.
- **VDSO DA evidence gate**: Current `NearDAAdapter` and
  `CelestiaDAAdapter` implementations are explicitly blocked from encrypted
  VDSO sidecar publication. A replacement route must inject receipt-verifier
  and blob-retriever observers that are not bound to the submitting adapter and
  establish exact retrieval-bound evidence; adapter self-verification,
  `mock_mode`, and a receipt's `verified` flag are not accepted as proof. The
  runtime blocks directly or partially bound methods; independent operational
  and deployment provenance remains a canary-admission review requirement.
- **VDSO implementation-identity gate**: The empty deployment activates no
  adapter or verifier. Upgradeable proxy implementations remain ineligible
  because an address codehash does not pin the proxy implementation; live
  activation requires an independently reviewed immutable direct deployment.
  Safe/timelock interface responses are source-level rehearsal checks only;
  deployment still requires known implementation bytecode and instance/role
  evidence.
- **VDSO canary controls**: Implemented host/epoch binding, non-timeout
  reservation recovery, destination fencing, proof/payload separation,
  classical XChaCha20-Poly1305 sidecar encryption, hybrid-suite binding for
  every Tier 2 or nonzero-settlement-cost authorization, separate
  authorization/proof/settlement labels, and fail-closed rejection of mock
  evidence. Reviewed HPKE, ML-DSA, and proof
  backends remain unconfigured; the code blocks rather than substitutes mocks.
- **
euron/sdk/interrupt_handler.py`**, **
euron/storage/arweave.py`**, and **
euron/payments/delivery_proof.py`**: Excluded incomplete live economic routes and changed TEE/ZK delivery proofs from soft acceptance to verifier-required failure.
- **`contracts/script/DeployVAMS.s.sol`**: Blocked the second legacy broad deployment path by default.
- **
euron/da/models.py`**: Added bounded scalar KPI sanitization before public DA serialization, rejecting raw world-state traces, prompts, credentials, nested payloads, non-finite numbers, and oversized values while retaining benchmark evidence.
- **
euron/da/models.py`**: Replaced arbitrary telemetry serialization with explicit schemas for world-state fidelity, continual-learning gain, and anomaly fields; public KPIs no longer accept free-form strings.
- **`contracts/script/DeployV2.s.sol`**: Blocked the legacy deployer-controlled deployment profile by default; public testnet requires a separate audited Safe/timelock ceremony.
- **`.github/workflows/security-gates.yml`** and **`scripts/security/`**: Added Slither, Semgrep, TruffleHog, default credential, public-content policy, mock-mode promotion, and Caddy config gates.
- **`gateway/server.py`**: Live environments now reject wildcard CORS origins.
- **`scripts/audit/economic_concentration.py`**: Require beneficial-owner attribution for reward flows and only flag sub-seven-day returns when the return recipient is the operator owner, eliminating unrelated-transfer false positives.
- **`RegionAwareDEC.sol`**: Made 30% the immutable governance ceiling for regional emissions instead of allowing configuration up to 100%, preserving INV-1 under privileged calls.
- **
euron/sdk/sequence_wallet.py`**: Restricted session validity to 1-24 hours and rejected empty or non-core contract allowlists, preserving INV-3 and INV-4.
- **
euron/trust_plugins/tee_plugin.py`**: Removed agent/session fallback identity and require an explicit non-zero root EOA for TEE proof encoding, preserving INV-6.
- **`CommitRevealOracle.sol`**: Added permissionless post-deadline resolution to an immutable fallback value with replay protection, preserving INV-7 without caller-selected stale values.
- **`.github/workflows/security-gates.yml`**: Removed direct workflow-input interpolation from the readiness shell step, defaulted non-dispatch runs to the canary stage through a quoted environment variable, and excluded generated Foundry/Vite caches from owned-source Semgrep analysis.
- **`.github/workflows/security-gates.yml`**: Routed event names and pull-request base/head SHAs through step environment variables before shell use, eliminating the remaining direct GitHub-context interpolation from change-classification scripts.
- **
euron/sdk/oms_identity.py`**, **
euron/sdk/trails_client.py`**, and **
euron/payments/coinme_client.py`**: Removed placeholder API-key fallbacks and fail closed outside mock mode when explicit live credentials are missing.
- **
euron/services/registry_client.py`**: Service Blocks now expose fail-closed memory policy metadata to prevent unreviewed persistent prompt-memory mutation in live paths.
- **
euron/sentinel/sentinel_node.py`**: Added telemetry-only `continualLearningGain` reporting without slashing, reward, routing, or regional-bonus impact.
- **`contracts/src/trust/plugins/WorldIDPlugin.sol`**: Replaced structural proof acceptance with the configured World ID verifier, binding proofs to the service/delivery signal and the VAMS action external nullifier; malformed proofs and verifier failures now return false.
- **Solidity CEI hardening**: Added missing reentrancy guards to Service Block registration, SLA slash retries, and security-budget updates; reordered payment, escrow, staking, hardware, Sentinel, and registry effects before external interactions.
- **Solidity precision and storage**: Replaced sequential voting-power divisions with `Math.mulDiv`, consumed provider rejection reasons, cached storage-array lengths, and made constructor-only references immutable.
- **
euron/intelligence/skill_discovery.py`**: Replaced executable pickle persistence with a bounded, schema-checked NumPy archive loaded with `allow_pickle=False`.
- **
euron/sentinel/sentinel_node.py`**: Moved weighted challenge selection and scheduler jitter to OS-backed `SystemRandom` and prevented negative scheduler delays.
- **
euron/sdk/akash_orchestrator.py`**: Resolves and verifies the Akash CLI as an absolute regular-file path before live subprocess execution and applies execution timeouts.
- **`gateway/server.py`** and **
euron/gateway/server.py`**: Tightened default local/direct server binds from `0.0.0.0` to `127.0.0.1` to satisfy the security gate and keep direct startup loopback-first.
- **
euron/storage/local.py`**: Normalized heartbeat IDs to integers before constructing the parameterized SQLite `IN` clause.
- **
euron/sentinel/challenges/latency_probe.py`**: Switched simulated RTT measurement to the monotonic performance clock; the success-path regression now injects a deterministic clock and async sleep so concurrent analyzer load cannot create a false zero-score failure.
- **
euron/runtime_safety.py`**: Added centralized live-environment safety gates for `VAMS_ENV=staging`, `VAMS_ENV=testnet`, and `VAMS_ENV=production`.
- **`gateway/server.py`**: Gateway DA audit initialization now rejects mock audit mode in live environments before any mock DA receipt can be emitted.
- **`gateway/server.py`**: Live environments now require `GATEWAY_ADMIN_DID`, reject Basic Auth on protected control-plane routes, enforce single-use DID signatures within the 5-minute timestamp window, and bind direct Uvicorn startup to `127.0.0.1`.
- **`gateway/server.py`**: Live `/heartbeat` telemetry now requires proxy-verified mTLS client certificate headers and an allowlisted certificate fingerprint via `GATEWAY_HEARTBEAT_CERT_FINGERPRINTS`.
- **
euron/sdk/oms_identity.py`**, **
euron/sdk/trails_client.py`**, **
euron/payments/coinme_client.py`**, **
euron/sdk/avail_substrate.py`**, **
euron/sdk/eigenda_kzg.py`**, **
euron/sdk/iagon_storage.py`**, **
euron/sdk/phala_tee.py`**, and **
euron/bridge_executor.py`**: Added fail-closed live-mode checks that reject mock clients, demo credentials, mock bridge verification, and mock TEE execution in staging/testnet/production.
- **
euron/da/adapters/avail_adapter.py`** and **
euron/da/adapters/eigenda_adapter.py`**: Explicitly block structured stub adapters from instantiating in live environments.
- **`contracts/src/registry/ServiceBlockRegistry.sol`**: Service Block provisioning now fails closed when verifier-governed quarantine is active.

### Testing
- **VDSO focused verification**: Python passed 65/65 VDSO boundary tests and
  Aiken passed all 10 VDSO conformance definitions. Changed VDSO/deployment
  Solidity paths pass scoped formatting; repository-wide formatting retains
  unrelated legacy drift.
- **Solidity verification status**: Final-tree `forge build --sizes` passed and
  `forge test -vvv` passed 693/693 tests across 40 suites. The
  `VAMSExecutionKernel` runtime is 10,467 bytes with 14,109 bytes of EIP-170
  margin. Exact-commit CI evidence remains required.
- **Audit controls**: Fifteen readiness tests, two deployment-source tests, two traceability tests, one workflow-supply-chain test, eight economic-concentration tests, and two adversarial-campaign tests passed; the 12-class agent corpus and first-party security scans also passed.
- **Economic adversarial campaign**: The seed `20260711` campaign passed 100,000 epochs with 20,000 detections per attack class, zero misses, and zero baseline false positives; synthetic evidence does not replace live beneficial-owner attestations.
- **Invariant regressions**: Focused runs passed 16 regional-emission tests, 3 stale-oracle tests, and 52 session-key/TEE/SDK tests.
- **Cardano verification**: `aiken check --deny --seed 20260713 --max-success
  250` passed 43 unit tests and 7 properties over 1,750 generated cases; all
  50 test definitions passed. Transaction-level validator state-machine
  properties remain required.
- **Frontend verification status**: 
ode --check` passed for the Vite/config modules, 
pm audit --audit-level=high` found zero vulnerabilities, and the Vite 7.3.6 production build passed with 1,712 modules transformed.
- **
euron/tests/test_performance_audit.py`**: Added regression coverage proving sensitive and structured KPI data cannot survive DA report serialization.
- **Security scripts**: Verified `default_credential_scan.py`, `public_content_policy_scan.py`, and `mock_mode_promotion_scan.py` passed locally.
- **World-state and SkillOps targeted tests**: Verified `pytest -q neuron/tests/test_service_blocks.py neuron/tests/test_world_state_fidelity.py neuron/tests/test_world_state_phase_boundary.py` passed with 31 tests.
- **Python aggregate**: Workspace-local componentized runs passed 684/684
  substantive tests (236 Neuron group A, 395 Neuron group B excluding the
  isolated latency case, 52 scripts, and the hardened latency regression).
  Monolithic sandbox runs were blocked by temporary-directory ACL errors, not
  test assertions; exact-commit CI execution remains required.
- **Python security gates**: Bandit reports no qualifying medium/high-confidence
  issue. Both Gateway and Neuron requirement sets pass `pip-audit` with no known
  vulnerabilities after removal of `python-ecdsa`.
- **VIR-Core verification**: Rust 1.92 Linux execution passed all 34/34 tests;
  format, workspace/all-target check, and Clippy with `-D warnings` also pass.
- **Cross-language analyzers**: Slither 0.11.5 passes the fail-high gate with 19
  adjudicated medium findings. Semgrep 1.169.0 reports zero findings across 444
  tracked files/520 rules and 61 explicit untracked VDSO files/314 rules. All
  17 timed-out rule/file pairs were separately source-reviewed with no confirmed
  vulnerability and are retained in `docs/audit/SEMGREP_ADJUDICATION.md`;
  exact-commit CI rerun and external acceptance remain required.
- **World ID regressions**: Added five Foundry tests covering zero-verifier rejection, verifier-bound acceptance, malformed input, wrong action scope, and verifier-revert failure.
- **Syntax/hygiene**: Verified touched Python files with `py_compile`; `git diff --check` passed.
- **Docs-only PR gate**: Planned verification with `git diff --check` over `docs/team` changes only; full gates remain active for pushes to `main` and PRs with code/config/funding changes.
- **Security/build gates**: Current first-party default-credential, mock-mode,
  and public-content scans, Aiken checks, full pytest, Bandit, evidence/schema,
  documentation, audit-program, invariant-traceability, workflow-pinning,
  deployment-source, and agent-red-team gates passed. Pip-audit, final Foundry,
  Linux Rust, Slither, and broad Semgrep scans now pass their configured local
  thresholds. Historical Gitleaks, TruffleHog, signed SBOM, exact-commit CI,
  and aggregate Cosign evidence remain blocking.
- **
euron/tests/test_runtime_safety.py`**: Added regression tests for local mock allowance and live-environment rejection across OMS, Trails, Coinme, DA adapters, DA audit logging, and bridge mock paths.
- **
euron/tests/test_gateway_auth_hardening.py`**: Added regression tests for DID signature replay rejection, live-mode Basic Auth rejection, live-mode loopback binding, and live heartbeat client certificate enforcement.

## [0.8.0] - 2026-06-23

### Added — Phase 7: CHC Cognitive Scoring & 6-Axis Composer Scoring
- **
euron/composer/models.py`**: Added `cognitive_requirements` (`Dict[str, float]`) to `InstanceBlueprint` for defining agent capability targets.
- **
euron/composer/scorer.py`**: Implemented the 6-axis composition ranking engine with the **Cattell-Horn-Carroll (CHC) cognitive shortfall scoring formula**:
  $$S_{\text{cog}} = 1.0 - \frac{1}{|D_{\text{req}}|} \sum_{d \in D_{\text{req}}} \max\left(0, \text{Req}_d - \text{Profile}_d\right)$$
- **
euron/composer/scorer.py`**: Implemented dynamic weights scaling that adjusts weights proportionally (dedicating 10% to skills and 10% to cognitive requirements when present) while maintaining the 1.0 sum constraint, preserving backward compatibility.
- **`gateway/server.py`**: Extended `NodeInfo` dataclass and heartbeat registration payloads to accept node cognitive profiles, TEE passports, credit scores, registered skills, hourly cost, and regions.
- **`frontend-vite/src/App.jsx`**: Built a new split-screen dashboard layout with an interactive SVG-based Radar Chart visualizing the 10 CHC domains (Decagon Graph) in light/dark modes.

### Testing
- **`scripts/docs/validate_vdso_evidence.py`**: Added fail-closed validation for
  discussion hash/size/line provenance, exact eight-principle coverage,
  repository line citations, controlled maturity labels, dual-host authority,
  proposed readiness status, ADR requirements, and INV-1 through INV-10
  traceability, with stdlib regression tests.
- Fully verified via 28 unit tests in `test_chc_scoring.py` and `test_composer_scorer.py` verifying dynamic scaling, shortfall math, edge cases, and 100% test success rate.

## [1.3.0-oms] - 2026-05-06

### Added — Phase 1: Two-Layer Identity Model
- **
euron/sdk/signer.py`**: `SignerInterface` (ABC), `EOASigner`, `SessionKeySigner`, and `SignerFactory`
  — abstracts signing away from raw `from_key()` calls across all transactional Python modules.
- **`VAMSAgentRegistry.sol`**: New `authorizedWallet` field on the `Agent` struct;
  `setAuthorizedWallet(bytes32 agentId, address wallet)` owner-only setter;
  `isAuthorizedCaller(bytes32 agentId, address caller)` view function;
  `AuthorizedWalletSet` event.

### Added — Phase 2: Trails Transport Integration
- **
euron/sdk/trails_client.py`**: Thin `TrailsClient` wrapper around OMS Trails API with
  `submit_intent()`, `get_status()`, and mock mode for testing.
- **`BridgeExecutor.py`**: `TRAILS` transport added to `BridgeTransport` enum;
  `TRANSPORT_MATRIX` updated to prefer Trails for the 4 AggLayer routes (Ethereum, Polygon, Arbitrum, Base)
  with AggLayer as fallback; `TrailsTransportHandler` class.

### Added — Phase 3: Sequence ERC-4337 Session Keys
- **
euron/sdk/sequence_wallet.py`**: `SequenceWalletManager` (ERC-4337 smart wallet lifecycle)
  and `SessionKeyManager` (scoped session keys with per-TrustTier value limits: BRONZE=100 $VAMS,
  SILVER=1K, GOLD=50K, PLATINUM=unlimited; 24h validity window default).

### Added — Phase 4: Coinme Fiat Rails + Insurance Fund Yield
- **
euron/payments/coinme_client.py`**: `CoinmeClient` — fiat-to-crypto on-ramp API wrapper
  with `create_checkout()`, `get_conversion_rate()`, and webhook handler.
- **
euron/payments/universal_topup.py`**: `UniversalTopUpManager` — orchestrates fiat → $VAMS
  conversion, applies gas abstraction premium (2–7%), deposits to agent `ComposedSettlement` escrow.
- **
euron/economics/yield_manager.py`**: `YieldManager` — manages Insurance Fund idle capital
  in OMS yield vaults; enforces ≤30% allocation cap and instant-withdrawal requirement.

### Added — Phase 5: Stablecoin Payouts + Enterprise RPCs + Identity
- **
euron/payments/stablecoin_payout.py`**: `StablecoinPayoutManager` — provider opt-in
  to auto-convert $VAMS rewards to USDC or USDT via OMS stablecoin settlement rails.
  Exposes `PayoutMode` enum: `VAMS_ONLY`, `STABLECOIN`, `HYBRID`.
- **
euron/sdk/oms_identity.py`**: `OMSIdentityVerifier` — institutional KYC/KYB verification
  via OMS Compliance module. Fail-closed: returns `False` on any network or parse error.
- **`docs/team/ARCHITECTURE_v0-6-0.md`**: New team architecture addendum covering all 5 OMS phases,
  updated CLR v3.1 decision tree, and security boundary documentation.

### Changed
- **
euron/payments/x402.py`**: Default signer switched from `EOASigner` to `SessionKeySigner`
  for payment operations; root EOA retained for channel creation only.
- **
euron/neuron.py`**: `SequenceWalletManager` initialised alongside existing components;
  session signer passed to `X402Client` and `trust_aggregator`.
- **
euron/clr_router.py`**: P3 (`P3_INSTITUTIONAL_COMPLIANCE`) routing now gates on
  `OMSIdentityVerifier.is_verified(agent_id)` in addition to the existing `PLATINUM` trust tier
  check. Non-verified addresses are rejected fail-closed.
- **
euron/chain_oracle.py`**: OMS enterprise RPC endpoints replace public fallbacks for all
  Polygon-ecosystem chains; SLA monitoring added with per-endpoint uptime/latency tracking.
- **`contracts/src/economic/RewardDistributor.sol`**: `payoutPreference` mapping
  (`address → PayoutMode`); `setPayoutPreference(PayoutMode)` function; `claimRewards()` now
  routes through conversion contract when preference is `STABLECOIN` or `HYBRID`.
- **`contracts/src/economic/VAMSInsuranceFund.sol`**: `YIELD_MANAGER_ROLE` added;
  `deployToYield(address vault, uint256 amount)` — capped at 30% of `totalFundBalance()`;
  `withdrawFromYield(address vault, uint256 amount)` — instant withdrawal path;
  `totalFundBalance()` now includes deployed capital via `totalDeployedBalance()`.
- **`contracts/src/registry/VAMSAgentRegistry.sol`**: `registerAgent()` sets `authorizedWallet`
  to the Sequence smart wallet address; all `msg.sender` checks accept authorized wallet.

### Security
- `OMSIdentityVerifier.is_verified()` is fail-closed: any exception (network, parse, timeout)
  returns `False`, preventing unauthenticated access to P3 institutional routes.
- Session keys are strictly scoped: value limit, allowed contract whitelist, and 24h validity
  window enforced by `SessionKeyManager`; limits scale with TrustTier.
- Insurance Fund yield deployment capped at ≤30% of `totalFundBalance()` to preserve solvency
  for concurrent insurance claims.
- TEE attestation binding preserved: `tee_plugin.py` always binds attestations to root EOA,
  not to session wallet identity.

### Testing
- **1,083 total tests passing** (619 Forge + 37 Aiken + 427 Pytest — zero regressions).
- New test coverage: `test_fiat_yield.py` (Coinme, UniversalTopup, YieldManager),
  `test_sequence_wallet.py` (session keys, tier scopes, expiry),
  `test_trails_client.py` (TrailsClient mock + fallback),
  `test_clr_v3.py` (19 tests — CLR P3 OMS gate, all routing paths, bridge regression guards).

---

## [1.2.0-autoskill] - 2026-04-29

### Added
- **Intelligence Layer (
euron/intelligence/`):** New AUTOSKILL-powered subsystem implementing
  PCA-based model-native skill discovery, activation-space anomaly detection, and
  inference-time steering based on the AUTOSKILL paper methodology.
  - `ActivationCache`: Thread-safe ring-buffer capture of final-layer model activations
    (framework-agnostic, numpy interface, `.npz` export)
  - `SkillDiscovery`: `IncrementalPCA` pipeline extracting orthogonal skill direction vectors
    with `.pkl` persistence and streaming support
  - `ActivationAnomalyDetector`: Mahalanobis-distance-based anomaly scoring in PCA skill space
    (3-sigma default threshold, per-component breakdown via `AnomalyReport`)
  - `SteeringEngine`: Non-destructive inference-time bias injection (`h ← h + α·v`) with
    hard `max_alpha` safety cap (default `0.3`) and unit-normalized direction vectors
- **`docs/INTELLIGENCE_LAYER.md`**: New comprehensive module guide covering all 4 classes,
  API references, integration examples, and safety considerations.
- **`docs/team/ARCHITECTURE_v0-5-0.md`**: New team architecture addendum documenting the
  Intelligence Layer data flow, modified subsystems, and validation results.
- **`docs/NODE_OPERATORS.md`**: Supplier guide for configuring and operating Intelligence
  Layer-enhanced Sentinel nodes.

### Changed
- `VAMSSentinelNode.audit_node()`: Audit reports now optionally include `activation_anomaly_score`
  (Mahalanobis distance) and `adversarial_flag` (bool) when an `ActivationAnomalyDetector` is
  configured. Existing behavior is fully preserved when no detector is provided.
- `VAMSSentinelNode.run_scheduler()`: Challenge selection is now AUTOSKILL-informed, weighting
  challenge types toward historical node skill gaps (`_node_skill_gaps` dict). Falls back to
  cryptographically-random selection when no detector is configured.
- `CandidateScorer`: Added 5th scoring dimension `skill_alignment` using cosine similarity
  between blueprint `skill_vector` and node `skill_profile`. Weight defaults to `0.0` for
  full backward compatibility with existing integrations.
- `InstanceBlueprint`: New optional field `skill_vector: Optional[List[float]] = None`.
- `ScoredCandidate`: New field `skill_alignment_score: float = 0.0`.
- `ScorerWeights`: New field `skill_alignment: float = 0.0`.

### Security
- `SteeringEngine` enforces hard alpha cap (`max_alpha`, default `0.3`) preventing adversarial
  agents from injecting catastrophic steering magnitudes. Values above `max_alpha` are silently
  clamped and logged as warnings.
- All `SteeringEngine` direction vectors are unit-normalized before application, ensuring
  consistent, bounded impact regardless of raw PCA component magnitudes.
- Validated: `α=0.5` steering achieves +9.2% security task accuracy with <1% degradation on
  unrelated capabilities (formatting tasks). Full safety validation in
  
euron/tests/test_steering_prototype.py`.

### Testing
- 373 tests passing (zero regressions across all existing suites).
- Added 
euron/tests/test_steering_prototype.py`: Phase 4 prototype validation tests.

---

## [1.1.0-audit-remediated] - 2026-04-26

### Security & Audit (Sprints 0-5)
- **Comprehensive Audit Remediation:** Successfully resolved all 68 security findings identified during the Pre-Testnet Security Audit (Phases 1-8).
- **Critical Fixes:** Resolved ECDSA signature recovery in `BatchSettlement`, fixed insurance fund drain vulnerability in `TransactionCompensation`, decoupled bridge proofs, and enforced on-chain stake verification in `governor.ak`.
- **Economic Invariants:** Enforced lock periods for `VAMSStaking` emergency withdrawals, bounded rewards with strict token deposits, and implemented strict dispute solvency rules in `X402EscrowManager`.
- **Infrastructure Security:** Implemented `_disableInitializers()` across all 16 target contracts, integrated proper role grants for 14 roles via `DeployV2.s.sol`, and securely wired all pausable sentinel targets.
- **Off-chain Hardening:** Corrected MEV protection configurations, replaced predictable PRNGs in Sentinels with cryptographically secure generation, and improved secondary transport fallback mechanism in `BridgeExecutor`.

## [1.0.0-icn] - 2026-04-09

### Added
- **Multi-DA Performance Anchor:** Implemented `da/PerformanceAnchor` to natively anchor SLAs to Celestia, Polygon DA, and EigenDA, providing hardware transparency.
- **Resource Composition Engine:** Created `composer/VAMSComposer` to automatically package compute requests into matching Blueprint profiles against available nodes.
- **Master Hybrid Escrow Model:** Deployed `ComposedSettlement.sol` replacing point-to-point escrows with atomic multi-party payments for orchestrated nodes.
- **Regional Dynamic Emissions:** Launched `RegionAwareDEC.sol` and `RegionalIncentives.sol` to align inflation rewards with geographic under-served capacity, reducing datacenter centralization.
- **Service Block Registry:** Created `registry/ServiceBlockRegistry.sol` enabling builders to package verified code execution environments and earn up to 50% revenue share.
- **Sentinel Enforcer Loop:** Added `sentinel/SLAEnforcer` module executing probabilistic slashing queries based on verifiable downtime logs.
- Added extensive Documentation: `docs/API_REFERENCE.md`, `docs/DEVELOPER_GUIDE.md`, `docs/team/ARCHITECTURE_v0-4-0.md`.

### Changed
- Converted monolithic 
euron/` Python backend into independent modular logic layers: `da/`, `composer/`, `economics/`, `services/`, `sentinel/`.
- Updated `gateway/server.py` to route modular endpoints across `/da`, `/composer`, `/economics`, `/services`, `/sentinel`.
- Unified the smart contract structure under `contracts/src/` with clear stratifications: `da/`, `economic/`, `infrastructure/`, `sentinel/`.
- Relicensed the codebase to emphasize open verifiable logic.

### Deprecated
- `VAMS_BountyEscrow` is fully deprecated. Use `ComposedSettlement`.
- The older Static Inflation schedules inside the token contract are deprecated for dynamic emissions (`RegionAwareDEC.sol`).
- Monolithic agent tasks are formally deprecated in favor of Composed Blueprints.

### Removed
- Legacy static `SLA` configurations which have been centralized in the multi-da anchor logs.
# Unreleased
- Ensure gateway application lifespan owns and deterministically stops the
  offline-node cleanup task and economics keeper.
- Harden CI dependency pins and audit coverage: pin pip 26.2 and httpx2 2.12.0,
  and audit the installed Python environment with the explicit PyPI service.


### Security — M0.3c-R3 evidence validation

- Hardened nested OpenZeppelin adjudication evidence with closed schemas, duplicate-key rejection, bounded metadata, and strict identity scalar validation.
- Replaced the duplicated reconciliation semantics with an independent JavaScript token parser and cryptography DER parser while preserving the 158-record exact set.
- Added before/after bypass regressions and fresh-scanner semantic-oracle assertions. This is local remediation evidence only; promotion gates remain open.

### M0.3c-R9 evidence hardening

- Bound M0.3c evidence validation to one immutable descriptor-based snapshot with final lifecycle stability checks.
- Replaced duplicated oracle semantic catalogs with independent derivation from pinned test and Solidity Git objects.
- Added deterministic race and semantic-independence regressions. No scanner suppression, vendor, production, runtime, gateway, CI, deployment, or mock-mode behavior changed.

- **M3.2a-R15 oracle trust remediation**: fixed-path/hash-bound datum registry selection, exact governed reserve equality, authenticated authority pre-state checks and frozen transition output-count binding. Focused tests pass 10/10. This is local remediation only; independent R16 review is next, M3.2b is not authorized, and F01-F05/M3 remain open.

### M3.2a-R19 oracle FIFO hardening — 2026-09-27

- Added nonblocking descriptor-bound final registry opens so FIFO and other non-regular registry objects reject before any read.
- Added independent FIFO/non-regular and address/CBOR mutation regressions. This is local remediation evidence only; independent R20 review is next and F01-F05/M3 remain open.

### M3 F04-R5 production hardening - 2026-09-29

Applied scoped identity-mint authorization, trusted authority anchoring, non-self-referential commitment projection, burn linkage and registration value conservation. Regenerated the pinned-Aiken blueprint with seven trusted parameters. The compiled 49-row evaluator remains blocked by missing reviewed ScriptContext fixtures; F04/M3 stay open and promotion remains not ready.
### M3 F04 compiled-contract remediation R6 - 2026-09-29

- Added total AgentDatumV1 validation at direct mint/burn and registry datum
  seams, deterministic raw-DID identity binding, and direct-burn payout/value
  conservation; regenerated the pinned-Aiken blueprint and reconciled forward
  provenance without changing the lockfile.
- Kept the accepted 49-row fixture byte-for-byte unchanged while making the
  current disposable evaluator derive artifact hashes and record three explicit
  legacy mint-side burn expectation amendments. Supplemental coverage executes
  28/28 compiled cases. Independent R6 review passed; F04 remains open pending
  a separate documentation/status closure record. F01-F05, M3,
  Deposit/ExecuteIntent, Pre-Prod admission and promotion remain open or not
  ready. INV-1 through INV-10 and mock behavior are unchanged.

### INV-3 session expiry boundary

- Session keys now fail closed at the exact expires_at timestamp, so the expiry instant is outside the valid window. The change preserves the 24-hour maximum and existing contract allowlist checks.


### M5.1a PostgreSQL transaction boundaries

- Commit successful PostgreSQL authority-repository transactions; roll back body and commit failures and attempt connection cleanup on all paths. A database commit failure after a provider effect stays unresolved until reconciliation by the same operation ID. Controlled-driver regressions pass; PostgreSQL durability, concurrency, restart, provider/DA, independent-observer, and full M5 qualification remain pending.


### M7 Sentinel package-import correction - 2026-10-06

- Resolve HardwareRegistryClient through the canonical neuron.sdk package in neuron.sentinel. The three previously blocked M1/runtime/F17 and broad Python selectors now collect and pass. The dedicated legacy test_sentinel.py selector still fails collection because it imports sentinel.sentinel_node as a top-level alias; no test import or Sentinel behavior was changed.
### M7 F04 anchor foundation R1 offline gate — 2026-10-08

- Recorded candidate anchor types, S0 lock, P0 issuance policy and a scoped offline build runner. The runner’s network/read-only boundaries passed independent review. In the first corrected-input run, pinned Aiken version exited 0 and aiken check exited 1 without a retained compiler diagnostic; the runner stopped before build. The cause is inconclusive, so compiled behavior, fixtures, mutations and reproducibility remain unestablished. F04 remains open; readiness remains NOT READY.

### Tokenomics hardening reconciliation - 2026-10-08

- Added a source-backed economic gap/acceptance matrix and linked it from the
  remediation plan, status and handoff. Existing economic gates now explicitly
  track vesting/GMV, unbonding, supply/emissions, fee phases/actual burns, reward
  funding, delegation, governance and DEC acceptance. This is documentation
  only: no economic parameter, runtime, finding status, invariant or mock
  behavior changed. Exclusions need reviewed scope and executable containment;
  no runtime acceptance is claimed. Readiness remains NOT READY and deployment
  and gated activations remain disabled.


Owner revocation amendment,2026-10-30: only the actual grant root EOA can permanently
revoke its exact domain-bound digest. The new revokedObjectGrants mapping is
monotonic and repeated revocation is idempotent. It cannot be cleared by governance
root reuse. Global policyVersion/authorityEpoch do not change on actor revocation,
so other actors' grants cannot be invalidated by unrelated revocation. Typed views
check the flag each time; native runtime readers must authenticate this current
flag with the same root/config source. This is revoke-only, not broader authority,
system pause, provider migration, key recovery or token delegation activation.

The first25-test candidate/full816-test result remains historical evidence. One
new native regression reproduced the absent owner path (26tests/1failure/0skips).
Candidate03 passes29focused tests, including4owner cases; Python codec12 remains
passing. Current full canonical suite/sizes follow this source amendment. New
mapping/event requires privacy review of consent-digest/root linkage. Changed
non-upgradeable policy needs a new separately authorized instance, with no proxy
adoption/migration claim. Full A-G/native/live/independent requirements remain.
