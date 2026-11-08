# Independent review - F05.2a current applied-policy identity

Verdict: PASS for the narrow current-source synthetic identity claim; no broader F05 or deployment acceptance.

The reviewer independently checked run2/RESULT.json, confirmed all 21 recorded Cardano input hashes match the current checkout and that the before/after maps are identical, verified the exact outer `bwrap --unshare-net` invocation, and confirmed the eight inner commands exited 0. Both builds report the same 3,467-byte compiled program, policy ID `9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731`, blueprint hash, current raw lock hash, and matching frozen artifact/transaction witness. Review did not rerun compilation or access credentials.

Limitations: evidence is synthetic fixture identity only. It establishes no ledger admission, Cardano Pre-Prod, live-network behavior, or deployment readiness and grants no negative-case or mutation credit. Dependency versions remain unpinned; the run used cached packages with network access disabled. F05 signature-domain and applied-parameter decisions and the F04 identity-entrypoint decision remain open.
