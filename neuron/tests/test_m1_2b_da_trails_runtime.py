"""Public-boundary coverage for M1.2b DA and Trails runtime gating."""

from __future__ import annotations

import logging

import pytest

import neuron.sdk.eigenda_kzg as eigenda_module
import neuron.sdk.trails_client as trails_module

from neuron.da.adapters.avail_adapter import AvailDAAdapter
from neuron.da.adapters.eigenda_adapter import EigenDAAdapter
from neuron.da.models import DAProtocol, DAReceipt
from neuron.da.performance_audit import PerformanceAuditLog
from neuron.runtime_safety import LiveModeSafetyError, RuntimeConfigurationError
from neuron.sdk.avail_substrate import AvailDAError, AvailDASDK
from neuron.sdk.eigenda_kzg import EigenDAError, EigenDASDK
from neuron.sdk.trails_client import TrailsClient, TrailsError


NON_LIVE_MODES = ("test", "local", "demo")
LIVE_MODES = ("staging", "testnet", "production")


class FakeResponse:
    def __init__(self, payload, error=None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error is not None:
            raise self.error

    def json(self):
        return self.payload


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def _next(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return FakeResponse(response)

    def post(self, url, **kwargs):
        return self._next("post", url, **kwargs)

    def get(self, url, **kwargs):
        return self._next("get", url, **kwargs)


@pytest.mark.parametrize("mode", NON_LIVE_MODES)
@pytest.mark.parametrize("adapter_type", (AvailDAAdapter, EigenDAAdapter))
@pytest.mark.asyncio
async def test_structured_adapters_require_explicit_non_live_mock(mode, adapter_type):
    adapter = adapter_type(mock_mode=True, environ={"VAMS_ENV": mode})
    receipt = await adapter.submit_blob(b"synthetic-payload")

    assert receipt.simulated is True
    assert receipt.verified is False
    assert receipt.blob_id.startswith(f"simulated:{adapter.protocol.value}:")
    assert receipt.commitment.startswith("simulated:sha256:")
    assert receipt.runtime_classification == "non-live"
    assert receipt.evidence_classification == "non-authoritative"
    assert await adapter.verify_blob(receipt) is False

    with pytest.raises(LiveModeSafetyError, match="structured stub"):
        adapter_type(mock_mode=False, environ={"VAMS_ENV": mode})


@pytest.mark.parametrize("mode", LIVE_MODES)
@pytest.mark.parametrize("factory", (AvailDAAdapter, EigenDAAdapter, AvailDASDK))
def test_structured_avail_and_eigenda_surfaces_cannot_register_live(mode, factory):
    with pytest.raises(LiveModeSafetyError, match=f"VAMS_ENV={mode}"):
        factory(mock_mode=True, environ={"VAMS_ENV": mode})


@pytest.mark.parametrize("mode", NON_LIVE_MODES)
def test_avail_sdk_only_emits_non_authoritative_simulation(mode):
    sdk = AvailDASDK(mock_mode=True, environ={"VAMS_ENV": mode})
    result = sdk.submit_data(b"synthetic-payload")

    assert result["status"] == "simulated"
    assert result["block_hash"].startswith("simulated:")
    assert result["verified"] is False
    assert result["simulated"] is True
    assert result["evidence_classification"] == "non-authoritative"
    with pytest.raises(AvailDAError, match="do not support authoritative retrieval"):
        sdk.retrieve_data(result["block_hash"], result["extrinsic_index"])


@pytest.mark.parametrize("mode", LIVE_MODES)
def test_eigenda_mock_is_rejected_live(mode):
    with pytest.raises(LiveModeSafetyError, match=f"VAMS_ENV={mode}"):
        EigenDASDK(mock_mode=True, environ={"VAMS_ENV": mode})


@pytest.mark.parametrize(
    ("factory", "variable"),
    (
        (AvailDAAdapter, "AVAIL_ADAPTER_MOCK_MODE"),
        (EigenDAAdapter, "EIGENDA_ADAPTER_MOCK_MODE"),
        (AvailDASDK, "AVAIL_MOCK_MODE"),
        (EigenDASDK, "EIGENDA_MOCK_MODE"),
        (TrailsClient, "TRAILS_MOCK_MODE"),
    ),
)
def test_component_mock_flags_reject_malformed_and_conflicting_values(factory, variable):
    with pytest.raises(RuntimeConfigurationError, match=f"Malformed {variable}"):
        factory(environ={"VAMS_ENV": "local", variable: "TRUE"})
    with pytest.raises(RuntimeConfigurationError, match="Conflicting mock configuration"):
        factory(
            mock_mode=True,
            environ={"VAMS_ENV": "local", variable: "false"},
        )


def test_scoped_mock_flags_default_off_without_provider_fallback():
    environment = {"VAMS_ENV": "local"}
    with pytest.raises(LiveModeSafetyError, match="structured stub"):
        AvailDAAdapter(environ=environment)
    with pytest.raises(LiveModeSafetyError, match="structured stub"):
        EigenDAAdapter(environ=environment)
    with pytest.raises(LiveModeSafetyError, match="structured stub"):
        AvailDASDK(environ=environment)
    with pytest.raises(EigenDAError, match="explicit valid EIGENDA_PROXY_URL"):
        EigenDASDK(environ=environment)
    with pytest.raises(TrailsError, match="TRAILS_API_KEY"):
        TrailsClient(environ=environment)


@pytest.mark.parametrize("mode", ("test", "local", "demo", "staging", "testnet", "production"))
def test_eigenda_real_path_uses_explicit_transport_in_every_mode(mode):
    transport = FakeTransport(
        [{"result": {"batchHeaderHash": "0xabc123", "blobIndex": 2}}]
    )
    sdk = EigenDASDK(
        mock_mode=False,
        rpc_url="https://eigenda.invalid/rpc",
        environ={"VAMS_ENV": mode},
        transport=transport,
    )

    result = sdk.submit_blob(b"synthetic-payload")

    assert result["status"] == "pending"
    assert result["simulated"] is False
    assert result["verified"] is False
    assert len(transport.calls) == 1


def test_eigenda_provider_failure_and_malformed_result_never_fallback_to_mock():
    failed = EigenDASDK(
        mock_mode=False,
        rpc_url="https://eigenda.invalid/rpc",
        environ={"VAMS_ENV": "testnet"},
        transport=FakeTransport([TimeoutError("credential=secret-value")]),
    )
    with pytest.raises(EigenDAError, match="provider request failed") as exc_info:
        failed.submit_blob(b"payload")
    assert "secret-value" not in str(exc_info.value)

    malformed = EigenDASDK(
        mock_mode=False,
        rpc_url="https://eigenda.invalid/rpc",
        environ={"VAMS_ENV": "testnet"},
        transport=FakeTransport([{"result": {"batchHeaderHash": None, "blobIndex": 0}}]),
    )
    with pytest.raises(EigenDAError, match="valid batch header hash"):
        malformed.submit_blob(b"payload")


def test_eigenda_retrieval_and_polling_fail_closed():
    malformed_blob = EigenDASDK(
        mock_mode=False,
        rpc_url="https://eigenda.invalid/rpc",
        environ={"VAMS_ENV": "testnet"},
        transport=FakeTransport([{"result": {"data": "not-hex"}}]),
    )
    with pytest.raises(EigenDAError, match="malformed blob data"):
        malformed_blob.retrieve_blob("0xabc123", 0)

    pending = EigenDASDK(
        mock_mode=False,
        rpc_url="https://eigenda.invalid/rpc",
        environ={"VAMS_ENV": "testnet"},
        transport=FakeTransport(
            [{"result": {"status": "pending"}}, {"result": {"status": "pending"}}]
        ),
        max_poll_attempts=2,
    )
    with pytest.raises(EigenDAError, match="polling exhausted"):
        pending.wait_for_confirmation("0xabc123", 0)


@pytest.mark.parametrize("mode", NON_LIVE_MODES)
def test_trails_explicit_mock_is_non_authoritative_and_rejected_by_live_boundary(mode):
    client = TrailsClient(mock_mode=True, environ={"VAMS_ENV": mode})
    receipt = client.submit_intent("source", "destination", b"payload")
    status = client.get_status(receipt.intent_id)

    assert receipt.simulated is True
    assert receipt.verified is False
    assert status.simulated is True
    assert status.tx_hash.startswith("simulated:sha256:")
    assert status.evidence_classification == "non-authoritative"
    with pytest.raises(TrailsError, match="not usable as a live result"):
        client.require_live_result(status)


@pytest.mark.parametrize("mode", LIVE_MODES)
def test_trails_mock_is_rejected_live(mode):
    with pytest.raises(LiveModeSafetyError, match=f"VAMS_ENV={mode}"):
        TrailsClient(mock_mode=True, environ={"VAMS_ENV": mode})


@pytest.mark.parametrize("mode", ("test", "local", "demo", "staging", "testnet", "production"))
def test_trails_real_path_uses_explicit_provider_in_every_mode(mode):
    transport = FakeTransport(
        [
            {
                "intent_id": "provider-intent",
                "status": "submitted",
                "estimated_settlement_time": 123,
            }
        ]
    )
    client = TrailsClient(
        mock_mode=False,
        api_url="https://trails.invalid/v1",
        api_key="provider-key",
        environ={"VAMS_ENV": mode},
        transport=transport,
    )
    receipt = client.submit_intent("source", "destination", b"payload")

    assert receipt.intent_id == "provider-intent"
    assert receipt.simulated is False
    assert receipt.verified is False
    assert receipt.runtime_classification == (
        "live" if mode in LIVE_MODES else "non-live"
    )


@pytest.mark.parametrize("mode", LIVE_MODES)
def test_trails_live_requires_endpoint_auth_and_rejects_placeholders(mode):
    with pytest.raises(TrailsError, match="TRAILS_API_KEY"):
        TrailsClient(mock_mode=False, environ={"VAMS_ENV": mode})
    with pytest.raises(TrailsError, match="TRAILS_API_URL"):
        TrailsClient(
            mock_mode=False,
            api_key="provider-key",
            environ={"VAMS_ENV": mode},
        )
    with pytest.raises(TrailsError, match="placeholder"):
        TrailsClient(
            mock_mode=False,
            api_url="https://trails.invalid/v1",
            api_key="demo" + "-key",
            environ={"VAMS_ENV": mode},
        )


def test_trails_live_provider_result_is_explicit_and_not_synthetic():
    transport = FakeTransport(
        [
            {
                "intent_id": "provider-intent",
                "status": "submitted",
                "estimated_settlement_time": 123,
            },
            {
                "intent_id": "provider-intent",
                "status": "settled",
                "tx_hash": "0xabc123",
            },
        ]
    )
    client = TrailsClient(
        mock_mode=False,
        api_url="https://trails.invalid/v1",
        api_key="provider-key",
        environ={"VAMS_ENV": "testnet"},
        transport=transport,
    )

    receipt = client.submit_intent("source", "destination", b"payload")
    status = client.get_status(receipt.intent_id)

    assert receipt.intent_id == "provider-intent"
    assert receipt.simulated is False
    assert status.tx_hash == "0xabc123"
    assert status.verified is False
    assert client.require_live_result(status) is status


def test_trails_provider_failure_is_sanitized_and_never_succeeds(caplog):
    client = TrailsClient(
        mock_mode=False,
        api_url="https://trails.invalid/v1",
        api_key="provider-key",
        environ={"VAMS_ENV": "testnet"},
        transport=FakeTransport([TimeoutError("Bearer private-provider-token")]),
    )
    with caplog.at_level(logging.ERROR), pytest.raises(
        TrailsError, match="provider submission failed"
    ) as exc_info:
        client.submit_intent("source", "destination", b"payload")

    rendered = str(exc_info.value) + caplog.text
    assert "private-provider-token" not in rendered
    assert "provider-key" not in rendered


def test_trails_malformed_or_mismatched_provider_data_fails_closed():
    missing_id = TrailsClient(
        mock_mode=False,
        api_url="https://trails.invalid/v1",
        api_key="provider-key",
        environ={"VAMS_ENV": "testnet"},
        transport=FakeTransport(
            [{"status": "submitted", "estimated_settlement_time": 123}]
        ),
    )
    with pytest.raises(TrailsError, match="omitted intent_id"):
        missing_id.submit_intent("source", "destination", b"payload")

    mismatch = TrailsClient(
        mock_mode=False,
        api_url="https://trails.invalid/v1",
        api_key="provider-key",
        environ={"VAMS_ENV": "testnet"},
        transport=FakeTransport(
            [{"intent_id": "other", "status": "settled", "tx_hash": "0xabc"}]
        ),
    )
    with pytest.raises(TrailsError, match="mismatched intent"):
        mismatch.get_status("expected")


def test_component_runtime_configuration_is_immutable_after_construction():
    environment = {"VAMS_ENV": "local"}
    client = TrailsClient(mock_mode=True, environ=environment)
    environment["VAMS_ENV"] = "production"
    environment["TRAILS_MOCK_MODE"] = "false"

    result = client.submit_intent("source", "destination", b"payload")
    assert result.simulated is True
    assert result.runtime_classification == "non-live"


@pytest.mark.parametrize(
    ("factory", "field", "replacement"),
    (
        (
            lambda: AvailDAAdapter(mock_mode=True, environ={"VAMS_ENV": "local"}),
            "mock_mode",
            False,
        ),
        (
            lambda: EigenDAAdapter(mock_mode=True, environ={"VAMS_ENV": "local"}),
            "rpc_url",
            "https://replacement.invalid",
        ),
        (
            lambda: AvailDASDK(mock_mode=True, environ={"VAMS_ENV": "local"}),
            "runtime_policy",
            None,
        ),
        (
            lambda: EigenDASDK(mock_mode=True, environ={"VAMS_ENV": "local"}),
            "max_poll_attempts",
            99,
        ),
        (
            lambda: TrailsClient(mock_mode=True, environ={"VAMS_ENV": "local"}),
            "api_url",
            "https://replacement.invalid",
        ),
        (
            lambda: PerformanceAuditLog(
                mock_mode=True,
                environ={"VAMS_ENV": "local"},
            ),
            "mock_mode",
            False,
        ),
    ),
)
def test_effective_component_configuration_rejects_reassignment(
    factory, field, replacement
):
    component = factory()

    with pytest.raises(RuntimeConfigurationError, match="configuration is immutable"):
        setattr(component, field, replacement)
    with pytest.raises(RuntimeConfigurationError, match="configuration is immutable"):
        component._immutable_runtime_fields = frozenset()


def test_audit_configuration_mapping_is_immutable():
    config = {"enabled_protocols": ["celestia", "avail"]}
    audit = PerformanceAuditLog(
        mock_mode=True,
        config=config,
        environ={"VAMS_ENV": "local"},
    )
    config["enabled_protocols"].append("eigenda")

    assert audit._configured_protocols == ("celestia", "avail")
    with pytest.raises(TypeError):
        audit._config["enabled_protocols"] = ("celestia",)


def test_missing_transport_dependency_never_falls_back_to_mock(monkeypatch):
    monkeypatch.setattr(eigenda_module, "requests", None)
    eigenda = EigenDASDK(
        mock_mode=False,
        rpc_url="https://eigenda.invalid/rpc",
        environ={"VAMS_ENV": "testnet"},
    )
    with pytest.raises(EigenDAError, match="provider request failed"):
        eigenda.submit_blob(b"payload")

    monkeypatch.setattr(trails_module, "requests", None)
    trails = TrailsClient(
        mock_mode=False,
        api_url="https://trails.invalid/v1",
        api_key="provider-key",
        environ={"VAMS_ENV": "testnet"},
    )
    with pytest.raises(TrailsError, match="provider submission failed"):
        trails.submit_intent("source", "destination", b"payload")


def test_trails_authentication_failure_is_sanitized_and_never_synthetic(caplog):
    client = TrailsClient(
        mock_mode=False,
        api_url="https://trails.invalid/v1",
        api_key="provider-key",
        environ={"VAMS_ENV": "testnet"},
        transport=FakeTransport(
            [PermissionError("401 Bearer private-provider-token")]
        ),
    )

    with caplog.at_level(logging.ERROR), pytest.raises(
        TrailsError, match="provider submission failed"
    ) as exc_info:
        client.submit_intent("source", "destination", b"payload")

    rendered = str(exc_info.value) + caplog.text
    assert "private-provider-token" not in rendered
    assert "provider-key" not in rendered
    assert "simulated:" not in rendered


@pytest.mark.asyncio
async def test_live_audit_provider_failure_never_falls_back_to_stub(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")
    audit = PerformanceAuditLog(mock_mode=False)

    class FailingLiveAdapter:
        async def submit_blob(self, _data):
            raise TimeoutError("private-provider-detail")

    class TrapStubAdapter:
        called = False

        async def submit_blob(self, _data):
            self.called = True
            raise AssertionError("stub fallback must not run")

    trap = TrapStubAdapter()
    audit.adapters[DAProtocol.CELESTIA] = FailingLiveAdapter()
    audit.adapters[DAProtocol.AVAIL] = trap
    result = await audit.publish_sentinel_report(
        {
            "nodeId": "node",
            "sentinelId": "sentinel",
            "challengeType": "gpu",
            "metricsScore": 1,
            "passed": True,
            "kpis": {},
            "timestamp": 1,
            "duration": 1.0,
        }
    )

    assert result == {
        "success": False,
        "protocol": "celestia",
        "error": "DA submission failed on celestia",
    }
    assert trap.called is False


@pytest.mark.asyncio
async def test_live_audit_consumer_rejects_simulated_adapter_output(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")
    audit = PerformanceAuditLog(mock_mode=False)

    class SimulatedAdapter:
        async def submit_blob(self, _data):
            return DAReceipt(
                protocol=DAProtocol.CELESTIA,
                blob_id="simulated:blob",
                height=1,
                commitment="0x" + "0" * 64,
                simulated=True,
                runtime_classification="non-live",
                evidence_classification="non-authoritative",
            )

    audit.adapters[DAProtocol.CELESTIA] = SimulatedAdapter()
    result = await audit.publish_sentinel_report(
        {
            "nodeId": "node",
            "sentinelId": "sentinel",
            "challengeType": "gpu",
            "metricsScore": 1,
            "passed": True,
            "kpis": {},
            "timestamp": 1,
            "duration": 1.0,
        }
    )

    assert result == {
        "success": False,
        "protocol": "celestia",
        "error": "DA submission failed on celestia",
    }
