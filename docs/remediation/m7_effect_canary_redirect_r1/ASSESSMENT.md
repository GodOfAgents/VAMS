# M7 local effect-provider redirect containment

Bandit 1.9.4 identified B310 in the local HTTP effect provider and its loopback integration tests. The provider validated its configured base URL as plain HTTP on 127.0.0.1, but urllib's default redirect handling could forward a signed request and payload to a redirect target. The client now uses a dedicated opener whose redirect handler rejects redirects. The regression server points its redirect at a dead loopback port and verifies the client reports the original 302; no transaction or non-loopback request is made.

The integration tests now use a small HTTPConnection helper that rejects any test URL outside 127.0.0.1, removing scanner findings on the tests' direct urllib calls.

Verification: neuron/tests/test_effect_canary.py passed 12/12 under Python 3.12.14 and pytest 9.1.1. The repository Bandit command passed with zero findings across the current neuron/ and gateway/ Python sources. The source inventory was unchanged during the run. The already-installed Bandit 1.9.4 binary and workflow configuration were hash-bound; network was disabled.

Changed files are neuron/effect_canary.py, neuron/tests/test_effect_canary.py, and docs/CHANGELOG.md. The two Python files are untracked dirty work in the current checkout; they were not staged or committed. INV-1 through INV-10 are not touched. No mock-mode policy, key material, provider identity, ledger evidence, live-network evidence, or deployment capability changed. This is local synthetic qualification code only and does not establish testnet readiness.

Independent review: PASS. The reviewer inspected the exact integrated source and tests, independently reproduced 12/12 focused tests and zero Bandit findings across 190 Python sources, and verified source/evidence hashes. The earlier m7_bandit_current_r2 result is pre-fix evidence and retains three findings; it is not the current result.
