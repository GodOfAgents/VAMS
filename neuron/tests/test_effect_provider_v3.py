"""Controlled-driver calls plus real ECDSA fixture keys; NOT PostgreSQL proof.

Queued rows exercise branch/control ordering. They do not emulate SQL semantics,
durability, unique constraints, locking, concurrent workers or crash recovery.
"""
from dataclasses import replace
import os
import unittest
from unittest.mock import patch

from neuron.effect_postgres_v3 import PostgresEffectDatabaseV3, META, FENCES, OBJECTS, MIGRATION_HASH
from neuron.effect_provider_v3 import PostgresObjectProviderV3, ObjectProviderIdentityV3, CurrentActionPolicyV1
from neuron.effect_protocol_v3 import (
    EffectV3Error, ObjectFenceV3, SignedEffectReceiptV3, sign_receipt,
    fence_ack_subject, verify_fence_ack, verify_effect, verify_fenced_absence,
)
from neuron.runtime_safety import RuntimeConfigurationError, LiveModeSafetyError
from neuron.signed_receipts import ReceiptError
from neuron.tests.test_effect_protocol_v3 import fixture_proposal, fixture_signer, fixture_admission


class FixturePolicy(CurrentActionPolicyV1):
    def __init__(self): self.calls = []; self.deny_at = None; self.return_value = None
    def assert_allowed(self, proposal, now):
        self.calls.append((proposal.digest, now))
        if len(self.calls) == self.deny_at: raise EffectV3Error('fixture policy DENY/UNKNOWN')
        return self.return_value


class ControlledConnection:
    def __init__(self, identity, rows=(), *, commit_error=None, body_error=None, rollback_error=None, close_error=None):
        self.rows = [(3, MIGRATION_HASH, identity.digest), *rows]
        self.events = []; self.inserts = []; self.commit_error = commit_error
        self.body_error = body_error; self.rollback_error = rollback_error; self.close_error = close_error
    def set_session(self, **kwargs): self.events.append(('session', kwargs))
    def cursor(self): return self
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params=None):
        self.events.append(('execute', sql, params))
        if 'pg_catalog.pg_constraint' in sql or 'tr.tgconstraint::bigint' in sql:
            self.catalog_tables = params[0]; self.catalog_query = sql
        if self.body_error: raise self.body_error
        if sql.startswith('INSERT INTO ' + OBJECTS): self.inserts.append(params)
    def fetchall(self):
        from neuron.tests.effect_unique_catalog_fixture import unique_catalog_rows,additional_catalog_rows
        additional = additional_catalog_rows(self.catalog_query,self.catalog_tables)
        if additional is not None: return additional
        return unique_catalog_rows(self.catalog_tables)
    def fetchone(self):
        if not self.rows: raise AssertionError('controlled test has no queued row')
        return self.rows.pop(0)
    def commit(self):
        self.events.append(('commit',))
        if self.commit_error: raise self.commit_error
    def rollback(self):
        self.events.append(('rollback',))
        if self.rollback_error: raise self.rollback_error
    def close(self):
        self.events.append(('close',))
        if self.close_error: raise self.close_error


