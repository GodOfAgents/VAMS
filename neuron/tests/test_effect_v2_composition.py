"""Additive composition/migration guards; SQL doubles do not qualify PostgreSQL."""
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from neuron.effect_canary import (
    AttenuatedCapability,EffectError,EffectCoordinator,PostgresAuthorityRepository,
)
from neuron.effect_proposal import AuthoritySignerV2,ProtocolError
from neuron.effect_gate_v2 import ObjectEffectBoundaryV2
from neuron.tests.test_effect_proposal_v2 import proposal


class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{"VAMS_ENV":"test"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_legacy_provisioning_cannot_reopen_a_v2_principal(self):
        class Cursor:
            rowcount=1
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def execute(self,sql,args=None):
                self.sql=sql
                if sql.startswith("INSERT"):
                    raise AssertionError("legacy provisioning crossed v2 exclusion")
            def fetchone(self):
                if "to_regclass" in self.sql: return ("vams_effect_v2_authority",)
                if "SELECT 1" in self.sql: return (1,)
                return None
        class Connection:
            def cursor(self): return Cursor()
        @contextmanager
        def connect():
            yield Connection()
        repository=PostgresAuthorityRepository("postgresql://synthetic-unused")
        repository._connection=connect
        capability=AttenuatedCapability("test-principal","task","test-provider",
            "ab"*32,3,1,1,200,"test-principal/object")
        with self.assertRaises(EffectError):
            repository.provision_capability(capability,10)

    def test_existing_coordinator_requires_explicit_v2_composition(self):
        with tempfile.TemporaryDirectory() as temp:
            signer=AuthoritySignerV2("issuer",b"a"*32)
            repository=PostgresAuthorityRepository("postgresql://synthetic-unused")
            authority=repository.versioned_effects(signer,"test-provider",b"o"*32,clock=lambda:100)
            provider=ObjectEffectBoundaryV2(str(Path(temp)/"provider.sqlite"),
                "test-provider",b"d"*32,b"m"*32,signer,b"o"*32,clock=lambda:100)
            ordinary=EffectCoordinator(repository,provider)
            with self.assertRaises(EffectError):
                ordinary.execute_v2(proposal(),b"synthetic-object")
            composed=EffectCoordinator.for_v2(authority,provider)
            with self.assertRaises(EffectError):
                composed.execute(None,b"synthetic-object")

    def test_authority_and_observer_key_reuse_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp,self.assertRaises(ProtocolError):
            ObjectEffectBoundaryV2(str(Path(temp)/"provider.sqlite"),
                "test-provider",b"d"*32,b"m"*32,
                AuthoritySignerV2("issuer",b"a"*32),b"a"*32)


if __name__=="__main__":
    unittest.main()
