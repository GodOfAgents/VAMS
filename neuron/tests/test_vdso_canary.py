import os
import asyncio
import hashlib
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from neuron.da.adapters.base import DAAdapter
from neuron.da.adapters.celestia_adapter import CelestiaDAAdapter
from neuron.da.adapters.near_adapter import NearDAAdapter
from neuron.da.models import DAProtocol, DAReceipt
from neuron.vdso.auth import (
    AuthorizationEnvelope,
    AuthorizationError,
    AuthorizationVerifier,
)
from neuron.vdso.codec import CanonicalEncodingError, decode, encode
from neuron.vdso.keccak import keccak_256
from neuron.vdso.models import (
    AccessMode,
    AdapterProfile,
    CapabilityRequirements,
    DomainAuthorityBinding,
    ExecutionTier,
    FailureCode,
    HostAuthority,
    ObjectAccess,
    SettlementMetadata,
    SignatureSuite,
    StateObjectHeader,
    TransitionReceipt,
    UnsignedIntent,
)
from neuron.vdso.routing import (
    NoEligibleAdapterError,
    derive_capability_requirements,
    select_adapter,
    select_intent_adapters,
)
from neuron.vdso.da import (
    EncryptedSidecarPublisher,
    RetrievalBoundLiveEvidence,
    VDSODAError,
)
from neuron.vdso.service import (
    InMemoryNonceStore,
    VDSOCanaryService,
    VDSOMode,
    VDSOServiceError,
)
from neuron.vdso.sidecar import (
    EncryptedWitnessSidecar,
    RecipientEnvelope,
    SidecarCryptoUnavailable,
    encrypt_sidecar,
    sidecar_content_hash,
)
from neuron.vdso.workflow import (
    VDSOOrchestrator,
    VDSOWorkflowDependencies,
    idempotency_key,
)

try:
    from nacl.bindings import crypto_aead_xchacha20poly1305_ietf_decrypt

    HAS_NACL = True
except ImportError:
    HAS_NACL = False


def b32(value: int) -> bytes:
    return value.to_bytes(32, "big")


def make_intent(
    *,
    tier: ExecutionTier = ExecutionTier.NATIVE_NON_ECONOMIC,
    suite: SignatureSuite = SignatureSuite.SECP256K1,
    valid_until_height: int = 2_000,
    max_settlement_cost=None,
) -> UnsignedIntent:
    settlement_cost = (
        5_000
        if max_settlement_cost is None
        and tier == ExecutionTier.IMMEDIATE_DUAL_VALIDITY
        else (0 if max_settlement_cost is None else max_settlement_cost)
    )
    return UnsignedIntent(
        schema_version=1,
        actor_root=b32(1),
        binding=DomainAuthorityBinding(b32(8), HostAuthority.POLYGON, 3),
        nonce=7,
        valid_until_height=valid_until_height,
        program_id=b32(2),
        workflow_definition_hash=b32(3),
        accesses=(ObjectAccess(b32(9), AccessMode.READ, 1),),
        input_commitment=b32(4),
        expected_output_commitment=b32(5),
        evidence_root=b32(6),
        sidecar_root=b32(7),
        signature_suite=suite,
        execution_tier=tier,
        max_execution_units=100_000,
        max_settlement_cost=settlement_cost,
    )


def make_adapter(
    adapter_id: int,
    *,
    host: HostAuthority = HostAuthority.POLYGON,
    cost: int = 10,
    latency: int = 100,
    mock_mode: bool = False,
    stub: bool = False,
    quarantined: bool = False,
) -> AdapterProfile:
    return AdapterProfile(
        adapter_id=b32(adapter_id),
        host_authority=host,
        access_modes=(AccessMode.READ, AccessMode.ACCUMULATE, AccessMode.RESERVE),
        maximum_tier=ExecutionTier.IMMEDIATE_DUAL_VALIDITY,
        privacy_class=2,
        estimated_cost=cost,
        estimated_latency_ms=latency,
        da_protocols=("celestia", "near"),
        active=True,
        quarantined=quarantined,
        mock_mode=mock_mode,
        stub=stub,
        expires_at=10_000,
        conformance_root=b32(50),
    )


def make_encrypted_sidecar(
    *,
    nonce: bytes = b"n" * 24,
    ciphertext: bytes = b"ciphertext-only",
    envelopes=None,
) -> EncryptedWitnessSidecar:
    recipient_envelopes = envelopes or (
        RecipientEnvelope(b32(4), b"enc", b"wrapped"),
    )
    content_hash = sidecar_content_hash(
        schema_version=1,
        nonce=nonce,
        ciphertext=ciphertext,
        plaintext_root=b32(1),
        policy_hash=b32(3),
        recipient_envelopes=recipient_envelopes,
    )
    return EncryptedWitnessSidecar(
        schema_version=1,
        nonce=nonce,
        ciphertext=ciphertext,
        plaintext_root=b32(1),
        content_hash=content_hash,
        policy_hash=b32(3),
        recipient_envelopes=recipient_envelopes,
    )


class _DurableNonceStore(InMemoryNonceStore):
    """Atomic test double standing in for a durable shared implementation."""

    durable = True


async def _independent_accept(_receipt, _payload):
    return True


