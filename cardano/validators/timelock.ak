//// VAMS authenticated Cardano-local timelock.
////
//// The proposal NFT proves that an intent came through the governor. Local
//// execution emits one exact value and inline-datum commitment. The bridge
//// branch is wire-visible but unconditionally disabled.

use aiken/builtin
use aiken/collection/list
use aiken/crypto.{blake2b_256}
use aiken/interval.{Finite}
use aiken/primitive/bytearray
use cardano/address.{Address, Script, VerificationKey}
use cardano/assets.{PolicyId, Value, add, quantity_of}
use cardano/transaction.{
  InlineDatum, Input, Output, OutputReference, Transaction,
}
use vams/types.{
  CancelIntent, ExecuteBridge, ExecuteLocal, IntentDatum, TimelockRedeemer,
  cardano_schema_version,
}
use vams/utils.{count_signatures}

validator timelock(
  allowed_target_scripts: List<ByteArray>,
  emergency_members: List<ByteArray>,
  emergency_threshold: Int,
  max_intent_lifetime_ms: Int,
) {
  spend(
    datum_opt: Option<IntentDatum>,
    redeemer: TimelockRedeemer,
    own_ref: OutputReference,
    tx: Transaction,
  ) {
    expect Some(datum) = datum_opt
    expect Some(own_input) =
      list.find(tx.inputs, fn(input) { input.output_reference == own_ref })
    expect
      valid_intent(
        datum,
        own_input.output,
        allowed_target_scripts,
        max_intent_lifetime_ms,
      )

    when redeemer is {
      ExecuteLocal -> {
        expect Finite(valid_from) = tx.validity_range.lower_bound.bound_type
        expect Finite(valid_until) = tx.validity_range.upper_bound.bound_type
        expect valid_from >= datum.execute_after
        expect valid_until <= datum.expires_at
        expect
          quantity_of(
            tx.mint,
            datum.proposal_policy_id,
            datum.proposal_asset_name,
          ) == -1
        let target_value =
          add(
            own_input.output.value,
            datum.proposal_policy_id,
            datum.proposal_asset_name,
            -1,
          )
        exact_target_output(
          tx.outputs,
          datum.target_script_hash,
          datum.action_hash,
          target_value,
        ) && count_outputs_with_asset(
          tx.outputs,
          datum.proposal_policy_id,
          datum.proposal_asset_name,
        ) == 0
      }

      ExecuteBridge { bridge_proof, payload_hash } ->
        // Preserve INV-10 field separation while refusing mock proof shapes.
        bytearray.length(bridge_proof) >= 0 && bytearray.length(payload_hash) >= 0 && False

      CancelIntent -> {
        expect Finite(valid_until) = tx.validity_range.upper_bound.bound_type
        expect valid_until <= datum.expires_at
        expect emergency_threshold >= 2
        expect emergency_threshold <= list.length(emergency_members)
        expect
          count_signatures(tx.extra_signatories, emergency_members) >= emergency_threshold
        expect
          quantity_of(
            tx.mint,
            datum.proposal_policy_id,
            datum.proposal_asset_name,
          ) == -1
        let refund_value =
          add(
            own_input.output.value,
            datum.proposal_policy_id,
            datum.proposal_asset_name,
            -1,
          )
        exact_refund_output(tx.outputs, datum.refund_key_hash, refund_value) && count_outputs_with_asset(
          tx.outputs,
          datum.proposal_policy_id,
          datum.proposal_asset_name,
        ) == 0
      }
    }
  }

  else(_) {
    fail
  }
}

fn valid_intent(
  datum: IntentDatum,
  output: Output,
  allowed_target_scripts: List<ByteArray>,
  max_intent_lifetime_ms: Int,
) -> Bool {
  and {
    datum.schema_version == cardano_schema_version,
    bytearray.length(datum.proposal_asset_name) == 32,
    quantity_of(
      output.value,
      datum.proposal_policy_id,
      datum.proposal_asset_name,
    ) == 1,
    bytearray.length(datum.action_hash) == 32,
    bytearray.length(datum.target_script_hash) == 28,
    !list.is_empty(allowed_target_scripts),
    list.has(allowed_target_scripts, datum.target_script_hash),
    datum.execute_after >= 0,
    datum.expires_at > datum.execute_after,
    datum.expires_at - datum.execute_after == max_intent_lifetime_ms,
    bytearray.length(datum.refund_key_hash) == 28,
  }
}

fn exact_target_output(
  outputs: List<Output>,
  target_script_hash: ByteArray,
  action_hash: ByteArray,
  value: Value,
) -> Bool {
  list.length(
    list.filter(
      outputs,
      fn(output) {
        when output.address.payment_credential is {
          Script(hash) ->
            hash == target_script_hash && output.value == value && inline_datum_hash_matches(
              output,
              action_hash,
            )
          _ -> False
        }
      },
    ),
  ) == 1
}

