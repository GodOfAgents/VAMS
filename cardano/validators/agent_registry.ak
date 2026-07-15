//// VAMS agent registry spend validator.
////
//// Registration is performed by agent_nft.mint. This validator only permits
//// exact metadata updates and owner-authorized deregistration. Slashing is
//// deliberately disabled in the initial Cardano Pre-Prod profile.

use aiken/collection/list
use aiken/primitive/bytearray
use cardano/address.{Address, Script, VerificationKey}
use cardano/assets.{
  PolicyId, Value, add, from_lovelace, lovelace_of, quantity_of,
}
use cardano/transaction.{
  InlineDatum, Input, Output, OutputReference, Transaction,
}
use vams/types.{
  AgentDatum, DeregisterAgent, RegistryRedeemer, SlashAgent, UpdateAgent,
  cardano_schema_version,
}
use vams/utils.{is_signed_by}

const min_agent_stake: Int = 1_000_000_000

validator agent_registry {
  spend(
    datum_opt: Option<AgentDatum>,
    redeemer: RegistryRedeemer,
    own_ref: OutputReference,
    tx: Transaction,
  ) {
    expect Some(datum) = datum_opt
    expect Some(own_input) =
      list.find(tx.inputs, fn(input) { input.output_reference == own_ref })
    expect valid_agent_state(datum, own_input.output)
    expect is_signed_by(tx.extra_signatories, datum.owner)

    when redeemer is {
      UpdateAgent { new_metadata_hash } -> {
        expect bytearray.length(new_metadata_hash) == 32
        let expected = AgentDatum { ..datum, metadata_hash: new_metadata_hash }
        let matches =
          list.filter(
            tx.outputs,
            fn(output) {
              output.address == own_input.output.address && output.value == own_input.output.value && has_agent_datum(
                output,
                expected,
              )
            },
          )
        list.length(matches) == 1 && outputs_with_identity(
          tx.outputs,
          datum.identity_policy_id,
          datum.identity_asset_name,
        ) == 1
      }

      DeregisterAgent -> {
        let asset_name = datum.identity_asset_name
        expect quantity_of(tx.mint, datum.identity_policy_id, asset_name) == -1
        let refund_value =
          add(own_input.output.value, datum.identity_policy_id, asset_name, -1)
        let refunds =
          list.filter(
            tx.outputs,
            fn(output) {
              when output.address.payment_credential is {
                VerificationKey(hash) ->
                  hash == datum.owner && output.value == refund_value
                _ -> False
              }
            },
          )
        list.length(refunds) == 1 && outputs_with_identity(
          tx.outputs,
          datum.identity_policy_id,
          asset_name,
        ) == 0
      }

      // SlashAgent remains wire-visible but cannot authorize a transition.
      _ -> False
    }
  }

  else(_) {
    fail
  }
}

fn valid_agent_state(datum: AgentDatum, output: Output) -> Bool {
  and {
    datum.schema_version == cardano_schema_version,
    bytearray.length(datum.identity_asset_name) == 32,
    quantity_of(
      output.value,
      datum.identity_policy_id,
      datum.identity_asset_name,
    ) == 1,
    bytearray.length(datum.did) >= 32,
    bytearray.length(datum.owner) == 28,
    datum.reputation_score >= 0,
    datum.reputation_score <= 10_000,
    bytearray.length(datum.metadata_hash) == 32,
    datum.is_active,
    datum.staked_amount == lovelace_of(output.value),
    datum.staked_amount >= min_agent_stake,
    list.is_empty(datum.authorized_slashers),
  }
}

fn has_agent_datum(output: Output, expected: AgentDatum) -> Bool {
  when output.datum is {
    InlineDatum(raw_datum) -> {
      expect actual: AgentDatum = raw_datum
      actual == expected
    }
    _ -> False
  }
}

fn outputs_with_identity(
  outputs: List<Output>,
  policy_id: PolicyId,
  asset_name: ByteArray,
) -> Int {
  list.length(
    list.filter(
      outputs,
      fn(output) { quantity_of(output.value, policy_id, asset_name) == 1 },
    ),
  )
}

test min_stake_is_1000_ada() {
  min_agent_stake == 1_000 * 1_000_000
}

const fixture_policy_id: PolicyId =
  #"11111111111111111111111111111111111111111111111111111111"

const fixture_script_hash: ByteArray =
  #"22222222222222222222222222222222222222222222222222222222"

const fixture_owner: ByteArray =
  #"33333333333333333333333333333333333333333333333333333333"

const fixture_asset_name: ByteArray =
  #"4444444444444444444444444444444444444444444444444444444444444444"

const fixture_ref: OutputReference =
  OutputReference {
    transaction_id: #"5555555555555555555555555555555555555555555555555555555555555555",
    output_index: 0,
  }

const fixture_address: Address =
  Address {
    payment_credential: Script(fixture_script_hash),
    stake_credential: None,
  }

const fixture_value: Value =
  from_lovelace(min_agent_stake)
    |> add(fixture_policy_id, fixture_asset_name, 1)

const fixture_datum: AgentDatum =
  AgentDatum {
    schema_version: cardano_schema_version,
    identity_policy_id: fixture_policy_id,
    identity_asset_name: fixture_asset_name,
    did: #"6666666666666666666666666666666666666666666666666666666666666666",
    owner: fixture_owner,
    reputation_score: 5_000,
    registered_at: 1,
    metadata_hash: #"7777777777777777777777777777777777777777777777777777777777777777",
    is_active: True,
    staked_amount: min_agent_stake,
    authorized_slashers: [],
  }

const fixture_input: Input =
  Input {
    output_reference: fixture_ref,
    output: Output {
      address: fixture_address,
      value: fixture_value,
      datum: InlineDatum(fixture_datum),
      reference_script: None,
    },
  }

test update_requires_exact_transaction_successor() {
  let new_hash =
    #"8888888888888888888888888888888888888888888888888888888888888888"
  let updated = AgentDatum { ..fixture_datum, metadata_hash: new_hash }
  let output =
    Output {
      address: fixture_address,
      value: fixture_value,
      datum: InlineDatum(updated),
      reference_script: None,
    }
  agent_registry.spend(
    Some(fixture_datum),
    UpdateAgent { new_metadata_hash: new_hash },
    fixture_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_input],
      outputs: [output],
      extra_signatories: [fixture_owner],
    },
  )
}

test update_rejects_value_substitution() fail {
  let new_hash =
    #"8888888888888888888888888888888888888888888888888888888888888888"
  let updated = AgentDatum { ..fixture_datum, metadata_hash: new_hash }
  let output =
    Output {
      address: fixture_address,
      value: fixture_value |> add("", "", -1),
      datum: InlineDatum(updated),
      reference_script: None,
    }
  agent_registry.spend(
    Some(fixture_datum),
    UpdateAgent { new_metadata_hash: new_hash },
    fixture_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_input],
      outputs: [output],
      extra_signatories: [fixture_owner],
    },
  )
}

test slashing_is_disabled_on_valid_state() fail {
  agent_registry.spend(
    Some(fixture_datum),
    SlashAgent {
      evidence_hash: #"9999999999999999999999999999999999999999999999999999999999999999",
      slash_amount: 1,
    },
    fixture_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_input],
      extra_signatories: [fixture_owner],
    },
  )
}
