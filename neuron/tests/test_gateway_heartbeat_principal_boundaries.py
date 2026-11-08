"""Independent format reference and extracted existing M2 parser parity."""
import ast
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import tracemalloc
import unittest

from gateway import heartbeat_principal_v1 as P
from neuron.tests import test_gateway_heartbeat_principal_v1 as H


class PrincipalBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source=Path(P.__file__).with_name('request_auth.py')
        tree=ast.parse(source.read_text(encoding='utf-8'))
        selected=[]
        for node in tree.body:
            if isinstance(node,ast.ClassDef) and node.name=='GatewayAuthenticationError':selected.append(node)
            if isinstance(node,ast.FunctionDef) and node.name in ('_validate_audience','_public_key_from_did'):selected.append(node)
            if isinstance(node,ast.Assign) and any(isinstance(n,ast.Name) and n.id in ('_AUDIENCE_RE','_LOWER_HEX_128_RE') for n in node.targets):selected.append(node)
        if len(selected)!=5:raise AssertionError('Existing M2 parser shape changed')
        cls.namespace={'re':re}
        exec(compile(ast.fix_missing_locations(ast.Module(body=selected,type_ignores=[])),str(source),'exec'),cls.namespace)
    def test_independently_frozen_reference_bytes_and_digest(self):
        reference=Path(__file__).with_name('fixtures')/'heartbeat-principal-v1-expected.json'
        v=json.loads(reference.read_text(encoding='utf-8'))
        self.assertEqual(hashlib.sha256(H.FIXTURE.read_bytes()).hexdigest(),v['fixture_sha256'])
        principal=H._principal_from_fixture()
        raw=bytes.fromhex(v['canonical_hex'])
        self.assertEqual(principal.canonical_bytes(),raw)
        self.assertEqual(len(raw),v['encoded_length'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(),v['sha256'])
        self.assertEqual(principal.digest.hex(),v['sha256'])
        self.assertEqual(P.HeartbeatPrincipalV1.from_bytes(raw),principal)
    def test_ordinary_serialized_did_acceptance_matches_actual_existing_M2_parser(self):
        principal=H._principal_from_fixture()
        cases=['did:key:'+'11'*64,'did:key:'+'00'*64,'did:key:'+'ff'*64,
            'did:key:'+'AA'*64,'did:key:'+'11'*63,'did:key:'+'11'*65,
            'DID:key:'+'11'*64,'did:key:'+'11'*64+'\n','',None,True,7,
            'did:key:'+'１'*128,'did:key: '+'11'*64]
        for value in cases:
            with self.subTest(value_type=type(value).__name__):
                root_error=None;key=principal.m2_signer_public_key
                try:key=self.namespace['_public_key_from_did'](value)
                except self.namespace['GatewayAuthenticationError'] as exc:root_error=exc
                try:
                    result=replace(principal,m2_signer_did=value,m2_signer_public_key=key)
                except P.HeartbeatPrincipalDataError:
                    self.assertIsNotNone(root_error)
                else:
                    self.assertIsNone(root_error)
                    self.assertEqual(result.m2_signer_public_key,key)
    def test_ordinary_serialized_audience_acceptance_matches_actual_existing_M2_parser(self):
        principal=H._principal_from_fixture()
        for value in ('a','gateway.testnet','a'*128,'a'*129,'','UPPER','_a','.a','a.',
                      '-a','a-','a\n','a b','ä',None,False,1):
            with self.subTest(value_type=type(value).__name__):
                root_error=None
                try:self.namespace['_validate_audience'](value)
                except self.namespace['GatewayAuthenticationError'] as exc:root_error=exc
                try:replace(principal,audience=value)
                except P.HeartbeatPrincipalDataError:self.assertIsNotNone(root_error)
                else:self.assertIsNone(root_error)
    def test_rejected_oversized_identity_text_has_bounded_temporary_allocation(self):
        principal=H._principal_from_fixture()
        # Allocate the caller's input before observation. Only the parser's
        # additional allocation is measured, with a broad 64KiB ceiling.
        huge_node='x'*1_000_000
        huge_did='did:key:'+'1'*1_000_000
        calls={
            'node-id':lambda:P.node_id_commitment(huge_node,host_domain=principal.host_domain,service_domain=principal.service_domain),
            'did':lambda:replace(principal,m2_signer_did=huge_did),
        }
        for label,call in calls.items():
            with self.subTest(field=label):
                tracemalloc.start()
                try:
                    with self.assertRaises(P.HeartbeatPrincipalDataError):call()
                    _,peak=tracemalloc.get_traced_memory()
                finally:tracemalloc.stop()
                self.assertLess(peak,65_536,'oversized input was copied before rejection')


if __name__=='__main__':unittest.main()
