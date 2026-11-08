"""
VAMS Neuron - Phala TEE SDK
===========================
Legacy Phala TEE client and local simulation fixtures. Provider responses are
not authenticated VAMS evidence and live action dispatch is unavailable.

Features:
- Local simulated report fixtures
- Legacy Phala and Marlin provider request wrappers
- Non-authoritative contract-call results in non-live configurations

Requires:
- Access to Phala RPC or Phat Contract SDK
- For full TEE: SGX-enabled hardware

Usage:
    from sdk.phala_tee import PhalaTEE
    
    tee = PhalaTEE()
    
    # Provider response is an unverified claim, not live VAMS evidence.
    report = tee.verify_sgx_quote(quote)
    
    # Direct contract calls are blocked in live and mock modes.
"""

import json
import os
import time
import hashlib
import base64
import requests
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple, Mapping
from enum import Enum

from neuron.runtime_safety import (
    ImmutableRuntimeConfiguration,
    LiveModeSafetyError,
    RuntimeConfigurationError,
    RuntimePolicy,
    load_runtime_policy,
    resolve_component_mock_mode,
)


PHALA_MOCK_VARIABLE = "PHALA_MOCK_MODE"
_DIAGNOSTIC_RESPONSE_LIMIT = 65_536
_DIAGNOSTIC_READ_REQUEST_LIMIT = 8_192
_DIAGNOSTIC_RESPONSE_ERRORS = frozenset(
    {
        "provider_response_too_large",
        "unsupported_content_encoding",
        "malformed_response",
        "provider_error",
    }
)


class _PhalaRuntimeDriftError(RuntimeConfigurationError):
    """Bounded rejection when ambient Phala runtime policy changes mid-call."""


def _status_only_health_probe(
    provider: str,
    technology: str,
    request,
    is_healthy,
    network: Optional[str] = None,
    runtime_check=None,
) -> dict:
    """Return bounded HTTP reachability only, always closing an acquired response."""
    started = None
    latency_ms = 0.0
    response = None
    status_code = None
    primary_error = None
    close_error = None
    final_check_error = None

    def check_runtime() -> None:
        try:
            runtime_check()
        except _PhalaRuntimeDriftError:
            raise
        except RuntimeConfigurationError:
            raise _PhalaRuntimeDriftError(
                "PhalaTEE runtime configuration changed during the operation"
            ) from None

    try:
        started = time.monotonic()
        if runtime_check is not None:
            check_runtime()
        response = request()
        if runtime_check is not None:
            check_runtime()
        status_code = response.status_code
        if runtime_check is not None:
            check_runtime()
        if type(status_code) is not int or not 100 <= status_code <= 599:
            raise ValueError("invalid HTTP status")
        latency_ms = (time.monotonic() - started) * 1000
    except BaseException as exc:
        primary_error = exc
    finally:
        if response is not None:
            try:
                response.close()
            except BaseException as exc:
                close_error = exc

        if runtime_check is not None:
            try:
                check_runtime()
            except BaseException as exc:
                final_check_error = exc

    # Runtime drift is the private, bounded rejection and wins over cleanup
    # failures. Other control exceptions propagate after the one close attempt.
    drift = next(
        (
            error
            for error in (primary_error, close_error, final_check_error)
            if isinstance(error, _PhalaRuntimeDriftError)
        ),
        None,
    )
    if drift is not None:
        raise drift
    for error in (primary_error, close_error, final_check_error):
        if error is not None and not isinstance(error, Exception):
            raise error

    failed = primary_error is not None or close_error is not None or final_check_error is not None
    result = {
        "status": "offline" if failed else ("healthy" if is_healthy(status_code) else "degraded"),
        "latency_ms": latency_ms,
        "provider": provider,
        "technology": technology,
        "verification_scope": "http_reachability",
        "evidence_classification": "non-authoritative",
    }
    if network is not None:
        result["network"] = network
    if failed:
        result["error"] = "provider_error"
    elif not is_healthy(status_code):
        result["error"] = f"HTTP {status_code}"
    return result


