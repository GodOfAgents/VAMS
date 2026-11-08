# M2.4b raw-wire ingress decision

Date: 2026-09-24
Scope: M2-R2 Finding 2 only
Decision: BLOCKED — explicit ingress-contract authorization required

## Outcome

No enforcement change is implemented. The current supported local stack cannot
prove the original raw-wire rejection contract:

1. Direct Uvicorn/h11 executable tests confirm that prohibited optional
   whitespace, duplicate identical Content-Length, comma-equivalent
   Content-Length, and one obsolete-fold representation are normalized before
   the request reaches ASGI. They execute the protected handler and consume a
   nonce.
2. The repository pins a Caddy 2.11.4 Alpine image in CI, but no Caddy binary,
   Docker runtime, cached OCI image, or executable Caddy toolchain exists in
   this environment. A real Caddy-to-Uvicorn chain therefore could not be run
   without installing or fetching a dependency, which this slice prohibits.
3. Live application startup does not enforce the proxy boundary. The normal
   gateway main function chooses loopback, but an explicit Uvicorn CLI command
   in testnet mode successfully started on 0.0.0.0.

The decision rule therefore requires a stop. No ASGI workaround, custom HTTP
parser, Uvicorn subclass, second ingress product, or inferred Caddy protection
was added. F08 and M2 remain REVALIDATED_OPEN.

## Versions and supported path

The existing Python toolchain reports:

| Component | Version / identity |
| --- | --- |
| Uvicorn | 0.52.4 |
| h11 | 0.16.0 |
| FastAPI | 0.141.1 |
| Starlette | 1.6.0 |
| Caddy deployment pin | caddy:2.11.4-alpine at sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648 |
| Locally executable Caddy | unavailable |
| Local Docker runtime / cached Caddy image | unavailable |

The documented intended path is:

    client -> Caddy TLS/mTLS -> loopback Uvicorn/h11 -> ASGI -> M2 auth

On that path Caddy is the first component that receives client wire bytes.
However, Caddyfile handlers operate after Caddy's HTTP parser. Exact
parser-to-config behavior is not claimed here because the pinned executable
was unavailable for the required real-chain test. On direct Uvicorn, h11 is
the first HTTP parser and demonstrably normalizes the affected fields before
Uvicorn creates the ASGI scope.

The checked-in Caddy template proxies to 127.0.0.1:8000 and overwrites the two
VAMS mTLS result headers. The workflow validates the pinned image. The
deployment blueprint still contains a separate caddy:latest example, and
neither source startup nor a deployment manifest proves that the pinned proxy
is the only live ingress.

## Direct normalization evidence

h11 0.16.0 source and executable behavior agree:

- h11._readers.header_field_re accepts whitespace after the colon and before
  line end but captures only the trimmed field value.
- h11._readers._obsolete_line_fold unfolds continuation lines before header
  decoding.
- h11._headers.normalize_and_validate splits Content-Length on commas, strips
  each member, accepts one unique value, and emits only the first duplicate
  field when repeated values agree.
- Uvicorn H11Protocol.handle_events receives the resulting h11 Request and
  copies those already-normalized headers into the ASGI scope.

The ASGI M2 middleware therefore cannot distinguish the original accepted wire
representations. Adding another middleware check would not restore the lost
information.

## Raw TCP outcome matrix

The probe used the real FastAPI application, loopback Uvicorn, h11, a real
temporary durable SQLite store, unique synthetic signed requests, and an outer
ASGI scope counter. It persisted no request body, signature, credential,
nonce, or raw signer evidence.

| Wire case | Direct response | ASGI | Handler | Nonce | First decisive component |
| --- | --- | ---: | ---: | ---: | --- |
| Leading OWS on each of 8 M2 headers | 200 for all 8 | 1 each | 1 each | 1 each | h11 trimmed before ASGI |
| Trailing OWS on each of 8 M2 headers | 200 for all 8 | 1 each | 1 each | 1 each | h11 trimmed before ASGI |
| Duplicate identical Content-Length | 200 | 1 | 1 | 1 | h11 collapsed duplicates |
| Conflicting Content-Length | 400, close | 0 | 0 | 0 | h11 rejected |
| Comma-list equal Content-Length | 200 | 1 | 1 | 1 | h11 collapsed equal list |
| Comma-list conflicting Content-Length | 400, close | 0 | 0 | 0 | h11 rejected |
| Content-Length plus Transfer-Encoding | 400, close | 1 | 0 | 0 | ASGI outer framing check |
| Duplicate Transfer-Encoding | 400, close | 0 | 0 | 0 | h11 rejected |
| Unsupported Transfer-Encoding | 400, close | 0 | 0 | 0 | h11 rejected |
| Whitespace before header colon | 400, close | 0 | 0 | 0 | h11 rejected |
| Obsolete fold after M2 version header | 200 | 1 | 1 | 1 | h11 unfolded/trimmed |
| Duplicate identical M2 header | 401 | 1 | 0 | 0 | M2 auth rejected |
| Duplicate conflicting M2 header | 401 | 1 | 0 | 0 | M2 auth rejected |
| Malformed request line | 400, close | 0 | 0 | 0 | h11 rejected |
| Absolute-form target | 404 | 1 | 0 | 0 | route policy denied |
| 20,000-byte request target | 404 | 1 | 0 | 0 | reached ASGI; route denied |
| 600 additional headers | 200 | 1 | 1 | 1 | direct Uvicorn accepted |
| One 20,000-byte header value | 200 | 1 | 1 | 1 | direct Uvicorn accepted |
| Fragmented header delivery | 200 | 1 | 1 | 1 | parsed as a valid request |
| Two pipelined valid requests | 200, 200 | 2 | 2 | 2 | valid sequential effects |
| Body and valid request after conflicting framing | 400, close | 0 | 0 | 0 | h11 rejected and closed |

