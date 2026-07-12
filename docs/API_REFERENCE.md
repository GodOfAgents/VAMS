# VAMS Gateway API Reference

**Gateway source:** `gateway/server.py`
**Gateway version:** v0.2.0-alpha
**Lifecycle:** Implemented API surface; live deployment pending
**Last verified:** 2026-07-12

This document describes the routes implemented by the root Gateway FastAPI
application. The application has no `/api/v1` prefix. Identity, Coinme, Trails,
and payout clients live in the Neuron SDK; they are not Gateway HTTP routes and
must not be advertised as such.

## Security Boundary

Direct Gateway startup binds to loopback. Live deployments require Caddy TLS,
explicit CORS origins, DID administration, and proxy-verified mTLS client
certificates for telemetry. Mock DA reporting is rejected in testnet and
production environments.

## Health And Nodes

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/` | Render the local status page. |
| `GET` | `/health` | Return Gateway health, version, and composer availability. |
| `POST` | `/heartbeat` | Register or refresh node telemetry. |
| `GET` | `/nodes` | List known nodes. |

## Resource Composition

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/compose` | Request a resource-composition plan. |
| `DELETE` | `/compose/{instance_id}` | Cancel a composed instance. |
| `GET` | `/compose/instances` | List composed instances. |
| `GET` | `/compose/blueprints` | List available blueprints. |

## Service And Economics Status

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/services/blocks` | List registered Service Block metadata. |
| `GET` | `/services/macros` | List Service Block macros. |
| `GET` | `/economics/status` | Return economics status data. |
| `GET` | `/economics/epochs` | List tracked economic epochs. |
| `GET` | `/economics/epochs/{epoch_id}` | Return one economic epoch. |
| `GET` | `/economics/estimate-apr` | Return the current estimate endpoint response. |

## Data Availability Status

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/da/status` | Return configured DA route status. |
| `GET` | `/da/anchors` | Return locally known DA anchors. |

## SDK-Only Integrations

`OMSIdentityVerifier`, `TrailsClient`, `CoinmeClient`, and the DA SDKs are
client libraries under `neuron/sdk/` and `neuron/payments/`. Their defaults are
mock-safe for local development and fail closed when a live environment is
configured without explicit credentials and non-mock integrations. They do not
provide public Gateway routes until separately implemented, tested, and added
to this reference.

## Legacy Neuron Gateway

`neuron/gateway/server.py` is a separate lightweight agent-facing service with
`/agents/register`, `/heartbeat`, `/tasks/pending`, and
`/tasks/{task_id}/result`. It is not a substitute for the root Gateway and has
its own deployment and security review requirements.