async def _independent_missing_blob(_receipt):
    return None


def unavailable_live_evidence():
    return RetrievalBoundLiveEvidence(
        receipt_verifier=_independent_accept,
        blob_retriever=_independent_missing_blob,
    )


class KeccakAndCodecTests(unittest.TestCase):
    def test_keccak_known_answer_empty(self):
        self.assertEqual(
            keccak_256(b"").hex(),
            "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470",
        )

    def test_keccak_known_answer_abc(self):
        self.assertEqual(
            keccak_256(b"abc").hex(),
            "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45",
        )

    def test_cbor_rejects_every_type_outside_vir_core_subset(self):
        for value in ({"unordered": "map"}, 0.1, -1, "text", True, None):
            with self.subTest(value=value), self.assertRaises(CanonicalEncodingError):
                encode(value)

    def test_cbor_uses_minimal_integer_encoding(self):
        self.assertEqual(encode(23), b"\x17")
        self.assertEqual(encode(24), b"\x18\x18")
        self.assertEqual(decode(encode((24, b"value"))), (24, b"value"))
        with self.assertRaisesRegex(CanonicalEncodingError, "non-minimal"):
            decode(b"\x18\x17")
        with self.assertRaisesRegex(CanonicalEncodingError, "trailing"):
            decode(b"\x17\x00")

    def test_rust_golden_vector_matches_byte_for_byte(self):
        vector_path = Path(__file__).parents[2] / "vams-vm" / "vectors" / "vir-core-v1.json"
        vector = json.loads(vector_path.read_text(encoding="utf-8"))
        intent = UnsignedIntent(
            schema_version=1,
            actor_root=bytes.fromhex("31" * 32),
            binding=DomainAuthorityBinding(
                bytes.fromhex("30" * 32), HostAuthority.CARDANO, 4
            ),
            nonce=42,
            valid_until_height=999,
            program_id=bytes.fromhex(vector["program_id"]),
            workflow_definition_hash=bytes.fromhex("60" * 32),
            accesses=(
                ObjectAccess(bytes.fromhex("20" * 32), AccessMode.READ, 5),
                ObjectAccess(bytes.fromhex("21" * 32), AccessMode.ACCUMULATE, 7),
            ),
            input_commitment=bytes.fromhex(
                "902188534cc8e8be436828d1329c194c793d2f591921e6f0d42c48379bfb14fc"
            ),
            expected_output_commitment=bytes.fromhex(
                "507c1c9e5414952f2017497a5a6da6cf639c820712d2266d2978ae5a200a3dcf"
            ),
            evidence_root=bytes.fromhex("61" * 32),
            sidecar_root=bytes.fromhex("62" * 32),
            signature_suite=SignatureSuite.SECP256K1_AND_ML_DSA_65,
            execution_tier=ExecutionTier.IMMEDIATE_DUAL_VALIDITY,
            max_execution_units=100,
            max_settlement_cost=5_000,
        )
        self.assertEqual(intent.canonical_bytes().hex(), vector["unsigned_intent_cbor"])
        self.assertEqual(intent.intent_id.hex(), vector["intent_id"])
        self.assertEqual(intent.workflow_id.hex(), vector["workflow_id"])
        header = StateObjectHeader(
            1,
            bytes.fromhex("20" * 32),
            DomainAuthorityBinding(bytes.fromhex("30" * 32), HostAuthority.CARDANO, 4),
            5,
            bytes.fromhex("40" * 32),
        )
        self.assertEqual(header.canonical_bytes().hex(), vector["state_object_header_cbor"])
        settlement = SettlementMetadata(
            schema_version=1,
            receipt_hash=bytes.fromhex(vector["semantic_receipt_hash"]),
            binding=DomainAuthorityBinding(
                bytes.fromhex("30" * 32), HostAuthority.CARDANO, 4
            ),
            source_chain_reference=bytes.fromhex("70" * 32),
            source_transaction_hash=bytes.fromhex("71" * 32),
            settled_at_height=123_456,
            bridge_proof_hash=bytes.fromhex("72" * 32),
            payload_hash=bytes.fromhex("73" * 32),
        )
        self.assertEqual(
            settlement.canonical_bytes().hex(),
            vector["settlement_metadata_cbor"],
        )
        self.assertEqual(
            SettlementMetadata.from_canonical_bytes(settlement.canonical_bytes()),
            settlement,
        )
        self.assertEqual(vector["invalid_settlement_metadata"], 44)

    def test_failure_code_43_matches_rust_receipt_representation(self):
        binding = DomainAuthorityBinding(b32(3), HostAuthority.POLYGON, 1)
        receipt = TransitionReceipt(
            schema_version=1,
            intent_id=b32(1),
            program_id=b32(2),
            binding=binding,
            pre_state_root=b32(4),
            post_state_root=b32(5),
            output_commitment=b32(6),
            gas_used=10,
            failure_code=FailureCode.UNSUPPORTED_POLICY_COMMITMENT,
            instruction_index=7,
        )
        self.assertEqual(int(FailureCode.UNSUPPORTED_POLICY_COMMITMENT), 43)
        self.assertEqual(
            receipt.canonical_bytes(),
            encode(
                (
                    1,
                    b32(1),
                    b32(2),
                    binding.canonical_value(),
                    b32(4),
                    b32(5),
                    b32(6),
                    10,
                    (1, 43, 7),
                )
            ),
        )

    def test_settlement_metadata_enforces_inv_10_separation(self):
        binding = DomainAuthorityBinding(b32(3), HostAuthority.POLYGON, 1)
        local = SettlementMetadata(
            schema_version=1,
            receipt_hash=b32(1),
            binding=binding,
            source_chain_reference=b"\x00" * 32,
            source_transaction_hash=b"\x00" * 32,
            settled_at_height=0,
            bridge_proof_hash=b"\x00" * 32,
            payload_hash=b"\x00" * 32,
        )
        self.assertTrue(local.canonical_bytes())
        self.assertEqual(
            SettlementMetadata.from_canonical_bytes(local.canonical_bytes()),
            local,
        )
        with self.assertRaisesRegex(ValueError, "distinct nonzero"):
            SettlementMetadata(
                schema_version=1,
                receipt_hash=b32(1),
                binding=binding,
                source_chain_reference=b32(2),
                source_transaction_hash=b32(3),
                settled_at_height=9,
                bridge_proof_hash=b32(4),
                payload_hash=b32(4),
            )
        with self.assertRaisesRegex(ValueError, "all-zero"):
            SettlementMetadata(
                schema_version=1,
                receipt_hash=b32(1),
                binding=binding,
                source_chain_reference=b"\x00" * 32,
                source_transaction_hash=b32(3),
                settled_at_height=0,
                bridge_proof_hash=b"\x00" * 32,
                payload_hash=b"\x00" * 32,
            )


