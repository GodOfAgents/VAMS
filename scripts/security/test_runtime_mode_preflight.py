from __future__ import annotations

import pytest

from neuron.runtime_safety import LiveModeSafetyError, RuntimeConfigurationError
from scripts.security.runtime_mode_preflight import main, validate_runtime


@pytest.mark.parametrize(
    ("mode", "classification"),
    (
        ("test", "non-live"),
        ("local", "non-live"),
        ("demo", "non-live"),
        ("staging", "live"),
        ("testnet", "live"),
        ("production", "live"),
    ),
)
def test_preflight_reports_the_exact_effective_mode(mode, classification):
    policy = validate_runtime({"VAMS_ENV": mode})
    assert policy.mode.value == mode
    assert policy.runtime_classification == classification


@pytest.mark.parametrize("mode", ("test", "local", "demo"))
def test_deployment_preflight_rejects_every_non_live_mode(mode):
    with pytest.raises(LiveModeSafetyError, match=f"got {mode}"):
        validate_runtime({"VAMS_ENV": mode}, require_live=True)


@pytest.mark.parametrize("mode", ("staging", "testnet", "production"))
def test_deployment_preflight_accepts_exact_live_modes(mode):
    policy = validate_runtime(
        {"VAMS_ENV": mode}, require_live=True, expected_mode=mode
    )
    assert policy.mode.value == mode


def test_expected_mode_mismatch_fails_closed():
    with pytest.raises(LiveModeSafetyError, match="expected testnet, got production"):
        validate_runtime(
            {"VAMS_ENV": "production"},
            require_live=True,
            expected_mode="testnet",
        )


@pytest.mark.parametrize("environment", ({}, {"VAMS_ENV": "Testnet"}, {"VAMS_ENV": " testnet"}))
def test_missing_or_malformed_mode_is_rejected(environment):
    with pytest.raises(RuntimeConfigurationError):
        validate_runtime(environment)


def test_cli_output_is_sanitized(monkeypatch, capsys):
    monkeypatch.setenv("VAMS_ENV", "testnet")
    monkeypatch.setenv("COINME_API_KEY", "must-not-appear")
    assert main(["--require-live", "--expected-mode", "testnet"]) == 0
    output = capsys.readouterr().out
    assert '"mode":"testnet"' in output
    assert '"runtime_classification":"live"' in output
    assert "must-not-appear" not in output


@pytest.mark.parametrize(
    "variable",
    (
        "COINME_MOCK_MODE",
        "BRIDGE_MOCK_MODE",
        "ESCROW_STATE_MOCK_MODE",
        "ANCHOR_MOCK_MODE",
        "OMS_MOCK_MODE",
        "PHALA_MOCK_MODE",
        "AVAIL_MOCK_MODE",
        "EIGENDA_MOCK_MODE",
        "TRAILS_MOCK_MODE",
    ),
)
def test_live_preflight_rejects_registered_component_mock_flags(variable):
    with pytest.raises(RuntimeConfigurationError, match=variable):
        validate_runtime(
            {"VAMS_ENV": "testnet", variable: "true"},
            require_live=True,
            expected_mode="testnet",
        )


def test_live_cli_preflight_rejects_aggregate_mock_configuration(
    monkeypatch, capsys
):
    monkeypatch.setenv("VAMS_ENV", "testnet")
    monkeypatch.setenv("COINME_MOCK_MODE", "true")
    monkeypatch.setenv("BRIDGE_MOCK_MODE", "true")
    monkeypatch.setenv("ESCROW_STATE_MOCK_MODE", "true")
    assert main(["--require-live", "--expected-mode", "testnet"]) == 1
    error = capsys.readouterr().err
    assert "BRIDGE_MOCK_MODE" in error
    assert "testnet" in error
