# Retained gateway requirements audit capture

Raw capture directory: `/home/GodOfAgents/vams-evidence/m7-pip-audit-gateway-r1-20261004/`.
The 16-file SHA256SUMS manifest verifies; manifest digest: `5600b1a665931fc4a59893eb130a056e79c8288d47385441f6dc10c6c546d6ee`.

The capture records command, timestamps, exit, tool/interpreter/workflow/requirements identities, empty stdout, stderr result, and before/after inventory manifests. Inventory diff is empty and both package inventories share SHA-256 `1cbec2a8b3e2c7b2d62a114f04ac3c79cd2a77a4af42c96f43f3b6d811b2c1a7`.

Scanner behavior note: the installed pip-audit `-r` implementation resolves through a temporary virtual environment with pip's dry-run/report path; transient setup and package-index access may occur even though the repository environment remains unchanged. The exact fetched artifacts were not captured.
