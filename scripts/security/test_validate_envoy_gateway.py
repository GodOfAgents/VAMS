from pathlib import Path

import pytest

from scripts.security.validate_envoy_gateway import (
    INGRESS_MARKER,
    validate_caddy_notice,
    validate_config_text,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG = (ROOT / "gateway" / "envoy.testnet.yaml").read_text(encoding="utf-8")
CADDY = (ROOT / "gateway" / "Caddyfile.testnet.example").read_text(encoding="utf-8")


def test_checked_in_envoy_contract_is_complete():
    assert validate_config_text(CONFIG) == []
    assert validate_caddy_notice(CADDY) == []


@pytest.mark.parametrize(
    "required",
    [
        "allow_chunked_length: false",
        "headers_with_underscores_action: REJECT_REQUEST",
        "path_with_escaped_slashes_action: REJECT_REQUEST",
        "- x-vams-ingress-version",
        "- x-vams-client-cert-fingerprint",
        "key: x-vams-ingress-version, value: " + INGRESS_MARKER,
        "address: 127.0.0.1, port_value: 8000",
    ],
)
def test_removing_security_boundary_entry_fails(required):
    assert validate_config_text(CONFIG.replace(required, "", 1))


def test_unsafe_chunked_length_setting_fails():
    mutated = CONFIG.replace("allow_chunked_length: false", "allow_chunked_length: true")
    assert validate_config_text(mutated)


def test_caddy_cannot_be_promoted_by_removing_retirement_notice():
    assert validate_caddy_notice(CADDY.replace("UNSUPPORTED FOR M2/LIVE GATEWAY USE", ""))
