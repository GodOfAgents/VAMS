"""Public-boundary regressions for the M2.1 gateway auth envelope."""

from __future__ import annotations

import hashlib
import threading
from dataclasses import replace

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from gateway.request_auth import (
    AUTH_ALGORITHM,
    AUTH_DOMAIN,
    AUTH_VERSION,
    ConfiguredAdminDIDResolver,
    GatewayAuthEnvelope,
    GatewayAuthenticationError,
    GatewayRequestAuthenticator,
    KeyResolution,
    KeyStatus,
    ProcessLocalReplayStore,
    ReplayNamespace,
    ReplayOutcome,
    RuntimePolicy,
    configured_gateway_audience,
    gateway_auth_dependency,
)
from neuron.runtime_safety import (
    REGISTERED_MOCK_VARIABLES,
    LiveModeSafetyError,
    RuntimeConfigurationError,
)
from neuron.secp256k1 import public_key_bytes, sign_message, verify_message


NOW = 1_700_000_000
AUDIENCE = "vams-gateway"
NONCE = "00112233445566778899aabbccddeeff"
PRIVATE_KEY = ec.derive_private_key(1, ec.SECP256K1())
PUBLIC_KEY = public_key_bytes(PRIVATE_KEY)
SIGNER = "did:key:" + PUBLIC_KEY.hex()

# Independently frozen review vector. Expected bytes are not produced by a
# helper during the test and therefore catch canonicalizer drift.
FIXED_CANONICAL_HEX = (
    "56414d533a474154455741593a524551554553542d415554483a763100000b"
    "0100000001310200000016736563703235366b312d65636473612d736861323536"
    "0300000004504f535404000000122f76312f6a6f62732f254532253832254143"
    "05000000107461673d61267461673d26656d707479"
    "0600000020e346432021b04179518d9614f3560ccd71354a4ee101ddcb893d6959a9d6301c"
    "070000000c76616d732d67617465776179"
    "08000000886469643a6b65793a373962653636376566396463626261633535613036323935"
    "63653837306230373032396266636462326463653238643935396632383135623136663831"
    "37393834383361646137373236613363343635356461346662666330653131303861386664"
    "313762343438613638353534313939633437643038666662313064346238"
    "090000001000112233445566778899aabbccddeeff"
    "0a00000008000000006553f1000b00000008000000006553f178"
)
FIXED_SIGNATURE_HEX = (
    "200c8cdec019f7b80011fb8a54f1473bd0d2dedbf9b73fd8e75f4e7fc7588285"
    "2ad7d2e1e84a52280ec7cdc16e0527a269d86caf7b6346e6ae895978b2fa72a8"
)


class FixedClock:
    def __init__(self, value: int = NOW):
        self.value = value

    def now(self) -> int:
        return self.value


class FixedResolver:
    def __init__(self, status: KeyStatus = KeyStatus.AVAILABLE):
        self.status = status

    def resolve(self, signer: str) -> KeyResolution:
        if self.status is KeyStatus.AVAILABLE:
            return KeyResolution(self.status, PUBLIC_KEY)
        return KeyResolution(self.status)


class FixedReplay:
    def __init__(self, outcome: ReplayOutcome):
        self.outcome = outcome

    def reserve_and_consume(self, namespace, *, expires_at, now):
        return self.outcome


@pytest.fixture(autouse=True)
def exact_test_runtime(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "test")
    for variable in REGISTERED_MOCK_VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def policy(mode: str = "test") -> RuntimePolicy:
    return RuntimePolicy.from_environment({"VAMS_ENV": mode})


def envelope(
    *,
    method: bytes = b"POST",
    path: bytes = b"/v1/jobs/%E2%82%AC",
    query: bytes = b"tag=a&tag=&empty",
    body: bytes = b'{"a":1}\n',
    audience: str = AUDIENCE,
    signer: str = SIGNER,
    nonce: str = NONCE,
    issued_at: int = NOW,
    expires_at: int = NOW + 120,
    version: str = AUTH_VERSION,
    algorithm: str = AUTH_ALGORITHM,
) -> GatewayAuthEnvelope:
    return GatewayAuthEnvelope(
        version=version,
        algorithm=algorithm,
        method=method,
        raw_path=path,
        raw_query=query,
        body_sha256=hashlib.sha256(body).digest(),
        audience=audience,
        signer=signer,
        nonce=bytes.fromhex(nonce),
        issued_at=issued_at,
        expires_at=expires_at,
    )