Every request that produced a rejection had zero handler executions and zero
nonce reservations. The material failure is that several wire forms required
to reject were instead normalized and accepted.

## Live-bind evidence

With synthetic testnet configuration satisfying the current live startup
checks, this command reached successful application startup:

    python -m uvicorn gateway.server:app --host 0.0.0.0 --port 0

Uvicorn reported a listener on http://0.0.0.0:<ephemeral-port>. It was then
stopped cleanly. This proves that gateway main choosing loopback is a safe
default, not an enforced live deployment boundary. A caller can bypass it by
invoking Uvicorn directly with a public host.

## Semantic and security assessment

Leading/trailing optional whitespace around a field value is an
RFC-equivalent representation after HTTP field parsing. Repeated
Content-Length fields with identical decimal values, and a comma-list of
identical values, are recoverable equivalent representations that an HTTP/1.1
recipient may reject or replace with one valid field. The present h11 behavior
chooses normalization. Conflicting lengths are ambiguous and are rejected.

Normalization does not by itself forge the M2 signature: the authenticated
logical value and body digest remain the same, and accepted requests still
consume their nonces. Identical Content-Length values also describe one body
length. The risk is parser agreement and boundary assurance:

- a proxy and backend that disagree on framing can enable request smuggling;
- accepting obsolete folding or unconstrained line/header sizes broadens the
  parser surface and resource-exhaustion exposure;
- signing an ASGI-normalized request cannot prove which equivalent wire form
  the client sent;
- direct public Uvicorn bypasses any Caddy-only rejection, TLS, and mTLS
  assumptions; and
- without a real pinned Caddy chain test, proxy/backend agreement remains
  unverified.

Replay protection remains effective for the normalized request only when the
validated durable schema and nonce store are available. It does not convert
normalization into proof of the original strict wire contract.

## Explicit options

### Option 1 — retain the original exact-wire rejection contract

Adopt a separately reviewed ingress that exposes or rejects the relevant raw
forms before normalization. It must be the only public listener, reject OWS,
duplicate/comma Content-Length, obsolete folding, ambiguous framing, and
bounded line/header excess, and forward one canonical request to loopback
Uvicorn. Direct live Uvicorn public binds must fail.

Costs:

- a new pinned runtime or proxy policy and its supply-chain maintenance;
- independent parser and smuggling review;
- TLS/mTLS, forwarding-header, timeout, body-limit, logging, and upgrade
  ownership;
- raw TCP/TLS tests against every supported version and upgrade;
- deployment/network-policy changes plus rollback and operations training; and
- ongoing differential proxy/backend parser tests.

This option preserves the literal acceptance contract but has the higher
dependency, operational, and maintenance burden. A custom parser or unreviewed
TCP shim is specifically not acceptable.

### Option 2 — revise M2 to authenticate proxy-normalized semantics

Explicitly authorize RFC-equivalent OWS and identical Content-Length
normalization at one pinned, reviewed proxy boundary. Continue to require
rejection of conflicting lengths, CL+TE ambiguity, duplicate/unsupported TE,
whitespace before the colon, obsolete folding, malformed lines/targets,
unbounded line/header count/bytes, and all parser disagreement.

The revised contract must also:

- pin and execute the tested Caddy image rather than use latest;
- prove Caddy-to-Uvicorn behavior with raw TLS/TCP integration tests;
- make Caddy the only public listener and make public Uvicorn startup fail in
  staging, testnet, and production;
- strip/overwrite trusted proxy, forwarding, and mTLS headers;
- bind M2 signatures to the documented normalized semantic values and exact
  post-framing body bytes;
- test that removing each ingress rule makes the raw-wire suite fail; and
- rerun smuggling, replay, restart, worker, lifecycle, and deployment gates on
  every ingress upgrade.

Costs:

- an explicit M2 acceptance/specification change and independent review;
- a locally available pinned Caddy test runtime in CI and reviewer
  environments;
- deployment manifest and network-policy enforcement;
- ongoing version-pinned differential integration testing; and
- client documentation for the normalized request contract.

## Recommendation and required authorization

Recommend **Option 2**, because the two originally reviewed forms are
standards-equivalent after parsing and their security can be expressed more
precisely as one pinned parser boundary plus mandatory rejection of ambiguous
framing. This recommendation is conditional: Caddy 2.11.4 must first be made
available through an authorized, checksum/content-digest-verified local
toolchain and must pass the complete raw TLS-to-Uvicorn matrix. If that
executable evidence shows Caddy cannot reject obsolete folding, ambiguous
framing, or configured line/header limits before proxying, use Option 1
instead.

No contract revision is authorized by this report. The owner must explicitly
choose Option 1 or Option 2 and separately authorize any required ingress
toolchain acquisition.

## Scope and invariant impact

Only this decision report changed. Gateway code, Caddy configuration,
deployment blueprints, workflows, route classifications, replay schema,
INV-5 traceability, frontend /nodes, credentials, vendors, and runtime
behavior are untouched.

INV-1 through INV-10 are not touched. Mock-mode behavior is unchanged. M1
containment and F17 lifecycle behavior are unchanged. F08 and M2 remain open.

Next action: explicit ingress-contract decision. No implementation slice should
start until that authorization is recorded.
