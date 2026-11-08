import hashlib
import json
import logging

import pytest
import requests

from neuron.clr_router import CLRouter, RoutingPriority, TransactionIntent, TrustTier
from neuron.runtime_safety import (
    LiveModeSafetyError,
    RuntimeConfigurationError,
    RuntimePolicy,
)
from neuron.sdk.oms_identity import OMSIdentityVerifier
from neuron.sdk.phala_tee import AttestationReport, PhalaTEE, TEEProvider
from neuron.sdk.trust_aggregator import TrustAggregatorClient
from neuron.trust_plugins.tee_plugin import TEEProofPlugin


ROOT_EOA = b"\x33" * 20
SERVICE_HASH = b"\x11" * 32
DELIVERY_HASH = b"\x22" * 32
LIVE_ENDPOINT = "https://provider.invalid"


class _FixtureRaw:
    """Local JSON-byte fixture; not an HTTP/urllib3 implementation."""
    def __init__(self, response):
        self.response = response
        self.data = None
        self.offset = 0
        self.requests = []

    def read(self, amount, *, decode_content=False):
        self.requests.append((amount, decode_content))
        if type(amount) is not int or amount <= 0 or decode_content is not False:
            raise AssertionError("Expected a bounded undecoded byte read")
        if self.data is None:
            payload = self.response._payload
            if isinstance(payload, Exception): raise payload
            self.data = json.dumps(payload).encode("utf-8")
        chunk = self.data[self.offset:self.offset + amount]
        self.offset += len(chunk)
        return chunk


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.headers = {}
        self.raw = _FixtureRaw(self)
        self.close_calls = 0

    def close(self):
        self.close_calls += 1

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeTransport:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []
        self.headers = {}

    def get(self, url, **kwargs):
        self.calls.append(("get", url, kwargs))
        if self.error:
            raise self.error
        return self.response

    def post(self, url, **kwargs):
        self.calls.append(("post", url, kwargs))
        if self.error:
            raise self.error
        return self.response


def oms_environment(mode, mock="false"):
    return {
        "VAMS_ENV": mode,
        "OMS_MOCK_MODE": mock,
        "OMS_IDENTITY_API": LIVE_ENDPOINT,
        "OMS_API_KEY": "unit-test-key",
    }


def phala_environment(mode, mock="false"):
    return {
        "VAMS_ENV": mode,
        "PHALA_MOCK_MODE": mock,
        "PHALA_RPC_URL": LIVE_ENDPOINT,
    }


@pytest.mark.parametrize("mode", ["test", "local", "demo"])
def test_oms_mock_requires_explicit_authorized_non_live_mode(mode):
    verifier = OMSIdentityVerifier(environ=oms_environment(mode, "true"))

    result = verifier.verify_identity("0x99aabb")

    assert result.verified is True
    assert result.simulated is True
    assert result.evidence_classification == "non-authoritative"
    assert result.usable_for_compliance is False


@pytest.mark.parametrize("mode", ["staging", "testnet", "production"])
def test_oms_mock_is_rejected_in_every_live_mode(mode):
    with pytest.raises(LiveModeSafetyError, match=rf"OMSIdentityVerifier.*{mode}"):
        OMSIdentityVerifier(environ=oms_environment(mode, "true"))


@pytest.mark.parametrize("mode", ["staging", "testnet", "production"])
def test_oms_live_mode_requires_explicit_endpoint_and_credential(mode):
    with pytest.raises(LiveModeSafetyError, match="OMS_IDENTITY_API and OMS_API_KEY"):
        OMSIdentityVerifier(environ={"VAMS_ENV": mode})


@pytest.mark.parametrize("value", ["", "TRUE", "1", " true", "false "])
def test_oms_mock_flag_is_strict(value):
    environment = oms_environment("test")
    environment["OMS_MOCK_MODE"] = value
    with pytest.raises(RuntimeConfigurationError, match="OMS_MOCK_MODE"):
        OMSIdentityVerifier(environ=environment)


def test_oms_conflicting_explicit_and_environment_configuration_fails():
    with pytest.raises(RuntimeConfigurationError, match="Conflicting.*OMSIdentityVerifier"):
        OMSIdentityVerifier(mock_mode=False, environ=oms_environment("test", "true"))


def test_oms_provider_success_is_live_eligible_only_in_live_runtime():
    transport = FakeTransport(FakeResponse({"is_verified": True}))
    verifier = OMSIdentityVerifier(
        environ=oms_environment("testnet"), transport=transport
    )

    result = verifier.verify_identity("0x112233")

    assert result.verified is True
    assert result.simulated is False
    assert result.evidence_classification == "live-provider"
    assert result.usable_for_compliance is True


