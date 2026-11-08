use aiken/interval
use cardano/address
use cardano/assets
use cardano/transaction.{
  InlineDatum, Input, Output, OutputReference, Transaction,
}
use f05_authority_policy
use vams/f05_authority.{
  AuthorityActive, AuthorityPendingTransitionV3, AuthorityStateV3,
  BootstrapAuthority, PendingNone,
}

const seed_ref: OutputReference =
  OutputReference {
    transaction_id: #"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    output_index: 7,
  }

const applied_policy_id: assets.PolicyId =
  #"9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731"

const committee: List<ByteArray> =
  [
    #"0f9e7d3242059f40158094de9b9f35491f02af6061212ffa63ea555e09ebd258",
    #"d149658ea1009933d948573e2e447b5e17d031e6a90423a7522c4e449fbe009a",
    #"de8ad1ded00aab5700c0f6b51057b74034b38f4efd1bd78a988ff9f82bc24d84",
    #"ef6d7b49b4e7f1d78156f4f33372253555123d91bc34155b253268fa10c35b95",
    #"f894dc38674c091488082554bd5e5f7f6ed8d85c5fbf894307e3a3f42e505191",
  ]

const proofs: List<ByteArray> =
  [
    #"45a81719485250a378bd9ccf51d6e6ffec75eb4df187879647284f1c17989acc767d84b13e22c73d2b6541f00923c94bd73cafbf8d1e6bfb197808e24047cb0d",
    #"906e971c9fa95d572ac3a503bb6be2e146efe5080964eb78394c4d10db42c89af7bc9c7447f9f9191a11c2fdadd66dde6502dca959cf64ec268ef35fff781705",
    #"c3d8e636f3b8cb0f75e2ee2db43bc6161a8e89ef9a3979c0884e3f723cbe0597d0385359f6b2b6cb5e90b03ebdd9dd7eea2d18508b566557ec05fef2705bf50a",
    #"ceaf461ea6ea3bc9a64657a2115c1b060af5593e30b0cb48ce1272f97b327178c7e9186afbe01c72f82bab2143ab07fa26b483966f93bd707292021f19353603",
    #"fc9f726e7c80136e83fdf5cb5032d5e3ef11226e65e5ff5f13ffaf8f8d1a3e4a95986b27569172f052a641f5b603e2d3881765234fff46028090eb8272e38009",
  ]

const state: AuthorityStateV3 =
  AuthorityStateV3 {
    schema_version: 3,
    bootstrap_tx_hash: seed_ref.transaction_id,
    bootstrap_output_index: 7,
    epoch: 0,
    ordered_keys: committee,
    threshold: 3,
    status: AuthorityActive,
    pending: AuthorityPendingTransitionV3 {
      kind: PendingNone,
      from_epoch: 0,
      to_epoch: 0,
      authorized_at_ms: 0,
      activation_at_ms: 0,
      next_key_count: 0,
      ordered_next_keys: #"00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
    },
  }

const authority_address_hash: ByteArray =
  #"b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66"

const authority_name: ByteArray = #"56414d532d4630352d415554482d5633"

fn seed_input() -> Input {
  Input {
    output_reference: seed_ref,
    output: Output {
      address: address.from_verification_key(
        #"61616161616161616161616161616161616161616161616161616161",
      ),
      value: assets.from_lovelace(2_000_000),
      datum: transaction.NoDatum,
      reference_script: None,
    },
  }
}

fn funding_input() -> Input {
  Input {
    output_reference: OutputReference {
      transaction_id: #"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      output_index: 3,
    },
    output: Output {
      address: address.from_verification_key(
        #"61616161616161616161616161616161616161616161616161616161",
      ),
      value: assets.from_lovelace(15_000_000),
      datum: transaction.NoDatum,
      reference_script: None,
    },
  }
}

fn valid_transaction() -> Transaction {
  let nft = assets.from_asset(applied_policy_id, authority_name, 1)
  let state_output = Output {
    address: address.from_script(authority_address_hash),
    value: assets.merge(assets.from_lovelace(10_000_000), nft),
    datum: InlineDatum(state),
    reference_script: None,
  }
  Transaction {
    ..transaction.placeholder,
    inputs: [seed_input(), funding_input()],
    outputs: [
      state_output,
      Output {
        address: address.from_verification_key(
          #"62626262626262626262626262626262626262626262626262626262",
        ),
        value: assets.from_lovelace(6_000_000),
        datum: InlineDatum(state),
        reference_script: None,
      },
    ],
    fee: 1_000_000,
    mint: nft,
    id: #"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    extra_signatories: [
      #"63636363636363636363636363636363636363636363636363636363",
    ],
    validity_range: interval.between(1_700_000_000_000, 1_700_000_030_000),
  }
}

fn run_policy(tx: Transaction) -> Bool {
  f05_authority_policy.f05_authority_policy.mint(
    seed_ref,
    committee,
    BootstrapAuthority { proofs },
    applied_policy_id,
    tx,
  )
}

test public_applied_policy_fixture_accepts() {
  run_policy(valid_transaction())
}

test public_seed_missing_regression_rejects() fail {
  run_policy(Transaction { ..valid_transaction(), inputs: [funding_input()] })
}
