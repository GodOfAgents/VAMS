"""Fail-closed authorization policy for VDSO canary intents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .models import ExecutionTier, SignatureSuite, UnsignedIntent


SignatureVerifier = Callable[[bytes, bytes, bytes], bool]


class AuthorizationError(ValueError):
    """Raised when an authorization envelope is missing or invalid."""


@dataclass(frozen=True)
class AuthorizationEnvelope:
    suite: SignatureSuite
    secp256k1_public_key: bytes
    secp256k1_signature: bytes
    ml_dsa_65_public_key: bytes = b""
    ml_dsa_65_signature: bytes = b""


class AuthorizationVerifier:
    """Verify classic and hybrid suites through audited injected backends.

    No mock verifier or shape-only fallback exists.  Tier 2 cannot pass unless
    both real verifier callbacks are configured and both signatures verify.
    """

    def __init__(
        self,
        *,
        secp256k1_verify: Optional[SignatureVerifier],
        ml_dsa_65_verify: Optional[SignatureVerifier] = None,
    ) -> None:
        self._secp256k1_verify = secp256k1_verify
        self._ml_dsa_65_verify = ml_dsa_65_verify

    def verify(self, intent: UnsignedIntent, envelope: AuthorizationEnvelope) -> None:
        try:
            intent.validate_execution_policy()
        except ValueError as exc:
            raise AuthorizationError(
                "signed intent violates mandatory host/access authorization policy"
            ) from exc
        if envelope.suite != intent.signature_suite:
            raise AuthorizationError("authorization suite does not match the signed intent")
        if self._secp256k1_verify is None:
            raise AuthorizationError("secp256k1 verifier is not configured")
        message = intent.intent_id
        if not self._secp256k1_verify(
            envelope.secp256k1_public_key, message, envelope.secp256k1_signature
        ):
            raise AuthorizationError("invalid secp256k1 authorization")

        tier_two = intent.execution_tier == ExecutionTier.IMMEDIATE_DUAL_VALIDITY
        hybrid = envelope.suite == SignatureSuite.SECP256K1_AND_ML_DSA_65
        if tier_two and not hybrid:
            raise AuthorizationError("Tier 2 authorization downgrade rejected")
        if hybrid:
            if self._ml_dsa_65_verify is None:
                raise AuthorizationError("ML-DSA-65 verifier is not configured")
            if not self._ml_dsa_65_verify(
                envelope.ml_dsa_65_public_key, message, envelope.ml_dsa_65_signature
            ):
                raise AuthorizationError("invalid ML-DSA-65 authorization")
