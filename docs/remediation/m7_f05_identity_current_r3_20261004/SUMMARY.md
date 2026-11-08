# F05.2a current-source applied-policy identity probe

Date: 2026-10-04

Identity-only synthetic fixture proof: PASS. Two disposable builds each matched the frozen applied artifact and transaction witness. Both produced policy ID `9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731`, compiled code SHA-256 `fc8726cff89172d4944e257a2eb2659d35363c8e5a4d423ed8a2112eb5af7e59`, and blueprint SHA-256 `c4230410d0caac45f2c71d36e45a539c78087697128ce1533306d17e96a48008`.

All 21 protected inputs matched the current checkout before and after the probe and both disposable copies; mismatches: 0. All 8 child commands succeeded. No simulator, test suite, negative cases, or mutations ran.

External verifier result SHA-256: `36959e745b1ba3088fffea40cb603e1922aabdb9f891602c699c9c4fe8e68634`. Raw result contents, applied parameters, CBOR, command output, and public keys were not imported. The recorded outer bwrap exit 0 is verifier-reported and not separately embedded in the external RESULT.

Tool identities: Aiken 1.1.21 SHA-256 `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`; Python 3.12.14 SHA-256 `aa01d96348989f33ed998b42c83e98593b41dba83914d9899730b90c36f2e5c9`; bwrap 0.11.1 SHA-256 `0abea81db798ebf6b4742ac0664802d97521547a353c2a0dbdc21d76cbbfd2c0`; probe SHA-256 `168e42f9b26ff549690bbba8c8b8ddd28a3d4effe6db650f3360ed0fe87d4bdb`.

Network was disabled; checkout read-only; external evidence directory separately writable.

```text
bwrap --unshare-net --ro-bind / / --tmpfs /tmp --dev-bind /dev /dev --proc /proc --bind /home/GodOfAgents/vams-evidence/m3-f05-2a-identity-current-r1-20261004 /home/GodOfAgents/vams-evidence/m3-f05-2a-identity-current-r1-20261004 --chdir /home/GodOfAgents/code/VAMS-testnet --clearenv --setenv HOME /tmp --setenv TMPDIR /tmp --setenv PATH /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin:/usr/bin:/bin --setenv LANG C.UTF-8 --setenv LC_ALL C.UTF-8 --setenv TZ UTC --setenv PYTHONDONTWRITEBYTECODE 1 --setenv PYTHONNOUSERSITE 1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python -B /home/GodOfAgents/vams-evidence/m3-f05-2a-identity-gate-20261002-r1/identity_probe.py --evidence /home/GodOfAgents/vams-evidence/m3-f05-2a-identity-current-r1-20261004/run
```

This closes only the original applied-policy identity gate for the synthetic fixture. It adds no negative-case or mutation credit, ledger admission, Cardano Pre-Prod rehearsal, or live-network evidence. F05 remains 45/55 negative cases and 18/21 mutations. The October 3 identity snapshot in `docs/remediation/m7_f05_identity_current_r2/` is superseded for this narrow current-source claim. Testnet readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
