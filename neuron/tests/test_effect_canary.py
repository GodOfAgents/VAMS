"""Standard-library integration tests for the separate local effect provider."""
import hashlib
import hmac
import io
import json
import os
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from http.client import HTTPConnection
from urllib.parse import urlsplit
from urllib.request import Request
from urllib.error import HTTPError
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server
from socketserver import ThreadingMixIn

from neuron.effect_canary import (
    ApprovedAction, EffectCoordinator, EffectError, EffectStatus,
    HttpObjectProvider, ResolvedImplementation,
)
from neuron.effect_provider import ObjectProvider


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def _send_loopback(req, timeout):
    parsed=urlsplit(req.full_url)
    if parsed.scheme!="http" or parsed.hostname!="127.0.0.1" or parsed.port is None:
        raise AssertionError("test request must stay on loopback")
    connection=HTTPConnection(parsed.hostname,parsed.port,timeout=timeout)
    try:
        connection.request(req.get_method(),parsed.path or "/",body=req.data,headers=dict(req.header_items()))
        response=connection.getresponse()
        status=response.status
        response.read()
        return status
    finally:
        connection.close()


class ProviderCanaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=str(Path(self.tmp.name)/"provider.sqlite")
        self.writer=b"w"*32
        self.observer=b"o"*32
        self.implementation=hashlib.sha256(b"pinned provider code").hexdigest()
        self.service=ObjectProvider(self.db,self.writer,self.observer,"local-object-v1",self.implementation)
        self.server=make_server("127.0.0.1",0,self.service.app,server_class=ThreadingWSGIServer,handler_class=QuietHandler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.client=HttpObjectProvider(f"http://127.0.0.1:{self.server.server_port}",self.writer,self.observer)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def action(self, *, content=b"synthetic VAMS object", key="principal-a/task-a/object-1", operation=None):
        return ApprovedAction(
            principal_id="principal-a",task_id="task-a",
            operation_id=operation or str(uuid.uuid4()),target="local-object-v1",
            implementation=ResolvedImplementation("local-object-provider","1.0.0",self.implementation),
            object_key=key,content_hash=hashlib.sha256(content).hexdigest(),
            cost_units=1,policy_revision=4,authority_epoch=7,expires_at=int(time.time())+300,
        )

    def test_provider_client_rejects_userinfo_host_confusion(self):
        with self.assertRaises(EffectError):
            HttpObjectProvider("http://127.0.0.1:8765" + "@attacker.example",self.writer,self.observer)

    def test_provider_client_does_not_follow_redirects(self):
        def redirect_app(environ,start_response):
            start_response("302 Found",[("Location","http://127.0.0.1:1/redirected")])
            return [b""]

        server=make_server("127.0.0.1",0,redirect_app,server_class=ThreadingWSGIServer,handler_class=QuietHandler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        client=HttpObjectProvider(f"http://127.0.0.1:{server.server_port}",self.writer,self.observer)
        try:
            with self.assertRaisesRegex(EffectError,r"provider rejected request \(302\)"):
                client.lookup("00000000-0000-0000-0000-000000000000")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_atomic_provider_write_idempotency_and_independent_observation(self):
        action=self.action()
        content=b"synthetic VAMS object"
        first=self.client.put(action,content)
        second=self.client.put(action,content)
        self.assertEqual(first,second)
        self.assertEqual(self.client.lookup(action.operation_id)["action_digest"],action.action_digest)
        observed=self.client.observe(action.operation_id)
        self.assertEqual(observed["object_hash"],action.content_hash)
        self.assertEqual(observed["principal_id"],action.principal_id)

    def test_operation_replay_with_substituted_action_is_rejected(self):
        operation=str(uuid.uuid4())
        original=self.action(operation=operation)
        self.client.put(original,b"synthetic VAMS object")
        changed=self.action(operation=operation,key="principal-a/task-a/other-object")
        with self.assertRaises(EffectError) as raised:
            self.client.put(changed,b"synthetic VAMS object")
        if getattr(raised.exception,"__context__",None) is not None and isinstance(raised.exception.__context__,HTTPError):
            raised.exception.__context__.close()

    def test_object_key_cannot_escape_principal_scope(self):
        action=self.action(key="principal-b/task-a/object-1")
        with self.assertRaises(EffectError) as raised:
            self.client.put(action,b"synthetic VAMS object")
        if getattr(raised.exception,"__context__",None) is not None and isinstance(raised.exception.__context__,HTTPError):
            raised.exception.__context__.close()

    def test_writer_cannot_use_observer_authority_or_replay_nonce(self):
        action=self.action()
        body=json.dumps({
            "operation_id":action.operation_id,"principal_id":action.principal_id,"task_id":action.task_id,
            "target":action.target,"implementation_digest":action.implementation.digest,"object_key":action.object_key,
            "content_hash":action.content_hash,"action_digest":action.action_digest,
            "authority_epoch":action.authority_epoch,"policy_revision":action.policy_revision,
            "expires_at":action.expires_at,"content_hex":b"synthetic VAMS object".hex(),
        },sort_keys=True,separators=(",",":")).encode()
        timestamp=str(int(time.time())); nonce="f"*32; path="/v1/objects"; method="PUT"
        message=b"\n".join((method.encode(),path.encode(),timestamp.encode(),nonce.encode(),hashlib.sha256(body).hexdigest().encode()))
        signature=hmac.new(self.observer,message,hashlib.sha256).hexdigest()
        request=Request(f"http://127.0.0.1:{self.server.server_port}{path}",data=body,method=method,headers={"Content-Type":"application/json","X-VAMS-Time":timestamp,"X-VAMS-Nonce":nonce,"X-VAMS-Signature":signature})
        self.assertEqual(_send_loopback(request,timeout=2),400)

    def test_same_signed_nonce_is_rejected_on_replay(self):
        body=b'{"operation_id":"00000000-0000-0000-0000-000000000000"}'
        timestamp=str(int(time.time())); nonce="a"*32; path="/v1/lookup"; method="POST"
        message=b"\n".join((method.encode(),path.encode(),timestamp.encode(),nonce.encode(),hashlib.sha256(body).hexdigest().encode()))
        signature=hmac.new(self.writer,message,hashlib.sha256).hexdigest()
        def send():
            req=Request(f"http://127.0.0.1:{self.server.server_port}{path}",data=body,method=method,headers={"Content-Type":"application/json","X-VAMS-Time":timestamp,"X-VAMS-Nonce":nonce,"X-VAMS-Signature":signature})
            return _send_loopback(req,timeout=2)
        self.assertEqual(send(),200)
        self.assertEqual(send(),409)

    def test_two_concurrent_retries_commit_one_immutable_object(self):
        from concurrent.futures import ThreadPoolExecutor
        action=self.action()
        content=b"synthetic VAMS object"
        with ThreadPoolExecutor(max_workers=2) as pool:
            receipts=list(pool.map(lambda _:self.client.put(action,content),range(2)))
        self.assertEqual(receipts[0],receipts[1])
        self.assertEqual(self.client.lookup(action.operation_id)["content_hash"],action.content_hash)

    def test_coordinator_reconciles_lost_acknowledgement_by_same_operation_id(self):
        class Repository:
            def __init__(self): self.reserved=0; self.spent=0; self.observations=[]
            def reserve(self,action,now): self.reserved=action.cost_units
            def mark_indeterminate(self,operation): pass
            def commit_if_current(self,action,effect):
                receipt=effect()
                self.spent+=action.cost_units;self.reserved-=action.cost_units
                from neuron.effect_canary import EffectOutcome
                return EffectOutcome(action.operation_id,EffectStatus.COMMITTED,receipt)
            def record_observation(self,receipt): self.observations.append(receipt)
        class LostAckProvider:
            def __init__(self,client): self.client=client;self.contract=client.contract;self.did_lose=False
            def put(self,action,content):
                receipt=self.client.put(action,content)
                if not self.did_lose:
                    self.did_lose=True
                    raise TimeoutError("acknowledgement lost after provider commit")
                return receipt
            def lookup(self,operation): return self.client.lookup(operation)
            def observe(self,operation): return self.client.observe(operation)
        repo=Repository(); action=self.action(); content=b"synthetic VAMS object"
        previous=os.environ.get("VAMS_ENV");os.environ["VAMS_ENV"]="test"
        try:
            outcome=EffectCoordinator(repo,LostAckProvider(self.client)).execute(action,content)
        finally:
            if previous is None: os.environ.pop("VAMS_ENV",None)
            else: os.environ["VAMS_ENV"]=previous
        self.assertEqual(outcome.status,EffectStatus.COMMITTED)
        self.assertEqual(repo.spent,1)
        self.assertEqual(len(repo.observations),1)
        self.assertEqual(self.client.lookup(action.operation_id)["content_hash"],action.content_hash)

    def test_coordinator_rejects_before_reserving_if_observer_is_unavailable(self):
        class Repository:
            def __init__(self): self.reserved=False
            def reserve(self,*args): self.reserved=True
        class UnavailableObserver:
            def __init__(self,client): self.client=client;self.contract=client.contract
            def observe(self,*args): raise EffectError("observer unavailable")
        repo=Repository();previous=os.environ.get("VAMS_ENV");os.environ["VAMS_ENV"]="test"
        try:
            with self.assertRaises(EffectError):
                EffectCoordinator(repo,UnavailableObserver(self.client)).execute(self.action(),b"synthetic VAMS object")
        finally:
            if previous is None: os.environ.pop("VAMS_ENV",None)
            else: os.environ["VAMS_ENV"]=previous
        self.assertFalse(repo.reserved)

    def test_expired_action_is_rejected_at_provider_commit(self):
        action=self.action()
        from dataclasses import replace
        action=replace(action,expires_at=int(time.time())-1)
        with self.assertRaises(EffectError):
            self.client.put(action,b"synthetic VAMS object")
        self.assertIsNone(self.client.lookup(action.operation_id))

    def test_coordinator_fails_closed_outside_explicit_local_mode(self):
        class Repository:
            def reserve(self,*args): raise AssertionError("must reject before reservation")
        previous=os.environ.pop("VAMS_ENV",None)
        try:
            with self.assertRaises(EffectError):
                EffectCoordinator(Repository(),self.client).execute(self.action(),b"synthetic VAMS object")
        finally:
            if previous is not None: os.environ["VAMS_ENV"]=previous


if __name__=="__main__":
    unittest.main()
