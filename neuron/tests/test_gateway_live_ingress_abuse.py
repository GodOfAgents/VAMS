"""Live Envoy-to-Gateway checks for remote clients, rate limiting and abuse limits.

Envoy listens on this host's non-loopback IPv4 address, so a connection from
that address looks like a remote client: it is not loopback and Envoy writes it
into X-Forwarded-For. Distinct loopback source addresses (127.0.x.y) stand in
for distinct clients. Certificates, keys and the replay store are temporary and
local-only; no request bytes or authentication values are printed.
"""

from __future__ import annotations

import os
import re
import socket
import ssl
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import neuron.tests.test_m2_4b_envoy_ingress as base
from gateway.route_security import (
    TRUSTED_INGRESS_VALUE,
    _validate_trusted_ingress,
    trusted_ingress_client,
)
from neuron.runtime_safety import RuntimeMode, RuntimePolicy
from neuron.tests.m2_gateway_helpers import AUDIENCE, PUBLIC_KEY, signed_headers


RATE_LIMIT = 5


def _external_ipv4() -> str | None:
    try:
        out = subprocess.check_output(("ip", "-4", "-o", "addr", "show"), text=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    for line in out.splitlines():
        fields = line.split()
        if len(fields) > 3:
            address = fields[3].split("/")[0]
            if not address.startswith("127."):
                return address
    return None


class LiveIngress:
    def __init__(self, root: Path, address: str, listener: int):
        self.root = root
        self.address = address
        self.listener = listener

    def send(
        self,
        wire: bytes,
        *,
        source: str,
        certificate: tuple[Path, Path] | None | bool = True,
        tls_max: ssl.TLSVersion | None = None,
        pause_after: int | None = None,
        pause: float = 0.0,
    ) -> int | str:
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(self.root / "ca.crt"))
        if tls_max is not None:
            context.minimum_version = ssl.TLSVersion.MINIMUM_SUPPORTED
            context.maximum_version = tls_max
            context.set_ciphers("DEFAULT:@SECLEVEL=0")
        if certificate is True:
            context.load_cert_chain(self.root / "client.crt", self.root / "client.key")
        elif certificate:
            context.load_cert_chain(*certificate)
        try:
            raw = socket.create_connection((self.address, self.listener), timeout=4, source_address=(source, 0))
            with context.wrap_socket(raw, server_hostname="localhost") as tls:
                tls.settimeout(4)
                if pause_after is not None:
                    tls.sendall(wire[:pause_after])
                    time.sleep(pause)
                    try:
                        tls.sendall(wire[pause_after:])
                    except OSError:
                        pass
                else:
                    tls.sendall(wire)
                data = b""
                while True:
                    try:
                        chunk = tls.recv(65536)
                    except (socket.timeout, ssl.SSLError, OSError):
                        break
                    if not chunk:
                        break
                    data += chunk
        except ssl.SSLError:
            return "tls-refused"
        except OSError:
            return "connection-refused"
        match = re.match(rb"HTTP/\d(?:\.\d)? (\d{3})", data)
        return int(match.group(1)) if match else "no-response"


