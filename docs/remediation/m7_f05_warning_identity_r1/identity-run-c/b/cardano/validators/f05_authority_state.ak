//// F05.2a authority state validator.
////
//// Transitions are deliberately disabled in this bootstrap-only slice. Future
//// authority transitions require a separately reviewed implementation.

use cardano/transaction.{OutputReference, Transaction}
use vams/f05_authority.{AuthoritySpendRedeemer, AuthorityStateV3}

validator f05_authority_state() {
  spend(
    _datum_opt: Option<AuthorityStateV3>,
    _redeemer: AuthoritySpendRedeemer,
    _own_ref: OutputReference,
    _tx: Transaction,
  ) {
    False
  }

  else(_) {
    fail
  }
}
