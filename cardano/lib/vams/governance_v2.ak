//// Authenticated governance v2 primitives. Native compilation is pending.
//// No signature, datum shape or self-declared policy is authority by itself.
use aiken/cbor
use aiken/collection/dict
use aiken/collection/list
use aiken/crypto.{blake2b_256}
use aiken/interval.{Finite}
use aiken/primitive/bytearray
use cardano/address.{Address, Script, VerificationKey}
use cardano/assets
use cardano/transaction.{InlineDatum, Input, NoDatum, Output, OutputReference, Transaction}
use vams/governance.{isqrt}
use vams/governance_v2_types.{
  AuthorityDatumV2, GovernanceAnchorV2, GovernanceBootstrapV2,
  GovernanceConfigV2, IntentDatumV2, PassedV2, PendingV2, ProposalDatumV2,
  VoteLockV2,
}

pub const delay_ms: Int = 172_800_000
pub const lifetime_ms: Int = 604_800_000
pub const voting_duration_ms: Int = 2_592_000_000
pub const interval_width_ms: Int = 300_000
pub const voter_limit: Int = 8
pub const datum_limit: Int = 896
pub const u32_max: Int = 4_294_967_295
pub const u64_max: Int = 18_446_744_073_709_551_615

pub fn uint32(value: Int) -> Bool { value >= 0 && value <= u32_max }
pub fn uint64(value: Int) -> Bool { value >= 0 && value <= u64_max }
pub fn key_hash(value: ByteArray) -> Bool { bytearray.length(value) == 28 }
pub fn digest32(value: ByteArray) -> Bool { bytearray.length(value) == 32 }

pub fn unique(values: List<ByteArray>) -> Bool {
  list.length(values) == list.length(list.unique(values))
}

