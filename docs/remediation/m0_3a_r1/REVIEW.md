# M0.3a-R1 local source review

This is local adjudication, not independent review or release approval.
Superproject: 829ab544571f12efe50ecb5740f129c8acb3e16f.
OpenZeppelin gitlink and clean HEAD: 239795bea728c8dca4deb6c66856dd58a6991112.

## Exact source review

All 161 prior stable identities across 23 paths were inspected. Each final
decision binds its complete file SHA-256, exact path, rule and line range.
The 86 JavaScript findings are Chai revertedWithCustomError assertions: a
test contract object and an expected public ERC error name. These expressions
do not assign or load credentials. Full-line anchored syntax is rechecked.
The remaining 75 findings are keyDer fields in the ECDSA P1363 verification
vector JSON. Each belongs to an EcPublicKey/EcdsaP1363Verify group and each DER
parses with `openssl pkey -pubin -inform DER -noout`. No private key is needed.
Only the proof category is retained; values, snippets, scanner matches,
entropy and value-derived fingerprints are not copied into decisions.

## Reachability review of current first-party execution boundaries

- Production compilation: contracts/foundry.toml uses src and lib; the
  OpenZeppelin remapping targets contracts/, not test/. All 23 paths are JS
  tests or JSON; none is a Solidity compilation unit. First-party Solidity
  source, scripts and tests contain no vm.ffi, vm.readFile or vm.parseJson call.
- Deployment: contracts/script contains Solidity entrypoints. First-party
  scripts and deployment configuration do not reference these 23 paths or
  their filenames; contracts/package.json contains dependency declarations
  and no command invoking vendor Hardhat tests.
- Runtime, gateway and credential loading: the first-party tracked/unignored
  execution/configuration inventory has no reference to these paths or their
  filenames. No vendor-test loader or Hardhat execution entrypoint was found.
- Frontend: frontend-vite/package.json runs Vite and ESLint from frontend-vite.
  Its first-party imports and configuration contain no reference to these files.
- CI execution: .github/workflows/security-gates.yml runs Forge under
  contracts, Python pytest, Aiken, Rust, and frontend npm commands. It has no
  vendor Hardhat/Mocha execution command. Python discovery does not execute
  .test.js/.behavior.js or the JSON fixture. Security scanners and this helper
  read vendor bytes as evidence; they do not execute the vendor tests.

The source-manifest digest in every decision binds the current first-party
source/configuration inventory, including dirty and unignored new source.
The helper rehashes that inventory before and after scanning. Documentation
and Codex instruction files are outside these execution roots. Other vendor
submodules were not reviewed; no conclusion about their findings is made.
This is a source/configuration reachability result, not a live deployment trace.
Changes to source, configuration, this review, or the vendor pin require review
and fresh decisions. No Foundry build is claimed by this slice.

## Decision policy and gate

Separate decisions.json contains one record per finding, keyed by finding_id.
Accepted means codex_local_source_review accepted the above exact proofs;
independent reviewer acceptance remains pending. The CLI requires an explicit
approved SHA-256 of decisions.json. It compares the full freshly adjudicated
record list against that content-addressed set. New, removed, changed,
unresolved, potential-credential, stale or unaccepted records cannot pass.
No Gitleaks suppression is added. Scanner exit 1 remains recorded even when
this separate local adjudication gate returns 0. Missing or malformed inputs
never authorize acceptance. Potential-credential blockers are published
atomically before a nonzero result. All raw scanner files are temporary mode
0700 directory contents and are removed before publication.

M0, M7, T06, F18 and all promotion gates remain open. The next single slice is
independent review of M0.3a-R1; no later submodule tranche starts here.
