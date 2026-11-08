# M2.4b-R2 pinned-ingress verification

Date: 2026-09-24
Scope: M2-R2 Finding 2 only
Verdict: BLOCKED — pinned Caddy 2.11.4 accepts prohibited framing

## Outcome

Implementation stopped at the mandatory parser-behavior boundary. The official,
checksum-verified Caddy 2.11.4 runtime accepted both of these raw HTTP/1.1 forms
over TLS and forwarded them to loopback Uvicorn/h11:

- Content-Length together with Transfer-Encoding: chunked; and
- obsolete folded request-header continuation.

Uvicorn received one request in each case and the synthetic handler returned
HTTP 200. Caddy removed Content-Length and forwarded the chunked body for the
first case; it unfolded X-Probe: one plus the continuation into
X-Probe: one two for the second. The original raw forms were no longer
available to ASGI.

The authorized M2.4b Option 2 contract requires both forms to be rejected and
requires an immediate stop on any pinned-ingress acceptance or parser-boundary
disagreement. Therefore no M2 contract revision, ingress header trust change,
application middleware, custom parser, Caddyfile change, CI/deployment change,
or live-bind claim was made. F08 and M2 remain open. INV-5 traceability and the
frontend /nodes disposition are unchanged.

## Verified acquisition

The runtime is stored outside the repository at:

    /home/GodOfAgents/vams-evidence/toolchains/caddy-2.11.4/caddy

| Item | Recorded value |
| --- | --- |
| Official release | https://github.com/caddyserver/caddy/releases/tag/v2.11.4 |
| Checksum manifest URL | https://github.com/caddyserver/caddy/releases/download/v2.11.4/caddy_2.11.4_checksums.txt |
| Archive URL | https://github.com/caddyserver/caddy/releases/download/v2.11.4/caddy_2.11.4_linux_amd64.tar.gz |
| Version output | v2.11.4 h1:XKxkMTgNSizEvKG6QHue6cAsFOteU2qA61w2tKkCWi0= |
| Expected manifest SHA-256 | 7bfa272f3ece3ac987c1e06cd3c0acf126749d88110c20d7b83dcea3caaf0080 |
| Observed manifest SHA-256 | 7bfa272f3ece3ac987c1e06cd3c0acf126749d88110c20d7b83dcea3caaf0080 |
| Published archive SHA-512 | 8220d1f013b6f27510247b2360c9e0ca9f018feebd82515f07635318b34ff9777ccc8fd0b6e6f2486ce3a33fe389fbb7db12d05baa474f4587509fb4f5ebf1c9 |
| Verified archive SHA-512 | same; sha512sum --check --strict returned OK |
| Observed archive SHA-256 | 527fbf917c39189a1e3b31d34fa955601680b2d5c8055d2a87b8b9588dec7bb9 |
| Observed binary SHA-256 | b7105518e3ed1c0761f232e44fc09345535533c9cb0abf0e12809416c7ac64d9 |

Acquisition used curl --fail --location --proto '=https' --tlsv1.2 for the
official checksum manifest and archive, verified the manifest asset digest,
selected the exact Linux AMD64 archive entry, ran strict SHA-512 verification,
extracted only into a mode-0700 external toolchain directory, and verified the
reported version before execution. No system install or global PATH change was
performed. A shell-wrapper naming artifact was corrected without re-downloading;
post-correction version and digest checks passed.

## Real-chain evidence

The probe used:

    raw TLS client -> Caddy 2.11.4 -> 127.0.0.1 Uvicorn 0.52.4/h11 0.16.0

All listeners used collision-free ephemeral ports. Caddy required a synthetic,
one-day client certificate issued by a temporary synthetic CA. The certificates,
keys, Caddyfile, process logs, and raw requests lived only in a temporary
directory and were removed on exit. The durable result contains only status,
normalized test metadata, versions, and hashes; it contains no credential,
signature, signer, nonce, or production identifier.

| Raw TLS case | Caddy response | Uvicorn/handler observation | Verdict |
| --- | --- | --- | --- |
| Valid control | 200 | body length 4 | control passed |
| OWS around Content-Length value | 200 | normalized Content-Length: 4 | allowed semantic normalization |
| Duplicate equal Content-Length | 200 | one normalized Content-Length: 4 | allowed semantic normalization |
| Comma-equal Content-Length | 400 | handler not reached | stricter than required |
| Conflicting Content-Length | 400 | handler not reached | required rejection |
| Content-Length plus Transfer-Encoding | 200 | body length 4; chunked framing forwarded | BLOCKER |
| Obsolete folded header | 200 | unfolded X-Probe: one two | BLOCKER |
| Whitespace before header colon | 400 | handler not reached | required rejection |
| Malformed request line | 400 | handler not reached | required rejection |

External sanitized evidence:

- /home/GodOfAgents/vams-evidence/m2_4b_r2/caddy_ingress_probe.py
  SHA-256 9a40632265d6c6772c0c556d95111e340e1f43562d8ecb9c0574ca5520655ad8
- /home/GodOfAgents/vams-evidence/m2_4b_r2/caddy_ingress_probe.json
  SHA-256 0e203caa4f2bc642742c7a919a5066c3672b96a7c2b859b0a7bf1f3466a2a2a0

## Security and invariant impact

No runtime, authentication, replay, route, gateway, workflow, deployment, or
business-logic source changed. INV-1 through INV-10 are untouched. Mock-mode
behavior and F17 lifecycle behavior are unchanged. No nonce-capable M2 request
was used by this parser characterization, and no production secret or identity
was present.

The shortest safe next decision is to reject Option 2 for Caddy 2.11.4 as
configured and choose either a separately reviewed ingress that rejects these
forms before normalization or an explicitly revised security requirement. Do
not compensate inside ASGI because the raw distinctions have already been lost.
