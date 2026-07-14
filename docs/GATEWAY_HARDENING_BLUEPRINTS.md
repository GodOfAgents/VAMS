# VAMS Gateway Hardening Blueprints (TLS & mTLS)

**Lifecycle:** Testnet deployment template; runtime evidence pending
**Last verified:** 2026-07-14

This guide provides configuration blueprints for securing the VAMS Gateway Server transport layer using **Caddy** (as an HTTPS reverse proxy) and **mutual TLS (mTLS)** for client authentication.

---

## 1. Caddy Reverse Proxy (HTTPS & TLS Termination)

Caddy automatically handles Let's Encrypt certificate acquisition, renewal, and HTTP-to-HTTPS redirection. It is the recommended proxy for VAMS Gateway deployments.

### Caddyfile Configuration

Use `gateway/Caddyfile.testnet.example` as the deployment template. The gateway
must run behind Caddy on loopback:

```bash
VAMS_ENV=testnet \
GATEWAY_ADMIN_DID=did:key:<admin-verifying-key> \
GATEWAY_ADMIN_PASSWORD=<non-default-secret> \
GATEWAY_HEARTBEAT_CERT_FINGERPRINTS=<allowed-client-cert-fingerprint> \
uvicorn gateway.server:create_public_app --factory --host 127.0.0.1 --port 8000
```

The Caddy proxy must set the headers consumed by `gateway/server.py`:
`X-VAMS-Client-Cert-Verified` and `X-VAMS-Client-Cert-Fingerprint`.

```caddy
gateway.vams.network {
    tls {
        client_auth {
            mode require_and_verify
            trusted_ca_cert_file /etc/caddy/certs/vams-root-ca.crt
        }
    }

    reverse_proxy 127.0.0.1:8000 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
        header_up X-VAMS-Client-Cert-Verified "success"
        header_up X-VAMS-Client-Cert-Fingerprint "{http.request.tls.client.fingerprint}"
    }
}
```

### Running Caddy

Run Caddy using Docker:

```bash
docker run -d -p 80:80 -p 443:443 \
    -v $PWD/Caddyfile:/etc/caddy/Caddyfile \
    -v caddy_data:/data \
    -v caddy_config:/config \
    caddy:2@sha256:af5fdcd76f2db5e4e974ee92f96ee8c0fc3edb55bd4ba5032547cbf3f65e486d
```

Validate the template before deployment:

```bash
docker run --rm \
    -e VAMS_ROOT_CA_CERT=/etc/ssl/certs/ca-certificates.crt \
    -v "$PWD/gateway/Caddyfile.testnet.example:/etc/caddy/Caddyfile:ro" \
    caddy:2@sha256:af5fdcd76f2db5e4e974ee92f96ee8c0fc3edb55bd4ba5032547cbf3f65e486d \
    caddy adapt --config /etc/caddy/Caddyfile --adapter caddyfile --pretty
docker run --rm \
    -e VAMS_ROOT_CA_CERT=/etc/ssl/certs/ca-certificates.crt \
    -v "$PWD/gateway/Caddyfile.testnet.example:/etc/caddy/Caddyfile:ro" \
    caddy:2@sha256:af5fdcd76f2db5e4e974ee92f96ee8c0fc3edb55bd4ba5032547cbf3f65e486d \
    caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
```

---

## 2. Mutual TLS (mTLS) Client Authentication

mTLS requires nodes to present a valid cryptographic certificate signed by the VAMS root Certificate Authority (CA) to connect to the gateway. This is recommended for high-security node-to-gateway telemetry lines.

### Uvicorn Startup Command

```bash
uvicorn gateway.server:create_public_app --factory --host 127.0.0.1 --port 8000
```

Direct public Uvicorn binding is not a live deployment mode. Caddy performs TLS
termination and client certificate validation, then forwards to loopback.

### Runtime selectors and private VDSO shadow

`VAMS_ENV` is a fail-closed selector and accepts only `local`, `staging`,
`testnet`, or `production`. `VAMS_NETWORK` is independent and accepts only
`polygon-amoy` or `cardano-preprod`; it is required for a private VDSO shadow.
Missing, unknown, or blank runtime selectors abort startup. A public process
must explicitly set `VAMS_ENV` and `VDSO_MODE=off` before invoking
`gateway.server:create_public_app` as an application factory.

Public Gateway deployments must retain `VDSO_MODE=off`, which mounts no VDSO
router. A private shadow is a separate application-factory composition:

