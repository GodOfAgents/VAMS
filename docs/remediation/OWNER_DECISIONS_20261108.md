# Owner decisions — 2026-11-08

Approved in chat by the project owner (Aseem Chishti) on 2026-11-08, answering
the five Phase 0 decisions of the testnet-readiness plan. These are recorded
decisions and scoped authorizations. They do not promote any finding, track or
readiness status: 13 findings open, 0 of 36 tracks verified, NOT READY.

## 1. Linux qualification runner (D1)

Use WSL2 Ubuntu 26.04 on the owner's workstation plus a disposable local
PostgreSQL as the D1 runner. Authorized: download from official upstream
release sources only (foundry-rs, aiken-lang, astral-sh uv / python-build-
standalone, nodejs.org, PyPI for the pinned CI tool versions, the official
PostgreSQL image), checksum verification where published, user-space install
under `~/.vams-tools`, no system package changes. Pins follow
`.github/workflows/security-gates.yml` and `ENVIRONMENT.md` (Foundry v1.7.1,
Aiken v1.1.21, Python 3.12, Node 22, Rust 1.92.0). Runner identity, tool
hashes and the resolved dependency lock must be recorded with each result.
Limitation: this is an owner-operated workstation, not an independent CI
runner; hosted exact-commit CI remains required for F16.

## 2. Native Aiken execution (D1-A)

Authorized: `aiken check`, `aiken build` and `aiken test` (including the CI
flags `--deny --seed 20260711 --max-success 250`) against the canonical
`cardano/` source with the pinned Linux Aiken 1.1.21. Original R28 and
Slot 08 remain NOT authorized by this decision.

## 3. First closed-canary enabled routes

Enable only effect routes that have a real, qualified verifier by canary
admission. The cross-chain bridge / ExecuteIntent route (F05) stays disabled.
TEE-dependent routes (F06) stay disabled unless authentic DCAP evidence exists
by admission. Every disabled route needs executable containment tests (deny
before any effect) and non-author review. Both Polygon Amoy and Cardano
Pre-Prod remain mandatory. Whether an excluded route's track counts as
not-applicable must follow the existing stage-applicability rules in
`scripts/audit/deployment_readiness.py`; no new exclusion is created here.

## 4. Economics TR-01 to TR-10

Accept the recommendations in `TOKENOMICS_OWNER_DECISIONS_R1_20261008.md`:
hard cap $1 \times 10^9$ and zero emissions; vesting unactivated with
executable containment; 14/30-day unbonding preserved with no emergency
bypass; buyback/burn and reward distribution not activated; zero reward rate
and no staking minter; delegation formally deferred with executable
disablement; ordinary governor constructed but inactive, restricted operations
through reviewed multisig/timelock. DEC floor/decay/terminal values remain
frozen-unset until a later economic design.

## 6. Historical harness tests (added later on 2026-11-08)

Six harness tests in `docs/remediation/m3_2b_r4`, `m3_2b_r6`,
`m3_f04_impl_r2` and `m3_f04_impl_r4` encode designs superseded by later owner
records (notably registry-side minting). Owner chose "Retire as historical":
keep the files as evidence, deselect the six exact node IDs in `pytest.ini`,
document them in `docs/remediation/HISTORICAL_TESTS.md`. Only an owner
decision may add further entries.

## 7. Remaining CI-green dispositions (added later on 2026-11-08)

Owner approved: (a) Bandit B608 findings in `neuron/effect_*` are suppressed
per line with a recorded reason only after verification that every
interpolated SQL identifier is a fixed `public.vams_effect_*` constant or an
allowlist/regex-validated name, enforced by a static guard test; B102 `exec`
findings in tests likewise per line. No Bandit scope or severity change.
(b) The semantic-MMU boundary inventory is re-checked anchor by anchor and
re-bound to current source, not retired. (c) Three R11 provenance tests are
retired as historical (see `HISTORICAL_TESTS.md`).

## 8. npm registry and Rust toolchain downloads (added later on 2026-11-08)

Owner approved downloads from the npm registry (frontend `npm ci` and
`npm audit` per the CI frontend gate) and the official Rust distribution
(rustup, Rust 1.92.0 with rustfmt/clippy, crates.io for `cargo-audit 0.22.2`
and the locked `vams-vm` dependencies, RustSec advisory data for
`cargo audit`). npm lifecycle scripts are inventoried before `npm ci` runs.
Not covered: Semgrep's `--config auto --metrics on` discovery scan (sends
metrics to and fetches rules from semgrep.dev; needs a D5-B decision).

## 9. Current-tree secret-scan rulings (added later on 2026-11-08)

Acting as disposition authority under decision 5, the owner accepted all
eight groups (A–H, 638 first-party findings) in
`repair_20261108/SECRET-SCAN-DISPOSITIONS.md` as non-credential, and chose
application option 1: exact Gitleaks fingerprints in `.gitleaksignore`, with
a CI re-proof check that fails unless every entry maps to an accepted
manifest record whose file still has its recorded SHA-256. No rule, path or
regex allowlist is widened. Complete-history scanning and the planned history
rewrite are not covered by this ruling.

## 5. Secret-scan disposition authority (D5)

The owner is the per-finding disposition authority for first-party secret-scan
matches. Standard: each decision binds the exact source manifest, path, file
hash, rule, lines and stable finding identity to a concrete public-source or
non-credential proof. No blanket allowlist, hidden exclusion, raw-secret
disclosure or history rewrite follows from this decision. Independent review
of the dispositions remains required before release.

## 10. F13 composed-settlement dispute window (2026-11-09)

The owner reviewed `repair_20261109/F13-DISPUTE-WINDOW-DESIGN.md` and approved
all six recommended parameters:

| # | Approved value |
|---|---|
| P1 | 72-hour hold after a delivery is earned |
| P2 | Resolver is the governance timelock (3-of-5 Safe + 48 h), set at deployment |
| P3 | Agent dispute bond of 5% of the row amount |
| P4 | 14-day resolution deadline |
| P5 | On deadline: provider paid, bond returned to the agent |
| P6 | Binary outcomes only: uphold (full refund) or reject (normal payment) |

Slashing stays disabled (tokenomics R1). The resolver's actual signers remain
UNKNOWN until the Phase 3 custody inputs arrive. Implementation still
requires targeted tests, size checks and non-author review before acceptance.
