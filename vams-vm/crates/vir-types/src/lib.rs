//! Consensus-facing VIR-Core types.
//!
//! Constructors enforce consensus bounds and authority bindings. Wire encoding
//! lives in `vir-codec` so this crate remains dependency-free.

use std::num::NonZeroU64;

pub const SCHEMA_VERSION: u16 = 1;
pub const MAX_OBJECT_ACCESSES: usize = 64;

#[derive(Clone, Copy, Debug, Default, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct Hash32([u8; 32]);

impl Hash32 {
    pub const ZERO: Self = Self([0_u8; 32]);

    #[must_use]
    pub const fn new(bytes: [u8; 32]) -> Self {
        Self(bytes)
    }

    #[must_use]
    pub const fn as_bytes(&self) -> &[u8; 32] {
        &self.0
    }

    #[must_use]
    pub fn is_zero(self) -> bool {
        self == Self::ZERO
    }
}

impl From<[u8; 32]> for Hash32 {
    fn from(value: [u8; 32]) -> Self {
        Self::new(value)
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum HostAuthority {
    PolygonAmoy = 0,
    CardanoPreProd = 1,
}

impl HostAuthority {
    #[must_use]
    pub const fn as_u8(self) -> u8 {
        self as u8
    }
}

impl TryFrom<u8> for HostAuthority {
    type Error = FailureCode;

    fn try_from(value: u8) -> Result<Self, Self::Error> {
        match value {
            0 => Ok(Self::PolygonAmoy),
            1 => Ok(Self::CardanoPreProd),
            _ => Err(FailureCode::UnsupportedHostAuthority),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum AccessMode {
    Read = 0,
    Consume = 1,
    Reserve = 2,
    Accumulate = 3,
}

impl AccessMode {
    #[must_use]
    pub const fn as_u8(self) -> u8 {
        self as u8
    }

    #[must_use]
    pub const fn is_mutating(self) -> bool {
        !matches!(self, Self::Read)
    }
}

impl TryFrom<u8> for AccessMode {
    type Error = FailureCode;

    fn try_from(value: u8) -> Result<Self, Self::Error> {
        match value {
            0 => Ok(Self::Read),
            1 => Ok(Self::Consume),
            2 => Ok(Self::Reserve),
            3 => Ok(Self::Accumulate),
            _ => Err(FailureCode::AccessDenied),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum SignatureSuite {
    Secp256k1 = 1,
    Secp256k1Mldsa65 = 2,
}

impl SignatureSuite {
    #[must_use]
    pub const fn as_u8(self) -> u8 {
        self as u8
    }
}

impl TryFrom<u8> for SignatureSuite {
    type Error = FailureCode;

    fn try_from(value: u8) -> Result<Self, Self::Error> {
        match value {
            1 => Ok(Self::Secp256k1),
            2 => Ok(Self::Secp256k1Mldsa65),
            _ => Err(FailureCode::InvalidSignatureSuite),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum ExecutionTier {
    Tier0 = 0,
    Tier1 = 1,
    Tier2 = 2,
}

impl ExecutionTier {
    #[must_use]
    pub const fn as_u8(self) -> u8 {
        self as u8
    }
}

impl TryFrom<u8> for ExecutionTier {
    type Error = FailureCode;

    fn try_from(value: u8) -> Result<Self, Self::Error> {
        match value {
            0 => Ok(Self::Tier0),
            1 => Ok(Self::Tier1),
            2 => Ok(Self::Tier2),
            _ => Err(FailureCode::InvalidExecutionTier),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u16)]
pub enum FailureCode {
    InvalidSchema = 1,
    MalformedEncoding = 2,
    NonCanonicalEncoding = 3,
    BoundsExceeded = 4,
    UnsupportedOpcode = 5,
    ArithmeticOverflow = 6,
    ArithmeticUnderflow = 7,
    DivisionByZero = 8,
    StackUnderflow = 9,
    StackOverflow = 10,
    InvalidProgram = 11,
    HostAuthorityMismatch = 12,
    StateDomainMismatch = 13,
    StaleObjectVersion = 14,
    AccessDenied = 15,
    FencingTokenRequired = 16,
    InvalidFencingToken = 17,
    OutOfGas = 18,
    UnsupportedProver = 19,
    UnconfiguredProver = 20,
    ReceiptMismatch = 21,
    IntentExpired = 22,
    NonCanonicalObjectOrder = 23,
    DuplicateObject = 24,
    ProgramIdMismatch = 25,
    InputCommitmentMismatch = 26,
    AuthorityEpochMismatch = 27,
    ObjectSetMismatch = 28,
    UnsupportedVersion = 29,
    TrailingData = 30,
    InvalidOutcome = 31,
    MissingHalt = 32,
    TrailingInstructionData = 33,
    InputOutOfBounds = 34,
    StackNotSingleton = 35,
    UnsupportedHostAuthority = 36,
    InvalidSignatureSuite = 37,
    InvalidExecutionTier = 38,
    TierSignatureMismatch = 39,
    ExecutionUnitLimitExceeded = 40,
    OutputCommitmentMismatch = 41,
    InvalidExecutionLimit = 42,
    UnsupportedPolicyCommitment = 43,
    InvalidSettlementMetadata = 44,
}

impl FailureCode {
    #[must_use]
    pub const fn as_u16(self) -> u16 {
        self as u16
    }
}

impl TryFrom<u16> for FailureCode {
    type Error = FailureCode;

    fn try_from(value: u16) -> Result<Self, Self::Error> {
        match value {
            1 => Ok(Self::InvalidSchema),
            2 => Ok(Self::MalformedEncoding),
            3 => Ok(Self::NonCanonicalEncoding),
            4 => Ok(Self::BoundsExceeded),
            5 => Ok(Self::UnsupportedOpcode),
            6 => Ok(Self::ArithmeticOverflow),
            7 => Ok(Self::ArithmeticUnderflow),
            8 => Ok(Self::DivisionByZero),
            9 => Ok(Self::StackUnderflow),
            10 => Ok(Self::StackOverflow),
            11 => Ok(Self::InvalidProgram),
            12 => Ok(Self::HostAuthorityMismatch),
            13 => Ok(Self::StateDomainMismatch),
            14 => Ok(Self::StaleObjectVersion),
            15 => Ok(Self::AccessDenied),
            16 => Ok(Self::FencingTokenRequired),
            17 => Ok(Self::InvalidFencingToken),
            18 => Ok(Self::OutOfGas),
            19 => Ok(Self::UnsupportedProver),
            20 => Ok(Self::UnconfiguredProver),
            21 => Ok(Self::ReceiptMismatch),
            22 => Ok(Self::IntentExpired),
            23 => Ok(Self::NonCanonicalObjectOrder),
            24 => Ok(Self::DuplicateObject),
            25 => Ok(Self::ProgramIdMismatch),
            26 => Ok(Self::InputCommitmentMismatch),
            27 => Ok(Self::AuthorityEpochMismatch),
            28 => Ok(Self::ObjectSetMismatch),
            29 => Ok(Self::UnsupportedVersion),
            30 => Ok(Self::TrailingData),
            31 => Ok(Self::InvalidOutcome),
            32 => Ok(Self::MissingHalt),
            33 => Ok(Self::TrailingInstructionData),
            34 => Ok(Self::InputOutOfBounds),
            35 => Ok(Self::StackNotSingleton),
            36 => Ok(Self::UnsupportedHostAuthority),
            37 => Ok(Self::InvalidSignatureSuite),
            38 => Ok(Self::InvalidExecutionTier),
            39 => Ok(Self::TierSignatureMismatch),
            40 => Ok(Self::ExecutionUnitLimitExceeded),
            41 => Ok(Self::OutputCommitmentMismatch),
            42 => Ok(Self::InvalidExecutionLimit),
            43 => Ok(Self::UnsupportedPolicyCommitment),
            44 => Ok(Self::InvalidSettlementMetadata),
            _ => Err(Self::InvalidOutcome),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct DomainAuthorityBinding {
    state_domain: Hash32,
    host_authority: HostAuthority,
    authority_epoch: u64,
}

impl DomainAuthorityBinding {
    #[must_use]
    pub const fn new(
        state_domain: Hash32,
        host_authority: HostAuthority,
        authority_epoch: u64,
    ) -> Self {
        Self {
            state_domain,
            host_authority,
            authority_epoch,
        }
    }

    #[must_use]
    pub const fn state_domain(&self) -> Hash32 {
        self.state_domain
    }

    #[must_use]
    pub const fn host_authority(&self) -> HostAuthority {
        self.host_authority
    }

    #[must_use]
    pub const fn authority_epoch(&self) -> u64 {
        self.authority_epoch
    }

    pub fn validate(&self, candidate: &Self) -> Result<(), FailureCode> {
        if self.state_domain != candidate.state_domain {
            return Err(FailureCode::StateDomainMismatch);
        }
        if self.host_authority != candidate.host_authority {
            return Err(FailureCode::HostAuthorityMismatch);
        }
        if self.authority_epoch != candidate.authority_epoch {
            return Err(FailureCode::AuthorityEpochMismatch);
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct StateObjectHeader {
    object_id: Hash32,
    binding: DomainAuthorityBinding,
    version: u64,
    state_commitment: Hash32,
}

impl StateObjectHeader {
    #[must_use]
    pub const fn new(
        object_id: Hash32,
        binding: DomainAuthorityBinding,
        version: u64,
        state_commitment: Hash32,
    ) -> Self {
        Self {
            object_id,
            binding,
            version,
            state_commitment,
        }
    }

    #[must_use]
    pub const fn object_id(&self) -> Hash32 {
        self.object_id
    }

    #[must_use]
    pub const fn binding(&self) -> DomainAuthorityBinding {
        self.binding
    }

    #[must_use]
    pub const fn version(&self) -> u64 {
        self.version
    }

    #[must_use]
    pub const fn state_commitment(&self) -> Hash32 {
        self.state_commitment
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ObjectAccess {
    object_id: Hash32,
    mode: AccessMode,
    expected_version: u64,
    fencing_token: Option<NonZeroU64>,
}

impl ObjectAccess {
    pub fn new(
        object_id: Hash32,
        mode: AccessMode,
        expected_version: u64,
        fencing_token: Option<NonZeroU64>,
    ) -> Result<Self, FailureCode> {
        match (mode, fencing_token) {
            (AccessMode::Reserve, None) => return Err(FailureCode::FencingTokenRequired),
            (AccessMode::Reserve, Some(_)) | (_, None) => {}
            (_, Some(_)) => return Err(FailureCode::InvalidFencingToken),
        }
        Ok(Self {
            object_id,
            mode,
            expected_version,
            fencing_token,
        })
    }

    #[must_use]
    pub const fn object_id(&self) -> Hash32 {
        self.object_id
    }

    #[must_use]
    pub const fn mode(&self) -> AccessMode {
        self.mode
    }

    #[must_use]
    pub const fn expected_version(&self) -> u64 {
        self.expected_version
    }

    #[must_use]
    pub const fn fencing_token(&self) -> Option<NonZeroU64> {
        self.fencing_token
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct IntentCommitments {
    actor_root: Hash32,
    workflow_definition_hash: Hash32,
    input_commitment: Hash32,
    expected_output_commitment: Hash32,
    evidence_root: Hash32,
    sidecar_root: Hash32,
}

impl IntentCommitments {
    #[must_use]
    pub const fn new(
        actor_root: Hash32,
        workflow_definition_hash: Hash32,
        input_commitment: Hash32,
        expected_output_commitment: Hash32,
        evidence_root: Hash32,
        sidecar_root: Hash32,
    ) -> Self {
        Self {
            actor_root,
            workflow_definition_hash,
            input_commitment,
            expected_output_commitment,
            evidence_root,
            sidecar_root,
        }
    }

    #[must_use]
    pub const fn actor_root(self) -> Hash32 {
        self.actor_root
    }

    #[must_use]
    pub const fn workflow_definition_hash(self) -> Hash32 {
        self.workflow_definition_hash
    }

    #[must_use]
    pub const fn input_commitment(self) -> Hash32 {
        self.input_commitment
    }

    #[must_use]
    pub const fn expected_output_commitment(self) -> Hash32 {
        self.expected_output_commitment
    }

    #[must_use]
    pub const fn evidence_root(self) -> Hash32 {
        self.evidence_root
    }

    #[must_use]
    pub const fn sidecar_root(self) -> Hash32 {
        self.sidecar_root
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ExecutionPolicy {
    signature_suite: SignatureSuite,
    execution_tier: ExecutionTier,
    max_execution_units: u64,
    max_settlement_cost: u64,
}

impl ExecutionPolicy {
    pub fn new(
        signature_suite: SignatureSuite,
        execution_tier: ExecutionTier,
        max_execution_units: u64,
        max_settlement_cost: u64,
    ) -> Result<Self, FailureCode> {
        if execution_tier == ExecutionTier::Tier2
            && signature_suite != SignatureSuite::Secp256k1Mldsa65
        {
            return Err(FailureCode::TierSignatureMismatch);
        }
        if max_execution_units == 0 {
            return Err(FailureCode::InvalidExecutionLimit);
        }
        Ok(Self {
            signature_suite,
            execution_tier,
            max_execution_units,
            max_settlement_cost,
        })
    }

    #[must_use]
    pub const fn signature_suite(self) -> SignatureSuite {
        self.signature_suite
    }

    #[must_use]
    pub const fn execution_tier(self) -> ExecutionTier {
        self.execution_tier
    }

    #[must_use]
    pub const fn max_execution_units(self) -> u64 {
        self.max_execution_units
    }

    #[must_use]
    pub const fn max_settlement_cost(self) -> u64 {
        self.max_settlement_cost
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct UnsignedIntent {
    commitments: IntentCommitments,
    binding: DomainAuthorityBinding,
    nonce: u64,
    valid_until_height: u64,
    program_id: Hash32,
    accesses: Vec<ObjectAccess>,
    execution_policy: ExecutionPolicy,
}

impl UnsignedIntent {
    pub fn new(
        commitments: IntentCommitments,
        binding: DomainAuthorityBinding,
        nonce: u64,
        valid_until_height: u64,
        program_id: Hash32,
        accesses: Vec<ObjectAccess>,
        execution_policy: ExecutionPolicy,
    ) -> Result<Self, FailureCode> {
        if accesses.len() > MAX_OBJECT_ACCESSES {
            return Err(FailureCode::BoundsExceeded);
        }
        let requires_hybrid_tier_two =
            requires_tier_two_authorization(&accesses, execution_policy.max_settlement_cost());
        if requires_hybrid_tier_two
            && (execution_policy.execution_tier() != ExecutionTier::Tier2
                || execution_policy.signature_suite() != SignatureSuite::Secp256k1Mldsa65)
        {
            return Err(FailureCode::TierSignatureMismatch);
        }
        for pair in accesses.windows(2) {
            let left = pair[0].object_id();
            let right = pair[1].object_id();
            if left == right {
                return Err(FailureCode::DuplicateObject);
            }
            if left > right {
                return Err(FailureCode::NonCanonicalObjectOrder);
            }
        }
        Ok(Self {
            commitments,
            binding,
            nonce,
            valid_until_height,
            program_id,
            accesses,
            execution_policy,
        })
    }

    #[must_use]
    pub const fn actor_root(&self) -> Hash32 {
        self.commitments.actor_root()
    }

    #[must_use]
    pub const fn binding(&self) -> DomainAuthorityBinding {
        self.binding
    }

    #[must_use]
    pub const fn nonce(&self) -> u64 {
        self.nonce
    }

    #[must_use]
    pub const fn valid_until_height(&self) -> u64 {
        self.valid_until_height
    }

    #[must_use]
    pub const fn program_id(&self) -> Hash32 {
        self.program_id
    }

    #[must_use]
    pub const fn workflow_definition_hash(&self) -> Hash32 {
        self.commitments.workflow_definition_hash()
    }

    #[must_use]
    pub fn accesses(&self) -> &[ObjectAccess] {
        &self.accesses
    }

    #[must_use]
    pub const fn input_commitment(&self) -> Hash32 {
        self.commitments.input_commitment()
    }

    #[must_use]
    pub const fn expected_output_commitment(&self) -> Hash32 {
        self.commitments.expected_output_commitment()
    }

    #[must_use]
    pub const fn evidence_root(&self) -> Hash32 {
        self.commitments.evidence_root()
    }

    #[must_use]
    pub const fn sidecar_root(&self) -> Hash32 {
        self.commitments.sidecar_root()
    }

    #[must_use]
    pub const fn signature_suite(&self) -> SignatureSuite {
        self.execution_policy.signature_suite()
    }

    #[must_use]
    pub const fn execution_tier(&self) -> ExecutionTier {
        self.execution_policy.execution_tier()
    }

    #[must_use]
    pub const fn max_execution_units(&self) -> u64 {
        self.execution_policy.max_execution_units()
    }

    #[must_use]
    pub const fn max_settlement_cost(&self) -> u64 {
        self.execution_policy.max_settlement_cost()
    }

    #[must_use]
    pub const fn commitments(&self) -> IntentCommitments {
        self.commitments
    }

    #[must_use]
    pub const fn execution_policy(&self) -> ExecutionPolicy {
        self.execution_policy
    }
}

fn requires_tier_two_authorization(accesses: &[ObjectAccess], max_settlement_cost: u64) -> bool {
    max_settlement_cost > 0 || accesses.iter().any(|access| access.mode().is_mutating())
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TransitionOutcome {
    Success,
    Failure {
        code: FailureCode,
        instruction_index: u32,
    },
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ReceiptCommitments {
    pre_state_root: Hash32,
    post_state_root: Hash32,
    output_commitment: Hash32,
}

impl ReceiptCommitments {
    #[must_use]
    pub const fn new(
        pre_state_root: Hash32,
        post_state_root: Hash32,
        output_commitment: Hash32,
    ) -> Self {
        Self {
            pre_state_root,
            post_state_root,
            output_commitment,
        }
    }

    #[must_use]
    pub const fn pre_state_root(&self) -> Hash32 {
        self.pre_state_root
    }

    #[must_use]
    pub const fn post_state_root(&self) -> Hash32 {
        self.post_state_root
    }

    #[must_use]
    pub const fn output_commitment(&self) -> Hash32 {
        self.output_commitment
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SemanticReceipt {
    intent_id: Hash32,
    program_id: Hash32,
    binding: DomainAuthorityBinding,
    commitments: ReceiptCommitments,
    gas_used: u64,
    outcome: TransitionOutcome,
}

impl SemanticReceipt {
    #[must_use]
    pub const fn new(
        intent_id: Hash32,
        program_id: Hash32,
        binding: DomainAuthorityBinding,
        commitments: ReceiptCommitments,
        gas_used: u64,
        outcome: TransitionOutcome,
    ) -> Self {
        Self {
            intent_id,
            program_id,
            binding,
            commitments,
            gas_used,
            outcome,
        }
    }

    #[must_use]
    pub const fn intent_id(&self) -> Hash32 {
        self.intent_id
    }

    #[must_use]
    pub const fn program_id(&self) -> Hash32 {
        self.program_id
    }

    #[must_use]
    pub const fn binding(&self) -> DomainAuthorityBinding {
        self.binding
    }

    #[must_use]
    pub const fn pre_state_root(&self) -> Hash32 {
        self.commitments.pre_state_root()
    }

    #[must_use]
    pub const fn post_state_root(&self) -> Hash32 {
        self.commitments.post_state_root()
    }

    #[must_use]
    pub const fn output_commitment(&self) -> Hash32 {
        self.commitments.output_commitment()
    }

    #[must_use]
    pub const fn commitments(&self) -> &ReceiptCommitments {
        &self.commitments
    }

    #[must_use]
    pub const fn gas_used(&self) -> u64 {
        self.gas_used
    }

    #[must_use]
    pub const fn outcome(&self) -> TransitionOutcome {
        self.outcome
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SettlementMetadata {
    receipt_hash: Hash32,
    binding: DomainAuthorityBinding,
    source_chain_reference: Hash32,
    source_transaction_hash: Hash32,
    settled_at_height: u64,
    bridge_proof_hash: Hash32,
    payload_hash: Hash32,
}

impl SettlementMetadata {
    pub fn new(
        receipt_hash: Hash32,
        binding: DomainAuthorityBinding,
        source_chain_reference: Hash32,
        source_transaction_hash: Hash32,
        settled_at_height: u64,
        bridge_proof_hash: Hash32,
        payload_hash: Hash32,
    ) -> Result<Self, FailureCode> {
        let is_cross_host = !source_chain_reference.is_zero();
        if is_cross_host {
            if source_transaction_hash.is_zero()
                || bridge_proof_hash.is_zero()
                || payload_hash.is_zero()
                || bridge_proof_hash == payload_hash
            {
                return Err(FailureCode::InvalidSettlementMetadata);
            }
        } else if !source_transaction_hash.is_zero()
            || settled_at_height != 0
            || !bridge_proof_hash.is_zero()
            || !payload_hash.is_zero()
        {
            return Err(FailureCode::InvalidSettlementMetadata);
        }

        Ok(Self {
            receipt_hash,
            binding,
            source_chain_reference,
            source_transaction_hash,
            settled_at_height,
            bridge_proof_hash,
            payload_hash,
        })
    }

    #[must_use]
    pub const fn receipt_hash(&self) -> Hash32 {
        self.receipt_hash
    }

    #[must_use]
    pub const fn binding(&self) -> DomainAuthorityBinding {
        self.binding
    }

    #[must_use]
    pub const fn source_chain_reference(&self) -> Hash32 {
        self.source_chain_reference
    }

    #[must_use]
    pub const fn source_transaction_hash(&self) -> Hash32 {
        self.source_transaction_hash
    }

    #[must_use]
    pub const fn settled_at_height(&self) -> u64 {
        self.settled_at_height
    }

    #[must_use]
    pub const fn bridge_proof_hash(&self) -> Hash32 {
        self.bridge_proof_hash
    }

    #[must_use]
    pub const fn payload_hash(&self) -> Hash32 {
        self.payload_hash
    }

    #[must_use]
    pub fn is_cross_host(&self) -> bool {
        !self.source_chain_reference.is_zero()
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ProverBackend {
    Sp1,
    RiscZero,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ProverError {
    Unconfigured(ProverBackend),
    Unsupported(ProverBackend),
}

impl ProverError {
    #[must_use]
    pub const fn failure_code(self) -> FailureCode {
        match self {
            Self::Unconfigured(_) => FailureCode::UnconfiguredProver,
            Self::Unsupported(_) => FailureCode::UnsupportedProver,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hash(byte: u8) -> Hash32 {
        Hash32::new([byte; 32])
    }

    fn commitments() -> IntentCommitments {
        IntentCommitments::new(hash(10), hash(11), hash(12), hash(13), hash(14), hash(15))
    }

    fn policy() -> ExecutionPolicy {
        match ExecutionPolicy::new(SignatureSuite::Secp256k1, ExecutionTier::Tier1, 100, 0) {
            Ok(value) => value,
            Err(code) => panic!("unexpected execution policy error: {code:?}"),
        }
    }

    #[test]
    fn preserves_both_host_authorities_without_universal_host() {
        let polygon = DomainAuthorityBinding::new(hash(1), HostAuthority::PolygonAmoy, 7);
        let cardano = DomainAuthorityBinding::new(hash(2), HostAuthority::CardanoPreProd, 4);
        assert_eq!(polygon.host_authority(), HostAuthority::PolygonAmoy);
        assert_eq!(cardano.host_authority(), HostAuthority::CardanoPreProd);
        assert_eq!(
            polygon.validate(&cardano),
            Err(FailureCode::StateDomainMismatch)
        );
    }

    #[test]
    fn authority_epoch_prevents_stale_writer_replay() {
        let current = DomainAuthorityBinding::new(hash(3), HostAuthority::PolygonAmoy, 9);
        let stale = DomainAuthorityBinding::new(hash(3), HostAuthority::PolygonAmoy, 8);
        assert_eq!(
            current.validate(&stale),
            Err(FailureCode::AuthorityEpochMismatch)
        );
    }

    #[test]
    fn reserve_requires_nonzero_fencing_token() {
        assert_eq!(
            ObjectAccess::new(hash(4), AccessMode::Reserve, 1, None),
            Err(FailureCode::FencingTokenRequired)
        );
        let token = NonZeroU64::new(1);
        assert!(ObjectAccess::new(hash(4), AccessMode::Reserve, 1, token).is_ok());
        assert_eq!(
            ObjectAccess::new(hash(4), AccessMode::Read, 1, token),
            Err(FailureCode::InvalidFencingToken)
        );
    }

    #[test]
    fn all_non_reserve_access_modes_are_fence_free() {
        for mode in [
            AccessMode::Read,
            AccessMode::Consume,
            AccessMode::Accumulate,
        ] {
            assert!(ObjectAccess::new(hash(mode.as_u8()), mode, 0, None).is_ok());
        }
    }

    #[test]
    fn intent_rejects_duplicate_and_unsorted_objects() {
        let first = ObjectAccess::new(hash(1), AccessMode::Read, 0, None);
        let second = ObjectAccess::new(hash(2), AccessMode::Read, 0, None);
        assert!(first.is_ok());
        assert!(second.is_ok());
        let first = match first {
            Ok(value) => value,
            Err(code) => panic!("unexpected access error: {code:?}"),
        };
        let second = match second {
            Ok(value) => value,
            Err(code) => panic!("unexpected access error: {code:?}"),
        };
        let binding = DomainAuthorityBinding::new(hash(9), HostAuthority::PolygonAmoy, 1);
        let duplicate = UnsignedIntent::new(
            commitments(),
            binding,
            1,
            10,
            hash(8),
            vec![first.clone(), first.clone()],
            policy(),
        );
        assert_eq!(duplicate, Err(FailureCode::DuplicateObject));
        let unsorted = UnsignedIntent::new(
            commitments(),
            binding,
            1,
            10,
            hash(8),
            vec![second, first],
            policy(),
        );
        assert_eq!(unsorted, Err(FailureCode::NonCanonicalObjectOrder));
    }

    #[test]
    fn tier_two_requires_hybrid_signature_suite() {
        assert_eq!(
            ExecutionPolicy::new(SignatureSuite::Secp256k1, ExecutionTier::Tier2, 100, 50),
            Err(FailureCode::TierSignatureMismatch)
        );
        assert!(
            ExecutionPolicy::new(
                SignatureSuite::Secp256k1Mldsa65,
                ExecutionTier::Tier2,
                100,
                50,
            )
            .is_ok()
        );
        assert_eq!(
            ExecutionPolicy::new(SignatureSuite::Secp256k1, ExecutionTier::Tier0, 0, 0),
            Err(FailureCode::InvalidExecutionLimit)
        );
    }

    #[test]
    fn mutating_or_settling_intents_cannot_downgrade_from_hybrid_tier_two() {
        let binding = DomainAuthorityBinding::new(hash(9), HostAuthority::PolygonAmoy, 1);
        let classical_tier_one =
            match ExecutionPolicy::new(SignatureSuite::Secp256k1, ExecutionTier::Tier1, 100, 0) {
                Ok(value) => value,
                Err(code) => panic!("unexpected policy error: {code:?}"),
            };
        let hybrid_tier_one = match ExecutionPolicy::new(
            SignatureSuite::Secp256k1Mldsa65,
            ExecutionTier::Tier1,
            100,
            0,
        ) {
            Ok(value) => value,
            Err(code) => panic!("unexpected policy error: {code:?}"),
        };

        for (mode, token) in [
            (AccessMode::Consume, None),
            (AccessMode::Reserve, NonZeroU64::new(1)),
            (AccessMode::Accumulate, None),
        ] {
            let access = match ObjectAccess::new(hash(1), mode, 0, token) {
                Ok(value) => value,
                Err(code) => panic!("unexpected access error: {code:?}"),
            };
            for execution_policy in [classical_tier_one, hybrid_tier_one] {
                assert_eq!(
                    UnsignedIntent::new(
                        commitments(),
                        binding,
                        1,
                        10,
                        hash(8),
                        vec![access.clone()],
                        execution_policy,
                    ),
                    Err(FailureCode::TierSignatureMismatch)
                );
            }
        }

        let nonzero_settlement_policy = match ExecutionPolicy::new(
            SignatureSuite::Secp256k1Mldsa65,
            ExecutionTier::Tier1,
            100,
            1,
        ) {
            Ok(value) => value,
            Err(code) => panic!("unexpected policy error: {code:?}"),
        };
        assert_eq!(
            UnsignedIntent::new(
                commitments(),
                binding,
                1,
                10,
                hash(8),
                Vec::new(),
                nonzero_settlement_policy,
            ),
            Err(FailureCode::TierSignatureMismatch)
        );
    }

    #[test]
    fn read_only_zero_cost_intents_may_use_lower_tiers() {
        let binding = DomainAuthorityBinding::new(hash(9), HostAuthority::PolygonAmoy, 1);
        let read = match ObjectAccess::new(hash(1), AccessMode::Read, 0, None) {
            Ok(value) => value,
            Err(code) => panic!("unexpected access error: {code:?}"),
        };
        for tier in [ExecutionTier::Tier0, ExecutionTier::Tier1] {
            let execution_policy =
                match ExecutionPolicy::new(SignatureSuite::Secp256k1, tier, 100, 0) {
                    Ok(value) => value,
                    Err(code) => panic!("unexpected policy error: {code:?}"),
                };
            assert!(
                UnsignedIntent::new(
                    commitments(),
                    binding,
                    1,
                    10,
                    hash(8),
                    vec![read.clone()],
                    execution_policy,
                )
                .is_ok()
            );
        }
    }

    #[test]
    fn settlement_metadata_enforces_local_zero_tuple_and_inv_10() {
        let binding = DomainAuthorityBinding::new(hash(9), HostAuthority::PolygonAmoy, 1);
        assert!(
            SettlementMetadata::new(
                hash(1),
                binding,
                Hash32::ZERO,
                Hash32::ZERO,
                0,
                Hash32::ZERO,
                Hash32::ZERO,
            )
            .is_ok()
        );
        assert_eq!(
            SettlementMetadata::new(
                hash(1),
                binding,
                Hash32::ZERO,
                hash(2),
                0,
                Hash32::ZERO,
                Hash32::ZERO,
            ),
            Err(FailureCode::InvalidSettlementMetadata)
        );
        assert_eq!(
            SettlementMetadata::new(hash(1), binding, hash(2), hash(3), 4, hash(5), hash(5),),
            Err(FailureCode::InvalidSettlementMetadata)
        );
        assert!(
            SettlementMetadata::new(hash(1), binding, hash(2), hash(3), 4, hash(5), hash(6),)
                .is_ok()
        );
    }
}