class IntentAndAuthorizationTests(unittest.TestCase):
    def test_intent_id_is_deterministic_and_32_bytes(self):
        intent = make_intent()
        self.assertEqual(intent.intent_id, make_intent().intent_id)
        self.assertEqual(len(intent.intent_id), 32)
        self.assertEqual(len(intent.workflow_id), 32)

    def test_unsorted_accesses_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "sorted"):
            UnsignedIntent(
                **{
                    **make_intent().__dict__,
                    "accesses": (
                        ObjectAccess(b32(10), AccessMode.READ, 1),
                        ObjectAccess(b32(9), AccessMode.READ, 1),
                    ),
                }
            )

    def test_tier_two_requires_hybrid_suite(self):
        with self.assertRaisesRegex(ValueError, "hybrid"):
            make_intent(tier=ExecutionTier.IMMEDIATE_DUAL_VALIDITY)

    def test_hybrid_authorization_requires_both_real_verifiers(self):
        intent = make_intent(
            tier=ExecutionTier.IMMEDIATE_DUAL_VALIDITY,
            suite=SignatureSuite.SECP256K1_AND_ML_DSA_65,
        )
        envelope = AuthorizationEnvelope(
            suite=SignatureSuite.SECP256K1_AND_ML_DSA_65,
            secp256k1_public_key=b"classic-key",
            secp256k1_signature=b"classic-signature",
            ml_dsa_65_public_key=b"pq-key",
            ml_dsa_65_signature=b"pq-signature",
        )
        verifier = AuthorizationVerifier(
            secp256k1_verify=lambda _key, _message, _signature: True,
            ml_dsa_65_verify=None,
        )
        with self.assertRaisesRegex(AuthorizationError, "ML-DSA-65"):
            verifier.verify(intent, envelope)

    def test_authorization_rechecks_mutation_tier_policy(self):
        intent = make_intent()
        object.__setattr__(intent.accesses[0], "mode", AccessMode.ACCUMULATE)
        envelope = AuthorizationEnvelope(
            suite=SignatureSuite.SECP256K1,
            secp256k1_public_key=b"classic-key",
            secp256k1_signature=b"classic-signature",
        )
        verifier = AuthorizationVerifier(
            secp256k1_verify=lambda _key, _message, _signature: True,
        )
        with self.assertRaisesRegex(AuthorizationError, "host/access"):
            verifier.verify(intent, envelope)
        read_intent = make_intent(tier=ExecutionTier.BATCHED_VALIDITY)
        object.__setattr__(read_intent, "max_settlement_cost", 1)
        with self.assertRaisesRegex(AuthorizationError, "host/access"):
            verifier.verify(read_intent, envelope)

    def test_reserve_requires_fence_and_non_reserve_rejects_one(self):
        with self.assertRaisesRegex(ValueError, "requires"):
            ObjectAccess(b32(9), AccessMode.RESERVE, 1)
        with self.assertRaisesRegex(ValueError, "only"):
            ObjectAccess(b32(9), AccessMode.READ, 1, 7)

    def test_zero_execution_limit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "nonzero"):
            UnsignedIntent(**{**make_intent().__dict__, "max_execution_units": 0})

    def test_nonzero_settlement_cost_requires_tier_two_even_for_read(self):
        with self.assertRaisesRegex(ValueError, "max_settlement_cost"):
            make_intent(
                tier=ExecutionTier.BATCHED_VALIDITY,
                max_settlement_cost=1,
            )
        accepted = make_intent(
            tier=ExecutionTier.BATCHED_VALIDITY,
            max_settlement_cost=0,
        )
        self.assertEqual(
            UnsignedIntent.from_canonical_bytes(accepted.canonical_bytes()),
            accepted,
        )
        raw = list(decode(accepted.canonical_bytes()))
        raw[15] = 1
        with self.assertRaisesRegex(ValueError, "invalid canonical unsigned intent"):
            UnsignedIntent.from_canonical_bytes(encode(tuple(raw)))

    def test_polygon_state_mutations_cannot_downgrade_below_tier_two_hybrid(self):
        accesses = (
            ObjectAccess(b32(9), AccessMode.CONSUME, 1),
            ObjectAccess(b32(9), AccessMode.RESERVE, 1, 11),
            ObjectAccess(b32(9), AccessMode.ACCUMULATE, 1),
        )
        for access in accesses:
            with self.subTest(mode=access.mode), self.assertRaisesRegex(
                ValueError, "Tier 2 hybrid"
            ):
                UnsignedIntent(
                    **{
                        **make_intent().__dict__,
                        "accesses": (access,),
                    }
                )

    def test_cardano_rejects_consume_and_reserve_at_model_boundary(self):
        cardano_binding = DomainAuthorityBinding(
            b32(8),
            HostAuthority.CARDANO,
            3,
        )
        for access in (
            ObjectAccess(b32(9), AccessMode.CONSUME, 1),
            ObjectAccess(b32(9), AccessMode.RESERVE, 1, 11),
        ):
            with self.subTest(mode=access.mode), self.assertRaisesRegex(
                ValueError, "Cardano authority"
            ):
                UnsignedIntent(
                    **{
                        **make_intent(
                            tier=ExecutionTier.IMMEDIATE_DUAL_VALIDITY,
                            suite=SignatureSuite.SECP256K1_AND_ML_DSA_65,
                        ).__dict__,
                        "binding": cardano_binding,
                        "accesses": (access,),
                    }
                )


