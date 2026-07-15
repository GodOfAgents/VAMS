//// VAMS canonical insurance-fund authentication policy.
////
//// This bootstrap policy mints exactly one fixed authentication asset and has
//// no burn path. The initial output must contain the schema-v2 fund datum.

use aiken/builtin
use aiken/collection/dict
use aiken/collection/list
use aiken/primitive/bytearray
use cardano/address.{Address, Script}
use cardano/assets.{PolicyId, lovelace_of, quantity_of, tokens}
use cardano/transaction.{
  InlineDatum, Input, NoDatum, Output, OutputReference, Transaction,
}
use vams/types.{FundDatum, FundState, InsuranceDatum, cardano_schema_version}

const fund_asset_name: ByteArray = "VAMS_FUND_V2"

validator fund_nft(
  bootstrap_ref: OutputReference,
  insurance_script_hash: ByteArray,
  guardians: List<ByteArray>,
  approval_threshold: Int,
  max_payout_bps: Int,
) {
  mint(_redeemer: Data, policy_id: PolicyId, tx: Transaction) {
    expect
      list.any(tx.inputs, fn(input) { input.output_reference == bootstrap_ref })
    expect
      dict.to_pairs(tokens(tx.mint, policy_id)) == [Pair(fund_asset_name, 1)]
    let matches =
      list.filter(
        tx.outputs,
        fn(output) {
          when output.address.payment_credential is {
            Script(hash) ->
              if hash != insurance_script_hash || quantity_of(
                output.value,
                policy_id,
                fund_asset_name,
              ) != 1 {
                False
              } else {
                when output.datum is {
                  InlineDatum(raw) -> {
                    expect datum: InsuranceDatum = raw
                    when datum is {
                      FundState(fund) -> and {
                          fund.schema_version == cardano_schema_version,
                          fund.fund_policy_id == policy_id,
                          fund.fund_asset_name == fund_asset_name,
                          fund.total_balance == lovelace_of(output.value),
                          fund.total_balance > 0,
                          fund.next_claim_id == 1,
                          list.is_empty(fund.pending_claim_commitments),
                          fund.max_payout_bps == max_payout_bps,
                          fund.max_payout_bps > 0,
                          fund.max_payout_bps <= 5_000,
                          fund.approval_threshold == approval_threshold,
                          approval_threshold >= 2,
                          approval_threshold <= list.length(guardians),
                          fund.guardians == guardians,
                        }
                      _ -> False
                    }
                  }
                  _ -> False
                }
              }
            _ -> False
          }
        },
      )
    list.length(matches) == 1
  }

  else(_) {
    fail
  }
}

test fund_asset_name_is_bounded() {
  bytearray.length(fund_asset_name) <= 32
}

const fixture_bootstrap_ref: OutputReference =
  OutputReference {
    transaction_id: #"0101010101010101010101010101010101010101010101010101010101010101",
    output_index: 0,
  }

const fixture_insurance_hash: ByteArray =
  #"02020202020202020202020202020202020202020202020202020202"

const fixture_policy_id: PolicyId =
  #"03030303030303030303030303030303030303030303030303030303"

const fixture_guardian_one: ByteArray =
  #"04040404040404040404040404040404040404040404040404040404"

const fixture_guardian_two: ByteArray =
  #"05050505050505050505050505050505050505050505050505050505"

fn fixture_bootstrap_input() -> Input {
  Input {
    output_reference: fixture_bootstrap_ref,
    output: Output {
      address: Address {
        payment_credential: Script(fixture_insurance_hash),
        stake_credential: None,
      },
      value: assets.from_lovelace(2_000_000),
      datum: NoDatum,
      reference_script: None,
    },
  }
}

fn fixture_fund_output() -> Output {
  let total_balance = 100_000_000
  let datum =
    FundDatum {
      schema_version: cardano_schema_version,
      fund_policy_id: fixture_policy_id,
      fund_asset_name,
      total_balance,
      next_claim_id: 1,
      pending_claim_commitments: [],
      max_payout_bps: 5_000,
      approval_threshold: 2,
      guardians: [fixture_guardian_one, fixture_guardian_two],
    }
  Output {
    address: Address {
      payment_credential: Script(fixture_insurance_hash),
      stake_credential: None,
    },
    value: assets.from_lovelace(total_balance)
      |> assets.add(fixture_policy_id, fund_asset_name, 1),
    datum: InlineDatum(FundState(datum)),
    reference_script: None,
  }
}

test bootstrap_creates_one_exact_canonical_fund() {
  fund_nft.mint(
    fixture_bootstrap_ref,
    fixture_insurance_hash,
    [fixture_guardian_one, fixture_guardian_two],
    2,
    5_000,
    builtin.i_data(0),
    fixture_policy_id,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_bootstrap_input()],
      outputs: [fixture_fund_output()],
      mint: assets.from_asset(fixture_policy_id, fund_asset_name, 1),
    },
  )
}

test bootstrap_rejects_duplicate_canonical_fund_outputs() fail {
  let output = fixture_fund_output()
  fund_nft.mint(
    fixture_bootstrap_ref,
    fixture_insurance_hash,
    [fixture_guardian_one, fixture_guardian_two],
    2,
    5_000,
    builtin.i_data(0),
    fixture_policy_id,
    Transaction {
      ..transaction.placeholder,
      inputs: [fixture_bootstrap_input()],
      outputs: [output, output],
      mint: assets.from_asset(fixture_policy_id, fund_asset_name, 1),
    },
  )
}
