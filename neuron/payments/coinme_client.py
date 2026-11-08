import json
import logging
import os
import requests
from typing import Dict, Any, Mapping, Optional

from neuron.runtime_safety import (
    ImmutableRuntimeConfiguration,
    LiveModeSafetyError,
    RuntimePolicy,
    load_runtime_policy,
    resolve_component_mock_mode,
)

logger = logging.getLogger("VAMS-Coinme")

COINME_MOCK_VARIABLE = "COINME_MOCK_MODE"


class CoinmeClient(ImmutableRuntimeConfiguration):
    """
    Wrapper for Coinme API (Fiat-to-crypto on-ramp).
    Provides universal top-up capabilities and KYC passthrough.
    """
    
    _immutable_runtime_fields = frozenset(
        {"api_key", "base_url", "mock_mode", "runtime_policy", "_transport"}
    )

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        mock_mode: Optional[bool] = None,
        *,
        environ: Optional[Mapping[str, str]] = None,
        policy: Optional[RuntimePolicy] = None,
        transport: Any = requests,
    ):
        source = os.environ if environ is None else environ
        self.runtime_policy = policy or load_runtime_policy(source)
        self.mock_mode = resolve_component_mock_mode(
            "CoinmeClient",
            COINME_MOCK_VARIABLE,
            mock_mode,
            policy=self.runtime_policy,
            environ=source,
        )
        self.api_key = api_key if api_key is not None else source.get("COINME_API_KEY", "")
        self.base_url = base_url if base_url is not None else source.get("COINME_API_URL", "")
        self._transport = transport

        if self.runtime_policy.is_live:
            raise LiveModeSafetyError(
                "CoinmeClient live execution is disabled until checkout, rate, KYC, "
                "and webhook authenticity are independently verified"
            )
        if not self.mock_mode and not self.api_key:
            raise LiveModeSafetyError("CoinmeClient requires COINME_API_KEY outside mock mode")
        if not self.mock_mode and not self.base_url:
            raise LiveModeSafetyError("CoinmeClient requires COINME_API_URL outside mock mode")

        self._freeze_runtime_configuration()
        logger.info(
            "Initialized CoinmeClient (mode=%s, classification=%s, simulated=%s)",
            self.runtime_policy.mode.value,
            self.runtime_policy.runtime_classification,
            self.mock_mode,
        )

    def create_checkout(self, amount_fiat: float, currency: str, dest_address: str) -> Dict[str, Any]:
        """
        Creates a checkout session for a fiat to crypto conversion.
        """
        if self.mock_mode:
            return {
                "session_id": "simulated:checkout",
                "checkout_url": "simulated://coinme/checkout",
                "amount_fiat": amount_fiat,
                "currency": currency,
                "dest_address": dest_address,
                "status": "simulated",
                "simulated": True,
                "evidence_classification": "non-authoritative",
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
            resp = self._transport.post(f"{self.base_url}/checkouts", json=payload, headers=headers, timeout=10)
            if resp.status_code in (200, 201):
                return resp.json()
            else:
                raise requests.HTTPError(f"Coinme checkout API returned status {resp.status_code}", response=resp)
        except Exception as exc:
            raise LiveModeSafetyError("CoinmeClient checkout provider request failed") from exc

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
            resp = self._transport.get(f"{self.base_url}/rates", params=params, headers=headers, timeout=5)
            if resp.status_code == 200:
                payload = resp.json()
                if not isinstance(payload, dict) or "rate" not in payload:
                    raise ValueError("missing rate")
                rate = float(payload["rate"])
                if rate <= 0:
                    raise ValueError("invalid rate")
                return rate
            raise requests.HTTPError(
                f"Coinme rates API returned status {resp.status_code}", response=resp
            )
        except Exception as exc:
            raise LiveModeSafetyError("CoinmeClient rate provider request failed") from exc

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
            resp = self._transport.get(f"{self.base_url}/kyc/{user_id}", headers=headers, timeout=5)
            if resp.status_code == 200:
                return resp.json()
            else:
                raise requests.HTTPError(f"Coinme KYC check returned status {resp.status_code}", response=resp)
        except Exception as exc:
            raise LiveModeSafetyError("CoinmeClient KYC provider request failed") from exc

    def handle_webhook(self, payload: str, signature: str) -> bool:
        """
        Handle payment confirmation webhooks.
        """
        if not self.mock_mode:
            raise LiveModeSafetyError(
                "CoinmeClient webhook handling is disabled until cryptographic "
                "signature verification is implemented"
            )
        try:
            data = json.loads(payload)
            return isinstance(data, dict) and bool(signature)
        except json.JSONDecodeError:
            return False
