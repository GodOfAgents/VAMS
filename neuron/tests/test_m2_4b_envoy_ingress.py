"""R5 integration checks for the reviewed Envoy-to-Gateway boundary.

The raw cases are the selected, sanitized M2.4b-R3/R4 fixtures. They are kept
in memory only; test output never includes request bytes or authentication
values.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import ssl
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from gateway.route_security import GatewayRouteSecurityMiddleware, TRUSTED_INGRESS_VALUE
from neuron.runtime_safety import RuntimeMode, RuntimePolicy
from neuron.secp256k1 import sign_message
from neuron.tests.m2_gateway_helpers import (
    AUDIENCE,
    PRIVATE_KEY,
    PUBLIC_KEY,
    compact_json,
    signed_headers,
)


ROOT = Path(__file__).resolve().parents[2]
ENVOY = Path(
    os.environ.get(
        "VAMS_ENVOY_BIN",
        "/home/GodOfAgents/vams-evidence/toolchains/envoy-1.39.1/envoy",
    )
)
ENVOY_SHA256 = "002c6e1c69ed0fa0ea381887247cadadfaec9481375fa8d8d2b1731eeabf40b8"
PYTHON = Path(os.environ.get("VAMS_TEST_PYTHON", os.sys.executable))


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_port(process: subprocess.Popen, port: int) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("local ingress process exited before readiness")
        with socket.socket() as sock:
            sock.settimeout(0.1)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.025)
    raise RuntimeError("local ingress readiness timeout")


def _make_certs(root: Path) -> str:
    (root / "server.ext").write_text(
        "basicConstraints=critical,CA:FALSE\n"
        "keyUsage=critical,digitalSignature,keyEncipherment\n"
        "extendedKeyUsage=serverAuth\nsubjectAltName=DNS:localhost\n"
    )
    (root / "client.ext").write_text(
        "basicConstraints=critical,CA:FALSE\n"
        "keyUsage=critical,digitalSignature,keyEncipherment\n"
        "extendedKeyUsage=clientAuth\n"
    )
    commands = (
        ("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=VAMS R5 CA", "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign", "-keyout", "ca.key", "-out", "ca.crt"),
        ("req", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=localhost", "-keyout", "server.key", "-out", "server.csr"),
        ("x509", "-req", "-days", "1", "-in", "server.csr", "-CA", "ca.crt", "-CAkey", "ca.key", "-CAcreateserial", "-extfile", "server.ext", "-out", "server.crt"),
        ("req", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=VAMS R5 Client", "-keyout", "client.key", "-out", "client.csr"),
        ("x509", "-req", "-days", "1", "-in", "client.csr", "-CA", "ca.crt", "-CAkey", "ca.key", "-CAcreateserial", "-extfile", "client.ext", "-out", "client.crt"),
    )
    for command in commands:
        subprocess.run(
            ("openssl", *command),
            cwd=root,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    der = ssl.PEM_cert_to_DER_cert((root / "client.crt").read_text())
    return hashlib.sha256(der).hexdigest()


def _render_config(root: Path, listener: int, upstream: int) -> Path:
    text = (ROOT / "gateway" / "envoy.testnet.yaml").read_text()
    replacements = {
        "address: 0.0.0.0, port_value: 8443": f"address: 127.0.0.1, port_value: {listener}",
        "address: 127.0.0.1, port_value: 8000": f"address: 127.0.0.1, port_value: {upstream}",
        "/etc/vams/gateway/tls/server.crt": str(root / "server.crt"),
        "/etc/vams/gateway/tls/server.key": str(root / "server.key"),
        "/etc/vams/gateway/tls/client-ca.crt": str(root / "ca.crt"),
    }
    for before, after in replacements.items():
        assert text.count(before) == 1
        text = text.replace(before, after)
    path = root / "envoy.yaml"
    path.write_text(text)
    return path


def _request_bytes(
    method: str,
    target: str,
    headers: dict[str, str],
    body: bytes = b"",
    *,
    extra: tuple[tuple[str, str], ...] = (),
    ows: bool = False,
) -> bytes:
    values = [("Host", "localhost"), *headers.items(), *extra]
    lower = {name.lower() for name, _ in values}
    if body and "content-length" not in lower and "transfer-encoding" not in lower:
        values.append(("Content-Length", str(len(body))))
    values.append(("Connection", "close"))
    separator = ":   " if ows else ": "
    head = method + " " + target + " HTTP/1.1\r\n"
    head += "".join(name + separator + value + "\r\n" for name, value in values)
    return head.encode("ascii") + b"\r\n" + body


def _status(raw: bytes) -> int:
    match = re.match(rb"HTTP/\d(?:\.\d)? (\d{3})", raw)
    assert match is not None
    return int(match.group(1))


def _json_body(raw: bytes) -> dict:
    return json.loads(raw.split(b"\r\n\r\n", 1)[1])


class Harness:
    def __init__(self, root: Path, envoy: subprocess.Popen, uvicorn: subprocess.Popen, listener: int, upstream: int):
        self.root = root
        self.envoy = envoy
        self.uvicorn = uvicorn
        self.listener = listener
        self.upstream = upstream

    def send(self, wire: bytes, *, certificate: bool = True) -> bytes:
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(self.root / "ca.crt"))
        if certificate:
            context.load_cert_chain(self.root / "client.crt", self.root / "client.key")
        with socket.create_connection(("127.0.0.1", self.listener), timeout=3) as raw:
            with context.wrap_socket(raw, server_hostname="localhost") as tls:
                tls.settimeout(3)
                tls.sendall(wire)
                chunks = []
                while True:
                    try:
                        chunk = tls.recv(65536)
                    except (socket.timeout, ssl.SSLError):
                        break
                    if not chunk:
                        break
                    chunks.append(chunk)
        return b"".join(chunks)

    def restart_gateway(self, environment: dict[str, str]) -> None:
        self.uvicorn.terminate()
        self.uvicorn.wait(timeout=5)
        self.uvicorn = _start_uvicorn(self.upstream, environment)


def _start_uvicorn(port: int, environment: dict[str, str]) -> subprocess.Popen:
    process = subprocess.Popen(
        (
            str(PYTHON),
            "-m",
            "uvicorn",
            "gateway.server:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
            "--log-level",
            "warning",
        ),
        cwd=ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_port(process, port)
    return process


@pytest.fixture(scope="module")
def live_envoy_gateway(tmp_path_factory):
    if not ENVOY.is_file():
        pytest.skip("verified Envoy 1.39.1 runtime is not available")
    assert hashlib.sha256(ENVOY.read_bytes()).hexdigest() == ENVOY_SHA256
    version = subprocess.check_output((str(ENVOY), "--version"), text=True)
    assert "/1.39.1/Clean/RELEASE/BoringSSL" in version

    root = tmp_path_factory.mktemp("m2-4b-r5")
    os.chmod(root, 0o700)
    fingerprint = _make_certs(root)
    listener, upstream = _free_port(), _free_port()
    config = _render_config(root, listener, upstream)
    subprocess.run((str(ENVOY), "--mode", "validate", "-c", str(config)), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    environment = os.environ.copy()
    environment.update(
        {
            "VAMS_ENV": "testnet",
            "GATEWAY_ADMIN_PASSWORD": "R5LocalOnlyPassword!",
            "GATEWAY_ADMIN_DID": "did:key:" + PUBLIC_KEY.hex(),
            "GATEWAY_AUTH_AUDIENCE": AUDIENCE,
            "GATEWAY_AUTH_REPLAY_DB": str(root / "replay.sqlite3"),
            "GATEWAY_ALLOWED_ORIGINS": "https://gateway.example",
            "GATEWAY_HEARTBEAT_CERT_FINGERPRINTS": fingerprint,
        }
    )
    for name in tuple(environment):
        if name.endswith("_MOCK_MODE") or name == "VAMS_IVT_MOCK":
            environment[name] = "false"

    uvicorn = _start_uvicorn(upstream, environment)
    envoy = subprocess.Popen(
        (str(ENVOY), "-c", str(config), "--disable-hot-restart", "--concurrency", "1", "--log-level", "warning"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_port(envoy, listener)
    harness = Harness(root, envoy, uvicorn, listener, upstream)
    harness.environment = environment
    try:
        yield harness
    finally:
        for process in (harness.envoy, harness.uvicorn):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def _heartbeat_body(block_height: int) -> bytes:
    payload = compact_json(
        {
            "node_id": "r5-synthetic-node",
            "block_height": block_height,
            "public_key": PUBLIC_KEY.hex(),
        }
    ).decode()
    return compact_json(
        {"payload": payload, "signature": sign_message(PRIVATE_KEY, payload.encode()).hex()}
    )


def test_canonical_mtls_request_executes_once_and_replay_survives_restart(live_envoy_gateway):
    body = _heartbeat_body(1)
    headers = signed_headers("POST", "/heartbeat", body=body, nonce=401)
    first = live_envoy_gateway.send(_request_bytes("POST", "/heartbeat", headers, body))
    assert _status(first) == 200
    assert _json_body(first)["heartbeat_count"] == 1
    assert _status(live_envoy_gateway.send(_request_bytes("POST", "/heartbeat", headers, body))) == 401
    live_envoy_gateway.restart_gateway(live_envoy_gateway.environment)
    assert _status(live_envoy_gateway.send(_request_bytes("POST", "/heartbeat", headers, body))) == 401


def test_selected_framing_case_is_rejected_without_nonce_or_extra_execution(live_envoy_gateway):
    body = _heartbeat_body(2)
    headers = signed_headers("POST", "/heartbeat", body=body, nonce=402)
    head = _request_bytes(
        "POST",
        "/heartbeat",
        headers,
        b"",
        extra=(("Content-Length", "5"), ("Transfer-Encoding", "chunked")),
    ).rsplit(b"\r\n\r\n", 1)[0]
    chunked = f"{len(body):X}\r\n".encode() + body + b"\r\n0\r\n\r\n"
    suffix = b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
    rejected = live_envoy_gateway.send(head + b"\r\n\r\n" + chunked + suffix)
    assert _status(rejected) >= 400
    accepted = live_envoy_gateway.send(_request_bytes("POST", "/heartbeat", headers, body))
    assert _status(accepted) == 200
    assert _json_body(accepted)["heartbeat_count"] == 1


def test_obsolete_fold_is_one_semantic_request_and_same_replay_identity(live_envoy_gateway):
    headers = signed_headers("GET", "/nodes", nonce=403)
    wire = _request_bytes("GET", "/nodes", headers, extra=(("X-Probe", "one\r\n two"),))
    assert _status(live_envoy_gateway.send(wire)) == 200
    assert _status(live_envoy_gateway.send(_request_bytes("GET", "/nodes", headers))) == 401


def test_security_header_fold_changes_meaning_and_does_not_consume_nonce(live_envoy_gateway):
    headers = signed_headers("GET", "/nodes", nonce=404)
    headers["X-VAMS-Auth-Version"] += "\r\n changed"
    assert _status(live_envoy_gateway.send(_request_bytes("GET", "/nodes", headers))) == 401
    clean = signed_headers("GET", "/nodes", nonce=404)
    assert _status(live_envoy_gateway.send(_request_bytes("GET", "/nodes", clean))) == 200


def test_equivalent_ows_preserves_authentication_and_duplicate_auth_fails(live_envoy_gateway):
    headers = signed_headers("GET", "/nodes", nonce=405)
    assert _status(live_envoy_gateway.send(_request_bytes("GET", "/nodes", headers, ows=True))) == 200
    duplicate = signed_headers("GET", "/nodes", nonce=406)
    rejected = _request_bytes(
        "GET",
        "/nodes",
        duplicate,
        extra=(("X-VAMS-Auth-Version", duplicate["X-VAMS-Auth-Version"]),),
    )
    assert _status(live_envoy_gateway.send(rejected)) == 401
    assert _status(live_envoy_gateway.send(_request_bytes("GET", "/nodes", duplicate))) == 200


@pytest.mark.parametrize("combined", [False, True])
def test_equivalent_content_lengths_reject_without_consuming_replay(live_envoy_gateway, combined):
    nonce = 408 if combined else 409
    body = _heartbeat_body(nonce)
    headers = signed_headers("POST", "/heartbeat", body=body, nonce=nonce)
    value = str(len(body))
    lengths = (("Content-Length", value + ", " + value),) if combined else (
        ("Content-Length", value),
        ("Content-Length", value),
    )
    response = live_envoy_gateway.send(
        _request_bytes("POST", "/heartbeat", headers, body, extra=lengths)
    )
    assert _status(response) == 400
    assert _status(
        live_envoy_gateway.send(_request_bytes("POST", "/heartbeat", headers, body))
    ) == 200


def test_proxy_headers_are_overwritten_and_verified_mtls_identity_reaches_gateway(live_envoy_gateway):
    body = _heartbeat_body(3)
    headers = signed_headers("POST", "/heartbeat", body=body, nonce=407)
    spoofed = (
        ("X-VAMS-Ingress-Version", "client-value"),
        ("X-Forwarded-For", "client-value"),
        ("X-Real-IP", "client-value"),
        ("X-VAMS-Client-Cert-Verified", "client-value"),
        ("X-VAMS-Client-Cert-Fingerprint", "client-value"),
    )
    response = live_envoy_gateway.send(_request_bytes("POST", "/heartbeat", headers, body, extra=spoofed))
    assert _status(response) == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("client", "marker", "expected"),
    [
        (("192.0.2.10", 1234), TRUSTED_INGRESS_VALUE, "untrusted_ingress_peer"),
        (("127.0.0.1", 1234), b"wrong", "untrusted_ingress_marker"),
    ],
)
async def test_direct_live_uvicorn_boundary_fails_before_downstream(client, marker, expected):
    called = False

    async def downstream(scope, receive, send):
        nonlocal called
        called = True

    middleware = GatewayRouteSecurityMiddleware(downstream)
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    app = SimpleNamespace(state=SimpleNamespace(runtime_policy=RuntimePolicy(RuntimeMode.TESTNET, False)))
    await middleware(
        {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "headers": [(b"x-vams-ingress-version", marker)],
            "client": client,
            "app": app,
        },
        receive,
        send,
    )
    assert called is False
    assert sent[0]["status"] == 403
    assert expected.encode() in sent[1]["body"]