class ProviderV3Tests(unittest.TestCase):
    def setUp(self):
        environment = {'VAMS_ENV': 'test', **{n: os.environ[n] for n in ('SystemRoot', 'WINDIR') if n in os.environ}}
        self.environment = patch.dict(os.environ, environment, clear=True)
        self.environment.start(); self.addCleanup(self.environment.stop)
        self.proposal = fixture_proposal()
        self.authority, self.provider_signer = fixture_signer(), fixture_signer()
        c = self.proposal.context
        self.identity = ObjectProviderIdentityV3(c.provider_id, c.host_domain, c.runtime_id,
            c.target, c.chain_id, self.authority.verifier(), self.provider_signer.verifier())
        self.database = PostgresEffectDatabaseV3('postgresql://synthetic-unused', self.identity.digest)
        self.policy = FixturePolicy()
        self.now = 1050
        self.provider = PostgresObjectProviderV3(self.database, self.identity, self.provider_signer,
            self.policy, clock=lambda: self.now)
        self.admission = fixture_admission(self.proposal, self.authority)
        self.fence = ObjectFenceV3.from_context(c, self.proposal.fencing_token)

    def connection(self, *rows, **failures): return ControlledConnection(self.identity, rows, **failures)
    def commit(self, connection):
        with patch.object(self.database, '_connect', return_value=connection):
            return self.provider.commit(self.proposal, self.admission, b'fixture-object')
    def event_names(self, connection): return [v[0] for v in connection.events]

    def test_provider_has_public_only_admission_authority(self):
        self.assertFalse(hasattr(self.provider.identity.authority, 'sign'))
        self.assertFalse(hasattr(self.provider.identity.authority, 'admit'))
        self.assertNotEqual(self.provider.identity.authority.issuer_id, self.provider._signer.verifier().issuer_id)

    def test_constructor_never_connects_or_migrates(self):
        with patch.object(self.database, '_connect', side_effect=AssertionError('connection in constructor')):
            PostgresObjectProviderV3(self.database, self.identity, self.provider_signer, self.policy)

    def test_reused_authority_provider_key_rejects(self):
        with self.assertRaises(EffectV3Error): replace(self.identity, provider=self.identity.authority).digest

    def test_signer_handle_is_not_accepted_as_public_authority(self):
        with self.assertRaises(EffectV3Error): replace(self.identity, authority=self.authority).digest

    def test_other_database_configuration_rejects_before_io(self):
        bad = PostgresEffectDatabaseV3('postgresql://synthetic-unused', b'x' * 32)
        with self.assertRaises(EffectV3Error): PostgresObjectProviderV3(bad, self.identity, self.provider_signer, self.policy)

    def test_untyped_or_boolean_policy_rejects(self):
        for value in (None, True, lambda *args: True):
            with self.assertRaises(EffectV3Error): PostgresObjectProviderV3(self.database, self.identity, self.provider_signer, value)

    def test_current_runtime_snapshot_cannot_rebind(self):
        with self.assertRaises(RuntimeConfigurationError): self.provider.identity = None
        with self.assertRaises(RuntimeConfigurationError): self.database.dsn = 'postgresql://other'

    def test_wrong_or_missing_runtime_rejects_before_driver(self):
        for environment in ({}, {'VAMS_ENV': 'TEST'}, {'VAMS_ENV': 'production'}, {'VAMS_ENV': 'test', 'VAMS_MOCK_MODE': 'true'}):
            with self.subTest(environment=environment), patch.dict(os.environ, environment, clear=True), \
                 patch.object(self.database, '_connect', side_effect=AssertionError('driver reached')):
                with self.assertRaises(LiveModeSafetyError): self.provider.commit(self.proposal, self.admission, b'fixture-object')

    def test_forged_authority_receipt_never_connects(self):
        with patch.object(self.database, '_connect', side_effect=AssertionError('driver reached')), self.assertRaises(ReceiptError):
            self.provider.commit(self.proposal, fixture_admission(self.proposal, self.provider_signer), b'fixture-object')

    def test_initial_policy_denial_has_zero_db_effects(self):
        self.policy.deny_at = 1
        with patch.object(self.database, '_connect', side_effect=AssertionError('driver reached')), self.assertRaises(EffectV3Error):
            self.provider.commit(self.proposal, self.admission, b'fixture-object')

    def test_policy_boolean_return_does_not_grant_permission(self):
        self.policy.return_value = True
        with patch.object(self.database, '_connect', side_effect=AssertionError('driver reached')), self.assertRaises(EffectV3Error):
            self.provider.commit(self.proposal, self.admission, b'fixture-object')

    def test_policy_change_after_lock_prevents_insert(self):
        self.policy.deny_at = 2
        connection = self.connection((self.fence.canonical_bytes(),))
        with self.assertRaises(EffectV3Error): self.commit(connection)
        self.assertEqual(connection.inserts, [])
        self.assertNotIn('commit', self.event_names(connection))
        self.assertEqual(self.event_names(connection)[-2:], ['rollback', 'close'])

    def test_wrong_target_runtime_domain_or_provider_never_connects(self):
        for field, value in dict(provider_id=b'x'*32, host_domain=b'x'*32, runtime_id=b'x'*32,
                                  target=b'x'*32, chain_id=1).items():
            changed = fixture_proposal(**{field: value})
            with patch.object(self.database, '_connect', side_effect=AssertionError('driver reached')), self.assertRaises(EffectV3Error):
                self.provider.commit(changed, fixture_admission(changed, self.authority), b'fixture-object')

    def test_wrong_or_oversized_content_never_connects(self):
        for content in (b'changed', b'x' * 1_048_577, bytearray(b'fixture-object')):
            with patch.object(self.database, '_connect', side_effect=AssertionError('driver reached')), self.assertRaises(EffectV3Error):
                self.provider.commit(self.proposal, self.admission, content)

    def test_success_joins_consumption_object_and_signed_record_before_receipt(self):
        connection = self.connection((self.fence.canonical_bytes(),), None)
        record = self.commit(connection)
        verify_effect(self.proposal, self.admission, record, self.identity.provider, self.now, authority=self.identity.authority)
        self.assertEqual(len(connection.inserts), 1)
        row = connection.inserts[0]
        self.assertEqual(row[0], self.proposal.operation_id)
        self.assertEqual(row[5:8], (self.admission.digest, self.proposal.context.nonce, b'fixture-object'))
        self.assertEqual(SignedEffectReceiptV3.from_bytes(row[8]), record)
        self.assertEqual(self.event_names(connection)[-2:], ['commit', 'close'])
        self.assertEqual(len(self.policy.calls), 2)
        self.assertEqual(connection.rows, [])

    def test_missing_or_stale_fence_has_zero_inserts(self):
        for row in (None, (replace(self.fence, fencing_token=8).canonical_bytes(),),
                    (replace(self.fence, policy_root=b'x'*32).canonical_bytes(),)):
            connection = self.connection(row)
            with self.assertRaises(EffectV3Error): self.commit(connection)
            self.assertEqual(connection.inserts, [])

    def test_unknown_commit_does_not_return_or_retry_and_keeps_identity(self):
        failure = RuntimeError('controlled unknown commit outcome')
        connection = self.connection((self.fence.canonical_bytes(),), None, commit_error=failure)
        with self.assertRaises(RuntimeError) as raised: self.commit(connection)
        self.assertIs(raised.exception, failure)
        self.assertEqual(len(connection.inserts), 1)
        self.assertEqual(connection.inserts[0][0], self.proposal.operation_id)
        self.assertEqual(self.event_names(connection).count('commit'), 1)
        self.assertEqual(self.event_names(connection)[-2:], ['rollback', 'close'])

    def test_cleanup_failures_do_not_replace_primary_commit_failure(self):
        failure = RuntimeError('controlled unknown commit')
        connection = self.connection((self.fence.canonical_bytes(),), None, commit_error=failure,
            rollback_error=ValueError('cleanup rollback'), close_error=ValueError('cleanup close'))
        with self.assertRaises(RuntimeError) as raised: self.commit(connection)
        self.assertIs(raised.exception, failure)
        self.assertEqual(self.event_names(connection)[-2:], ['rollback', 'close'])

    def test_schema_or_identity_mismatch_rejects_before_effect(self):
        for first in ((2, MIGRATION_HASH, self.identity.digest), (3, b'x'*32, self.identity.digest),
                      (3, MIGRATION_HASH, b'x'*32), None):
            connection = self.connection(); connection.rows = [first]
            with self.assertRaises(EffectV3Error): self.commit(connection)
            self.assertEqual(connection.inserts, [])

    def test_historical_lookup_after_policy_change_does_not_dispatch(self):
        original = self.connection((self.fence.canonical_bytes(),), None)
        record = self.commit(original)
        row = original.inserts[0]
        self.now = 2000; self.policy.deny_at = 3
        connection = self.connection((row[3], row[4], row[7], row[8]))
        with patch.object(self.database, '_connect', return_value=connection):
            recovered = self.provider.lookup(self.proposal, self.admission)
        self.assertEqual(recovered, record)
        self.assertEqual(len(self.policy.calls), 2)
        self.assertEqual(connection.inserts, [])
        with self.assertRaises((EffectV3Error, ReceiptError)):
            self.provider.commit(self.proposal, self.admission, b'fixture-object')

    def test_lookup_rejects_tampered_persisted_bytes(self):
        original = self.connection((self.fence.canonical_bytes(),), None)
        self.commit(original); row = original.inserts[0]
        connection = self.connection((row[3], row[4], b'corrupt', row[8]))
        with patch.object(self.database, '_connect', return_value=connection), self.assertRaises(EffectV3Error):
            self.provider.lookup(self.proposal, self.admission)

    def test_repeated_current_commit_returns_only_retained_same_obligation(self):
        original = self.connection((self.fence.canonical_bytes(),), None)
        record = self.commit(original); row = original.inserts[0]
        connection = self.connection((self.fence.canonical_bytes(),), (row[3], row[4], row[7], row[8]))
        self.assertEqual(self.commit(connection), record)
        self.assertEqual(connection.inserts, [])

    def test_fence_ack_escapes_after_transaction_commit(self):
        f = self.fence
        update = sign_receipt(self.authority, purpose=2, subject=f.digest, provider=f.provider_id,
            epoch=f.authority_epoch, policy=f.policy_version, fence=f.fencing_token,
            issued_at=f.issued_at, expires_at=f.expires_at)
        connection = self.connection(None)
        with patch.object(self.database, '_connect', return_value=connection): ack = self.provider.advance_fence(f, update)
        verify_fence_ack(f, update, ack, self.identity.provider, self.now, authority=self.identity.authority)
        self.assertEqual(self.event_names(connection)[-2:], ['commit', 'close'])

    def test_fence_commit_failure_does_not_release_ack(self):
        f = self.fence
        update = sign_receipt(self.authority, purpose=2, subject=f.digest, provider=f.provider_id,
            epoch=f.authority_epoch, policy=f.policy_version, fence=f.fencing_token,
            issued_at=f.issued_at, expires_at=f.expires_at)
        connection = self.connection(None, commit_error=RuntimeError('unknown fence commit'))
        with patch.object(self.database, '_connect', return_value=connection), self.assertRaisesRegex(RuntimeError, 'unknown fence'):
            self.provider.advance_fence(f, update)
        self.assertEqual(self.event_names(connection).count('commit'), 1)

    def test_database_missing_driver_never_falls_back_to_sqlite(self):
        import sys
        with patch.dict(sys.modules, {'psycopg2': None}), self.assertRaises(EffectV3Error): self.database._connect()

    def test_explicit_migration_rejects_partial_schema(self):
        connection = self.connection(); connection.rows = [(META, None, None)]
        with patch.object(self.database, '_connect', return_value=connection), self.assertRaises(EffectV3Error):
            self.database.migrate()
        self.assertNotIn('commit', self.event_names(connection))

    def test_explicit_new_schema_migration_and_version_readback(self):
        connection = self.connection()
        connection.rows = [(None, None, None), (3, MIGRATION_HASH, self.identity.digest)]
        with patch.object(self.database, '_connect', return_value=connection): self.database.migrate()
        statements = [v[1] for v in connection.events if v[0] == 'execute']
        self.assertEqual(sum(s.startswith('CREATE TABLE ') for s in statements), 3)
        self.assertEqual(self.event_names(connection)[-2:], ['commit', 'close'])

    def fence_evidence(self, fence):
        update = sign_receipt(self.authority, purpose=2, subject=fence.digest, provider=fence.provider_id,
            epoch=fence.authority_epoch, policy=fence.policy_version, fence=fence.fencing_token,
            issued_at=fence.issued_at, expires_at=fence.expires_at)
        ack = sign_receipt(self.provider_signer, purpose=3, subject=fence_ack_subject(fence, update),
            provider=fence.provider_id, epoch=fence.authority_epoch, policy=fence.policy_version,
            fence=fence.fencing_token, issued_at=self.now, expires_at=fence.expires_at)
        return update, ack

    def test_fence_does_not_downgrade_epoch_policy_or_token(self):
        old_update, old_ack = self.fence_evidence(self.fence)
        for changes in ({'authority_epoch': 3, 'fencing_token': 10},
                        {'authority_epoch': 4, 'fencing_token': 9},
                        {'authority_epoch': 4, 'fencing_token': 10, 'policy_version': 6},
                        {'authority_epoch': 4, 'fencing_token': 10, 'policy_root': b'X'*32}):
            fence = replace(self.fence, **changes)
            update, _ = self.fence_evidence(fence)
            connection = self.connection((self.fence.canonical_bytes(), old_update.canonical_bytes(), old_ack.canonical_bytes()))
            with patch.object(self.database, '_connect', return_value=connection), self.assertRaises(EffectV3Error):
                self.provider.advance_fence(fence, update)
            self.assertNotIn('commit', self.event_names(connection))

    def test_expired_fence_cannot_create_an_ack(self):
        update, _ = self.fence_evidence(self.fence)
        self.now = 1100
        with patch.object(self.database, '_connect', side_effect=AssertionError('driver reached')), self.assertRaises(ReceiptError):
            self.provider.advance_fence(self.fence, update)

    def test_authenticated_absence_requires_retained_newer_fence(self):
        fence = replace(self.fence, authority_epoch=4, policy_version=8, fencing_token=10)
        update, ack = self.fence_evidence(fence)
        connection = self.connection((fence.canonical_bytes(), update.canonical_bytes(), ack.canonical_bytes()), None)
        with patch.object(self.database, '_connect', return_value=connection):
            absence = self.provider.prove_fenced_absence(self.proposal, fence, update, ack)
        verify_fenced_absence(self.proposal, fence, update, ack, absence, self.identity.provider,
            self.now + 1000, authority=self.identity.authority)
        self.assertEqual(connection.inserts, [])
        self.assertEqual(self.event_names(connection)[-2:], ['commit', 'close'])

    def test_existing_operation_cannot_be_reported_absent(self):
        fence = replace(self.fence, authority_epoch=4, policy_version=8, fencing_token=10)
        update, ack = self.fence_evidence(fence)
        connection = self.connection((fence.canonical_bytes(), update.canonical_bytes(), ack.canonical_bytes()), (1,))
        with patch.object(self.database, '_connect', return_value=connection), self.assertRaises(EffectV3Error):
            self.provider.prove_fenced_absence(self.proposal, fence, update, ack)
        self.assertNotIn('commit', self.event_names(connection))

    def test_missing_retained_fence_never_proves_absence(self):
        fence = replace(self.fence, authority_epoch=4, policy_version=8, fencing_token=10)
        update, ack = self.fence_evidence(fence)
        connection = self.connection(None)
        with patch.object(self.database, '_connect', return_value=connection), self.assertRaises(EffectV3Error):
            self.provider.prove_fenced_absence(self.proposal, fence, update, ack)

    def test_absence_requires_new_epoch_and_fencing_token(self):
        update, ack = self.fence_evidence(self.fence)
        with patch.object(self.database, '_connect', side_effect=AssertionError('driver reached')), self.assertRaises(EffectV3Error):
            self.provider.prove_fenced_absence(self.proposal, self.fence, update, ack)

    def test_lost_fence_ack_can_be_recovered_after_expiry_without_resend(self):
        update, ack = self.fence_evidence(self.fence)
        self.now = 2000
        connection = self.connection((self.fence.canonical_bytes(), update.canonical_bytes(), ack.canonical_bytes()))
        with patch.object(self.database, '_connect', return_value=connection):
            self.assertEqual(self.provider.lookup_fence(self.fence, update), ack)
        self.assertEqual(connection.inserts, [])
        statements = [v[1] for v in connection.events if v[0] == 'execute']
        self.assertFalse(any(s.startswith(('INSERT', 'UPDATE')) for s in statements))

    def test_unknown_fence_lookup_is_not_an_acknowledgement(self):
        update, _ = self.fence_evidence(self.fence)
        connection = self.connection(None)
        with patch.object(self.database, '_connect', return_value=connection):
            self.assertIsNone(self.provider.lookup_fence(self.fence, update))

    def test_old_wire_objects_cannot_enter_v3_direct_commit(self):
        for value in (None, {}, b'old-v2-mac', self.proposal.canonical_bytes()):
            with patch.object(self.database, '_connect', side_effect=AssertionError('driver reached')), self.assertRaises(EffectV3Error):
                self.provider.commit(value, self.admission, b'fixture-object')


if __name__ == '__main__': unittest.main()
