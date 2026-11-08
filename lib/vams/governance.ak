use aiken/collection/list
use aiken/crypto.{blake2b_256}
use aiken/interval.{Finite}
use aiken/primitive/bytearray
use cardano/address.{Script}
use cardano/assets
use cardano/transaction.{
  InlineDatum, Input, Output, OutputReference, Transaction,
}
use vams/types.{
  GovernanceConfigV1, IntentDatumV1, ProposalDatumV1, VoteLockRecordV1,
}

pub const max_voters: Int = 8

pub const max_members: Int = 5

pub const authority_threshold: Int = 3

pub const max_inputs: Int = 16

pub const max_outputs: Int = 16

pub const max_signers: Int = 5

pub const max_validity_width_ms: Int = 300_000

pub const max_voting_duration_ms: Int = 2_592_000_000

pub const normal_delay_ms: Int = 86_400_000

pub const max_intent_lifetime_ms: Int = 604_800_000

pub const max_datum_bytes: Int = 896

pub fn bounded_tx(tx: Transaction) -> Bool {
  list.length(tx.inputs) <= max_inputs && list.length(tx.outputs) <= max_outputs && list.length(
    tx.extra_signatories,
  ) <= max_signers && unique_bytes(tx.extra_signatories)
}

pub fn finite_interval(tx: Transaction) -> Bool {
  when
    (
      tx.validity_range.lower_bound.bound_type,
      tx.validity_range.upper_bound.bound_type,
    )
  is {
    (Finite(lower), Finite(upper)) ->
      upper >= lower && upper - lower <= max_validity_width_ms
    _ -> False
  }
}

pub fn finite_before(tx: Transaction, deadline: Int) -> Bool {
  when
    (
      tx.validity_range.lower_bound.bound_type,
      tx.validity_range.upper_bound.bound_type,
    )
  is {
    (Finite(lower), Finite(upper)) ->
      upper >= lower && lower < deadline && upper <= deadline
    _ -> False
  }
}

pub fn finite_after(tx: Transaction, deadline: Int) -> Bool {
  when
    (
      tx.validity_range.lower_bound.bound_type,
      tx.validity_range.upper_bound.bound_type,
    )
  is {
    (Finite(lower), Finite(upper)) -> upper >= lower && lower >= deadline
    _ -> False
  }
}

pub fn current_time(tx: Transaction) -> Option<Int> {
  when tx.validity_range.lower_bound.bound_type is {
    Finite(value) -> Some(value)
    _ -> None
  }
}

pub fn unique_bytes(values: List<ByteArray>) -> Bool {
  list.length(values) == list.length(list.unique(values))
}

pub fn valid_vkh(vkh: ByteArray) -> Bool {
  bytearray.length(vkh) == 28
}

pub fn valid_hash(value: ByteArray) -> Bool {
  bytearray.length(value) == 32
}

pub fn valid_domain(value: ByteArray) -> Bool {
  bytearray.length(value) <= 32
}

pub fn config_valid(c: GovernanceConfigV1) -> Bool {
  c.version == 1 && c.network_id >= 0 && c.network_id <= 15 && c.authority_state_lovelace > 0 && c.proposal_base_lovelace > 0 && c.per_voter_refund_lovelace > 0 && c.policy_epoch >= 0 && bytearray.length(
    c.authority_policy_id,
  ) == 28 && bytearray.length(c.governor_script_hash) == 28 && bytearray.length(
    c.timelock_script_hash,
  ) == 28 && list.length(c.members) <= max_members && list.length(c.members) == max_members && unique_bytes(
    c.members,
  ) && list.all(c.members, valid_vkh) && c.threshold == authority_threshold && c.normal_delay_ms == normal_delay_ms && c.emergency_disabled && c.next_proposal_nonce >= 0 && c.next_intent_nonce >= 0 && c.max_lock_vams > 0 && list.length(
    c.caps,
  ) == 5 && c.caps == [
    max_voters, max_inputs, max_outputs, max_inputs, max_datum_bytes,
  ] && list.length(c.target_domains) > 0 && list.all(
    c.target_domains,
    valid_domain,
  )
}

pub fn authority_asset_name(config: GovernanceConfigV1) -> ByteArray {
  blake2b_256(
    bytearray.concat(
      #"56414d532f617574686f726974792f763100",
      bytearray.concat(
        config.authority_policy_id,
        bytearray.concat(
          config.seed.transaction_id,
          bytearray.concat(
            bytearray.from_int_big_endian(config.seed.output_index, 4),
            bytearray.concat(
              bytearray.from_int_big_endian(config.network_id, 1),
              bytearray.from_int_big_endian(config.policy_epoch, 4),
            ),
          ),
        ),
      ),
    ),
  )
}