class _PhalaDiagnosticResponseError(Exception):
    """Fixed, bounded failure from an untrusted diagnostic response body."""

    def __init__(self, code: str):
        self.code = code if code in _DIAGNOSTIC_RESPONSE_ERRORS else "provider_error"
        super().__init__(self.code)


def _ambient_policy_for(component: str, source, supplied: Optional[RuntimePolicy]):
    ambient = load_runtime_policy(os.environ)
    configured = load_runtime_policy(source)
    if configured != ambient or (supplied is not None and supplied != ambient):
        raise RuntimeConfigurationError(
            f"Conflicting runtime policy for {component}; ambient runtime configuration is authoritative"
        )
    return ambient


class TEEProvider(Enum):
    """Supported TEE providers per ARCHITECTURE_v0-3-0.md §18."""
    PHALA = "phala"      # Intel SGX
    MARLIN = "marlin"    # AWS Nitro
    AUTOMATA = "automata" # Multi-Prover


@dataclass
class AttestationReport:
    """Legacy provider claim or explicitly simulated local report."""
    provider: TEEProvider
    is_valid: bool
    quote_hash: str
    mrenclave: Optional[str] = None  # SGX measurement
    mrsigner: Optional[str] = None   # SGX signer
    pcr_values: Optional[Dict[int, str]] = None  # For Nitro
    timestamp: float = 0.0
    error: Optional[str] = None
    simulated: bool = False
    runtime_classification: str = "non-live"
    evidence_classification: str = "non-authoritative"
    attested_root_eoa: Optional[str] = None
    report_data: Optional[str] = None
    provider_claim_valid: Optional[bool] = None

    @property
    def usable_as_live_evidence(self) -> bool:
        # The legacy Phala/Marlin response protocol is not authenticated.
        return False
    
    def to_dict(self) -> dict:
        return {
            "provider": self.provider.value,
            "is_valid": self.is_valid,
            "quote_hash": self.quote_hash[:16] + "..." if self.quote_hash else "",
            "mrenclave": self.mrenclave[:16] + "..." if self.mrenclave else None,
            "timestamp": self.timestamp,
            "error": self.error,
            "simulated": self.simulated,
            "runtime_classification": self.runtime_classification,
            "evidence_classification": self.evidence_classification,
            "provider_claim_valid": self.provider_claim_valid,
        }


@dataclass
class PhatContractResult:
    """Result from a Phat Contract call."""
    success: bool
    output: Any
    gas_used: int
    execution_time_ms: float
    error: Optional[str] = None
    simulated: bool = False
    evidence_classification: str = "non-authoritative"
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output": self.output,
            "gas_used": self.gas_used,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
            "simulated": self.simulated,
            "evidence_classification": self.evidence_classification,
        }


# Known Phala RPC endpoints
PHALA_RPC_ENDPOINTS = {
    "mainnet": "https://api.phala.network/pruntime",
    "testnet": "https://poc5.phala.network/pruntime",
    "local": "http://localhost:8000"
}

# Known Marlin Oyster endpoints
MARLIN_ENDPOINTS = {
    "mainnet": "https://gateway.marlin.org/attestation",
    "testnet": "https://testnet.marlin.org/attestation"
}