@pytest.mark.parametrize(
    ("transport", "error_code"),
    [
        (FakeTransport(error=requests.Timeout("contains-sensitive-detail")), "provider_unavailable"),
        (FakeTransport(FakeResponse({"is_verified": "yes"})), "malformed_response"),
        (FakeTransport(FakeResponse({}, status_code=503)), "provider_status"),
    ],
)
def test_oms_provider_failures_fail_closed_without_mock_fallback(transport, error_code):
    verifier = OMSIdentityVerifier(
        environ=oms_environment("testnet"), transport=transport
    )

    result = verifier.verify_identity("0xprivate-subject")

    assert result.verified is False
    assert result.simulated is False
    assert result.error_code == error_code
    assert result.evidence_classification == "non-authoritative"


def test_oms_diagnostics_do_not_expose_subject_or_provider_exception(caplog):
    caplog.set_level(logging.ERROR)
    verifier = OMSIdentityVerifier(
        environ=oms_environment("testnet"),
        transport=FakeTransport(error=requests.Timeout("secret-token")),
    )

    verifier.verify_identity("0xprivate-subject")

    assert "0xprivate-subject" not in caplog.text
    assert "secret-token" not in caplog.text
    assert "OMSIdentityVerifier" in caplog.text


def test_p3_blocks_simulated_oms_success():
    verifier = OMSIdentityVerifier(environ=oms_environment("test", "true"))
    router = CLRouter(identity_verifier=verifier)
    intent = TransactionIntent(
        value_usd=1000,
        max_latency_ms=30000,
        requires_privacy=False,
        requires_institutional_compliance=True,
        agent_address="0x99aabb",
        loaded_service_blocks=["ServiceBlock_OMS_v1"],
    )

    with pytest.raises(PermissionError, match="live OMS verified identity"):
        router.route(intent, TrustTier.PLATINUM)


@pytest.mark.parametrize(
    "response,error",
    [
        (FakeResponse({"is_verified": False}), None),
        (FakeResponse({}, status_code=503), None),
        (FakeResponse({"is_verified": "yes"}), None),
        (None, requests.Timeout("synthetic timeout")),
    ],
    ids=["unverified", "provider-status", "malformed", "timeout"],
)
def test_p3_provider_nonverification_fails_closed(response, error):
    transport = FakeTransport(response=response, error=error)
    verifier = OMSIdentityVerifier(
        environ=oms_environment("testnet"),
        transport=transport,
    )
    router = CLRouter(identity_verifier=verifier)
    intent = TransactionIntent(
        value_usd=1000,
        max_latency_ms=30000,
        requires_privacy=False,
        requires_institutional_compliance=True,
        agent_address="0x112233",
        loaded_service_blocks=["ServiceBlock_OMS_v1"],
    )

    with pytest.raises(PermissionError, match="live OMS verified identity"):
        router.route(intent, TrustTier.PLATINUM)

    assert len(transport.calls) == 1


def test_p3_accepts_successful_live_oms_result():
    verifier = OMSIdentityVerifier(
        environ=oms_environment("testnet"),
        transport=FakeTransport(FakeResponse({"is_verified": True})),
    )
    router = CLRouter(identity_verifier=verifier)
    intent = TransactionIntent(
        value_usd=1000,
        max_latency_ms=30000,
        requires_privacy=False,
        requires_institutional_compliance=True,
        agent_address="0x112233",
        loaded_service_blocks=["ServiceBlock_OMS_v1"],
    )

    decision = router.route(intent, TrustTier.PLATINUM)

    assert decision.priority is RoutingPriority.P3_INSTITUTIONAL_COMPLIANCE


def test_p3_rejects_successful_provider_result_in_non_live_runtime():
    verifier = OMSIdentityVerifier(
        environ=oms_environment("test"),
        transport=FakeTransport(FakeResponse({"is_verified": True})),
    )
    router = CLRouter(identity_verifier=verifier)
    intent = TransactionIntent(
        value_usd=1000,
        max_latency_ms=30000,
        requires_privacy=False,
        requires_institutional_compliance=True,
        agent_address="0x112233",
        loaded_service_blocks=["ServiceBlock_OMS_v1"],
    )

    with pytest.raises(PermissionError, match="live OMS verified identity"):
        router.route(intent, TrustTier.PLATINUM)


def test_p3_rejects_unavailable_oms_verifier(monkeypatch):
    def unavailable_verifier():
        raise RuntimeError("sanitized fixture failure")

    monkeypatch.setattr("neuron.clr_router.OMSIdentityVerifier", unavailable_verifier)
    router = CLRouter()
    intent = TransactionIntent(
        value_usd=1000,
        max_latency_ms=30000,
        requires_privacy=False,
        requires_institutional_compliance=True,
        agent_address="0x112233",
        loaded_service_blocks=["ServiceBlock_OMS_v1"],
    )

    with pytest.raises(PermissionError, match="verifier is unavailable"):
        router.route(intent, TrustTier.PLATINUM)


