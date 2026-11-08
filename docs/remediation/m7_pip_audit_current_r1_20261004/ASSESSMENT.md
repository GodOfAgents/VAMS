# M7 pip-audit local environment assessment (r1)

Date: 2026-10-04
Disposition: **FAIL for the captured installed environment**
Readiness: **NOT READY**

The exact workflow command `pip-audit --local --vulnerability-service pypi` ran once with pip-audit 2.10.1 and Python 3.12.14. Exit 1; advisory lookup succeeded. Output reports 13 rows across anyio 4.14.1 (3), httpcore2 2.5.0 (1), httpx2 2.5.0 (4), pip 26.1.2 (2 rows for one advisory ID with two fix strings), and urllib3 2.7.0 (3). These are 12 distinct advisory IDs. Exact IDs and fix versions are in retained stdout. The command does not classify severity; none is inferred.

The scan covered 103 distributions in the installed tool interpreter environment. A read-only crosswalk found all direct entries in both repository requirements files present at versions satisfying their declared lower bounds. This is still an installed-environment scan, not requirements-file resolution or hosted CI. The two workflow commands `pip-audit -r gateway/requirements.txt` and `pip-audit -r neuron/requirements.txt` remain unrun. Findings remain unadjudicated and unwaived.

The ten-file raw capture and checksum manifest are retained at `/home/GodOfAgents/vams-evidence/m7-pip-audit-current-r1-20261004/`. No dependency, vendor, toolchain, source, credential, or activation changed. INV-1 through INV-10 were not touched. F04 anchoring/registration, F05 (45/55 negatives; 18/21 mutations), T06/history, remaining security and reproducible-build gates, Foundry build/test, and Cardano Pre-Prod / Polygon Amoy prerequisites remain open. Readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Next single slice: run exact workflow command `pip-audit -r gateway/requirements.txt` with the installed tool, without changing repository dependencies; preserve resolver/advisory output and independently review it before the neuron requirements command.
