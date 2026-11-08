# M3.1b-R9 deterministic Aiken dependency provenance

Date: 2026-09-26

This policy is forward-looking current-state assurance only. The exact accepted
R4 cardano/aiken.lock bytes are permanently unavailable. No historical
equivalence to R4 is claimed, and no lock bytes were reconstructed.

Aiken v1.1.21 was observed in two identical offline-equivalent isolated runs
to rewrite only the lock etag retrieval timestamp fields:
- etags.*[0].secs_since_epoch
- etags.*[0].nanos_since_epoch

The etag integrity digests, dependency identities, versions, sources,
requirements, resolved package content, and compiled programs remained equal.
Raw lockfile differences remain visible and are never silently discarded.

Future assurance uses:
1. the exact current source snapshot;
2. the closed versioned cardano/aiken-dependency-manifest.json;
3. the pinned compiler version and binary hash;
4. resolved package content digests using the documented null-delimited tree
   digest;
5. semantic lock projection that excludes only the two proven timestamp fields;
6. generated blueprint and every compiled-program hash; and
7. a repository source-integrity check before and after isolated verification.

The repository-native runner
scripts/remediation/verify_m3_1b_r9.py never runs Aiken in the checkout. It
rejects unknown manifest/lock fields, duplicate dependencies, malformed hashes,
unsupported sources, unsafe copied files, package-content drift, semantic lock
drift, compiler drift, blueprint/program drift, and source mutation.

This does not close F01, F02-F05, or M3. Deposit remains disabled pending F05.
No Pre-Prod admission, funding, deployment, or promotion claim is made.
