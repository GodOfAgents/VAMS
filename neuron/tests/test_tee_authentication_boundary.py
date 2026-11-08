"""Legacy TEE containment with local transport/vendor fixtures, never authentic quotes."""
import hashlib
import io
import json
import os
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from neuron.runtime_safety import LiveModeSafetyError, RuntimeConfigurationError, RuntimePolicy
from neuron.sdk import phala_tee as P
from neuron.sdk import trust_aggregator as A
from neuron.trust_plugins import tee_plugin as T

LIVE = ('staging', 'testnet', 'production')
LOCAL = ('test', 'local', 'demo')
ROOT = b'\x33' * 20
SERVICE = b'\x11' * 32
DELIVERY = b'\x22' * 32


def environment(mode='test', mock=False):
    return {'VAMS_ENV': mode, 'PHALA_MOCK_MODE': 'true' if mock else 'false',
        'PHALA_RPC_URL': 'https://provider.invalid', 'VAMS_PHAT_PYTHON_RUNTIME': 'synthetic-runtime',
        'PHALA_API_KEY': 'synthetic-fixture-only'}


def matching_claim():
    return {'valid': True, 'mrenclave': '11'*32, 'mrsigner': '22'*32,
        'attested_root_eoa': '0x'+ROOT.hex(),
        'report_data': hashlib.sha3_256(SERVICE+DELIVERY+ROOT).hexdigest()}


class _FixtureRaw:
    """Local JSON-byte fixture; not an HTTP/urllib3 implementation."""
    def __init__(self, response):
        self.response = response
        self.data = None
        self.offset = 0
        self.requests = []

    def read(self, amount, *, decode_content=False):
        self.requests.append((amount, decode_content))
        if type(amount) is not int or amount <= 0 or decode_content is not False:
            raise AssertionError("Expected a bounded undecoded byte read")
        if self.data is None:
            if self.response.callback: self.response.callback()
            payload = self.response.payload
            if isinstance(payload, Exception): raise payload
            self.data = json.dumps(payload).encode("utf-8")
        chunk = self.data[self.offset:self.offset + amount]
        self.offset += len(chunk)
        return chunk


class Response:
    def __init__(self, payload, status=200, callback=None):
        self.payload=payload; self.status_code=status; self.callback=callback
        self.headers={}; self.raw=_FixtureRaw(self); self.close_calls=0
    def close(self):
        self.close_calls+=1
    def json(self):
        if self.callback: self.callback()
        if isinstance(self.payload, Exception): raise self.payload
        return self.payload


class Transport:
    def __init__(self, response=None, callback=None):
        self.headers={}; self.calls=[]; self.response=response or Response({'output':'fixture','gas_used':1}); self.callback=callback
    def post(self, url, **kwargs):
        self.calls.append(('post',url,kwargs))
        if self.callback: self.callback()
        return self.response
    def get(self, url, **kwargs):
        self.calls.append(('get',url,kwargs))
        if self.callback: self.callback()
        return self.response


class ObservedArguments(list):
    def __init__(self, callback=None): super().__init__(['synthetic-value']); self.reads=0; self.callback=callback
    def __bool__(self):
        self.reads+=1
        if self.callback: self.callback()
        return True


class Unreadable:
    def __init__(self): self.reads=[]
    def __len__(self): self.reads.append('len'); raise AssertionError('input must remain unread')
    def __bool__(self): self.reads.append('bool'); raise AssertionError('input must remain unread')
    def items(self): self.reads.append('items'); raise AssertionError('input must remain unread')


class ClaimedClient:
    def __init__(self): self.calls=0
    def verify_sgx_quote(self, quote):
        self.calls+=1
        claim=matching_claim()
        return SimpleNamespace(usable_as_live_evidence=True, evidence_classification='live-provider',
            attested_root_eoa=claim['attested_root_eoa'], report_data=claim['report_data'],
            mrenclave=claim['mrenclave'], mrsigner=claim['mrsigner'])


