#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

python3 "$REPO_ROOT/scripts/security/runtime_mode_preflight.py" \
  --require-live \
  --expected-mode testnet

echo "Deployment blocked: cdk-deployment/deploy.sh is an incomplete scaffold and cannot produce live evidence." >&2
exit 1
