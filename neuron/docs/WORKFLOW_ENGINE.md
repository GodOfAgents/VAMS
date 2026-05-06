# VAMS Neuron Workflow Engine (DBOS)

The VAMS Neuron implements durable, crash-proof execution using the [DBOS Python SDK](https://dbos.dev/).

## Overview

In decentralized AI networks, node crashes, RPC timeouts, and transient failures are common. Traditional Python execution loses state in memory when a crash occurs. VAMS solves this by storing execution state in PostgreSQL using DBOS.

- **Exactly-once execution:** Steps never run twice, even if the node restarts.
- **Crash recovery:** If the process dies mid-workflow, it resumes exactly where it left off.
- **Idempotency:** Workflows are assigned unique IDs, preventing duplicate runs.

## Architecture

```
[Agent Intent] -> VAMS Neuron -> DBOS Workflow -> DBOS Steps -> External Services
                                      │
                                      ▼
                               [PostgreSQL] (State Checkpoints)
```

## Setup

VAMS requires a PostgreSQL database to manage workflow state. Two strategies are supported:

### 1. Local Docker (Development)

The easiest way to get started is by running a local PostgreSQL container.

```bash
cd neuron
cp .env.example .env
./scripts/setup_dbos.sh
```

### 2. Neon Serverless (Production)

For persistent, scalable production deployments, we recommend [Neon](https://neon.tech/).

1. Create a Neon project.
2. Get the connection string.
3. Add it to your `.env` file:
   `DBOS_DB_URL="postgresql://user:password@ep-name.region.aws.neon.tech/neondb?sslmode=require"`

### `dbos_config.py` Singleton

The VAMS Neuron initializes DBOS exactly once via `neuron/dbos_config.py`. This ensures that all workflows use the same database connection pool and schema.

## Step Reference

All durable functions in VAMS are decorated with `@DBOS.step()`.

| Step Function | Purpose | Upgrading from Mock to Real |
|---------------|---------|-----------------------------|
| `step_gather_data` | Collects necessary input context for the task. | Replace `asyncio.sleep()` with real DA/Oracle queries. |
| `step_run_inference` | Prompts the AI model (or compute provider). | Integrate with IO.net or Bittensor SDKs. |
| `step_execute_action` | Dispatches transactions or API calls. | Use `mev_protection.py` to route signed txs. |
| `step_report_result` | Saves the final outcome or anchors it to L1. | Use `anchoring.py` to commit state to Polygon/Celestia. |

## Running & Monitoring

To run a workflow, set the workflow ID and call the function:

```python
from dbos import DBOS
from workflows import vams_data_pipeline

# Set a deterministic workflow ID for idempotency
DBOS.set_workflow_id("unique_run_123")
result = vams_data_pipeline("unique_run_123")
```

Or run the interactive demo:
```bash
python neuron.py --demo-workflow
```

## Testing

The testing suite uses `DBOSTestClient` to simulate execution without requiring a persistent database connection during unit tests.

To run the workflow tests:
```bash
pytest tests/test_workflows.py -v
```

## Crash Recovery Demo

To see crash recovery in action:
1. Run `python neuron.py --demo-workflow`.
2. When you see `-- Simulated crash! --`, the process will artificially exit (simulating a panic/OOM).
3. The demo automatically restarts itself.
4. Notice how steps 1 and 2 are skipped (because they are marked `[DONE]`), and execution resumes cleanly from step 3.
