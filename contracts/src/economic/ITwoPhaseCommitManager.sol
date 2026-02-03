// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title ITwoPhaseCommitManager
 * @author VAMS Protocol
 * @notice Interface for atomic multi-service workflow orchestration
 * @dev Implements 2PC pattern for cross-service atomicity
 * 
 * Architecture Reference: ARCHITECTURE_v0-3-0.md §20.2.5
 * 
 * Two-Phase Commit Pattern:
 * 1. PREPARE: Agent locks funds in escrows for all services
 * 2. EXECUTE: Services execute and report readiness
 * 3. COMMIT: Coordinator reveals secret, allowing claims
 *    OR ABORT: Timeout or failure triggers refunds
 * 
 * Use Cases:
 * - Multi-model AI pipelines
 * - Complex agent workflows
 * - Cross-provider service chains
 */
interface ITwoPhaseCommitManager {
    // ============ Enums ============
    
    /**
     * @notice Workflow state
     */
    enum WorkflowState {
        PENDING,    // Created, waiting for all services to prepare
        PREPARED,   // All services prepared, ready to commit
        COMMITTED,  // Secret revealed, services can claim
        ABORTED,    // Workflow aborted, refunds available
        EXPIRED     // Deadline passed without commit
    }
    
    /**
     * @notice Service state within workflow
     */
    enum ServiceState {
        PENDING,    // Awaiting preparation
        PREPARED,   // Service ready (locked funds)
        CLAIMED,    // Service completed and claimed
        REFUNDED    // Service refunded (abort/expire)
    }
    
    // ============ Structs ============
    
    /**
     * @notice Service request in a workflow
     * @param provider Provider address
     * @param amount Payment amount
     * @param serviceType Type of service
     * @param timeout Timeout for this service (seconds)
     */
    struct ServiceRequest {
        address provider;
        uint256 amount;
        bytes32 serviceType;
        uint256 timeout;
    }
    
    /**
     * @notice Service entry in workflow
     * @param escrowId Linked escrow in X402EscrowManager
     * @param provider Provider address
     * @param amount Payment amount
     * @param state Current state
     * @param preparedAt When service was marked prepared
     */
    struct ServiceEntry {
        bytes32 escrowId;
        address provider;
        uint256 amount;
        ServiceState state;
        uint256 preparedAt;
    }
    
    /**
     * @notice Workflow details
     * @param workflowId Unique identifier
     * @param agent Initiating agent
     * @param state Current state
     * @param totalValue Sum of all service amounts
     * @param serviceCount Number of services
     * @param preparedCount Number of prepared services
     * @param createdAt Creation timestamp
     * @param prepareDeadline Deadline for all services to prepare
     * @param commitDeadline Deadline to commit after all prepared
     * @param commitSecretHash Hash of commit secret
     */
    struct Workflow {
        bytes32 workflowId;
        address agent;
        WorkflowState state;
        uint256 totalValue;
        uint256 serviceCount;
        uint256 preparedCount;
        uint256 createdAt;
        uint256 prepareDeadline;
        uint256 commitDeadline;
        bytes32 commitSecretHash;
    }
    
    // ============ Events ============
    
    event WorkflowInitiated(
        bytes32 indexed workflowId,
        address indexed agent,
        uint256 serviceCount,
        uint256 totalValue,
        uint256 prepareDeadline
    );
    
    event ServicePrepared(
        bytes32 indexed workflowId,
        bytes32 indexed escrowId,
        address indexed provider
    );
    
    event WorkflowPrepared(bytes32 indexed workflowId, uint256 commitDeadline);
    
    event WorkflowCommitted(bytes32 indexed workflowId, bytes32 secret);
    
    event WorkflowAborted(bytes32 indexed workflowId, string reason);
    
    event WorkflowExpired(bytes32 indexed workflowId);
    
    event ServiceClaimed(
        bytes32 indexed workflowId,
        bytes32 indexed escrowId,
        address indexed provider,
        uint256 amount
    );
    
    event ServiceRefunded(
        bytes32 indexed workflowId,
        bytes32 indexed escrowId,
        address indexed agent,
        uint256 amount
    );
    
    // ============ Errors ============
    
    /// @notice Workflow not found
    error WorkflowNotFound(bytes32 workflowId);
    
