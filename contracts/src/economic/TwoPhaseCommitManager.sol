// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

import {ITwoPhaseCommitManager} from "./ITwoPhaseCommitManager.sol";
import {IX402EscrowManager} from "./IX402EscrowManager.sol";

/**
 * @title TwoPhaseCommitManager
 * @author VAMS Protocol
 * @notice Orchestrates atomic multi-service workflows using 2PC pattern
 * @dev Implements workflow atomicity per ARCHITECTURE_v0-3-0.md §20.2.5
 * 
 * Pattern:
 * 1. Agent initiates workflow with N services
 * 2. Each service provider marks their service as PREPARED
 * 3. Once all prepared, agent reveals commit secret
 * 4. Providers can claim their escrows with the secret
 * 
 * Failure Mode:
 * - If any service fails to prepare before deadline: ABORT
 * - If agent doesn't commit after all prepared: EXPIRE
 * - Both cases allow refunds to agent
 */
contract TwoPhaseCommitManager is 
    Initializable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    ReentrancyGuard,
    ITwoPhaseCommitManager 
{
    using SafeERC20 for IERC20;
    
    // ============ Constants ============
    
    /// @notice Default prepare window: 1 hour
    uint256 public constant DEFAULT_PREPARE_WINDOW = 1 hours;
    
    /// @notice Default commit window: 30 minutes
    uint256 public constant DEFAULT_COMMIT_WINDOW = 30 minutes;
    
    /// @notice Role for administration
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    
    // ============ Storage ============
    
    /// @notice VAMS token
    IERC20 public vamsToken;
    
    /// @notice Escrow manager
    IX402EscrowManager public escrowManager;
    
    /// @notice Workflows by ID
    mapping(bytes32 => Workflow) private _workflows;
    
    /// @notice Services in workflow
    mapping(bytes32 => mapping(bytes32 => ServiceEntry)) private _services;
    
    /// @notice Escrow IDs per workflow
    mapping(bytes32 => bytes32[]) private _workflowEscrows;
    
    /// @notice Agent's workflows
    mapping(address => bytes32[]) private _agentWorkflows;
    
    /// @notice Revealed secrets (for providers to claim)
    mapping(bytes32 => bytes32) private _revealedSecrets;
    
    /// @notice Total workflows created
    uint256 public totalWorkflows;
    
    // ============ Initializer ============
    
    /**
     * @notice Initialize the 2PC manager
     * @param admin Protocol admin
     * @param _vamsToken VAMS token
     * @param _escrowManager X402 escrow manager
     */
    function initialize(
        address admin,
        address _vamsToken,
        address _escrowManager
    ) external initializer {
        require(admin != address(0) && _vamsToken != address(0), "Zero address");
        
        __AccessControl_init();
        __Pausable_init();
        
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ADMIN_ROLE, admin);
        
        vamsToken = IERC20(_vamsToken);
        escrowManager = IX402EscrowManager(_escrowManager);
    }
    
    // ============ View Functions ============
    
    /// @inheritdoc ITwoPhaseCommitManager
    function getWorkflow(bytes32 workflowId) 
        external 
        view 
        override 
        returns (Workflow memory) 
    {
        return _workflows[workflowId];
    }
    
    /// @inheritdoc ITwoPhaseCommitManager
    function getService(bytes32 workflowId, bytes32 escrowId) 
        external 
        view 
        override 
        returns (ServiceEntry memory) 
    {
        return _services[workflowId][escrowId];
    }
    
    /// @inheritdoc ITwoPhaseCommitManager
    function getWorkflowEscrows(bytes32 workflowId) 
        external 
        view 
        override 
        returns (bytes32[] memory) 
    {
        return _workflowEscrows[workflowId];
    }
    
    /// @inheritdoc ITwoPhaseCommitManager
    function isReadyToCommit(bytes32 workflowId) 
        external 
        view 
        override 
        returns (bool) 
    {
        Workflow storage wf = _workflows[workflowId];
        return wf.state == WorkflowState.PREPARED ||
               (wf.state == WorkflowState.PENDING && 
                wf.preparedCount == wf.serviceCount);
    }
    
    /// @inheritdoc ITwoPhaseCommitManager
    function isExpired(bytes32 workflowId) 
        external 
        view 
        override 
        returns (bool) 
    {
        Workflow storage wf = _workflows[workflowId];
        
        if (wf.state == WorkflowState.EXPIRED) return true;
        
        // Check prepare deadline
        if (wf.state == WorkflowState.PENDING && 
            block.timestamp > wf.prepareDeadline) {
            return true;
        }
        
        // Check commit deadline
        if (wf.state == WorkflowState.PREPARED && 
            block.timestamp > wf.commitDeadline) {
            return true;
        }
        
        return false;
    }
    
    // ============ Agent Functions ============
    
    /// @inheritdoc ITwoPhaseCommitManager
    function initiateWorkflow(
        bytes32 workflowId,
        ServiceRequest[] calldata services,
        bytes32 commitSecretHash,
        uint256 prepareWindow
    ) external override nonReentrant whenNotPaused returns (bytes32[] memory escrowIds) {
        if (services.length == 0) revert EmptyServiceList();
        if (commitSecretHash == bytes32(0)) revert ZeroValue();
        if (_workflows[workflowId].createdAt != 0) {
            revert InvalidWorkflowState(
                workflowId, 
                _workflows[workflowId].state, 
                WorkflowState.PENDING
            );
        }
        
        uint256 actualPrepareWindow = prepareWindow > 0 ? 
            prepareWindow : DEFAULT_PREPARE_WINDOW;
        
        // Calculate total value
        uint256 totalValue = 0;
        for (uint256 i = 0; i < services.length; i++) {
            totalValue += services[i].amount;
        }
        
        // Create workflow
        _workflows[workflowId] = Workflow({
            workflowId: workflowId,
            agent: msg.sender,
            state: WorkflowState.PENDING,
            totalValue: totalValue,
            serviceCount: services.length,
            preparedCount: 0,
            createdAt: block.timestamp,
            prepareDeadline: block.timestamp + actualPrepareWindow,
            commitDeadline: 0, // Set when all prepared
            commitSecretHash: commitSecretHash
        });
        
        // Create escrows for each service
        escrowIds = new bytes32[](services.length);
        
        for (uint256 i = 0; i < services.length; i++) {
            ServiceRequest calldata svc = services[i];
            
            // Lock escrow via escrow manager
            // Using workflow-specific nonce pattern
            uint256 nonce = uint256(keccak256(abi.encodePacked(workflowId, i)));
            
            bytes32 escrowId = escrowManager.lockEscrow(
                svc.provider,
                svc.amount,
                nonce,
                svc.timeout > 0 ? svc.timeout : actualPrepareWindow + DEFAULT_COMMIT_WINDOW,
                commitSecretHash, // Use commit secret as HTLC hashlock
                svc.serviceType
            );
            
            escrowIds[i] = escrowId;
            _workflowEscrows[workflowId].push(escrowId);
            
            // Track service
            _services[workflowId][escrowId] = ServiceEntry({
                escrowId: escrowId,
                provider: svc.provider,
                amount: svc.amount,
                state: ServiceState.PENDING,
                preparedAt: 0
            });
        }
        
        _agentWorkflows[msg.sender].push(workflowId);
        totalWorkflows++;
        
        emit WorkflowInitiated(
            workflowId,
            msg.sender,
            services.length,
            totalValue,
            _workflows[workflowId].prepareDeadline
        );
        
        return escrowIds;
    }
    
    /// @inheritdoc ITwoPhaseCommitManager
    function commitWorkflow(bytes32 workflowId, bytes32 secret) 
        external 
        override 
        whenNotPaused 
    {
        Workflow storage wf = _workflows[workflowId];
        
        if (wf.createdAt == 0) revert WorkflowNotFound(workflowId);
        if (msg.sender != wf.agent) revert UnauthorizedCaller();
        
        // Must be PREPARED (or PENDING with all services prepared)
        if (wf.state == WorkflowState.PENDING && 
            wf.preparedCount == wf.serviceCount) {
            // Auto-transition to PREPARED
            wf.state = WorkflowState.PREPARED;
            wf.commitDeadline = block.timestamp + DEFAULT_COMMIT_WINDOW;
        }
        
        if (wf.state != WorkflowState.PREPARED) {
            revert InvalidWorkflowState(workflowId, wf.state, WorkflowState.PREPARED);
        }
        
        if (block.timestamp > wf.commitDeadline) {
            revert DeadlineExpired(wf.commitDeadline);
        }
        
        // Verify secret
        if (keccak256(abi.encodePacked(secret)) != wf.commitSecretHash) {
            revert InvalidCommitSecret(
                keccak256(abi.encodePacked(secret)),
                wf.commitSecretHash
            );
        }
        
        wf.state = WorkflowState.COMMITTED;
        _revealedSecrets[workflowId] = secret;
        
        emit WorkflowCommitted(workflowId, secret);
    }
    
    /// @inheritdoc ITwoPhaseCommitManager
    function abortWorkflow(bytes32 workflowId, string calldata reason) 
        external 
        override 
    {
        Workflow storage wf = _workflows[workflowId];
        
        if (wf.createdAt == 0) revert WorkflowNotFound(workflowId);
        if (msg.sender != wf.agent) revert UnauthorizedCaller();
        
        // Can only abort PENDING or PREPARED workflows
        if (wf.state != WorkflowState.PENDING && 
            wf.state != WorkflowState.PREPARED) {
            revert InvalidWorkflowState(workflowId, wf.state, WorkflowState.PENDING);
        }
        
        wf.state = WorkflowState.ABORTED;
        
        emit WorkflowAborted(workflowId, reason);
    }
    
    // ============ Provider Functions ============
    
    /// @inheritdoc ITwoPhaseCommitManager
    function markServicePrepared(bytes32 workflowId, bytes32 escrowId) 
        external 
        override 
    {
        Workflow storage wf = _workflows[workflowId];
        ServiceEntry storage svc = _services[workflowId][escrowId];
        
        if (wf.createdAt == 0) revert WorkflowNotFound(workflowId);
        if (svc.escrowId == bytes32(0)) {
            revert ServiceNotFound(workflowId, escrowId);
        }
        if (msg.sender != svc.provider) revert UnauthorizedCaller();
        
        if (wf.state != WorkflowState.PENDING) {
            revert InvalidWorkflowState(workflowId, wf.state, WorkflowState.PENDING);
        }
        
        if (block.timestamp > wf.prepareDeadline) {
            revert DeadlineExpired(wf.prepareDeadline);
        }
        
        if (svc.state != ServiceState.PENDING) {
            revert ServiceAlreadyPrepared(escrowId);
        }
        
        svc.state = ServiceState.PREPARED;
        svc.preparedAt = block.timestamp;
        wf.preparedCount++;
        
        emit ServicePrepared(workflowId, escrowId, msg.sender);
        
        // Check if all services are prepared
        if (wf.preparedCount == wf.serviceCount) {
            wf.state = WorkflowState.PREPARED;
            wf.commitDeadline = block.timestamp + DEFAULT_COMMIT_WINDOW;
            
            emit WorkflowPrepared(workflowId, wf.commitDeadline);
        }
    }
    
    // ============ Settlement Functions ============
    
    /// @inheritdoc ITwoPhaseCommitManager
    function processExpiredWorkflow(bytes32 workflowId) external override {
        Workflow storage wf = _workflows[workflowId];
        
        if (wf.createdAt == 0) revert WorkflowNotFound(workflowId);
        
        bool expired = false;
        
        if (wf.state == WorkflowState.PENDING && 
            block.timestamp > wf.prepareDeadline) {
            expired = true;
        } else if (wf.state == WorkflowState.PREPARED && 
            block.timestamp > wf.commitDeadline) {
            expired = true;
        }
        
        if (!expired) {
            if (wf.state == WorkflowState.PENDING) {
                revert DeadlineNotReached(wf.prepareDeadline);
            } else {
                revert DeadlineNotReached(wf.commitDeadline);
            }
        }
        
        wf.state = WorkflowState.EXPIRED;
        
        emit WorkflowExpired(workflowId);
    }
    
    /// @inheritdoc ITwoPhaseCommitManager
    function claimRefund(bytes32 workflowId, bytes32 escrowId) 
        external 
        override 
        nonReentrant 
    {
        Workflow storage wf = _workflows[workflowId];
        ServiceEntry storage svc = _services[workflowId][escrowId];
        
        if (wf.createdAt == 0) revert WorkflowNotFound(workflowId);
        if (svc.escrowId == bytes32(0)) {
            revert ServiceNotFound(workflowId, escrowId);
        }
        
        // Only agent can claim refund
        if (msg.sender != wf.agent) revert UnauthorizedCaller();
        
        // Can only refund ABORTED or EXPIRED workflows
        if (wf.state != WorkflowState.ABORTED && 
            wf.state != WorkflowState.EXPIRED) {
            revert InvalidWorkflowState(workflowId, wf.state, WorkflowState.ABORTED);
        }
        
        if (svc.state == ServiceState.REFUNDED) {
            revert ServiceAlreadyPrepared(escrowId); // Already refunded
        }
        
        svc.state = ServiceState.REFUNDED;
        
        // Trigger refund via escrow manager
        // Note: This relies on escrow being past expiry
        escrowManager.refundExpiredEscrow(escrowId);
        
        emit ServiceRefunded(workflowId, escrowId, msg.sender, svc.amount);
    }
    
    /**
     * @notice Get revealed secret for a committed workflow
     * @dev Providers can use this to claim their escrows
     * @param workflowId Workflow ID
     * @return The revealed commit secret
     */
    function getRevealedSecret(bytes32 workflowId) 
        external 
        view 
        returns (bytes32) 
    {
        return _revealedSecrets[workflowId];
    }
    
    /**
     * @notice Get agent's workflows
     * @param agent Agent address
     * @return Array of workflow IDs
     */
    function getAgentWorkflows(address agent) 
        external 
        view 
        returns (bytes32[] memory) 
    {
        return _agentWorkflows[agent];
    }
    
    // ============ Admin Functions ============
    
    /**
     * @notice Update escrow manager
     * @param _escrowManager New escrow manager
     */
    function setEscrowManager(address _escrowManager) 
        external 
        onlyRole(ADMIN_ROLE) 
    {
        escrowManager = IX402EscrowManager(_escrowManager);
    }
    
    /**
     * @notice Pause the contract
     */
    function pause() external onlyRole(ADMIN_ROLE) {
        _pause();
    }
    
    /**
     * @notice Unpause the contract
     */
    function unpause() external onlyRole(ADMIN_ROLE) {
        _unpause();
    }
    
    // ============ Storage Gap ============
    
    /// @dev Reserved storage space for future upgrades
    uint256[50] private __gap;
}
