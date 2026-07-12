# VAMS Architecture Traceability Report

**Current architecture:** v0.8.0 cognitive/composer over the v0.6.0 OMS security baseline  
**Promotion status:** Evidence structure implemented; deployment remains blocked

The version discrepancy is resolved by treating v0.6.0 as the historically
audited OMS baseline and v0.7.0/v0.8.0 as additive architecture layers. The
machine-readable trace starts at v0.3.0 and requires every addendum through
v0.8.0 plus the current Composer, S-MMU, ProPlay, Gateway, and frontend anchors.

`scripts/audit/validate_traceability.py` fails if the architecture ceiling
diverges from `control-matrix.json`, an addendum disappears, a current component
is absent, or an invariant loses an enforcement/test anchor.

This report proves source traceability only. It does not prove deployed bytecode,
live integrations, economic safety, or independent review.
