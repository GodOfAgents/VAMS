# Authorized solc 0.8.24 acquisition and verification

- Official release index: https://binaries.soliditylang.org/linux-amd64/list.json
- Index object SHA-256 observed: `ee1a2b4811bd1225c220cd2342e2b49a58cbe18f5687f230f456c443b29497d6` (47,730 bytes).
- Matching published build entry: path `solc-linux-amd64-v0.8.24+commit.e11b9ed9`; version `0.8.24`; long version `0.8.24+commit.e11b9ed9`; published SHA-256 `0xfb03a29a517452b9f12bcf459ef37d0a543765bb3bbc911e70a87d6a37c30d5f`.
- Artifact URL: `https://binaries.soliditylang.org/linux-amd64/solc-linux-amd64-v0.8.24+commit.e11b9ed9`
- Stored path: `/home/GodOfAgents/vams-evidence/toolchains/solc-0.8.24/solc-linux-amd64-v0.8.24+commit.e11b9ed9`; mode `0555`; observed SHA-256 `fb03a29a517452b9f12bcf459ef37d0a543765bb3bbc911e70a87d6a37c30d5f`.

Commands/results:

1. Read the official index over HTTPS using `curl --fail --silent --show-error --location --proto '=https' --tlsv1.2`; parsed the exact build path and compared the published `sha256` field with the user-authorized value. Match.
2. Downloaded the exact artifact once with `curl --fail --silent --show-error --location --proto '=https' --tlsv1.2` to a staging file under `/home/GodOfAgents/vams-evidence/toolchains/solc-0.8.24/`.
3. Before execution, `sha256sum --check --strict` over the staged file reported `OK` and its observed digest matched `fb03a29a517452b9f12bcf459ef37d0a543765bb3bbc911e70a87d6a37c30d5f`.
4. Executed only `"/home/GodOfAgents/vams-evidence/toolchains/solc-0.8.24/solc-linux-amd64-v0.8.24+commit.e11b9ed9" --version` after the checksum match. Output:

```text
solc, the solidity compiler commandline interface
Version: 0.8.24+commit.e11b9ed9.Linux.g++
```

The acquisition shell wrapper returned 1 at its final post-move `sha256sum` display because a PowerShell-fed Bash variable carried a carriage return in that one argument. The staged checksum check and version check had already passed. A Python directory-entry check, the pre-test compiler hash/version gate recorded in `RUN.json`, a literal-path `sha256sum` command, and independent review all confirmed the exact final path and digest above. There was no checksum or version mismatch, no unverified binary was executed, and the partial staging path was cleaned.

No system-wide install or PATH change occurred. No additional dependency was acquired.
