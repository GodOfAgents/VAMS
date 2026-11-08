"""Extracted actual handler/NodeInfo and real crypto; no ASGI/M2/TLS claim."""
import ast
from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List
import unittest
from unittest.mock import Mock

from neuron import secp256k1 as S


class FixtureHTTPException(Exception):
    def __init__(self, status_code, detail=None):
        self.status_code, self.detail = status_code, detail
        super().__init__(detail)


class HeartbeatBodyBoundaryTests(unittest.TestCase):
    def setUp(self):
        source = Path(S.__file__).resolve().parents[1] / 'gateway/server.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        model = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'NodeInfo')
        handler = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'receive_heartbeat')
        if any(isinstance(n, (ast.Await, ast.Yield, ast.YieldFrom)) for n in ast.walk(handler)):
            raise AssertionError('Fixture runner cannot exercise an awaited handler')
        handler.decorator_list = []
        self.nodes, self.verify_calls = {}, []
        self.certificate = Mock(return_value='fixture-certificate-accepted')
        def verify(*args):
            self.verify_calls.append(args)
            return S.verify_message(*args)
        namespace = dict(dataclass=dataclass,field=field,asdict=asdict,datetime=datetime,
            Dict=Dict,List=List,time=SimpleNamespace(time=lambda:1000.0),NODE_TIMEOUT=60,
            MAX_NODES=100,nodes=self.nodes,json=json,logger=Mock(),
            HeartbeatRequest=object,Request=object,HTTPException=FixtureHTTPException,
            verify_message=verify,verify_heartbeat_client_certificate=self.certificate)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[model,handler],type_ignores=[])),str(source),'exec'),namespace)  # nosec B102 # test-only exec of AST-extracted repository source
        self.handler,self.node_type = namespace['receive_heartbeat'],namespace['NodeInfo']
    def invoke(self, payload, signature=''):
        text = payload if isinstance(payload,str) else json.dumps(payload,separators=(',',':'))
        coroutine = self.handler(SimpleNamespace(payload=text,signature=signature),object())
        try:
            coroutine.send(None)
        except StopIteration as completed:
            return completed.value
        finally:
            coroutine.close()
        raise AssertionError('Unexpected coroutine suspension')
    def reject(self,payload,signature='',status=403):
        error = None
        try:self.invoke(payload,signature)
        except FixtureHTTPException as exc:error=exc
        self.assertIsNotNone(error,'handler accepted an invalid node body')
        self.assertEqual(error.status_code,status)
        return error
    def signed(self,key,payload):
        text=json.dumps(payload,separators=(',',':'))
        return text,S.sign_message(key,text.encode()).hex()
    def test_first_empty_or_nonstring_key_never_creates_node(self):
        for key in ('',None,False,0,[],{}):
            with self.subTest(key=key):
                self.reject({'node_id':'fixture-node','block_height':99,'public_key':key})
                self.assertEqual(self.nodes,{})
    def test_existing_empty_key_never_updates_counter_block_or_time(self):
        node=self.node_type(node_id='fixture-node',public_key='',last_block=7,last_seen=23,heartbeat_count=5)
        self.nodes[node.node_id]=node
        before=asdict(node)
        self.reject({'node_id':node.node_id,'block_height':99,'public_key':''})
        self.assertEqual(asdict(node),before)
        self.assertIs(self.nodes[node.node_id],node)
    def test_malformed_key_or_signature_is_denied_before_mutation(self):
        key=S.generate_private_key();public=S.public_key_bytes(key).hex()
        for public_key,signature in ((' ',''),('00'*64,''),('not-hex','00'),
                                     (public,''),(public,'not-hex'),(public,'00'*64)):
            with self.subTest(public_key_length=len(public_key),signature_length=len(signature)):
                self.reject({'node_id':'fixture-node','public_key':public_key},signature)
                self.assertEqual(self.nodes,{})
    def test_valid_first_and_cached_key_signatures_preserve_body_bytes(self):
        key=S.generate_private_key();public=S.public_key_bytes(key).hex()
        payload={'node_id':'fixture-node','block_height':7,'public_key':public}
        text,signature=self.signed(key,payload)
        self.assertEqual(self.invoke(text,signature),{'status':'ok','node_id':'fixture-node','heartbeat_count':1})
        self.assertEqual(self.verify_calls[-1],(bytes.fromhex(public),text.encode(),bytes.fromhex(signature)))
        self.assertEqual(self.nodes['fixture-node'].public_key,public)
        second={'node_id':'fixture-node','block_height':8}
        text,signature=self.signed(key,second)
        self.assertEqual(self.invoke(text,signature)['heartbeat_count'],2)
        self.assertEqual(self.nodes['fixture-node'].last_block,8)
        self.assertEqual(len(self.verify_calls),2)
    def test_supplied_key_cannot_replace_cached_key_or_authenticate_wrong_signature(self):
        owner=S.generate_private_key();other=S.generate_private_key()
        node=self.node_type(node_id='fixture-node',public_key=S.public_key_bytes(owner).hex(),heartbeat_count=4)
        self.nodes[node.node_id]=node;before=asdict(node)
        payload={'node_id':node.node_id,'public_key':S.public_key_bytes(other).hex(),'block_height':99}
        text,signature=self.signed(other,payload)
        self.reject(text,signature)
        self.assertEqual(asdict(node),before)
        self.assertEqual(self.verify_calls[-1][0],bytes.fromhex(node.public_key))
    def test_certificate_fixture_denial_precedes_body_verification_and_mutation(self):
        self.certificate.side_effect=FixtureHTTPException(403,'fixture certificate denied')
        self.reject({'node_id':'fixture-node','public_key':''})
        self.assertEqual(self.nodes,{})
        self.assertEqual(self.verify_calls,[])
        self.certificate.assert_called_once()
    def test_missing_first_key_is_denied_without_mutation(self):
        self.reject({'node_id':'fixture-node','block_height':99})
        self.assertEqual(self.nodes,{})
        self.assertEqual(self.verify_calls,[])
    def test_malformed_json_is_denied_without_mutation(self):
        self.reject('{',status=400)
        self.assertEqual(self.nodes,{})
        self.assertEqual(self.verify_calls,[])


if __name__=='__main__':unittest.main()
