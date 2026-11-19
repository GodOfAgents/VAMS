# Payment catalog compatibility and EIP-3009 component

15–16 November 2026. Local engineering repairs; live payments remain disabled.
Windows and WSL integration and its exact successor source manifest are recorded
in VAMS-payment-native-20261115-02. Original failed attempts remain evidence.

## Implemented changes

Payment ledger guards reject every rewrite rule while holding their table locks.
Each appended event requires one affected row and exact native-value readback.
Missing, suppressed or altered event insertion aborts the enclosing transaction;
monetary reservation and V5 execution-cost accounting remain distinct.

The exact PostgresAuthorityDatabaseV5 now supports an explicit sealed payment
manifest with immutable absent/present installation stage. Default configuration
commitment bytes and the default closed V5 relationship graph are preserved.
The selected payment manifest changes the explicit extension configuration
commitment; stage does not change that commitment. There is no automatic schema
adoption, migration of old state, inferred allowlist or mutable stage transition.
PaymentLedgerV1 requires the same configured manifest. Migration uses an absent
instance, validates the complete installed graph before COMMIT, and requires new
present instances afterward. Retained absent instances must reject protected use.

The present profile locks V5 then all four payment relations and verifies the
compiled constraints, fixed relation properties and complete sixteen-FK/internal
trigger graph using the unchanged shared V3 validator. Default and opt-in guards
check relationship interception before reading protected metadata. Unknown FKs,
triggers, rewrite rules and partial installations remain errors. DDL and frozen
V1/V3/V5 wire encodings are unchanged.

eip3009_v1.py is a pure EOA data codec using Keccak EIP-712 domains and distinct
TransferWithAuthorization/ReceiveWithAuthorization type hashes. It constructs
typed data/ABI bytes and verifies public low-S signatures and strict validity
windows; it never signs or submits. V1 intent projection permits transfer only.
Receive data construction requires caller==payee, which is metadata rather than
proof of an actual caller. Transfer is bearer authorization and does not enforce
an exclusive facilitator. The token standard does not bind VAMS jobs, reserve
funds, establish nonce consumption/finality or credit a settlement allocation.
See the [primary EIP-3009 specification](https://eips.ethereum.org/EIPS/eip-3009).
Real token support/domain, facilitator, custody and allocation-aware funding
remain required reviewed inputs; no deployment identifier is invented here.

## Executed evidence and its limits

The original three event/rule regression methods failed on retained old source
(six failure events, not six methods). The four-payload repair passed 54 methods
and 263 subtests. The complete compatibility successor passed 184 methods and 446
subtests across fourteen payment/V5/canary files, with zero failures/skips. Counts
overlap. The earlier183-pass/one-failure run is preserved: its old metadata cursor
lacked the newly required catalog replies. The revised fixture supplies valid
unique/FK/trigger rows to the real validators and keeps its stale-digest assertion.
These checks use SQL/catalog/transaction doubles and synthetic signing keys.

The specifically approved official pinned PostgreSQL18.6 image was digest-checked
and unpacked in a new private user-space directory without a daemon or system
package changes. Sixteen extractor safety methods passed after preserving a
fixture-exception expectation failure. The extracted filesystem's9662 entries
are checked before native execution; unpacking normalizations are disclosed in
the extraction receipt. This is content-digest/TLS provenance, not artifact-signing
or a completed supply-chain audit.

Actual PG18 preflight passed with non-root UID999, private loopback/no external
route, SCRAM, TLS verify-full/TLSv1.3 and graceful owned-server shutdown. The
installed psycopg2 client is2.9.13 with libpq17.11; server is180006. Original
scratch compilation captured226 catalog rows,69 V5 CHECKs and35 payment constraints
in independently reviewed manifests. Original runtime migrations then succeeded
but scope preparation FAILED: fourteen adjacent FKs exceeded the old twelve-FK
contract. That actual native defect observation remains a failure; later money
and rule checks were not reached. The repaired source's native successor and
post-integration checks have separate receipts; consult their actual results,
never infer a PASS from this component description.

Native SQL with local synthetic policy/provider/payment keys is distinct from
authentic authority, token payment/finality, independent hosted qualification,
human custody/privacy assurance or operational observation. Concurrency, actual
commit-ack loss, restart/restore and the full frozen release/security workflow
remain separate requirements unless their own accepted receipts establish them.

## BYTEA repair and fresh native result, 16 November

The journal now copies exact memoryview values to immutable bytes before its
existing encoding/length and authenticated-history checks. Released views produce
the controlled encoding error; no bytearray/general coercion or driver-wide
typecaster is installed. Eleven new helper/consumer fixture methods cover real
generation/head/history/completion decoding, malformed values and tampering.
The complete fifteen-file local run passed 195 methods and 474 subtests, with
zero failures/skips. This includes earlier focused counts; do not add them.

A fresh diagnostic ran the actual present schema guard successfully and rolled
back. A separate READ ONLY bound BYTEA query returned a readonly contiguous
memoryview, format c; the unpatched journal rejected it. All twelve tables stayed
unchanged. The diagnostic is explicitly not a qualification pass. The precise
cause of the earlier coarse prepare/activate failure remains unproven; that old
scope was never reopened or retried.

The repaired source then passed one fresh native SQL campaign: separate approved
compiler/runtime databases, actual migrations, scope prepare/activation, initial
admission, monetary reserve, all five retained absent-component rejections, and
owner rewrite-rule rejection without data changes. Its native graph contains
sixteen foreign keys and sixty-four internal RI triggers. Exposure then unknown
retained the original credential digest and reservation; one intent has three
events. The oracle checked 100 atomic monetary units remain reserved and the V5
execution cost is reserved once with zero spent. These are unfunded fixture units.
Both compiler and runtime servers stopped gracefully; source/tools stayed bound.

Evidence: PG18-BYTEA-SMOKE-01.json and native-results/pg18-bytea-smoke-01 under
VAMS-payment-native-20261115-02. The native source has 4,211 selected paths; the
canonical successor adds/updates only the four documentation payloads beyond
those exact production/test bytes. The two-root journal and final full Windows
check establish the integration mapping separately. Full combined-source tests
and scanner receipts are subsequent evidence, not inferred from this campaign.
This native SQL pass uses synthetic provider/policy/payment keys; it does not
verify a token transfer, finality, registry producer, external effect, custody or
authentic production authority. Race/crash/restart/restore and broader release
gates remain required. No reward, signing, funding or live route is enabled.

## Invariants and remaining scope

INV-1 through INV-8 are not changed. INV-9-adjacent monetary liabilities remain
reserved until authenticated resolution; this is not proof of funded token or
reward-pool solvency. INV-10 separation is preserved: typed transfer/SQL receipts
are never bridge or execution proofs. No signing authority, minter, reward,
emission, refund/release path, live route or privileged role is enabled.

Full A--G and both Polygon Amoy/Cardano Pre-Prod remain required:13 findings open,
0/36 formally verified tracks, zero readiness promotions, NOT READY. Genuine
provider/DCAP/EZKL/DA/observer, custody/privacy/security assurance, native Cardano
and remaining runtime/release gates, both-chain rehearsals and actual7-/14-day
observation requirements are unchanged. No R28, Slot08 or Aiken is used here.
