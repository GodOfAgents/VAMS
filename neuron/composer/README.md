# Resource Composition Engine (`neuron/composer/`)

This package implements Phase 3 (Intelligence) of the ICN-inspired roadmap.

## Overview
Instead of agents manually selecting single DePIN providers, the Composer lets an agent request a logical "blueprint" (e.g. `AI_INFERENCE_STANDARD`), then intelligently queries, scores, and provisions multiple candidate nodes that can satisfy the hardware, latency, and compliance requirements.

## Components
- `composer.py`: The `VAMSResourceComposer`. Handlers provider queries and returns an optimal `InstancePlan`.
- `models.py`: Dataclasses modeling the hardware (`ComputeSpec`, `GPUType`, `NetworkSpec`) and overall `InstanceBlueprint`.
- `blueprints.py`: Pre-defined templates for common workloads (AI Inference, Training, Privacy Shield).

## Workflow
1. Agent selects a blueprint (`AI_INFERENCE_STANDARD`).
2. `composer.compose_instance()` analyzes the specs.
3. Candidate nodes are fetched via mock/real DePIN APIs.
4. Candidates are scored based on uptime, latency, DEC boosts, and price.
5. The best candidate is selected for the `InstancePlan`.