class CapabilityRouterTests(unittest.TestCase):
    def test_router_hard_filters_mock_stub_and_quarantine(self):
        requirements = CapabilityRequirements(
            host_authority=HostAuthority.POLYGON,
            access_mode=AccessMode.READ,
            execution_tier=ExecutionTier.BATCHED_VALIDITY,
            minimum_privacy_class=1,
            maximum_cost=100,
            required_da=("celestia",),
        )
        selected = select_adapter(
            (
                make_adapter(1, mock_mode=True, cost=1),
                make_adapter(2, stub=True, cost=2),
                make_adapter(3, quarantined=True, cost=3),
                make_adapter(4, cost=20),
            ),
            requirements,
            now=1_000,
        )
        self.assertEqual(selected.adapter_id, b32(4))

    def test_router_has_deterministic_adapter_id_tiebreaker(self):
        requirements = CapabilityRequirements(
            host_authority=HostAuthority.POLYGON,
            access_mode=AccessMode.READ,
            execution_tier=ExecutionTier.NATIVE_NON_ECONOMIC,
            minimum_privacy_class=1,
            maximum_cost=100,
        )
        selected = select_adapter(
            (make_adapter(2), make_adapter(1)), requirements, now=1_000
        )
        self.assertEqual(selected.adapter_id, b32(1))

    def test_cardano_consume_and_reserve_are_disabled(self):
        for access_mode in (AccessMode.CONSUME, AccessMode.RESERVE):
            requirements = CapabilityRequirements(
                host_authority=HostAuthority.CARDANO,
                access_mode=access_mode,
                execution_tier=ExecutionTier.IMMEDIATE_DUAL_VALIDITY,
                minimum_privacy_class=1,
                maximum_cost=100,
            )
            with self.subTest(access_mode=access_mode), self.assertRaises(
                NoEligibleAdapterError
            ):
                select_adapter(
                    (make_adapter(1, host=HostAuthority.CARDANO),),
                    requirements,
                    now=1_000,
                )

    def test_routing_requirements_are_derived_from_signed_intent(self):
        intent = make_intent(
            tier=ExecutionTier.BATCHED_VALIDITY,
            suite=SignatureSuite.SECP256K1,
        )
        requirements = derive_capability_requirements(intent)
        self.assertEqual(len(requirements), 1)
        self.assertEqual(requirements[0].host_authority, HostAuthority.POLYGON)
        self.assertEqual(requirements[0].execution_tier, ExecutionTier.BATCHED_VALIDITY)
        self.assertEqual(requirements[0].maximum_cost, intent.max_settlement_cost)
        self.assertEqual(requirements[0].maximum_cost, 0)
        self.assertEqual(requirements[0].required_da, ("celestia",))
        selected = select_intent_adapters(
            (make_adapter(2, cost=0, latency=200), make_adapter(1, cost=0)),
            intent,
            now=1_000,
        )
        self.assertEqual(selected[0].adapter_id, b32(1))
        downgraded = make_intent(tier=ExecutionTier.BATCHED_VALIDITY)
        object.__setattr__(downgraded, "max_settlement_cost", 1)
        with self.assertRaisesRegex(ValueError, "max_settlement_cost"):
            derive_capability_requirements(downgraded)


