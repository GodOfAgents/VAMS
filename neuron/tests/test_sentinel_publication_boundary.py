"""Controlled dependency fixtures of real Sentinel methods; not live evidence."""
import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,patch

from neuron.runtime_safety import load_runtime_policy,LiveModeSafetyError
from neuron.sentinel.sentinel_node import VAMSSentinelNode


class RegistryTrap:
    def __init__(self):self.accesses=0
    @property
    def web3(self):
        self.accesses+=1
        return SimpleNamespace(eth=SimpleNamespace())


class SentinelPublicationBoundaryTests(unittest.IsolatedAsyncioTestCase):
    def node(self):
        source={'VAMS_ENV':'test'}
        # Exercise real public methods with explicit dependency counters. This
        # does not instantiate a real SDK/DA/challenge or demonstrate hardware.
        node=VAMSSentinelNode.__new__(VAMSSentinelNode)
        node.runtime_policy=load_runtime_policy(source); node.mock_mode=False
        node._runtime_environ=source;node.operator_address='public-fixture'
        node.registry=RegistryTrap();node.private_key=None;node.sla_enforcer_address=None
        node.anomaly_detector=None;node.world_state_fidelity_sentinel=None
        node._node_skill_gaps={}
        node._secure_random=SimpleNamespace(choice=lambda values:values[0],uniform=lambda *args:0)
        node.challenges={'latency':SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(
            score=10000,passed=True,kpis={}))) }
        node.da=SimpleNamespace(publish_sentinel_report=AsyncMock(return_value={
            'success':True,'protocol':'fixture','daHeight':1,'daCommitment':'public-fixture'}))
        node._freeze_runtime_configuration()
        return node,source

    async def audit(self,node):return await node.audit_node(b'n'*32,'fixture-only','latency',b'h'*32)

    async def test_local_publication_without_sla_configuration_stays_true(self):
        node,_=self.node()
        with self.assertLogs('neuron.sentinel.sentinel_node',level='INFO') as logs:
            self.assertIs(await self.audit(node),True)
        node.da.publish_sentinel_report.assert_awaited_once()
        self.assertNotIn('Audit anchored',' '.join(logs.output))
        self.assertEqual(node.registry.accesses,0)

    async def test_requested_sla_has_no_false_success_or_web3_access(self):
        node,_=self.node();node.private_key=object();node.sla_enforcer_address='public-fixture'
        with self.assertLogs('neuron.sentinel.sentinel_node',level='INFO') as logs:
            self.assertIs(await self.audit(node),False)
        self.assertEqual(node.registry.accesses,0)
        self.assertNotIn('completed successfully',' '.join(logs.output))

    async def test_direct_sla_placeholder_rejects_before_sdk_access(self):
        node,_=self.node()
        with self.assertRaises(LiveModeSafetyError):await node._submit_sla_report({}, {})
        self.assertEqual(node.registry.accesses,0)

    async def test_partial_sla_configuration_fails_explicitly(self):
        for field,value in (('private_key',object()),('sla_enforcer_address','public-fixture')):
            node,_=self.node();setattr(node,field,value)
            self.assertIs(await self.audit(node),False)
            self.assertEqual(node.registry.accesses,0)

    async def test_non_boolean_da_success_does_not_mean_publication(self):
        for value in ('true','false',1,0,[],{},None):
            node,_=self.node();node.da.publish_sentinel_report.return_value['success']=value
            self.assertIs(await self.audit(node),False)

    async def test_probe_exception_is_exact_false_and_bounded_diagnostic(self):
        node,_=self.node();node.challenges['latency'].run.side_effect=ValueError('private-fixture-diagnostic-marker')
        with self.assertLogs('neuron.sentinel.sentinel_node',level='ERROR') as logs:
            self.assertIs(await self.audit(node),False)
        self.assertNotIn('private-fixture-diagnostic-marker',' '.join(logs.output))
        node.da.publish_sentinel_report.assert_not_awaited()

    async def test_da_exception_is_exact_false_and_bounded_diagnostic(self):
        node,_=self.node();node.da.publish_sentinel_report.side_effect=ValueError('private-fixture-diagnostic-marker')
        with self.assertLogs('neuron.sentinel.sentinel_node',level='ERROR') as logs:
            self.assertIs(await self.audit(node),False)
        self.assertNotIn('private-fixture-diagnostic-marker',' '.join(logs.output))

    async def test_da_failure_does_not_log_backend_payload(self):
        node,_=self.node();node.da.publish_sentinel_report.return_value={'success':False,'error':'private-fixture-diagnostic-marker'}
        with self.assertLogs('neuron.sentinel.sentinel_node',level='ERROR') as logs:
            self.assertIs(await self.audit(node),False)
        self.assertNotIn('private-fixture-diagnostic-marker',' '.join(logs.output))

    async def test_invalid_node_input_does_not_break_failure_return(self):
        node,_=self.node()
        self.assertIs(await node.audit_node(None,'fixture-only','latency',b'h'*32),False)

    async def test_direct_probe_rejects_live_invalid_and_changed_modes(self):
        for mode in ('testnet','staging','production','invalid','local'):
            node,source=self.node();source['VAMS_ENV']=mode
            with self.assertRaises(LiveModeSafetyError):
                await node.execute_challenge(b'n'*32,'fixture-only','latency',b'h'*32)
            node.challenges['latency'].run.assert_not_awaited()

    async def test_audit_entry_rejects_runtime_drift_with_zero_effects(self):
        node,source=self.node();source['VAMS_ENV']='testnet'
        self.assertIs(await self.audit(node),False)
        node.challenges['latency'].run.assert_not_awaited()
        node.da.publish_sentinel_report.assert_not_awaited()

    async def test_mode_drift_during_awaited_probe_prevents_publication(self):
        node,source=self.node();result=node.challenges['latency'].run.return_value
        async def change_mode(_):source['VAMS_ENV']='testnet';return result
        node.challenges['latency'].run.side_effect=change_mode
        self.assertIs(await self.audit(node),False)
        node.da.publish_sentinel_report.assert_not_awaited()

    async def test_registered_mock_drift_prevents_probe(self):
        node,source=self.node();source['SENTINEL_MOCK_MODE']='true'
        with self.assertRaises(LiveModeSafetyError):
            await node.execute_challenge(b'n'*32,'fixture-only','latency',b'h'*32)
        node.challenges['latency'].run.assert_not_awaited()

    async def test_scheduler_rejects_drift_before_task_creation(self):
        node,source=self.node();source['VAMS_ENV']='testnet'
        with patch('neuron.sentinel.sentinel_node.asyncio.create_task',side_effect=lambda coro:coro.close()) as task:
            # A bounded timeout exposes the old endless loop; no worker is left.
            with self.assertRaises(LiveModeSafetyError):await asyncio.wait_for(node.run_scheduler(),.05)
            task.assert_not_called()

    async def test_local_custom_mapping_does_not_rebind_to_process_environment(self):
        node,_=self.node()
        with patch.dict('os.environ',{'VAMS_ENV':'local'},clear=True):
            self.assertIs(await self.audit(node),True)

    async def test_runtime_source_cannot_be_rebound_after_freeze(self):
        node,_=self.node()
        with self.assertRaises(LiveModeSafetyError):node._runtime_environ={'VAMS_ENV':'test'}

    async def test_live_constructor_rejects_before_dependency_construction(self):
        for mode in ('staging','testnet','production'):
            with self.assertRaises(LiveModeSafetyError):VAMSSentinelNode(environ={'VAMS_ENV':mode})

    async def test_actual_constructor_retains_the_injected_mapping(self):
        source={'VAMS_ENV':'test'}
        names=('HardwareRegistryClient','PerformanceAuditLog','GPUBenchmark','CPUBenchmark',
               'StorageBenchmark','LatencyBenchmark','MemoryBenchmark')
        from contextlib import ExitStack
        with ExitStack() as stack:
            factories=[stack.enter_context(patch('neuron.sentinel.sentinel_node.'+name)) for name in names]
            node=VAMSSentinelNode(environ=source)
        self.assertIs(node._runtime_environ,source)
        self.assertTrue(all(factory.call_count==1 for factory in factories))
        source['VAMS_ENV']='testnet'
        with self.assertRaises(LiveModeSafetyError):
            await node.execute_challenge(b'n'*32,'fixture-only','latency',b'h'*32)

    async def test_drift_during_publication_returns_false_without_claiming_absence(self):
        node,source=self.node();result=node.da.publish_sentinel_report.return_value
        async def publish(*args,**kwargs):source['VAMS_ENV']='testnet';return result
        node.da.publish_sentinel_report.side_effect=publish
        self.assertIs(await self.audit(node),False)
        node.da.publish_sentinel_report.assert_awaited_once() # Publication may already exist.


if __name__=='__main__':unittest.main()
