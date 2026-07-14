//! Fail-closed RISC Zero adapter boundary.
//!
//! No RISC Zero SDK is linked in this foundation. Calls cannot return mock proofs.

use vir_types::{Hash32, ProverBackend, ProverError};

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct RiscZeroProverAdapter;

impl RiscZeroProverAdapter {
    #[must_use]
    pub const fn unconfigured() -> Self {
        Self
    }

    pub const fn prove(
        &self,
        _program_id: Hash32,
        _intent_id: Hash32,
    ) -> Result<Vec<u8>, ProverError> {
        Err(ProverError::Unconfigured(ProverBackend::RiscZero))
    }

    pub const fn verify(
        &self,
        _program_id: Hash32,
        _receipt_hash: Hash32,
        _proof: &[u8],
    ) -> Result<(), ProverError> {
        Err(ProverError::Unsupported(ProverBackend::RiscZero))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use vir_types::FailureCode;

    #[test]
    fn never_emits_or_accepts_placeholder_proofs() {
        let adapter = RiscZeroProverAdapter::unconfigured();
        let hash = Hash32::new([1; 32]);
        let prove = adapter.prove(hash, hash);
        assert!(matches!(
            prove,
            Err(error) if error.failure_code() == FailureCode::UnconfiguredProver
        ));
        let verify = adapter.verify(hash, hash, &[]);
        assert!(matches!(
            verify,
            Err(error) if error.failure_code() == FailureCode::UnsupportedProver
        ));
    }
}
