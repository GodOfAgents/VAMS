# Sentinel Network (`neuron/sentinel/`)

This package implements Phase 2 (Performance Enforcement) of the ICN-inspired roadmap.

## Overview
The Sentinel Network performs randomized challenge-response benchmarks physically testing DePIN hardware nodes (GPU performance, IOPS, Memory bandwidth, Latency) rather than relying on self-reported SLAs. Results dictate automated on-chain slashing. 

## Components
- `sentinel_node.py`: The core `VAMSSentinelNode` runner. Dispatches challenges, processes results, and interacts with the DA layer and blockchain.
- `challenges/`: Base abstract interface + implemented benchmarks:
  - `gpu_challenge.py`: Tests FLOPS or deep learning ops.
  - `cpu_challenge.py`: High-stress deterministic CPU test.
  - `memory_challenge.py`: Standard read/write bandwidth checks.
  - `storage_challenge.py`: Evaluates IOPS against pre-claimed hardware class rates.
  - `latency_challenge.py`: Evaluates global networking.

## Flow
1. Node is challenged by a randomized Sentinel.
2. The specific benchmark runs.
3. The result is passed to `performance_audit.py` (DA layer) for immutability.
4. The `SLAEnforcer` contract is called to update trust scores or slash performance bonds if standard is missed.
