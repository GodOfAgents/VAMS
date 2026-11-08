# M7 gateway requirements pip-audit assessment (r1)

Date: 2026-10-04
Disposition: **PASS for gateway requirements resolution**
Readiness: **NOT READY**

The exact workflow command `pip-audit -r gateway/requirements.txt` ran once using pip-audit 2.10.1 / Python 3.12.14. It exited 0 and reported `No known vulnerabilities found`. The raw capture records empty stdout and the message on stderr. Workflow SHA-256 was `baf53503673b70c5185f654f8f694f1feaf98af68ee56e29c83c01ee0cf0593c`; gateway requirements SHA-256 was `c442d01c246812c909fd28f6cf90c14c5e17921597d409c0492fbbf808e0f0b3`.

The scanner resolved the requirements in a temporary virtual environment through pip's dry-run/report path. Its source uses temporary pip/wheel/setuptools setup and may query/fetch package-index metadata; the exact fetched URLs/bytes are not recorded. No separate install/update command was run. The pinned toolchain's 103-distribution inventory was byte-identical before and after (SHA-256 `1cbec2a8b3e2c7b2d62a114f04ac3c79cd2a77a4af42c96f43f3b6d811b2c1a7`). The canonical checkout was unchanged by the scan. This is a local dependency-resolution result, not hosted CI evidence.

This slice does not close the separate `pip-audit --local` result (13 rows / five installed-environment packages), nor the neuron requirements audit. No repository dependency, vendor, source, credential, or persistent toolchain changed. INV-1 through INV-10 were not touched. Readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Next: the neuron requirements audit invokes the same temporary pip resolver/tool setup behavior. It is held pending the user's explicit decision about allowing that transient resolution/fetch behavior under the no-tool-install/fetch constraint. Other already-installed offline gates remain available while this specific audit is held.
