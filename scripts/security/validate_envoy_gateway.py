#!/usr/bin/env python3
"""Fail-closed static contract checks for the sole live Gateway ingress."""

from __future__ import annotations

import argparse
from pathlib import Path


ENVOY_VERSION = "1.39.1"
ENVOY_SHA256 = "002c6e1c69ed0fa0ea381887247cadadfaec9481375fa8d8d2b1731eeabf40b8"
INGRESS_MARKER = "envoy-1.39.1-v1"


REQUIRED_SNIPPETS = (
    "Envoy 1.39.1",
    ENVOY_SHA256,
    "require_client_certificate: true",
    "allow_absolute_url: false",
    "accept_http_10: false",
    "allow_chunked_length: false",
    "override_stream_error_on_invalid_http_message: false",
    "headers_with_underscores_action: REJECT_REQUEST",
    "normalize_path: true",
    "merge_slashes: false",
    "path_with_escaped_slashes_action: REJECT_REQUEST",
    "max_request_headers_kb: 16",
    "max_request_bytes: 1048576",
    "request_headers_timeout: 2s",
    "request_timeout: 5s",
    "stream_idle_timeout: 5s",
    "address: 127.0.0.1, port_value: 8000",
    "key: x-vams-ingress-version, value: " + INGRESS_MARKER,
    "key: x-vams-client-cert-verified, value: success",
    "key: x-vams-client-cert-fingerprint, value: \"%DOWNSTREAM_PEER_FINGERPRINT_256%\"",
    "append_action: OVERWRITE_IF_EXISTS_OR_ADD",
    "forward_client_cert_details: SANITIZE_SET",
    'regex: "^(GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS)$"',
)

REMOVED_HEADERS = (
    "forwarded",
    "x-forwarded-for",
    "x-forwarded-host",
    "x-forwarded-proto",
    "x-forwarded-port",
    "x-real-ip",
    "x-vams-ingress-trust",
    "x-vams-ingress-version",
    "x-vams-client-cert-verified",
    "x-vams-client-cert-fingerprint",
    "x-forwarded-tls-client-cert-verified",
    "x-forwarded-tls-client-cert-fingerprint",
    "x-ssl-client-verify",
    "x-ssl-client-fingerprint",
)

FORBIDDEN_SNIPPETS = (
    "allow_chunked_length: true",
    "accept_http_10: true",
    "allow_absolute_url: true",
    "headers_with_underscores_action: ALLOW",
    "path_with_escaped_slashes_action: KEEP_UNCHANGED",
    "cluster: caddy",
)


def validate_config_text(text: str) -> list[str]:
    errors: list[str] = []
    for snippet in REQUIRED_SNIPPETS:
        if snippet not in text:
            errors.append("required ingress contract entry missing: " + snippet)
    for header in REMOVED_HEADERS:
        if text.count("- " + header) != 1:
            errors.append("trusted client header is not removed exactly once: " + header)
    for snippet in FORBIDDEN_SNIPPETS:
        if snippet in text:
            errors.append("unsafe ingress option present: " + snippet)
    if text.count("address: 0.0.0.0, port_value: 8443") != 1:
        errors.append("the sole public TLS listener is not explicit")
    if text.count("key: x-vams-ingress-version, value: " + INGRESS_MARKER) != 1:
        errors.append("the versioned ingress marker is missing or ambiguous")
    if text.count("name: loopback_uvicorn") != 2:
        errors.append("the loopback-only upstream cluster is missing or ambiguous")
    if "tls_minimum_protocol_version: TLSv1_2" not in text:
        errors.append("TLS minimum is not pinned")
    if "tls_maximum_protocol_version: TLSv1_3" not in text:
        errors.append("TLS maximum is not pinned")
    return errors


def validate_caddy_notice(text: str) -> list[str]:
    required = ("HISTORICAL TEMPLATE", "UNSUPPORTED FOR M2/LIVE GATEWAY USE", "Envoy 1.39.1")
    return ["Caddy retirement notice is incomplete: " + item for item in required if item not in text]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("gateway/envoy.testnet.yaml"))
    parser.add_argument("--caddy", type=Path, default=Path("gateway/Caddyfile.testnet.example"))
    args = parser.parse_args()
    errors = validate_config_text(args.config.read_text(encoding="utf-8"))
    errors.extend(validate_caddy_notice(args.caddy.read_text(encoding="utf-8")))
    if errors:
        for error in errors:
            print("ERROR: " + error)
        return 1
    print("Envoy live-ingress contract: PASS")
    print("version=" + ENVOY_VERSION + " sha256=" + ENVOY_SHA256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