pub fn joined(parts: List<ByteArray>) -> ByteArray {
  list.foldl(parts, #"", fn(part, acc) { bytearray.concat(acc, part) })
}

pub fn domain_bytes(domain: ByteArray) -> ByteArray {
  joined([bytearray.from_int_big_endian(bytearray.length(domain), 1), domain])
}

pub fn small_datum(raw: Data) -> Bool {
  bytearray.length(cbor.serialise(raw)) <= datum_limit
}

pub fn bootstrap_valid(b: GovernanceBootstrapV2) -> Bool {
  digest32(b.seed.transaction_id) && uint32(b.seed.output_index) && b.network_id >= 0 && b.network_id <= 15 && uint32(b.policy_epoch) && list.length(b.members) == 5 && unique(b.members) && list.all(b.members, key_hash)
}

pub fn config_valid(c: GovernanceConfigV2) -> Bool {
  let ids = [c.authority_policy_id, c.proposal_policy_id, c.receipt_policy_id, c.intent_policy_id, c.vams_policy_id]
  and {
    c.version == 2,
    c.network_id >= 0 && c.network_id <= 15,
    uint32(c.policy_epoch),
    digest32(c.seed.transaction_id) && uint32(c.seed.output_index),
    list.all(ids, key_hash) && unique(ids),
    key_hash(c.governor_script_hash) && key_hash(c.timelock_script_hash),
    unique([c.authority_policy_id, c.governor_script_hash, c.timelock_script_hash]),
    bytearray.length(c.vams_asset_name) <= 32,
    list.length(c.members) == 5 && unique(c.members) && list.all(c.members, key_hash),
    c.threshold == 3,
    c.normal_delay_ms == delay_ms && c.emergency_disabled,
    uint64(c.authority_state_lovelace) && c.authority_state_lovelace > 0,
    uint64(c.proposal_base_lovelace) && c.proposal_base_lovelace > 0,
    uint64(c.per_voter_refund_lovelace) && c.per_voter_refund_lovelace > 0,
    uint64(c.proposal_base_lovelace + voter_limit * c.per_voter_refund_lovelace),
    uint64(c.next_proposal_nonce) && uint64(c.next_intent_nonce),
    c.max_lock_vams > 0 && c.max_lock_vams <= 1_000_000_000,
    list.length(c.target_domains) > 0 && list.length(c.target_domains) <= 4,
    unique(c.target_domains),
    list.all(c.target_domains, fn(d) { bytearray.length(d) > 0 && bytearray.length(d) <= 32 }),
  }
}

pub fn matches_bootstrap(c: GovernanceConfigV2, b: GovernanceBootstrapV2) -> Bool {
  c.seed == b.seed && c.network_id == b.network_id && c.policy_epoch == b.policy_epoch && c.members == b.members
}

pub fn authority_name(c: GovernanceConfigV2) -> ByteArray {
  blake2b_256(joined([
    #"56414d532f617574686f726974792f763200", c.authority_policy_id,
    c.seed.transaction_id, bytearray.from_int_big_endian(c.seed.output_index, 4),
    bytearray.from_int_big_endian(c.network_id, 1), bytearray.from_int_big_endian(c.policy_epoch, 4),
  ]))
}

pub fn proposal_name(c: GovernanceConfigV2, p: ProposalDatumV2) -> ByteArray {
  blake2b_256(joined([
    #"56414d532f70726f706f73616c2f763200", c.authority_policy_id, authority_name(c),
    c.proposal_policy_id, bytearray.from_int_big_endian(p.policy_epoch, 4),
    bytearray.from_int_big_endian(p.nonce, 8), p.proposer_vkh, p.description_hash,
    p.action_hash, p.payload_hash, domain_bytes(p.target_domain),
    bytearray.from_int_big_endian(p.quorum, 8), bytearray.from_int_big_endian(p.deadline, 8),
  ]))
}

pub fn receipt_name(c: GovernanceConfigV2, proposal_asset: ByteArray, lock: VoteLockV2, index: Int) -> ByteArray {
  blake2b_256(joined([
    #"56414d532f726563656970742f763200", c.receipt_policy_id, c.proposal_policy_id,
    proposal_asset, lock.voter_vkh, bytearray.from_int_big_endian(lock.locked_vams, 8),
    if lock.support { #"01" } else { #"00" }, bytearray.from_int_big_endian(index, 4),
  ]))
}

/// Explicit bytes avoid depending on alternate accepted CBOR encodings.
pub fn proposal_commitment(p: ProposalDatumV2) -> ByteArray {
  let locks = list.map(p.locks, fn(lock) {
    joined([lock.voter_vkh, bytearray.from_int_big_endian(lock.locked_vams, 8),
      if lock.support { #"01" } else { #"00" },
      bytearray.from_int_big_endian(lock.weight, 8), lock.receipt_name])
  })
  blake2b_256(joined(list.concat([
    #"56414d532f70726f706f73616c2d73746174652f763200", p.proposal_asset,
    if p.state == PassedV2 { #"01" } else { #"00" },
    bytearray.from_int_big_endian(p.yes_weight, 8), bytearray.from_int_big_endian(p.no_weight, 8),
    bytearray.from_int_big_endian(list.length(p.locks), 1),
  ], locks)))
}

pub fn intent_name(c: GovernanceConfigV2, i: IntentDatumV2) -> ByteArray {
  blake2b_256(joined([
    #"56414d532f696e74656e742f763200", c.intent_policy_id, c.proposal_policy_id,
    i.proposal_asset, i.proposal_id, i.action_hash, i.payload_hash, domain_bytes(i.target_domain),
    bytearray.from_int_big_endian(i.policy_epoch, 4), bytearray.from_int_big_endian(i.nonce, 8),
    bytearray.from_int_big_endian(i.queue_time, 8), i.proposer_vkh,
  ]))
}

/// All input references use the frozen32byte transaction ID/u32 index boundary.
pub fn output_reference_valid(reference: OutputReference) -> Bool {
  digest32(reference.transaction_id) && uint32(reference.output_index)
}

pub fn envelope(tx: Transaction) -> Bool {
  and {
    list.length(tx.inputs) > 0 && list.length(tx.inputs) <= 16,
    list.length(tx.reference_inputs) <= 1,
    list.all(tx.inputs, fn(input) { output_reference_valid(input.output_reference) }),
    list.all(tx.reference_inputs, fn(input) { output_reference_valid(input.output_reference) }),
    list.length(tx.outputs) > 0 && list.length(tx.outputs) <= 16,
    list.length(tx.extra_signatories) <= 5 && unique(tx.extra_signatories),
    list.all(tx.extra_signatories, key_hash),
    uint64(tx.fee),
    list.length(tx.redeemers) <= 8,
    tx.certificates == [] && tx.withdrawals == [],
    tx.votes == [] && tx.proposal_procedures == [],
    tx.current_treasury_amount == None && tx.treasury_donation == None,
    tx.datums == dict.empty,
    list.length(assets.flatten(tx.mint)) <= 16,
    list.all(tx.outputs, fn(output) {
      output.reference_script == None && list.length(assets.flatten(output.value)) <= 16 && when output.datum is {
        InlineDatum(raw) -> small_datum(raw)
        NoDatum -> True
        _ -> False
      }
    }),
    when (tx.validity_range.lower_bound.bound_type, tx.validity_range.upper_bound.bound_type) is {
      (Finite(lower), Finite(upper)) -> uint64(lower) && uint64(upper) && upper > lower && upper - lower <= interval_width_ms
        && tx.validity_range.lower_bound.is_inclusive && !tx.validity_range.upper_bound.is_inclusive
      _ -> False
    },
  }
}

/// Lower bound for conditions that must hold throughout the inclusion window.
pub fn now_ms(tx: Transaction) -> Int {
  expect Finite(value) = tx.validity_range.lower_bound.bound_type
  value
}

/// Conservative Queue anchor: every permitted inclusion precedes this bound.
/// Call only after envelope has validated the nonempty [lower, upper) range.
pub fn upper_ms(tx: Transaction) -> Int {
  expect Finite(value) = tx.validity_range.upper_bound.bound_type
  value
}

pub fn before_ms(tx: Transaction, deadline: Int) -> Bool {
  expect Finite(upper) = tx.validity_range.upper_bound.bound_type
  now_ms(tx) < deadline && upper <= deadline
}

pub fn threshold(c: GovernanceConfigV2, tx: Transaction) -> Bool {
  list.length(list.filter(c.members, fn(member) { list.has(tx.extra_signatories, member) })) >= 3
}

pub fn script_address(hash: ByteArray) -> Address {
  Address { payment_credential: Script(hash), stake_credential: None }
}

pub fn key_address(hash: ByteArray) -> Address {
  Address { payment_credential: VerificationKey(hash), stake_credential: None }
}

pub fn inline_output(address: Address, value: assets.Value, datum: Data) -> Output {
  Output { address, value, datum: InlineDatum(datum), reference_script: None }
}

pub fn payment_output(address: Address, value: assets.Value) -> Output {
  Output { address, value, datum: NoDatum, reference_script: None }
}

pub fn authority_value(c: GovernanceConfigV2) -> assets.Value {
  assets.from_lovelace(c.authority_state_lovelace)
    |> assets.add(c.authority_policy_id, authority_name(c), 1)
}

pub fn read_authority(anchor: GovernanceAnchorV2, tx: Transaction, consumed: Bool) -> (Input, GovernanceConfigV2) {
  expect key_hash(anchor.policy_id) && digest32(anchor.asset_name)
  expect if consumed { tx.reference_inputs == [] } else { list.length(tx.reference_inputs) == 1 }
  let candidates = if consumed { tx.inputs } else { tx.reference_inputs }
  expect [input] = list.filter(candidates, fn(input) {
    assets.quantity_of(input.output.value, anchor.policy_id, anchor.asset_name) != 0
  })
  expect input.output.address == script_address(anchor.policy_id)
  expect input.output.reference_script == None
  expect InlineDatum(raw) = input.output.datum
  expect small_datum(raw)
  expect authority: AuthorityDatumV2 = raw
  let c = authority.config
  expect config_valid(c)
  expect c.authority_policy_id == anchor.policy_id && authority_name(c) == anchor.asset_name
  expect input.output.value == authority_value(c)
  (input, c)
}

pub fn proposal_valid(c: GovernanceConfigV2, p: ProposalDatumV2) -> Bool {
  expect list.length(p.locks) <= voter_limit
  let locks_valid = list.all(list.indexed_map(p.locks, fn(index, lock) {
    key_hash(lock.voter_vkh) && lock.locked_vams > 0 && lock.locked_vams <= c.max_lock_vams && lock.weight == isqrt(lock.locked_vams) && lock.receipt_name == receipt_name(c, p.proposal_asset, lock, index)
  }), fn(valid) { valid })
  and {
    p.version == 2 && uint64(p.nonce), key_hash(p.proposer_vkh),
    digest32(p.description_hash) && digest32(p.action_hash) && digest32(p.payload_hash),
    list.has(c.target_domains, p.target_domain), p.policy_epoch == c.policy_epoch,
    p.quorum > 0 && p.quorum <= voter_limit * isqrt(c.max_lock_vams), uint64(p.deadline),
    list.length(p.locks) <= voter_limit,
    unique(list.map(p.locks, fn(lock) { lock.voter_vkh })),
    unique(list.map(p.locks, fn(lock) { lock.receipt_name })),
    locks_valid,
    p.yes_weight == list.foldl(p.locks, 0, fn(lock, sum) { sum + if lock.support { lock.weight } else { 0 } }),
    p.no_weight == list.foldl(p.locks, 0, fn(lock, sum) { sum + if lock.support { 0 } else { lock.weight } }),
    p.proposal_asset == proposal_name(c, p),
    when p.state is {
      PendingV2 -> True
      PassedV2 -> p.yes_weight + p.no_weight >= p.quorum && p.yes_weight > p.no_weight
    },
  }
}

pub fn proposal_value(c: GovernanceConfigV2, p: ProposalDatumV2) -> assets.Value {
  let total = list.foldl(p.locks, 0, fn(lock, sum) { sum + lock.locked_vams })
  let base = assets.from_lovelace(c.proposal_base_lovelace + list.length(p.locks) * c.per_voter_refund_lovelace)
    |> assets.add(c.proposal_policy_id, p.proposal_asset, 1)
    |> assets.add(c.vams_policy_id, c.vams_asset_name, total)
  list.foldl(p.locks, base, fn(lock, value) { assets.add(value, c.receipt_policy_id, lock.receipt_name, 1) })
}

pub fn read_proposal(c: GovernanceConfigV2, tx: Transaction) -> (Input, ProposalDatumV2) {
  expect [input] = list.filter(tx.inputs, fn(input) { input.output.address == script_address(c.governor_script_hash) })
  expect input.output.reference_script == None
  expect InlineDatum(raw) = input.output.datum
  expect small_datum(raw)
  expect p: ProposalDatumV2 = raw
  expect list.length(p.locks) <= voter_limit
  expect proposal_valid(c, p) && p.nonce < c.next_proposal_nonce
  expect input.output.value == proposal_value(c, p)
  (input, p)
}

pub fn receipt_burns(c: GovernanceConfigV2, p: ProposalDatumV2) -> assets.Value {
  list.foldl(p.locks, assets.from_asset(c.proposal_policy_id, p.proposal_asset, -1), fn(lock, value) {
    assets.add(value, c.receipt_policy_id, lock.receipt_name, -1)
  })
}

pub fn voter_refunds(c: GovernanceConfigV2, p: ProposalDatumV2) -> List<Output> {
  list.map(p.locks, fn(lock) {
    payment_output(key_address(lock.voter_vkh), assets.from_lovelace(c.per_voter_refund_lovelace)
      |> assets.add(c.vams_policy_id, c.vams_asset_name, lock.locked_vams))
  })
}

/// Ordered protocol outputs prevent one payment satisfying two obligations.
/// The sole funding input pays all fees. A vote explicitly permits VAMS here;
/// every other action requires ADA-only funding. No governed value pays a fee.
pub fn funded_outputs(c: GovernanceConfigV2, tx: Transaction, governed: List<Input>, expected: List<Output>, lovelace: Int, vams: Int, voter: Option<ByteArray>) -> Bool {
  expect lovelace >= 0 && vams >= 0
  expect list.length(tx.inputs) == list.length(governed) + 1
  let governed_refs = list.map(governed, fn(input) { input.output_reference })
  expect list.length(list.unique(governed_refs)) == list.length(governed_refs)
  expect [funding] = list.filter(tx.inputs, fn(input) { !list.has(governed_refs, input.output_reference) })
  expect VerificationKey(funder) = funding.output.address.payment_credential
  expect list.has(tx.extra_signatories, funder)
  expect funding.output.datum == NoDatum && funding.output.reference_script == None
  let available_lovelace = assets.lovelace_of(funding.output.value)
  let available_vams = assets.quantity_of(funding.output.value, c.vams_policy_id, c.vams_asset_name)
  expect when voter is {
    Some(vkh) -> vkh == funder && funding.output.value == (assets.from_lovelace(available_lovelace) |> assets.add(c.vams_policy_id, c.vams_asset_name, available_vams))
    None -> available_vams == 0 && funding.output.value == assets.from_lovelace(available_lovelace)
  }
  expect available_lovelace >= lovelace + tx.fee && available_vams >= vams
  let change_lovelace = available_lovelace - lovelace - tx.fee
  let change_vams = available_vams - vams
  if change_lovelace == 0 && change_vams == 0 {
    tx.outputs == expected
  } else {
    expect change_lovelace > 0
    let change = payment_output(funding.output.address, assets.from_lovelace(change_lovelace)
      |> assets.add(c.vams_policy_id, c.vams_asset_name, change_vams))
    tx.outputs == list.concat(expected, [change])
  }
}
