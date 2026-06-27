# VAMS API Reference (v1.3.0-oms)

The VAMS Gateway Server provides a unified REST/WebSocket interface to the decentralized infrastructure stack. For intelligence layer internals see [INTELLIGENCE_LAYER.md](./INTELLIGENCE_LAYER.md). For OMS integration architecture see [team/ARCHITECTURE_v0-6-0.md](./team/ARCHITECTURE_v0-6-0.md).

> [!WARNING]
> **Implementation Status Disclosure:**
> The REST Gateway Server (`gateway/server.py`) currently implements the core node registration, heartbeat monitoring, Resource Composer matchmaking, and basic economics/epoch endpoints.
> Endpoints in this reference marked with **`v1.3.0+`** (including `/identity/` institutional compliance checks, `/payments/` Coinme fiat on-ramps, and stablecoin payout preference setters) are implemented client-side within the Neuron SDK (`neuron/sdk/`) or are simulated under test modes. Direct gateway HTTP routing for these endpoints is in deployment prep.

## Base URL
`/api/v1`

## Authentication
VAMS requires bearer token authentication. Include the `Authorization` header containing either an API Key or a signed payload (`x402`).

`Authorization: Bearer <vams_token>`

---

## 1. Data Availability (DA) 
Endpoints for checking the status and history of the Multi-DA Performance Anchor.

### `GET /da/status`
Returns the connectivity and health status of all supported DA layer adapters.

- **Response (200 OK):**
  ```json
  {
    "version": "v0.2.0-alpha",
    "da_layer": "Phase 0 Foundation",
    "adapters": {
      "celestia": {
        "name": "CelestiaDAAdapter",
        "rpc_url": "https://rpc-mocha.pops.one",
        "mock_mode": true,
        "healthy": true
      },
      "near": {
        "name": "NearDAAdapter",
        "rpc_url": "https://rpc.testnet.near.org",
        "mock_mode": true,
        "healthy": true
      },
      "eigenda": {
        "name": "EigenDAAdapter",
        "rpc_url": "https://holesky.drpc.org",
        "mock_mode": true,
        "healthy": true
      },
      "avail": {
        "name": "AvailDAAdapter",
        "rpc_url": "https://avail-turing.api.onfinality.io/public",
        "mock_mode": true,
        "healthy": true
      }
    }
  }
  ```

### `GET /da/anchors`
Queries anchored performance audit records that have been posted to the DA layers.

- **Query Parameters:**
  - `protocol` (optional, e.g. `celestia`, `near`)
  - `limit` (optional, default: 50)
- **Response (200 OK):**
  ```json
  {
    "total": 1,
    "protocol_filter": null,
    "anchors": [
      {
        "node_id": "test_node_01",
        "protocol": "celestia",
        "blob_id": "blob_cel_12345",
        "height": 9836950,
        "report_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "timestamp": 1736703540.123
      }
    ]
  }
  ```

---

## 2. Resource Composer
Endpoints for dynamic blueprint packaging.

### `POST /composer/blueprint`
Generates a multi-provider infrastructure blueprint based on resource tags.

- **Request Body:**
  ```json
  {
    "target_region": "eu-central-1",
    "resource_tags": ["gpu:h100>2", "memory>128GB", "zkml:enabled"],
    "max_cost_hour_vams": "50",
    "skill_vector": [0.92, -0.12, 0.34, 0.05, -0.21, 0.0, 0.0, 0.0, 0.0, 0.0]
  }
  ```
  > **Note (`skill_vector`):** Optional. 10-dimensional PCA coordinate vector representing the
  > desired skill profile for matched nodes. Omit to use 4-axis scoring (v1.0.0-icn behavior).
  > When provided, a 5th `skill_alignment` score is added and the response includes
  > `skill_alignment_scores` per matched block. See [INTELLIGENCE_LAYER.md](./INTELLIGENCE_LAYER.md).
- **Response (200 OK):**
  ```json
  {
    "blueprint_id": "bp-9912",
    "matched_blocks": ["sb-102", "sb-405"],
    "estimated_cost_per_hour": 35.5,
    "confidence_score": 0.95,
    "skill_alignment_scores": {"sb-102": 0.87, "sb-405": 0.61}
  }
  ```
  > **Note (`skill_alignment_scores`):** Present only when `skill_vector` was provided in the request.

---

## 3. Economics & Settlement
Interact with regional emissions and composed settlements.

