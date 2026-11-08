"""Durable revocation clock rollback regressions; SQLite only, local tests."""

from __future__ import annotations

import gc
import hashlib
import os
import sqlite3
import tempfile
import unittest
from contextlib import ExitStack, closing
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from gateway.replay_store import (
    REPLAY_CLOCK_ROLLBACK_TOLERANCE_SECONDS,
    CleanupOutcome,
    RevocationIdentity,
    RevocationOutcome,
    SQLiteDurableReplayStore,
    SQLiteReplayConfiguration,
)
from gateway.request_auth import (
    AUTH_VERSION,
    GatewayRequestAuthenticator,
    KeyResolution,
    KeyStatus,
    ReplayNamespace,
    ReplayOutcome,
    gateway_auth_dependency,
)
from neuron.runtime_safety import REGISTERED_MOCK_VARIABLES, load_runtime_policy
from neuron.tests.m2_gateway_helpers import AUDIENCE, SIGNER, signed_headers


T = 1_800_000_000
BODY = b'{"action":"protected"}'
PATH = b"/protected"


class MutableClock:
    def __init__(self, value: int):
        self.value = value
        self.script = []

    def now(self) -> int:
        if self.script:
            self.value = self.script.pop(0)
        return self.value


class FixedSignerResolver:
    def resolve(self, signer: str) -> KeyResolution:
        if signer != SIGNER:
            return KeyResolution(KeyStatus.UNKNOWN)
        from neuron.tests.m2_gateway_helpers import PUBLIC_KEY

        return KeyResolution(KeyStatus.AVAILABLE, PUBLIC_KEY)


class SyntheticRequest:
    """Minimal ASGI-shaped request consumed by GatewayRequestAuthenticator."""

    def __init__(self, headers: dict[str, str], body: bytes = BODY):
        self.scope = {
            "type": "http",
            "method": "POST",
            "raw_path": PATH,
            "query_string": b"",
            "headers": [
                (name.lower().encode("ascii"), value.encode("ascii"))
                for name, value in headers.items()
            ],
        }
        self._body = body

    async def body(self) -> bytes:
        return self._body


