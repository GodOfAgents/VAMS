---
name: vams-six-hats
description: Run a structured Six Thinking Hats review for VAMS architecture, research, protocol design, deployment decisions, roadmap tradeoffs, security posture, or product strategy. Use when the user asks for six hats, Blue Hat, Black Hat, Red Hat, Yellow Hat, Green Hat, White Hat, decision framing, or multi-perspective VAMS analysis.
---

# VAMS Six Hats

Use this skill to structure decisions without losing technical rigor.

## Workflow

1. Define the decision, scope, and stage.
2. Read relevant code/docs if the decision depends on implementation reality.
3. Use the hats in this order:
   - Blue: frame the decision and success criteria.
   - White: list verified facts and missing data.
   - Black: identify failure modes, blockers, and invariant risks.
   - Yellow: identify benefits and strategic upside.
   - Green: propose alternatives and redesigns.
   - Red: capture intuition, stakeholder concern, and narrative risk.
   - Blue: conclude with decision, next action, and owner.
4. If safety-critical, let Black Hat findings override optimism.

## Output Shape

Use short sections for each hat, then a final **Decision** section.

If facts are missing, say exactly what must be inspected or tested before a
decision can be made.

Read `references/hats.md` for VAMS-specific prompts.
