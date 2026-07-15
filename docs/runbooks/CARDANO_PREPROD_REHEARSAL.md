# Cardano Pre-Prod Deployment Rehearsal

**Network:** Cardano Pre-Prod, network magic `1`

**Posture:** Faucet-only, transaction construction only until explicit approval
**Last verified:** 2026-07-15 (source/tooling only; applied artifacts pending)

Only `agent_registry.ak`, `governor.ak`, `insurance_fund.ak`, and `timelock.ak`
are persistent validators. `agent_nft.ak`, `proposal_nft.ak`, and `fund_nft.ak`
are auxiliary one-shot policies and must be listed separately.
`cardano/lib/vams/vdso.ak` is a conformance library and must not appear in a
deployment transaction or validator list.

## Build and deterministic extraction

```bash
cd cardano
aiken check --deny --seed 20260713 --max-success 250
aiken build
cd ..
python scripts/deployment/cardano_preprod_artifacts.py \
  --blueprint cardano/plutus.json \
  --output-dir build/cardano-preprod-templates \
  --commit-sha "$(git rev-parse HEAD)"
```

The extractor fails if any authoritative validator is absent or a VDSO entry
is present. It writes explicitly non-deployable template records and
`cardano-preprod-artifacts.json`. A template hash is not a final script hash
and must not be entered in the deployment register.

Create a public parameter manifest that validates against
`docs/audit/schemas/cardano-preprod-parameters.schema.json`. It must bind the
exact commit and contain the ordered Plutus-Data CBOR parameters for all four
persistent validators plus exactly one canonical `fund_nft` bootstrap policy
instance. Add `agent_nft` or `proposal_nft` instances only when the reviewed
transaction actually creates an agent or proposal. Seed UTxO references,
script hashes, thresholds, timing bounds, public asset identifiers, and allowed
target scripts are public; signing keys are never parameters.

Apply every parameter and emit final artifacts into a new empty directory:

```bash
python scripts/deployment/cardano_preprod_apply.py \
  --blueprint cardano/plutus.json \
  --parameters "$CARDANO_PARAMETER_MANIFEST" \
  --output-dir build/cardano-preprod-applied \
  --commit-sha "$(git rev-parse HEAD)" \
  --aiken aiken
```

The apply tool rejects missing, extra, malformed, or wrong-order parameter
sets, a missing/duplicate fund bootstrap, any VDSO entry, a dirty Cardano tree,
a mismatched commit, nonempty output directories, and any applied script that
remains parameterized. Its schema-v3 manifest records four persistent
validators, all three auxiliary templates, and only the real applied auxiliary
instances separately.
Run it twice into separate empty directories and require byte-for-byte
identical output.

Independently derive each script hash with the pinned `cardano-cli` release and
compare it to the extractor manifest. A mismatch is an automatic stop:

```bash
for script in build/cardano-preprod-applied/*.plutus; do
  cardano-cli conway transaction policyid --script-file "$script"
done
```

For spending validators, also use the pinned `cardano-cli` script-address/hash
command appropriate to the reviewed CLI release; `policyid` is only the
independent check for minting policies. Every independently derived hash must
match `cardano-preprod-artifacts.json`.

## External inputs

- `CARDANO_NODE_SOCKET_PATH` or an approved provider endpoint for Pre-Prod;
  provider URLs may be sensitive if token-bearing.
- `PAYMENT_ADDRESS`: funded faucet-only Pre-Prod address; public.
- `PAYMENT_SKEY_FILE`: local signing-key file path; the file contents are
  secret and must never be copied into evidence, chat, or Git.
- Governance, emergency, guardian, and recovery script/multisig parameters,
  approved owner sets, thresholds, setup evidence, and recovery procedure.
- `CARDANO_PARAMETER_MANIFEST`: path to the reviewed public JSON parameter
  manifest. It contains no signing secrets but must be approved as part of the
  exact deployment ceremony.

## Construct without submitting

Verify the network and current protocol parameters, query faucet UTxOs, then
construct and sign the exact transaction in an isolated signing environment.
Do not submit it:

```bash
cardano-cli conway query tip --testnet-magic 1
cardano-cli conway query utxo \
  --address "$PAYMENT_ADDRESS" --testnet-magic 1 --out-file preprod-utxo.json
cardano-cli conway query protocol-parameters \
  --testnet-magic 1 --out-file preprod-protocol-parameters.json
# Construct the reviewed transaction with explicit script outputs and datum.
# Sign only in the isolated signer; retain the body hash and redacted summary.
```

The reviewed transaction body must reference exactly four applied persistent
validators and separately enumerate only the required applied auxiliary
policies. Confirm the schema-v2 authentication asset classes, unique seed
UTxOs, exact inline datum/reference-script choices, intended multisig and
timelock controls, allowed Cardano-local target scripts, network magic `1`, and
no VDSO, bridge execution, cross-chain deposits, slashing, rewards, incentives,
or real value. Record deterministic CBOR/script hashes and the transaction-body
hash, but do not invent a transaction ID before submission.

## Approval, confirmation, and recovery

Stop before `cardano-cli conway transaction submit`. Submission requires the
user's explicit approval for the exact signed transaction body. After an
approved submission, independently query confirmation and each script output,
then populate `cardano-preprod-deployment.json`. If confirmation or state is
wrong, do not resubmit blindly: preserve the signed body and provider logs,
halt dependent deployment, and execute the pre-reviewed recovery transaction
or governance/timelock cancellation path.
