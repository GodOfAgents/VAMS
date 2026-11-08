"""Mock research and unbound submission boundaries; no authentic proof claims."""
import io
import json
import os
import time
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from neuron.runtime_safety import LiveModeSafetyError, RuntimeConfigurationError
from neuron.sdk import parallel_web as P
from neuron.sdk import trust_aggregator as A

LIVE = ('staging', 'testnet', 'production')
LOCAL = ('test', 'local', 'demo')
QUERY = 'LOCAL_SYNTHETIC_QUERY_NOT_A_REAL_REQUEST'


class ObservedResults:
    def __init__(self):self.reads=[]
    def __len__(self):self.reads.append('len');return 0
    def __iter__(self):self.reads.append('iter');return iter(())


class UnsupportedBundle:
    def __init__(self):self.reads=[]
    def __len__(self):self.reads.append('len');raise AssertionError('bundle length must not be read')
    def __iter__(self):self.reads.append('iter');raise AssertionError('bundle must not be iterated')
    def __contains__(self,key):self.reads.append('contains');raise AssertionError('bundle must not be inspected')
    def get(self,*args):self.reads.append('get');raise AssertionError('bundle must not be inspected')


class StubParallel:
    def __init__(self):self.calls=[]
    def search(self,query):self.calls.append('search');return []
    def generate_proof_of_research(self,results):self.calls.append('serialize');return b'local-fixture'


