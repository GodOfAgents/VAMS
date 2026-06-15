import pytest
import time
from neuron.sdk.trails_client import TrailsClient

def test_submit_intent_mock():
    client = TrailsClient(mock_mode=True)
    receipt = client.submit_intent("VAMS_L3", "Polygon", b"payload", 100)
    assert receipt.intent_id is not None
    assert receipt.status == "submitted"
    assert receipt.estimated_settlement_time >= int(time.time()) + 5

def test_get_status_mock():
    client = TrailsClient(mock_mode=True)
    receipt = client.submit_intent("VAMS_L3", "Polygon", b"payload", 100)
    status = client.get_status(receipt.intent_id)
    assert status.intent_id == receipt.intent_id
    assert status.status == "settled"
    assert status.tx_hash.startswith("0x")

from unittest.mock import patch, MagicMock
import requests

@patch("requests.post")
def test_live_mode_submit_intent(mock_post):
    # Mock response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "intent_id": "real-intent-123",
        "status": "submitted",
        "estimated_settlement_time": 999999
    }
    mock_post.return_value = mock_resp
    
    client = TrailsClient(mock_mode=False, api_url="https://api.test.trails", api_key="test-key")
    receipt = client.submit_intent("VAMS_L3", "Polygon", b"payload", 100)
    
    assert receipt.intent_id == "real-intent-123"
    assert receipt.status == "submitted"
    assert receipt.estimated_settlement_time == 999999
    
    # Verify requests.post was called with correct parameters
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.test.trails/intents"
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["json"]["source"] == "VAMS_L3"
    assert kwargs["json"]["destination"] == "Polygon"

@patch("requests.get")
def test_live_mode_get_status(mock_get):
    # Mock response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "intent_id": "real-intent-123",
        "status": "settled",
        "tx_hash": "0xabc"
    }
    mock_get.return_value = mock_resp
    
    client = TrailsClient(mock_mode=False, api_url="https://api.test.trails", api_key="test-key")
    status = client.get_status("real-intent-123")
    
    assert status.intent_id == "real-intent-123"
    assert status.status == "settled"
    assert status.tx_hash == "0xabc"
    
    # Verify requests.get was called
    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert args[0] == "https://api.test.trails/intents/real-intent-123"
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
