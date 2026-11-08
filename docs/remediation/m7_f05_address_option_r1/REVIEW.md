# Independent integrated review

Verdict: PASS for the bounded synthetic address-encoding correction and positive observation only; full F05 public suite FAIL, no new case/mutation credit.

The reviewer read the exact integrated harness (SHA-256 `9f26eb11f3511647db9422d9e97464fca2083546d92bee379ae8bb06c78fc228`) and separate address tests (SHA-256 `78ece760e7192fa412b33ea38777ae170947223eaf39b5e2024a14e0d5c74853`). The Plutus Option constructors and separate stake hash are correct. The reviewer independently ran offline, read-only focused address/alias tests: 24/24 PASS, `git diff --check` exit 0. The coordinator's additional harness diagnostics yield 27/27 PASS. The 23 protected files were unchanged during full execution.

The positive capture is a diagnostic monkeypatch of the harness stop function and records evaluator acceptance before the negatives. The full harness itself passed that control but exited 1 at `remove_no_extra_asset_guard / authority_extra_native_asset` without a result artifact. The earlier signed transaction-simulator extra-asset triad is separate evidence and is not overturned by this synthetic harness failure. INV-1INV-10 enforcement files, compiled validator, fixture, and blueprint were untouched. No mock promotion or live evidence.

Next slice: diagnose this mutation/fixture interaction separately; retain the unconditional_success context-rebinding defect and owner evidence-scope decisions as independent blockers.
