# INV-5 OMS route focused verification

The focused offline Python suites passed **88/88** under Python 3.12.14 and pytest 9.1.1 with `VAMS_ENV=test`. The run covered current CLR routing, OMS identity handling, and adjacent hybrid/integration tests. The bounded addition in this slice connects provider non-verification to the P3 route: an explicit `is_verified: false` response, HTTP 503, malformed payload, and timeout each raise `PermissionError` at `CLRouter.route`; each case makes one provider transport call.

Current implementation requires `ServiceBlock_OMS_v1`, rejects unavailable verifier construction, and routes only when `is_compliance_verified` returns true. OMS results count as compliance-usable only when verified evidence is classified `live-provider`. Mock success and non-live runtime responses remain non-authoritative. The implementation source was not changed in this slice; one test file changed.

The first isolated command omitted required `VAMS_ENV` and failed during test setup (20 failed, 64 passed); it is not gate evidence. The recorded rerun sets `VAMS_ENV=test` and passes. Static syntax check and `git diff --check` exited 0.

This remains local test evidence with synthetic provider responses. It does not prove a real OMS provider, external endpoint/credential readiness, hosted CI, production whitelist/provider provenance, chain behavior, or deployment readiness. Higher-priority CLR routes may precede P3 when multiple routing flags are requested; this slice does not settle intended precedence. Readiness stays **NOT READY** and deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
