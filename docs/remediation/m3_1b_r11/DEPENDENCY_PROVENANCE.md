# M3.1b-R11 dependency provenance contract

R11 closes the four findings from the independent M3.1b-R10 review without
changing the Cardano validator, shared types, lockfile, generated blueprint,
or dependency contents. The manifest at
cardano/aiken-dependency-manifest.json is now a versioned, closed contract
for the exact lib/ and alidators/ Aiken source set, project inputs,
packages.toml canonical package index, package-cache topology and files,
pinned compiler, blueprint, and every compiled program identity.

scripts/remediation/verify_m3_1b_r9.py validates all paths and file types
without following links, rejects traversal and unsafe dependency identifiers,
copies only digest-bound inputs into a disposable workspace, sets
AIKEN_NO_NETWORK=1, and runs only the checksum-verified Aiken 1.1.21
check/uild. It verifies the source and package snapshots before and after
the isolated build and permits only the two observed lockfile etag timestamps
to vary.

The exact mutation-sensitive tests are in
scripts/remediation/test_m3_1b_r9_provenance.py. R11 is local remediation,
not independent acceptance. F01 remains REVALIDATED_OPEN, Deposit remains
disabled pending F05, M3 remains open, Pre-Prod admission is INCONCLUSIVE, and
promotion is NOT READY.
