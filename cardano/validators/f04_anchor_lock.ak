//// F04 fixed, unspendable anchor lock S0.
//// No parameters or escape path are permitted in this script.

use cardano/transaction.{OutputReference, Transaction}

validator f04_anchor_lock() {
  spend(
    _datum_opt: Option<Data>,
    _redeemer: Data,
    _own_ref: OutputReference,
    _tx: Transaction,
  ) {
    False
  }

  else(_) {
    fail
  }
}
