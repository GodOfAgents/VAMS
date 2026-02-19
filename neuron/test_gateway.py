import requests
import time
import sys

BASE_URL = "http://localhost:8000"

def test_gateway():
    print(f"Testing Gateway at {BASE_URL}...")
    
    # 1. Check Root
    try:
        r = requests.get(BASE_URL)
        print(f"ROOT: {r.status_code} {r.json()}")
    except Exception as e:
        print(f"❌ Server not reachable: {e}")
        sys.exit(1)

    # 2. Register Agent
    agent_data = {
        "node_id": "test_agent_01",
        "public_key": "0xPubicKey123",
        "stake_amount": 1000.0,
        "capabilities": {"compute": "gpu"},
        "version": "1.0.0"
    }
    
    r = requests.post(f"{BASE_URL}/agents/register", json=agent_data)
    print(f"REGISTER: {r.status_code} {r.json()}")
    assert r.status_code == 200

    # 3. Send Heartbeat
    hb_data = {
        "payload": f"{time.time()}|active|test_agent_01",
        "signature": "0xSig123"
    }
    r = requests.post(f"{BASE_URL}/heartbeat", json=hb_data)
    print(f"HEARTBEAT: {r.status_code} {r.json()}")
    assert r.status_code == 200
    
    # 4. Check Rate Limit (Stub)
    # We won't flood it here, but just ensuring consecutive calls work
    r = requests.get(f"{BASE_URL}/")
    assert r.status_code == 200
    
    print("\n✅ Gateway Verification Successful!")

if __name__ == "__main__":
    time.sleep(2) # Wait for server boot
    test_gateway()
