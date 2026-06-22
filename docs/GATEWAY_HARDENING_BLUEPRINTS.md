# VAMS Gateway Hardening Blueprints (TLS & mTLS)

This guide provides configuration blueprints for securing the VAMS Gateway Server transport layer using **Caddy** (as an HTTPS reverse proxy) and **mutual TLS (mTLS)** for client authentication.

---

## 1. Caddy Reverse Proxy (HTTPS & TLS Termination)

Caddy automatically handles Let's Encrypt certificate acquisition, renewal, and HTTP-to-HTTPS redirection. It is the recommended proxy for VAMS Gateway deployments.

### Caddyfile Configuration

Create a file named `Caddyfile` on your gateway server host:

```caddy
# Replace with your gateway's domain name
gateway.vams.network {
    # Reverse proxy requests to the local Uvicorn ASGI server
    reverse_proxy 127.0.0.1:8000 {
        # Preserve original headers for rate limiting and CORS validation
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }

    # Enable HTTP/2 and HTTP/3
    protocols h1 h2 h3

    # Hardened TLS configuration
    tls {
        protocols tls1.2 tls1.3
        ciphers ECDHE-ECDSA-AES256-GCM-SHA384 ECDHE-RSA-AES256-GCM-SHA384 ECDHE-ECDSA-CHACHA20-POLY1305
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

---

## 2. Mutual TLS (mTLS) Client Authentication

mTLS requires nodes to present a valid cryptographic certificate signed by the VAMS root Certificate Authority (CA) to connect to the gateway. This is recommended for high-security node-to-gateway telemetry lines.

### Uvicorn mTLS Configuration

To enable mTLS directly at the Uvicorn level, start the server using the `--ssl-keyfile`, `--ssl-certfile`, and `--ssl-ca-certs` options.

#### Startup Command

```bash
uvicorn gateway.server:app \
    --host 0.0.0.0 \
    --port 8443 \
    --ssl-keyfile certs/server.key \
    --ssl-certfile certs/server.crt \
    --ssl-ca-certs certs/ca.crt \
    --ssl-cert-reqs 2  # 2 = ssl.CERT_REQUIRED
```

### Caddy mTLS configuration (Alternative)

If you terminate TLS at the Caddy proxy level, you can configure Caddy to perform client certificate validation:

```caddy
gateway.vams.network {
    reverse_proxy 127.0.0.1:8000

    tls {
        client_auth {
            mode require_and_verify
            trusted_ca_cert_file /etc/caddy/certs/ca.crt
        }
    }
}
```

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
