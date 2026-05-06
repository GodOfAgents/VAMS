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

def test_live_mode_not_implemented():
    client = TrailsClient(mock_mode=False)
    with pytest.raises(NotImplementedError):
        client.submit_intent("VAMS_L3", "Polygon", b"payload")
        
    with pytest.raises(NotImplementedError):
        client.get_status("some_id")
