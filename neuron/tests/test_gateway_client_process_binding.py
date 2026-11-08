"""Actual legacy client and extracted parent; memory-only transport/key/store."""
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from neuron.gateway import client as G
from neuron import runtime_safety as R
from neuron.tests import test_neuron_lifecycle_boundary as L

BASE='https://synthetic-gateway.invalid'
OPS=('register','deregister','heartbeat','poll','result')


class PrivateDiagnostic(R.RuntimeConfigurationError):
    reads=0
    def __str__(self):
        type(self).reads+=1
        return 'SYNTHETIC_PRIVATE_DIAGNOSTIC'
    def __repr__(self):
        type(self).reads+=1
        return 'SYNTHETIC_PRIVATE_DIAGNOSTIC'


class ProcessBindingTests(unittest.TestCase):
    def setUp(self):
        p=patch.dict(os.environ,{'VAMS_ENV':'test'},clear=True);p.start();self.addCleanup(p.stop)
        self.session=Mock(name='memory-only-session');self.session.headers={}
        self.response=Mock(name='memory-only-response');self.response.status_code=200
        self.response.json.return_value={'agent_id':'fixture-agent','tasks':['fixture-task']}
        self.session.post.return_value=self.response;self.session.get.return_value=self.response
        p=patch.object(G.requests,'Session',return_value=self.session)
        self.factory=p.start();self.addCleanup(p.stop)
        PrivateDiagnostic.reads=0
    def tearDown(self):
        self.assertEqual(PrivateDiagnostic.reads,0,'caught diagnostic was formatted')
    def capture(self,call):
        try:call()
        except BaseException as exc:return exc
        return None
    def denied(self,call):
        error=self.capture(call)
        self.assertIsInstance(error,R.LiveModeSafetyError,'missing policy denial')
        self.assertIn('GatewayClient',str(error))
        self.assertNotIn('SYNTHETIC_PRIVATE',str(error))
        return error
    def invoke(self,client,op):
        if op=='register':return client.register_agent('fixture-node','fixture-public',0.0,{'compute':False})
        if op=='deregister':return client.deregister_agent('fixture-signature')
        if op=='heartbeat':return client.send_heartbeat('fixture-payload','fixture-signature')
        if op=='poll':return client.poll_tasks('fixture-node')
        return client.submit_result('fixture-task',{'output':'fixture'},'fixture-signature')
    def no_transport(self):
        self.session.get.assert_not_called();self.session.post.assert_not_called()
    def test_actual_ambient_cannot_be_replaced_by_caller_context(self):
        source={'VAMS_ENV':'local'};policy=R.load_runtime_policy(source)
        for ambient in ({},{'VAMS_ENV':'production'},{'VAMS_ENV':'staging'},
                        {'VAMS_ENV':'testnet'},{'VAMS_ENV':'unknown'},
                        {'VAMS_ENV':'test','OMS_MOCK_MODE':'true'}):
            for kwargs in ({'environ':source},{'environ':source,'runtime_policy':policy}):
                with self.subTest(ambient=ambient,kwargs=list(kwargs)),patch.dict(os.environ,ambient,clear=True):
                    self.denied(lambda:G.GatewayClient('http://127.0.0.1:8000',**kwargs))
                    self.factory.assert_not_called();self.no_transport()
    def test_all_matching_live_modes_refuse_session_even_with_https(self):
        for mode in ('staging','testnet','production'):
            source={'VAMS_ENV':mode}
            with self.subTest(mode=mode),patch.dict(os.environ,source,clear=True):
                self.denied(lambda:G.GatewayClient(BASE,environ=source,runtime_policy=R.load_runtime_policy(source)))
                self.factory.assert_not_called();self.no_transport()
    def test_malformed_supplied_policy_and_environment_refuse_session(self):
        for kwargs in ({'runtime_policy':{}},{'runtime_policy':object()},
                       {'environ':[]},{'environ':'test'},{'environ':{}},
                       {'environ':{'VAMS_ENV':'test','OMS_MOCK_MODE':'TRUE'}}):
            with self.subTest(kwargs=list(kwargs)):
                self.denied(lambda:G.GatewayClient(BASE,**kwargs))
                self.factory.assert_not_called()
    def test_matching_nonlive_context_and_flags_preserve_session_headers(self):
        for mode in ('test','local','demo'):
            source={'VAMS_ENV':mode,'OMS_MOCK_MODE':'true','ordinary':'fixture'}
            with self.subTest(mode=mode),patch.dict(os.environ,source,clear=True):
                policy=R.load_runtime_policy(source)
                client=G.GatewayClient('  '+BASE+'/  ',environ=source,runtime_policy=policy)
                self.assertEqual(client.base_url,BASE)
                self.assertEqual(client.runtime_policy,policy)
                self.assertEqual(self.session.headers,{'User-Agent':'VAMS-Neuron/1.0','Content-Type':'application/json'})
                self.no_transport()
    def test_constructor_rechecks_after_url_preparation(self):
        class DriftingURL:
            def strip(_self):
                os.environ['VAMS_ENV']='production'
                return BASE
        self.denied(lambda:G.GatewayClient(DriftingURL()))
        self.factory.assert_not_called();self.no_transport()
    def test_policy_parser_exception_is_sanitized_without_stringifying(self):
        with patch.object(G,'load_runtime_policy',side_effect=PrivateDiagnostic()):
            error=self.denied(lambda:G.GatewayClient(BASE))
            self.assertTrue(error.__suppress_context__)
        self.factory.assert_not_called()
    def test_all_operations_reject_drift_before_transport_or_early_return(self):
        for op in OPS:
            for ambient in ({},{'VAMS_ENV':'production'},{'VAMS_ENV':'local'},
                            {'VAMS_ENV':'unknown'},{'VAMS_ENV':'test','OMS_MOCK_MODE':'true'},
                            {'VAMS_ENV':'test','NEURON_MOCK_MODE':'TRUE'}):
                with self.subTest(op=op,ambient=ambient),patch.dict(os.environ,{'VAMS_ENV':'test'},clear=True):
                    client=G.GatewayClient(BASE);client.agent_id='fixture-agent'
                    self.session.get.reset_mock();self.session.post.reset_mock()
                    with patch.dict(os.environ,ambient,clear=True):self.denied(lambda:self.invoke(client,op))
                    self.no_transport()
        client=G.GatewayClient(BASE)
        os.environ['VAMS_ENV']='production'
        self.denied(lambda:client.deregister_agent('fixture-signature'))
        self.no_transport()
    def test_request_argument_preparation_drift_cannot_dispatch(self):
        class DriftingString:
            def __str__(_self):os.environ['VAMS_ENV']='production';return 'fixture'
        class DriftingCapabilities:
            def __bool__(_self):os.environ['OMS_MOCK_MODE']='true';return True
        for op in ('register','deregister','poll','result'):
            with self.subTest(op=op),patch.dict(os.environ,{'VAMS_ENV':'test'},clear=True):
                client=G.GatewayClient(BASE);client.agent_id=DriftingString()
                self.session.get.reset_mock();self.session.post.reset_mock()
                if op=='register':call=lambda:client.register_agent('n','p',0.0,DriftingCapabilities())
                elif op=='deregister':call=lambda:client.deregister_agent('s')
                elif op=='poll':call=lambda:client.poll_tasks(DriftingString())
                else:call=lambda:client.submit_result(DriftingString(),{},'s')
                self.denied(call);self.no_transport()
    def test_transport_callback_drift_cannot_adopt_ack_or_registration_state(self):
        for op in OPS:
            with self.subTest(op=op),patch.dict(os.environ,{'VAMS_ENV':'test'},clear=True):
                client=G.GatewayClient(BASE);client.agent_id='existing';client.registered=True
                def dispatch(*args,**kwargs):os.environ['VAMS_ENV']='production';return self.response
                self.session.post.side_effect=dispatch;self.session.get.side_effect=dispatch
                self.denied(lambda:self.invoke(client,op))
                self.assertEqual(client.agent_id,'existing');self.assertTrue(client.registered)
                self.response.json.assert_not_called()
    def test_json_callback_drift_prevents_state_or_task_adoption(self):
        for op in ('register','poll'):
            with self.subTest(op=op),patch.dict(os.environ,{'VAMS_ENV':'test'},clear=True):
                client=G.GatewayClient(BASE)
                def decode():os.environ['VAMS_ENV']='production';return {'agent_id':'new','tasks':['unadmitted']}
                self.response.json.side_effect=decode
                self.denied(lambda:self.invoke(client,op))
                self.assertIsNone(client.agent_id);self.assertFalse(client.registered)
    def test_private_guard_survives_transport_restoring_environment(self):
        for op in OPS:
            with self.subTest(op=op):
                client=G.GatewayClient(BASE);client.agent_id='fixture-agent'
                def dispatch(*args,**kwargs):
                    os.environ['VAMS_ENV']='production'
                    try:
                        guard=getattr(client,'_require_current_runtime',None)
                        if guard:guard()
                    finally:os.environ['VAMS_ENV']='test'
                    return self.response
                self.session.post.side_effect=dispatch;self.session.get.side_effect=dispatch
                error=self.denied(lambda:self.invoke(client,op))
                self.assertEqual(type(error).__name__,'_GatewayRuntimeDriftError')
    def test_public_callback_diagnostics_remain_ordinary_fixed_failure(self):
        expected=(None,False,False,[],False)
        for op,want in zip(OPS,expected):
            with self.subTest(op=op):
                client=G.GatewayClient(BASE);client.agent_id='fixture-agent'
                self.session.post.side_effect=PrivateDiagnostic();self.session.get.side_effect=PrivateDiagnostic()
                self.assertEqual(self.invoke(client,op),want)
    def test_matching_local_wire_for_every_operation(self):
        expected={
            'register':('post','/agents/register',{'node_id':'fixture-node','public_key':'fixture-public','stake_amount':0.0,'capabilities':{'compute':False},'version':'1.0.0'},10,'fixture-agent'),
            'deregister':('post','/agents/fixture-agent/deregister',{'signature':'fixture-signature'},10,True),
            'heartbeat':('post','/heartbeat',{'payload':'fixture-payload','signature':'fixture-signature'},5,True),
            'poll':('get','/tasks/pending?node_id=fixture-node',None,5,['fixture-task']),
            'result':('post','/tasks/fixture-task/result',{'result':{'output':'fixture'},'signature':'fixture-signature'},10,True)}
        for op,(method,path,body,timeout,want) in expected.items():
            with self.subTest(op=op):
                client=G.GatewayClient(BASE);client.agent_id='fixture-agent'
                self.session.get.reset_mock();self.session.post.reset_mock()
                self.assertEqual(self.invoke(client,op),want)
                kwargs={'timeout':timeout,'allow_redirects':False}
                if body is not None:kwargs['json']=body
                getattr(self.session,method).assert_called_once_with(BASE+path,**kwargs)
                getattr(self.session,'get' if method=='post' else 'post').assert_not_called()
    def test_extracted_parent_to_actual_client_preserves_local_wire(self):
        holder=L.LifecycleBoundaryTests();holder.setUp()
        try:
            with holder.node() as node:
                node.gateway=G.GatewayClient(BASE,runtime_policy=node.runtime_policy,environ=dict(os.environ))
                self.assertTrue(node.send_heartbeat(SimpleNamespace(height=7,provider='celestia',network='fixture')))
                self.session.post.assert_called_once()
                args,kwargs=self.session.post.call_args
                self.assertEqual(args,(BASE+'/heartbeat',))
                self.assertEqual(set(kwargs),{'json','timeout','allow_redirects'})
                self.assertEqual(kwargs['timeout'],5);self.assertFalse(kwargs['allow_redirects'])
                self.assertEqual(kwargs['json']['signature'],'53'*64)
                self.assertIn('"type":"VAMS_HEARTBEAT"',kwargs['json']['payload'])
                self.assertTrue(node.gateway_available)
        finally:holder.tearDown()
    def test_extracted_parent_drift_stops_actual_client_transport(self):
        holder=L.LifecycleBoundaryTests();holder.setUp()
        try:
            with holder.node() as node:
                node.gateway=G.GatewayClient(BASE,runtime_policy=node.runtime_policy,environ=dict(os.environ))
                holder.callbacks['heartbeat-store']=lambda:os.environ.__setitem__('VAMS_ENV','production')
                error=self.capture(lambda:node.send_heartbeat(SimpleNamespace(height=7,provider='celestia',network='fixture')))
                self.assertEqual(type(error).__name__,'_NeuronRuntimeDriftError')
                self.no_transport()
        finally:holder.tearDown()


if __name__=='__main__':unittest.main()