class PhalaTEE(ImmutableRuntimeConfiguration):
    """
    Phala TEE SDK for VAMS Neuron.
    
    Legacy provider calls are retained as unqualified, non-authoritative results.
    
    Historical design documents describe multi-TEE use for critical operations.
    This SDK does not authorize those operations; its provider reports remain
    non-authoritative until an authenticated verifier backend is integrated.

    """

    _immutable_runtime_fields = frozenset({"runtime_policy", "mock_mode"})
    
    def __init__(
        self,
        network: str = "testnet",
        phat_api_key: Optional[str] = None,
        timeout: int = 30,
        *,
        mock_mode: Optional[bool] = None,
        runtime_policy: Optional[RuntimePolicy] = None,
        environ: Optional[Mapping[str, str]] = None,
        phala_rpc: Optional[str] = None,
        marlin_rpc: Optional[str] = None,
        python_runtime: Optional[str] = None,
        transport=None,
    ):
        """
        Initialize Phala TEE client.
        
        Args:
            network: Network to connect to (mainnet, testnet, local)
            phat_api_key: Optional API key for Phat Contract access
            timeout: Request timeout in seconds
        """
        source = os.environ if environ is None else environ
        ambient_policy = _ambient_policy_for("PhalaTEE", source, runtime_policy)
        self.runtime_policy = ambient_policy
        ambient_mock = resolve_component_mock_mode(
            "PhalaTEE",
            PHALA_MOCK_VARIABLE,
            None,
            policy=self.runtime_policy,
            environ=os.environ,
        )
        if mock_mode is not None and not isinstance(mock_mode, bool):
            raise RuntimeConfigurationError(
                "Malformed mock selection for PhalaTEE; use a boolean"
            )
        if mock_mode is not None and mock_mode != ambient_mock:
            raise RuntimeConfigurationError(
                "Conflicting mock selection for PhalaTEE; ambient configuration is authoritative"
            )
        self.mock_mode = ambient_mock
        if network not in PHALA_RPC_ENDPOINTS:
            raise LiveModeSafetyError("PhalaTEE received an unsupported network")
        self.network = network
        self.phat_api_key = (
            phat_api_key if phat_api_key is not None else source.get("PHALA_API_KEY")
        )
        self.timeout = timeout
        self.python_runtime = (
            python_runtime
            if python_runtime is not None
            else source.get("VAMS_PHAT_PYTHON_RUNTIME", "")
        )

        configured_phala_rpc = phala_rpc or source.get("PHALA_RPC_URL")
        configured_marlin_rpc = marlin_rpc or source.get("MARLIN_ATTESTATION_URL")
        if self.runtime_policy.is_live and not self.mock_mode and not configured_phala_rpc:
            raise LiveModeSafetyError(
                "PhalaTEE real live mode requires PHALA_RPC_URL"
            )
        self.phala_rpc = configured_phala_rpc or PHALA_RPC_ENDPOINTS[network]
        self.marlin_rpc = configured_marlin_rpc or MARLIN_ENDPOINTS.get(
            network, MARLIN_ENDPOINTS["testnet"]
        )

        if transport is None:
            self._session = requests.Session()
            self._session.headers.update({
                "Content-Type": "application/json",
                "Accept": "application/json"
            })
        else:
            self._session = transport
        self._freeze_runtime_configuration()

    def _assert_current_runtime(self) -> None:
        try:
            current = load_runtime_policy(os.environ)
            if current != self.runtime_policy:
                raise _PhalaRuntimeDriftError(
                    "PhalaTEE runtime configuration changed during the operation"
                )
            current_mock = resolve_component_mock_mode(
                "PhalaTEE",
                PHALA_MOCK_VARIABLE,
                self.mock_mode,
                policy=current,
                environ=os.environ,
            )
            if current_mock != self.mock_mode:
                raise _PhalaRuntimeDriftError(
                    "PhalaTEE runtime configuration changed during the operation"
                )
        except _PhalaRuntimeDriftError:
            raise
        except LiveModeSafetyError:
            raise _PhalaRuntimeDriftError(
                "PhalaTEE runtime configuration changed during the operation"
            ) from None

    def _read_diagnostic_json_body(self, response) -> bytes:
        """Read a bounded identity-encoded response without eager body helpers."""
        try:
            headers = response.headers
            if not isinstance(headers, Mapping):
                raise _PhalaDiagnosticResponseError("provider_error")
            encodings = [
                value
                for name, value in headers.items()
                if isinstance(name, str) and name.lower() == "content-encoding"
            ]
        except _PhalaRuntimeDriftError:
            raise
        except _PhalaDiagnosticResponseError:
            raise
        except Exception:
            raise _PhalaDiagnosticResponseError("provider_error") from None

        if len(encodings) > 1:
            raise _PhalaDiagnosticResponseError("unsupported_content_encoding")
        if encodings:
            encoding = encodings[0]
            if not isinstance(encoding, str) or encoding.strip().lower() != "identity":
                raise _PhalaDiagnosticResponseError(
                    "unsupported_content_encoding"
                )

        try:
            raw = response.raw
            reader = raw.read
        except _PhalaRuntimeDriftError:
            raise
        except Exception:
            raise _PhalaDiagnosticResponseError("provider_error") from None
        if not callable(reader):
            raise _PhalaDiagnosticResponseError("provider_error")

        body = bytearray()
        while True:
            self._assert_current_runtime()
            remaining = _DIAGNOSTIC_RESPONSE_LIMIT - len(body)
            amount = min(_DIAGNOSTIC_READ_REQUEST_LIMIT, remaining + 1)
            try:
                chunk = reader(amount, decode_content=False)
            except _PhalaRuntimeDriftError:
                raise
            except requests.RequestException:
                raise
            except Exception:
                raise _PhalaDiagnosticResponseError("provider_error") from None

            # Detect mode drift before inspecting or appending bytes returned by
            # the provider. A callback cannot make the bytes part of a report.
            self._assert_current_runtime()
            if not isinstance(chunk, bytes) or len(chunk) > amount:
                raise _PhalaDiagnosticResponseError("provider_error")
            if not chunk:
                break
            if len(chunk) > remaining:
                raise _PhalaDiagnosticResponseError(
                    "provider_response_too_large"
                )
            body.extend(chunk)

        return bytes(body)

    def _consume_diagnostic_response(self, response):
        """Close one streamed diagnostic response before returning any body."""
        status_code = None
        body = None
        failure = None
        drift_error = None
        control_error = None
        control_traceback = None
        close_control_error = None
        close_control_traceback = None
        final_control_error = None
        final_control_traceback = None
        close_failed = False

        try:
            try:
                # This check is inside the cleanup scope: even drift immediately
                # after POST return must still close the acquired response.
                self._assert_current_runtime()
                status_code = response.status_code
                self._assert_current_runtime()
                if status_code == 200:
                    body = self._read_diagnostic_json_body(response)
            except _PhalaRuntimeDriftError as exc:
                drift_error = exc
            except _PhalaDiagnosticResponseError as exc:
                failure = exc.code
            except requests.RequestException:
                failure = "provider_unavailable"
            except Exception:
                failure = "provider_error"
            except BaseException as exc:
                # Process-control events are not provider failures. Defer them
                # until the acquired streamed response has had one cleanup attempt.
                control_error = exc
                control_traceback = exc.__traceback__
        finally:
            # A true finally is required because cancellation/process-control
            # events can bypass ordinary Exception handling at any point above.
            try:
                close = response.close
                if not callable(close):
                    close_failed = True
                else:
                    close()
            except _PhalaRuntimeDriftError as exc:
                if drift_error is None:
                    drift_error = exc
            except Exception:
                close_failed = True
            except BaseException as exc:
                close_control_error = exc
                close_control_traceback = exc.__traceback__

            # Recheck even after close failure. A cleanup exception must never
            # hide this SDK's private mode-drift rejection. Process-control
            # events from this final check are deferred too.
            try:
                self._assert_current_runtime()
            except _PhalaRuntimeDriftError as exc:
                if drift_error is None:
                    drift_error = exc
            except Exception:
                failure = "provider_error"
            except BaseException as exc:
                final_control_error = exc
                final_control_traceback = exc.__traceback__

        if drift_error is not None:
            raise drift_error
        if control_error is not None:
            raise control_error.with_traceback(control_traceback)
        if close_control_error is not None:
            raise close_control_error.with_traceback(close_control_traceback)
        if final_control_error is not None:
            raise final_control_error.with_traceback(final_control_traceback)
        if close_failed:
            return status_code, None, "provider_error"
        if failure is not None:
            return status_code, None, failure
        return status_code, body, None

    @staticmethod
    def _is_hex(value: object, length: int) -> bool:
        if not isinstance(value, str):
            return False
        raw = value.removeprefix("0x")
        if len(raw) != length:
            return False
        try:
            bytes.fromhex(raw)
        except ValueError:
            return False
        return True

    def _report(
        self,
        provider: TEEProvider,
        quote_hash: str,
        *,
        valid: bool,
        simulated: bool = False,
        error: Optional[str] = None,
        **details,
    ) -> AttestationReport:
        self._assert_current_runtime()
        if simulated:
            self.runtime_policy.authorize_component_mock("PhalaTEE", self.mock_mode)
            if not self.mock_mode:
                raise LiveModeSafetyError(
                    "PhalaTEE simulated reports require the configured local mock"
                )
        accepted = bool(valid and simulated)
        return AttestationReport(
            provider=provider,
            is_valid=accepted,
            quote_hash=quote_hash,
            timestamp=time.time(),
            error=error if simulated or not valid else "authentic_verifier_unavailable",
            simulated=simulated,
            runtime_classification=self.runtime_policy.runtime_classification,
            evidence_classification="non-authoritative",
            **details,
        )
    
    def verify_sgx_quote(self, quote: bytes) -> AttestationReport:
        """
        Submit an Intel SGX quote to the legacy provider endpoint.

        This SDK does not authenticate the provider's JSON response; returned
        reports cannot be used as live evidence.
        
        Args:
            quote: Raw SGX quote bytes
            
        Returns:
            AttestationReport with verification result
        """
        self._assert_current_runtime()
        quote_hash = hashlib.sha256(quote).hexdigest()

        if self.mock_mode:
            return self._simulate_attestation(quote, TEEProvider.PHALA)
        
        try:
            # This legacy endpoint response is recorded as an unverified claim.
            request_body = {"quote": base64.b64encode(quote).decode()}
            headers = {"Accept-Encoding": "identity"}
            if self.phat_api_key:
                headers["Authorization"] = f"Bearer {self.phat_api_key}"
            self._assert_current_runtime()
            response = self._session.post(
                f"{self.phala_rpc}/prpc/PhactoryAPI.VerifyAttestation",
                json=request_body,
                timeout=self.timeout,
                headers=headers,
                allow_redirects=False,
                stream=True,
            )
            status_code, response_body, response_error = (
                self._consume_diagnostic_response(response)
            )
            if response_error is not None:
                return self._report(
                    TEEProvider.PHALA,
                    quote_hash,
                    valid=False,
                    error=response_error,
                )
            if status_code != 200:
                return self._report(
                    TEEProvider.PHALA, quote_hash, valid=False, error="provider_status"
                )
            try:
                result = json.loads(response_body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
                return self._report(
                    TEEProvider.PHALA,
                    quote_hash,
                    valid=False,
                    error="malformed_response",
                )
            self._assert_current_runtime()
            if not isinstance(result, dict) or type(result.get("valid")) is not bool:
                return self._report(
                    TEEProvider.PHALA,
                    quote_hash,
                    valid=False,
                    error="malformed_response",
                    provider_claim_valid=(
                        result.get("valid")
                        if isinstance(result, dict)
                        and type(result.get("valid")) is bool
                        else None
                    ),
                )
            if result["valid"] and not (
                self._is_hex(result.get("mrenclave"), 64)
                and self._is_hex(result.get("mrsigner"), 64)
                and self._is_hex(result.get("attested_root_eoa"), 40)
                and self._is_hex(result.get("report_data"), 64)
            ):
                return self._report(
                    TEEProvider.PHALA,
                    quote_hash,
                    valid=False,
                    error="malformed_response",
                )
            return self._report(
                TEEProvider.PHALA,
                quote_hash,
                valid=False,
                provider_claim_valid=result["valid"],
                error=(
                    "authentic_verifier_unavailable"
                    if result["valid"]
                    else "provider_claim_false"
                ),
                mrenclave=result.get("mrenclave"),
                mrsigner=result.get("mrsigner"),
                attested_root_eoa=result.get("attested_root_eoa"),
                report_data=result.get("report_data"),
            )
        except _PhalaRuntimeDriftError:
            raise
        except requests.RequestException:
            return self._report(
                TEEProvider.PHALA, quote_hash, valid=False, error="provider_unavailable"
            )
        except (TypeError, ValueError):
            return self._report(
                TEEProvider.PHALA, quote_hash, valid=False, error="malformed_response"
            )
        except Exception:
            return self._report(
                TEEProvider.PHALA, quote_hash, valid=False, error="provider_error"
            )
    
    def verify_nitro_quote(self, attestation_doc: bytes) -> AttestationReport:
        """
        Submit a Nitro attestation document to the legacy provider endpoint.

        This SDK does not authenticate the provider's JSON response; returned
        reports cannot be used as live evidence.
        
        Args:
            attestation_doc: CBOR-encoded attestation document
            
        Returns:
            AttestationReport with verification result
        """
        self._assert_current_runtime()
        quote_hash = hashlib.sha256(attestation_doc).hexdigest()

        if self.mock_mode:
            return self._simulate_attestation(attestation_doc, TEEProvider.MARLIN)
        
        try:
            # Call Marlin Oyster for Nitro verification
            request_body = {"attestation": base64.b64encode(attestation_doc).decode()}
            headers = {"Accept-Encoding": "identity"}
            self._assert_current_runtime()
            response = self._session.post(
                f"{self.marlin_rpc}/verify",
                json=request_body,
                timeout=self.timeout,
                headers=headers,
                allow_redirects=False,
                stream=True,
            )
            status_code, response_body, response_error = (
                self._consume_diagnostic_response(response)
            )
            if response_error is not None:
                return self._report(
                    TEEProvider.MARLIN,
                    quote_hash,
                    valid=False,
                    error=response_error,
                )
            if status_code != 200:
                return self._report(
                    TEEProvider.MARLIN, quote_hash, valid=False, error="provider_status"
                )
            try:
                result = json.loads(response_body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
                return self._report(
                    TEEProvider.MARLIN,
                    quote_hash,
                    valid=False,
                    error="malformed_response",
                )
            self._assert_current_runtime()
            if not isinstance(result, dict) or type(result.get("valid")) is not bool:
                return self._report(
                    TEEProvider.MARLIN,
                    quote_hash,
                    valid=False,
                    error="malformed_response",
                )
            return self._report(
                TEEProvider.MARLIN,
                quote_hash,
                valid=False,
                provider_claim_valid=result["valid"],
                error=(
                    "authentic_verifier_unavailable"
                    if result["valid"]
                    else "provider_claim_false"
                ),
                pcr_values=result.get("pcrs"),
                attested_root_eoa=result.get("attested_root_eoa"),
                report_data=result.get("report_data"),
            )
        except _PhalaRuntimeDriftError:
            raise
        except requests.RequestException:
            return self._report(
                TEEProvider.MARLIN, quote_hash, valid=False, error="provider_unavailable"
            )
        except (TypeError, ValueError):
            return self._report(
                TEEProvider.MARLIN, quote_hash, valid=False, error="malformed_response"
            )
        except Exception:
            return self._report(
                TEEProvider.MARLIN, quote_hash, valid=False, error="provider_error"
            )
    
    def _simulate_attestation(self, data: bytes, provider: TEEProvider) -> AttestationReport:
        """
        Simulate attestation verification for testing/demo.
        
        This fixture is authorized only by the explicit non-live mock setting.
        """
        self._assert_current_runtime()
        self.runtime_policy.authorize_component_mock("PhalaTEE", self.mock_mode)
        if not self.mock_mode:
            raise LiveModeSafetyError("PhalaTEE simulation was not explicitly enabled")
        return self._report(
            provider,
            hashlib.sha256(data).hexdigest(),
            valid=True,
            simulated=True,
            mrenclave=hashlib.sha256(b"simulated_mrenclave").hexdigest(),
            mrsigner=hashlib.sha256(b"simulated_mrsigner").hexdigest(),
        )
    
    def verify_multi_tee(
        self,
        quotes: Dict[TEEProvider, bytes],
        required: int = 2
    ) -> Tuple[bool, List[AttestationReport]]:
        """
        Verify attestations from multiple TEE providers.
        
        The compatibility helper accepts only the documented threshold value 2.
        Its reports are fixtures/provider claims, not critical-operation authority.
        
        Args:
            quotes: Dict mapping provider to attestation quote
            required: Number of valid attestations needed
            
        Returns:
            Tuple of (is_valid, list of reports)
        """
        self._assert_current_runtime()
        if type(required) is not int or required != 2:
            raise ValueError("multi-TEE verification requires exactly two attestations")
        reports = []
        valid_count = 0
        
        for provider, quote in quotes.items():
            self._assert_current_runtime()
            if provider == TEEProvider.PHALA:
                report = self.verify_sgx_quote(quote)
            elif provider == TEEProvider.MARLIN:
                report = self.verify_nitro_quote(quote)
            else:
                if self.mock_mode:
                    report = self._simulate_attestation(quote, provider)
                else:
                    report = self._report(
                        provider,
                        hashlib.sha256(quote).hexdigest(),
                        valid=False,
                        error="unsupported_provider",
                    )
            
            reports.append(report)
            if report.is_valid:
                valid_count += 1
        
        self._assert_current_runtime()
        return (valid_count >= 2, reports)
    
    def call_phat_contract(
        self,
        contract_address: str,
        method: str,
        args: List[Any] = None,
        gas_limit: int = 1000000000
    ) -> PhatContractResult:
        """
        Call a Phat Contract method in a non-live, non-mock configuration.

        There is no authenticated action-admission integration. Live use and
        mock-mode calls are rejected.
        
        Phat Contracts run inside SGX enclaves and can:
        - Make HTTP requests
        - Access randomness
        - Perform private computation
        
        Args:
            contract_address: On-chain contract address
            method: Method name to call
            args: Method arguments
            gas_limit: Maximum gas for execution
            
        Returns:
            PhatContractResult with output or error
        """
        self._assert_current_runtime()
        if self.mock_mode:
            raise LiveModeSafetyError(
                "PhalaTEE contract calls are unavailable in mock mode"
            )
        if self.runtime_policy.is_live:
            raise LiveModeSafetyError(
                "PhalaTEE contract calls require unavailable authenticated action admission"
            )
        start = time.time()
        
        try:
            request_payload = {
                "address": contract_address,
                "payload": {"method": method, "args": args or []},
                "gas_limit": gas_limit,
            }
            headers = (
                {"Authorization": f"Bearer {self.phat_api_key}"}
                if self.phat_api_key
                else {}
            )
            self._assert_current_runtime()
            response = self._session.post(
                f"{self.phala_rpc}/prpc/PinkRuntime.ContractQuery",
                json=request_payload,
                timeout=self.timeout,
                headers=headers,
                allow_redirects=False,
            )
            self._assert_current_runtime()
            
            execution_time = (time.time() - start) * 1000
            
            status_code = response.status_code
            self._assert_current_runtime()
            if status_code == 200:
                result = response.json()
                self._assert_current_runtime()
                if not isinstance(result, dict):
                    return PhatContractResult(
                        success=False,
                        output=None,
                        gas_used=0,
                        execution_time_ms=execution_time,
                        error="malformed_response",
                    )
                return PhatContractResult(
                    success=True,
                    output=result.get("output"),
                    gas_used=result.get("gas_used", 0),
                    execution_time_ms=execution_time,
                    evidence_classification="non-authoritative",
                )
            else:
                return PhatContractResult(
                    success=False,
                    output=None,
                    gas_used=0,
                    execution_time_ms=execution_time,
                    error="provider_status"
                )

        except _PhalaRuntimeDriftError:
            raise
        except Exception:
            return PhatContractResult(
                success=False,
                output=None,
                gas_used=0,
                execution_time_ms=(time.time() - start) * 1000,
                error="provider_error"
            )

    def execute_python_in_enclave(self, script_code: str, args: Dict[str, Any] = None) -> PhatContractResult:
        """
        Compatibility wrapper for a configured Phat Contract method.

        This does not establish enclave confidentiality or action authorization.
        
        Args:
            script_code: Raw Python code string to execute
            args: kwargs to inject into the execution scope
        """
        self._assert_current_runtime()
        if self.runtime_policy.is_live:
            raise LiveModeSafetyError(
                "PhalaTEE enclave execution requires unavailable authenticated action admission"
            )
        # This compatibility path is available only in non-live configurations.
        
        if self.mock_mode:
            script_length = len(script_code)
            self._assert_current_runtime()
            return PhatContractResult(
                success=True,
                output={"status": "simulated", "script_length": script_length},
                gas_used=150000,
                execution_time_ms=0.0,
                simulated=True,
                evidence_classification="non-authoritative",
            )

        contract_address = self.python_runtime
        if not contract_address or contract_address in {"0x0000...", "0x0"}:
            raise LiveModeSafetyError(
                "PhalaTEE enclave execution requires VAMS_PHAT_PYTHON_RUNTIME"
            )
        payload = {
            "script": script_code,
            "ctx": args or {}
        }
        
        # No authenticated action-admission or confidentiality protocol is wired here.
        serialized_payload = json.dumps(payload)
        self._assert_current_runtime()
        result = self.call_phat_contract(contract_address, "run_python", [serialized_payload])
        self._assert_current_runtime()
        return result
    
    def get_phat_contract_info(self, contract_address: str) -> Optional[dict]:
        """
        Get information about a deployed Phat Contract.
        
        Args:
            contract_address: Contract address
            
        Returns:
            Contract metadata or None
        """
        self._assert_current_runtime()
        url = f"{self.phala_rpc}/contracts/{contract_address}"
        self._assert_current_runtime()
        try:
            response = self._session.get(
                url,
                timeout=self.timeout
            )
            self._assert_current_runtime()
            
            status_code = response.status_code
            self._assert_current_runtime()
            if status_code == 200:
                result = response.json()
                self._assert_current_runtime()
                return result
            return None
            
        except _PhalaRuntimeDriftError:
            raise
        except Exception:
            return None
    
    def check_health(self) -> dict:
        """Report status-only HTTP reachability, not TEE health or proof."""
        return _status_only_health_probe(
            "phala",
            "Intel SGX",
            lambda: self._session.get(
                "https://phala.network",
                timeout=self.timeout // 2,
                stream=True,
                allow_redirects=False,
            ),
            lambda status: 200 <= status < 300,
            network=self.network,
            runtime_check=self._assert_current_runtime,
        )


class MarlinOyster:
    """
    Marlin Oyster SDK for AWS Nitro Enclave verification.
    
    Complements Phala for multi-TEE attestation.
    """
    
    def __init__(self, network: str = "testnet", timeout: int = 30):
        self.network = network
        self.timeout = timeout
        self.endpoint = MARLIN_ENDPOINTS.get(network, MARLIN_ENDPOINTS["testnet"])
        self._session = requests.Session()
    
    def check_health(self) -> dict:
        """Report status-only HTTP reachability, not Nitro health or proof."""
        return _status_only_health_probe(
            "marlin",
            "AWS Nitro",
            lambda: self._session.get(
                "https://www.marlin.org",
                timeout=self.timeout // 2,
                stream=True,
                allow_redirects=False,
            ),
            lambda status: 200 <= status < 300,
            network=self.network,
        )


class AutomataMultiProver:
    """
    Automata Multi-Prover SDK.
    
    Provides protocol-level attestation combining multiple proof types.
    """
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.endpoint = "https://1rpc.io/ata"
        self._session = requests.Session()
    
    def check_health(self) -> dict:
        """Report 1RPC HTTP reachability, not multi-prover health or proof."""
        return _status_only_health_probe(
            "automata",
            "Multi-Prover",
            lambda: self._session.post(
                self.endpoint,
                json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
                timeout=self.timeout // 2,
                stream=True,
                allow_redirects=False,
            ),
            lambda status: status == 200,
        )


def check_all_tee_health() -> Dict[str, dict]:
    """Check only HTTP reachability; results are non-authoritative observations."""
    return {
        "phala": PhalaTEE().check_health(),
        "marlin": MarlinOyster().check_health(),
        "automata": AutomataMultiProver().check_health()
    }


if __name__ == "__main__":
    print("VAMS Provider HTTP Reachability (Unverified)")
    print("=" * 40)
    
    # Check all TEE providers
    health = check_all_tee_health()
    
    for provider, status in health.items():
        marked = (
            status.get("verification_scope") == "http_reachability"
            and status.get("evidence_classification") == "non-authoritative"
        )
        symbol = "✓" if marked and status.get("status") == "healthy" else "✗"
        tech = status.get("technology", "N/A")
        state = "HTTP reachable" if symbol == "✓" else "unknown/unverified"
        print(f"[{symbol}] {provider.upper():10} | target: {tech:12} | {state}; non-authoritative")