class ResearchProofBoundariesTest(unittest.TestCase):
    def test_live_search_rejects_before_output_delay_or_fixture_creation(self):
        for mode in LIVE:
            with self.subTest(mode=mode),patch.dict(os.environ,{'VAMS_ENV':mode},clear=True),\
                    patch.object(P.time,'sleep') as delay,redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(LiveModeSafetyError):P.ParallelWebClient().search(QUERY)
                delay.assert_not_called();self.assertEqual(output.getvalue(),'')

    def test_live_proof_generation_rejects_before_input_inspection_or_serialization(self):
        for mode in LIVE:
            results=ObservedResults()
            with self.subTest(mode=mode),patch.dict(os.environ,{'VAMS_ENV':mode},clear=True),\
                    patch.object(P.json,'dumps',wraps=json.dumps) as serialize,redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(LiveModeSafetyError):P.ParallelWebClient().generate_proof_of_research(results)
                self.assertEqual(results.reads,[]);serialize.assert_not_called();self.assertEqual(output.getvalue(),'')

    def test_legacy_collection_rejects_live_before_any_provider_callback(self):
        for mode in LIVE:
            client=A.TrustAggregatorClient.__new__(A.TrustAggregatorClient);client.parallel=StubParallel()
            with self.subTest(mode=mode),patch.dict(os.environ,{'VAMS_ENV':mode},clear=True),redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(LiveModeSafetyError):client.collect_available_proofs()
                self.assertEqual(client.parallel.calls,[]);self.assertEqual(output.getvalue(),'')

    def test_missing_or_unknown_runtime_rejects_mock_operations(self):
        for environment in ({},{'VAMS_ENV':'prod'},{'VAMS_ENV':'TEST'}):
            for operation in ('search','research','legacy'):
                client=A.TrustAggregatorClient.__new__(A.TrustAggregatorClient);client.parallel=StubParallel()
                with self.subTest(environment=environment,operation=operation),patch.dict(os.environ,environment,clear=True),\
                        patch.object(P.time,'sleep'),redirect_stdout(io.StringIO()):
                    with self.assertRaises(RuntimeConfigurationError):
                        if operation=='search':P.ParallelWebClient().search(QUERY)
                        elif operation=='research':P.ParallelWebClient().generate_proof_of_research([])
                        else:client.collect_available_proofs()
                    self.assertEqual(client.parallel.calls,[])

    def test_local_search_and_bytes_are_explicitly_non_authoritative(self):
        for mode in LOCAL:
            with self.subTest(mode=mode),patch.dict(os.environ,{'VAMS_ENV':mode},clear=True),\
                    patch.object(P.time,'sleep'),patch.object(P.time,'time',return_value=1234.0),\
                    redirect_stdout(io.StringIO()) as output:
                client=P.ParallelWebClient();results=client.search(QUERY)
                self.assertEqual(len(results),1);result=results[0]
                self.assertIs(getattr(result,'simulated',None),True)
                self.assertEqual(getattr(result,'evidence_classification',None),'non-authoritative')
                self.assertTrue('Fixture' in result.title or 'Simulated' in result.title)
                self.assertNotIn('Verified information',result.content_snippet)
                self.assertEqual(result.confidence_score,0.98)  # retained fixture score, not assurance
                self.assertEqual(getattr(result,'confidence_classification',None),'fixture-only')
                payload=json.loads(client.generate_proof_of_research(results))
                self.assertEqual(payload.get('schema'),'vams.parallel-research-simulation.v1')
                self.assertIs(payload.get('simulated'),True);self.assertEqual(payload.get('evidence_classification'),'non-authoritative')
                self.assertEqual(payload.get('confidence_classification'),'fixture-only')
                self.assertEqual(payload['result_count'],1);self.assertEqual(payload['created_at'],1234.0)
                self.assertNotIn(QUERY,output.getvalue())

    def test_local_legacy_fixture_collection_remains_available(self):
        for mode in LOCAL:
            client=A.TrustAggregatorClient.__new__(A.TrustAggregatorClient);client.parallel=P.ParallelWebClient()
            with self.subTest(mode=mode),patch.dict(os.environ,{'VAMS_ENV':mode},clear=True),patch.object(P.time,'sleep'),redirect_stdout(io.StringIO()):
                results=client.collect_available_proofs()
                self.assertEqual(set(results),{A.VAMSProofType.PARALLEL_RESEARCH,A.VAMSProofType.PHALA_EXECUTION,A.VAMSProofType.ERC8004_IDENTITY})
                self.assertIs(json.loads(results[A.VAMSProofType.PARALLEL_RESEARCH]).get('simulated'),True)

    def test_new_plugin_collection_is_preserved_independently_of_legacy_guard(self):
        for mode in LOCAL+LIVE:
            calls=[];key=b'P'*32
            result=A.ProofResult(valid=True,proof_type=key,proof_data=b'fixture-proof',trust_weight=1,metadata={'evidence_classification':'non-authoritative'})
            def generate(**kwargs):calls.append(kwargs);return result
            plugin=SimpleNamespace(name=lambda:'local-fixture',generate_proof=generate)
            client=A.TrustAggregatorClient.__new__(A.TrustAggregatorClient);client.plugins={key:plugin}
            with self.subTest(mode=mode),patch.dict(os.environ,{'VAMS_ENV':mode},clear=True),redirect_stdout(io.StringIO()):
                collected=client.collect_plugin_proofs(b's'*32,b'd'*32)
                self.assertEqual(collected,{key:result});self.assertEqual(len(calls),1)
                self.assertEqual(calls[0],{'service_hash':b's'*32,'delivery_hash':b'd'*32})

    def test_unbound_legacy_submission_never_reports_success_in_any_mode(self):
        for mode in LOCAL+LIVE:
            client=A.TrustAggregatorClient.__new__(A.TrustAggregatorClient);bundle=UnsupportedBundle()
            with self.subTest(mode=mode),patch.dict(os.environ,{'VAMS_ENV':mode},clear=True),\
                    patch.object(time,'sleep') as delay,redirect_stdout(io.StringIO()) as output:
                with self.assertRaisesRegex(LiveModeSafetyError,'unavailable'):client.submit_bundle(bundle)
                self.assertEqual(bundle.reads,[]);delay.assert_not_called();self.assertEqual(output.getvalue(),'')

    def test_unbound_plugin_submission_rejects_supported_data_before_signer_rpc_or_receipt(self):
        for mode in LOCAL+LIVE:
            for bundle in ({},{b'P'*32:A.ProofResult(valid=True,proof_type=b'P'*32,proof_data=b'fixture',trust_weight=1,metadata={})},
                    {A.TEEProofPlugin.PROOF_TYPE_ID:A.ProofResult(valid=True,proof_type=A.TEEProofPlugin.PROOF_TYPE_ID,proof_data=b'fixture',trust_weight=1,metadata={'evidence_classification':'live-provider'})}):
                # No signer/RPC/plugin attributes are installed. A submission
                # must reject without attempting to read or construct them.
                client=A.TrustAggregatorClient.__new__(A.TrustAggregatorClient)
                with self.subTest(mode=mode,keys=tuple(bundle)),patch.dict(os.environ,{'VAMS_ENV':mode},clear=True),\
                        patch.object(time,'sleep') as delay,redirect_stdout(io.StringIO()) as output:
                    with self.assertRaisesRegex(LiveModeSafetyError,'unavailable'):client.submit_plugin_bundle(bundle)
                    delay.assert_not_called();self.assertEqual(output.getvalue(),'')

    def test_unbound_plugin_submission_rejects_unsupported_mapping_without_callbacks(self):
        client=A.TrustAggregatorClient.__new__(A.TrustAggregatorClient);bundle=UnsupportedBundle()
        with patch.dict(os.environ,{'VAMS_ENV':'test'},clear=True),redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(LiveModeSafetyError,'unavailable'):client.submit_plugin_bundle(bundle)
            self.assertEqual(bundle.reads,[]);self.assertEqual(output.getvalue(),'')

    def test_existing_zkml_and_non_authoritative_tee_denials_remain(self):
        client=A.TrustAggregatorClient.__new__(A.TrustAggregatorClient)
        cases=((A.ZKMLProofPlugin.PROOF_TYPE_ID,{'evidence_classification':'live-provider'},'ZKML'),
               (A.TEEProofPlugin.PROOF_TYPE_ID,{'evidence_classification':'non-authoritative'},'non-authoritative TEE'))
        with patch.dict(os.environ,{'VAMS_ENV':'test'},clear=True),redirect_stdout(io.StringIO()):
            for key,metadata,reason in cases:
                result=A.ProofResult(valid=True,proof_type=key,proof_data=b'fixture',trust_weight=1,metadata=metadata)
                with self.subTest(reason=reason),self.assertRaisesRegex(LiveModeSafetyError,reason):client.submit_plugin_bundle({key:result})

    def test_local_client_cannot_emit_mock_after_environment_changes_to_live(self):
        with patch.dict(os.environ,{'VAMS_ENV':'local'},clear=True):client=P.ParallelWebClient()
        with patch.dict(os.environ,{'VAMS_ENV':'testnet'},clear=True),patch.object(P.time,'sleep'),redirect_stdout(io.StringIO()):
            with self.assertRaises(LiveModeSafetyError):client.search(QUERY)
            with self.assertRaises(LiveModeSafetyError):client.generate_proof_of_research([])

    def test_collection_constructor_does_not_read_ambient_signing_material(self):
        class ReadOnlyWeb3Fixture:
            @staticmethod
            def HTTPProvider(url):return ('unconnected-provider-fixture',url)
            def __init__(self,provider):self.provider=provider
        for mode in LOCAL+LIVE:
            with self.subTest(mode=mode),patch.dict(os.environ,{'VAMS_ENV':mode,'VAMS_PRIVATE_KEY':'SYNTHETIC_VALUE_MUST_NOT_BE_READ'},clear=True),\
                    patch.object(os,'getenv',side_effect=AssertionError('ambient key read forbidden')) as ambient,\
                    patch.object(A,'Web3',ReadOnlyWeb3Fixture),patch.object(A,'PhalaTEE',return_value=object()),\
                    patch.object(A,'discover_plugins',return_value=[]),redirect_stdout(io.StringIO()):
                client=A.TrustAggregatorClient('https://example.invalid','fixture-contract')
                ambient.assert_not_called()
                self.assertIsNone(client.private_key);self.assertIsNone(client.signer);self.assertIsNone(client.account)
                self.assertEqual(client.collect_plugin_proofs(b's'*32,b'd'*32),{})


    def test_plugin_error_does_not_format_exception_or_stop_other_collectors(self):
        class OpaqueDiagnostic(Exception):
            reads=0
            def __str__(self):
                type(self).reads+=1
                return 'SYNTHETIC_PLUGIN_DIAGNOSTIC_MUST_NOT_ESCAPE'
            def __repr__(self):
                type(self).reads+=1
                return 'SYNTHETIC_PLUGIN_REPR_MUST_NOT_ESCAPE'
        def fail(**kwargs):raise OpaqueDiagnostic()
        key=b'G'*32
        result=A.ProofResult(valid=True,proof_type=key,proof_data=b'fixture',trust_weight=1,metadata={'evidence_classification':'non-authoritative'})
        client=A.TrustAggregatorClient.__new__(A.TrustAggregatorClient)
        client.plugins={b'B'*32:SimpleNamespace(name=lambda:'bad-fixture',generate_proof=fail),key:SimpleNamespace(name=lambda:'good-fixture',generate_proof=lambda **kw:result)}
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(client.collect_plugin_proofs(b's'*32,b'd'*32),{key:result})
        self.assertEqual(OpaqueDiagnostic.reads,0)
        self.assertNotIn('SYNTHETIC_PLUGIN',output.getvalue())

    def test_plugin_error_handler_does_not_call_the_failed_plugins_name(self):
        calls=[]
        def fail(**kwargs):raise RuntimeError('SYNTHETIC_PLUGIN_FAILURE')
        def unsafe_name():calls.append('name');raise RuntimeError('SYNTHETIC_PLUGIN_NAME_FAILURE')
        client=A.TrustAggregatorClient.__new__(A.TrustAggregatorClient)
        client.plugins={b'B'*32:SimpleNamespace(name=unsafe_name,generate_proof=fail)}
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(client.collect_plugin_proofs(b's'*32,b'd'*32),{})
        self.assertEqual(calls,[]);self.assertNotIn('SYNTHETIC_PLUGIN',output.getvalue())



if __name__=='__main__':unittest.main()
