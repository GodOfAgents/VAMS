# VAMS Technical Product Requirements Document (PRD)
## For Developers, Engineers, and Contributors

**Version:** 1.0  
**Status:** Ideation Phase  
**Last Updated:** January 2026  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Product Vision](#2-product-vision)
3. [Technical Requirements](#3-technical-requirements)
4. [System Architecture](#4-system-architecture)
5. [Component Specifications](#5-component-specifications)
6. [API Specifications](#6-api-specifications)
7. [Smart Contract Interfaces](#7-smart-contract-interfaces)
8. [Data Models](#8-data-models)
9. [Security Requirements](#9-security-requirements)
10. [Infrastructure Requirements](#10-infrastructure-requirements)
11. [Testing Requirements](#11-testing-requirements)
12. [Development Phases](#12-development-phases)
13. [Contribution Guidelines](#13-contribution-guidelines)

---

## 1. Executive Summary

### 1.1 Product Overview

VAMS (Verifiable and Agentic Modular Stack) is a Layer 3 meta-layer that enables autonomous AI agents to operate across multiple blockchains. The core innovation is the **Conditional L1 Router (CLR)**, which dynamically routes transactions to optimal execution environments based on metadata constraints.

### 1.2 Target Users

| User Type | Description |
|-----------|-------------|
| **Agent Developers** | Build autonomous agents using VAMS SDK |
| **Protocol Integrators** | Connect DePIN protocols to VAMS |
| **Validators** | Operate CLR nodes and Agent L1 validators |
| **Enterprise Clients** | Deploy compliant agent systems |

### 1.3 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Routing Latency (p99) | <200ms | Prometheus metrics |
| Transaction Throughput | 10,000 TPS | Load testing |
| Uptime | 99.9% | Monitoring |
| Security | 0 Critical Vulnerabilities | Audit reports |

---

## 2. Product Vision

### 2.1 Problem Statement

Current blockchain infrastructure fails autonomous agents:

1. **Latency-Security Tradeoff**: Fast chains sacrifice security; secure chains are slow
2. **State Contention**: Agents compete with unrelated traffic for blockspace
3. **Fragmented Liquidity**: No unified access to cross-chain capital
4. **Regulatory Gap**: No protocol-level compliance

### 2.2 Solution

VAMS introduces four routing paths:

```
┌────────────┬─────────────────┬───────────────────┬──────────────┐
│   Path     │   Destination   │    Transport      │   Latency    │
├────────────┼─────────────────┼───────────────────┼──────────────┤
│ Privacy    │ Phala TEE       │ Encrypted RPC     │ ~500ms       │
│ Security   │ Ethereum        │ AggLayer          │ ~12 min      │
│ Sovereignty│ Avalanche L1    │ AWM/Teleporter    │ ~250ms       │
│ Velocity   │ Solana/SEI      │ Hyperlane/LZ      │ ~400ms       │
└────────────┴─────────────────┴───────────────────┴──────────────┘
```

---

## 3. Technical Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-001 | Route transactions based on metadata constraints | P0 | Planned |
| FR-002 | Support Privacy, Security, Sovereignty, Velocity paths | P0 | Planned |
| FR-003 | Execute x402 agent-to-agent payments | P0 | Planned |
| FR-004 | Screen transactions for OFAC compliance | P1 | Planned |
| FR-005 | Support custom gas tokens on Agent L1s | P1 | Planned |
| FR-006 | Provide durable execution via DBOS | P1 | Planned |
| FR-007 | Integrate TEE attestation verification | P1 | Planned |
| FR-008 | Batch settle x402 credits | P2 | Planned |

### 3.2 Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-001 | Routing decision latency | <50ms (p50), <200ms (p99) |
| NFR-002 | System availability | 99.9% |
| NFR-003 | Maximum concurrent agents | 100,000 |
| NFR-004 | Data retention | 90 days (hot), 7 years (cold) |
| NFR-005 | Recovery Time Objective (RTO) | <15 minutes |
| NFR-006 | Recovery Point Objective (RPO) | <1 minute |

### 3.3 Technology Stack

| Layer | Technology | Justification |
|-------|------------|---------------|
| **Language (Backend)** | Rust, TypeScript | Performance, safety |
| **Language (Contracts)** | Solidity, Rust | EVM + Solana support |
| **Database** | PostgreSQL, Redis | DBOS compatibility |
| **Message Queue** | NATS | Low latency |
| **Orchestration** | Kubernetes | Scalability |
| **Monitoring** | Prometheus, Grafana | Industry standard |

---

## 4. System Architecture

### 4.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            VAMS SYSTEM ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐               │
│  │   Agent     │     │   Agent     │     │   Agent     │               │
│  │   SDK       │     │   SDK       │     │   SDK       │               │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘               │
│         │                   │                   │                       │
│         └───────────────────┼───────────────────┘                       │
│                             │                                           │
│                    ┌────────▼────────┐                                  │
│                    │   API GATEWAY   │                                  │
│                    │   (REST/gRPC)   │                                  │
│                    └────────┬────────┘                                  │
│                             │                                           │
│  ┌──────────────────────────┼──────────────────────────┐               │
│  │                    CLR SERVICE                       │               │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐ │               │
│  │  │ Privacy │  │Security │  │Sovereign│  │Velocity │ │               │
│  │  │ Router  │  │ Router  │  │ Router  │  │ Router  │ │               │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘ │               │
│  └───────┼────────────┼────────────┼────────────┼──────┘               │
│          │            │            │            │                       │
│     ┌────▼────┐  ┌────▼────┐  ┌────▼────┐  ┌────▼────┐                 │
│     │  Phala  │  │AggLayer │  │  VAMS   │  │Hyperlane│                 │
│     │   TEE   │  │  (ETH)  │  │ Gateway │  │  (SOL)  │                 │
│     └─────────┘  └─────────┘  └─────────┘  └─────────┘                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Component Diagram

```
┌───────────────────────────────────────────────────────────────┐
│                         COMPONENTS                             │
├───────────────────────────────────────────────────────────────┤
│                                                                │
│  FRONTEND                                                      │
│  ├── vams-sdk (TypeScript/Rust)                               │
│  └── vams-cli                                                  │
│                                                                │
│  BACKEND                                                       │
│  ├── api-gateway (REST/gRPC endpoints)                        │
│  ├── clr-service (Routing decision engine)                    │
│  ├── settlement-service (x402 batch settlement)               │
│  ├── compliance-service (OFAC screening)                      │
│  └── monitor-service (Prometheus exporter)                    │
│                                                                │
│  SMART CONTRACTS                                               │
│  ├── VAMSGateway.sol (Avalanche C-Chain)                      │
│  ├── VAMSRouter.sol (Multi-chain)                             │
│  ├── X402Settlement.sol (Payment settlement)                  │
│  └── AgentRegistry.sol (Agent management)                     │
│                                                                │
│  INFRASTRUCTURE                                                │
│  ├── Kubernetes manifests                                      │
│  ├── Terraform configs                                         │
│  └── Helm charts                                               │
│                                                                │
└───────────────────────────────────────────────────────────────┘
```

---

## 5. Component Specifications

### 5.1 CLR Service

**Purpose:** Core routing decision engine

**Responsibilities:**
- Parse transaction metadata
- Execute routing logic (Privacy → Security → Sovereignty → Velocity)
- Select optimal transport layer
- Return routing decision

**Interface:**

```rust
pub struct CLRService {
    privacy_router: PrivacyRouter,
    security_router: SecurityRouter,
    sovereignty_router: SovereigntyRouter,
    velocity_router: VelocityRouter,
}

impl CLRService {
    pub async fn route(&self, metadata: VAMSMetadata) -> Result<RoutingDecision, CLRError>;
}
```

**Configuration:**

```yaml
clr:
  security_threshold_usd: 10000
  velocity_threshold_ms: 1000
  min_validators_high_value: 13
  ofac_screening_enabled: true
```

### 5.2 VAMS Gateway

**Purpose:** Security perimeter for cross-chain messaging

**Responsibilities:**
- Receive messages from Hyperlane/LayerZero
- Screen for OFAC compliance
- Rate limit traffic
- Relay via Teleporter to Agent L1s

**Deployment:** Dedicated Avalanche L1 (ACP-77)

### 5.3 x402 Settlement Service

**Purpose:** Batch settle agent-to-agent payments

**Responsibilities:**
- Manage agent credit balances
- Process local debits (instant)
- Batch on-chain settlements (every 10s)
- Handle MEV protection via Lit Protocol

**Flow:**

```
Agent A → Credit Debit (local, instant)
        → Signed Receipt
        → Batch Queue
        → On-chain Settlement (every 10s)
```

### 5.4 Agent SDK

**Purpose:** Developer interface for building agents

**Languages:** TypeScript, Rust, Python

**Features:**
- Transaction submission
- Routing simulation
- x402 payment handling
- State management (DBOS integration)

---

## 6. API Specifications

### 6.1 REST API

**Base URL:** `https://api.vams.network/v3`

#### Route Transaction

```http
POST /route
Content-Type: application/json

{
  "agent_id": "agent_abc123",
  "value_usd": 5000,
  "max_latency_ms": 500,
  "requires_privacy": false,
  "requires_compliance": false,
  "requires_custom_gas": false,
  "requires_isolated_throughput": false,
  "payload": "0x..."
}
```

**Response:**

```json
{
  "path": "velocity",
  "target_chain_id": 1399811149,
  "transport": "hyperlane",
  "estimated_latency_ms": 400,
  "estimated_cost_usd": 0.001,
  "routing_hash": "0x..."
}
```

#### Simulate Routing

```http
POST /route/simulate
```

Returns routing decision without execution.

#### Get Agent

```http
GET /agents/{agent_id}
```

#### Submit x402 Payment

```http
POST /x402/pay
Content-Type: application/json

{
  "agent_id": "agent_abc123",
  "provider_id": "provider_xyz789",
  "amount": "1000000",
  "nonce": 42
}
```

### 6.2 gRPC API

```protobuf
syntax = "proto3";

package vams.v3;

service CLRService {
  rpc Route(RouteRequest) returns (RoutingDecision);
  rpc SimulateRoute(RouteRequest) returns (RoutingDecision);
}

message RouteRequest {
  string agent_id = 1;
  uint64 value_usd = 2;
  uint32 max_latency_ms = 3;
  bool requires_privacy = 4;
  bool requires_compliance = 5;
  bool requires_custom_gas = 6;
  bool requires_isolated_throughput = 7;
  bytes payload = 8;
}

message RoutingDecision {
  string path = 1;
  uint64 target_chain_id = 2;
  string transport = 3;
  uint32 estimated_latency_ms = 4;
  double estimated_cost_usd = 5;
  bytes routing_hash = 6;
}
```

---

## 7. Smart Contract Interfaces

### 7.1 VAMSGateway.sol

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IVAMSGateway {
    /// @notice Relay message to target Avalanche L1
    /// @param sourceMessageId Message ID from source chain
    /// @param targetL1Id Target L1 blockchain ID
    /// @param payload Encoded transaction payload
    function relayToL1(
        bytes32 sourceMessageId,
        bytes32 targetL1Id,
        bytes calldata payload
    ) external;

    /// @notice Batch settle x402 credits
    /// @param settlements Array of settlements to process
    function batchSettleX402(
        X402Settlement[] calldata settlements
    ) external;

    /// @notice Check if address is OFAC compliant
    /// @param addr Address to check
    /// @return isClean True if not sanctioned
    function screenOFAC(address addr) external view returns (bool isClean);

    /// @notice Emergency pause (governance only)
    function pause() external;

    /// @notice Unpause (governance only)
    function unpause() external;
}

struct X402Settlement {
    bytes32 agentId;
    address provider;
    uint256 amount;
}
```

### 7.2 AgentRegistry.sol

```solidity
interface IAgentRegistry {
    /// @notice Register a new agent
    function registerAgent(
        bytes32 agentId,
        address owner,
        bytes calldata config
    ) external returns (bool);

    /// @notice Get agent details
    function getAgent(bytes32 agentId) external view returns (Agent memory);

    /// @notice Update agent configuration
    function updateAgent(
        bytes32 agentId,
        bytes calldata config
    ) external returns (bool);

    /// @notice Deactivate agent
    function deactivateAgent(bytes32 agentId) external returns (bool);
}

struct Agent {
    bytes32 id;
    address owner;
    uint256 createdAt;
    uint256 totalTransactions;
    bool isActive;
    bytes config;
}
```

---

## 8. Data Models

### 8.1 Core Schemas

```typescript
// TypeScript definitions

interface VAMSMetadata {
  agentId: string;
  valueUsd: number;
  maxLatencyMs: number;
  requiresPrivacy: boolean;
  requiresCompliance: boolean;
  requiresCustomGas: boolean;
  requiresIsolatedThroughput: boolean;
  payload: Uint8Array;
}

interface RoutingDecision {
  path: 'privacy' | 'security' | 'sovereignty' | 'velocity' | 'default';
  targetChainId: bigint;
  transport: 'hyperlane' | 'layerzero' | 'agglayer' | 'awm' | 'teleporter';
  estimatedLatencyMs: number;
  estimatedCostUsd: number;
  routingHash: Uint8Array;
}

interface Agent {
  id: string;
  owner: string;
  name: string;
  status: 'active' | 'paused' | 'terminated';
  createdAt: Date;
  config: AgentConfig;
}

interface X402Payment {
  agentId: string;
  providerId: string;
  amount: bigint;
  nonce: number;
  signature: Uint8Array;
  status: 'pending' | 'settled' | 'failed';
}
```

### 8.2 Database Schema

```sql
-- PostgreSQL schema

CREATE TABLE agents (
    id UUID PRIMARY KEY,
    owner_address VARCHAR(42) NOT NULL,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    config JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE transactions (
    id UUID PRIMARY KEY,
    agent_id UUID REFERENCES agents(id),
    routing_path VARCHAR(20) NOT NULL,
    target_chain_id BIGINT NOT NULL,
    transport VARCHAR(20) NOT NULL,
    payload BYTEA,
    tx_hash VARCHAR(66),
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    confirmed_at TIMESTAMP
);

CREATE TABLE x402_settlements (
    id UUID PRIMARY KEY,
    agent_id UUID REFERENCES agents(id),
    provider_address VARCHAR(42) NOT NULL,
    amount NUMERIC(78, 0) NOT NULL,
    nonce INTEGER NOT NULL,
    batch_id UUID,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    settled_at TIMESTAMP
);

CREATE INDEX idx_transactions_agent ON transactions(agent_id);
CREATE INDEX idx_transactions_status ON transactions(status);
CREATE INDEX idx_settlements_batch ON x402_settlements(batch_id);
```

---

## 9. Security Requirements

### 9.1 Threat Model

| Threat | Severity | Mitigation |
|--------|----------|------------|
| Gateway contract compromise | Critical | Multi-sig (3/5), timelock (48h) |
| Bridge exploit | Critical | Pessimistic proofs, daily caps |
| x402 MEV exposure | High | Lit Protocol threshold encryption |
| L1 validator collusion | Medium | Min 13 validators for >$10k |
| TEE side-channel attack | Medium | Multi-TEE redundancy |
| API DDoS | Medium | Rate limiting, Cloudflare |

### 9.2 Audit Requirements

| Component | Auditor | Deadline |
|-----------|---------|----------|
| VAMSGateway.sol | Trail of Bits | Before Phase 3 |
| X402Settlement.sol | OpenZeppelin | Before Phase 3 |
| CLR Logic | Runtime Verification | Before Phase 3 |
| Agent SDK | Internal security review | Before Phase 2 |

### 9.3 Security Practices

- All smart contracts must have 100% test coverage
- Formal verification for critical paths
- Bug bounty program via Immunefi
- Regular penetration testing
- Dependency scanning (Snyk/Dependabot)

---

## 10. Infrastructure Requirements

### 10.1 Kubernetes Cluster

```yaml
# Minimum production requirements
nodes:
  - role: api-gateway
    count: 3
    cpu: 4 cores
    memory: 8 GB
  - role: clr-service
    count: 5
    cpu: 8 cores
    memory: 16 GB
  - role: settlement-service
    count: 3
    cpu: 4 cores
    memory: 8 GB
```

### 10.2 Database

- PostgreSQL 15+ (primary)
- Redis 7+ (caching, rate limiting)
- Replication: synchronous for transactions

### 10.3 Monitoring

```yaml
prometheus:
  scrape_interval: 15s
  retention: 30d

alertmanager:
  receivers:
    - pagerduty
    - slack

grafana:
  dashboards:
    - clr-routing
    - x402-settlements
    - gateway-health
```

---

## 11. Testing Requirements

### 11.1 Test Categories

| Category | Coverage Target | Tools |
|----------|-----------------|-------|
| Unit Tests | >90% | Jest, pytest, cargo test |
| Integration Tests | >80% | Hardhat, Foundry |
| E2E Tests | Critical paths | Playwright |
| Load Tests | 10,000 TPS | k6, Locust |
| Security Tests | OWASP Top 10 | ZAP, Burp Suite |

### 11.2 Test Environments

| Environment | Purpose | Data |
|-------------|---------|------|
| Local | Developer testing | Mock |
| Dev | Integration testing | Testnet |
| Staging | Pre-production | Testnet (mirrored) |
| Production | Live | Mainnet |

---

## 12. Development Phases

### Phase 0: Foundation (Q1 2026)

- [ ] Repository setup
- [ ] CI/CD pipeline
- [ ] Core data models
- [ ] API specification (OpenAPI)
- [ ] Smart contract scaffolding

### Phase 1: Core Routing (Q1 2026)

- [ ] CLR service implementation
- [ ] Privacy router (Phala integration)
- [ ] Velocity router (Hyperlane integration)
- [ ] Basic SDK (TypeScript)

### Phase 2: Gateway & Settlement (Q2 2026)

- [ ] VAMS Gateway contract
- [ ] x402 settlement service
- [ ] OFAC screening integration
- [ ] Testnet deployment

### Phase 3: Security & Compliance (Q2 2026)

- [ ] Security audits
- [ ] Polygon ID integration
- [ ] Rate limiting
- [ ] Guarded mainnet launch

### Phase 4: Scale (Q3 2026)

- [ ] Performance optimization
- [ ] Additional SDK languages
- [ ] DAO governance
- [ ] Open mainnet

---

## 13. Contribution Guidelines

### 13.1 Getting Started

```bash
# Clone repository
git clone https://github.com/VAMS-Protocol/vams.git
cd vams

# Install dependencies
pnpm install

# Run tests
pnpm test

# Start local dev environment
pnpm dev
```

### 13.2 Code Standards

| Area | Standard |
|------|----------|
| TypeScript | ESLint + Prettier |
| Rust | rustfmt + clippy |
| Solidity | solhint + forge fmt |
| Commits | Conventional Commits |
| PRs | Squash merge |

### 13.3 PR Process

1. Fork the repository
2. Create feature branch (`feat/my-feature`)
3. Write tests
4. Submit PR with description
5. Pass CI checks
6. Get 2 approvals
7. Squash merge

### 13.4 Issue Labels

| Label | Description |
|-------|-------------|
| `good-first-issue` | Suitable for new contributors |
| `help-wanted` | Extra attention needed |
| `bug` | Something isn't working |
| `enhancement` | New feature request |
| `security` | Security-related |

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **ACP-77** | Avalanche pay-as-you-go L1 validation |
| **AWM** | Avalanche Warp Messaging |
| **CLR** | Conditional L1 Router |
| **DBOS** | Database Operating System |
| **TEE** | Trusted Execution Environment |
| **x402** | HTTP 402-based payment protocol |

---

## Appendix B: References

1. [ARCHITECTURE.md](./ARCHITECTURE.md) - Technical specification
2. [WHITEPAPER.md](./WHITEPAPER.md) - Executive summary
3. [Polygon AggLayer](https://docs.polygon.technology/agg-layer/)
4. [Avalanche ACP-77](https://github.com/avalanche-foundation/ACPs)
5. [DBOS Documentation](https://docs.dbos.dev/)

---

**Document Version:** 1.0  
**Maintainer:** Aseem Chishti  
**Contact:** aseeminksa@gmail.com