def test_oms_configuration_is_read_at_construction_not_import(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "local")
    monkeypatch.setenv("OMS_MOCK_MODE", "false")
    monkeypatch.setenv("OMS_IDENTITY_API", LIVE_ENDPOINT)
    monkeypatch.setenv("OMS_API_KEY", "unit-test-key")
    monkeypatch.setenv("VAMS_ENV", "testnet")
    monkeypatch.setenv("OMS_MOCK_MODE", "true")

    with pytest.raises(LiveModeSafetyError, match="testnet"):
        OMSIdentityVerifier()


def activate_phala_environment(monkeypatch, mode, mock="false"):
    """Select actual process policy; a constructor map cannot grant authority."""
    settings = phala_environment(mode, mock)
    for key, value in settings.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("PHALA_API_KEY", raising=False)
    return settings


@pytest.mark.parametrize("mode", ["test", "local", "demo"])
def test_phala_mock_requires_explicit_authorized_non_live_mode(mode, monkeypatch):
    tee = PhalaTEE(environ=activate_phala_environment(monkeypatch, mode, "true"))

    report = tee.verify_sgx_quote(b"synthetic-quote")

    assert report.is_valid is True
    assert report.simulated is True
    assert report.evidence_classification == "non-authoritative"
    assert report.usable_as_live_evidence is False


@pytest.mark.parametrize("mode", ["staging", "testnet", "production"])
def test_phala_mock_is_rejected_in_every_live_mode(mode, monkeypatch):
    with pytest.raises(LiveModeSafetyError, match=rf"PhalaTEE.*{mode}"):
        PhalaTEE(environ=activate_phala_environment(monkeypatch, mode, "true"))


@pytest.mark.parametrize("mode", ["staging", "testnet", "production"])
def test_phala_live_mode_requires_explicit_endpoint(mode, monkeypatch):
    activate_phala_environment(monkeypatch, mode)
    monkeypatch.delenv("PHALA_RPC_URL", raising=False)
    with pytest.raises(LiveModeSafetyError, match="PHALA_RPC_URL"):
        PhalaTEE(environ={"VAMS_ENV": mode, "PHALA_MOCK_MODE": "false"})


def test_phala_provider_timeout_does_not_fallback_to_simulation(monkeypatch):
    tee = PhalaTEE(
        environ=activate_phala_environment(monkeypatch, "testnet"),
        transport=FakeTransport(error=requests.Timeout("secret-attestation")),
    )

    report = tee.verify_sgx_quote(b"synthetic-quote")

    assert report.is_valid is False
    assert report.simulated is False
    assert report.error == "provider_unavailable"


def test_phala_malformed_provider_response_fails_closed(monkeypatch):
    tee = PhalaTEE(
        environ=activate_phala_environment(monkeypatch, "testnet"),
        transport=FakeTransport(FakeResponse({"valid": "yes"})),
    )

    report = tee.verify_sgx_quote(b"synthetic-quote")

    assert report.is_valid is False
    assert report.error == "malformed_response"


def test_phala_live_enclave_configuration_does_not_authorize_execution(monkeypatch):
    transport = FakeTransport(FakeResponse({"output": {}, "gas_used": 1}))
    tee = PhalaTEE(
        environ={
            **activate_phala_environment(monkeypatch, "testnet"),
            "VAMS_PHAT_PYTHON_RUNTIME": "runtime-contract",
            "PHALA_API_KEY": "unit-test-only-credential",
        },
        transport=transport,
    )

    with pytest.raises(LiveModeSafetyError, match="authenticated action admission"):
        tee.execute_python_in_enclave("print('fixture')")
    assert transport.calls == []


def test_phala_execution_configuration_is_immutable_after_construction(monkeypatch):
    transport = FakeTransport(FakeResponse({"output": {}, "gas_used": 1}))
    tee = PhalaTEE(
        environ={
            **activate_phala_environment(monkeypatch, "test"),
            "VAMS_PHAT_PYTHON_RUNTIME": "runtime-a",
        },
        transport=transport,
    )
    monkeypatch.setenv("VAMS_PHAT_PYTHON_RUNTIME", "runtime-b")

    result = tee.execute_python_in_enclave("print('fixture')")

    assert result.success is True
    assert transport.calls[-1][2]["json"]["address"] == "runtime-a"


def test_phala_valid_claim_without_binding_fields_is_malformed(monkeypatch):
    tee = PhalaTEE(
        environ=activate_phala_environment(monkeypatch, "testnet"),
        transport=FakeTransport(FakeResponse({"valid": True})),
    )

    report = tee.verify_sgx_quote(b"synthetic-quote")

    assert report.is_valid is False
    assert report.error == "malformed_response"


