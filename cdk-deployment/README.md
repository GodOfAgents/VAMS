# VAMS L3 CDK Deployment

**Lifecycle:** Local prototype scaffold
**Last verified:** 2026-07-12

## Prerequisites
- Docker & Docker Compose
- jq (for script parsing)
- Minimum Specs: 8 vCPU, 16GB RAM (for full ZkEVM node)

The checked-in `deploy.sh` performs mock checks and does not launch a Polygon
CDK network. Do not use it as a testnet or production deployment procedure.

## Prototype Walkthrough
1. Configure your chain in `config.json`.
2. Run the deployment script:
   ```bash
   ./deploy.sh
   ```
3. Inspect the generated command output. It is not evidence that a chain is running.

## Production Deployment
No production deployment procedure is documented or authorized. A future CDK
runbook must include real infrastructure configuration, DA committee evidence,
key management, monitoring, rollback, and an independently reviewed deployment
manifest. See `docs/L3_CHAIN_AND_DA.md` for the current boundary.
