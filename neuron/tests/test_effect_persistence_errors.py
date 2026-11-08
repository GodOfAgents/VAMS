"""Public error rendering with synthetic driver failures; not native PG evidence."""
import io
import logging
import os
import sys
import traceback
import types
import unittest
from unittest.mock import Mock,patch

from neuron.effect_postgres_v3 import PostgresEffectDatabaseV3
from neuron.effect_protocol_v3 import EffectV3Error
from neuron.tests import test_effect_provider_v3 as provider_fixtures

SENSITIVE='fixture_private_record_do_not_log'

class FixturePgError(Exception):
    def __init__(self):
        super().__init__('synthetic backend detail: '+SENSITIVE)
        self.pgerror=SENSITIVE;self.pgcode='23505'
        self.diag=types.SimpleNamespace(message_detail=SENSITIVE)
        self.cursor=types.SimpleNamespace(query=SENSITIVE)

class FixtureIntegrityError(FixturePgError):pass
class FixtureOperationalError(FixturePgError):pass

class ErrorConnection:
    def __init__(self,phase,error=None,cleanup_error=None):
        self.phase=phase;self.error=error or FixturePgError();self.cleanup_error=cleanup_error
        self.events=[]
    def set_session(self,**kwargs):
        self.events.append('SESSION')
        if self.phase=='SESSION':raise self.error
    def commit(self):
        self.events.append('COMMIT')
        if self.phase=='COMMIT':raise self.error
    def rollback(self):
        self.events.append('ROLLBACK')
        if self.cleanup_error:raise self.cleanup_error
    def close(self):
        self.events.append('CLOSE')
        if self.phase=='CLOSE':raise self.error
        if self.cleanup_error:raise self.cleanup_error

class PersistenceErrorPrivacyTests(unittest.TestCase):
    def setUp(self):
        environment={'VAMS_ENV':'test',**{n:os.environ[n] for n in ('SystemRoot','WINDIR') if n in os.environ}}
        self.env=patch.dict(os.environ,environment,clear=True);self.env.start();self.addCleanup(self.env.stop)
        self.driver=types.ModuleType('psycopg2');self.driver.Error=FixturePgError
        self.driver.connect=Mock(side_effect=FixturePgError())
        self.modules=patch.dict(sys.modules,{'psycopg2':self.driver});self.modules.start();self.addCleanup(self.modules.stop)
        self.db=PostgresEffectDatabaseV3('postgresql://synthetic-unused',b'c'*32)
    def caught(self,callback):
        try:callback()
        except Exception as exc:return exc
        self.fail('failure returned a successful result')
    def transaction(self,connection,error=None):
        with patch.object(self.db,'_connect',return_value=connection):
            with self.db._transaction():
                connection.events.append('BODY')
                if error is not None:raise error
                return 'success-only-after-context-exit'
    def assert_public_error(self,error,phase):
        self.assertNotIn(SENSITIVE,str(error))
        self.assertNotIn(SENSITIVE,repr(error))
        self.assertNotIn(SENSITIVE,''.join(traceback.format_exception(error)))
        self.assertEqual(getattr(error,'stage',None),phase)
        self.assertEqual(getattr(error,'outcome',None),'UNKNOWN')
        self.assertIsNone(error.__cause__)
        self.assertNotIn(SENSITIVE,repr(vars(error)))
        self.assertFalse(any(hasattr(error,n) for n in ('pgerror','pgcode','diag','cursor')))
    def test_connection_driver_details_are_not_public(self):
        self.assert_public_error(self.caught(self.db._connect),'CONNECT')
        self.assertEqual(self.driver.connect.call_count,1)
    def test_session_body_commit_and_close_details_are_not_public(self):
        for phase in ('SESSION','BODY','COMMIT','CLOSE'):
            with self.subTest(phase=phase):
                c=ErrorConnection(phase)
                error=self.caught(lambda:self.transaction(c,c.error if phase=='BODY' else None))
                self.assert_public_error(error,phase)
    def test_driver_subclasses_are_redacted(self):
        for kind in (FixtureIntegrityError,FixtureOperationalError):
            with self.subTest(kind=kind.__name__):
                c=ErrorConnection('COMMIT',kind())
                self.assert_public_error(self.caught(lambda:self.transaction(c)),'COMMIT')
    def test_cleanup_failures_do_not_replace_primary_driver_failure(self):
        c=ErrorConnection('COMMIT',cleanup_error=FixtureOperationalError())
        self.assert_public_error(self.caught(lambda:self.transaction(c)),'COMMIT')
        self.assertEqual(c.events,['SESSION','BODY','COMMIT','ROLLBACK','CLOSE'])
    def test_domain_failure_keeps_identity_and_cleanup(self):
        error=EffectV3Error('bounded domain failure');c=ErrorConnection('none',cleanup_error=FixturePgError())
        self.assertIs(self.caught(lambda:self.transaction(c,error)),error)
        self.assertEqual(c.events,['SESSION','BODY','ROLLBACK','CLOSE'])
    def test_interrupt_keeps_identity_and_cleanup(self):
        error=KeyboardInterrupt();c=ErrorConnection('none')
        with self.assertRaises(KeyboardInterrupt) as raised:self.transaction(c,error)
        self.assertIs(raised.exception,error);self.assertEqual(c.events,['SESSION','BODY','ROLLBACK','CLOSE'])
    def test_non_driver_failure_keeps_existing_semantics(self):
        error=RuntimeError('controlled non-driver failure');c=ErrorConnection('COMMIT',error)
        self.assertIs(self.caught(lambda:self.transaction(c)),error)
        self.assertEqual(c.events.count('COMMIT'),1)
    def test_provider_unknown_commit_does_not_escape_receipt_or_retry(self):
        fixture=provider_fixtures.ProviderV3Tests('test_constructor_never_connects_or_migrates')
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        c=fixture.connection((fixture.fence.canonical_bytes(),),None,commit_error=FixturePgError())
        error=self.caught(lambda:fixture.commit(c));self.assert_public_error(error,'COMMIT')
        self.assertEqual(len(c.inserts),1)
        self.assertEqual(c.inserts[0][0],fixture.proposal.operation_id)
        self.assertEqual(fixture.event_names(c).count('commit'),1)
        self.assertEqual(fixture.event_names(c)[-2:],['rollback','close'])
    def test_close_failure_after_commit_is_unknown_without_retry_or_refund(self):
        c=ErrorConnection('CLOSE')
        self.assert_public_error(self.caught(lambda:self.transaction(c)),'CLOSE')
        self.assertEqual(c.events,['SESSION','BODY','COMMIT','CLOSE'])
    def test_standard_logger_does_not_render_driver_or_chained_detail(self):
        stream=io.StringIO();logger=logging.Logger('synthetic-error-rendering')
        logger.addHandler(logging.StreamHandler(stream))
        try:self.db._connect()
        except Exception:logger.exception('bounded persistence failure')
        self.assertNotIn(SENSITIVE,stream.getvalue())
        self.assertIn('bounded persistence failure',stream.getvalue())
    def test_serialization_contains_only_bounded_public_metadata(self):
        error=self.caught(self.db._connect)
        self.assertEqual(vars(error),{'stage':'CONNECT','outcome':'UNKNOWN'})
        self.assert_public_error(error,'CONNECT')

if __name__=='__main__':unittest.main()
