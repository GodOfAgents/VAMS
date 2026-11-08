"""
VAMS OMS Identity Integration
=============================
Integrates with the Polygon Open Money Stack (OMS) Identity and Compliance layer.
This validates KYC/KYB status for institutional routing and other compliance requirements.
"""
import os
import requests
from dataclasses import dataclass
from typing import Mapping, Optional

import logging

from neuron.runtime_safety import (
    LiveModeSafetyError,
    RuntimePolicy,
    load_runtime_policy,
    resolve_component_mock_mode,
)

logger = logging.getLogger("VAMS-OMS-Identity")

OMS_MOCK_VARIABLE = "OMS_MOCK_MODE"


@dataclass(frozen=True)
class OMSVerificationResult:
    """Sanitized identity-verification outcome with explicit provenance."""

    verified: bool
    simulated: bool
    runtime_classification: str
    evidence_classification: str
    error_code: Optional[str] = None

    @property
    def usable_for_compliance(self) -> bool:
        return self.verified and self.evidence_classification == "live-provider"


class OMSIdentityVerifier:
    """
    Client for OMS Identity to verify if an address meets institutional compliance requirements.
    """
    def __init__(
        self,
        api_url: str = None,
        api_key: str = None,
        mock_mode: Optional[bool] = None,
        *,
        runtime_policy: Optional[RuntimePolicy] = None,
        environ: Optional[Mapping[str, str]] = None,
        transport=None,
        timeout: float = 5.0,
    ):
        source = os.environ if environ is None else environ
        self.runtime_policy = runtime_policy or load_runtime_policy(source)
        self.mock_mode = resolve_component_mock_mode(
            "OMSIdentityVerifier",
            OMS_MOCK_VARIABLE,
            mock_mode,
            policy=self.runtime_policy,
            environ=source,
        )
        self.api_url = api_url if api_url is not None else source.get("OMS_IDENTITY_API", "")
        self.api_key = api_key if api_key is not None else source.get("OMS_API_KEY", "")
        self._transport = transport or requests
        self.timeout = timeout

        if not self.mock_mode and (not self.api_url or not self.api_key):
            raise LiveModeSafetyError(
                "OMSIdentityVerifier real mode requires OMS_IDENTITY_API and OMS_API_KEY"
            )

        logger.info(
            "Initialized OMSIdentityVerifier mode=%s runtime=%s",
            "simulation" if self.mock_mode else "provider",
            self.runtime_policy.runtime_classification,
        )

    def _result(
        self, verified: bool, *, simulated: bool, error_code: Optional[str] = None
    ) -> OMSVerificationResult:
        evidence = (
            "live-provider"
            if verified and not simulated and self.runtime_policy.is_live
            else "non-authoritative"
        )
        return OMSVerificationResult(
            verified=verified,
            simulated=simulated,
            runtime_classification=self.runtime_policy.runtime_classification,
            evidence_classification=evidence,
            error_code=error_code,
        )

    def verify_identity(self, address: str) -> OMSVerificationResult:
        """Verify an address without exposing it in diagnostics or metadata."""

        if not address:
            return self._result(False, simulated=self.mock_mode, error_code="missing_subject")

        if self.mock_mode:
            return self._result(
                address.lower().startswith("0x99"),
                simulated=True,
            )

        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = self._transport.get(
                f"{self.api_url.rstrip('/')}/v1/verification/{address}",
                headers=headers,
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                logger.warning("OMSIdentityVerifier provider returned non-success status")
                return self._result(False, simulated=False, error_code="provider_status")
            payload = resp.json()
            if not isinstance(payload, dict) or type(payload.get("is_verified")) is not bool:
                logger.warning("OMSIdentityVerifier provider returned malformed response")
                return self._result(False, simulated=False, error_code="malformed_response")
            return self._result(payload["is_verified"], simulated=False)
        except requests.RequestException:
            logger.error("OMSIdentityVerifier provider request failed")
            return self._result(False, simulated=False, error_code="provider_unavailable")
        except (TypeError, ValueError):
            logger.error("OMSIdentityVerifier provider response was invalid")
            return self._result(False, simulated=False, error_code="malformed_response")
        except Exception:
            logger.error("OMSIdentityVerifier provider operation failed")
            return self._result(False, simulated=False, error_code="provider_error")

    def is_verified(self, address: str) -> bool:
        """
        Check if an address has a verified identity meeting institutional compliance standards.
        """
        return self.verify_identity(address).verified

    def is_compliance_verified(self, address: str) -> bool:
        """Return true only for a successful live-provider compliance result."""

        return self.verify_identity(address).usable_for_compliance
