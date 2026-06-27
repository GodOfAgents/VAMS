import json
import logging
import os
import requests
from typing import Dict, Any, Optional

from neuron.runtime_safety import require_live_secret, require_not_live_mock

logger = logging.getLogger("VAMS-Coinme")

class CoinmeClient:
    """
    Wrapper for Coinme API (Fiat-to-crypto on-ramp).
    Provides universal top-up capabilities and KYC passthrough.
    """
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = None, mock_mode: Optional[bool] = None):
        self.api_key = api_key or os.getenv("COINME_API_KEY", "demo-key")
        self.base_url = base_url or os.getenv("COINME_API_URL", "https://api.coinme.com/v1")
        
        # Determine mock mode
        if mock_mode is not None:
            self.mock_mode = mock_mode
        else:
            self.mock_mode = os.getenv("COINME_MOCK_MODE", "true").lower() == "true" or self.api_key == "demo-key"

        require_not_live_mock("CoinmeClient", self.mock_mode)
        require_live_secret("CoinmeClient", self.api_key, insecure_values={"demo-key"})
            
        logger.info(f"Initialized CoinmeClient (mock_mode={self.mock_mode}, url={self.base_url})")

    def create_checkout(self, amount_fiat: float, currency: str, dest_address: str) -> Dict[str, Any]:
        """
        Creates a checkout session for a fiat to crypto conversion.
        """
        logger.info(f"Creating checkout for {amount_fiat} {currency} to {dest_address}")
        
        if self.mock_mode:
            return {
                "session_id": "sess_" + dest_address[:8] + str(int(amount_fiat)),
                "checkout_url": f"https://checkout.coinme.com/pay/{dest_address[:8]}",
                "amount_fiat": amount_fiat,
                "currency": currency,
                "dest_address": dest_address,
                "status": "pending"
            }
            
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "amount": amount_fiat,
                "currency": currency,
                "destination_address": dest_address
            }
            resp = requests.post(f"{self.base_url}/checkouts", json=payload, headers=headers, timeout=10)
            if resp.status_code in (200, 201):
                return resp.json()
            else:
                logger.error(f"Coinme checkout API failed: Status {resp.status_code}, Response: {resp.text}")
                raise requests.HTTPError(f"Coinme checkout API returned status {resp.status_code}", response=resp)
        except Exception as e:
            logger.error(f"Error creating Coinme checkout: {e}")
            raise

    def get_conversion_rate(self, from_currency: str, to_token: str) -> float:
        """
        Get current exchange rate.
        """
        if self.mock_mode:
            if from_currency == "USD" and to_token == "VAMS":
                return 10.0 # 1 USD = 10 VAMS
            return 1.0
            
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            params = {"from": from_currency, "to": to_token}
            resp = requests.get(f"{self.base_url}/rates", params=params, headers=headers, timeout=5)
            if resp.status_code == 200:
                return float(resp.json().get("rate", 1.0))
            else:
                logger.warning(f"Coinme rates API failed: Status {resp.status_code}. Using fallback rate.")
        except Exception as e:
            logger.error(f"Error fetching Coinme conversion rate: {e}")
            
        # Fallback rate
        if from_currency == "USD" and to_token == "VAMS":
            return 10.0
        return 1.0

    def get_kyc_status(self, user_id: str) -> Dict[str, Any]:
        """
        Check KYC status from Coinme MTL coverage.
        """
        if self.mock_mode:
            return {
                "user_id": user_id,
                "status": "verified",
                "level": 2
            }
            
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = requests.get(f"{self.base_url}/kyc/{user_id}", headers=headers, timeout=5)
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.error(f"Coinme KYC check failed: Status {resp.status_code}")
                raise requests.HTTPError(f"Coinme KYC check returned status {resp.status_code}", response=resp)
        except Exception as e:
            logger.error(f"Error checking Coinme KYC: {e}")
            raise

    def handle_webhook(self, payload: str, signature: str) -> bool:
        """
        Handle payment confirmation webhooks.
        """
        try:
            # Simple signature verification placeholder / validation
            # In production, this would do cryptographic verification (HMAC-SHA256) of signature
            if not signature and not self.mock_mode:
                logger.warning("Missing Coinme webhook signature")
                return False
                
            data = json.loads(payload)
            logger.info(f"Handled webhook for session {data.get('session_id')}")
            return True
        except json.JSONDecodeError:
            return False
