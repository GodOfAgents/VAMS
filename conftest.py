"""Repository-wide pytest collection boundaries.

The listed modules are preserved historical M0.3 evidence-package validators.
Their source-snapshot contracts were superseded by the compact M0.4 current-tree
gate and must not be treated as product/CI tests.  Keep this list exact: no
directory or glob exclusion is permitted here.
"""

collect_ignore = [
    "scripts/security/test_m0_3a_adjudicator.py",
    "docs/remediation/m0_3b_r1/tools/test_m0_3b_adjudicator.py",
    "docs/remediation/m0_3c_r1/tools/test_m0_3c_adjudicator.py",
    "docs/remediation/m0_3c_r1/tools/test_m0_3c_r7.py",
    "docs/remediation/m0_3c_r1/tools/test_m0_3c_r9.py",
    "docs/remediation/m0_3c_r1/tools/test_m0_3c_semantic_oracle.py",
    "docs/remediation/m0_3c_r1/tools/test_m0_3c_validator.py",
]
