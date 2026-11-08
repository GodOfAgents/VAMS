import asyncio
import importlib
import sys

import pytest

from neuron.anchoring import L1StateAnchor
from neuron.payments.coinme_client import CoinmeClient
from neuron.runtime_safety import (
    LiveModeSafetyError,
    RuntimeConfigurationError,
    load_runtime_policy,
)


def policy(mode: str):
    return load_runtime_policy({"VAMS_ENV": mode})


@pytest.mark.parametrize("mode", ["staging", "testnet", "production"])
def test_anchor_rejects_live_before_submission(mode):
    with pytest.raises(LiveModeSafetyError, match="L1StateAnchor live execution"):
        L1StateAnchor(
            mock_mode=False,
            policy=policy(mode),
            environ={"VAMS_ENV": mode},
        )


def test_anchor_requires_explicit_non_live_simulation_and_marks_receipt():
    with pytest.raises(LiveModeSafetyError, match="no authoritative"):
        L1StateAnchor(policy=policy("demo"), environ={"VAMS_ENV": "demo"})

    anchor = L1StateAnchor(
        mock_mode=True,
        policy=policy("demo"),
        environ={"VAMS_ENV": "demo"},
    )
    receipt = anchor.submit_anchor("0x" + "12" * 32, 2)
    assert receipt.simulated is True
    assert receipt.tx_hash.startswith("simulated:sha256:")
    assert not receipt.tx_hash.startswith("0x")


@pytest.mark.parametrize("mode", ["test", "local", "staging", "testnet", "production"])
def test_demo_cli_requires_exact_demo_mode(monkeypatch, mode):
    demo_cli = importlib.import_module("neuron.demo_cli")
    monkeypatch.setenv("VAMS_ENV", mode)
    with pytest.raises(LiveModeSafetyError, match="explicit VAMS_ENV=demo"):
        demo_cli.ImmortalAgentDemo(policy=policy(mode))


def test_demo_cli_has_non_authoritative_synthetic_identifiers(monkeypatch):
    demo_cli = importlib.import_module("neuron.demo_cli")
    monkeypatch.setenv("VAMS_ENV", "demo")
    assert demo_cli.DEMO_AGENT_ID.startswith("simulated:agent:")
    demo = demo_cli.ImmortalAgentDemo(
        workflow_id="synthetic-test",
        enable_crash=False,
        policy=policy("demo"),
    )
    trade = demo._step_execute_trade()
    assert trade["tx_hash"].startswith("simulated:sha256:")
    assert trade["chain"] == "Polygon CDK (simulated)"


@pytest.mark.parametrize("mode", ["staging", "testnet", "production"])
def test_legacy_gateway_rejects_live_before_lifespan_yield(monkeypatch, mode):
    legacy = importlib.import_module("neuron.gateway.server")
    monkeypatch.setenv("VAMS_ENV", mode)
    legacy.app.state.startup_policy = policy(mode)

    async def enter_lifespan():
        async with legacy.lifespan(legacy.app):
            raise AssertionError("live legacy gateway accepted traffic")

    with pytest.raises(LiveModeSafetyError, match="Legacy neuron gateway"):
        asyncio.run(enter_lifespan())


def test_legacy_gateway_non_live_classification_is_sanitized(monkeypatch):
    legacy = importlib.import_module("neuron.gateway.server")
    monkeypatch.setenv("VAMS_ENV", "test")
    legacy.app.state.startup_policy = policy("test")

    async def enter_lifespan():
        async with legacy.lifespan(legacy.app):
            result = legacy.home()
            assert result["mode"] == "test"
            assert result["runtime_classification"] == "non-live"
            assert result["evidence_classification"] == "non-authoritative"

    asyncio.run(enter_lifespan())


@pytest.mark.parametrize("raw_mode", [None, "prod", "Testnet", " testnet"])
def test_legacy_gateway_rejects_missing_or_malformed_mode_before_yield(
    monkeypatch, raw_mode
):
    legacy = importlib.import_module("neuron.gateway.server")
    legacy.app.state._state.pop("startup_policy", None)
    if raw_mode is None:
        monkeypatch.delenv("VAMS_ENV", raising=False)
    else:
        monkeypatch.setenv("VAMS_ENV", raw_mode)

    async def enter_lifespan():
        async with legacy.lifespan(legacy.app):
            raise AssertionError("invalid-mode legacy gateway accepted traffic")

    with pytest.raises(RuntimeConfigurationError, match="VAMS_ENV"):
        asyncio.run(enter_lifespan())


def test_public_client_rejects_policy_environment_rebinding(monkeypatch):
    supplied = policy("test")
    monkeypatch.setenv("VAMS_ENV", "production")
    with pytest.raises(RuntimeConfigurationError, match="Conflicting runtime policy"):
        CoinmeClient(mock_mode=True, policy=supplied)


def test_legacy_gateway_rejects_policy_environment_rebinding(monkeypatch):
    legacy = importlib.import_module("neuron.gateway.server")
    legacy.app.state.startup_policy = policy("test")
    monkeypatch.setenv("VAMS_ENV", "production")

    async def enter_lifespan():
        async with legacy.lifespan(legacy.app):
            raise AssertionError("conflicting gateway policy reached lifespan yield")

    with pytest.raises(RuntimeConfigurationError, match="Conflicting runtime policy"):
        asyncio.run(enter_lifespan())


@pytest.mark.parametrize("branch", ["--comms", "--route", "--x402"])
@pytest.mark.parametrize("mode", ["test", "local", "staging", "testnet", "production"])
def test_neuron_simulation_branches_require_explicit_demo(monkeypatch, branch, mode):
    neuron_entry = importlib.import_module("neuron.neuron")
    monkeypatch.setenv("VAMS_ENV", mode)
    monkeypatch.setattr(sys, "argv", ["neuron.py", branch])
    with pytest.raises(LiveModeSafetyError, match="requires explicit VAMS_ENV=demo"):
        neuron_entry.main()


@pytest.mark.parametrize("mode", ["staging", "testnet", "production"])
def test_neuron_legacy_gateway_branch_rejects_before_server_import(
    monkeypatch, mode
):
    neuron_entry = importlib.import_module("neuron.neuron")
    monkeypatch.setenv("VAMS_ENV", mode)
    monkeypatch.setattr(sys, "argv", ["neuron.py", "--gateway-server"])
    with pytest.raises(LiveModeSafetyError, match="Legacy neuron gateway"):
        neuron_entry.main()


def test_executable_demo_modules_do_not_self_select_runtime_mode():
    root = __import__("pathlib").Path(__file__).resolve().parents[2]
    for relative in (
        "neuron/demo_cli.py",
        "neuron/sdk/iagon_storage.py",
        "neuron/sdk/akash_orchestrator.py",
    ):
        text = (root / relative).read_text(encoding="utf-8")
        assert 'os.environ["VAMS_ENV"]' not in text
        assert 'os.environ["IAGON_MOCK_MODE"]' not in text
        assert 'os.environ["AKASH_MOCK_MODE"]' not in text
