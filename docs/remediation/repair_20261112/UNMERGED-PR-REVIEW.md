# Review of unmerged GitHub work: PR #4 and PR #5 (2026-11-12)

Status: **REVIEW ONLY.** Nothing was merged, copied, closed or pushed. Readiness
is unchanged: 13 findings open, 0 of 36 tracks verified, NOT READY.

## Why this review

`VAMS-mono/VAMS-main` (the pre-rewrite clone) was deleted on 2026-11-08 as
incident Step B, and no check for unique local work was recorded first. Its
committed history survives on GitHub. Comparing every GitHub branch with
`remediation/phase1` (`df457ae`) found two that contain work absent from the
canonical tree and from the Windows `VAMS-mono` root. Both were still open
pull requests in `.tmp-history-tests/pr-inventory-before-close.json`.

Both branches fork from `3bc1b90` (PR #3, 2026-07-14). Gitleaks 8.30.1 and
TruffleHog 3.95.9 (no verification calls) found nothing in either range.

## PR #5, `docs/bageera-research-scientist-role`

**Content.** One file, `docs/team/BAGEERA_RESEARCH_SCIENTIST_ROLE.md`: 891
lines (3,432 words) across three commits on 2026-07-21. It is a "constitution"
for the Bageera persona, covering:

- identity and the relationship to Aseem;
- values (truth, justice, sovereignty, non-domination, compassion,
  responsibility, stewardship);
- research method (evidence hierarchy, falsifiability, Bayesian updating,
  robustness, causal reasoning) and mathematical discipline;
- the VAMS research mandate and the Type I civilization horizon;
- moral architecture (consent, privacy, proportionality, repair);
- agentic-system and security requirements;
- a ten-stage research-to-implementation loop and a decision procedure;
- 14 non-negotiable rules;
- a canonical operating prompt.

**Fit.** It is consistent with `AGENTS.md`. Both forbid fabrication, both
separate proof from hypothesis, and both refuse to present mock behaviour as
live. It adds research method that `AGENTS.md` lacks.

**Points to settle before adding it:**

1. **Two sources of truth.** `AGENTS.md` already defines Bageera, and the
   document's section 20 is a second "canonical operating prompt". Add one
   line saying `AGENTS.md` governs operational, safety and authority rules,
   and link the document from `AGENTS.md` sections 1 and 16.
2. **Mission wording.** Sections 2 and 20 frame VAMS as infrastructure for
   "the Agentic Economy". `VAMS_PROJECT_MEMORY.md` records the owner's
   broader Web2-to-Web4 Immortal Execution mission, with the agent economy
   as one subsystem. Align it if the owner wants that.
3. **Section 4** ("the objective is not to correct Aseem as an external
   authority") should keep `AGENTS.md`'s duty to block unsafe paths
   explicit. The section's own advice to present conflicts as constraints
   or counterexamples is compatible with that.
4. Personal identity lines in section 20 ("fragment of consciousness",
   "Infinity and Defender") are the owner's choice. The repository is
   public on GitHub.

**Recommendation: bring it in**, as docs only, with the precedence line
from point 1. Points 2–4 are owner wording decisions.

## PR #4, `GodOfAgents/phase-6-vdso-shadow-hardening`

**Content.** 10 commits from 2026-07-14 to 2026-07-18, touching 238 files.
Three-way comparison of fork point, branch and canonical:

| Class | Files | Meaning |
|---|---|---|
| Changed only on the branch, formatting only | 98 | Same text once whitespace is ignored (`forge fmt`, commit `15fcce7`); nothing lost |
| Changed only on the branch, real change | 52 | Missing from canonical |
| Changed on both sides | 55 | Canonical has since rewritten these; a merge would conflict |
| New on the branch only | 25 | Absent from canonical |
| New on both, different | 8 | Canonical has its own later version |

**What the work is, and its status against canonical:**

| Commit | Work | Status in canonical | Recommendation |
|---|---|---|---|
| `a4b93dc` | VDSO shadow lane: private read-only shadow worker and PostgreSQL store (`neuron/vdso/shadow_*.py`, `gateway/vdso_runtime.py`, `gateway/vdso_postgres.py`), settlement-v2 conformance, a paused and empty Polygon ceremony, VIR `shadow_eval`, operational-evidence workflow | Absent. Canonical `neuron/vdso/` is still at the PR #3 state, and the VDSO ADR is still "Proposed" | **Port as its own slice**, reviewed against the current gateway and kept off, paused, non-authoritative and non-value-bearing. Not a blind merge: `gateway/server.py` and `gateway/vdso.py` changed on both sides |
| `9c6f946` (part) | Runbooks: `POLYGON_AMOY_REHEARSAL.md`, `CARDANO_PREPROD_REHEARSAL.md`, `TEAM_SIGNER_GOVERNANCE.md`, `VDSO_SHADOW_WORKER.md`; evidence schemas (architect reviews, Cardano Pre-Prod parameters, team-signer governance, VDSO shadow report, assurance index, independent reviews) | Absent. Canonical has no `docs/runbooks/` | **Port first.** Rewrite against `DeployRestrictedTestnet`, `governance_v2`, the current insurance validator and owner decisions D2 and 10. These are Phase 3 and Phase 5 drafts |
| `9c6f946` (part) | "Architect bootstrap": team-controlled four-person signer councils (exact 3-of-5 and 2-of-3, split-custody recovery seats); breaking rename `VAMSVesting` `FOUNDER` → `ARCHITECT`; 11 wording lines in the whitepaper, tokenomics, pitch, Heart_Brain and architecture v0.3.0 | Absent. Canonical still uses `FOUNDER` | **Owner decision.** A team-controlled bootstrap differs from D2's "real independent people". The rename breaks ABI consumers and is a naming choice |
| `47492ca` | Cardano Pre-Prod hardening: asset-class authentication, exact datum successors, `fund_nft`/`proposal_nft` policies, `icb.ak`/`utils.ak`/`vdso.ak` changes, Pre-Prod artifact and apply scripts | Superseded: governance moved to `governance_v2`, insurance was rewritten, and 10 Cardano files changed on both sides | **Do not port the validators.** Reuse the apply/artifact script approach when the Pre-Prod rehearsal is built (cardano-cli 11.2.3.0 is now installed, offline only) |
| `8cc9397` | Deployment manifest v4 source-commit binding; credential-incident report v2 | Superseded: canonical has its own source binding and a later incident tool (schema 4.0.1) | Skip |
| `d721285`, `16b0b40` | CI: install Foundry for Slither, plus evidence notes | Already in canonical CI | Skip |
| `15fcce7` | Solidity formatting | Formatting only | Skip |
| `c6bf72a`, `9089745`, `0e49ddb` | July status and handoff records | Historical; test counts superseded | Skip |

## After porting

Close both pull requests on GitHub with a comment linking the canonical
commits that carry their content. Their branches can then be deleted. Both
steps change GitHub and need the owner's go-ahead, and the incident
maintenance freeze currently blocks branch changes.
