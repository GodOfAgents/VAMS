# Independent review - F05.2a applied-policy identity revalidation

PASS for the narrow current synthetic fixture identity claim. The reviewer independently matched all 21 canonical Cardano input hashes to the result's before/after inventories, compared both isolated build outputs with the applied artifact and valid fixture witness, decoded Mint[0], and recomputed BLAKE2b-224(0x03 || compiledCode). Blueprint outputs match, normalized locks equal the canonical lock, and pinned Aiken is v1.1.21+42babe5 with SHA-256 07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79.

Limitations: the manifest and copied exact probe source were added after review and then all manifest entries were verified by the coordinator. Separate build directories do not establish process/network isolation; Aiken resolved two packages from cache. This is synthetic identity only, with no ledger/live evidence or new F05 count credit.
