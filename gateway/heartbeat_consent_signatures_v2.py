"""Proposed body-key signature checking, with no enrollment or authority grant.

A successful result proves one signature for one declared key role and canonical
record. The caller must independently authenticate the source/current record,
actual timelock operation, post-ETA challenge, policy, freshness, nonce and consent
consumption. This module has no store, issuer, network client or live route.
M2-key possession, mTLS and governance remain separate requirements.
"""
from __future__ import annotations

from .heartbeat_consent_v2 import (
    HeartbeatConsentBaseIntentV2, HeartbeatConsentWitnessV2,
    MODE_ROTATE_NORMAL, ROLE_MASK_ROTATE_NORMAL, ROLE_NEW_KEY, ROLE_OLD_KEY,
)
from .heartbeat_principal_v1 import HeartbeatPrincipalV1
from neuron.secp256k1 import verify_message

SIGNATURE_DOMAIN = b"VAMS:GATEWAY:HEARTBEAT-CONSENT-SIGNATURE:v2\x00"
ALGORITHM_RAW_SECP256K1_SHA256_LOW_S = 1


def body_key_statement(witness_raw: bytes, role: int) -> bytes:
    """Return proposed role-separated signed bytes; authenticate no native facts.

    SHA-256 is applied once by the existing ECDSA/SHA-256 verifier to these
    bytes. The inner witness digest already commits to its own distinct domain,
    complete base intent, operation/ETA/challenge/times, mode and required roles.
    Distinct role bytes prevent reusing one signature as both required roles.
    """
    if type(witness_raw) is not bytes or type(role) is not int:
        raise ValueError("invalid consent signature data")
    witness = HeartbeatConsentWitnessV2.from_bytes(witness_raw)
    if role not in (ROLE_OLD_KEY, ROLE_NEW_KEY) or not witness.required_role_mask & role:
        raise ValueError("signature role is not required by this mode")
    return SIGNATURE_DOMAIN + bytes((ALGORITHM_RAW_SECP256K1_SHA256_LOW_S, role)) + witness.digest


def verify_body_key_signature(
    *, base_raw: bytes, witness_raw: bytes, principal_raw: bytes,
    role: int, signature: bytes,
) -> bool:
    """Verify one bound body-key signature, never registry/current authority.

    In normal rotation the consumer needs independently successful OLD and NEW
    statements. Enrollment and recovery admit only NEW here; this function does
    not prove that recovery passed its mandatory 48-hour governance timelock.
    Record presence/currentness and key-distinctness policy are not inferred.
    """
    if (
        type(base_raw) is not bytes or type(witness_raw) is not bytes
        or type(principal_raw) is not bytes or type(signature) is not bytes
        or len(signature) != 64 or type(role) is not int
    ):
        return False
    try:
        base = HeartbeatConsentBaseIntentV2.from_bytes(base_raw)
        witness = HeartbeatConsentWitnessV2.from_bytes(witness_raw)
        record = HeartbeatPrincipalV1.from_bytes(principal_raw)
        if not witness.matches_base_data(base) or record.principal_id != base.principal_id:
            return False
        if role == ROLE_NEW_KEY:
            if (
                record.digest != base.proposed_record_digest
                or record.principal_generation != base.proposed_generation
                or record.policy_root != base.policy_root
                or record.policy_version != base.policy_version
                or record.authority_epoch != base.authority_epoch
            ):
                return False
        elif role == ROLE_OLD_KEY:
            if (
                base.mode != MODE_ROTATE_NORMAL
                or record.digest != base.expected_record_digest
                or record.principal_generation != base.expected_generation
            ):
                return False
        else:
            return False
        statement = body_key_statement(witness_raw, role)
        return verify_message(record.body_public_key, statement, signature)
    except (TypeError, ValueError, OverflowError):
        return False

def verify_normal_rotation_signature_pair(
    *, base_raw: bytes, witness_raw: bytes,
    old_principal_raw: bytes, proposed_principal_raw: bytes,
    old_signature: bytes, new_signature: bytes,
) -> bool:
    """Check both normal-rotation body-key roles over the same exact intent/witness.

    True means only that the supplied OLD and NEW signatures verify against the
    supplied canonical records and identical base/witness bytes. It does not
    authenticate current authority, a Timelock operation, challenge, clock,
    policy, replay state, or authorize any mutation. Key-distinctness policy is
    intentionally not inferred.
    """
    if (
        type(base_raw) is not bytes or type(witness_raw) is not bytes
        or type(old_principal_raw) is not bytes or type(proposed_principal_raw) is not bytes
        or type(old_signature) is not bytes or type(new_signature) is not bytes
        or len(old_signature) != 64 or len(new_signature) != 64
    ):
        return False
    try:
        base = HeartbeatConsentBaseIntentV2.from_bytes(base_raw)
        witness = HeartbeatConsentWitnessV2.from_bytes(witness_raw)
        if (
            base.mode != MODE_ROTATE_NORMAL
            or witness.required_role_mask != ROLE_MASK_ROTATE_NORMAL
            or not witness.matches_base_data(base)
        ):
            return False
    except (TypeError, ValueError, OverflowError):
        return False

    return (
        verify_body_key_signature(
            base_raw=base_raw, witness_raw=witness_raw, principal_raw=old_principal_raw,
            role=ROLE_OLD_KEY, signature=old_signature,
        )
        and verify_body_key_signature(
            base_raw=base_raw, witness_raw=witness_raw, principal_raw=proposed_principal_raw,
            role=ROLE_NEW_KEY, signature=new_signature,
        )
    )

