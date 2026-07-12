"""
VAMS OMS Identity Integration
=============================
Integrates with the Polygon Open Money Stack (OMS) Identity and Compliance layer.
This validates KYC/KYB status for institutional routing and other compliance requirements.
"""
import os
import requests
from typing import Dict, Optional

import logging

from neuron.runtime_safety import (
    LiveModeSafetyError,
    require_live_secret,
    require_not_live_mock,
)

logger = logging.getLogger("VAMS-OMS-Identity")

class OMSIdentityVerifier:
    """
    Client for OMS Identity to verify if an address meets institutional compliance requirements.
    """
    def __init__(self, api_url: str = None, api_key: str = None, mock_mode: Optional[bool] = None):
        self.api_url = api_url or os.getenv("OMS_IDENTITY_API", "https://api.oms.polygon.technology/identity")
        self.api_key = api_key or os.getenv("OMS_API_KEY", "")
        
        # Determine mock mode: parameter takes precedence, then environment variable, defaulting to True
        if mock_mode is not None:
            self.mock_mode = mock_mode
        else:
            self.mock_mode = os.getenv("OMS_MOCK_MODE", "true").lower() == "true"

        require_not_live_mock("OMSIdentityVerifier", self.mock_mode)
        require_live_secret("OMSIdentityVerifier", self.api_key)
        if not self.mock_mode and not self.api_key:
            raise LiveModeSafetyError("OMSIdentityVerifier requires OMS_API_KEY outside mock mode")
            
        logger.info(f"Initialized OMSIdentityVerifier (mock_mode={self.mock_mode}, url={self.api_url})")

    def is_verified(self, address: str) -> bool:
        """
        Check if an address has a verified identity meeting institutional compliance standards.
        """
        if not address:
            return False
            
        if self.mock_mode:
            # For demonstration and testing purposes, assume addresses starting with 0x99 are verified
            is_verified_mock = address.lower().startswith("0x99")
            logger.debug(f"OMS Identity (Mock Mode) checked {address}: {'VERIFIED' if is_verified_mock else 'UNVERIFIED'}")
            return is_verified_mock
            
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = requests.get(f"{self.api_url}/v1/verification/{address}", headers=headers, timeout=5)
            if resp.status_code == 200:
                is_verified = resp.json().get("is_verified", False)
                logger.info(f"OMS Identity checked {address}: {'VERIFIED' if is_verified else 'UNVERIFIED'}")
                return is_verified
            else:
                logger.warning(f"OMS Identity check failed: API returned status code {resp.status_code} for {address}")
                return False
        except requests.RequestException as e:
            logger.error(f"OMS Identity check error for {address}: {e}")
            # Fail closed on identity verification errors
            return False
        except Exception as e:
            logger.error(f"Unexpected error in OMS Identity verification: {e}")
            return False
