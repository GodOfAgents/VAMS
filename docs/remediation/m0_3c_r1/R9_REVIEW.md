# M0.3c-R9 remediation review

Status: locally implemented and verified; independent M0.3c-R10 review required.

R9 replaces pathname-based durable-evidence validation with one descriptor-bound immutable snapshot. Every allowed artifact is opened once relative to already-open no-follow directory descriptors, bounded, read into immutable bytes, and checked for device, inode, type, link count, size, mtime, and ctime stability before success. Outer and inner manifests, JSON schemas, attestation records, and gate data are parsed only from captured bytes. Deterministic full-validator tests reject inode replacement, same-inode writes, truncate/extend/restore, manifest replacement, JSON replacement, directory replacement, and mutation after parsing. A pathname-reopen denial test passes.

The independent semantic oracle no longer contains or imports production error-policy or execution-target catalogs. It derives callers, deployed artifacts, invoked operations, declarations, signatures, selectors, and graph routes from pinned JavaScript and Solidity Git objects. This exposed and corrected the production FlashMint target from $ERC20FlashMint to the deployed $ERC20FlashMintMock. Production and oracle results agree on the freshly observed set.

Fresh results remain 158 findings across 22 paths: 83 exact custom-error assertion fixtures and 75 public DER vectors, with 821 directly owned blobs and three excluded gitlinks. Dispositions are 158 confirmed_noncredential_fixture, zero unresolved, and zero potential credentials. Focused R9 tests pass 13/13; complete M0.3c passes 60/60; M0.3a 20/20; M0.3b 16/16; existing Gitleaks 11/11. The negative fixture, expanded R4/R6 matrix, pre-fix R8 reproduction, 34-case binding matrix, fresh scan/reconciliation, exact-set gate, and diff checks pass.

No vendor, .gitleaks.toml, production contract, runtime, gateway, CI, deployment, or mock-mode behavior changed. INV-1 through INV-10 have no impact. M0, M7, T06, F18, and every promotion gate remain open. The next slice is independent M0.3c-R10 review.
