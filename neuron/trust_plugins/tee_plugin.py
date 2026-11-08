"""
VAMS Trust Plugin — TEE Provider Compatibility
================================================
Provides local simulated proof fixtures. Live Phala proof generation is disabled
until an authenticated verifier backend is integrated.
"""

import hashlib
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, Mapping
from web3 import Web3
from eth_abi import encode

from neuron.runtime_safety import (
    ImmutableRuntimeConfiguration,
    LiveModeSafetyError,
    RuntimeConfigurationError,
    RuntimePolicy,
    load_runtime_policy,
    resolve_component_mock_mode,
)
from neuron.sdk.phala_tee import PhalaTEE


class _TEEPluginRuntimeDriftError(RuntimeConfigurationError):
    """Bounded rejection when the ambient policy changes during proof work."""


def _ambient_policy_for(source, supplied):
    ambient = load_runtime_policy(os.environ)
    configured = load_runtime_policy(source)
    if configured != ambient or (supplied is not None and supplied != ambient):
        raise RuntimeConfigurationError(
            "Conflicting runtime policy for TEEProofPlugin; ambient runtime configuration is authoritative"
        )
    return ambient


@dataclass
class ProofResult:
    """Result of proof generation or verification."""
    valid: bool
    proof_type: bytes  # bytes32 identifier
    proof_data: bytes  # ABI-encoded proof
    trust_weight: int  # basis points (0-10000)
    metadata: Optional[Dict[str, Any]] = None


class BaseProofPlugin(ABC):
    """Abstract base class for all VAMS proof plugins."""

    @abstractmethod
    def proof_type(self) -> bytes:
        """Return the keccak256 proof type identifier."""
        pass

    @abstractmethod
    def name(self) -> str:
        """Return human-readable plugin name."""
        pass

    @abstractmethod
    def trust_weight(self) -> int:
        """Return trust weight in basis points (0-10000)."""
        pass

    @abstractmethod
    def generate_proof(
        self,
        service_hash: bytes,
        delivery_hash: bytes,
        **kwargs,
    ) -> ProofResult:
        """Generate a proof for the given service/delivery pair."""
        pass

    @abstractmethod
    def verify_proof(
        self,
        service_hash: bytes,
        delivery_hash: bytes,
        proof_data: bytes,
    ) -> bool:
        """Verify a proof locally (before on-chain submission)."""
        pass


