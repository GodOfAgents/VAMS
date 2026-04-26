//// VAMS Agent Identity NFT Minting Policy
////
//// Mints exactly one identity NFT to be used natively within the Agent Registry.
//// Ensures global uniqueness by requiring a specific UTXO output reference
//// to be consumed during the transaction (One-Shot Minting).

use aiken/collection/dict
use aiken/collection/list
use cardano/assets.{PolicyId, tokens}
use cardano/transaction.{OutputReference, Transaction}

/// Minting policy for VAMS Agent NFTs.
/// Requires a specific output reference (UTXO) to be consumed to ensure uniqueness.
validator agent_nft(utxo_ref: OutputReference) {
  mint(_redeemer: Data, policy_id: PolicyId, tx: Transaction) {
    // Extract tokens minted under this policy
    let policy_tokens = tokens(tx.mint, policy_id)
    // Verify exactly 1 asset class is affected
    when dict.to_pairs(policy_tokens) is {
      [Pair(_asset_name, amount)] ->
        // Minting Branch: Must mint exactly 1 token and consume the utxo_ref
        if amount == 1 {
          let has_expected_input =
            list.any(
              tx.inputs,
              fn(input) { input.output_reference == utxo_ref },
            )
          has_expected_input
        } else if // Burning Branch: Can burn 1 token (deregistration) without utxo_ref
        amount == -1 {
          True
        } else {
          // Invalid quantity
          False
        }
      _ -> False
    }
    // More than one asset class involved or none
  }

  else(_) {
    fail
  }
}
