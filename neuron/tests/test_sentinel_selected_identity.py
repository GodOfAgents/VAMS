"""Local selected-account/report binding; no actual key, provider or custody evidence."""
from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, PropertyMock, patch

from neuron.runtime_safety import LiveModeSafetyError, RuntimeConfigurationError
from neuron.sdk import hardware_registry as H
from neuron.sentinel import sentinel_node as S

SELECTED = '0x' + '1' * 40
DIFFERENT = '0x' + '2' * 40
ZERO = '0x' + '0' * 40


class SentinelSelectedIdentityTests(unittest.IsolatedAsyncioTestCase):
    def fixtures(self, stack, *, parse_failure=False, selected=SELECTED):
        calls = []
        class Account:
            @staticmethod
            def from_key(value):
                calls.append('parse')
                if parse_failure: raise ValueError('SYNTHETIC_PARSE_DETAIL_MUST_NOT_ESCAPE')
                return SimpleNamespace(address=selected)
        class Web3:
            @staticmethod
            def HTTPProvider(url): calls.append('configure-provider'); return object()
            @staticmethod
            def to_checksum_address(value): return value
            def __init__(self, provider):
                self.eth = SimpleNamespace(account=Account, default_account=DIFFERENT, contract=lambda **kw: object())
        stack.enter_context(patch('web3.Web3', Web3))
        da = SimpleNamespace(publish_sentinel_report=AsyncMock(return_value={
            'success': True, 'protocol': 'fixture', 'daHeight': 1, 'daCommitment': 'fixture'}))
        da_factory = stack.enter_context(patch.object(S, 'PerformanceAuditLog', return_value=da))
        challenge = SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(score=10000, passed=True, kpis={})))
        for name in ('GPUBenchmark', 'CPUBenchmark', 'StorageBenchmark', 'LatencyBenchmark', 'MemoryBenchmark'):
            stack.enter_context(patch.object(S, name, return_value=challenge))
        return calls, da_factory, da

    def node(self):
        return S.VAMSSentinelNode(private_key='synthetic-parse-input', registry_addr='fixture-registry',
            rpc_url='https://example.invalid', environ={'VAMS_ENV': 'test'})

    async def test_selected_account_ignores_different_web3_default(self):
        with ExitStack() as stack:
            calls, _, _ = self.fixtures(stack)
            node = self.node()
            self.assertEqual(node.registry.w3.eth.default_account, DIFFERENT)
            self.assertEqual(node.registry.account_address, SELECTED)
            self.assertEqual(node.operator_address, SELECTED)
            self.assertEqual(calls.count('parse'), 1)

    async def test_sdk_no_key_address_is_none_and_property_is_read_only(self):
        c = H.HardwareRegistryClient()
        self.assertIsNone(c.account_address)
        with self.assertRaises(AttributeError): c.account_address = DIFFERENT

    async def test_sdk_key_without_registry_configuration_has_no_derived_identity(self):
        with ExitStack() as stack:
            calls, _, _ = self.fixtures(stack)
            c = H.HardwareRegistryClient(private_key='synthetic-parse-input')
            self.assertIsNone(c.account_address)
            self.assertEqual(calls, [])

    async def test_missing_configuration_rejects_identity_before_da_construction(self):
        with ExitStack() as stack:
            calls, da_factory, _ = self.fixtures(stack)
            with self.assertRaisesRegex(RuntimeConfigurationError, 'identity'):
                S.VAMSSentinelNode(private_key='synthetic-parse-input', environ={'VAMS_ENV': 'test'})
            da_factory.assert_not_called(); self.assertEqual(calls, [])

    async def test_parse_failure_is_bounded_and_rejects_before_da_construction(self):
        with ExitStack() as stack:
            calls, da_factory, _ = self.fixtures(stack, parse_failure=True)
            with self.assertLogs(H.logger, level='ERROR') as logs:
                with self.assertRaises(RuntimeConfigurationError) as error: self.node()
            self.assertNotIn('SYNTHETIC_PARSE_DETAIL', str(error.exception))
            self.assertNotIn('SYNTHETIC_PARSE_DETAIL', ' '.join(logs.output))
            da_factory.assert_not_called(); self.assertEqual(calls.count('parse'), 1)

    async def test_no_key_placeholder_does_not_read_account_address(self):
        with ExitStack() as stack:
            calls, da_factory, _ = self.fixtures(stack)
            accessor = stack.enter_context(patch.object(H.HardwareRegistryClient, 'account_address',
                new_callable=PropertyMock, create=True, side_effect=AssertionError('No account read without supplied key')))
            node = S.VAMSSentinelNode(environ={'VAMS_ENV': 'test'})
            self.assertEqual(node.operator_address, ZERO); accessor.assert_not_called()
            self.assertEqual(calls, []); da_factory.assert_called_once()

    async def test_live_mode_refusal_precedes_registry_or_account_access(self):
        with patch.object(S, 'HardwareRegistryClient') as registry, patch.object(S, 'PerformanceAuditLog') as da:
            for mode in ('staging', 'testnet', 'production'):
                with self.subTest(mode=mode), self.assertRaises(LiveModeSafetyError):
                    S.VAMSSentinelNode(private_key='synthetic-parse-input', environ={'VAMS_ENV': mode})
            registry.assert_not_called(); da.assert_not_called()

    async def test_malformed_or_zero_selected_address_rejects(self):
        for address in (None, '', ZERO, '0x' + 'g'*40, SELECTED+' ', True, '1'*40):
            with self.subTest(address=address), ExitStack() as stack:
                _, da_factory, _ = self.fixtures(stack, selected=address)
                with self.assertRaises(RuntimeConfigurationError): self.node()
                da_factory.assert_not_called()

    async def test_actual_report_binds_selected_actor_and_sla_stays_unavailable(self):
        with ExitStack() as stack:
            _, _, da = self.fixtures(stack)
            node = self.node()
            report = await node.execute_challenge(b'n'*32, 'fixture-only', 'latency', b'h'*32)
            self.assertEqual(report['sentinelId'], SELECTED)
            self.assertIs(await node.audit_node(b'n'*32, 'fixture-only', 'latency', b'h'*32), False)
            self.assertEqual(da.publish_sentinel_report.await_count, 1)
            with self.assertRaises(LiveModeSafetyError): await node._submit_sla_report(report, {})


if __name__ == '__main__': unittest.main()