### `POST /economics/escrow`
Locks capital for a composed blueprint execution.

- **Request Body:**
  ```json
  {
    "blueprint_id": "bp-9912",
    "duration_hours": 24
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "allocation_id": "0xabcd...",
    "escrow_status": "locked",
    "expires_at": 1735689600
  }
  ```

### `GET /economics/region/{region_id}`
Returns the current dynamic multiplier for a geographical region.

- **Response (200 OK):**
  ```json
  {
    "region_id": "eu-central-1",
    "multiplier_bps": 12000,
    "demand_status": "HIGH"
  }
  ```

---

## 4. Service Blocks Marketplace
Interact with reusable execution environments.

### `GET /services/blocks`
List available Service Blocks.

- **Query Parameters:** `category`, `min_tier`
- **Response (200 OK):**
  ```json
  {
    "blocks": [
      {
        "id": "sb-102",
        "name": "Llama 3 70B TEE-Wrapped",
        "category": "ai-inference",
        "trust_tier": 2,
        "builder_rev_share_bps": 500
      }
    ]
  }
  ```

---

## 5. Sentinel Network
Used by monitoring watchtowers to report SLA compliance.

### `POST /sentinel/report`
Submit an SLA observation report.

- **Request Body:**
  ```json
  {
    "provider_id": "0x123...",
    "uptime_ms": 86000000,
    "latency_avg_ms": 45,
    "signature": "0x...",
    "activation_vector": [0.12, -0.34, ...]   
  }
  ```
  > **Note (`activation_vector`):** Optional. Final-layer hidden state from the challenge
  > response. When present, the Sentinel computes Mahalanobis anomaly score and returns
  > `activation_anomaly_score` and `adversarial_flag` in the response.
- **Response (200 OK):**
  ```json
  {
    "status": "recorded",
    "slashed": false,
    "activation_anomaly_score": 1.24,
    "adversarial_flag": false
  }
  ```
  > **Note (`adversarial_flag`):** `true` triggers Mahalanobis anomaly review in the
  > `SLAEnforcer` contract. Present only when `activation_vector` was provided in the request.

---

## 6. Intelligence Layer (v1.2.0+)

Read-only query endpoints for the on-node Intelligence Layer state.

### `GET /intelligence/skill-profile/{node_id}`
Returns the current skill profile (PCA skill-space fingerprint) of a registered node.

- **Response (200 OK):**
  ```json
  {
    "node_id": "0x123...",
    "coordinates": [0.91, -0.14, 0.32, 0.06, -0.22, 0.01, -0.05, 0.12, 0.03, -0.08],
    "magnitude": 0.98,
    "dominant_skill": 0,
    "sample_count": 1024,
    "model_id": "llama3-8b"
  }
  ```

### `GET /intelligence/anomaly-score/{node_id}`
Returns the latest anomaly score recorded for a node.

- **Response (200 OK):**
  ```json
  {
    "node_id": "0x123...",
    "mahalanobis_distance": 1.24,
    "anomaly_score": 0.21,
    "adversarial_flag": false,
    "threshold": 3.0,
    "most_anomalous_component": 2,
    "last_updated": 1735689600
  }
  ```

### `GET /intelligence/model-info`
Returns the current Intelligence Layer model metadata.

- **Response (200 OK):**
  ```json
  {
    "pca_model_version": "1.0.0",
    "n_components": 10,
    "hidden_dim": 4096,
    "fit_samples": 10000,
    "total_variance_captured": 0.93,
    "baseline_threshold": 3.0,
    "max_alpha": 0.3
  }
  ```

---

## 7. Identity & Compliance (v1.3.0+)

Endpoints for OMS-based KYC/KYB institutional identity verification.
Required for agents routing via the P3 Institutional Compliance CLR path.

### `GET /identity/status/{agent_id}`
Returns the OMS identity verification status for an agent address.

- **Response (200 OK):**
  ```json
  {
    "agent_id": "0x123...",
    "is_verified": true,
    "kyc_tier": "INSTITUTIONAL",
    "verified_at": 1746547200,
    "expires_at": 1778083200
  }
  ```
- **Response (200 OK — unverified):**
  ```json
  {
    "agent_id": "0x456...",
    "is_verified": false,
    "kyc_tier": null,
    "verified_at": null,
    "expires_at": null
  }
  ```

### `POST /identity/verify`
Triggers an OMS KYC credential check for an agent address.

