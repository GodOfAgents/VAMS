# VAMS Gateway Hardening Blueprint (Envoy TLS and mTLS)

**Lifecycle:** reviewed testnet ingress template; deployment pending
**Last verified:** 2026-09-24

Envoy 1.39.1 is the sole supported public listener for the live VAMS Gateway.
Use `gateway/envoy.testnet.yaml`. The historical Caddy template is unsupported
for M2, staging, testnet, or production Gateway traffic and must not be placed
in front of or behind Envoy.

## Pinned runtime

- Official asset: `envoy-1.39.1-linux-x86_64`
- Source: `https://github.com/envoyproxy/envoy/releases/download/v1.39.1/envoy-1.39.1-linux-x86_64`
- SHA-256: `002c6e1c69ed0fa0ea381887247cadadfaec9481375fa8d8d2b1731eeabf40b8`
- Required version suffix: `/1.39.1/Clean/RELEASE/BoringSSL`

Do not use a latest tag or an unverified binary. CI downloads the exact asset,
checks the digest before execution, validates the version, runs the repository
contract validator, and asks Envoy to validate the rendered configuration.

## Testnet ingress topology

```text
verified mTLS client -> Envoy 1.39.1 :8443 -> 127.0.0.1:8000 Uvicorn
```

The reviewed configuration requires client certificates, TLS 1.2 or 1.3,
strict built-in HTTP/1 validation, mixed length/transfer framing disabled,
normalized paths, rejected escaped separators and underscore headers, an
explicit method set, bounded headers and bodies, and bounded request,
connection, stream, and upstream timeouts. Uvicorn is not a public listener.

Envoy removes client-supplied forwarding, ingress-trust, and certificate
assertion headers. It then writes the reviewed forwarding values, the fixed
`envoy-1.39.1-v1` ingress marker, and the verified client-certificate status
and SHA-256 fingerprint. Its only upstream cluster is loopback Uvicorn.

The marker is not authorization. Live Gateway code also requires a loopback
peer, the M2 request signature, durable replay/revocation state, and the mTLS
identity allowlist on routes such as `/heartbeat`.

## Gateway startup

Provide the reviewed TLS files at the paths declared by the Envoy template,
then start Uvicorn only on loopback:

```bash
VAMS_ENV=testnet \
GATEWAY_ADMIN_DID=did:key:<admin-verifying-key> \
GATEWAY_ADMIN_PASSWORD=<non-default-secret> \
GATEWAY_AUTH_AUDIENCE=<fixed-audience> \
GATEWAY_AUTH_REPLAY_DB=/var/lib/vams/gateway-replay.sqlite3 \
GATEWAY_ALLOWED_ORIGINS=https://gateway.example \
GATEWAY_HEARTBEAT_CERT_FINGERPRINTS=<allowed-client-cert-fingerprint> \
uvicorn gateway.server:app --host 127.0.0.1 --port 8000
```

Validate the exact template and rendered certificate paths before any launch:

```bash
python scripts/security/validate_envoy_gateway.py
sha256sum /path/to/envoy
/path/to/envoy --version
/path/to/envoy --mode validate -c /path/to/rendered-envoy.yaml
```

This document does not authorize deployment. Certificate issuance, secret
provisioning, service supervision, firewall policy, and deployment ceremony
remain separate reviewed work.

## RFC 9112 acceptance contract

The authenticated request begins at the trusted Envoy output. Ambiguous
framing that can change message boundaries or create an additional upstream
request must reject. Obsolete line folding may be accepted only when Envoy
replaces it with spaces before interpretation and forwards one unambiguous
semantic request with no residual bytes or second execution. Equivalent OWS is
acceptable only when method, target, security-header meaning, body bytes,
request count, and replay identity remain unchanged. The qualified VAMS
profile rejects duplicate-identical and comma-equivalent content lengths
before upstream rather than normalizing them.

The earlier R4 rule requiring every obsolete fold to reject was stricter than
RFC 9112. R5 replaces it with this security-equivalence rule. It does not
enable a lenient parser option or permit normalization that changes any M2
authenticated meaning.

## Client mTLS

Clients send requests to Envoy and present a certificate chained to the
configured client CA. They must also send a valid M2 envelope. A client must
never supply or depend on `X-VAMS-Ingress-Version`, forwarding headers, or
`X-VAMS-Client-Cert-*`; Envoy removes and regenerates those fields.
