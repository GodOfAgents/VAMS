---
name: vams-red-team
description: Perform adversarial VAMS security review for protocol designs, diffs, PRs, deployments, gateway routes, smart contracts, DA adapters, bridges, session keys, TEE trust, OMS identity, token economics, and cognitive-layer memory/search systems. Use when the user asks for red team, attack analysis, abuse cases, exploit paths, or pre-audit critique.
---

# VAMS Red Team

Use this skill to think like a capable adversary while staying within defensive
review boundaries. Do not provide exploit code for live systems.

## Workflow

1. Define assets, trust boundaries, attacker roles, and deployment stage.
2. Read relevant code and docs; do not rely on architecture claims.
3. Use `references/threat-model.md` to enumerate attack classes.
4. Identify practical exploit paths and required preconditions.
5. Rank findings by exploitability, blast radius, and invariant impact.
6. Provide concrete mitigations and tests.
7. Block deployment if a high-impact path is unmitigated.

## Output Shape

- **Attack Surface:** components and trust boundaries.
- **Findings:** severity, path, preconditions, impact, evidence.
- **Invariant Impact:** affected INV IDs.
- **Mitigations:** specific code/config/test changes.
- **Residual Risk:** what remains after fixes.

Keep the review technical and grounded. Avoid generic security checklists unless
they map to an actual VAMS path.