- **Request Body:**
  ```json
  {
    "agent_id": "0x123...",
    "credential_type": "KYB"
  }
  ```
- **Response (202 Accepted):**
  ```json
  {
    "status": "pending",
    "verification_session_id": "vs-8821",
    "redirect_url": "https://oms.polygon.technology/verify/vs-8821"
  }
  ```
  > **Note:** Verification is asynchronous. Poll `GET /identity/status/{agent_id}` to check completion.

---

## 8. Fiat On-Ramp — Coinme (v1.3.0+)

Endpoints for fiat-to-$VAMS conversion via the Coinme integration.
Allows consumers to fund agent escrow accounts using credit card or bank transfer.

### `POST /payments/topup/create`
Creates a Coinme checkout session for fiat-to-$VAMS conversion.

- **Request Body:**
  ```json
  {
    "amount_fiat": 100.0,
    "currency": "USD",
    "dest_address": "0x123..."
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "session_id": "cs-7712",
    "checkout_url": "https://pay.coinme.com/checkout/cs-7712",
    "estimated_vams": 423.5,
    "fee_pct": 3.5,
    "expires_at": 1746550800
  }
  ```

### `GET /payments/topup/rate`
Returns the current fiat-to-$VAMS conversion rate.

- **Query Parameters:** `currency` (e.g., `USD`, `EUR`, `GBP`)
- **Response (200 OK):**
  ```json
  {
    "from_currency": "USD",
    "to_token": "VAMS",
    "rate": 4.235,
    "fee_pct": 3.5,
    "valid_for_seconds": 30
  }
  ```

### `POST /payments/topup/webhook`
Coinme payment confirmation webhook (called by Coinme upon successful payment).

- **Request Body:** Coinme-signed webhook payload (HMAC-SHA256)
- **Response (200 OK):**
  ```json
  { "status": "processed", "escrow_tx": "0xabc..." }
  ```
  > **Security:** Verify the `X-Coinme-Signature` header before processing. See [DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md#7-fiat-top-up-via-coinme-v130--consumers) for webhook validation code.

---

## 9. Stablecoin Payouts (v1.3.0+)

Endpoints for managing provider stablecoin payout preferences on the `RewardDistributor` contract.

### `POST /economics/payout-preference`
Sets the provider's payout preference. Signed by the provider's session key or EOA.

- **Request Body:**
  ```json
  {
    "provider_address": "0x123...",
    "mode": "STABLECOIN",
    "signature": "0x..."
  }
  ```
  > **`mode` values:** `VAMS_ONLY` (default), `STABLECOIN` (100% USDC/USDT), `HYBRID` (50/50 split)
- **Response (200 OK):**
  ```json
  {
    "status": "set",
    "tx_hash": "0xdef...",
    "mode": "STABLECOIN"
  }
  ```

### `GET /economics/payout-preference/{address}`
Queries the current payout preference for a provider address.

- **Response (200 OK):**
  ```json
  {
    "provider_address": "0x123...",
    "mode": "STABLECOIN",
    "mode_int": 1,
    "supported_tokens": ["USDC", "USDT"]
  }
  ```

---

## 10. Nodes Registry & Telemetry (v0.8.0)

Endpoints for querying the active DePIN compute nodes registry and telemetry status.

### `GET /nodes`
Returns a list of all registered nodes including their live telemetry data, cognitive profiles, and TEE remote attestations.

- **Response (200 OK):**
  ```json
  {
    "total": 1,
    "online": 1,
    "nodes": [
      {
        "node_id": "node_01",
        "public_key": "0xabc...",
        "last_block": 104230,
        "network": "Amoy",
        "last_seen": 1782212345.0,
        "heartbeat_count": 42,
        "first_seen": 1782210000.0,
        "region": "us-east-1",
        "cost_per_hour": 0.15,
        "credit_score": 750,
        "passports": "ERC-8004 Phala TEE",
        "skills": ["llm-inference", "vector-db-ops"],
        "cognitive_profile": {
          "K": 0.85,
          "RW": 0.90,
          "M": 0.75,
          "R": 0.80,
          "WM": 0.85,
          "MS": 0.95,
          "MR": 0.90,
          "V": 0.50,
          "A": 0.30,
          "S": 0.70
        },
        "is_online": true,
        "uptime": "39m",
        "last_seen_formatted": "16:43:11"
      }
    ]
  }
  ```