def live_attestation(root=ROOT_EOA, *, simulated=False):
    binding = hashlib.sha3_256(SERVICE_HASH + DELIVERY_HASH + root).hexdigest()
    return AttestationReport(
        provider=TEEProvider.PHALA,
        is_valid=True,
        quote_hash="sanitized-test-hash",
        mrenclave="11" * 32,
        mrsigner="22" * 32,
        simulated=simulated,
        runtime_classification="live",
        evidence_classification=("non-authoritative" if simulated else "live-provider"),
        attested_root_eoa="0x" + root.hex(),
        report_data=binding,
    )


class FakePhalaClient:
    def __init__(self, report):
        self.report = report
        self.calls = 0

    def verify_sgx_quote(self, quote):
        self.calls += 1
        return self.report


def test_tee_plugin_rejects_fabricated_live_report_with_matching_root(monkeypatch):
    settings = activate_phala_environment(monkeypatch, "testnet")
    client = FakePhalaClient(live_attestation())
    plugin = TEEProofPlugin(
        runtime_policy=RuntimePolicy.from_environment(settings),
        environ=settings,
        phala_client=client,
    )
    result = plugin.generate_proof(
        SERVICE_HASH, DELIVERY_HASH, root_address=ROOT_EOA, sgx_quote=b"synthetic-quote"
    )
    assert result.valid is False
    assert result.proof_data == b""
    assert result.metadata["reason"] == "authentic_verifier_unavailable"
    assert result.metadata["root_binding"] == "unverified"
    assert client.calls == 0


def test_tee_plugin_rejects_session_key_substitution(monkeypatch):
    plugin = TEEProofPlugin(
        mock_mode=True,
        environ=activate_phala_environment(monkeypatch, "test", "true"),
    )
    with pytest.raises(ValueError, match="session key"):
        plugin.generate_proof(
            SERVICE_HASH,
            DELIVERY_HASH,
            root_address=ROOT_EOA,
            session_key_address=ROOT_EOA,
        )


def test_tee_plugin_rejects_unqualified_wrong_root_report_before_client(monkeypatch):
    settings = activate_phala_environment(monkeypatch, "testnet")
    client = FakePhalaClient(live_attestation(b"\x44" * 20))
    plugin = TEEProofPlugin(
        runtime_policy=RuntimePolicy.from_environment(settings),
        environ=settings,
        phala_client=client,
    )
    result = plugin.generate_proof(
        SERVICE_HASH, DELIVERY_HASH, root_address=ROOT_EOA, sgx_quote=b"synthetic-quote"
    )
    assert result.valid is False
    assert result.proof_data == b""
    assert result.metadata["root_binding"] == "unverified"
    assert result.metadata["reason"] == "authentic_verifier_unavailable"
    assert client.calls == 0


def test_non_live_simulated_proof_cannot_cross_live_verification_boundary(monkeypatch):
    simulated = TEEProofPlugin(
        mock_mode=True,
        environ=activate_phala_environment(monkeypatch, "demo", "true"),
    ).generate_proof(SERVICE_HASH, DELIVERY_HASH, root_address=ROOT_EOA)
    settings = activate_phala_environment(monkeypatch, "testnet")
    policy = RuntimePolicy.from_environment(settings)
    live_plugin = TEEProofPlugin(
        runtime_policy=policy,
        environ=settings,
        phala_client=FakePhalaClient(live_attestation(simulated=True)),
    )

    assert simulated.metadata["evidence_classification"] == "non-authoritative"
    assert live_plugin.verify_proof(
        SERVICE_HASH, DELIVERY_HASH, simulated.proof_data
    ) is False


def test_non_live_simulated_proof_cannot_cross_submission_boundary(monkeypatch):
    simulated = TEEProofPlugin(
        mock_mode=True,
        environ=activate_phala_environment(monkeypatch, "test", "true"),
    ).generate_proof(SERVICE_HASH, DELIVERY_HASH, root_address=ROOT_EOA)
    client = TrustAggregatorClient.__new__(TrustAggregatorClient)
    client.plugins = {}

    with pytest.raises(LiveModeSafetyError, match="non-authoritative TEE"):
        client.submit_plugin_bundle({TEEProofPlugin.PROOF_TYPE_ID: simulated})


def test_phala_configuration_is_read_at_construction_not_import(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "local")
    monkeypatch.setenv("PHALA_MOCK_MODE", "false")
    monkeypatch.setenv("VAMS_ENV", "production")
    monkeypatch.setenv("PHALA_MOCK_MODE", "true")
    monkeypatch.setenv("PHALA_RPC_URL", LIVE_ENDPOINT)

    with pytest.raises(LiveModeSafetyError, match="production"):
        PhalaTEE()