def signed_headers(env: GatewayAuthEnvelope, **overrides: str) -> dict[str, str]:
    headers = {
        "X-VAMS-Auth-Version": env.version,
        "X-VAMS-Auth-Algorithm": env.algorithm,
        "X-VAMS-Auth-Audience": env.audience,
        "X-VAMS-Auth-Signer": env.signer,
        "X-VAMS-Auth-Nonce": env.nonce.hex(),
        "X-VAMS-Auth-Issued-At": str(env.issued_at),
        "X-VAMS-Auth-Expires-At": str(env.expires_at),
        "X-VAMS-Auth-Signature": sign_message(
            PRIVATE_KEY, env.canonical_bytes()
        ).hex(),
    }
    headers.update(overrides)
    return headers


def app_client(
    *,
    resolver=None,
    replay=None,
    audience: str = AUDIENCE,
    clock=None,
) -> TestClient:
    auth = GatewayRequestAuthenticator(
        expected_audience=audience,
        clock=clock or FixedClock(),
        key_resolver=resolver or FixedResolver(),
        replay_store=replay
        or ProcessLocalReplayStore(policy()),
    )
    dependency = gateway_auth_dependency(auth)
    app = FastAPI()

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def protected(
        request: Request,
        authenticated=Depends(dependency),
    ):
        downstream = await request.body()
        return {
            "body_hex": downstream.hex(),
            "authenticated_hex": authenticated.raw_body.hex(),
            "path": authenticated.envelope.raw_path.decode("ascii"),
            "query": authenticated.envelope.raw_query.decode("ascii"),
        }

    return TestClient(app)


def send(
    client: TestClient,
    env: GatewayAuthEnvelope,
    *,
    body: bytes = b'{"a":1}\n',
    headers: dict[str, str] | list[tuple[str, str]] | None = None,
    host: str | None = None,
):
    target = env.raw_path.decode("ascii")
    if env.raw_query:
        target += "?" + env.raw_query.decode("ascii")
    actual_headers = signed_headers(env) if headers is None else headers
    if host is not None:
        if not isinstance(actual_headers, dict):
            actual_headers = list(actual_headers) + [("Host", host)]
        else:
            actual_headers = {**actual_headers, "Host": host}
    return client.request(env.method.decode("ascii"), target, content=body, headers=actual_headers)


def test_fixed_known_vector_is_stable_and_verifies():
    env = envelope()
    assert env.canonical_bytes().hex() == FIXED_CANONICAL_HEX
    assert env.canonical_bytes().startswith(AUTH_DOMAIN)
    assert verify_message(
        PUBLIC_KEY, env.canonical_bytes(), bytes.fromhex(FIXED_SIGNATURE_HEX)
    )
    assert envelope().canonical_bytes() == env.canonical_bytes()


def test_distinct_requests_do_not_collapse_to_one_canonical_message():
    variants = [
        envelope(),
        envelope(method=b"PUT"),
        envelope(path=b"/v1/jobs/other"),
        envelope(query=b"tag=a&empty&tag="),
        envelope(body=b'{"a":1}'),
        envelope(audience="vams-testnet-gateway"),
        envelope(nonce="10112233445566778899aabbccddeeff"),
        envelope(issued_at=NOW - 1),
        envelope(expires_at=NOW + 119),
    ]
    canonical = [item.canonical_bytes() for item in variants]
    assert len(set(canonical)) == len(canonical)


@pytest.mark.parametrize("body", [b"", b"\x00\xff\x01", b" {} \n", b'{"b":2,"a":1}'])
def test_exact_body_bytes_are_authenticated_and_forwarded(body: bytes):
    env = envelope(body=body, query=b"")
    response = send(app_client(), env, body=body)
    assert response.status_code == 200
    assert response.json()["body_hex"] == body.hex()
    assert response.json()["authenticated_hex"] == body.hex()


@pytest.mark.parametrize(
    "original,changed",
    [
        (b'{"a":1}\n', b'{"a": 1}\n'),
        (b'{"a":1}\n', b'{"a":1}'),
        (b'{"a":1}\n', b'{"a":1}\r\n'),
        (b'{"a":1,"b":2}', b'{"b":2,"a":1}'),
    ],
)
def test_body_whitespace_or_newline_change_rejects(
    original: bytes, changed: bytes
):
    env = envelope(query=b"", body=original)
    response = send(app_client(), env, body=changed)
    assert response.status_code == 401
    assert response.json()["detail"].endswith("signature verifier (invalid_signature)")


