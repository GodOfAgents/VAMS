# VAMS L3 CDK Deployment

## Prerequisites
- Docker & Docker Compose
- jq (for script parsing)
- Minimum Specs: 8 vCPU, 16GB RAM (for full ZkEVM node)

## Quick Start (Devnet)
1. Configure your chain in `config.json`.
2. Run the deployment script:
   ```bash
   ./deploy.sh
   ```
3. The chain will be available at `http://localhost:8545`.

## Production Deployment
For production, we recommend using a cloud provider (AWS/GCP) with managed Kubernetes.
See `docs/L3_CHAIN_AND_DA.md` for architecture details.
