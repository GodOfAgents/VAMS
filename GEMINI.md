# VAMS AI Agent Instructions & Guidelines

Welcome to the Verifiable and Agentic Modular Stack (VAMS) repository. As an AI Agent operating within this repository, you must adhere strictly to the following engineering realities and operational rules.

## Core Operational Rules

1. **Verify Implementation Reality vs. Documentation:** 
   - **Do not blindly trust documentation.** The documentation in this repository often represents a forward-looking vision or roadmap. 
   - Before executing a task, always cross-reference the documentation with the actual code. For example, `API_REFERENCE.md` may advertise routes that are not yet implemented in `gateway/server.py`. 
   - **Do not execute incomplete or inconsistent tasks.** If you are asked to integrate a component, verify that its dependencies are not just stubs (e.g., `TrailsClient`, `EigenDA Adapter`, `Avail Adapter` currently throw `NotImplementedError` or return mock behaviors).

2. **Project Status Context:**
   - **This project is a "Pre-Testnet Candidate" in a hardening phase.** Do NOT publicly endorse it as "production-grade" or "ready for broader developer adoption" without explicit live deployment evidence.
   - Any claims of "ready for testnet" must be treated as "deployment prep" rather than a verified live state until actual testnet addresses and tx hashes are provided.

3. **Security and Hardening:**
   - Operational security hardening is ongoing. Be vigilant for mock defaults, testnet simplifications (e.g., Cardano ICB structural verification), and default fallback passwords (e.g., `"vams2026"` in the gateway).
   - Flag any security cleanup needs before declaring a feature complete.

4. **Testing and Build Integrity:**
   - The test suite is substantial but environment-sensitive. When running Python tests, pay attention to skipped tests and warnings.
   - Frontend builds may be fragile (e.g., missing entry files like `/src/main.tsx`). Verify the build process locally before making UI architecture decisions.

---

## Agent Skills Directory

Use the following specialized VAMS skills (via slash commands like `/vams-dev-contracts`) whenever you need to perform domain-specific tasks. They contain highly tailored instructions for this repository.

### Development Skills
- `/vams-dev-lead`: Tech Lead & Orchestrator. Use this to break down features, assign tasks to other agents, and make architectural decisions.
- `/vams-dev-contracts`: Senior Solidity Engineer. Use this to write smart contracts, implement interfaces, and optimize gas.
- `/vams-dev-backend`: Backend API & Data Engineer. Use this for indexers (The Graph/Ponder), databases, and traditional APIs.
- `/vams-dev-frontend`: Frontend & Web3 UX Engineer. Use this to build the React/Next.js dashboard, wallet connections, and data visualization.
- `/vams-dev-agents`: AI & Off-Chain Logic Engineer. Use this to build the Python/Node.js agent behaviors, keeper bots, and signing logic.
- `/vams-dev-devops`: DevOps & SRE. Use this for CI/CD pipelines, Docker, deployment scripts, and node infrastructure.
- `/vams-dev-qa`: QA & Test Engineer. Use this to write unit tests, integration tests, and simulation scenarios.
- `/vams-dev-security`: Security Engineer (Builder). Use this to write security hooks, implement circuit breakers, and run static analysis.

### Architecture, Auditing & Validation
- `/vams-architecture-verification`: Validates architecture correctness, decentralization, and scalability. Use this for analyzing trust assumptions, L1/L2 interactions, and single points of failure.
- `/vams-audit`: Tier-1 Security Auditor (CertiK / Trail of Bits standard). Use this to perform comprehensive smart contract auditing, formal verification, economic exploit analysis, and cryptographic architecture review (ZKP/FHE).
- `/vams-security-audit`: Performs pre-audit security hardening. Use this to identify attack surfaces, smart contract vulnerabilities, and agent manipulation vectors.
- `/vams-devops-readiness`: Validates operational reality. Use this to check upgrade strategies, monitoring, incident response, and node operations.
- `/vams-compliance-legal`: Reduces regulatory risk. Use this to scan for token classification issues, jurisdictional exposure, and data privacy.

### Economics & Tokenomics
- `/vams-tokenomics-validation`: Stress-tests economic sustainability. Use this to analyze token utility, inflation/deflation mechanics, and incentive alignment.
- `/vams-agent-game-theory`: Ensures rational agent behavior. Use this to analyze Nash equilibria, collusion incentives, and slashing mechanisms.

### Strategy & Research
- `/vams-blue-hat-orchestrator`: Controls sequencing and final decisions. Use this to resolve conflicts between agents and produce the final Go/No-Go decision.
- `/vams-market-narrative`: Aligns architecture with market promise. Use this to check product-market fit, competitor comparison, and narrative gaps.
- `/vams-internet-researcher`: Deep internet research & competitive intelligence agent. Use this to gather real-time market data, analyze competitor protocols, track ecosystem developments, source academic papers, and compile actionable intelligence reports.
- `/vams-documentation-transparency`: Ensures auditability and clarity. Use this to check spec completeness, missing assumptions, and onboarding friction.

*Always invoke these skills when shifting contexts to ensure high-quality, specialized outputs.*
