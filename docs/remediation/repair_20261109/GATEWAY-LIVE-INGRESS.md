# Gateway live ingress: remote clients, rate limiting, abuse limits (2026-11-09)

Status: **TWO DEFECTS FIXED IN SOURCE; non-author review pending.** This is
local native evidence for parts of T31 (mTLS, replay, rate limiting) and T35
(TLS and resource limits). Both tracks stay `partial`. DAST, an external
vantage point, a load test, a container scan and the R28 host boundary
remain. Readiness is unchanged: 13 findings open, 0 of 36 tracks verified,
NOT READY.

High-risk change class (AGENTS.md section 7): gateway authentication, rate
limits and the bind/ingress boundary. Design rationale and tests follow.

## Setup

- Envoy 1.39.1, official binary, SHA-256
  `002c6e1c69ed0fa0ea381887247cadadfaec9481375fa8d8d2b1731eeabf40b8`.
- Configuration: the reviewed `gateway/envoy.testnet.yaml`, rendered with
  temporary local certificates.
- Gateway: Uvicorn in `VAMS_ENV=testnet` on a loopback port.
- The listener is bound to this host's non-loopback IPv4 address. A
  connection from that address is a stand-in for a remote client: it is not
  loopback, and Envoy writes it into `X-Forwarded-For`.
- Distinct loopback source addresses stand in for distinct clients.

This is one host, not an external vantage point.

## Defect 1: every remote client was refused (403)

**Cause.** Uvicorn processes proxy headers by default: `proxy_headers=True`,
trusted from 127.0.0.1. The reviewed Envoy route writes the downstream
client address into `X-Forwarded-For`, so Uvicorn replaced the transport
peer, the loopback Envoy connection, with the remote client's address.
`_validate_trusted_ingress` requires a loopback peer in live modes, so it
refused every remote request with `untrusted_ingress_peer`, on public and
signed routes alike.

Both launch paths had the default:

- `python -m gateway.server`: `uvicorn.run(app, host=..., port=8000)`;
- the documented `uvicorn gateway.server:app --host 127.0.0.1 --port 8000`.

The existing live tests (`test_m2_4b_envoy_ingress.py`) could not see it,
because their client is itself on 127.0.0.1.

**Impact.** On the restricted testnet no remote node or user could use the
gateway: heartbeats, node views and admin routes were all refused. The
failure was closed, not a security hole, but it blocked the deployment.

**Fix.**

- `gateway/server.py` `main()` passes `proxy_headers=False`. The launch
  command in `docs/GATEWAY_HARDENING_BLUEPRINTS.md` adds
  `--no-proxy-headers` and explains why it is required. The existing live
  harness now launches the same way.
- `gateway/route_security.py`:
  - A rewritten peer still fails closed, but with a named code,
    `ingress_peer_rewritten_by_proxy_headers`, so operators see the cause.
    The condition is a non-loopback peer equal to the single forwarded
    address while the ingress marker is present.
  - New `trusted_ingress_client(scope)` returns the Envoy-asserted client
    address. It does so only for a loopback peer with the exact ingress
    marker and exactly one `X-Forwarded-For` value that parses as an IP.
    Envoy strips client-supplied forwarding headers and writes that value
    from the TCP address, so a client cannot choose it. Anything else
    returns `None`.

## Defect 2: rejected requests were never rate limited

**Cause.** Starlette runs the last-added middleware first.
`RateLimitMiddleware` was added before `GatewayRouteSecurityMiddleware`, so
it ran inside it. Route security answers ingress, framing, routing and
authentication failures itself, without calling inner layers. Those
requests were never counted, which allowed unlimited secp256k1 signature
verification attempts from one client.

**Fix.**

- Middleware order on the way in is now: runtime classification → rate
  limit → size limit → route security → CORS → routes.
- The bucket key is `client:<Envoy-asserted address>` when
  `trusted_ingress_client` returns one, else `peer:<transport peer>`.
- New clients share an overflow bucket once 10,000 buckets exist. Before,
  memory had no bound under address spraying.
- A non-positive rate or window is treated as invalid and falls back to the
  defaults. Before, a window of 0 divided by zero on every request.

## Before and after (same probe, live Envoy, `GATEWAY_RATE_LIMIT=5/60`)

Pre-fix tree: commit `d472b49` in a temporary worktree, launched as
documented before the fix. Fixed tree: launched with `--no-proxy-headers`.

| Probe | Before | After |
|---|---|---|
| Remote-style client, `GET /health` | 403 `untrusted_ingress_peer` | 200 |
| Remote-style client, signed `GET /nodes` | 403 `untrusted_ingress_peer` | 200 |
| Client A sends 7 requests | 5 × 200, then 429, 429 | same |
| Client B after A is limited | 200 | 200 |
| Client A adds spoofed `X-Forwarded-For` | 429 | 429 |
| 6 bad-signature requests, then `/health` | 6 × 401, then 200 | 5 × 401, then 429, then 429 |

Envoy and the gateway also enforce the following, unchanged by this repair
and now covered by live regression tests:

| Abuse case | Result |
|---|---|
| No client certificate | refused at TLS, no HTTP response |
| Client certificate from an unrelated CA | refused at TLS, no HTTP response |
| TLS 1.1 | refused (protocol version alert) |
| Body over 1 MiB | 413 |
| Header over 16 KiB | 431 |
| 101 headers | 431 |
| Header name with underscore | 400 |
| `TRACE` | 405 |
| HTTP/1.0 | 426 |
| Headers sent slowly (3 s pause) | 408 |
| Escaped slash in path | 400 |

## Tests

New file `neuron/tests/test_gateway_live_ingress_abuse.py`, 28 tests:

- **Live, through Envoy:**
  - the remote client reaches public and signed routes;
  - the limit applies per client;
  - spoofed `X-Forwarded-For` does not escape the limit;
  - rejected authentication counts against the limit;
  - the 11 abuse cases above.
- **Unit:**
  - 9 trust-rule cases for `trusted_ingress_client`;
  - the named rewrite code;
  - `main()` disables proxy headers and binds loopback;
  - the limiter runs before route security;
  - the bucket cap.

It skips if the pinned Envoy binary or a non-loopback IPv4 address is
missing.

Results:

- The new file and the existing live Envoy file together: 38 passed, in
  three consecutive runs.
- Full Python suite and Bandit: see the commit message.

## Privacy inventory

The `gateway/server.py` and `gateway/route_security.py` digests were
refreshed, and the moved line ranges were re-mapped to the same code. A
dated `anchor_rebinding_20261109_gateway_ingress` entry was added. The
rate-limit sentence now states the bucket key. That key is the same client
IP the limiter already held through Uvicorn's rewrite. No new field,
recipient, persistence or flow. This is not privacy approval; T33 stays
BLOCKED.

## Invariants

No change to INV-1 to INV-10. INV-5 and INV-6 are unaffected: OMS and TEE
paths are not touched, and the mTLS fingerprint allowlist for `/heartbeat`
is unchanged.

## Still open for T31 and T35

- DAST against the deployed ingress.
- An external vantage point and real client network paths.
- A load test sized to the deployment.
- A TLS scan from outside the host.
- A container image scan.
- Effective host enforcement (R28, not authorized).
- Envoy has no rate-limit filter. Limiting happens in the gateway process,
  per process: buckets are lost on restart and not shared between replicas.
- Keying by IP address treats clients behind one NAT as one client. Keying
  by mTLS certificate fingerprint is an alternative for review.
