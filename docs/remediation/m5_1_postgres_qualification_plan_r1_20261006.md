# M5.1 PostgreSQL qualification preparation and route decision

**State:** preparation only; no PostgreSQL acquisition, installation, service, provider route, credential, or external observer was selected or run. M5 and testnet readiness remain OPEN / NOT READY.

**Tree binding:** canonical HEAD `829ab544571f12efe50ecb5740f129c8acb3e16f`, branch `testnet/remediation-20260907`; 156 pre-existing porcelain entries were preserved. `git diff --check` passed at inspection. No source or configuration changed in this slice.

## Source reality and current verification

- `neuron/effect_canary.py` defines `PostgresAuthorityRepository` with schema initialization, authority provisioning/revocation, budget reservation, commit, indeterminate marking, and observation recording.
- **Blocking source issue found:** `PostgresAuthorityRepository._connection()` yields a default psycopg2 connection and only calls `conn.close()`. `initialize`, `provision_capability`, `reserve`, `commit_if_current`, `revoke`, `mark_indeterminate`, and `record_observation` issue writes without an explicit commit or rollback policy. Closing an open psycopg2 transaction rolls it back. The first database-backed check must verify this behavior; do not treat the repository as qualified. Correct transaction ownership and failure semantics in a separate source slice, add focused tests, and independently review before accepting PostgreSQL results.
- `neuron/effect_provider.py` is a local loopback object provider with SQLite object/idempotency storage. `HttpObjectProvider` restricts the URL to loopback and `VAMS_ENV` blocks the provider outside local/test/demo. Writer and observer keys are distinct, but both APIs query the same process and SQLite store. `separate-provider-observer-credential` is a label, not proof of independent operator control.
- Source binding at inspection: `neuron/effect_canary.py` SHA-256 `a5ac67887a06d7f747fcfd8fde92e9263ff5b94f569861a4481d301aff973c94`; `neuron/effect_provider.py` `f2bcb6309f369be292666f7bbea38f14fb2f5da24e07ea0281ce0086dd8e1528`; `neuron/effect_canary_cli.py` `6d9686e7cf15080739196dd82ae6a1421438f2f2796cdbc55f23aae527d4f54c`; `neuron/tests/test_effect_canary.py` `e4b07ef73ed89a69c26a7acabc6e06ef02bc11cbd17e21120130e6f5ea6b838a`; plan SHA-256 `33c2e5d1891bb572774998c5026f0b33b9a315d5832e1dad35874a5c0901bfbc`. These bind the observations and test result below to the dirty working tree, not HEAD alone.
- Existing local test command passed: `VAMS_ENV=test /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python -m pytest -q neuron/tests/test_effect_canary.py`  Result: **12 passed**, Python 3.12.14, psycopg2 2.9.12, pytest 9.1.1. This is loopback/SQLite synthetic evidence only. No test instantiates `PostgresAuthorityRepository`.
- Current environment has no PostgreSQL client/server or container runtime, and `VAMS_EFFECT_DATABASE_URL` / `VAMS_ENV` are unset. The pinned psycopg2 driver is present. No approved managed database endpoint has been identified.

## Database decision and bounded provisioning option

**First choice:** owner identifies an already approved, isolated PostgreSQL service and makes its endpoint available through the approved secret/environment manager. Pin its major/minor version and record service owner, isolation boundary, backup/retention, and cleanup. Do not put a DSN or password in this document, shell history, command output, or evidence logs.

**Fallback if no approved service exists:** PostgreSQL **18.6**, the supported upstream minor at plan time, from the official release source:

- Tarball: `https://ftp.postgresql.org/pub/source/v18.6/postgresql-18.6.tar.bz2`
- Official SHA-256 sidecar: `https://ftp.postgresql.org/pub/source/v18.6/postgresql-18.6.tar.bz2.sha256`
- Pinned SHA-256: `555610c24d53e4316da5b7d3fc25c279d96856d5e0e23ee308c328c5fa881d9f`
- Verify HTTPS, compare the downloaded sidecar byte-for-byte to the pinned digest record below, then `sha256sum -c expected.sha256`. Stop and remove only the incomplete download files on any mismatch. No detached upstream signature was verified; the sidecar and archive are from the same official TLS host. Recheck release status and digest before any later acquisition.
- Source-build prerequisites from PostgreSQL 18 documentation: C99-capable compiler, GNU make >=3.81, tar+bzip2, Flex, Bison >=2.3, Perl >=5.14. `--without-readline --without-zlib --without-icu` avoids those optional libraries. Current WSL inspection found no `cc`, `gcc`, `make`, `perl`, `bison`, or `flex`; acquiring these prerequisites also requires separate specific authorization. No download/build is authorized by this plan.