@pytest.fixture(scope="module")
def live_ingress(tmp_path_factory):
    if not base.ENVOY.is_file():
        pytest.skip("verified Envoy 1.39.1 runtime is not available")
    address = _external_ipv4()
    if address is None:
        pytest.skip("no non-loopback IPv4 address to stand in for a remote client")
    root = tmp_path_factory.mktemp("gateway-live-ingress")
    os.chmod(root, 0o700)
    fingerprint = base._make_certs(root)
    listener, upstream = base._free_port(), base._free_port()
    config = base._render_config(root, listener, upstream)
    text = config.read_text()
    loopback_listener = f"address: 127.0.0.1, port_value: {listener}"
    assert text.count(loopback_listener) == 1
    config.write_text(text.replace(loopback_listener, f"address: {address}, port_value: {listener}"))
    subprocess.run((str(base.ENVOY), "--mode", "validate", "-c", str(config)), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    environment = os.environ.copy()
    environment.update({
        "VAMS_ENV": "testnet",
        "GATEWAY_ADMIN_PASSWORD": "LiveIngressLocalOnly!",
        "GATEWAY_ADMIN_DID": "did:key:" + PUBLIC_KEY.hex(),
        "GATEWAY_AUTH_AUDIENCE": AUDIENCE,
        "GATEWAY_AUTH_REPLAY_DB": str(root / "replay.sqlite3"),
        "GATEWAY_ALLOWED_ORIGINS": "https://gateway.example",
        "GATEWAY_HEARTBEAT_CERT_FINGERPRINTS": fingerprint,
        "GATEWAY_RATE_LIMIT": f"{RATE_LIMIT}/600",
    })
    for name in tuple(environment):
        if name.endswith("_MOCK_MODE") or name == "VAMS_IVT_MOCK":
            environment[name] = "false"
    uvicorn = base._start_uvicorn(upstream, environment)
    envoy = subprocess.Popen(
        (str(base.ENVOY), "-c", str(config), "--disable-hot-restart", "--concurrency", "1", "--log-level", "warning"),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 10
    while True:
        if envoy.poll() is not None:
            raise RuntimeError("envoy exited before readiness")
        with socket.socket() as probe:
            probe.settimeout(0.1)
            if probe.connect_ex((address, listener)) == 0:
                break
        if time.monotonic() > deadline:
            raise RuntimeError("envoy readiness timeout")
        time.sleep(0.025)
    try:
        yield LiveIngress(root, address, listener)
    finally:
        for process in (envoy, uvicorn):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


HEALTH = base._request_bytes("GET", "/health", {})


def test_remote_client_reaches_public_and_signed_routes(live_ingress):
    # Before the fix Uvicorn replaced the peer with this address and the
    # gateway refused it as untrusted_ingress_peer (403).
    assert live_ingress.send(HEALTH, source=live_ingress.address) == 200
    headers = signed_headers("GET", "/nodes", nonce=7101)
    assert live_ingress.send(base._request_bytes("GET", "/nodes", headers), source=live_ingress.address) == 200


def test_rate_limit_is_per_client_behind_envoy(live_ingress):
    statuses = [live_ingress.send(HEALTH, source="127.0.0.21") for _ in range(RATE_LIMIT + 1)]
    assert statuses == [200] * RATE_LIMIT + [429]
    assert live_ingress.send(HEALTH, source="127.0.0.22") == 200


def test_spoofed_forwarded_for_does_not_escape_the_limit(live_ingress):
    for _ in range(RATE_LIMIT):
        assert live_ingress.send(HEALTH, source="127.0.0.23") == 200
    spoofed = base._request_bytes("GET", "/health", {}, extra=(("X-Forwarded-For", "198.51.100.7"),))
    assert live_ingress.send(spoofed, source="127.0.0.23") == 429


def test_rejected_authentication_counts_against_the_limit(live_ingress):
    for nonce in range(7201, 7201 + RATE_LIMIT):
        headers = signed_headers("GET", "/nodes", nonce=nonce)
        signature = headers["X-VAMS-Auth-Signature"]
        headers["X-VAMS-Auth-Signature"] = signature[:-1] + ("0" if signature[-1] != "0" else "1")
        assert live_ingress.send(base._request_bytes("GET", "/nodes", headers), source="127.0.0.24") == 401
    assert live_ingress.send(HEALTH, source="127.0.0.24") == 429


def _wrong_ca_certificate(root: Path) -> tuple[Path, Path]:
    folder = root / "wrong-ca"
    if not folder.exists():
        folder.mkdir()
        subprocess.run(
            ("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
             "-subj", "/CN=Unrelated CA", "-keyout", "key.pem", "-out", "cert.pem"),
            cwd=folder, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    return folder / "cert.pem", folder / "key.pem"


OVERSIZED_BODY = b'{"a":"' + b"x" * (1_048_576 + 16) + b'"}'
# The handshake refusal can surface as a TLS alert, a reset or a silent close,
# depending on timing; what matters is that no HTTP response is returned.
NO_HTTP = "no-http-response"

ABUSE_CASES = [
    ("no_client_certificate", dict(certificate=None), HEALTH, NO_HTTP),
    ("wrong_ca_certificate", dict(certificate="wrong"), HEALTH, NO_HTTP),
    ("tls_1_1", dict(tls_max=ssl.TLSVersion.TLSv1_1), HEALTH, ("tls-refused",)),
    ("body_over_1_mib", {}, base._request_bytes("POST", "/heartbeat", {"Content-Type": "application/json"}, OVERSIZED_BODY), (413,)),
    ("header_over_16_kib", {}, base._request_bytes("GET", "/health", {"X-Big": "y" * 17_000}), (431,)),
    ("over_100_headers", {}, base._request_bytes("GET", "/health", {f"X-H{i}": "v" for i in range(101)}), (431,)),
    ("underscore_header", {}, base._request_bytes("GET", "/health", {"X_Spoof": "v"}), (400,)),
    ("trace_method", {}, base._request_bytes("TRACE", "/health", {}), (405,)),
    ("http_1_0", {}, b"GET /health HTTP/1.0\r\nHost: localhost\r\n\r\n", (426,)),
    ("escaped_slash", {}, base._request_bytes("GET", "/nodes%2Fx", {}), (400,)),
    ("slow_headers", dict(pause_after=20, pause=3.0), HEALTH, (408,)),
]


@pytest.mark.parametrize(
    ("index", "case"), list(enumerate(ABUSE_CASES)), ids=[case[0] for case in ABUSE_CASES]
)
def test_envoy_abuse_limits(live_ingress, index, case):
    _name, options, wire, expected = case
    options = dict(options)
    if options.get("certificate") == "wrong":
        options["certificate"] = _wrong_ca_certificate(live_ingress.root)
    result = live_ingress.send(wire, source=f"127.0.1.{index + 1}", **options)
    if expected == NO_HTTP:
        assert not isinstance(result, int), result
    else:
        assert result in expected


# --- Unit checks of the trust rules ---------------------------------------

LIVE = RuntimePolicy(mode=RuntimeMode.TESTNET, gateway_mock_enabled=False)


def _scope(client, headers):
    return {
        "type": "http",
        "client": client,
        "headers": headers,
        "app": SimpleNamespace(state=SimpleNamespace(runtime_policy=LIVE)),
    }


MARKER = (b"x-vams-ingress-version", TRUSTED_INGRESS_VALUE)


@pytest.mark.parametrize(
    ("client", "headers", "expected"),
    [
        (("127.0.0.1", 1), [MARKER, (b"x-forwarded-for", b"203.0.113.9")], "203.0.113.9"),
        (("127.0.0.1", 1), [MARKER, (b"x-forwarded-for", b"2001:db8::1")], "2001:db8::1"),
        (("127.0.0.1", 1), [(b"x-forwarded-for", b"203.0.113.9")], None),
        (("127.0.0.1", 1), [MARKER], None),
        (("127.0.0.1", 1), [MARKER, (b"x-forwarded-for", b"203.0.113.9"), (b"x-forwarded-for", b"198.51.100.1")], None),
        (("127.0.0.1", 1), [MARKER, (b"x-forwarded-for", b"203.0.113.9, 198.51.100.1")], None),
        (("127.0.0.1", 1), [MARKER, (b"x-forwarded-for", b"not-an-ip")], None),
        (("192.0.2.10", 1), [MARKER, (b"x-forwarded-for", b"203.0.113.9")], None),
        (None, [MARKER, (b"x-forwarded-for", b"203.0.113.9")], None),
    ],
)
def test_trusted_ingress_client_only_trusts_the_envoy_assertion(client, headers, expected):
    assert trusted_ingress_client(_scope(client, headers)) == expected


def test_proxy_header_rewrite_is_named_and_still_refused():
    rewritten = _scope(("203.0.113.9", 4444), [MARKER, (b"x-forwarded-for", b"203.0.113.9")])
    assert _validate_trusted_ingress(rewritten) == "ingress_peer_rewritten_by_proxy_headers"
    unrelated = _scope(("203.0.113.9", 4444), [MARKER, (b"x-forwarded-for", b"198.51.100.1")])
    assert _validate_trusted_ingress(unrelated) == "untrusted_ingress_peer"


@pytest.fixture
def server(monkeypatch):
    # gateway.server reads VAMS_ENV at import; import it under the test profile.
    monkeypatch.setenv("VAMS_ENV", "test")
    monkeypatch.setenv("GATEWAY_ADMIN_PASSWORD", os.environ.get("GATEWAY_ADMIN_PASSWORD", "LiveIngressLocalOnly!"))
    from gateway import server as module

    return module


def test_gateway_main_disables_uvicorn_proxy_headers(server, monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")
    with patch("gateway.server.uvicorn.run") as run:
        server.main()
    assert run.call_args.kwargs["proxy_headers"] is False
    assert run.call_args.kwargs["host"] == "127.0.0.1"


def test_rate_limiter_runs_before_route_security(server):
    from gateway.route_security import GatewayRouteSecurityMiddleware

    order = [entry.cls for entry in server.app.user_middleware]  # outermost first
    assert order.index(server.RateLimitMiddleware) < order.index(GatewayRouteSecurityMiddleware)


def test_rate_limiter_bounds_bucket_count(server):
    limiter = server.RateLimitMiddleware(app=None, limit=3, window_sec=60)
    limiter.MAX_BUCKETS = 4
    now = time.time()
    limiter.buckets = {f"client:198.51.100.{i}": {"tokens": 3.0, "last_refill": now} for i in range(4)}

    async def call_next(_request):
        from starlette.responses import PlainTextResponse
        return PlainTextResponse("ok")

    import asyncio
    from starlette.requests import Request

    request = Request({"type": "http", "client": ("10.9.9.9", 1), "headers": [], "method": "GET", "path": "/"})
    response = asyncio.run(limiter.dispatch(request, call_next))
    assert response.status_code == 200
    assert len(limiter.buckets) == 5
    assert limiter.OVERFLOW_KEY in limiter.buckets
