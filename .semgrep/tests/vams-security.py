# Semgrep test fixtures for .semgrep/vams-security.yml. Intentionally unsafe;
# excluded from the repository scan. Run: semgrep --test --config .semgrep/vams-security.yml .semgrep/tests
import logging
import os
import socket
import subprocess

import uvicorn
from fastapi.middleware.cors import CORSMiddleware

from neuron.secp256k1 import verify_digest, verify_message

log = logging.getLogger(__name__)


def launch(app, host, policy):
    # ruleid: vams-uvicorn-proxy-headers-enabled
    uvicorn.run(app, host=host, port=8000)
    # ruleid: vams-uvicorn-proxy-headers-enabled
    uvicorn.run(app, host=host, port=8000, proxy_headers=True)
    # ok: vams-uvicorn-proxy-headers-enabled
    uvicorn.run(app, host=host, port=8000, proxy_headers=False)


def bind(app, sock):
    # ruleid: vams-bind-all-interfaces
    uvicorn.run(app, host="0.0.0.0", port=8000, proxy_headers=False)
    # ruleid: vams-bind-all-interfaces
    sock.bind(("0.0.0.0", 9000))
    # ok: vams-bind-all-interfaces
    sock.bind(("127.0.0.1", 9000))


def credentials(supplied):
    # ruleid: vams-default-credential
    password = os.getenv("GATEWAY_ADMIN_PASSWORD", "vams2026")
    # ruleid: vams-default-credential
    fallback = "vams2026"
    # ok: vams-default-credential
    if supplied == "vams2026":
        raise RuntimeError("default password refused")
    return password, fallback


def mock_flags(source):
    # ruleid: vams-direct-mock-flag-read
    a = os.getenv("OMS_MOCK_MODE", "true")
    # ruleid: vams-direct-mock-flag-read
    b = os.environ.get("PHALA_MOCK_MODE")
    # ruleid: vams-direct-mock-flag-read
    c = os.environ["AVAIL_MOCK_MODE"]
    # ruleid: vams-direct-mock-flag-read
    d = source.get(TRAILS_MOCK_VARIABLE, "false")
    # ok: vams-direct-mock-flag-read
    e = os.getenv("OMS_IDENTITY_API", "")
    # ok: vams-direct-mock-flag-read
    f = source.get("mock_routes_disabled")
    return a, b, c, d, e, f


def signatures(public_key, message, signature, digest, peer):
    # ruleid: vams-ignored-signature-verification
    verify_message(public_key, message, signature)
    # ruleid: vams-ignored-signature-verification
    peer.verify_digest(public_key, digest, signature)
    # ok: vams-ignored-signature-verification
    if not verify_message(public_key, message, signature):
        raise PermissionError("bad signature")
    # ok: vams-ignored-signature-verification
    valid = verify_digest(public_key, digest, signature)
    # ok: vams-ignored-signature-verification
    assert verify_message(public_key, message, signature)
    # ok: vams-ignored-signature-verification
    accepted = valid and verify_message(public_key, message, signature)
    # ok: vams-ignored-signature-verification
    return verify_digest(public_key, digest, signature) or accepted


def logs(api_key, private_key, fencing_token, user):
    # ruleid: vams-secret-in-log
    log.info("key %s", api_key)
    # ruleid: vams-secret-in-log
    log.debug(f"signing with {private_key}")
    # ruleid: vams-secret-in-log
    print("admin", admin_password)
    # ok: vams-secret-in-log
    log.info("fence %s for %s", fencing_token, user)
    # ok: vams-secret-in-log
    log.warning("api key missing")


def cors(app):
    # ruleid: vams-cors-wildcard-with-credentials
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True)
    # ok: vams-cors-wildcard-with-credentials
    app.add_middleware(CORSMiddleware, allow_origins=["https://gateway.example"], allow_credentials=True)


def existing(cmd, expression):
    # ruleid: vams-python-subprocess-shell-true
    subprocess.run(cmd, shell=True)
    # ok: vams-python-subprocess-shell-true
    subprocess.run([cmd], check=True)
    # ruleid: vams-python-dynamic-eval
    return eval(expression)
