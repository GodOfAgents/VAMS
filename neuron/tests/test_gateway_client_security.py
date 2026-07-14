import pytest

from neuron.gateway.client import GatewayClient


def test_local_gateway_allows_plaintext_loopback(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "local")

    client = GatewayClient("http://127.0.0.1:8000/")

    assert client.base_url == "http://127.0.0.1:8000"


def test_local_gateway_rejects_plaintext_remote_host(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "local")

    with pytest.raises(ValueError, match="restricted to loopback"):
        GatewayClient("http://gateway.example")


def test_live_gateway_requires_https(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")

    with pytest.raises(ValueError, match="must use HTTPS"):
        GatewayClient("http://127.0.0.1:8000")

    assert GatewayClient("https://gateway.example/").base_url == "https://gateway.example"


@pytest.mark.parametrize(
    "url",
    ["gateway.example", "https://example.invalid", ""],
)
def test_gateway_rejects_ambiguous_or_credentialed_urls(monkeypatch, url):
    monkeypatch.setenv("VAMS_ENV", "local")

    with pytest.raises(ValueError, match="host and no userinfo"):
        GatewayClient(url)
