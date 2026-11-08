# Local environment inventory and bootstrap

Recommended host arrangement: Windows -> WSL2 Ubuntu 24.04 -> isolated VAMS checkout + Codex CLI. No GPU configuration is necessary to begin contract and ordinary software tests. GPU/model/prover workloads are additional tasks with their own measured requirements.

The following pins were read from the current dirty-tree
`.github/workflows/security-gates.yml` at superproject HEAD
`829ab544571f12efe50ecb5740f129c8acb3e16f`. They are a baseline to verify,
not a claim that these working-tree values are committed or are the latest
upstream releases.

| Tool | CI selection |
|---|---|
| Foundry executables | v1.7.1 |
| Aiken | v1.1.21 |
| Rust toolchain | 1.92.0; rustfmt and clippy |
| cargo-audit | 0.22.2, installed locked |
| Python | 3.12 (record the actual patch version used) |
| pip | 26.2 |
| Node.js | 22 (record actual patch version and npm) |
| Slither | slither-analyzer 0.11.5 |
| Bandit | 1.9.4 |
| pip-audit | 2.10.1 |
| Semgrep | 1.169.0 |
| GitLeaks | 8.30.1 |
| pytest / pytest-asyncio / anyio | 9.1.1 / 1.4.0 / 4.14.1 |
| httpx / httpx2 / httpcore2 | 0.28.1 / 2.12.0 / 2.12.0 |
| git-filter-repo | 2.47.0 |

Re-read the rest of the workflow for TruffleHog, Caddy, SBOM and signing tooling. Inspect contracts/foundry.toml for compiler, FFI and profiles, cardano/aiken.toml and lock, vams-vm/rust-toolchain.toml/Cargo.lock, both Python requirements and frontend lockfile. Native version equality alone does not guarantee parity: record compile flags, submodules, runtime libraries and service dependencies.

## Bootstrap behavior for Codex

Propose a reproducible install script using official upstream distribution sources, checksum/signature verification where available and explicit versions. Ask for system/network permission. Do not run an uninspected remote installer as root. Keep production keys out of this environment. Do not replace CI pins with arbitrary latest versions; if a pin cannot be resolved, report it with source evidence and propose a reviewed correction.

Create a Python 3.12 venv in the checkout if already ignored, or a separate approved development directory. Avoid system pip installation. Install the exact CI testing tools and project requirements. Record package resolution without changing lockfiles silently. Install Node 22 inside Ubuntu rather than relying on a Windows node.exe. Use pinned Aiken Linux tooling, not the checked-in Windows executable.

A Foundry install can use official foundryup, then `foundryup -i v1.7.1`, after verifying that pin against current CI. Rust uses `rustup toolchain install 1.92.0 --profile minimal --component rustfmt,clippy` and the CI-selected cargo-audit. Confirm installers/options from current upstream docs before execution.

## Minimum version check

```bash
git --version
python3.12 --version
node --version
npm --version
forge --version
anvil --version
cast --version
aiken --version
rustc +1.92.0 --version
cargo +1.92.0 --version
codex --version
```

Missing commands are NOT_RUN/BLOCKED_ENVIRONMENT, not green. Do not skip their gate from final readiness.

## Representative native commands

These are not an exhaustive release runner. Use the current CI source for the complete gate list.

```bash
(cd contracts && forge build --sizes && forge test -vvv)
(cd cardano && aiken check --deny --seed 20260711 --max-success 250)
(cd vams-vm && cargo +1.92.0 fmt --all -- --check && \
 cargo +1.92.0 check --workspace --all-targets --locked && \
 cargo +1.92.0 clippy --workspace --all-targets --locked -- -D warnings && \
 cargo +1.92.0 test --workspace --all-targets --locked && \
 cargo +1.92.0 audit --deny warnings)
python -m pytest -v --tb=short
(cd frontend-vite && npm ci && npm audit --audit-level=high && \
 npm audit --omit=dev --audit-level=high && npm run lint && npm run build)
python scripts/audit/audit_program.py validate
```

Inspect scripts and required environment first. DBOS, PostgreSQL, local RPC, mTLS fixtures and other integration dependencies must be installed/run with explicit test configuration. `aiken check` is the observed CI test command; do not use the older AGENTS.md command list uncritically.

Do not globally export VAMS_ENV=local to work around a deployment test failure. Local unit fixtures may use explicit simulation; separate integration cases must prove real `testnet` fail-closed behavior.

Limit concurrent compiler/test jobs initially. Increase only based on measured CPU/RAM pressure; never lower fuzz/property coverage or disable a suite to hide resource problems. Rerun final gates with their required settings.