class CanaryServiceTests(unittest.TestCase):
    def test_local_nonce_claim_is_atomic_under_alias_race(self):
        store = InMemoryNonceStore()
        nonce_key = (b32(1), b32(8), 3, 7)
        intent_ids = tuple(b32(value) for value in range(1, 17))
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = tuple(
                pool.map(
                    lambda intent_id: store.check_and_record(nonce_key, intent_id),
                    intent_ids,
                )
            )
        self.assertEqual(sum(results), 1)

    def test_shadow_submission_is_idempotent_and_performs_no_writes(self):
        service = VDSOCanaryService(
            mode=VDSOMode.SHADOW,
            height_provider=lambda _binding: 1_000,
        )
        intent = make_intent()
        first = service.submit_shadow(intent)
        second = service.submit_shadow(intent)
        self.assertEqual(first, second)
        self.assertEqual(first.external_writes, 0)
        self.assertEqual(first.status, "shadow_accepted")

    def test_nonce_alias_rejects_distinct_intent_but_allows_identical_retry(self):
        service = VDSOCanaryService(
            mode=VDSOMode.SHADOW,
            height_provider=lambda _binding: 1_000,
        )
        first_intent = make_intent()
        alias_intent = UnsignedIntent(
            **{**first_intent.__dict__, "program_id": b32(99)}
        )
        first = service.submit_shadow(first_intent)
        self.assertEqual(service.submit_shadow(first_intent), first)
        with self.assertRaisesRegex(VDSOServiceError, "nonce reuse"):
            service.submit_shadow(alias_intent)

    def test_authoritative_mode_is_unconditionally_blocked(self):
        with self.assertRaisesRegex(VDSOServiceError, "authoritative"):
            VDSOCanaryService(mode=VDSOMode.AUTHORITATIVE)

    def test_live_canary_requires_contract_configuration(self):
        with patch.dict(os.environ, {"VAMS_ENV": "testnet"}, clear=True):
            with self.assertRaisesRegex(VDSOServiceError, "registry addresses"):
                VDSOCanaryService(mode=VDSOMode.CANARY)

    def test_expired_intent_is_rejected(self):
        service = VDSOCanaryService(
            mode=VDSOMode.SHADOW,
            height_provider=lambda _binding: 1_000,
        )
        with self.assertRaisesRegex(VDSOServiceError, "expired"):
            service.submit_shadow(make_intent(valid_until_height=999))

    def test_height_expiry_is_not_interpreted_as_unix_time(self):
        service = VDSOCanaryService(
            mode=VDSOMode.SHADOW,
            height_provider=lambda _binding: 1_000,
        )
        record = service.simulate(make_intent(valid_until_height=1_000))
        self.assertEqual(record.status, "simulated")

    def test_claimed_height_must_match_trusted_binding_height(self):
        service = VDSOCanaryService(
            mode=VDSOMode.SHADOW,
            height_provider=lambda binding: (
                1_000 if binding.host_authority == HostAuthority.POLYGON else 2_000
            ),
        )
        with self.assertRaisesRegex(VDSOServiceError, "does not match"):
            service.simulate(make_intent(), current_height=999)
        self.assertEqual(
            service.simulate(make_intent(), current_height=1_000).status,
            "simulated",
        )

    def test_missing_trusted_height_provider_fails_closed(self):
        service = VDSOCanaryService(mode=VDSOMode.SHADOW)
        with self.assertRaisesRegex(VDSOServiceError, "trusted host height"):
            service.simulate(make_intent())

    def test_live_canary_rejects_placeholder_contract_addresses(self):
        with patch.dict(
            os.environ,
            {
                "VAMS_ENV": "testnet",
                "VDSO_OBJECT_STORE_ADDRESS": "0x1",
                "VDSO_EXECUTION_KERNEL_ADDRESS": "0x2",
                "VDSO_ADAPTER_REGISTRY_ADDRESS": "0x3",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(VDSOServiceError, "20-byte"):
                VDSOCanaryService(mode=VDSOMode.CANARY, height_provider=lambda _binding: 1)

    def test_live_canary_requires_durable_nonce_and_deployment_verifier(self):
        live = {
            "VAMS_ENV": "testnet",
            "VDSO_OBJECT_STORE_ADDRESS": "0x" + "11" * 20,
            "VDSO_EXECUTION_KERNEL_ADDRESS": "0x" + "22" * 20,
            "VDSO_ADAPTER_REGISTRY_ADDRESS": "0x" + "33" * 20,
        }
        with patch.dict(os.environ, live, clear=True):
            with self.assertRaisesRegex(VDSOServiceError, "durable atomic nonce"):
                VDSOCanaryService(
                    mode=VDSOMode.CANARY,
                    height_provider=lambda _binding: 1_000,
                )
            with self.assertRaisesRegex(VDSOServiceError, "deployment verifier"):
                VDSOCanaryService(
                    mode=VDSOMode.CANARY,
                    height_provider=lambda _binding: 1_000,
                    nonce_store=_DurableNonceStore(),
                )

    def test_live_deployment_verifier_checks_each_authority_binding(self):
        live = {
            "VAMS_ENV": "testnet",
            "VDSO_OBJECT_STORE_ADDRESS": "0x" + "11" * 20,
            "VDSO_EXECUTION_KERNEL_ADDRESS": "0x" + "22" * 20,
            "VDSO_ADAPTER_REGISTRY_ADDRESS": "0x" + "33" * 20,
        }
        seen = []

        def reject_binding(config, binding):
            seen.append((config.environment, binding.state_domain, binding.authority_epoch))
            return False

        with patch.dict(os.environ, live, clear=True):
            service = VDSOCanaryService(
                mode=VDSOMode.CANARY,
                height_provider=lambda _binding: 1_000,
                nonce_store=_DurableNonceStore(),
                deployment_verifier=reject_binding,
            )
        with self.assertRaisesRegex(VDSOServiceError, "rejected binding"):
            service.simulate(make_intent(), current_height=1_000)
        self.assertEqual(seen, [("testnet", b32(8), 3)])


class SidecarPolicyTests(unittest.TestCase):
    def test_missing_hpke_backend_fails_before_plaintext_storage(self):
        with self.assertRaisesRegex(SidecarCryptoUnavailable, "HPKE"):
            encrypt_sidecar(
                b"sensitive witness",
                plaintext_root=b32(1),
                policy_hash=b32(2),
                recipients=((b32(3), b"recipient-public-key"),),
                hpke_seal=None,
                associated_data=b"header",
            )

    def test_ciphertext_only_publisher_verifies_real_adapter_receipt(self):
        observed_blobs = {}

        class FakeCelestia(DAAdapter):
            protocol = DAProtocol.CELESTIA
            name = "fake-celestia"

            def __init__(self):
                super().__init__("https://celestia.invalid", mock_mode=False)
                self.submitted = b""

            async def submit_blob(self, data, namespace=None):
                self.submitted = data
                observed_blobs["blob-1"] = data
                return DAReceipt(
                    protocol=self.protocol,
                    blob_id="blob-1",
                    height=7,
                    commitment="0x" + hashlib.sha256(data).hexdigest(),
                    verified=False,
                )

            async def verify_blob(self, receipt):
                return receipt.blob_id == "blob-1"

            async def get_blob(self, blob_id):
                return self.submitted if blob_id == "blob-1" else None

        sidecar = make_encrypted_sidecar()
        adapter = FakeCelestia()

        async def independent_verify(receipt, payload):
            return (
                receipt.blob_id in observed_blobs
                and observed_blobs[receipt.blob_id] == payload
            )

        async def independent_retrieve(receipt):
            return observed_blobs.get(receipt.blob_id)

        publisher = EncryptedSidecarPublisher(
            adapter,
            live_evidence=RetrievalBoundLiveEvidence(
                receipt_verifier=independent_verify,
                blob_retriever=independent_retrieve,
            ),
        )
        receipt = asyncio.run(
            publisher.publish(
                sidecar,
                expected_sidecar_root=sidecar.content_hash,
            )
        )
        self.assertEqual(receipt.protocol, "celestia")
        self.assertEqual(receipt.content_hash, sidecar.content_hash)
        self.assertNotIn(b"sensitive witness", adapter.submitted)
        object.__setattr__(sidecar, "ciphertext", b"tampered-ciphertext")
        with self.assertRaisesRegex(VDSODAError, "integrity"):
            asyncio.run(
                publisher.publish(
                    sidecar,
                    expected_sidecar_root=sidecar.content_hash,
                )
            )
        envelope_tamper = make_encrypted_sidecar()
        object.__setattr__(
            envelope_tamper.recipient_envelopes[0],
            "wrapped_key",
            b"",
        )
        with self.assertRaisesRegex(VDSODAError, "integrity"):
            asyncio.run(
                publisher.publish(
                    envelope_tamper,
                    expected_sidecar_root=envelope_tamper.content_hash,
                )
            )

    def test_adapter_self_verification_cannot_establish_live_evidence(self):
        class LyingAdapter(DAAdapter):
            protocol = DAProtocol.CELESTIA
            name = "lying-adapter"

            def __init__(self):
                super().__init__("https://example.invalid", mock_mode=False)
                self.submitted = b""

            async def submit_blob(self, data, namespace=None):
                self.submitted = data
                return DAReceipt(
                    protocol=self.protocol,
                    blob_id="fabricated",
                    height=9,
                    commitment="0x" + hashlib.sha256(data).hexdigest(),
                )

            async def verify_blob(self, receipt):
                return True

            async def get_blob(self, blob_id):
                return self.submitted

        adapter = LyingAdapter()
        publisher = EncryptedSidecarPublisher(
            adapter,
            live_evidence=RetrievalBoundLiveEvidence(
                receipt_verifier=adapter.verify_blob,
                blob_retriever=adapter.get_blob,
            ),
        )
        sidecar = make_encrypted_sidecar()
        with self.assertRaisesRegex(VDSODAError, "independent"):
            asyncio.run(
                publisher.publish(
                    sidecar,
                    expected_sidecar_root=sidecar.content_hash,
                )
            )

    def test_sidecar_publication_rejects_detached_signed_root(self):
        class RetrievalAdapter(DAAdapter):
            protocol = DAProtocol.CELESTIA
            name = "retrieval-adapter"

            async def submit_blob(self, data, namespace=None):
                raise AssertionError("detached sidecar must fail before submission")

            async def verify_blob(self, receipt):
                return False

            async def get_blob(self, blob_id):
                return None

        publisher = EncryptedSidecarPublisher(
            RetrievalAdapter("https://example.invalid", mock_mode=False),
            live_evidence=unavailable_live_evidence(),
        )
        with self.assertRaisesRegex(VDSODAError, "detached"):
            asyncio.run(
                publisher.publish(
                    make_encrypted_sidecar(),
                    expected_sidecar_root=b32(99),
                )
            )

    def test_current_near_fabricated_receipt_lacks_live_retrieval_evidence(self):
        adapter = NearDAAdapter(mock_mode=False)
        self.assertFalse(adapter.mock_mode)
        with self.assertRaisesRegex(VDSODAError, "not VDSO live-evidence capable"):
            EncryptedSidecarPublisher(
                adapter,
                live_evidence=unavailable_live_evidence(),
            )

    def test_current_celestia_mock_fallback_cannot_masquerade_as_live(self):
        adapter = CelestiaDAAdapter(mock_mode=False)
        self.assertFalse(adapter.mock_mode)
        with self.assertRaisesRegex(VDSODAError, "not VDSO live-evidence capable"):
            EncryptedSidecarPublisher(
                adapter,
                live_evidence=unavailable_live_evidence(),
            )

    def test_sidecar_hash_binds_nonce_and_recipient_metadata(self):
        original = make_encrypted_sidecar()
        changed_nonce = make_encrypted_sidecar(nonce=b"m" * 24)
        changed_envelope = make_encrypted_sidecar(
            envelopes=(RecipientEnvelope(b32(4), b"different-enc", b"wrapped"),)
        )
        self.assertNotEqual(original.content_hash, changed_nonce.content_hash)
        self.assertNotEqual(original.content_hash, changed_envelope.content_hash)

    def test_sidecar_rejects_recipient_aliases_and_noncanonical_order(self):
        duplicate = (
            RecipientEnvelope(b32(4), b"enc-a", b"wrapped-a"),
            RecipientEnvelope(b32(4), b"enc-b", b"wrapped-b"),
        )
        with self.assertRaisesRegex(ValueError, "unique"):
            make_encrypted_sidecar(envelopes=duplicate)
        unsorted = (
            RecipientEnvelope(b32(5), b"enc-a", b"wrapped-a"),
            RecipientEnvelope(b32(4), b"enc-b", b"wrapped-b"),
        )
        with self.assertRaisesRegex(ValueError, "sorted"):
            make_encrypted_sidecar(envelopes=unsorted)

    def test_sidecar_rejects_content_hash_tamper(self):
        valid = make_encrypted_sidecar()
        with self.assertRaisesRegex(ValueError, "content_hash"):
            EncryptedWitnessSidecar(
                **{**valid.__dict__, "content_hash": b32(99)}
            )

    def test_mock_da_adapter_is_rejected(self):
        class MockNear(DAAdapter):
            protocol = DAProtocol.NEAR_DA
            name = "mock-near"

            async def submit_blob(self, data, namespace=None):
                raise AssertionError("must not submit")

            async def verify_blob(self, receipt):
                return False

            async def get_blob(self, blob_id):
                return None

        adapter = MockNear("https://near.invalid", mock_mode=True)
        with self.assertRaisesRegex(VDSODAError, "mock"):
            EncryptedSidecarPublisher(
                adapter,
                live_evidence=unavailable_live_evidence(),
            )

    @unittest.skipUnless(HAS_NACL, "PyNaCl is required for XChaCha20-Poly1305")
    def test_sidecar_uses_random_nonce_and_authenticated_encryption(self):
        captured_keys = []

        def hpke_stub(_recipient_public_key, data_key, _aad):
            captured_keys.append(data_key)
            return b"encapsulated", b"wrapped-key"

        kwargs = {
            "plaintext_root": b32(1),
            "policy_hash": b32(2),
            "recipients": ((b32(3), b"recipient-public-key"),),
            "hpke_seal": hpke_stub,
            "associated_data": b"bound-header",
        }
        first = encrypt_sidecar(b"sensitive witness", **kwargs)
        second = encrypt_sidecar(b"sensitive witness", **kwargs)
        self.assertNotEqual(first.nonce, second.nonce)
        self.assertNotEqual(first.ciphertext, second.ciphertext)
        recovered = crypto_aead_xchacha20poly1305_ietf_decrypt(
            first.ciphertext,
            b"bound-header",
            first.nonce,
            captured_keys[0],
        )
        self.assertEqual(recovered, b"sensitive witness")
        self.assertNotIn(b"sensitive witness", first.ciphertext)


class DurableWorkflowTests(unittest.TestCase):
    def test_shadow_workflow_has_deterministic_id_and_no_external_effect(self):
        intent = make_intent()
        orchestrator = VDSOOrchestrator(
            VDSOCanaryService(mode=VDSOMode.SHADOW, height_provider=lambda _binding: 1_000)
        )
        result = asyncio.run(orchestrator.run(intent))
        self.assertEqual(result.workflow_id, intent.workflow_id)
        self.assertEqual(result.external_writes, 0)
        self.assertEqual(result.completed_steps, ("canonical_simulation",))

    def test_step_idempotency_key_is_stable(self):
        intent = make_intent()
        self.assertEqual(
            idempotency_key(intent.intent_id, "submit_execution"),
            idempotency_key(intent.intent_id, "submit_execution"),
        )

    def test_reservation_failure_starts_recovery_and_never_auto_unlocks(self):
        sidecar = make_encrypted_sidecar()
        intent = UnsignedIntent(
            **{
                **make_intent(
                    tier=ExecutionTier.IMMEDIATE_DUAL_VALIDITY,
                    suite=SignatureSuite.SECP256K1_AND_ML_DSA_65,
                ).__dict__,
                "accesses": (ObjectAccess(b32(9), AccessMode.RESERVE, 1, 11),),
                "sidecar_root": sidecar.content_hash,
            }
        )
        calls = []

        async def evidence(key, payload):
            calls.append(("evidence", key))
            return payload

        async def fail_submit(key, payload):
            calls.append(("submit", key))
            raise RuntimeError("submission ambiguity")

        async def passthrough(key, payload):
            calls.append(("passthrough", key))
            return payload

        async def recover(key, payload):
            calls.append(("recover", key))
            return b"recovery-pending"

        with patch.dict(
            os.environ,
            {
                "VAMS_ENV": "local",
                "VDSO_OBJECT_STORE_ADDRESS": "0x1",
                "VDSO_EXECUTION_KERNEL_ADDRESS": "0x2",
                "VDSO_ADAPTER_REGISTRY_ADDRESS": "0x3",
            },
            clear=False,
        ):
            service = VDSOCanaryService(
                mode=VDSOMode.CANARY,
                adapters=(make_adapter(1),),
                height_provider=lambda _binding: 1_000,
            )
        service.store_encrypted_sidecar(sidecar)
        orchestrator = VDSOOrchestrator(
            service,
            VDSOWorkflowDependencies(
                acquire_evidence=evidence,
                submit_execution=fail_submit,
                await_finality=passthrough,
                verify_receipt=passthrough,
                recover_reservation=recover,
            ),
            routing_time_provider=lambda: 1_000,
        )
        result = asyncio.run(orchestrator.run(intent))
        self.assertEqual(result.status, "recovery_pending")
        self.assertTrue(result.recovery_started)
        self.assertEqual(result.selected_adapter_ids, (b32(1),))
        self.assertEqual([name for name, _key in calls], ["evidence", "submit", "recover"])

    def test_cardano_policy_bypass_fails_before_any_orchestration_step(self):
        intent = UnsignedIntent(
            **{
                **make_intent(
                    tier=ExecutionTier.IMMEDIATE_DUAL_VALIDITY,
                    suite=SignatureSuite.SECP256K1_AND_ML_DSA_65,
                ).__dict__,
                "binding": DomainAuthorityBinding(
                    b32(8), HostAuthority.CARDANO, 3
                ),
            }
        )
        object.__setattr__(intent.accesses[0], "mode", AccessMode.CONSUME)
        calls = []

        async def must_not_run(key, payload):
            calls.append(key)
            return payload

        orchestrator = VDSOOrchestrator(
            VDSOCanaryService(
                mode=VDSOMode.SHADOW,
                height_provider=lambda _binding: 1_000,
            ),
            VDSOWorkflowDependencies(
                acquire_evidence=must_not_run,
                submit_execution=must_not_run,
                await_finality=must_not_run,
                verify_receipt=must_not_run,
            ),
        )
        with self.assertRaisesRegex(Exception, "host/access policy"):
            asyncio.run(orchestrator.run(intent))
        self.assertEqual(calls, [])

    def test_missing_signed_sidecar_and_adapter_fail_before_external_steps(self):
        calls = []

        async def must_not_run(key, payload):
            calls.append(key)
            return payload

        dependencies = VDSOWorkflowDependencies(
            acquire_evidence=must_not_run,
            submit_execution=must_not_run,
            await_finality=must_not_run,
            verify_receipt=must_not_run,
        )
        service = VDSOCanaryService(
            mode=VDSOMode.CANARY,
            adapters=(make_adapter(1),),
            height_provider=lambda _binding: 1_000,
        )
        service.store_encrypted_sidecar(make_encrypted_sidecar())
        orchestrator = VDSOOrchestrator(
            service,
            dependencies,
            routing_time_provider=lambda: 1_000,
        )
        with self.assertRaisesRegex(Exception, "failed closed"):
            asyncio.run(orchestrator.run(make_intent()))
        self.assertEqual(calls, [])

        sidecar = make_encrypted_sidecar()
        bound_intent = UnsignedIntent(
            **{**make_intent().__dict__, "sidecar_root": sidecar.content_hash}
        )
        no_adapter_service = VDSOCanaryService(
            mode=VDSOMode.CANARY,
            height_provider=lambda _binding: 1_000,
        )
        no_adapter_service.store_encrypted_sidecar(sidecar)
        no_adapter_orchestrator = VDSOOrchestrator(
            no_adapter_service,
            dependencies,
            routing_time_provider=lambda: 1_000,
        )
        with self.assertRaisesRegex(Exception, "failed closed"):
            asyncio.run(no_adapter_orchestrator.run(bound_intent))
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