class GatewayRevocationClockTest(unittest.TestCase):
    def setUp(self):
        self._environment = ExitStack()
        self._environment.enter_context(patch.dict(os.environ, {"VAMS_ENV": "test"}))
        for variable in REGISTERED_MOCK_VARIABLES:
            self._environment.enter_context(patch.dict(os.environ, {variable: ""}))
            os.environ.pop(variable, None)
        self.temporary = tempfile.TemporaryDirectory(prefix="vams-replay-clock-")
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(self._environment.close)
        # Old SQLite code leaves connection cycles for GC; collect those only
        # for test cleanup. The explicit-close regression below does not rely
        # on GC and keeps every connection alive through its assertion.
        self.addCleanup(gc.collect)
        self.database = Path(self.temporary.name) / "replay.sqlite3"

    def store(self, clock: MutableClock) -> SQLiteDurableReplayStore:
        return SQLiteDurableReplayStore(
            SQLiteReplayConfiguration(database_path=str(self.database)),
            load_runtime_policy(),
            clock=clock,
        )

    def auth_dependency(self, store, clock: MutableClock):
        auth = GatewayRequestAuthenticator(
            expected_audience=AUDIENCE,
            clock=clock,
            key_resolver=FixedSignerResolver(),
            replay_store=store,
        )
        return gateway_auth_dependency(auth)

    @staticmethod
    def headers(nonce: int, *, now: int, issued_at: int, expires_at: int):
        return signed_headers(
            "POST",
            PATH.decode("ascii"),
            body=BODY,
            nonce=nonce,
            now=now,
            issued_at=issued_at,
            expires_at=expires_at,
            audience=AUDIENCE,
        )

    @staticmethod
    async def protected_call(dependency, request, effects):
        try:
            authenticated = await dependency(request)
        except HTTPException as exc:
            return exc
        effects.append(authenticated)
        return authenticated

    def dependency_call(self, dependency, headers, effects):
        coroutine = self.protected_call(
            dependency, SyntheticRequest(headers), effects
        )
        try:
            coroutine.send(None)
        except StopIteration as completed:
            return completed.value
        finally:
            coroutine.close()
        self.fail("synthetic authentication unexpectedly suspended for I/O")

    def revoke(self, store, *, signer_digest: bytes, effective_at: int, now: int):
        return store.revoke_signer(
            RevocationIdentity(signer_digest), effective_at=effective_at, now=now
        )

    def test_effective_revocation_survives_tolerated_rollbacks_and_restart(self):
        clock = MutableClock(T)
        store = self.store(clock)
        digest = hashlib.sha256(SIGNER.encode("ascii")).digest()
        self.assertEqual(
            self.revoke(store, signer_digest=digest, effective_at=T, now=T),
            RevocationOutcome.APPLIED,
        )
        effects = []
        dependency = self.auth_dependency(store, clock)

        first = self.dependency_call(
            dependency,
            self.headers(100, now=T, issued_at=T, expires_at=T + 30),
            effects,
        )
        self.assertIsInstance(first, HTTPException)
        self.assertEqual(first.status_code, 401)
        self.assertIn("revoked_nonce", first.detail)
        self.assertEqual(effects, [])

        for nonce, rollback in enumerate((1, 299, 300), start=101):
            with self.subTest(rollback=rollback):
                clock.value = T - rollback
                # Reopen the same durable store to exercise restart persistence.
                restarted = self.store(clock)
                dependency = self.auth_dependency(restarted, clock)
                denied = self.dependency_call(
                    dependency,
                    self.headers(
                        nonce,
                        now=T - rollback,
                        issued_at=T,
                        expires_at=T + 30,
                    ),
                    effects,
                )
                self.assertIsInstance(denied, HTTPException)
                self.assertEqual(denied.status_code, 401)
                self.assertIn("revoked_nonce", denied.detail)
                self.assertEqual(effects, [])

    def test_rollback_beyond_tolerance_is_storage_failure(self):
        clock = MutableClock(T)
        store = self.store(clock)
        digest = hashlib.sha256(SIGNER.encode("ascii")).digest()
        self.assertEqual(
            self.revoke(store, signer_digest=digest, effective_at=T, now=T),
            RevocationOutcome.APPLIED,
        )
        clock.value = T - REPLAY_CLOCK_ROLLBACK_TOLERANCE_SECONDS - 1
        namespace = ReplayNamespace(
            AUTH_VERSION,
            AUDIENCE,
            digest,
            (900).to_bytes(16, "big"),
        )
        self.assertEqual(
            store.reserve_and_consume(
                namespace,
                expires_at=T + 30,
                now=clock.value,
            ),
            ReplayOutcome.STORAGE_FAILURE,
        )

    def test_nonrevoked_signer_accepts_once_then_duplicate_remains_denied(self):
        clock = MutableClock(T)
        store = self.store(clock)
        dependency = self.auth_dependency(store, clock)
        effects = []
        headers = self.headers(201, now=T, issued_at=T, expires_at=T + 30)
        accepted = self.dependency_call(dependency, headers, effects)
        self.assertFalse(isinstance(accepted, HTTPException))
        self.assertEqual(len(effects), 1)
        duplicate = self.dependency_call(dependency, headers, effects)
        self.assertIsInstance(duplicate, HTTPException)
        self.assertEqual(duplicate.status_code, 401)
        self.assertIn("duplicate_nonce", duplicate.detail)
        self.assertEqual(len(effects), 1)

    def test_scheduled_revocation_is_not_effective_before_its_time(self):
        clock = MutableClock(T)
        store = self.store(clock)
        digest = hashlib.sha256(SIGNER.encode("ascii")).digest()
        self.assertEqual(
            self.revoke(store, signer_digest=digest, effective_at=T + 60, now=T),
            RevocationOutcome.APPLIED,
        )
        effects = []
        clock.value = T + 30
        dependency = self.auth_dependency(store, clock)
        accepted = self.dependency_call(
            dependency,
            self.headers(301, now=T + 30, issued_at=T + 30, expires_at=T + 60),
            effects,
        )
        self.assertFalse(isinstance(accepted, HTTPException))
        self.assertEqual(len(effects), 1)

        clock.value = T + 60
        denied = self.dependency_call(
            dependency,
            self.headers(302, now=T + 60, issued_at=T + 60, expires_at=T + 90),
            effects,
        )
        self.assertIsInstance(denied, HTTPException)
        self.assertIn("revoked_nonce", denied.detail)
        self.assertEqual(len(effects), 1)

    def test_persisted_high_watermark_bounds_expiry_recording_reservation_and_cleanup(self):
        clock = MutableClock(T - 500)
        store = self.store(clock)
        signer = hashlib.sha256(b"cleanup-row-signer").digest()
        expiring = ReplayNamespace(
            AUTH_VERSION, AUDIENCE, signer, (401).to_bytes(16, "big")
        )
        # At T-500, this reservation's retention boundary is exactly T.
        self.assertEqual(
            store.reserve_and_consume(expiring, expires_at=T - 360, now=T - 500),
            ReplayOutcome.ACCEPTED,
        )
        clock.value = T
        self.assertEqual(
            self.revoke(
                store,
                signer_digest=hashlib.sha256(b"watermark-anchor").digest(),
                effective_at=T,
                now=T,
            ),
            RevocationOutcome.APPLIED,
        )

        # A tolerant rollback must still run cleanup at logical time T.
        clock.value = T - 1
        cleaned = store.cleanup(now=T - 1)
        self.assertEqual(cleaned.outcome, CleanupOutcome.COMPLETED)
        with sqlite3.connect(self.database) as connection:
            row = connection.execute(
                "SELECT 1 FROM replay_reservations WHERE nonce = ?",
                (expiring.nonce,),
            ).fetchone()
        self.assertIsNone(row)

        # Recording and reservation timestamps use the same durable logical time.
        future_digest = hashlib.sha256(b"future-revocation").digest()
        self.assertEqual(
            self.revoke(
                store,
                signer_digest=future_digest,
                effective_at=T + 50,
                now=T - 1,
            ),
            RevocationOutcome.APPLIED,
        )
        ns = ReplayNamespace(
            AUTH_VERSION,
            AUDIENCE,
            hashlib.sha256(b"ordinary-signer").digest(),
            (402).to_bytes(16, "big"),
        )
        self.assertEqual(
            store.reserve_and_consume(ns, expires_at=T + 30, now=T - 1),
            ReplayOutcome.ACCEPTED,
        )
        clock.value = T - 2
        expired = ReplayNamespace(
            AUTH_VERSION,
            AUDIENCE,
            ns.signer_digest,
            (403).to_bytes(16, "big"),
        )
        self.assertEqual(
            store.reserve_and_consume(expired, expires_at=T - 1, now=T - 2),
            ReplayOutcome.STORAGE_FAILURE,
        )
        # The wall clock also rolls back between transaction start and commit.
        clock.script = [T - 1, T - 2]
        commit_ns = ReplayNamespace(
            AUTH_VERSION,
            AUDIENCE,
            hashlib.sha256(b"commit-clock-signer").digest(),
            (404).to_bytes(16, "big"),
        )
        self.assertEqual(
            store.reserve_and_consume(
                commit_ns,
                expires_at=T + 30,
                now=T - 1,
            ),
            ReplayOutcome.ACCEPTED,
        )
        with sqlite3.connect(self.database) as connection:
            recorded = connection.execute(
                "SELECT recorded_at FROM signer_revocations WHERE signer_digest = ?",
                (future_digest,),
            ).fetchone()
            reserved = connection.execute(
                "SELECT reserved_at FROM replay_reservations WHERE nonce = ?",
                (ns.nonce,),
            ).fetchone()
            commit_reserved = connection.execute(
                "SELECT reserved_at FROM replay_reservations WHERE nonce = ?",
                (commit_ns.nonce,),
            ).fetchone()
        self.assertEqual(recorded, (T,))
        self.assertEqual(reserved, (T,))
        self.assertEqual(commit_reserved, (T,))


    def test_connections_close_after_success_lock_failure_and_setup_failure(self):
        original_connect = sqlite3.connect
        opened = []
        fail_setup = [False]

        class TrackedConnection(sqlite3.Connection):
            explicitly_closed = False
            def close(self):
                self.explicitly_closed = True
                return super().close()
            def execute(self, statement, *args):
                if fail_setup[0] and statement.startswith("PRAGMA busy_timeout="):
                    raise sqlite3.OperationalError("synthetic setup failure")
                return super().execute(statement, *args)

        def tracked_connect(*args, **kwargs):
            connection = original_connect(*args, factory=TrackedConnection, **kwargs)
            opened.append(connection)
            return connection

        try:
            with patch("gateway.replay_store.sqlite3.connect", side_effect=tracked_connect):
                clock = MutableClock(T)
                store = self.store(clock)
                namespace = ReplayNamespace(AUTH_VERSION, AUDIENCE, b"n" * 32, (601).to_bytes(16, "big"))
                self.assertEqual(store.reserve_and_consume(namespace, expires_at=T + 60, now=T), ReplayOutcome.ACCEPTED)
                self.assertEqual(self.revoke(store, signer_digest=b"r" * 32, effective_at=T, now=T), RevocationOutcome.APPLIED)
                self.assertEqual(store.cleanup(now=T).outcome, CleanupOutcome.COMPLETED)
                with closing(original_connect(self.database, isolation_level=None)) as blocker:
                    blocker.execute("BEGIN IMMEDIATE")
                    self.assertEqual(store.reserve_and_consume(namespace, expires_at=T + 60, now=T), ReplayOutcome.STORAGE_FAILURE)
                    blocker.rollback()
                fail_setup[0] = True
                self.assertEqual(store.cleanup(now=T).outcome, CleanupOutcome.STORAGE_FAILURE)
                self.assertEqual(len(opened), 6)
                self.assertTrue(all(connection.explicitly_closed for connection in opened))
        finally:
            for connection in opened:
                connection.close()

    def test_noninteger_durable_clock_fails_closed_at_every_storage_entrypoint(self):
        clock = MutableClock(T)
        store = self.store(clock)
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("UPDATE replay_metadata SET clock_high_watermark=?", (T + 0.5,))
        namespace = ReplayNamespace(AUTH_VERSION, AUDIENCE, b"f" * 32, (602).to_bytes(16, "big"))
        self.assertEqual(store.reserve_and_consume(namespace, expires_at=T + 60, now=T), ReplayOutcome.STORAGE_FAILURE)
        self.assertEqual(self.revoke(store, signer_digest=b"f" * 32, effective_at=T, now=T), RevocationOutcome.STORAGE_FAILURE)
        self.assertEqual(store.cleanup(now=T).outcome, CleanupOutcome.STORAGE_FAILURE)


if __name__ == "__main__":
    unittest.main()
