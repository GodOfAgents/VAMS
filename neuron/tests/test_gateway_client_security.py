import pytest
from urllib.parse import urlunsplit

from neuron.gateway.client import GatewayClient
from neuron.runtime_safety import LiveModeSafetyError


def _credentialed_gateway_url() -> str:
    credentials = ":".join(("fixture-user", "fixture-password"))
    return urlunsplit(("https", f"{credentials}@gateway.example", "", "", ""))


def test_local_gateway_allows_plaintext_loopback(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "local")

    client = GatewayClient("http://127.0.0.1:8000/")

    assert client.base_url == "http://127.0.0.1:8000"


def test_local_gateway_rejects_plaintext_remote_host(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "local")

    with pytest.raises(ValueError, match="restricted to loopback"):
        GatewayClient("http://gateway.example")


def test_legacy_gateway_refuses_live_use_until_m2_client_is_implemented(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")

    for url in ("http://127.0.0.1:8000", "https://gateway.example/"):
        with pytest.raises(LiveModeSafetyError, match="Legacy GatewayClient"):
            GatewayClient(url)


@pytest.mark.parametrize(
    "url",
    ["gateway.example", _credentialed_gateway_url(), ""],
)
def test_gateway_rejects_ambiguous_or_credentialed_urls(monkeypatch, url):
    monkeypatch.setenv("VAMS_ENV", "local")

    with pytest.raises(ValueError, match="host and no userinfo"):
        GatewayClient(url)
