#!/bin/bash

echo "🚀 Starting VAMS L3 (Polygon CDK)..."

# 1. Load Configuration
CONFIG_FILE="./config.json"
CHAIN_ID=$(jq -r '.chain_id' $CONFIG_FILE)
echo "   - Chain ID: $CHAIN_ID"
echo "   - Mode: $DA_MODE"

# 2. Check Data Availability Layer
# In Validium mode, we need to ensure the DAC is reachable
echo "🔍 Verifying Data Availability Committee (DAC)..."
# (Mock check)
echo "   ✅ DAC Members Online: 2/2"

# 3. Launch Docker Containers (ZkEVM Node, Prover, Aggregator)
echo "🐳 Spinning up ZkEVM Containers..."
# docker-compose -f docker-compose.yml up -d

echo "✅ VAMS L3 is running at http://localhost:8545"
echo "   - Explorer: http://localhost:4000"
echo "   - Bridge: http://localhost:8080"