pub fn proposal_asset_name(
  config: GovernanceConfigV1,
  proposer: ByteArray,
  action: ByteArray,
  domain: ByteArray,
  nonce: Int,
) -> ByteArray {
  blake2b_256(
    bytearray.concat(
      #"56414d532f70726f706f73616c2f763100",
      bytearray.concat(
        config.authority_policy_id,
        bytearray.concat(
          authority_asset_name(config),
          bytearray.concat(
            bytearray.from_int_big_endian(nonce, 8),
            bytearray.concat(
              proposer,
              bytearray.concat(
                action,
                bytearray.push(domain, bytearray.length(domain)),
              ),
            ),
          ),
        ),
      ),
    ),
  )
}

pub fn receipt_asset_name(
  receipt_policy: ByteArray,
  proposal_policy: ByteArray,
  proposal_asset: ByteArray,
  voter: ByteArray,
  locked: Int,
  support: Bool,
  index: Int,
) -> ByteArray {
  bytearray.slice(
    blake2b_256(
      bytearray.concat(
        #"56414d532f726563656970742f763100",
        bytearray.concat(
          receipt_policy,
          bytearray.concat(
            proposal_policy,
            bytearray.concat(
              proposal_asset,
              bytearray.concat(
                voter,
                bytearray.concat(
                  bytearray.from_int_big_endian(locked, 8),
                  bytearray.concat(
                    if support {
                      #"01"
                    } else {
                      #"00"
                    },
                    bytearray.from_int_big_endian(index, 4),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    ),
    0,
    31,
  )
}

pub fn intent_asset_name(
  intent_policy: ByteArray,
  proposal_policy: ByteArray,
  proposal_asset: ByteArray,
  proposer: ByteArray,
  queue_time: Int,
  action: ByteArray,
) -> ByteArray {
  bytearray.slice(
    blake2b_256(
      bytearray.concat(
        #"56414d532f696e74656e742f763100",
        bytearray.concat(
          intent_policy,
          bytearray.concat(
            proposal_policy,
            bytearray.concat(
              proposal_asset,
              bytearray.concat(
                proposer,
                bytearray.concat(
                  bytearray.from_int_big_endian(queue_time, 8),
                  action,
                ),
              ),
            ),
          ),
        ),
      ),
    ),
    0,
    31,
  )
}

pub fn signer_threshold(
  signers: List<ByteArray>,
  members: List<ByteArray>,
  threshold: Int,
) -> Bool {
  unique_bytes(signers) && list.length(signers) <= max_signers && list.length(
    list.filter(members, fn(member) { list.has(signers, member) }),
  ) >= threshold
}

pub fn proposal_immutable(
  before: ProposalDatumV1,
  after: ProposalDatumV1,
) -> Bool {
  before.version == after.version && before.proposal_asset == after.proposal_asset && before.nonce == after.nonce && before.proposer_vkh == after.proposer_vkh && before.description_hash == after.description_hash && before.action_hash == after.action_hash && before.target_domain == after.target_domain && before.policy_epoch == after.policy_epoch && before.quorum == after.quorum && before.deadline == after.deadline
}

pub fn intent_immutable(before: IntentDatumV1, after: IntentDatumV1) -> Bool {
  before.version == after.version && before.proposal_id == after.proposal_id && before.proposal_asset == after.proposal_asset && before.action_hash == after.action_hash && before.payload_hash == after.payload_hash && before.target_domain == after.target_domain && before.policy_epoch == after.policy_epoch && before.nonce == after.nonce && before.queue_time == after.queue_time && before.execute_after == after.execute_after && before.lifetime == after.lifetime && before.proposer_vkh == after.proposer_vkh && before.consumed == after.consumed
}

pub fn valid_lock(lock: VoteLockRecordV1) -> Bool {
  valid_vkh(lock.voter_vkh) && lock.locked_vams > 0 && lock.weight == isqrt(
    lock.locked_vams,
  ) && lock.weight > 0 && bytearray.length(lock.receipt_name) == 32
}

pub fn isqrt(n: Int) -> Int {
  if n <= 0 {
    0
  } else if n == 1 {
    1
  } else {
    sqrt_iter(n, n / 2)
  }
}

fn sqrt_iter(n: Int, guess: Int) -> Int {
  let next = ( guess + n / guess ) / 2
  if next >= guess {
    guess
  } else {
    sqrt_iter(n, next)
  }
}

pub fn proposal_output(outputs: List<Output>) -> Option<ProposalDatumV1> {
  when list.find(outputs, fn(_output) { True }) is {
    Some(output) ->
      when output.datum is {
        InlineDatum(raw) -> {
          expect datum: ProposalDatumV1 = raw
          Some(datum)
        }
        _ -> None
      }
    None -> None
  }
}

pub fn has_asset(
  input: Input,
  policy: ByteArray,
  name: ByteArray,
  quantity: Int,
) -> Bool {
  when input.output.address.payment_credential is {
    Script(hash) ->
      assets.quantity_of(input.output.value, hash, name) == quantity && hash == policy
    _ -> False
  }
}

pub fn output_has_asset(
  output: Output,
  policy: ByteArray,
  name: ByteArray,
  quantity: Int,
) -> Bool {
  assets.quantity_of(output.value, policy, name) == quantity
}
