# M2.4b Envoy ingress current-source revalidation

Date: 2026-10-03
Status: PASS for the focused M2.4b Envoy loopback mTLS suite; independent review PASS.

## Verification

The focused neuron/tests/test_m2_4b_envoy_ingress.py suite passed 10/10 under pinned Python 3.12.14 / pytest 9.1.1. The suite verified the local Envoy executable SHA-256 against its pinned digest and checked its 1.39.1 version. OpenSSL 3.5.5 generated disposable one-day test certificates. The run was network-isolated; Envoy and Uvicorn bound to loopback; source was read-only. Exact command, binary/source hashes and captures are in this directory.

The integration exercises mTLS gateway requests, trust-bound certificate fingerprint handling, replay persistence across gateway restart, HTTP framing ambiguity, header normalization and proxy identity forwarding. Ten cases passed; no tests skipped.

## Limits

This is a synthetic local handshake with temporary certificates, local SQLite and loopback processes. It does not establish public ingress, production TLS/certificate operations, external credentials, deployed Envoy behavior, testnet transactions, or deployment readiness. No tool was installed or fetched, and no source, credential, vendor, or deployment state changed.