@pytest.mark.parametrize(
    "field,value",
    [
        ("method", b"PUT"),
        ("raw_path", b"/v1/other"),
        ("raw_query", b"tag=&tag=a&empty"),
        ("body_sha256", hashlib.sha256(b"different").digest()),
        ("audience", "other-gateway"),
        ("signer", "did:key:" + (b"\x01" * 64).hex()),
        ("nonce", bytes.fromhex("10112233445566778899aabbccddeeff")),
        ("issued_at", NOW - 1),
        ("expires_at", NOW + 119),
    ],
)
def test_each_signed_field_changes_canonical_message(field, value):
    original = envelope()
    changed = replace(original, **{field: value})
    assert changed.canonical_bytes() != original.canonical_bytes()


@pytest.mark.parametrize(
    "query",
    [
        b"tag=a&tag=&empty",
        b"tag=&tag=a&empty",
        b"tag=a&tag&empty=",
        b"q=%E2%82%AC",
        b"reserved=%26%3D%2B%3F&plus=+",
    ],
)
def test_query_order_repetition_empty_forms_and_unicode_are_wire_bound(query: bytes):
    env = envelope(query=query, body=b"")
    response = send(app_client(), env, body=b"")
    assert response.status_code == 200
    assert response.json()["query"] == query.decode("ascii")


def test_fixed_audience_does_not_derive_from_host():
    env = envelope(query=b"", body=b"")
    assert send(app_client(), env, body=b"", host="attacker.invalid").status_code == 200
    wrong = envelope(query=b"", body=b"", audience="attacker.invalid")
    response = send(app_client(), wrong, body=b"")
    assert response.status_code == 401
    assert "audience_mismatch" in response.json()["detail"]


@pytest.mark.parametrize(
    "path,code",
    [
        (b"//admin", "malformed_path"),
        (b"http://host/admin", "malformed_path"),
        (b"/a//b", "malformed_path"),
        (b"/a/../b", "path_traversal"),
        (b"/a/%2E%2E/b", "noncanonical_path"),
        (b"/a/%2f/b", "malformed_path"),
        (b"/a/%2F/b", "noncanonical_path"),
        (b"/a?b", "malformed_path"),
        (b"/a#b", "malformed_path"),
        (b"/a\\b", "malformed_path"),
        (b"/a/%ZZ", "malformed_path"),
        (b"/a/%41", "noncanonical_path"),
        (b"/caf%C3%A9/e%CC%81", "noncanonical_path"),
    ],
)
def test_absolute_fragment_traversal_and_ambiguous_paths_reject(path: bytes, code: str):
    with pytest.raises(GatewayAuthenticationError, match=code):
        envelope(path=path)


@pytest.mark.parametrize(
    "query",
    [
        b"a=1&&b=2",
        b"=value",
        b"a=1;b=2",
        b"q=%41",
        b"q=%zz",
        b"q=e%CC%81",
    ],
)
def test_ambiguous_or_noncanonical_queries_reject(query: bytes):
    with pytest.raises(GatewayAuthenticationError, match="query"):
        envelope(query=query)


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"path": b"/" + b"a" * 2_048}, "malformed_path"),
        ({"query": b"a=" + b"b" * 8_191}, "malformed_query"),
        ({"audience": "a" * 129}, "malformed_audience"),
        ({"method": b"POSTING"}, "unsupported_method"),
    ],
)
def test_envelope_field_size_and_closed_method_bounds(changes, code):
    with pytest.raises(GatewayAuthenticationError, match=code):
        envelope(**changes)


def test_oversized_body_rejects_at_public_boundary():
    body = b"x" * 1_048_577
    env = envelope(query=b"", body=body)
    response = send(app_client(), env, body=body)
    assert response.status_code == 401
    assert "body_too_large" in response.json()["detail"]