All source/build/toolchain/data/log files remain outside the checkout:
- source/build: `/home/GodOfAgents/vams-evidence/m5.1/postgresql-18.6/{src,build}`
- installed prefix: `/home/GodOfAgents/vams-evidence/toolchains/postgresql-18.6`
- data, socket, log: `/home/GodOfAgents/vams-evidence/m5.1/postgresql-18.6/{pgdata,socket,postgres.log}`
- create the directories mode 0700 and run as the non-root task user. Do not create a system service or modify global PATH.

Commands below are a **future execution recipe only**. They require explicit approval of the environment and any missing build dependencies; none was run in M5.1.

```bash
set -euo pipefail
umask 077
M5=/home/GodOfAgents/vams-evidence/m5.1/postgresql-18.6
PREFIX=/home/GodOfAgents/vams-evidence/toolchains/postgresql-18.6
mkdir -m 700 -p "$M5/src" "$M5/build" "$M5/pgdata" "$M5/socket"
cd "$M5/src"
curl --fail --show-error --location --proto '=https' --proto-redir '=https' --tlsv1.2   --output postgresql-18.6.tar.bz2   https://ftp.postgresql.org/pub/source/v18.6/postgresql-18.6.tar.bz2
curl --fail --show-error --location --proto '=https' --proto-redir '=https' --tlsv1.2   --output postgresql-18.6.tar.bz2.sha256   https://ftp.postgresql.org/pub/source/v18.6/postgresql-18.6.tar.bz2.sha256
printf '%s  %s\n'   555610c24d53e4316da5b7d3fc25c279d96856d5e0e23ee308c328c5fa881d9f   postgresql-18.6.tar.bz2 > expected.sha256
cmp expected.sha256 postgresql-18.6.tar.bz2.sha256
sha256sum --check expected.sha256
tar -xjf postgresql-18.6.tar.bz2
cd "$M5/build"
"$M5/src/postgresql-18.6/configure" --prefix="$PREFIX"   --without-readline --without-zlib --without-icu
make -j2
make install
"$PREFIX/bin/postgres" --version
```

After provisioning authorization, the isolated cluster uses a private Unix socket only (no TCP listener), peer auth for the same unprivileged OS user, rejected host auth, checksums, and durable commit settings:

```bash
M5=/home/GodOfAgents/vams-evidence/m5.1/postgresql-18.6
PREFIX=/home/GodOfAgents/vams-evidence/toolchains/postgresql-18.6
"$PREFIX/bin/initdb" -D "$M5/pgdata" --username="$(id -un)"   --no-locale --encoding=UTF8 --data-checksums   --auth-local=peer --auth-host=reject
cat >> "$M5/pgdata/postgresql.conf" <<EOF
listen_addresses = ''
unix_socket_directories = '$M5/socket'
unix_socket_permissions = 0700
port = 55432
fsync = on
synchronous_commit = on
full_page_writes = on
EOF
"$PREFIX/bin/pg_ctl" -D "$M5/pgdata" -l "$M5/postgres.log" start
"$PREFIX/bin/pg_isready" -h "$M5/socket" -p 55432
"$PREFIX/bin/createdb" -h "$M5/socket" -p 55432 vams_effect_m5
"$PREFIX/bin/psql" -X -h "$M5/socket" -p 55432 -d vams_effect_m5   -v ON_ERROR_STOP=1 -c "SELECT current_setting('server_version_num');"
```

The credential-free local test DSN is `postgresql://$(id -un)@/vams_effect_m5?host=/home/GodOfAgents/vams-evidence/m5.1/postgresql-18.6/socket&port=55432`; the pinned psycopg2 parser accepted this URI. In execution, provide it only in the test process environment. For a managed service, inject the DSN through its approved secret manager and do not print it.