class TeeAuthenticationBoundaryTests(unittest.TestCase):
    def test_live_direct_contract_call_rejects_before_arguments_or_transport(self):
        for mode in LIVE:
            with self.subTest(mode=mode), patch.dict(os.environ, environment(mode), clear=True):
                transport=Transport(); client=P.PhalaTEE(transport=transport); args=ObservedArguments()
                with self.assertRaises(LiveModeSafetyError): client.call_phat_contract('synthetic-contract','method',args)
                self.assertEqual(args.reads,0); self.assertEqual(transport.calls,[])

    def test_live_script_call_rejects_even_with_runtime_key_and_correct_configuration(self):
        for mode in LIVE:
            with self.subTest(mode=mode), patch.dict(os.environ, environment(mode), clear=True):
                transport=Transport(); client=P.PhalaTEE(transport=transport); context=ObservedArguments()
                with patch.object(P.json,'dumps',wraps=P.json.dumps) as serialization:
                    with self.assertRaises(LiveModeSafetyError): client.execute_python_in_enclave('synthetic-script',context)
                    serialization.assert_not_called()
                self.assertEqual(context.reads,0); self.assertEqual(transport.calls,[])

    def test_process_live_cannot_be_overridden_by_supplied_local_environment(self):
        for cls in (P.PhalaTEE,T.TEEProofPlugin):
            with self.subTest(cls=cls),patch.dict(os.environ,environment('production'),clear=True):
                with self.assertRaises(LiveModeSafetyError): cls(environ=environment('test',True),mock_mode=True)

    def test_missing_or_invalid_process_mode_cannot_be_supplied_by_a_mapping(self):
        for ambient in ({},{'VAMS_ENV':'prod'}):
            for cls in (P.PhalaTEE,T.TEEProofPlugin):
                with self.subTest(ambient=ambient,cls=cls),patch.dict(os.environ,ambient,clear=True):
                    with self.assertRaises(RuntimeConfigurationError): cls(environ=environment('test',True),mock_mode=True)

    def test_effective_runtime_and_mock_configuration_cannot_be_reassigned(self):
        with patch.dict(os.environ,environment(),clear=True):
            for client in (P.PhalaTEE(transport=Transport()),T.TEEProofPlugin(phala_client=ClaimedClient())):
                with self.subTest(client=type(client)):
                    with self.assertRaises(LiveModeSafetyError): client.mock_mode=True
                    with self.assertRaises(LiveModeSafetyError): client.runtime_policy=RuntimePolicy.from_environment({'VAMS_ENV':'demo'})

    def test_explicit_mock_argument_cannot_replace_the_ambient_selection(self):
        for ambient in ({'VAMS_ENV':'test'}, environment('test',False)):
            for cls in (P.PhalaTEE,T.TEEProofPlugin):
                with self.subTest(ambient=ambient,cls=cls),patch.dict(os.environ,ambient,clear=True):
                    with self.assertRaises(RuntimeConfigurationError): cls(mock_mode=True)

    def test_mapping_without_security_fields_cannot_supply_authorization_defaults(self):
        for cls in (P.PhalaTEE,T.TEEProofPlugin):
            with self.subTest(cls=cls),patch.dict(os.environ,environment('test',True),clear=True):
                with self.assertRaises(RuntimeConfigurationError): cls(environ={'PHALA_RPC_URL':'https://provider.invalid'})

    def test_ambient_drift_stops_direct_and_mock_producers_before_input(self):
        for mode in ('testnet','local','invalid'):
            with self.subTest(mode=mode),patch.dict(os.environ,environment('test',True),clear=True):
                transport=Transport(); client=P.PhalaTEE(transport=transport); plugin=T.TEEProofPlugin(phala_client=client)
                os.environ['VAMS_ENV']=mode
                for operation in (lambda:client.execute_python_in_enclave(Unreadable()),
                        lambda:client.call_phat_contract('fixture','fixture',Unreadable()),
                        lambda:plugin.generate_proof(SERVICE,DELIVERY,root_address=ROOT)):
                    with self.assertRaises(LiveModeSafetyError): operation()
                self.assertEqual(transport.calls,[])

    def test_matching_sgx_provider_json_cannot_become_valid_live_evidence(self):
        for mode in LIVE+LOCAL:
            with self.subTest(mode=mode),patch.dict(os.environ,environment(mode),clear=True):
                transport=Transport(Response(matching_claim())); report=P.PhalaTEE(transport=transport).verify_sgx_quote(b'synthetic-quote')
                self.assertIs(report.is_valid,False); self.assertIs(report.usable_as_live_evidence,False)
                self.assertEqual(report.evidence_classification,'non-authoritative')
                self.assertIs(getattr(report,'provider_claim_valid',None),True)
                self.assertIs(report.to_dict().get('provider_claim_valid'),True)
                self.assertEqual(len(transport.calls),1)

    def test_matching_nitro_provider_json_is_only_a_claim(self):
        with patch.dict(os.environ,environment('testnet'),clear=True):
            transport=Transport(Response({'valid':True,'pcrs':{'0':'synthetic-pcr'}}))
            report=P.PhalaTEE(transport=transport).verify_nitro_quote(b'synthetic-nitro')
            self.assertIs(report.is_valid,False); self.assertIs(report.usable_as_live_evidence,False)
            self.assertIs(getattr(report,'provider_claim_valid',None),True)

    def test_caller_constructed_valid_report_flags_never_create_live_usability(self):
        report=P.AttestationReport(P.TEEProvider.PHALA,True,'1'*64,
            simulated=False,runtime_classification='live',evidence_classification='live-provider')
        self.assertIs(report.usable_as_live_evidence,False)

    def test_false_malformed_and_provider_errors_are_not_promoted(self):
        for payload, status, expected_claim in (({'valid':False},200,False),({'valid':'true'},200,None),
                ({'valid':True},200,None),({},503,None),(ValueError('synthetic-provider-detail'),200,None)):
            with self.subTest(payload=type(payload),status=status),patch.dict(os.environ,environment('testnet'),clear=True):
                transport=Transport(Response(payload,status)); report=P.PhalaTEE(transport=transport).verify_sgx_quote(b'synthetic-quote')
                self.assertFalse(report.is_valid); self.assertFalse(report.simulated); self.assertFalse(report.usable_as_live_evidence)
                self.assertIs(getattr(report,'provider_claim_valid',None),expected_claim)
                self.assertNotIn('synthetic-provider-detail',report.error or '')

    def test_plugin_and_aggregator_do_not_accept_matching_rpc_claim_as_proof(self):
        with patch.dict(os.environ,environment('testnet'),clear=True):
            transport=Transport(Response(matching_claim())); sdk=P.PhalaTEE(transport=transport)
            plugin=T.TEEProofPlugin(phala_client=sdk)
            result=plugin.generate_proof(SERVICE,DELIVERY,root_address=ROOT,sgx_quote=b'synthetic-quote')
            self.assertFalse(result.valid); self.assertEqual(result.proof_data,b'')
            self.assertEqual(result.metadata.get('reason'),'authentic_verifier_unavailable')
            collector=A.TrustAggregatorClient.__new__(A.TrustAggregatorClient);collector.plugins={plugin.PROOF_TYPE_ID:plugin}
            with redirect_stdout(io.StringIO()):
                self.assertEqual(collector.collect_plugin_proofs(SERVICE,DELIVERY,root_address=ROOT,sgx_quote=b'synthetic-quote'),{})
            self.assertEqual(transport.calls,[])

    def test_injected_client_with_fabricated_usable_flag_is_not_authority(self):
        with patch.dict(os.environ,environment('testnet'),clear=True):
            claimed=ClaimedClient(); plugin=T.TEEProofPlugin(phala_client=claimed)
            result=plugin.generate_proof(SERVICE,DELIVERY,root_address=ROOT,sgx_quote=b'synthetic-quote')
            self.assertFalse(result.valid); self.assertEqual(result.proof_data,b''); self.assertEqual(claimed.calls,0)

    def test_real_plugin_rejects_before_proof_length_decode_or_provider_callbacks(self):
        with patch.dict(os.environ,environment('testnet'),clear=True):
            claimed=ClaimedClient(); plugin=T.TEEProofPlugin(phala_client=claimed); proof=Unreadable()
            with patch('eth_abi.decode') as decoding, patch.object(T,'decode',decoding,create=True):
                self.assertIs(plugin.verify_proof(SERVICE,DELIVERY,proof),False)
                decoding.assert_not_called()
            self.assertEqual(proof.reads,[]);self.assertEqual(claimed.calls,0)

    def test_real_multi_tee_claims_do_not_meet_the_quorum(self):
        with patch.dict(os.environ,environment('testnet'),clear=True):
            client=P.PhalaTEE(transport=Transport(Response(matching_claim())))
            valid,reports=client.verify_multi_tee({P.TEEProvider.PHALA:b'sgx',P.TEEProvider.MARLIN:b'nitro'},required=2)
            self.assertIs(valid,False);self.assertTrue(all(not r.is_valid for r in reports))

    def test_critical_quorum_cannot_be_lowered_or_replaced_with_non_integer(self):
        for quorum in (0,1,-1,3,4,True,False,2.0,'2',None):
            with self.subTest(quorum=quorum),patch.dict(os.environ,environment(),clear=True):
                transport=Transport(); client=P.PhalaTEE(transport=transport); quotes=Unreadable()
                with self.assertRaises(ValueError): client.verify_multi_tee(quotes,required=quorum)
                self.assertEqual(quotes.reads,[]);self.assertEqual(transport.calls,[])

    def test_local_script_simulation_remains_explicit_and_never_uses_transport(self):
        for mode in LOCAL:
            with self.subTest(mode=mode),patch.dict(os.environ,environment(mode,True),clear=True):
                transport=Transport(); client=P.PhalaTEE(transport=transport)
                result=client.execute_python_in_enclave('synthetic-script')
                self.assertTrue(result.success);self.assertTrue(result.simulated)
                self.assertEqual(result.evidence_classification,'non-authoritative');self.assertEqual(transport.calls,[])
                report=client.verify_sgx_quote(b'synthetic-quote')
                self.assertTrue(report.is_valid);self.assertTrue(report.simulated);self.assertFalse(report.usable_as_live_evidence)

    def test_mock_direct_contract_call_cannot_accidentally_perform_http(self):
        with patch.dict(os.environ,environment('test',True),clear=True):
            transport=Transport(); client=P.PhalaTEE(transport=transport)
            with self.assertRaises(LiveModeSafetyError): client.call_phat_contract('fixture','method',ObservedArguments())
            self.assertEqual(transport.calls,[])

    def test_local_real_transport_compatibility_is_only_non_authoritative(self):
        with patch.dict(os.environ,environment(),clear=True):
            transport=Transport(); client=P.PhalaTEE(transport=transport)
            result=client.execute_python_in_enclave('synthetic-script',{'value':'synthetic'})
            self.assertTrue(result.success);self.assertEqual(result.evidence_classification,'non-authoritative')
            self.assertEqual(len(transport.calls),1)

    def test_configuration_change_after_transport_prevents_success_adoption_not_the_prior_effect(self):
        with patch.dict(os.environ,environment(),clear=True):
            transport=Transport(callback=lambda:os.environ.update(VAMS_ENV='production')); client=P.PhalaTEE(transport=transport)
            with self.assertRaises(LiveModeSafetyError): client.call_phat_contract('fixture','method',[])
            self.assertEqual(len(transport.calls),1)

    def test_argument_callback_drift_prevents_the_next_transport_stage(self):
        with patch.dict(os.environ,environment(),clear=True):
            transport=Transport(); client=P.PhalaTEE(transport=transport)
            args=ObservedArguments(lambda:os.environ.update(VAMS_ENV='production'))
            with self.assertRaises(LiveModeSafetyError): client.call_phat_contract('fixture','method',args)
            self.assertEqual(args.reads,1);self.assertEqual(transport.calls,[])

    def test_local_mock_plugin_preserves_root_checks_and_fixture_classification(self):
        with patch.dict(os.environ,environment('test',True),clear=True):
            plugin=T.TEEProofPlugin(mock_mode=True,phala_client=ClaimedClient())
            result=plugin.generate_proof(SERVICE,DELIVERY,root_address=ROOT)
            self.assertTrue(result.valid);self.assertTrue(result.metadata['simulated'])
            self.assertEqual(result.metadata['root_binding'],'simulated')
            self.assertEqual(result.metadata['evidence_classification'],'non-authoritative')
            self.assertIs(plugin.verify_proof(SERVICE,DELIVERY,result.proof_data),True)
            with self.assertRaises(ValueError):plugin.generate_proof(SERVICE,DELIVERY,root_address=b'\0'*20)
            with self.assertRaises(ValueError):plugin.generate_proof(SERVICE,DELIVERY,root_address=ROOT,session_key_address=ROOT)


if __name__=='__main__':unittest.main()
