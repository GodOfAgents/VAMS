//! Bounded deterministic VIR-Core reference interpreter.
//!
//! VIR-Core v1 exposes no wall clock, randomness, network, filesystem, floating
//! point, recursion, dynamic linking, or host syscalls. Programs are straight-
//! line bytecode ending in `HALT`; all arithmetic is checked.

use std::fmt;

use vir_codec::{
    derive_post_state_root, input_commitment, intent_id, keccak256, output_commitment,
    program_id as derive_program_id,
};
use vir_types::{
    AccessMode, DomainAuthorityBinding, FailureCode, Hash32, HostAuthority, ReceiptCommitments,
    SemanticReceipt, StateObjectHeader, TransitionOutcome, UnsignedIntent,
};

pub const VIR_VERSION: u16 = 1;
pub const MAX_BYTECODE_LENGTH: usize = 4_096;
pub const MAX_INSTRUCTIONS: usize = 1_024;
pub const MAX_STACK_DEPTH: usize = 256;
pub const MAX_INPUT_VALUES: usize = 64;

pub const HOST_FUNCTION_SET_POLICY_ASCII: &[u8] = b"VAMS:VIR:v1:host-functions:none";
pub const GAS_SCHEDULE_POLICY_ASCII: &[u8] =
    b"VAMS:VIR:v1:gas:push=1,load-input=1,add=2,sub=2,mul=3,div=3,eq=2,dup=1,drop=1,halt=0";
pub const ARITHMETIC_POLICY_ASCII: &[u8] =
    b"VAMS:VIR:v1:arithmetic:u64,checked-overflow,checked-underflow,zero-divisor-reject";

#[must_use]
pub fn supported_host_function_set_hash() -> Hash32 {
    keccak256(HOST_FUNCTION_SET_POLICY_ASCII)
}

#[must_use]
pub fn supported_gas_schedule_hash() -> Hash32 {
    keccak256(GAS_SCHEDULE_POLICY_ASCII)
}

#[must_use]
pub fn supported_arithmetic_policy_hash() -> Hash32 {
    keccak256(ARITHMETIC_POLICY_ASCII)
}

pub mod opcode {
    pub const PUSH_U64: u8 = 0x01;
    pub const LOAD_INPUT: u8 = 0x02;
    pub const ADD_U64: u8 = 0x10;
    pub const SUB_U64: u8 = 0x11;
    pub const MUL_U64: u8 = 0x12;
    pub const DIV_U64: u8 = 0x13;
    pub const EQ_U64: u8 = 0x20;
    pub const DUP: u8 = 0x21;
    pub const DROP: u8 = 0x22;
    pub const HALT: u8 = 0xff;
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RuntimeError {
    code: FailureCode,
    instruction_index: u32,
}

impl RuntimeError {
    #[must_use]
    pub const fn new(code: FailureCode, instruction_index: u32) -> Self {
        Self {
            code,
            instruction_index,
        }
    }

    #[must_use]
    pub const fn code(self) -> FailureCode {
        self.code
    }

    #[must_use]
    pub const fn instruction_index(self) -> u32 {
        self.instruction_index
    }
}

impl fmt::Display for RuntimeError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            formatter,
            "VIR runtime error {:?} at instruction {}",
            self.code, self.instruction_index
        )
    }
}

impl std::error::Error for RuntimeError {}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Program {
    bytecode: Vec<u8>,
    host_function_set_hash: Hash32,
    gas_schedule_hash: Hash32,
    arithmetic_policy_hash: Hash32,
}

impl Program {
    pub fn new(
        bytecode: Vec<u8>,
        host_function_set_hash: Hash32,
        gas_schedule_hash: Hash32,
        arithmetic_policy_hash: Hash32,
    ) -> Result<Self, RuntimeError> {
        if host_function_set_hash != supported_host_function_set_hash()
            || gas_schedule_hash != supported_gas_schedule_hash()
            || arithmetic_policy_hash != supported_arithmetic_policy_hash()
        {
            return Err(RuntimeError::new(
                FailureCode::UnsupportedPolicyCommitment,
                0,
            ));
        }
        validate_bytecode(&bytecode)?;
        Ok(Self {
            bytecode,
            host_function_set_hash,
            gas_schedule_hash,
            arithmetic_policy_hash,
        })
    }