class TEEProofPlugin(BaseProofPlugin, ImmutableRuntimeConfiguration):
    """Local simulated fixture plugin; provider responses are not live proofs."""

    PROOF_TYPE_ID = Web3.keccak(text="PHALA_EXECUTION")
    _immutable_runtime_fields = frozenset({"runtime_policy", "mock_mode"})

    def __init__(
        self,
        tee_provider: str = "phala",
        *,
        mock_mode: Optional[bool] = None,
        runtime_policy: Optional[RuntimePolicy] = None,
        environ: Optional[Mapping[str, str]] = None,
        phala_client: Optional[PhalaTEE] = None,
    ):
        source = os.environ if environ is None else environ
        ambient_policy = _ambient_policy_for(source, runtime_policy)
        self.runtime_policy = ambient_policy
        ambient_mock = resolve_component_mock_mode(
            "TEEProofPlugin",
            "PHALA_MOCK_MODE",
            None,
            policy=self.runtime_policy,
            environ=os.environ,
        )
        if mock_mode is not None and not isinstance(mock_mode, bool):
            raise RuntimeConfigurationError(
                "Malformed mock selection for TEEProofPlugin; use a boolean"
            )
        if mock_mode is not None and mock_mode != ambient_mock:
            raise RuntimeConfigurationError(
                "Conflicting mock selection for TEEProofPlugin; ambient configuration is authoritative"
            )
        self.mock_mode = ambient_mock
        self.tee_provider = tee_provider
        self.phala_client = phala_client or PhalaTEE(
            mock_mode=self.mock_mode,
            runtime_policy=self.runtime_policy,
            environ=source,
        )
        self._freeze_runtime_configuration()

    def _assert_current_runtime(self) -> None:
        try:
            current = load_runtime_policy(os.environ)
            if current != self.runtime_policy:
                raise _TEEPluginRuntimeDriftError(
                    "TEEProofPlugin runtime configuration changed during the operation"
                )
            current_mock = resolve_component_mock_mode(
                "TEEProofPlugin",
                "PHALA_MOCK_MODE",
                self.mock_mode,
                policy=current,
                environ=os.environ,
            )
            if current_mock != self.mock_mode:
                raise _TEEPluginRuntimeDriftError(
                    "TEEProofPlugin runtime configuration changed during the operation"
                )
        except _TEEPluginRuntimeDriftError:
            raise
        except LiveModeSafetyError:
            raise _TEEPluginRuntimeDriftError(
                "TEEProofPlugin runtime configuration changed during the operation"
            ) from None

    def proof_type(self) -> bytes:
        return self.PROOF_TYPE_ID

    def name(self) -> str:
        return "Simulated TEE Provider Fixture"

    def trust_weight(self) -> int:
        return 2500  # 25%

    def generate_proof(
        self,
        service_hash: bytes,
        delivery_hash: bytes,
        **kwargs,
    ) -> ProofResult:
        """Generate a local fixture or reject unqualified provider evidence."""
        self._assert_current_runtime()
        if not self.mock_mode:
            return ProofResult(
                valid=False,
                proof_type=self.PROOF_TYPE_ID,
                proof_data=b"",
                trust_weight=self.trust_weight(),
                metadata={
                    "provider": self.tee_provider,
                    "simulated": False,
                    "evidence_classification": "rejected",
                    "root_binding": "unverified",
                    "reason": "authentic_verifier_unavailable",
                },
            )

        root_address = kwargs.get("root_address")
        if (
            not isinstance(root_address, bytes)
            or len(root_address) != 20
            or root_address == b"\x00" * 20
        ):
            raise ValueError("TEE attestations require a non-zero 20-byte root EOA")
        session_key_address = kwargs.get("session_key_address")
        if session_key_address is not None and session_key_address == root_address:
            raise ValueError("root EOA must not be supplied as a session key")

        binding = hashlib.sha3_256(
            service_hash + delivery_hash + root_address
        ).digest()
        mrenclave = kwargs.get("mrenclave", b"\x5f\x9c" + b"\x00" * 30)
        mrsigner = kwargs.get("mrsigner", b"\xab\xc0" + b"\x00" * 30)
        sgx_quote = (
            b"\x03\x00"
            + mrenclave
            + mrsigner
            + binding
            + b"\x00" * 64
        )
        evidence_classification = "non-authoritative"

        self._assert_current_runtime()
        proof_data = self._abi_encode_attestation(
            sgx_quote=sgx_quote,
            mrenclave=mrenclave,
            mrsigner=mrsigner,
            attested_agent=root_address,
        )

        self._assert_current_runtime()
        return ProofResult(
            valid=True,
            proof_type=self.PROOF_TYPE_ID,
            proof_data=proof_data,
            trust_weight=self.trust_weight(),
            metadata={
                "provider": self.tee_provider,
                "simulated": True,
                "evidence_classification": evidence_classification,
                "runtime_classification": self.runtime_policy.runtime_classification,
                "root_binding": "simulated",
            },
        )

    def verify_proof(
        self,
        service_hash: bytes,
        delivery_hash: bytes,
        proof_data: bytes,
    ) -> bool:
        """Verify a local simulated fixture; live verification is unavailable."""
        self._assert_current_runtime()
        if not self.mock_mode:
            return False
        proof_length = len(proof_data)
        self._assert_current_runtime()
        return proof_length > 64

    def _abi_encode_attestation(
        self,
        sgx_quote: bytes,
        mrenclave: bytes,
        mrsigner: bytes,
        attested_agent: bytes,
    ) -> bytes:
        """Encode a local simulated fixture in the legacy ABI layout."""
        self._assert_current_runtime()
        if not self.mock_mode:
            raise LiveModeSafetyError(
                "TEEProofPlugin proof encoding is unavailable without authenticated evidence"
            )
        # Using eth_abi for proper ABI encoding
        encoded = encode(['bytes', 'bytes32', 'bytes32', 'address'],
                         [sgx_quote, mrenclave, mrsigner, attested_agent])
        self._assert_current_runtime()
        return encoded
