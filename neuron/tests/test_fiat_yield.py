import pytest
from unittest.mock import MagicMock
from neuron.payments.coinme_client import CoinmeClient
from neuron.payments.universal_topup import UniversalTopUpManager
from neuron.economics.yield_manager import YieldManager
from neuron.runtime_safety import LiveModeSafetyError

def test_coinme_client_topup():
    client = CoinmeClient(
        api_key="test_key",
        mock_mode=True,
        environ={"VAMS_ENV": "test"},
    )
    session = client.create_checkout(100.0, "USD", "0xabc123")
    assert session["amount_fiat"] == 100.0
    assert session["currency"] == "USD"
    assert session["status"] == "simulated"
    assert session["simulated"] is True
    assert session["evidence_classification"] == "non-authoritative"

def test_universal_topup_manager():
    mock_client = MagicMock()
    mock_client.create_checkout.return_value = {"status": "pending"}
    
    mock_settlement = MagicMock()
    
    manager = UniversalTopUpManager(mock_client, mock_settlement, premium_bps=500)
    result = manager.initiate_top_up("agent_1", "0xabc", 100.0, "USD")
    
    # 5% of 100 is 5
    assert result["premium_applied_fiat"] == 5.0
    assert result["net_amount_fiat"] == 100.0
    mock_client.create_checkout.assert_called_once_with(105.0, "USD", "0xabc")

def test_universal_topup_webhook():
    mock_client = MagicMock()
    mock_client.handle_webhook.return_value = True
    
    manager = UniversalTopUpManager(mock_client, MagicMock())
    assert manager.process_webhook_deposit('{"session_id": "123"}', "sig") == True

def test_yield_manager_deploy():
    mock_fund = MagicMock()
    mock_signer = MagicMock()
    mock_signer.get_address.return_value = "0xyieldmanager"
    mock_signer.sign_transaction.return_value = "signed_tx"
    
    manager = YieldManager(mock_fund, mock_signer)
    with pytest.raises(LiveModeSafetyError):
        manager.deploy_capital("0xvault", 1000)
    assert mock_fund.mock_calls == []
    assert mock_signer.mock_calls == []

def test_yield_manager_withdraw():
    mock_fund = MagicMock()
    mock_signer = MagicMock()
    mock_signer.get_address.return_value = "0xyieldmanager"
    mock_signer.sign_transaction.return_value = "signed_tx"
    
    manager = YieldManager(mock_fund, mock_signer)
    with pytest.raises(LiveModeSafetyError):
        manager.withdraw_capital("0xvault", 500)
    assert mock_fund.mock_calls == []
    assert mock_signer.mock_calls == []
