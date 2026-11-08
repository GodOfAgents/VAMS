"""Disabled-yield write boundaries: no actual signing, RPC or recovery evidence."""
import unittest
from unittest.mock import MagicMock, patch

from neuron.economics import yield_manager as module
from neuron.runtime_safety import LiveModeSafetyError


class YieldDisabledBoundaryTests(unittest.TestCase):
    def test_deploy_rejects_without_building_or_signing(self):
        fund, signer = MagicMock(), MagicMock()
        manager = module.YieldManager(fund, signer)
        with self.assertRaises(LiveModeSafetyError):
            manager.deploy_capital('fixture-vault', 1000)
        self.assertEqual(fund.mock_calls, [])
        self.assertEqual(signer.mock_calls, [])

    def test_withdraw_rejects_without_building_or_signing(self):
        fund, signer = MagicMock(), MagicMock()
        manager = module.YieldManager(fund, signer)
        with self.assertRaises(LiveModeSafetyError):
            manager.withdraw_capital('fixture-vault', 500)
        self.assertEqual(fund.mock_calls, [])
        self.assertEqual(signer.mock_calls, [])

    def test_every_mode_and_unknown_configuration_reject_before_poison_collaborators(self):
        class Poison:
            def __getattr__(self, name):
                raise AssertionError('disabled yield must not access collaborator attributes')
        for mode in (None, 'test', 'local', 'demo', 'staging', 'testnet', 'production', 'unknown'):
            env = {} if mode is None else {'VAMS_ENV': mode}
            with self.subTest(mode=mode), patch.dict('os.environ', env, clear=True):
                manager = module.YieldManager(Poison(), Poison())
                for name in ('deploy_capital', 'withdraw_capital'):
                    with self.subTest(method=name), self.assertRaises(LiveModeSafetyError):
                        getattr(manager, name)(Poison(), Poison())

    def test_invalid_and_extreme_arguments_cannot_reach_signer_or_logs(self):
        manager = module.YieldManager(MagicMock(), MagicMock())
        with patch.object(module.logger, 'info') as log:
            for amount in (None, False, True, -1, 0, 1.0, float('nan'), 2**256):
                for name in ('deploy_capital', 'withdraw_capital'):
                    with self.subTest(amount=repr(amount), method=name), self.assertRaises(LiveModeSafetyError):
                        getattr(manager, name)(object(), amount)
            log.assert_not_called()
        self.assertEqual(manager.fund.mock_calls, [])
        self.assertEqual(manager.signer.mock_calls, [])

    def test_read_only_balance_query_is_preserved_without_signer(self):
        fund, signer = MagicMock(), MagicMock()
        fund.functions.totalDeployedBalance.return_value.call.return_value = 123
        manager = module.YieldManager(fund, signer)
        self.assertEqual(manager.get_deployed_balance(), 123)
        fund.functions.totalDeployedBalance.assert_called_once_with()
        self.assertEqual(signer.mock_calls, [])

    def test_failed_balance_query_is_not_fabricated(self):
        fund, signer = MagicMock(), MagicMock()
        fund.functions.totalDeployedBalance.return_value.call.side_effect = RuntimeError('fixture-read-unavailable')
        manager = module.YieldManager(fund, signer)
        with self.assertRaisesRegex(RuntimeError, 'fixture-read-unavailable'):
            manager.get_deployed_balance()
        self.assertEqual(signer.mock_calls, [])


if __name__ == '__main__':
    unittest.main()