    /// @notice Invalid workflow state for operation
    error InvalidWorkflowState(bytes32 workflowId, WorkflowState current, WorkflowState required);
    
    /// @notice Service not found in workflow
    error ServiceNotFound(bytes32 workflowId, bytes32 escrowId);
    
    /// @notice Invalid commit secret
    error InvalidCommitSecret(bytes32 provided, bytes32 expected);
    
    /// @notice Deadline expired
    error DeadlineExpired(uint256 deadline);
    
    /// @notice Deadline not yet reached
    error DeadlineNotReached(uint256 deadline);
    
    /// @notice Caller not authorized
    error UnauthorizedCaller();
    
    /// @notice Empty service list
    error EmptyServiceList();
    
    /// @notice Zero value
    error ZeroValue();
    
    /// @notice Service already prepared
    error ServiceAlreadyPrepared(bytes32 escrowId);
    
    // ============ Constants View ============
    
    /// @notice Default prepare window (1 hour)
    function DEFAULT_PREPARE_WINDOW() external view returns (uint256);
    
    /// @notice Default commit window (30 minutes)
    function DEFAULT_COMMIT_WINDOW() external view returns (uint256);
    
    // ============ View Functions ============
    
    /**
     * @notice Get workflow details
     * @param workflowId Workflow ID
     * @return Workflow struct
     */
    function getWorkflow(bytes32 workflowId) external view returns (Workflow memory);
    
    /**
     * @notice Get service in workflow
     * @param workflowId Workflow ID
     * @param escrowId Escrow ID
     * @return ServiceEntry struct
     */
    function getService(bytes32 workflowId, bytes32 escrowId) 
        external view returns (ServiceEntry memory);
    
    /**
     * @notice Get all escrow IDs in workflow
     * @param workflowId Workflow ID
     * @return Array of escrow IDs
     */
    function getWorkflowEscrows(bytes32 workflowId) 
        external view returns (bytes32[] memory);
    
    /**
     * @notice Check if workflow is ready to commit
     * @param workflowId Workflow ID
     * @return True if all services prepared
     */
    function isReadyToCommit(bytes32 workflowId) external view returns (bool);
    
    /**
     * @notice Check if workflow has expired
     * @param workflowId Workflow ID
     * @return True if expired
     */
    function isExpired(bytes32 workflowId) external view returns (bool);
    
    // ============ Agent Functions ============
    
    /**
     * @notice Initiate a multi-service workflow
     * @param workflowId Unique workflow identifier
     * @param services Array of service requests
     * @param commitSecretHash Hash of the commit secret
     * @param prepareWindow Time allowed for all services to prepare
     * @return escrowIds Array of created escrow IDs
     */
    function initiateWorkflow(
        bytes32 workflowId,
        ServiceRequest[] calldata services,
        bytes32 commitSecretHash,
        uint256 prepareWindow
    ) external returns (bytes32[] memory escrowIds);
    
    /**
     * @notice Commit workflow by revealing secret
     * @dev Called after all services are prepared
     * @param workflowId Workflow ID
     * @param secret Preimage of commitSecretHash
     */
    function commitWorkflow(bytes32 workflowId, bytes32 secret) external;
    
    /**
     * @notice Abort workflow
     * @dev Can be called by agent before commit
     * @param workflowId Workflow ID
     * @param reason Abort reason
     */
    function abortWorkflow(bytes32 workflowId, string calldata reason) external;
    
    // ============ Provider Functions ============
    
    /**
     * @notice Mark service as prepared
     * @dev Called by provider after locking resources
     * @param workflowId Workflow ID
     * @param escrowId Escrow for this service
     */
    function markServicePrepared(bytes32 workflowId, bytes32 escrowId) external;
    
    // ============ Settlement Functions ============
    
    /**
     * @notice Process expired workflow
     * @dev Marks workflow as expired and enables refunds
     * @param workflowId Workflow ID
     */
    function processExpiredWorkflow(bytes32 workflowId) external;
    
    /**
     * @notice Claim refund for aborted/expired service
     * @param workflowId Workflow ID
     * @param escrowId Escrow to refund
     */
    function claimRefund(bytes32 workflowId, bytes32 escrowId) external;
}