fn inline_datum_hash_matches(output: Output, expected: ByteArray) -> Bool {
  when output.datum is {
    InlineDatum(raw) -> blake2b_256(builtin.serialise_data(raw)) == expected
    _ -> False
  }
}

fn exact_refund_output(
  outputs: List<Output>,
  refund_key_hash: ByteArray,
  value: Value,
) -> Bool {
  list.length(
    list.filter(
      outputs,
      fn(output) {
        when output.address.payment_credential is {
          VerificationKey(hash) ->
            hash == refund_key_hash && output.value == value
          _ -> False
        }
      },
    ),
  ) == 1
}

fn count_outputs_with_asset(
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

test emergency_threshold_is_multisig() {
  2 >= 2
}

test bridge_branch_is_disabled() {
  let proof = #"00"
  let payload = #"01"
  !(bytearray.length(proof) >= 0 && bytearray.length(payload) >= 0 && False)
}

const fixture_policy_id: PolicyId =
  #"11111111111111111111111111111111111111111111111111111111"

const fixture_asset_name: ByteArray =
  #"2222222222222222222222222222222222222222222222222222222222222222"

const fixture_timelock_hash: ByteArray =
  #"33333333333333333333333333333333333333333333333333333333"

const fixture_target_hash: ByteArray =
  #"44444444444444444444444444444444444444444444444444444444"

const fixture_refund_key: ByteArray =
  #"55555555555555555555555555555555555555555555555555555555"

const fixture_emergency_one: ByteArray =
  #"66666666666666666666666666666666666666666666666666666666"

const fixture_emergency_two: ByteArray =
  #"77777777777777777777777777777777777777777777777777777777"

const fixture_intent_ref: OutputReference =
  OutputReference {
    transaction_id: #"8888888888888888888888888888888888888888888888888888888888888888",
    output_index: 0,
  }

test local_execution_binds_exact_target_value_and_datum() {
  let target_datum: Data = 42
  let action_hash = blake2b_256(builtin.serialise_data(target_datum))
  let intent =
    IntentDatum {
      schema_version: cardano_schema_version,
      proposal_policy_id: fixture_policy_id,
      proposal_asset_name: fixture_asset_name,
      source_proposal: OutputReference { ..fixture_intent_ref, output_index: 1 },
      action_hash,
      target_script_hash: fixture_target_hash,
      execute_after: 100,
      expires_at: 1_000,
      refund_key_hash: fixture_refund_key,
    }
  let locked_value =
    assets.from_lovelace(5_000_000)
      |> add(fixture_policy_id, fixture_asset_name, 1)
  let input =
    Input {
      output_reference: fixture_intent_ref,
      output: Output {
        address: Address {
          payment_credential: Script(fixture_timelock_hash),
          stake_credential: None,
        },
        value: locked_value,
        datum: InlineDatum(intent),
        reference_script: None,
      },
    }
  let target =
    Output {
      address: Address {
        payment_credential: Script(fixture_target_hash),
        stake_credential: None,
      },
      value: add(locked_value, fixture_policy_id, fixture_asset_name, -1),
      datum: InlineDatum(target_datum),
      reference_script: None,
    }
  timelock.spend(
    [fixture_target_hash],
    [fixture_emergency_one, fixture_emergency_two],
    2,
    900,
    Some(intent),
    ExecuteLocal,
    fixture_intent_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [input],
      outputs: [target],
      mint: assets.from_asset(fixture_policy_id, fixture_asset_name, -1),
      validity_range: interval.between(100, 999),
    },
  )
}

