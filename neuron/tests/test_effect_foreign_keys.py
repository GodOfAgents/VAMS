"""Controlled FK/trigger catalog states, not native SQL or trigger execution."""
import copy
import unittest
from unittest.mock import patch

from neuron.effect_protocol_v3 import EffectV3Error
from neuron.runtime_safety import RuntimeConfigurationError
from neuron.tests import test_effect_unique_keys as fixtures
from neuron.tests.effect_unique_catalog_fixture import foreign_key_catalog_rows,trigger_catalog_rows


class ForeignKeyCatalogConnection(fixtures.CatalogConnection):
    def __init__(self,version,migration,catalog,tables):
        super().__init__(version,migration,catalog)
        self.foreign=foreign_key_catalog_rows(tables)
        self.triggers=trigger_catalog_rows(tables)

    def fetchall(self):
        if "WHERE c.contype='f'" in self.catalog_query:
            return self.foreign
        if 'tr.tgconstraint::bigint' in self.catalog_query:
            return self.triggers
        return super().fetchall()


class ForeignKeyPrerequisiteTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.UniqueKeyPrerequisiteTests('test_valid_catalog_allows_body_and_commit')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)

    def schemas(self):
        for database,connection,tables in self.fixture.schemas():
            yield database,ForeignKeyCatalogConnection(*connection.metadata[:2],connection.catalog,tables)

    def denied(self,database,connection):
        self.fixture.rejected_before_body(database,connection)

    def mutate(self,kind,variants):
        for database,connection in self.schemas():
            original=getattr(connection,kind)
            for index in range(len(original)):
                for field,value in variants:
                    with self.subTest(kind=kind,schema=connection.metadata[0],row=index,field=field,value=value):
                        probe=ForeignKeyCatalogConnection(*connection.metadata[:2],connection.catalog,[])
                        probe.foreign=copy.deepcopy(connection.foreign);probe.triggers=copy.deepcopy(connection.triggers)
                        rows=getattr(probe,kind);row=list(rows[index]);row[field]=value;rows[index]=tuple(row)
                        self.denied(database,probe)

    def test_valid_migration_relationships_and_internal_triggers_allow_body(self):
        for database,connection in self.schemas():
            body=[]
            with patch.object(database,'_connect',return_value=connection):
                with database.transaction():body.append('protected-body-entered')
            self.assertEqual(body,['protected-body-entered'])
            self.assertIn(('commit',),connection.events)

    def test_every_declared_foreign_key_is_required(self):
        for database,connection in self.schemas():
            for index in range(len(connection.foreign)):
                with self.subTest(schema=connection.metadata[0],row=index):
                    probe=ForeignKeyCatalogConnection(*connection.metadata[:2],connection.catalog,[])
                    probe.foreign=connection.foreign[:index]+connection.foreign[index+1:]
                    self.denied(database,probe)

    def test_extra_and_external_incoming_or_outgoing_relationships_reject(self):
        for database,connection in self.schemas():
            row=connection.foreign[0]
            extra=list(row);extra[0]=999
            incoming=list(row);incoming[1]='public.unreviewed_external_child'
            outgoing=list(row);outgoing[3]='public.unreviewed_external_parent'
            variants=(connection.foreign+[tuple(extra)], [tuple(incoming)]+connection.foreign[1:],
                [tuple(outgoing)]+connection.foreign[1:], connection.foreign+[row])
            for index,rows in enumerate(variants):
                with self.subTest(schema=connection.metadata[0],variant=index):
                    probe=ForeignKeyCatalogConnection(*connection.metadata[:2],connection.catalog,[])
                    probe.foreign=rows;self.denied(database,probe)

    def test_fk_actions_match_validation_enforcement_and_replica_mode_reject(self):
        self.mutate('foreign',[(5,False),(6,False),(7,True),(8,True),(12,False),
            (9,'c'),(9,'n'),(9,'d'),(9,'r'),(10,'c'),(10,'n'),(10,'d'),(10,'r'),
            (11,'f'),(11,'p'),(5,1),(6,None),(2,['wrong_column']),(4,['wrong_reference'])])

    def test_trigger_function_event_timing_and_qualifier_mutations_reject(self):
        self.mutate('triggers',[(2,False),(2,1),(3,'D'),(3,'R'),(3,'A'),
            (4,'public.RI_FKey_check_ins'),(4,'pg_catalog.RI_FKey_cascade_del'),
            (5,7),(5,False),(6,True),(7,True),(8,1),(9,False),(10,False),(11,False)])

    def test_missing_duplicate_and_extra_internal_triggers_reject(self):
        for database,connection in self.schemas():
            for index,rows in enumerate((connection.triggers[:-1],connection.triggers+[connection.triggers[0]],
                    [connection.triggers[0]]+connection.triggers[:-1])):
                with self.subTest(schema=connection.metadata[0],variant=index):
                    probe=ForeignKeyCatalogConnection(*connection.metadata[:2],connection.catalog,[])
                    probe.foreign=connection.foreign;probe.triggers=rows;self.denied(database,probe)

    def test_malformed_or_unknown_foreign_catalog_cannot_authorize_body(self):
        for database,connection in self.schemas():
            for index,rows in enumerate((None,[None],connection.foreign[:-1]+[connection.foreign[-1][:-1]])):
                with self.subTest(schema=connection.metadata[0],variant=index):
                    probe=ForeignKeyCatalogConnection(*connection.metadata[:2],connection.catalog,[])
                    probe.foreign=rows;self.denied(database,probe)
        self.mutate('foreign',[(0,True),(0,0),(0,4_294_967_296),(2,None),(4,'scope_id')])

    def test_unknown_or_rebound_trigger_constraint_cannot_authorize_body(self):
        self.mutate('triggers',[(1,True),(1,0),(1,999),(0,'public.unreviewed_table')])
        for database,connection in self.schemas():
            for index,rows in enumerate((None,[None],connection.triggers[:-1]+[connection.triggers[-1][:-1]])):
                with self.subTest(schema=connection.metadata[0],variant=index):
                    probe=ForeignKeyCatalogConnection(*connection.metadata[:2],connection.catalog,[])
                    probe.foreign=connection.foreign;probe.triggers=rows;self.denied(database,probe)

    def test_duplicate_constraint_oid_cannot_alias_distinct_relationships(self):
        for database,connection in self.schemas():
            if len(connection.foreign)<2:continue
            row=list(connection.foreign[-1]);row[0]=connection.foreign[0][0]
            connection.foreign[-1]=tuple(row);self.denied(database,connection)

    def test_foreign_key_contract_cannot_be_rebound(self):
        for database,_ in self.schemas():
            with self.subTest(database=type(database).__name__),self.assertRaises(RuntimeConfigurationError):
                database._foreign_keys=()


if __name__=='__main__':unittest.main()
