// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title TestConstants
 * @notice Shared constants for all VAMS tests
 */
library TestConstants {
    // ============ Token Constants ============
    uint256 constant TOTAL_SUPPLY = 1_000_000_000 ether;
    uint256 constant INITIAL_BALANCE = 1_000_000 ether;

    // ============ Staking Constants ============
    uint256 constant MIN_STAKE = 50_000 ether;
    uint256 constant UNBONDING_PERIOD = 14 days;

    // ============ Vesting Constants ============
    uint256 constant CLIFF_DURATION = 180 days;
    uint256 constant VESTING_DURATION = 730 days; // 2 years

    // ============ Agent Registry Constants ============
    uint256 constant MIN_AGENT_STAKE = 1000 ether;
    uint256 constant CHALLENGE_WINDOW = 7 days;
    uint256 constant MIN_CHALLENGER_STAKE = 100 ether;

    // ============ Provider Bond Constants ============
    uint256 constant MIN_BOND = 10_000 ether;
    uint256 constant BOND_COVERAGE_RATIO = 10;
    uint256 constant WITHDRAWAL_DELAY = 7 days;

    // ============ Escrow Constants ============
    uint256 constant MIN_ESCROW_VALIDITY = 5 minutes;
    uint256 constant MAX_ESCROW_VALIDITY = 24 hours;
    uint256 constant DISPUTE_WINDOW = 72 hours;
    uint256 constant SETTLEMENT_FEE_BPS = 5; // 0.05%

    // ============ Batch Settlement Constants ============
    uint256 constant BATCH_DISPUTE_WINDOW = 24 hours;

    // ============ Two Phase Commit Constants ============
    uint256 constant DEFAULT_PREPARE_WINDOW = 1 hours;
    uint256 constant DEFAULT_COMMIT_WINDOW = 30 minutes;

    // ============ Insurance Constants ============
    uint256 constant CLAIM_WINDOW = 7 days;
    uint8 constant APPROVAL_THRESHOLD = 2;
    uint256 constant MAX_PAYOUT_BPS = 5000; // 50%

    // ============ Slashing Constants ============
    uint256 constant SLASH_TO_INSURANCE_BPS = 5000; // 50%

    // ============ Test Identifiers ============
    bytes32 constant TEST_AGENT_ID = keccak256("test-agent-1");
    bytes32 constant TEST_PUBLIC_KEY_HASH = keccak256("test-public-key");
    bytes32 constant TEST_SERVICE_TYPE = keccak256("compute");
    bytes32 constant TEST_WORKFLOW_ID = keccak256("test-workflow-1");
    bytes32 constant TEST_COMMIT_SECRET = keccak256("secret");
    bytes32 constant TEST_MERKLE_ROOT = keccak256("merkle-root");

    // ============ Basis Points ============
    uint256 constant BPS_DENOMINATOR = 10000;
}
