#!/usr/bin/env python3
"""F12 native PostgreSQL crash/restart campaign for the V3 object-effect path.

For each kill point around every external-effect and checkpoint boundary this:

1. creates a fresh authority database and a fresh provider database on a real
   PostgreSQL server (TLS verify-full), runs both explicit migrations, and
   installs one authority scope through the real coordinator;
2. starts WORKER 1 in its own OS process, which runs the real
   ``ObjectEffectCoordinatorV3.execute`` and dies with ``os._exit(137)`` at the
   kill point (no cleanup, no rollback call; the server sees a dropped socket);
3. starts WORKER 2 in a separate fresh OS process, which follows the recovery
   procedure: execute if nothing was dispatched, otherwise reconcile, and if the
   provider has no evidence, compensate by fenced cutover plus authenticated
   absence (refund of the reserved budget);
4. checks the databases directly: exactly one provider effect or none, the
   authority operation's terminal status, budget reserved/spent arithmetic, the
   admitted policy epoch/version, that a repeat execute creates no second
   effect, and that a late commit after compensation is refused.

Scope: the V3 Python effect path (authority + provider stores). It runs in
VAMS_ENV=test because V3 candidates refuse live modes by design; TLS is still
verify-full via libpq settings. Keys are fixed LOCAL-ONLY test keys. Token
payment settlement (Solidity) and real provider hosts are outside this run.

Usage (WSL D1 runner):
  PGPASSFILE-style secret: the admin password is read from --password-file and
  passed only through the PGPASSWORD environment variable of child processes.
  python effect_v3_native_pg_campaign.py --out <record.json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

KILL_POINTS = (
    "before_reserve_commit",   # reserve transaction open, COMMIT never sent
    "after_reserve",           # reservation committed, dispatch not claimed
    "after_claim",             # dispatch claimed, provider never called
    "provider_precommit",      # provider insert executed, COMMIT never sent
    "after_provider_commit",   # provider effect committed, authority not told
    "accept_precommit",        # authority accept executed, COMMIT never sent
    "after_accept",            # everything committed, worker dies before returning
)
EXPECTED = {  # kill point -> (provider effects, authority status, recovery path)
    "before_reserve_commit": (1, "committed", "execute"),
    "after_reserve": (1, "committed", "execute"),
    "after_claim": (0, "rejected", "compensate"),
    "provider_precommit": (0, "rejected", "compensate"),
    "after_provider_commit": (1, "committed", "reconcile"),
    "accept_precommit": (1, "committed", "reconcile"),
    "after_accept": (1, "committed", "reconcile"),
}
CONTENT = b"fixture-object"
MAINTENANCE_DB = "vams_canary"  # the container's initial database; campaign databases are separate
NOW = 1050


# ---- deterministic components (identical in every process) -------------------

def _components(authority_dsn: str, provider_dsn: str):
    from cryptography.hazmat.primitives.asymmetric import ec
    from neuron.effect_authority_v3 import ObjectAuthorityScopeV3, PostgresEffectAuthorityV3
    from neuron.effect_authority_store_v3 import PostgresAuthorityDatabaseV3, authority_configuration
    from neuron.effect_postgres_v3 import PostgresEffectDatabaseV3
    from neuron.effect_provider_v3 import PostgresObjectProviderV3, ObjectProviderIdentityV3
    from neuron.effect_coordinator_v3 import ObjectEffectCoordinatorV3, DirectObjectProviderTransportV3
    from neuron.effect_protocol_v3 import ObjectFenceV3, ReceiptSignerV3
    from neuron.tests.test_effect_protocol_v3 import fixture_proposal
    from neuron.tests.test_effect_authority_v3 import FixtureAuthorityPolicy
    from neuron.tests.test_effect_provider_v3 import FixturePolicy

    def key(label: str):
        # LOCAL-ONLY deterministic test keys; never used outside this campaign.
        scalar = int.from_bytes(hashlib.sha256(b"VAMS-F12-NATIVE-PG-TEST-KEY:" + label.encode()).digest(), "big")
        return ReceiptSignerV3(ec.derive_private_key(scalar % (2**255) + 1, ec.SECP256K1()))

    proposal = fixture_proposal(budget=10)
    authority_signer, provider_signer = key("authority"), key("provider")
    c = proposal.context
    identity = ObjectProviderIdentityV3(c.provider_id, c.host_domain, c.runtime_id, c.target, c.chain_id,
                                        authority_signer.verifier(), provider_signer.verifier())
    authority_db = PostgresAuthorityDatabaseV3(authority_dsn, authority_configuration(identity))
    provider_db = PostgresEffectDatabaseV3(provider_dsn, identity.digest)
    authority = PostgresEffectAuthorityV3(authority_db, identity, authority_signer, FixtureAuthorityPolicy(),
                                          clock=lambda: NOW)
    provider = PostgresObjectProviderV3(provider_db, identity, provider_signer, FixturePolicy(), clock=lambda: NOW)
    transport = DirectObjectProviderTransportV3(provider)
    coordinator = ObjectEffectCoordinatorV3(authority, transport)
    scope = ObjectAuthorityScopeV3(c, (b"r" * 32, b"s" * 32), 10, 4, 9)
    fence = ObjectFenceV3.from_context(c, 9)
    cutover_fence = replace(fence, authority_epoch=4, policy_version=8, fencing_token=10)
    return dict(proposal=proposal, authority_db=authority_db, provider_db=provider_db, authority=authority,
                provider=provider, transport=transport, coordinator=coordinator, scope=scope,
                fence=fence, cutover_fence=cutover_fence)


# ---- worker processes -------------------------------------------------------------

def _install_kill_hooks(point: str) -> None:
    """Patch classes in THIS process only so the worker dies at `point`."""
    from neuron.effect_authority_v3 import PostgresEffectAuthorityV3
    from neuron.effect_provider_v3 import PostgresObjectProviderV3
    from neuron.effect_postgres_v3 import PostgresEffectDatabaseV3

    stage = {"name": None}

    def die():
        sys.stdout.flush()
        os._exit(137)

    class KillingConnection:
        def __init__(self, inner): self._inner = inner
        def __getattr__(self, name): return getattr(self._inner, name)
        def commit(self):
            if (point, stage["name"]) in (("before_reserve_commit", "reserve"),
                                          ("provider_precommit", "provider_commit"),
                                          ("accept_precommit", "accept")):
                die()
            return self._inner.commit()

    original_connect = PostgresEffectDatabaseV3._connect
    def connect(self):
        return KillingConnection(original_connect(self))
    PostgresEffectDatabaseV3._connect = connect

    def staged(cls, method, name, after_point=None):
        original = getattr(cls, method)
        def wrapper(self, *args, **kwargs):
            previous, stage["name"] = stage["name"], name
            try:
                result = original(self, *args, **kwargs)
            finally:
                stage["name"] = previous
            if after_point == point:
                die()
            return result
        setattr(cls, method, wrapper)

    staged(PostgresEffectAuthorityV3, "reserve", "reserve", "after_reserve")
    staged(PostgresEffectAuthorityV3, "claim_dispatch", "claim", "after_claim")
    staged(PostgresObjectProviderV3, "commit", "provider_commit", "after_provider_commit")
    staged(PostgresEffectAuthorityV3, "accept_effect", "accept", "after_accept")


def worker_one(args) -> int:
    _install_kill_hooks(args.point)
    parts = _components(args.authority_dsn, args.provider_dsn)
    parts["coordinator"].execute(parts["proposal"], CONTENT)
    print(json.dumps({"worker": 1, "completed_without_kill": True}))
    return 0


def worker_two(args) -> int:
    from neuron.effect_authority_v3 import ReconciliationRequiredV3
    from neuron.effect_protocol_v3 import ObjectFenceV3
    parts = _components(args.authority_dsn, args.provider_dsn)
    authority, coordinator, proposal = parts["authority"], parts["coordinator"], parts["proposal"]
    report = {"worker": 2}
    operation = authority.read_operation(proposal)
    report["found_status"] = None if operation is None else operation.status
    if operation is None or operation.status == "reserved":
        coordinator.execute(proposal, CONTENT)
        report["path"] = "execute"
    else:
        try:
            coordinator.reconcile(proposal)
            report["path"] = "reconcile"
        except ReconciliationRequiredV3:
            # No provider evidence: fence the old scope, then prove absence and refund.
            scope_id = ObjectFenceV3.from_context(proposal.context, proposal.fencing_token).scope_id
            coordinator.start_cutover(scope_id, parts["cutover_fence"])
            coordinator.reconcile_absence(proposal)
            report["path"] = "compensate"
            # A late commit with the original admission must now be refused.
            admission = authority.read_operation(proposal).admission
            try:
                parts["transport"].commit(proposal, admission, CONTENT)
                report["late_commit_refused"] = False
            except Exception as error:  # refusal is the expected outcome
                report["late_commit_refused"] = True
                report["late_commit_error"] = type(error).__name__
    # A repeat execute must never create a second provider effect.
    try:
        coordinator.execute(proposal, CONTENT)
        report["repeat_execute"] = "returned"
    except Exception as error:
        report["repeat_execute"] = "refused:" + type(error).__name__
    final = authority.read_operation(proposal)
    report["final_status"] = final.status
    # The admission retained across the crash keeps the original policy epoch/version.
    admitted = final.admission.receipt
    report["admitted_authority_epoch"] = admitted.authority_epoch
    report["admitted_policy_version"] = admitted.policy_version
    report["proposal_authority_epoch"] = proposal.context.authority_epoch
    report["proposal_policy_version"] = proposal.context.policy_version
    print(json.dumps(report))
    return 0


# ---- driver -----------------------------------------------------------------------

def _admin(database: str, env: dict):
    import psycopg2
    return psycopg2.connect(host="127.0.0.1", port=env["PGPORT"], user=env["PGUSER"], dbname=database,
                            sslmode="verify-full", sslrootcert=env["PGSSLROOTCERT"],
                            password=env["PGPASSWORD"], connect_timeout=5)


def _dsn(database: str, env: dict) -> str:
    # No password in the DSN; libpq reads PGPASSWORD/PGSSLROOTCERT from the environment.
    return f"postgresql://{env['PGUSER']}@127.0.0.1:{env['PGPORT']}/{database}?sslmode=verify-full"


def _fresh_databases(case: str, env: dict) -> tuple[str, str]:
    names = (f"vams_f12_{case}_authority", f"vams_f12_{case}_provider")
    conn = _admin(MAINTENANCE_DB, env)
    conn.autocommit = True
    with conn.cursor() as cur:
        for name in names:
            cur.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')  # nosec B608 # fixed campaign names
            cur.execute(f'CREATE DATABASE "{name}"')  # nosec B608 # fixed campaign names
    conn.close()
    return names


def _state(databases: tuple[str, str], env: dict, operation_id: bytes) -> dict:
    from neuron.effect_authority_store_v3 import SCOPES, OPERATIONS
    from neuron.effect_postgres_v3 import OBJECTS
    authority_db, provider_db = databases
    out = {}
    conn = _admin(provider_db, env)
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {OBJECTS}")  # nosec B608 # fixed table constant
        out["provider_effects_total"] = cur.fetchone()[0]
        cur.execute(f"SELECT count(*) FROM {OBJECTS} WHERE operation_id=%s", (operation_id,))  # nosec B608
        out["provider_effects_for_operation"] = cur.fetchone()[0]
    conn.close()
    conn = _admin(authority_db, env)
    with conn.cursor() as cur:
        cur.execute(f"SELECT status, cost_units FROM {OPERATIONS} WHERE operation_id=%s", (operation_id,))  # nosec B608
        row = cur.fetchone()
        out["authority_status"], out["cost_units"] = (row[0], row[1]) if row else (None, None)
        cur.execute(f"SELECT status, budget_limit, budget_reserved, budget_spent FROM {SCOPES}")  # nosec B608
        scopes = cur.fetchall()
        out["scopes"] = [dict(status=s[0], limit=s[1], reserved=s[2], spent=s[3]) for s in scopes]
        cur.execute(f"SELECT count(*) FROM {OPERATIONS}")  # nosec B608
        out["authority_operations_total"] = cur.fetchone()[0]
    conn.close()
    return out


def _run_worker(role: str, point: str, dsns: tuple[str, str], env: dict) -> tuple[int, str, float]:
    started = time.monotonic()
    proc = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), role, "--point", point,
                           "--authority-dsn", dsns[0], "--provider-dsn", dsns[1]],
                          cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=120, check=False)
    tail = (proc.stdout.strip().splitlines() or [""])[-1]
    err = proc.stderr.strip().splitlines()[-1:] if proc.returncode not in (0, 137) else []
    return proc.returncode, tail + ((" | stderr: " + err[0]) if err else ""), round(time.monotonic() - started, 2)


def campaign(args) -> dict:
    password = Path(args.password_file).expanduser().read_text().strip()
    env = {
        "PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", ""),
        "PYTHONPATH": str(ROOT), "VAMS_ENV": "test",
        "PGUSER": args.user, "PGPORT": str(args.port), "PGPASSWORD": password,
        "PGSSLROOTCERT": str(Path(args.ca).expanduser()), "PGSSLMODE": "verify-full",
    }
    os.environ.update({k: v for k, v in env.items() if k.startswith("PG") or k == "VAMS_ENV"})
    import psycopg2
    server = {}
    conn = _admin(MAINTENANCE_DB, env)
    with conn.cursor() as cur:
        cur.execute("SHOW server_version"); server["server_version"] = cur.fetchone()[0]
        cur.execute("SELECT ssl, version FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
        row = cur.fetchone(); server["ssl"], server["tls_version"] = bool(row[0]), row[1]
    conn.close()
    server["psycopg2"] = psycopg2.__version__

    results, failures = [], []
    for point in KILL_POINTS:
        databases = _fresh_databases(point, env)
        dsns = (_dsn(databases[0], env), _dsn(databases[1], env))
        parts = _components(*dsns)
        parts["authority_db"].migrate()
        parts["provider_db"].migrate()
        parts["coordinator"].install(parts["scope"])
        operation_id = parts["proposal"].operation_id
        code1, out1, t1 = _run_worker("worker-one", point, dsns, env)
        between = _state(databases, env, operation_id)
        code2, out2, t2 = _run_worker("worker-two", point, dsns, env)
        after = _state(databases, env, operation_id)
        try:
            report = json.loads(out2.split(" | stderr:")[0])
        except ValueError:
            report = {"raw": out2}
        effects, status, path = EXPECTED[point]
        scope = after["scopes"][0] if after["scopes"] else {}
        checks = {
            "worker_one_killed": code1 == 137,
            "worker_two_exit_zero": code2 == 0,
            "recovery_path": report.get("path") == path,
            "provider_effects_exact": after["provider_effects_total"] == effects,
            "authority_status": after["authority_status"] == status,
            "single_operation_row": after["authority_operations_total"] == 1,
            "budget_arithmetic": (scope.get("spent") == (3 if status == "committed" else 0)
                                  and scope.get("reserved") == 0),
            "repeat_execute_refused": str(report.get("repeat_execute", "")).startswith("refused"),
            "policy_epoch_preserved": (report.get("admitted_authority_epoch") == report.get("proposal_authority_epoch")
                                       and report.get("admitted_policy_version") == report.get("proposal_policy_version")),
        }
        if path == "compensate":
            checks["late_commit_refused"] = report.get("late_commit_refused") is True
        ok = all(checks.values())
        if not ok:
            failures.append(point)
        results.append({"kill_point": point, "databases": list(databases), "expected": {
            "provider_effects": effects, "authority_status": status, "recovery_path": path},
            "worker_one": {"exit": code1, "seconds": t1, "last_line": out1},
            "state_after_kill": between, "worker_two": {"exit": code2, "seconds": t2, "report": report},
            "state_after_recovery": after, "checks": checks, "pass": ok})
    return {
        "schema": "vams.f12_native_pg_campaign/1",
        "status": "PASS" if not failures else "FAIL",
        "evidence_class": "NATIVE_POSTGRESQL_LOCAL_PROCESS_KILL",
        "server": server,
        "kill_points": list(KILL_POINTS),
        "failures": failures,
        "results": results,
        "limits": [
            "V3 object-effect Python path only; runs in VAMS_ENV=test because V3 candidates refuse live modes.",
            "Single local PostgreSQL 17 container; no network partition, failover or replica behaviour.",
            "Workers die by os._exit(137) at instrumented boundaries; not power loss or kernel crash.",
            "Fixed LOCAL-ONLY keys and fixture policies; no real provider host, signer custody or chain payment.",
            "Token payment settlement (Solidity ComposedSettlement) is outside this run.",
            "Not independent review or operational qualification evidence.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd")
    for role in ("worker-one", "worker-two"):
        w = sub.add_parser(role)
        w.add_argument("--point", required=True, choices=KILL_POINTS)
        w.add_argument("--authority-dsn", required=True)
        w.add_argument("--provider-dsn", required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--password-file", default="~/.vams-tools/pg/admin.password")
    parser.add_argument("--ca", default="~/.vams-tools/pg/ca.crt")
    parser.add_argument("--user", default="vams_admin")
    parser.add_argument("--port", type=int, default=55432)
    args = parser.parse_args()
    if args.cmd == "worker-one":
        return worker_one(args)
    if args.cmd == "worker-two":
        return worker_two(args)
    if not args.out:
        parser.error("--out is required")
    record = campaign(args)
    args.out.write_text(json.dumps(record, indent=2, default=str) + "\n")
    print(f"{record['status']}: {len(record['results']) - len(record['failures'])}/{len(record['results'])} "
          f"kill points recovered as expected; failures={record['failures']}")
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
