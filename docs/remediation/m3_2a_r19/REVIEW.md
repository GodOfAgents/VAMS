# M3.2a-R19 FIFO and independent-oracle remediation

Date: 2026-09-27
Branch: testnet/remediation-20260907
HEAD: 829ab544571f12efe50ecb5740f129c8acb3e16f
Origin: https://github.com/GodOfAgents/VAMS.git

## Scope and prerequisite

R18 was strictly verified before editing. Evidence package /home/GodOfAgents/vams-evidence/m3-2a-r18-review-20260927-829ab544571f has SHA256SUMS digest eb4b4b6f67c76283be986327aa6a6df223f1da8cc90190012164d5402f903366 and every listed file passed. The pre-fix isolated FIFO reproduction hit the hard three-second timeout, exit 124. No network, installation, fetch, deployment or Git history operation was used.

## Remediation

address_value_oracle.py now opens the final fixed registry component with O_RDONLY|O_NONBLOCK|O_NOFOLLOW|O_CLOEXEC. The descriptor is fstat'ed before any read; non-regular objects and oversized files are rejected; reads remain descriptor-bound and bounded; all descriptors close on success and failure. No normative R7 JSON, frozen hash, Cardano source, manifest, dependency, vendor or deployment file changed.

test_r19_oracle.py is the independent public-boundary suite. It derives enterprise address bytes directly from the documented header formula and uses frozen raw datum vectors without production address, registry, CBOR or expected-successor helpers. It covers FIFO with no writer and with a writer, descriptor cleanup, directory/socket/final-symlink/ancestor-symlink rejection, and address/integer-encoding mutation checks.

test_r19_mutations.py is a separate implementation-mutation harness for candidate-versus-canonical comparison. It proves the unchanged implementation rejects a perturbed encoder and that a disposable removal of the comparison is detected. It is not used as the independent value oracle.

## Fresh verification

- R19 focused tests: 9/9, exit 0.
- R17 focused tests: 6/6, exit 0.
- Complete oracle suite: 10/10, exit 0.
- Complete governance suite: 12/12, exit 0.
- Complete provenance suite: 20/20, exit 0.
- Two isolated offline Aiken 1.1.21 verifier runs: both ok=true, check_exit=0, build_exit=0; source manifest d255e13f04d2e27b595430cc2decf532c38e0444c01488dbfb7f312edc3afa55 and blueprint 7b39b883cdc7b55aef08554e92cb089a4b3a91a6250138c4f0b181b37cfd0a80 matched.
- Python compilation, JSON/documentation validation and git diff --check: exit 0.
- Recursive submodules and frozen continuity hashes: unchanged.
- Final dirty-path count: 114.

Post-fix hashes: address_value_oracle.py 50211e76db54ceafd303f63d83c8aabfc914e0b98d2aef56cb5558e1a88bb95b; test_r19_oracle.py 1084a1c7396fcffdf81a12f0ac0fd00a642f7d599c9c8427cc1192bf250710dd; test_r19_mutations.py 2122d49bbbc2f176d8b2e56721119b0916bae4987c0f18f478d7616b9dfee8a6.

## Status

R19 is local remediation evidence only; independent M3.2a-R20 FIFO/oracle micro-review is required. F01-F05 remain REVALIDATED_OPEN, Deposit remains disabled pending F05, M3 remains OPEN, Pre-Prod admission remains INCONCLUSIVE, promotion remains NOT READY, and M3.2b is not authorized. INV-1 through INV-10 and mock-mode behavior are unchanged.
