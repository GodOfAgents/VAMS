# Cardano Pre-Prod Deployment Rehearsal

**Network:** Cardano Pre-Prod, network magic `1`

**Posture:** Faucet-only, transaction construction only until explicit approval
**Last verified:** 2026-07-14

Only `agent_registry.ak`, `governor.ak`, `insurance_fund.ak`, and `timelock.ak`
are deployable validators. `cardano/lib/vams/vdso.ak` is a conformance library
and must not appear in a deployment transaction or validator list.

## Build and deterministic extraction

```bash
cd cardano
aiken check --deny --seed 20260713 --max-success 250
aiken build
cd ..
python scripts/deployment/cardano_preprod_artifacts.py \
  --blueprint cardano/plutus.json \
  --output-dir build/cardano-preprod \
  --commit-sha "$(git rev-parse HEAD)"
```

The extractor fails if any authoritative validator is absent or a VDSO entry
is present. It writes four deterministic Plutus V3 text envelopes and
`cardano-preprod-artifacts.json`, binding the blueprint, CBOR, artifact hashes,
source paths, and Aiken-declared script hashes to the exact commit. Re-run the
command and require byte-for-byte identical output.

Independently derive each script hash with the pinned `cardano-cli` release and
compare it to the extractor manifest. A mismatch is an automatic stop:

```bash
for script in build/cardano-preprod/*.plutus; do
  cardano-cli conway transaction policyid --script-file "$script"
done
```

## External inputs

- `CARDANO_NODE_SOCKET_PATH` or an approved provider endpoint for Pre-Prod;
  provider URLs may be sensitive if token-bearing.
- `PAYMENT_ADDRESS`: funded faucet-only Pre-Prod address; public.
- `PAYMENT_SKEY_FILE`: local signing-key file path; the file contents are
  secret and must never be copied into evidence, chat, or Git.
- Governance, emergency, guardian, and recovery script/multisig parameters,
  approved owner sets, thresholds, setup evidence, and recovery procedure.

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

The reviewed transaction body must reference exactly the four extracted
scripts, correct inline datum/reference-script choices, intended multisig and
timelock controls, network magic `1`, and no VDSO, rewards, incentives, or real
value. Record deterministic CBOR/script hashes and transaction-body hash, but
do not invent a transaction ID before submission.

## Approval, confirmation, and recovery

Stop before `cardano-cli conway transaction submit`. Submission requires the
user's explicit approval for the exact signed transaction body. After an
approved submission, independently query confirmation and each script output,
then populate `cardano-preprod-deployment.json`. If confirmation or state is
wrong, do not resubmit blindly: preserve the signed body and provider logs,
halt dependent deployment, and execute the pre-reviewed recovery transaction
or governance/timelock cancellation path.