@pytest.mark.parametrize(
    "header,value,code",
    [
        ("X-VAMS-Auth-Version", "2", "unsupported_version"),
        ("X-VAMS-Auth-Algorithm", "ed25519", "unsupported_algorithm"),
        ("X-VAMS-Auth-Nonce", "0" * 32, "malformed_nonce"),
        ("X-VAMS-Auth-Nonce", "AA" * 16, "malformed_nonce"),
        ("X-VAMS-Auth-Nonce", "1" * 4097, "auth_headers_too_large"),
        ("X-VAMS-Auth-Issued-At", "NaN", "malformed_issued_at"),
        ("X-VAMS-Auth-Issued-At", "inf", "malformed_issued_at"),
        ("X-VAMS-Auth-Issued-At", "1.0", "malformed_issued_at"),
        ("X-VAMS-Auth-Issued-At", "01", "malformed_issued_at"),
        ("X-VAMS-Auth-Expires-At", "9223372036854775808", "malformed_timestamp"),
        ("X-VAMS-Auth-Signature", "00", "malformed_signature"),
        ("X-VAMS-Auth-Signer", "did:key:NOT-HEX", "malformed_signer"),
    ],
)
def test_strict_headers_reject_before_acceptance(header: str, value: str, code: str):
    env = envelope(query=b"", body=b"")
    headers = signed_headers(env, **{header: value})
    response = send(app_client(), env, body=b"", headers=headers)
    assert response.status_code == 401
    assert code in response.json()["detail"]


@pytest.mark.parametrize(
    "issued,expires,clock,code",
    [
        (NOW, NOW, NOW, "invalid_time_window"),
        (NOW, NOW + 301, NOW, "lifetime_too_long"),
        (NOW + 301, NOW + 302, NOW, "issued_in_future"),
        (NOW - 301, NOW - 1, NOW, "expired"),
    ],
)
def test_time_bounds_fail_closed(issued: int, expires: int, clock: int, code: str):
    env = envelope(query=b"", body=b"", issued_at=issued, expires_at=expires)
    response = send(app_client(clock=FixedClock(clock)), env, body=b"")
    assert response.status_code == 401
    assert code in response.json()["detail"]


@pytest.mark.parametrize("value", [True, 1.0])
def test_typed_envelope_rejects_boolean_and_float_timestamps(value):
    with pytest.raises(GatewayAuthenticationError, match="malformed_timestamp"):
        envelope(issued_at=value)


@pytest.mark.parametrize(
    "header,code",
    [
        ("X-VAMS-Auth-Version", "missing_version"),
        ("X-VAMS-Auth-Algorithm", "missing_algorithm"),
        ("X-VAMS-Auth-Audience", "missing_audience"),
        ("X-VAMS-Auth-Signer", "missing_signer"),
        ("X-VAMS-Auth-Nonce", "missing_nonce"),
        ("X-VAMS-Auth-Issued-At", "missing_issued_at"),
        ("X-VAMS-Auth-Expires-At", "missing_expires_at"),
        ("X-VAMS-Auth-Signature", "missing_signature"),
    ],
)
def test_each_required_header_is_mandatory(header: str, code: str):
    env = envelope(query=b"", body=b"")
    missing_headers = signed_headers(env)
    del missing_headers[header]
    missing = send(app_client(), env, body=b"", headers=missing_headers)
    assert missing.status_code == 401
    assert code in missing.json()["detail"]


@pytest.mark.parametrize(
    "header,code",
    [
        ("X-VAMS-Auth-Nonce", "duplicate_nonce"),
        ("X-VAMS-Auth-Signature", "duplicate_signature"),
    ],
)
def test_security_header_duplication_rejects(header: str, code: str):
    env = envelope(query=b"", body=b"")
    pairs = list(signed_headers(env).items())
    pairs.append((header, signed_headers(env)[header]))
    duplicate = send(app_client(), env, body=b"", headers=pairs)
    assert duplicate.status_code == 401
    assert code in duplicate.json()["detail"]


@pytest.mark.parametrize(
    "header,code",
    [
        (("X-VAMS-Auth-Future", "value"), "unknown_auth_header"),
        (("X-VAMS-Timestamp", str(NOW)), "conflicting_legacy_auth_header"),
        (("X-VAMS-DID", SIGNER), "conflicting_legacy_auth_header"),
    ],
)
def test_unknown_or_legacy_auth_headers_reject_closed_schema(header, code):
    env = envelope(query=b"", body=b"")
    pairs = list(signed_headers(env).items()) + [header]
    response = send(app_client(), env, body=b"", headers=pairs)
    assert response.status_code == 401
    assert code in response.json()["detail"]