```powershell
uvicorn gateway.server:create_shadow_app --factory --host 127.0.0.1 --port 8000
```

It requires `VDSO_MODE=shadow`, `VDSO_POSTGRES_DSN`,
`VDSO_AMOY_RPC_URL`, and address plus runtime-code-hash variables for all seven
modules (`VDSO_OBJECT_STORE`, `VDSO_RESERVATION_MANAGER`,
`VDSO_ADAPTER_REGISTRY`, `VDSO_PROGRAM_REGISTRY`, `VDSO_PROOF_ROUTER`,
`VDSO_CAPABILITY_ROUTER`, and `VDSO_EXECUTION_KERNEL`, each suffixed with
`_ADDRESS`, `_CODE_HASH`, `_DEPLOYMENT_TX_HASH`, `_DEPLOYMENT_BLOCK_NUMBER`,
and `_DEPLOYMENT_BLOCK_HASH`). Per-module creation provenance is required
because a Forge broadcast deploys the seven contracts in separate
transactions. Control-plane binding also requires
`VAMS_VDSO_GOVERNANCE_SAFE`, `VAMS_VDSO_TIMELOCK`,
`VAMS_VDSO_PAUSE_COUNCIL`, `VAMS_VDSO_GUARDIAN`,
`VAMS_VDSO_RECOVERY_AUTHORITY`, and `VAMS_VDSO_DEPLOYER`. Cardano-host reads
also require `VAMS_VDSO_SAFE_PROXY_RUNTIME_CODE_HASH`,
`VAMS_VDSO_SAFE_SINGLETON`,
`VAMS_VDSO_SAFE_SINGLETON_RUNTIME_CODE_HASH`, and
`VAMS_VDSO_TIMELOCK_RUNTIME_CODE_HASH` from the signed deployment evidence,
plus the timelock's own `VAMS_VDSO_TIMELOCK_DEPLOYMENT_TX_HASH`,
`VAMS_VDSO_TIMELOCK_DEPLOYMENT_BLOCK_NUMBER`, and
`VAMS_VDSO_TIMELOCK_DEPLOYMENT_BLOCK_HASH`.
Cardano-host reads add the pinned official `VDSO_CARDANO_BLOCKFROST_URL` and a
secret-injected `VDSO_CARDANO_BLOCKFROST_PROJECT_ID`.

The on-chain observer checks chain ID `80002`, exact runtime code hashes,
all-seven paused state, module wiring, timelock delay/known role bindings,
deployer role removal, Safe proxy/singleton runtime identity, the governance
3-of-5 and pause/guardian/recovery 2-of-3 owner thresholds, zero enabled Safe
modules, zero Safe transaction/module guards, zero Safe fallback handlers, zero
Safe transaction nonce, zero recovery verifier, and deterministic empty domain, object, reservation, adapter,
program, verifier, receipt, and execution records. Every verification is pinned to one
block number/hash, proves each address had no code before its recorded creation
block, binds its creation receipt, and reconstructs all module and timelock role
grants/revocations from creation through the fixed snapshot. Any unknown module
event, unexpected role holder, unpause, or active-state mutation fails closed.
Signed deployment-event evidence remains a promotion requirement independent
of this live observer. In particular, current nonce and extension state cannot
prove the absence of historical Safe hash preapprovals; a pinned audited Safe
release plus complete setup and `ApproveHash` history remains mandatory. Live
shadow composition initializes PostgreSQL atomic
nonce/replay stores during application lifespan. The shadow exposes
authenticated `READ` behavior only and cannot publish sidecars, mutate state,
execute Tier 2, or transfer value.

Live PostgreSQL transport is accepted only over a local Unix socket/loopback or
with remote `sslmode=verify-full` plus an explicit `sslrootcert`. Replay expiry
and bounded pruning use PostgreSQL `clock_timestamp()` in the claim transaction,
so one process's clock cannot prematurely overwrite another process's live claim.

---

## 3. Client Node Configuration (Neuron)

For nodes sending telemetry to an mTLS-enabled gateway:

### Python Request client setup (`neuron/gateway/client.py`)

Ensure your HTTP client passes client certificates:

```python
import requests

# Path to client certificate and key
client_cert = ('certs/client.crt', 'certs/client.key')
ca_cert = 'certs/ca.crt'

response = requests.post(
    "https://gateway.vams.network:8443/heartbeat",
    json=heartbeat_payload,
    cert=client_cert,
    verify=ca_cert
)
```
