# Retained pip-audit local capture

Raw capture: `/home/GodOfAgents/vams-evidence/m7-pip-audit-current-r1-20261004/`. All ten entries in its SHA256SUMS verify.

Key hashes: stdout `c5177c516f6340eb1093cb74fb85ee566140e13320f990c6f237f0d4a13fe23d`; stderr `ff174debbe2a0e53c848d45286cef1967a23b0f33dc3d8ff417f74e38a8206c2`; local inventory `1cbec2a8b3e2c7b2d62a114f04ac3c79cd2a77a4af42c96f43f3b6d811b2c1a7`. Raw manifest contains hashes for all captured command, time, exit, metadata, inventory, stdout/stderr records.

The workflow also runs `pip-audit -r gateway/requirements.txt` and `pip-audit -r neuron/requirements.txt`; neither is covered by this `--local` capture.
