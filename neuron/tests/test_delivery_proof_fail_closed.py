from neuron.payments.delivery_proof import (
    HashPreimageProof,
    ProofType,
    ProofType,
    TEEAttestationProof,
    ZKMLProof,
)


def test_hash_preimage_rejects_malformed_commitment() -> None:
    proof = HashPreimageProof(
        proof_type=ProofType.HASH_PREIMAGE,
        service_id="service",
        consumer="consumer",
        provider="provider",
        preimage="value",
    )

    assert proof.verify("malformed") is False
    assert proof.verify("sha256:not-hex") is False


def test_tee_proof_requires_real_verifier():
    proof = TEEAttestationProof(
        proof_type=ProofType.TEE_ATTESTATION,
        service_id="svc",
        consumer="consumer",
        provider="provider",
        quote="quote",
        signature="signature",
        measurement="expected",
    )

    assert proof.verify("sgx:expected") is False


def test_zkml_proof_requires_real_verifier():
    proof = ZKMLProof(
        proof_type=ProofType.ZK_SNARK,
        service_id="svc",
        consumer="consumer",
        provider="provider",
        snark_proof="non-empty-is-not-enough",
        public_inputs="inputs",
    )

    assert proof.verify("zk:model") is False


def test_external_verifier_result_is_enforced():
    proof = ZKMLProof(
        proof_type=ProofType.ZK_SNARK,
        service_id="svc",
        consumer="consumer",
        provider="provider",
        snark_proof="proof",
        public_inputs="inputs",
        verifier=lambda proof, inputs, commitment: (
            proof == "proof" and inputs == "inputs" and commitment == "zk:model"
        ),
    )

    assert proof.verify("zk:model") is True
    assert proof.verify("zk:other") is False
