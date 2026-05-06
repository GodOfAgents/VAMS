import requests
import logging
from typing import Optional
from neuron import config

logger = logging.getLogger("OMSIdentity")

class OMSIdentityVerifier:
    """
    Verifies institutional identity via Polygon Open Money Stack (OMS).
    Checks if an address has a valid KYC status to enable institutional routing (P3).
    """

    def __init__(self, api_url: str = None, api_key: str = None):
        self.api_url = api_url or config.OMS_IDENTITY_API
        self.api_key = api_key or config.OMS_API_KEY
        self.mock_mode = config.MOCK_MODE

    def is_verified(self, address: str) -> bool:
        """
        Queries the OMS Identity API to check the verification status of an address.
        """
        if self.mock_mode:
            # Mock verification for testing: addresses starting with 0x0 are institutional
            logger.info(f"[MOCK] Verifying OMS Identity for {address}")
            return address.lower().startswith("0x0")

        if not self.api_key:
            logger.warning("OMS_API_KEY not configured. Falling back to unverified status.")
            return False

        try:
            # Simulate call to OMS Identity API
            # Headers include the Bearer token for authentication
            response = requests.get(
                f"{self.api_url}/{address}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unverified")
                logger.info(f"OMS Identity status for {address}: {status}")
                return status == "verified"
            else:
                logger.error(f"OMS Identity API error: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to query OMS Identity API: {e}")
            return False

    def get_tier(self, address: str) -> int:
        """
        Returns the identity tier: 0 (retail), 1 (institutional/KYC)
        Used by CLRouter for P3 vs Public routing decisions.
        """
        return 1 if self.is_verified(address) else 0

if __name__ == "__main__":
    # Configure logging for standalone test
    logging.basicConfig(level=logging.INFO)
    verifier = OMSIdentityVerifier()
    # 0x0... address should be verified in mock mode
    test_addr_1 = "0x0123456789abcdef0123456789abcdef01234567"
    test_addr_2 = "0x123456789abcdef0123456789abcdef01234567"
    
    print(f"Testing address {test_addr_1}: {'VERIFIED' if verifier.is_verified(test_addr_1) else 'UNVERIFIED'}")
    print(f"Testing address {test_addr_2}: {'VERIFIED' if verifier.is_verified(test_addr_2) else 'UNVERIFIED'}")
