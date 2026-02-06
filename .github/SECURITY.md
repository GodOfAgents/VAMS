# Security Policy

## Reporting a Vulnerability

The VAMS Protocol team takes security vulnerabilities seriously. We appreciate your efforts to responsibly disclose your findings.

### Contact Information

**Email**: security@vams.io  
**PGP Key**: Available upon request

### Response Timeline

- **Initial Response**: Within 48 hours
- **Triage & Assessment**: Within 5 business days
- **Resolution Timeline**: Depends on severity (see below)

| Severity | Resolution Target |
|----------|------------------|
| Critical | 24-48 hours |
| High | 7 days |
| Medium | 14 days |
| Low | 30 days |

## Bug Bounty Program

We offer rewards for qualifying vulnerabilities discovered in our smart contracts and infrastructure:

| Severity | Reward Range |
|----------|-------------|
| Critical | $10,000 - $50,000 |
| High | $5,000 - $10,000 |
| Medium | $1,000 - $5,000 |
| Low | $100 - $1,000 |

### Scope

**In Scope:**
- Smart contracts in `/contracts/src/`
- Upgrade mechanisms and proxy patterns
- Access control and role management
- Token economics and fee distribution
- Agent registry and slashing mechanisms
- Payment channel and settlement logic

**Out of Scope:**
- Frontend applications
- Third-party dependencies (report to respective maintainers)
- Issues already reported or known
- Theoretical vulnerabilities without proof of concept
- Social engineering attacks

### Qualifying Criteria

1. First reporter of the vulnerability
2. Provides clear reproduction steps
3. Does not exploit the vulnerability on mainnet
4. Does not publicly disclose before resolution
5. Vulnerability must affect deployed contracts

## Responsible Disclosure Guidelines

1. **Do Not**:
   - Access or modify user data beyond what's necessary to demonstrate the vulnerability
   - Perform any attacks that could harm the availability of our services
   - Use social engineering tactics against our team or users
   - Publicly disclose the vulnerability before we've had a chance to address it

2. **Do**:
   - Provide detailed reports with reproduction steps
   - Give us reasonable time to investigate and fix the issue
   - Encrypt sensitive communications using our PGP key
   - Include your wallet address for bounty payments

## Security Measures

### Smart Contract Security

- **Audits**: All production contracts undergo professional security audits
- **Upgradability**: UUPS pattern with timelock governance
- **Access Control**: Role-based access with multi-sig requirements
- **Storage Gaps**: 50-slot gaps reserved for future upgrades
- **Reentrancy Guards**: All state-changing functions protected

### Operational Security

- **Multi-Signature**: Critical operations require 2/3 or 3/5 multi-sig
- **Timelock**: Governance actions have mandatory delay periods
- **Monitoring**: 24/7 on-chain monitoring and alerting
- **Incident Response**: Documented procedures for security events

## Previous Audits

| Auditor | Date | Report |
|---------|------|--------|
| Pending | Q2 2026 | Pre-mainnet audit scheduled |

## Acknowledgments

We thank the following security researchers for their responsible disclosures:

*No disclosures reported yet*

---

**Note**: This policy is subject to change. Please check back regularly for updates.
