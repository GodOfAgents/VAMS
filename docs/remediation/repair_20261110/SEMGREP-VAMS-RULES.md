# VAMS-specific Semgrep rules (2026-11-10)

Status: **9 new blocking rules, each with tests; repository clean against
all 12.** Author review only; non-author review pending. Readiness is
unchanged: 13 findings open, 0 of 36 tracks verified, NOT READY.

## Why

The blocking gate (`.semgrep/vams-security.yml`) had 3 generic rules. The new
rules encode defect classes found in this repository, so they cannot quietly
return. Semgrep Community Edition 1.169.0 runs locally with `--metrics off`
and, as of this change, `SEMGREP_ENABLE_VERSION_CHECK=0`: no source, metrics
or version request leaves the runner.

## Rules

| Rule | Guards against | Origin |
|---|---|---|
| `vams-uvicorn-proxy-headers-enabled` | `uvicorn.run` without `proxy_headers=False` | Gateway refused every remote client (`GATEWAY-LIVE-INGRESS.md`, 2026-11-09) |
| `vams-uvicorn-cli-proxy-headers-enabled` | A documented or scripted gateway launch without `--no-proxy-headers` (Markdown, shell, service, Docker, YAML, TOML; excludes historical `docs/remediation`) | Same |
| `vams-bind-all-interfaces` | `host="0.0.0.0"` or a socket bound to `0.0.0.0` | AGENTS.md loopback-behind-Envoy rule |
| `vams-default-credential` / `-js` | The literal `"vams2026"` anywhere except an equality check that rejects it | AGENTS.md default-credential rule |
| `vams-direct-mock-flag-read` | Reading an upper-case `*MOCK*` environment variable directly instead of through `resolve_component_mock_mode` / `load_runtime_policy`, which refuse mock behaviour in live modes | Mock-mode leakage invariant |
| `vams-ignored-signature-verification` | A bare `verify_message(...)` / `verify_digest(...)` statement; both return `False` instead of raising | Same class as the non-reverting `EffectReceiptV3.verify` traced in the Slither review |
| `vams-secret-in-log` | Logging or printing a variable named like a password, API key, private key, mnemonic or bearer token | Gateway logging rule |
| `vams-cors-wildcard-with-credentials` | `CORSMiddleware` with `allow_origins=["*"]` and credentials | Gateway CORS rule |

The F14 class (a NaN that passes `NaN > threshold`) has no rule. A
syntactic pattern would flag almost every comparison, so F14 relies on its
regression tests.

## Tests

- `.semgrep/tests/` contains annotated fixtures: `ruleid:` cases that must
  fire and `ok:` cases that must not, for all 12 rules.
- `scripts/security/semgrep_rule_tests.sh` runs `semgrep --test` offline.
  Result: 12/12 pass.
- CI runs the script before the gate. The fixtures are deliberately unsafe,
  so the gate and discovery scans exclude `.semgrep/tests`.

**Historical replay.** The rules were run on pre-fix sources from commit
`d472b49`:

- `gateway/server.py` was flagged at its old `uvicorn.run`;
- `docs/GATEWAY_HARDENING_BLUEPRINTS.md` was flagged at its old launch
  command;
- a probe `os.getenv("OMS_MOCK_MODE", "true")` was flagged.

## Repository scan

Gate command plus `--exclude .semgrep/tests`, 524 files: 0 findings, 0
errors, exit 0. That is after three source decisions on the five first-pass
hits:

1. `neuron/gateway/server.py:211`: the legacy gateway's `uvicorn.run` now
   passes `proxy_headers=False`. It already refused live modes, so this is
   consistency, not a live fix. The privacy inventory digest was re-bound;
   no anchor moved.
2. `neuron/trust.py` (2 lines): the mode comes from the resolver; the raw
   flag value is kept only to detect drift after startup. Each line carries
   an inline `nosemgrep` with that reason.
3. `scripts/audit/*` (2): these were lower-case manifest keys
   (`mock_routes_disabled`, `mock_mode`), not environment variables. The
   rule now matches upper-case variable names only, and an `ok:` fixture
   covers the case.

Python full suite: 3480 passed. The only failure was the inventory digest
for (1); after the re-bind, the boundary, trust and legacy-gateway suites
pass (82). Bandit is clean. Audit script tests: 218 OK.

## Not changed

- The discovery scan still runs `--metrics on --config auto`. Switching to
  metrics off with a vendored, pinned rule pack is owner decision D5-B and
  needs a one-time download approval.
- Semgrep Pro, Supply Chain and Secrets are not adopted. Pro could only ever
  be advisory, and it needs a semgrep.dev account and an external-service
  and privacy decision.
- Semgrep does not prove protocol properties such as authorization, replay
  or settlement. Foundry, Aiken and the live gateway tests remain the
  evidence for those.
