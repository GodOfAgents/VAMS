# VAMS Gateway Hardening Blueprints (TLS & mTLS)

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
uvicorn gateway.server:app --host 127.0.0.1 --port 8000
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
    caddy:latest
```

Validate the template before deployment:

```bash
caddy adapt --config gateway/Caddyfile.testnet.example --adapter caddyfile
caddy validate --config gateway/Caddyfile.testnet.example --adapter caddyfile
```

---

## 2. Mutual TLS (mTLS) Client Authentication

mTLS requires nodes to present a valid cryptographic certificate signed by the VAMS root Certificate Authority (CA) to connect to the gateway. This is recommended for high-security node-to-gateway telemetry lines.

### Uvicorn Startup Command

```bash
uvicorn gateway.server:app --host 127.0.0.1 --port 8000
```

Direct public Uvicorn binding is not a live deployment mode. Caddy performs TLS
termination and client certificate validation, then forwards to loopback.

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
