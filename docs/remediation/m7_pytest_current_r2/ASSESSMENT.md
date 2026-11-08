# Current root Python suite revalidation

The current dirty checkout collected 1,605 tests. In the source-stable full run, 1,604 tests and 441 subtests passed; one test failed. This does not pass the Python gate.

The remaining test is scripts/remediation/test_m3_1b_r9_provenance.py::R11BoundaryTests::test_authoritative_mutation_detected. The test's verifier copies the current Cardano sources and package cache into a temporary directory, disables network access, and runs the pinned Aiken compiler. Aiken exits before the injected source mutation can be detected because aiken-lang/stdlib and aiken-lang/fuzz are identified by floating v2 tags; the isolated resolver reports an uncertain local version while network is disabled. This matches the known M7 G1 unpinned-dependency warning. The failure is not credited as an implementation pass.

The other ten failures in the first attempt were caused by the checkout being mounted read-only even though repository tests intentionally create scratch files, and by omission of the preinstalled Aiken directory from PATH. The corrected full run used a disposable writable overlay, no network, pinned Python 3.12.14/pytest 9.1.1, and pinned Aiken 1.1.21. No canonical source files changed during that run.

A direct Aiken check outside the disposable overlay rewrote only cardano/aiken.lock volatile timestamps. The file was restored byte-for-byte from two local evidence snapshots matching the provenance manifest's original raw SHA-256 acffff4aee9569e1ee1de468839077af467b5e403fd96450290cd367b339c651. It remains dirty relative to Git as before that check; no other user changes were reverted.

Remediation requires an owner decision on changing dependency identity: the current offline verifier cannot prove reproducibility from floating tags alone. No dependency, vendor, lock, or verifier change is made by this slice. This evidence is local test execution only; it does not imply ledger admission, live-network evidence, or deployment readiness.
