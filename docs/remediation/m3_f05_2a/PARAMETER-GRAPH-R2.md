# F05.2a R2 parameter and artifact dependency graph

Status: proposal for independent review; no source edits or canonical transfer.

1. Pin canonical state-validator source, `aiken.toml`, exact stdlib/fuzz
   dependencies and `cardano/aiken.lock`; compile with Aiken 1.1.21, Plutus V3.
2. Apply the state validator with **zero parameters**. Record complete UPLC
   bytes, their canonical encoding, and the resulting 28-byte ScriptHash.
3. Insert that exact ScriptHash as a reviewed generated constant into the
   mint-policy source. Do not add a policy-hash or caller credential parameter
   to the state validator. The mint policy's genesis reference and ordered
   five public keys are its only deployment parameters; R4 Pre-Prod network
   tuple is a source-fixed domain constant.
4. Recompile with the same pinned environment. Verify state-validator bytes
   and hash are identical to step 2. Apply the mint policy to exact seed/key
   parameters and derive the policy hash. The fixed singleton asset name plus
   that policy hash defines the one permitted NFT.
5. Construct the exact 10,000,000-lovelace + singleton output at the state
   validator address. No fees, collateral or change are charged to this
   output. Independently verify all five signatures over Amendment R2's exact
   canonical message.
6. Record source/compiler/lock/parameter/program/hash/policy/address/output
   values in forward provenance and independently reproduce them.

The only accepted policy application is the one whose exact seed/key parameter
bytes are fixed in the deployment provenance record and whose resulting
policy ID is consumed by all deployment-facing clients. Other self-consistent
parameter applications are distinct policy instances and are not admitted as
the deployment authority; Plutus cannot query the external canonical
parameter manifest.

The graph has no back-edge: state validator -> state hash -> policy source ->
policy -> singleton -> genesis output. In particular, policy ID, NFT, seed
output, and generated policy artifact never determine state-validator code or
parameters. The network tuple is signed and source-fixed, but the Plutus V3
context omits actual network identity; the signed domain is not an on-chain
network oracle.
