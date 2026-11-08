# M7 local Bandit gate

## Result

The workflow-configured Bandit scan passed locally against the current checkout's `neuron/` and `gateway/` trees. Pinned Bandit 1.9.4 ran with the workflow thresholds `-ll -ii`; the JSON-format option only enabled safe result capture. The scanner exited 0 with zero findings. No report snippets or source lines were retained.

## Verification

The exact outer command, scanner command, tool/runtime pins, workflow hash, output hash, and sanitized counts are in [RUN.json](RUN.json). [RESULT.json](RESULT.json) contains only filenames, finding identifiers, severity/confidence, and line numbers; its finding list is empty. The scanner's raw output was captured in process memory, hashed, and discarded.

An initial wrapper attempt failed to parse the scanner output and produced no evidence. The corrected wrapper was then run again with network access disabled and produced the recorded exit-0 result.

## Scope and limits

This verifies only Bandit's local `neuron/` and `gateway/` scan on the captured dirty checkout. It does not prove CI execution, dependency audit, other security tools, whole-repository security, invariant coverage, live-network behavior, or readiness. The Gitleaks current-tree gate remains failed; M7 and all other mandatory readiness gates remain open. No application source, credentials, vendors, dependencies, or Git history changed.