@pytest.mark.parametrize(
    "status,expected_status,code",
    [
        (KeyStatus.UNKNOWN, 401, "unknown_signer"),
        (KeyStatus.REVOKED, 401, "revoked_signer"),
        (KeyStatus.UNAVAILABLE, 503, "key_unavailable"),
    ],
)
def test_key_resolution_outcomes_fail_closed(status, expected_status, code):
    env = envelope(query=b"", body=b"")
    response = send(app_client(resolver=FixedResolver(status)), env, body=b"")
    assert response.status_code == expected_status
    assert code in response.json()["detail"]
    assert SIGNER not in response.text
    assert signed_headers(env)["X-VAMS-Auth-Signature"] not in response.text


def test_key_resolver_failure_is_sanitized():
    class BrokenResolver:
        def resolve(self, signer: str):
            raise RuntimeError("provider leaked internal key database path")

    env = envelope(query=b"", body=b"")
    response = send(app_client(resolver=BrokenResolver()), env, body=b"")
    assert response.status_code == 503
    assert "key_unavailable" in response.json()["detail"]
    assert "database" not in response.text


@pytest.mark.parametrize(
    "outcome,status,code",
    [
        (ReplayOutcome.DUPLICATE, 401, "duplicate_nonce"),
        (ReplayOutcome.REVOKED, 401, "revoked_nonce"),
        (ReplayOutcome.UNAVAILABLE, 503, "replay_unavailable"),
        (ReplayOutcome.STORAGE_FAILURE, 503, "storage_failure"),
    ],
)
def test_replay_outcomes_fail_closed(outcome, status, code):
    env = envelope(query=b"", body=b"")
    response = send(app_client(replay=FixedReplay(outcome)), env, body=b"")
    assert response.status_code == status
    assert code in response.json()["detail"]


def test_process_local_replay_is_atomic_for_one_namespace():
    store = ProcessLocalReplayStore(policy())
    namespace = ReplayNamespace(
        AUTH_VERSION,
        AUDIENCE,
        hashlib.sha256(SIGNER.encode()).digest(),
        bytes.fromhex(NONCE),
    )
    outcomes: list[ReplayOutcome] = []
    barrier = threading.Barrier(12)

    def attempt():
        barrier.wait()
        outcomes.append(store.reserve_and_consume(namespace, expires_at=NOW + 60, now=NOW))

    threads = [threading.Thread(target=attempt) for _ in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert outcomes.count(ReplayOutcome.ACCEPTED) == 1
    assert outcomes.count(ReplayOutcome.DUPLICATE) == 11


@pytest.mark.parametrize("mode", ["staging", "testnet", "production"])
def test_process_local_replay_is_prohibited_in_live_modes(mode: str, monkeypatch):
    monkeypatch.setenv("VAMS_ENV", mode)
    with pytest.raises(LiveModeSafetyError, match="process-local"):
        ProcessLocalReplayStore(policy(mode))


def test_process_local_replay_rejects_policy_environment_rebinding(monkeypatch):
    monkeypatch.setenv("VAMS_ENV", "testnet")
    with pytest.raises(RuntimeConfigurationError, match="does not match"):
        ProcessLocalReplayStore(policy())


def test_configured_resolver_preserves_existing_single_admin_did_trust():
    resolver = ConfiguredAdminDIDResolver({"GATEWAY_ADMIN_DID": SIGNER})
    assert resolver.resolve(SIGNER) == KeyResolution(KeyStatus.AVAILABLE, PUBLIC_KEY)
    assert resolver.resolve("did:key:" + (b"\x01" * 64).hex()).status is KeyStatus.UNKNOWN
    assert ConfiguredAdminDIDResolver({}).resolve(SIGNER).status is KeyStatus.UNAVAILABLE


def test_gateway_audience_configuration_is_explicit_and_strict():
    assert configured_gateway_audience(
        {"GATEWAY_AUTH_AUDIENCE": "vams.gateway.testnet"}
    ) == "vams.gateway.testnet"
    with pytest.raises(GatewayAuthenticationError, match="missing_audience"):
        configured_gateway_audience({})
    with pytest.raises(GatewayAuthenticationError, match="malformed_audience"):
        configured_gateway_audience({"GATEWAY_AUTH_AUDIENCE": "TestNet Gateway"})


def test_reusing_exact_authenticated_request_is_rejected():
    client = app_client()
    env = envelope(query=b"", body=b"")
    assert send(client, env, body=b"").status_code == 200
    second = send(client, env, body=b"")
    assert second.status_code == 401
    assert "duplicate_nonce" in second.json()["detail"]
