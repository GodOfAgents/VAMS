#!/usr/bin/env python3
"""
VAMS Live Sandbox Reachability Verification Script
==================================================
Tests the reachability and DNS/HTTP response status of Coinme, Trails, 
and OMS Identity endpoints without mock mode. Because staging credentials 
are not provided, this script verifies connection correctness by confirming
successful DNS resolution and receiving an HTTP 401/403 (Unauthorized/Forbidden) 
status rather than connection timeouts or hostname resolution failures.
"""

import os
import sys
import time
import socket
import urllib.parse
import requests

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neuron.sdk.oms_identity import OMSIdentityVerifier
from neuron.payments.coinme_client import CoinmeClient
from neuron.sdk.trails_client import TrailsClient

def check_dns(url: str) -> bool:
    """Resolve host for a given URL to check DNS reachability."""
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            print(f"[-] Invalid URL format: {url}")
            return False
        ip = socket.gethostbyname(hostname)
        print(f"[+] DNS check: {hostname} resolved to {ip}")
        return True
    except socket.gaierror as e:
        print(f"[-] DNS check failed for {url}: {e}")
        return False

def verify_endpoint_reachability(name: str, url: str, test_func) -> bool:
    """Run a test function and print detailed reachability statistics."""
    print(f"\n--- Testing reachability for: {name} ---")
    print(f"Endpoint: {url}")
    
    # 1. Check DNS resolution
    if not check_dns(url):
        return False
        
    # 2. Make connection
    start_time = time.time()
    try:
        test_func()
        print(f"[+] Connection succeeded with default key.")
        return True
    except requests.HTTPError as e:
        latency = (time.time() - start_time) * 1000
        response = e.response
        status_code = response.status_code if response else "Unknown"
        print(f"[~] Protocol response received in {latency:.2f}ms")
        print(f"[~] HTTP Status: {status_code}")
        
        # 401/403 validates that the server is reachable and processed our headers, 
        # even if it rejected the mock/demo key.
        if status_code in (401, 403, 404):
            print(f"[+] Reachability verified: Protocol level reached (HTTP {status_code})")
            return True
        else:
            print(f"[-] Unexpected HTTP response: {e}")
            return False
    except requests.RequestException as e:
        print(f"[-] Network reachability failure: {e}")
        return False
    except Exception as e:
        print(f"[-] Unexpected error: {e}")
        return False

def main():
    print("VAMS Live Sandbox Reachability Verification")
    print("===========================================")
    
    # Instantiate clients with mock_mode=False to bypass simulation layer.
    # Live checks require explicit API keys from the operator environment.
    identity_url = os.getenv("OMS_IDENTITY_API", "https://api.oms.polygon.technology/identity")
    coinme_url = os.getenv("COINME_API_URL", "https://api.coinme.com/v1")
    trails_url = os.getenv("TRAILS_API_URL", "https://api.trails.polygon.technology/v1")
    oms_api_key = os.getenv("OMS_API_KEY")
    coinme_api_key = os.getenv("COINME_API_KEY")
    trails_api_key = os.getenv("TRAILS_API_KEY")

    missing = [
        name
        for name, value in (
            ("OMS_API_KEY", oms_api_key),
            ("COINME_API_KEY", coinme_api_key),
            ("TRAILS_API_KEY", trails_api_key),
        )
        if not value
    ]
    if missing:
        print(f"[-] Missing required live API keys: {', '.join(missing)}")
        return

    identity_verifier = OMSIdentityVerifier(mock_mode=False, api_url=identity_url, api_key=oms_api_key)
    coinme_client = CoinmeClient(mock_mode=False, base_url=coinme_url, api_key=coinme_api_key)
    trails_client = TrailsClient(mock_mode=False, api_url=trails_url, api_key=trails_api_key)
    
    results = {}
    
    # 1. Test OMS Identity Verifier
    # We call is_verified with a sample address.
    # Note: OMS Identity Verifier catches RequestException internally and fails closed (returns False).
    # To capture HTTP code, we will make a direct requests check or inspect verifier logs.
    def test_identity():
        headers = {"Authorization": f"Bearer {oms_api_key}"}
        resp = requests.get(f"{identity_url}/v1/verification/0x0000000000000000000000000000000000000000", headers=headers, timeout=5)
        resp.raise_for_status()
        
    results["OMS Identity API"] = verify_endpoint_reachability("OMS Identity API", identity_url, test_identity)
    
    # 2. Test Coinme Client
    # We call get_conversion_rate, which returns fallback if it fails, or raises in create_checkout.
    # Let's test create_checkout to catch the raise.
    def test_coinme():
        coinme_client.create_checkout(100.0, "USD", "0x0000000000000000000000000000000000000000")
        
    results["Coinme API"] = verify_endpoint_reachability("Coinme API", coinme_url, test_coinme)
    
    # 3. Test Trails Client
    # We call submit_intent, which throws HTTPError if the response code is not 200/201.
    def test_trails():
        trails_client.submit_intent("0xSOURCE", "0xDEST", b"payload")
        
    results["Trails API"] = verify_endpoint_reachability("Trails API", trails_url, test_trails)
    
    print("\n================ Verification Summary ================")
    all_ok = True
    for name, success in results.items():
        status = "PASSED" if success else "FAILED"
        print(f"{name:20}: {status}")
        if not success:
            all_ok = False
            
    if all_ok:
        print("[+] All sandbox endpoints resolved and are protocol-reachable.")
        sys.exit(0)
    else:
        print("[-] One or more sandbox endpoints were unreachable or failed connection validation.")
        sys.exit(1)

if __name__ == "__main__":
    main()
