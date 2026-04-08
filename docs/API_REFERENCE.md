# VAMS API Reference (v1.0.0-icn)

The VAMS Gateway Server provides a unified REST/WebSocket interface to the decentralized infrastructure stack.

## Base URL
`/api/v1`

## Authentication
VAMS requires bearer token authentication. Include the `Authorization` header containing either an API Key or a signed payload (`x402`).

`Authorization: Bearer <vams_token>`

---

## 1. Data Availability (DA) 
Endpoints for interacting with the Multi-DA Performance Anchor.

### `POST /da/anchor`
Anchors a performance report to a selected DA layer.

- **Request Body:**
  ```json
  {
    "protocol": "celestia",
    "blob": "e3b0...985",
    "provider_id": "0x123..."
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "status": "anchored",
    "receipt": "0xabc...",
    "transaction_hash": "0xdef..."
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
    "max_cost_hour_vams": "50"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "blueprint_id": "bp-9912",
    "matched_blocks": ["sb-102", "sb-405"],
    "estimated_cost_per_hour": 35.5,
    "confidence_score": 0.95
  }
  ```

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
    "signature": "0x..."
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "status": "recorded",
    "slashed": false
  }
  ```
