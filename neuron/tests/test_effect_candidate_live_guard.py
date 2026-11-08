"""Startup containment only; no live backend, PG or external-effect evidence."""
from contextlib import ExitStack
import os
import unittest
from unittest.mock import patch

from neuron.effect_postgres_v3 import PostgresEffectDatabaseV3
from neuron.effect_authority_store_v3 import PostgresAuthorityDatabaseV3, authority_configuration
from neuron.effect_authority_store_v4 import PostgresAuthorityDatabaseV4, authority_configuration_v4
from neuron.effect_provider_v3 import PostgresObjectProviderV3, ObjectProviderIdentityV3
from neuron.effect_authority_v3 import PostgresEffectAuthorityV3
from neuron.effect_authority_v4 import PostgresEffectAuthorityV4
from neuron.runtime_safety import LiveModeSafetyError
from neuron.signed_receipts import ReceiptSignerV3
from neuron.tests.test_effect_protocol_v3 import fixture_proposal, fixture_signer
from neuron.tests.test_effect_provider_v3 import FixturePolicy
from neuron.tests.test_effect_authority_v3 import FixtureAuthorityPolicy
from neuron.tests.test_effect_renewal_v4 import FixtureRenewalPolicy


class EffectCandidateStartupTests(unittest.TestCase):
    def attempt(self, mode, kind, reject):
        environment = {'VAMS_ENV': mode, **{n: os.environ[n] for n in ('SystemRoot', 'WINDIR') if n in os.environ}}
        with patch.dict(os.environ, environment, clear=True):
            c = fixture_proposal().context
            authority, provider = fixture_signer(), fixture_signer()
            identity = ObjectProviderIdentityV3(c.provider_id, c.host_domain, c.runtime_id,
                c.target, c.chain_id, authority.verifier(), provider.verifier())
            classes = {
                'provider': (PostgresEffectDatabaseV3, PostgresObjectProviderV3, identity.digest, provider, FixturePolicy),
                'authority3': (PostgresAuthorityDatabaseV3, PostgresEffectAuthorityV3, authority_configuration(identity), authority, FixtureAuthorityPolicy),
                'authority4': (PostgresAuthorityDatabaseV4, PostgresEffectAuthorityV4, authority_configuration_v4(identity), authority, FixtureRenewalPolicy),
            }
            database_type, candidate_type, configuration, signer, policy_type = classes[kind]
            database = database_type('postgresql://synthetic-unused', configuration)
            policy = policy_type()
            events = []
            def forbidden(name):
                def invoke(*args, **kwargs):
                    events.append(name)
                    raise AssertionError('startup reached ' + name)
                return invoke
            with ExitStack() as stack:
                stack.enter_context(patch.object(database, '_connect', side_effect=forbidden('connect')))
                stack.enter_context(patch.object(database, 'migrate', side_effect=forbidden('migrate')))
                stack.enter_context(patch.object(ReceiptSignerV3, 'sign', side_effect=forbidden('sign')))
                for method in ('assert_allowed', 'assert_scope_allowed', 'assert_fence_allowed', 'assert_renewal_allowed'):
                    if hasattr(policy, method):
                        stack.enter_context(patch.object(policy, method, side_effect=forbidden(method)))
                def construct():
                    return candidate_type(database, identity, signer, policy, clock=forbidden('clock'))
                if reject:
                    with self.assertRaises(LiveModeSafetyError):
                        construct()
                else:
                    self.assertIsInstance(construct(), candidate_type)
                self.assertEqual(events, [])
                self.assertEqual(policy.calls, [])

    def test_staging_provider_rejects(self):
        self.attempt('staging', 'provider', True)

    def test_testnet_provider_rejects(self):
        self.attempt('testnet', 'provider', True)

    def test_production_provider_rejects(self):
        self.attempt('production', 'provider', True)

    def test_staging_authority3_rejects(self):
        self.attempt('staging', 'authority3', True)

    def test_testnet_authority3_rejects(self):
        self.attempt('testnet', 'authority3', True)

    def test_production_authority3_rejects(self):
        self.attempt('production', 'authority3', True)

    def test_staging_authority4_rejects(self):
        self.attempt('staging', 'authority4', True)

    def test_testnet_authority4_rejects(self):
        self.attempt('testnet', 'authority4', True)

    def test_production_authority4_rejects(self):
        self.attempt('production', 'authority4', True)

    def test_nonlive_provider_fixtures_remain_available(self):
        for mode in ('test', 'local', 'demo'):
            with self.subTest(mode=mode):
                self.attempt(mode, 'provider', False)

    def test_nonlive_authority3_fixtures_remain_available(self):
        for mode in ('test', 'local', 'demo'):
            with self.subTest(mode=mode):
                self.attempt(mode, 'authority3', False)

    def test_nonlive_authority4_fixtures_remain_available(self):
        for mode in ('test', 'local', 'demo'):
            with self.subTest(mode=mode):
                self.attempt(mode, 'authority4', False)