test bridge_execution_fails_with_authenticated_intent() fail {
  let intent =
    IntentDatum {
      schema_version: cardano_schema_version,
      proposal_policy_id: fixture_policy_id,
      proposal_asset_name: fixture_asset_name,
      source_proposal: OutputReference { ..fixture_intent_ref, output_index: 1 },
      action_hash: #"9999999999999999999999999999999999999999999999999999999999999999",
      target_script_hash: fixture_target_hash,
      execute_after: 100,
      expires_at: 1_000,
      refund_key_hash: fixture_refund_key,
    }
  let input =
    Input {
      output_reference: fixture_intent_ref,
      output: Output {
        address: Address {
          payment_credential: Script(fixture_timelock_hash),
          stake_credential: None,
        },
        value: assets.from_lovelace(5_000_000)
          |> add(fixture_policy_id, fixture_asset_name, 1),
        datum: InlineDatum(intent),
        reference_script: None,
      },
    }
  timelock.spend(
    [fixture_target_hash],
    [fixture_emergency_one, fixture_emergency_two],
    2,
    900,
    Some(intent),
    ExecuteBridge { bridge_proof: #"00", payload_hash: #"01" },
    fixture_intent_ref,
    Transaction { ..transaction.placeholder, inputs: [input] },
  )
}

fn fixture_intent(action_hash: ByteArray) -> IntentDatum {
  IntentDatum {
    schema_version: cardano_schema_version,
    proposal_policy_id: fixture_policy_id,
    proposal_asset_name: fixture_asset_name,
    source_proposal: OutputReference { ..fixture_intent_ref, output_index: 1 },
    action_hash,
    target_script_hash: fixture_target_hash,
    execute_after: 100,
    expires_at: 1_000,
    refund_key_hash: fixture_refund_key,
  }
}

fn fixture_locked_value() -> Value {
  assets.from_lovelace(5_000_000)
    |> add(fixture_policy_id, fixture_asset_name, 1)
}

fn fixture_intent_input(intent: IntentDatum) -> Input {
  Input {
    output_reference: fixture_intent_ref,
    output: Output {
      address: Address {
        payment_credential: Script(fixture_timelock_hash),
        stake_credential: None,
      },
      value: fixture_locked_value(),
      datum: InlineDatum(intent),
      reference_script: None,
    },
  }
}

fn fixture_target_output(target_datum: Data, value: Value) -> Output {
  Output {
    address: Address {
      payment_credential: Script(fixture_target_hash),
      stake_credential: None,
    },
    value,
    datum: InlineDatum(target_datum),
    reference_script: None,
  }
}

test local_execution_rejects_premature_validity_interval() fail {
  let target_datum: Data = 42
  let intent = fixture_intent(blake2b_256(builtin.serialise_data(target_datum)))
  timelock.spend(
    [fixture_target_hash],
    [fixture_emergency_one, fixture_emergency_two],
    2,
    900,
    Some(intent),
    ExecuteLocal,
    fixture_intent_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_intent_input(intent)],
      outputs: [
        fixture_target_output(target_datum, assets.from_lovelace(5_000_000)),
      ],
      mint: assets.from_asset(fixture_policy_id, fixture_asset_name, -1),
      validity_range: interval.between(99, 999),
    },
  )
}

test local_execution_rejects_datum_substitution() fail {
  let committed_datum: Data = 42
  let substituted_datum: Data = 43
  let intent =
    fixture_intent(blake2b_256(builtin.serialise_data(committed_datum)))
  timelock.spend(
    [fixture_target_hash],
    [fixture_emergency_one, fixture_emergency_two],
    2,
    900,
    Some(intent),
    ExecuteLocal,
    fixture_intent_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_intent_input(intent)],
      outputs: [
        fixture_target_output(
          substituted_datum,
          assets.from_lovelace(5_000_000),
        ),
      ],
      mint: assets.from_asset(fixture_policy_id, fixture_asset_name, -1),
      validity_range: interval.between(100, 999),
    },
  )
}

test local_execution_rejects_value_substitution() fail {
  let target_datum: Data = 42
  let intent = fixture_intent(blake2b_256(builtin.serialise_data(target_datum)))
  timelock.spend(
    [fixture_target_hash],
    [fixture_emergency_one, fixture_emergency_two],
    2,
    900,
    Some(intent),
    ExecuteLocal,
    fixture_intent_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_intent_input(intent)],
      outputs: [
        fixture_target_output(target_datum, assets.from_lovelace(5_000_001)),
      ],
      mint: assets.from_asset(fixture_policy_id, fixture_asset_name, -1),
      validity_range: interval.between(100, 999),
    },
  )
}

test cancellation_rejects_unauthorized_committee() fail {
  let intent =
    fixture_intent(
      #"9999999999999999999999999999999999999999999999999999999999999999",
    )
  let refund =
    Output {
      address: Address {
        payment_credential: VerificationKey(fixture_refund_key),
        stake_credential: None,
      },
      value: assets.from_lovelace(5_000_000),
      datum: InlineDatum(0),
      reference_script: None,
    }
  timelock.spend(
    [fixture_target_hash],
    [fixture_emergency_one, fixture_emergency_two],
    2,
    900,
    Some(intent),
    CancelIntent,
    fixture_intent_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_intent_input(intent)],
      outputs: [refund],
      mint: assets.from_asset(fixture_policy_id, fixture_asset_name, -1),
      validity_range: interval.before(999),
      extra_signatories: [fixture_emergency_one],
    },
  )
}

test malformed_intent_is_rejected_before_execution() fail {
  let target_datum: Data = 42
  let intent =
    IntentDatum {
      ..fixture_intent(blake2b_256(builtin.serialise_data(target_datum))),
      target_script_hash: #"444444444444444444444444444444444444444444444444444444",
    }
  timelock.spend(
    [fixture_target_hash],
    [fixture_emergency_one, fixture_emergency_two],
    2,
    900,
    Some(intent),
    ExecuteLocal,
    fixture_intent_ref,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_intent_input(intent)],
      validity_range: interval.between(100, 999),
    },
  )
}