Stop with `pg_ctl -D "$M5/pgdata" stop -m fast`; confirm the exact PID is gone, the socket is removed, and no TCP listener exists. Preserve sanitized results and hashes for review. Only after evidence review, remove the exact private `pgdata` and `socket` directories; retain the checksum-verified source/build identity and evidence as directed by the owner. No broad cleanup command may target the checkout or a computed/unverified path.

## Qualification matrix and boundaries

After the transaction-boundary source issue is fixed and independently reviewed, create `neuron/tests/test_effect_canary_postgres.py` and run:

```bash
VAMS_ENV=test /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python   -m pytest -q neuron/tests/test_effect_canary_postgres.py   neuron/tests/test_effect_canary.py
```

The environment variable is injected before the command; do not echo the DSN. Use synthetic inputs, a fresh random test principal/operation ID, the isolated PostgreSQL schema and only the existing loopback SQLite provider. The following exact outcomes are acceptance targets:

| Scenario | Measurable acceptance |
|---|---|
| Shared-budget contention | 16 independent workers reserve cost 1 against budget 4: exactly 4 reservations succeed; 12 reject; reserved + spent never exceeds 4. |
| Duplicate/restart | Same operation UUID and identical action remains one reservation after a worker restart; same UUID with altered action is rejected. |
| Authority ordering | Use barriers to force revoke-before-commit and commit-lock-before-revoke. A stale epoch/revision never initiates a provider effect; a commit that acquired the lock first can finish once, then the new revoked epoch persists and blocks later effects. |
| Multiworker recovery | Stop worker A after reservation; worker B resumes the same operation ID; exactly one local-provider object and one spend result. |
| Lost acknowledgement | Inject timeout after the local provider commits but before repository checkpoint; restart worker, reconcile using same ID, obtain exact content/action/provider-record hashes; reservation returns to 0 and spent equals the cost exactly once. Any disagreement remains indeterminate and cannot be reported as success. |
| Persistence and cleanup | Restart PostgreSQL and workers; durable schema v1, authority, operation, and observation state remain exact. After stop, no process, private socket, or TCP listener remains. |

Require all designated tests to pass with **0 failures and 0 skips**, exact source/toolchain hashes, sanitized output, and independent review of the exact run. A first test must demonstrate durable `initialize`/provision writes; the current source is expected to fail before its transaction semantics are corrected.

These tests can establish only PostgreSQL authority/recovery mechanics combined with a **synthetic local provider**. They cannot establish a real provider, DA persistence/finality, provider atomicity, remote idempotency, actual network behavior, or independent observation; they receive no full M5, ledger, or readiness credit.

## Provider/DA and independent-observer owner decision

Before provider integration, the owner must record, without credentials:

1. **Provider/DA route:** exact provider and DA product/service, account/tenant/project, region and endpoint identity; which system performs the object effect and which supplies DA; supported API/version; atomicity and durability semantics; operation-ID idempotency; exact lookup/readback APIs; content/receipt/finality evidence; rate and cost limits.
2. **Observer:** named independent organization/operator, the separately administered read-only endpoint/data source, accountable controller of observer access, and ability to retrieve the stored object bytes (or independently derive its hash), operation ID, action digest, content hash, provider record/receipt, and observation time.
3. **Failure and trust boundary:** outage/compromise behavior for provider and observer, proof that the observer route does not share the writer's process/database/administrator, and evidence signing/retention method.

Separate keys inside `ObjectProvider`, a second process under the same administrator, or a second credential in the same provider control plane are **not** independent observation. If owner chooses provider-native readback with shared control, label it provider consistency evidence only and keep the independent-observer M5 gate open. Any adapter, endpoint allowlist, mode/config behavior, or credential handling requires its own design, security review, and tests; do not weaken the current local/test/demo and loopback guards.

## Gates

- **M5.1 (this plan):** independent review of this exact document; owner supplies the approved database source/environment and the exact provider/DA and observer choices. No execution credit.
- **Database slice:** after environment approval and separately reviewed transaction fix, run the synthetic PostgreSQL matrix; record database-only credit.
- **Provider/DA slice:** separate approved route, adapter design, threat review, and tests; no credentials in source/output.
- **Integrated M5:** synthetic authorized effects, failure injection, recovery on a second worker, one effect/no duplicate spend, current authority at effect boundary, bounded budget, exact independent readback and bound receipts, and independent reviewer acceptance.
- Until all required integrated execution and independent-observation evidence passes, **M5 and readiness remain OPEN / NOT READY**. Deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
