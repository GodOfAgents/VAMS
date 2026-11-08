import pytest

from neuron.runtime_safety import (
    REGISTERED_MOCK_VARIABLES,
    RuntimeConfigurationError,
    RuntimeMode,
    RuntimePolicy,
    resolve_component_mock_mode,
)


EXPECTED_M1_MOCK_FLAGS = (
    "VAMS_MOCK_MODE",
    "AKASH_MOCK_MODE",
    "ANCHOR_MOCK_MODE",
    "AVAIL_ADAPTER_MOCK_MODE",
    "AVAIL_MOCK_MODE",
    "BRIDGE_ISM_MOCK_MODE",
    "BRIDGE_MOCK_MODE",
    "CELESTIA_LIGHT_MOCK_MODE",
    "COGNITIVE_SYNC_MOCK_MODE",
    "COINME_MOCK_MODE",
    "DA_ROUTER_MOCK_MODE",
    "EIGENDA_ADAPTER_MOCK_MODE",
    "EIGENDA_MOCK_MODE",
    "ESCROW_STATE_MOCK_MODE",
    "IAGON_MOCK_MODE",
    "MEV_MOCK_MODE",
    "NEURON_MOCK_MODE",
    "OMS_MOCK_MODE",
    "PAYMENT_CHANNEL_MOCK_MODE",
    "PHALA_MOCK_MODE",
    "SENTINEL_MOCK_MODE",
    "TRAILS_MOCK_MODE",
    "VAMS_IVT_MOCK",
    "X402_MOCK_MODE",
    "X402_RECOVERY_MOCK_MODE",
)


@pytest.mark.parametrize(
    ("mode", "is_live", "evidence"),
    [
        ("test", False, "non-authoritative"),
        ("local", False, "non-authoritative"),
        ("demo", False, "non-authoritative"),
        ("staging", True, "runtime-mode-only"),
        ("testnet", True, "runtime-mode-only"),
        ("production", True, "runtime-mode-only"),
    ],
)
def test_every_canonical_runtime_mode(mode, is_live, evidence):
    policy = RuntimePolicy.from_environment({"VAMS_ENV": mode})

    assert policy.mode is RuntimeMode(mode)
    assert policy.is_live is is_live
    assert policy.evidence_classification == evidence


@pytest.mark.parametrize(
    "environment",
    [
        {},
        {"VAMS_ENV": ""},
        {"VAMS_ENV": "   "},
        {"VAMS_ENV": " testnet"},
        {"VAMS_ENV": "testnet "},
        {"VAMS_ENV": "Testnet"},
        {"VAMS_ENV": "PRODUCTION"},
        {"VAMS_ENV": "preview"},
    ],
)
def test_missing_unknown_or_malformed_modes_fail_closed(environment):
    with pytest.raises(RuntimeConfigurationError, match="VAMS_ENV"):
        RuntimePolicy.from_environment(environment)


def test_live_gateway_mock_configuration_is_a_conflict():
    with pytest.raises(
        RuntimeConfigurationError,
        match=r"VAMS_MOCK_MODE=true.*VAMS_ENV=testnet",
    ):
        RuntimePolicy.from_environment(
            {"VAMS_ENV": "testnet", "VAMS_MOCK_MODE": "true"}
        )


@pytest.mark.parametrize("mode", ["test", "local", "demo"])
def test_gateway_mock_is_allowed_only_in_explicit_non_live_modes(mode):
    policy = RuntimePolicy.from_environment(
        {"VAMS_ENV": mode, "VAMS_MOCK_MODE": "true"}
    )

    assert policy.gateway_mock_enabled is True
    assert policy.is_live is False
    assert policy.evidence_classification == "non-authoritative"


@pytest.mark.parametrize("mode", ["staging", "testnet", "production"])
def test_gateway_mock_is_rejected_in_every_live_mode(mode):
    with pytest.raises(RuntimeConfigurationError, match=mode):
        RuntimePolicy.from_environment(
            {"VAMS_ENV": mode, "VAMS_MOCK_MODE": "true"}
        )


@pytest.mark.parametrize("value", ["", " true", "true ", "TRUE", "1", "yes"])
def test_gateway_mock_flag_is_strict(value):
    with pytest.raises(RuntimeConfigurationError, match="VAMS_MOCK_MODE"):
        RuntimePolicy.from_environment(
            {"VAMS_ENV": "test", "VAMS_MOCK_MODE": value}
        )


def test_demo_is_explicit_and_is_not_inferred_from_credentials_or_provider_state():
    local = RuntimePolicy.from_environment(
        {
            "VAMS_ENV": "local",
            "COINME_API_KEY": "demo" + "-key",
            "OMS_API_KEY": "placeholder",
            "PROVIDER_FAILURE": "true",
        }
    )
    assert local.mode is RuntimeMode.LOCAL
    assert local.is_demo is False

    demo = RuntimePolicy.from_environment(
        {"VAMS_ENV": "demo", "VAMS_MOCK_MODE": "true"}
    )
    assert demo.mode is RuntimeMode.DEMO
    assert demo.is_demo is True

    with pytest.raises(RuntimeConfigurationError, match="VAMS_ENV is required"):
        RuntimePolicy.from_environment(
            {"COINME_API_KEY": "demo" + "-key", "PROVIDER_FAILURE": "true"}
        )


def test_runtime_policy_is_immutable():
    policy = RuntimePolicy.from_environment({"VAMS_ENV": "test"})

    with pytest.raises(AttributeError):
        policy.gateway_mock_enabled = True


def test_registered_mock_flag_contract_is_complete_and_stable():
    assert REGISTERED_MOCK_VARIABLES == EXPECTED_M1_MOCK_FLAGS


@pytest.mark.parametrize("variable", EXPECTED_M1_MOCK_FLAGS)
@pytest.mark.parametrize("mode", ["staging", "testnet", "production"])
def test_every_registered_mock_flag_fails_closed_in_live_modes(variable, mode):
    with pytest.raises(RuntimeConfigurationError, match=variable):
        RuntimePolicy.from_environment({"VAMS_ENV": mode, variable: "true"})


def test_supplied_policy_cannot_rebind_a_conflicting_process_environment():
    test_policy = RuntimePolicy.from_environment({"VAMS_ENV": "test"})
    with pytest.raises(RuntimeConfigurationError, match="Conflicting runtime policy"):
        resolve_component_mock_mode(
            "CoinmeClient",
            "COINME_MOCK_MODE",
            True,
            policy=test_policy,
            environ={"VAMS_ENV": "production"},
        )


def test_supplied_policy_cannot_hide_a_registered_mock_flag():
    test_policy = RuntimePolicy.from_environment({"VAMS_ENV": "test"})
    with pytest.raises(RuntimeConfigurationError, match="Conflicting runtime policy"):
        resolve_component_mock_mode(
            "CoinmeClient",
            "COINME_MOCK_MODE",
            True,
            policy=test_policy,
            environ={"VAMS_ENV": "test", "COINME_MOCK_MODE": "true"},
        )