    #[must_use]
    pub fn bytecode(&self) -> &[u8] {
        &self.bytecode
    }

    #[must_use]
    pub fn id(&self) -> Hash32 {
        derive_program_id(
            VIR_VERSION,
            &self.bytecode,
            self.host_function_set_hash,
            self.gas_schedule_hash,
            self.arithmetic_policy_hash,
        )
    }

    #[must_use]
    pub const fn host_function_set_hash(&self) -> Hash32 {
        self.host_function_set_hash
    }

    #[must_use]
    pub const fn gas_schedule_hash(&self) -> Hash32 {
        self.gas_schedule_hash
    }

    #[must_use]
    pub const fn arithmetic_policy_hash(&self) -> Hash32 {
        self.arithmetic_policy_hash
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ExecutionContext {
    execution_height: u64,
    gas_limit: u64,
    pre_state_root: Hash32,
}

impl ExecutionContext {
    #[must_use]
    pub const fn new(execution_height: u64, gas_limit: u64, pre_state_root: Hash32) -> Self {
        Self {
            execution_height,
            gas_limit,
            pre_state_root,
        }
    }

    #[must_use]
    pub const fn execution_height(self) -> u64 {
        self.execution_height
    }

    #[must_use]
    pub const fn gas_limit(self) -> u64 {
        self.gas_limit
    }

    #[must_use]
    pub const fn pre_state_root(self) -> Hash32 {
        self.pre_state_root
    }
}

pub fn execute(
    program: &Program,
    intent: &UnsignedIntent,
    authoritative_binding: DomainAuthorityBinding,
    objects: &[StateObjectHeader],
    input_values: &[u64],
    context: ExecutionContext,
) -> Result<SemanticReceipt, RuntimeError> {
    preflight(
        program,
        intent,
        authoritative_binding,
        objects,
        input_values,
        context,
    )?;

    let (result, gas_used) = interpret(program, input_values, context.gas_limit())?;
    let intent_id = intent_id(intent);
    let output_commitment = output_commitment(&[result]);
    if output_commitment != intent.expected_output_commitment() {
        return Err(RuntimeError::new(FailureCode::OutputCommitmentMismatch, 0));
    }
    let post_state_root =
        derive_post_state_root(context.pre_state_root(), intent_id, output_commitment);
    Ok(SemanticReceipt::new(
        intent_id,
        program.id(),
        authoritative_binding,
        ReceiptCommitments::new(context.pre_state_root(), post_state_root, output_commitment),
        gas_used,
        TransitionOutcome::Success,
    ))
}

fn preflight(
    program: &Program,
    intent: &UnsignedIntent,
    authoritative_binding: DomainAuthorityBinding,
    objects: &[StateObjectHeader],
    input_values: &[u64],
    context: ExecutionContext,
) -> Result<(), RuntimeError> {
    if program.id() != intent.program_id() {
        return Err(RuntimeError::new(FailureCode::ProgramIdMismatch, 0));
    }
    authoritative_binding
        .validate(&intent.binding())
        .map_err(|code| RuntimeError::new(code, 0))?;
    if context.execution_height() > intent.valid_until_height() {
        return Err(RuntimeError::new(FailureCode::IntentExpired, 0));
    }
    if context.gas_limit() > intent.max_execution_units() {
        return Err(RuntimeError::new(
            FailureCode::ExecutionUnitLimitExceeded,
            0,
        ));
    }
    if input_values.len() > MAX_INPUT_VALUES {
        return Err(RuntimeError::new(FailureCode::BoundsExceeded, 0));
    }
    if input_commitment(input_values) != intent.input_commitment() {
        return Err(RuntimeError::new(FailureCode::InputCommitmentMismatch, 0));
    }
    if objects.len() != intent.accesses().len() {
        return Err(RuntimeError::new(FailureCode::ObjectSetMismatch, 0));
    }

    for (access, object) in intent.accesses().iter().zip(objects) {
        if authoritative_binding.host_authority() == HostAuthority::CardanoPreProd
            && matches!(access.mode(), AccessMode::Consume | AccessMode::Reserve)
        {
            return Err(RuntimeError::new(FailureCode::AccessDenied, 0));
        }
        if access.object_id() != object.object_id() {
            return Err(RuntimeError::new(FailureCode::ObjectSetMismatch, 0));
        }
        authoritative_binding
            .validate(&object.binding())
            .map_err(|code| RuntimeError::new(code, 0))?;
        if access.expected_version() != object.version() {
            return Err(RuntimeError::new(FailureCode::StaleObjectVersion, 0));
        }
    }
    Ok(())
}

fn validate_bytecode(bytecode: &[u8]) -> Result<(), RuntimeError> {
    if bytecode.is_empty() {
        return Err(RuntimeError::new(FailureCode::InvalidProgram, 0));
    }
    if bytecode.len() > MAX_BYTECODE_LENGTH {
        return Err(RuntimeError::new(FailureCode::BoundsExceeded, 0));
    }

    let mut pc = 0_usize;
    let mut instruction_count = 0_usize;
    while pc < bytecode.len() {
        if instruction_count >= MAX_INSTRUCTIONS {
            return Err(RuntimeError::new(
                FailureCode::BoundsExceeded,
                instruction_index(instruction_count)?,
            ));
        }
        let opcode = bytecode[pc];
        pc += 1;
        instruction_count += 1;
        match opcode {
            opcode::PUSH_U64 => {
                advance_immediate(&mut pc, 8, bytecode.len(), instruction_count - 1)?
            }
            opcode::LOAD_INPUT => {
                advance_immediate(&mut pc, 1, bytecode.len(), instruction_count - 1)?
            }
            opcode::ADD_U64
            | opcode::SUB_U64
            | opcode::MUL_U64
            | opcode::DIV_U64
            | opcode::EQ_U64
            | opcode::DUP
            | opcode::DROP => {}
            opcode::HALT => {
                if pc != bytecode.len() {
                    return Err(RuntimeError::new(
                        FailureCode::TrailingInstructionData,
                        instruction_index(instruction_count - 1)?,
                    ));
                }
                return Ok(());
            }
            _ => {
                return Err(RuntimeError::new(
                    FailureCode::UnsupportedOpcode,
                    instruction_index(instruction_count - 1)?,
                ));
            }
        }
    }
    Err(RuntimeError::new(
        FailureCode::MissingHalt,
        instruction_index(instruction_count)?,
    ))
}

fn advance_immediate(
    pc: &mut usize,
    width: usize,
    length: usize,
    index: usize,
) -> Result<(), RuntimeError> {
    *pc = pc.checked_add(width).ok_or_else(|| {
        RuntimeError::new(
            FailureCode::BoundsExceeded,
            instruction_index(index).unwrap_or(u32::MAX),
        )
    })?;
    if *pc > length {
        return Err(RuntimeError::new(
            FailureCode::InvalidProgram,
            instruction_index(index)?,
        ));
    }
    Ok(())
}

fn instruction_index(index: usize) -> Result<u32, RuntimeError> {
    u32::try_from(index).map_err(|_| RuntimeError::new(FailureCode::BoundsExceeded, u32::MAX))
}

fn interpret(
    program: &Program,
    inputs: &[u64],
    gas_limit: u64,
) -> Result<(u64, u64), RuntimeError> {
    let bytecode = program.bytecode();
    let mut pc = 0_usize;
    let mut index = 0_u32;
    let mut gas_used = 0_u64;
    let mut stack = Vec::with_capacity(16);

    loop {
        let operation = bytecode
            .get(pc)
            .copied()
            .ok_or_else(|| RuntimeError::new(FailureCode::MissingHalt, index))?;
        pc += 1;
        gas_used = gas_used
            .checked_add(gas_cost(operation))
            .ok_or_else(|| RuntimeError::new(FailureCode::OutOfGas, index))?;
        if gas_used > gas_limit {
            return Err(RuntimeError::new(FailureCode::OutOfGas, index));
        }

        match operation {
            opcode::PUSH_U64 => {
                let end = pc
                    .checked_add(8)
                    .ok_or_else(|| RuntimeError::new(FailureCode::InvalidProgram, index))?;
                let bytes = bytecode
                    .get(pc..end)
                    .ok_or_else(|| RuntimeError::new(FailureCode::InvalidProgram, index))?;
                let mut value = [0_u8; 8];
                value.copy_from_slice(bytes);
                push(&mut stack, u64::from_be_bytes(value), index)?;
                pc = end;
            }
            opcode::LOAD_INPUT => {
                let input_index = bytecode
                    .get(pc)
                    .copied()
                    .ok_or_else(|| RuntimeError::new(FailureCode::InvalidProgram, index))?;
                pc += 1;
                let value = inputs
                    .get(usize::from(input_index))
                    .copied()
                    .ok_or_else(|| RuntimeError::new(FailureCode::InputOutOfBounds, index))?;
                push(&mut stack, value, index)?;
            }
            opcode::ADD_U64 => {
                let (left, right) = pop_pair(&mut stack, index)?;
                let value = left
                    .checked_add(right)
                    .ok_or_else(|| RuntimeError::new(FailureCode::ArithmeticOverflow, index))?;
                push(&mut stack, value, index)?;
            }
            opcode::SUB_U64 => {
                let (left, right) = pop_pair(&mut stack, index)?;
                let value = left
                    .checked_sub(right)
                    .ok_or_else(|| RuntimeError::new(FailureCode::ArithmeticUnderflow, index))?;
                push(&mut stack, value, index)?;
            }
            opcode::MUL_U64 => {
                let (left, right) = pop_pair(&mut stack, index)?;
                let value = left
                    .checked_mul(right)
                    .ok_or_else(|| RuntimeError::new(FailureCode::ArithmeticOverflow, index))?;
                push(&mut stack, value, index)?;
            }
            opcode::DIV_U64 => {
                let (left, right) = pop_pair(&mut stack, index)?;
                let value = left
                    .checked_div(right)
                    .ok_or_else(|| RuntimeError::new(FailureCode::DivisionByZero, index))?;
                push(&mut stack, value, index)?;
            }
            opcode::EQ_U64 => {
                let (left, right) = pop_pair(&mut stack, index)?;
                push(&mut stack, u64::from(left == right), index)?;
            }
            opcode::DUP => {
                let value = stack
                    .last()
                    .copied()
                    .ok_or_else(|| RuntimeError::new(FailureCode::StackUnderflow, index))?;
                push(&mut stack, value, index)?;
            }
            opcode::DROP => {
                pop(&mut stack, index)?;
            }
            opcode::HALT => {
                if stack.len() != 1 {
                    return Err(RuntimeError::new(FailureCode::StackNotSingleton, index));
                }
                return Ok((stack[0], gas_used));
            }
            _ => return Err(RuntimeError::new(FailureCode::UnsupportedOpcode, index)),
        }
        index = index
            .checked_add(1)
            .ok_or_else(|| RuntimeError::new(FailureCode::BoundsExceeded, u32::MAX))?;
    }
}

const fn gas_cost(operation: u8) -> u64 {
    match operation {
        opcode::PUSH_U64 | opcode::LOAD_INPUT | opcode::DUP | opcode::DROP => 1,
        opcode::ADD_U64 | opcode::SUB_U64 | opcode::EQ_U64 => 2,
        opcode::MUL_U64 | opcode::DIV_U64 => 3,
        opcode::HALT => 0,
        _ => u64::MAX,
    }
}

fn push(stack: &mut Vec<u64>, value: u64, index: u32) -> Result<(), RuntimeError> {
    if stack.len() >= MAX_STACK_DEPTH {
        return Err(RuntimeError::new(FailureCode::StackOverflow, index));
    }
    stack.push(value);
    Ok(())
}

fn pop(stack: &mut Vec<u64>, index: u32) -> Result<u64, RuntimeError> {
    stack
        .pop()
        .ok_or_else(|| RuntimeError::new(FailureCode::StackUnderflow, index))
}

fn pop_pair(stack: &mut Vec<u64>, index: u32) -> Result<(u64, u64), RuntimeError> {
    let right = pop(stack, index)?;
    let left = pop(stack, index)?;
    Ok((left, right))
}

#[cfg(test)]
mod tests {
    use std::num::NonZeroU64;

    use super::*;
    use vir_codec::output_commitment;
    use vir_types::{
        AccessMode, ExecutionPolicy, ExecutionTier, HostAuthority, IntentCommitments, ObjectAccess,
        SignatureSuite,
    };

    fn hash(byte: u8) -> Hash32 {
        Hash32::new([byte; 32])
    }

    fn hex(hash: Hash32) -> String {
        let mut output = String::with_capacity(64);
        for byte in hash.as_bytes() {
            use std::fmt::Write as _;
            let result = write!(&mut output, "{byte:02x}");
            assert!(result.is_ok());
        }
        output
    }

    fn must<T, E: fmt::Debug>(result: Result<T, E>) -> T {
        match result {
            Ok(value) => value,
            Err(error) => panic!("unexpected error: {error:?}"),
        }
    }

    fn push_u64(bytecode: &mut Vec<u8>, value: u64) {
        bytecode.push(opcode::PUSH_U64);
        bytecode.extend_from_slice(&value.to_be_bytes());
    }

    fn program(bytecode: Vec<u8>) -> Program {
        must(Program::new(
            bytecode,
            supported_host_function_set_hash(),
            supported_gas_schedule_hash(),
            supported_arithmetic_policy_hash(),
        ))
    }

    fn candidate_program(bytecode: Vec<u8>) -> Result<Program, RuntimeError> {
        Program::new(
            bytecode,
            supported_host_function_set_hash(),
            supported_gas_schedule_hash(),
            supported_arithmetic_policy_hash(),
        )
    }

    fn fixture(
        program: &Program,
        authority: HostAuthority,
        inputs: &[u64],
        expected_output: u64,
    ) -> (
        DomainAuthorityBinding,
        UnsignedIntent,
        Vec<StateObjectHeader>,
        ExecutionContext,
    ) {
        fixture_with_access(
            program,
            authority,
            inputs,
            expected_output,
            AccessMode::Read,
            None,
        )
    }

    fn fixture_with_access(
        program: &Program,
        authority: HostAuthority,
        inputs: &[u64],
        expected_output: u64,
        mode: AccessMode,
        fencing_token: Option<NonZeroU64>,
    ) -> (
        DomainAuthorityBinding,
        UnsignedIntent,
        Vec<StateObjectHeader>,
        ExecutionContext,
    ) {
        let binding = DomainAuthorityBinding::new(hash(1), authority, 7);
        let access = must(ObjectAccess::new(hash(2), mode, 3, fencing_token));
        let commitments = IntentCommitments::new(
            hash(6),
            hash(7),
            input_commitment(inputs),
            output_commitment(&[expected_output]),
            hash(8),
            hash(9),
        );
        let policy = must(ExecutionPolicy::new(
            SignatureSuite::Secp256k1Mldsa65,
            ExecutionTier::Tier2,
            100,
            50,
        ));
        let intent = must(UnsignedIntent::new(
            commitments,
            binding,
            9,
            1_000,
            program.id(),
            vec![access],
            policy,
        ));
        let objects = vec![StateObjectHeader::new(hash(2), binding, 3, hash(4))];
        let context = ExecutionContext::new(900, 100, hash(5));
        (binding, intent, objects, context)
    }

    #[test]
    fn checked_add_is_deterministic_on_both_hosts() {
        let mut bytecode = Vec::new();
        push_u64(&mut bytecode, 7);
        push_u64(&mut bytecode, 9);
        bytecode.push(opcode::ADD_U64);
        bytecode.push(opcode::HALT);
        let program = program(bytecode);

        for authority in [HostAuthority::PolygonAmoy, HostAuthority::CardanoPreProd] {
            let (binding, intent, objects, context) = fixture(&program, authority, &[], 16);
            let first = must(execute(&program, &intent, binding, &objects, &[], context));
            let second = must(execute(&program, &intent, binding, &objects, &[], context));
            assert_eq!(first, second);
            assert_eq!(first.binding().host_authority(), authority);
            assert_eq!(first.output_commitment(), output_commitment(&[16]));
            assert_eq!(first.gas_used(), 4);
        }
    }

    #[test]
    fn host_access_policy_is_explicit_and_fail_closed() {
        let mut bytecode = Vec::new();
        push_u64(&mut bytecode, 1);
        bytecode.push(opcode::HALT);
        let program = program(bytecode);
        let modes = [
            AccessMode::Read,
            AccessMode::Consume,
            AccessMode::Reserve,
            AccessMode::Accumulate,
        ];

        for mode in modes {
            let token = if mode == AccessMode::Reserve {
                NonZeroU64::new(1)
            } else {
                None
            };
            let (binding, intent, objects, context) =
                fixture_with_access(&program, HostAuthority::CardanoPreProd, &[], 1, mode, token);
            let result = execute(&program, &intent, binding, &objects, &[], context);
            if matches!(mode, AccessMode::Read | AccessMode::Accumulate) {
                assert!(result.is_ok());
            } else {
                assert!(matches!(
                    result,
                    Err(value) if value.code() == FailureCode::AccessDenied
                ));
            }
        }

        for mode in modes {
            let token = if mode == AccessMode::Reserve {
                NonZeroU64::new(1)
            } else {
                None
            };
            let (binding, intent, objects, context) =
                fixture_with_access(&program, HostAuthority::PolygonAmoy, &[], 1, mode, token);
            assert!(execute(&program, &intent, binding, &objects, &[], context).is_ok());
        }
    }

    #[test]
    fn input_addition_holds_for_a_bounded_value_corpus() {
        let program = program(vec![
            opcode::LOAD_INPUT,
            0,
            opcode::LOAD_INPUT,
            1,
            opcode::ADD_U64,
            opcode::HALT,
        ]);
        for left in 0_u64..128 {
            let right = 1_000 - left;
            let inputs = [left, right];
            let (binding, intent, objects, context) =
                fixture(&program, HostAuthority::PolygonAmoy, &inputs, 1_000);
            let receipt = must(execute(
                &program, &intent, binding, &objects, &inputs, context,
            ));
            assert_eq!(receipt.output_commitment(), output_commitment(&[1_000]));
        }
    }

    #[test]
    fn arithmetic_overflow_and_gas_exhaustion_fail_closed() {
        let mut bytecode = Vec::new();
        push_u64(&mut bytecode, u64::MAX);
        push_u64(&mut bytecode, 1);
        bytecode.push(opcode::ADD_U64);
        bytecode.push(opcode::HALT);
        let program = program(bytecode);
        let (binding, intent, objects, context) =
            fixture(&program, HostAuthority::PolygonAmoy, &[], 0);
        let error = execute(&program, &intent, binding, &objects, &[], context);
        assert!(matches!(
            error,
            Err(value) if value.code() == FailureCode::ArithmeticOverflow
        ));

        let gas_starved = ExecutionContext::new(900, 1, hash(5));
        let error = execute(&program, &intent, binding, &objects, &[], gas_starved);
        assert!(matches!(
            error,
            Err(value) if value.code() == FailureCode::OutOfGas
        ));
    }

    #[test]
    fn host_mismatch_stale_object_and_expiry_fail_closed() {
        let mut bytecode = Vec::new();
        push_u64(&mut bytecode, 1);
        bytecode.push(opcode::HALT);
        let program = program(bytecode);
        let (polygon, intent, objects, context) =
            fixture(&program, HostAuthority::PolygonAmoy, &[], 1);
        let cardano = DomainAuthorityBinding::new(
            polygon.state_domain(),
            HostAuthority::CardanoPreProd,
            polygon.authority_epoch(),
        );
        let error = execute(&program, &intent, cardano, &objects, &[], context);
        assert!(matches!(
            error,
            Err(value) if value.code() == FailureCode::HostAuthorityMismatch
        ));

        let stale = vec![StateObjectHeader::new(hash(2), polygon, 2, hash(4))];
        let error = execute(&program, &intent, polygon, &stale, &[], context);
        assert!(matches!(
            error,
            Err(value) if value.code() == FailureCode::StaleObjectVersion
        ));

        let expired = ExecutionContext::new(1_001, 100, hash(5));
        let error = execute(&program, &intent, polygon, &objects, &[], expired);
        assert!(matches!(
            error,
            Err(value) if value.code() == FailureCode::IntentExpired
        ));
    }

    #[test]
    fn execution_unit_and_expected_output_bounds_fail_closed() {
        let mut bytecode = Vec::new();
        push_u64(&mut bytecode, 1);
        bytecode.push(opcode::HALT);
        let program = program(bytecode);

        let (binding, intent, objects, _) = fixture(&program, HostAuthority::PolygonAmoy, &[], 1);
        let excessive_limit = ExecutionContext::new(900, 101, hash(5));
        let error = execute(&program, &intent, binding, &objects, &[], excessive_limit);
        assert!(matches!(
            error,
            Err(value) if value.code() == FailureCode::ExecutionUnitLimitExceeded
        ));

        let (binding, wrong_output, objects, context) =
            fixture(&program, HostAuthority::PolygonAmoy, &[], 2);
        let error = execute(&program, &wrong_output, binding, &objects, &[], context);
        assert!(matches!(
            error,
            Err(value) if value.code() == FailureCode::OutputCommitmentMismatch
        ));
    }

    #[test]
    fn rejects_forbidden_or_unbounded_program_shapes() {
        let unsupported = candidate_program(vec![0x40, opcode::HALT]);
        assert!(matches!(
            unsupported,
            Err(value) if value.code() == FailureCode::UnsupportedOpcode
        ));
        let missing_halt = candidate_program(vec![opcode::DUP]);
        assert!(matches!(
            missing_halt,
            Err(value) if value.code() == FailureCode::MissingHalt
        ));
        let trailing = candidate_program(vec![opcode::HALT, opcode::HALT]);
        assert!(matches!(
            trailing,
            Err(value) if value.code() == FailureCode::TrailingInstructionData
        ));
    }

    #[test]
    fn rejects_policy_commitment_relabeling() {
        let bytecode = vec![opcode::HALT];
        for (host, gas, arithmetic) in [
            (
                hash(1),
                supported_gas_schedule_hash(),
                supported_arithmetic_policy_hash(),
            ),
            (
                supported_host_function_set_hash(),
                hash(2),
                supported_arithmetic_policy_hash(),
            ),
            (
                supported_host_function_set_hash(),
                supported_gas_schedule_hash(),
                hash(3),
            ),
        ] {
            let result = Program::new(bytecode.clone(), host, gas, arithmetic);
            assert!(matches!(
                result,
                Err(value) if value.code() == FailureCode::UnsupportedPolicyCommitment
            ));
        }
    }

    #[test]
    fn supported_policy_hashes_match_documented_ascii() {
        assert_eq!(
            hex(supported_host_function_set_hash()),
            "926aa059fa0db9477ba813b969d5c1dcf92fbcdbf7e00d6ceeec13ceef33e860"
        );
        assert_eq!(
            hex(supported_gas_schedule_hash()),
            "ea7983ef0e10911d248e354efebafd3b05a479e50ba5f0cfa46890f74034f773"
        );
        assert_eq!(
            hex(supported_arithmetic_policy_hash()),
            "e6231804a0697191feee14abb9b5806f393a2725a10c0fc92f0159ee79c893a5"
        );
    }

    #[test]
    fn reserve_access_retains_nonzero_fence_at_type_boundary() {
        let token = NonZeroU64::new(42);
        let access = must(ObjectAccess::new(hash(7), AccessMode::Reserve, 1, token));
        assert_eq!(access.fencing_token(), token);
    }
}
