# Service Blocks Marketplace (`neuron/services/`)

This package represents the other half of Phase 3 (Intelligence).

## Overview
It implements a decentralized service layer where third-party builders can publish "Macro Blocks" (composable infra packages + setups), enabling them to earn revenue share alongside base compute providers when their blocks are utilized by agents.

## Components
- `registry_client.py`: The `ServiceBlockClient`. Provides Python SDK bindings to interact with the on-chain `ServiceBlockRegistry`.
- `macro_blocks.py`: Pre-defined composite blocks like `AI_AGENT_STARTER_PACK` (NodeJS + Ollama) and `PRIVACY_SHIELD_ENTERPRISE` (SGX + Proxy).

## Relevant Contracts
- `contracts/src/infrastructure/ServiceBlockRegistry.sol`: Contains logic for verifying builder signatures, tracking deployment metrics, and managing the builder-to-provider revenue split limits.
