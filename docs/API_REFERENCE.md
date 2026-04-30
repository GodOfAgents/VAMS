# VAMS API Reference (v1.2.0-autoskill)

The VAMS Gateway Server provides a unified REST/WebSocket interface to the decentralized infrastructure stack. For intelligence layer internals see [INTELLIGENCE_LAYER.md](./INTELLIGENCE_LAYER.md).

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
