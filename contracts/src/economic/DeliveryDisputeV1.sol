// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {IComposedSettlement} from "./IComposedSettlement.sol";

/// @notice Settlement callback used only for an upheld dispute.
interface IDisputeRefundTarget {
    function refundUpheldDispute(bytes32 allocationId, uint256 providerIndex) external;
    function refundedProviderShareV3(bytes32 allocationId, uint256 providerIndex) external view returns (bool);
}

/**
 * @title DeliveryDisputeV1
 * @notice Dispute window for earned composed-settlement deliveries (F13, owner decision 10).
 * @dev Deployed by ComposedSettlement in its constructor, so both addresses are bound
 *      permanently. Every earned delivery is held for DISPUTE_WINDOW. During it the
 *      allocation's agent may open one dispute per row by posting a bond of BOND_BPS of
 *      the row amount (rounded up). The resolver (the governance timelock) either
 *      upholds it (full row refund to the agent, bond returned) or rejects it (row
 *      released for normal payment, bond to the provider). If unresolved by
 *      RESOLUTION_PERIOD, anyone may finalize: the row is released and the bond goes
 *      back to the agent. No slashing (tokenomics R1). Outcomes are binary.
 */
contract DeliveryDisputeV1 is ReentrancyGuard {
    using SafeERC20 for IERC20;

    uint256 public constant DISPUTE_WINDOW = 72 hours;
    uint256 public constant RESOLUTION_PERIOD = 14 days;
    uint256 public constant BOND_BPS = 500;
    uint256 public constant BPS_DENOMINATOR = 10_000;

    enum State { NONE, OPEN, UPHELD, REJECTED, TIMED_OUT }

    struct Dispute {
        State state;
        address agent;
        address provider;
        uint256 bond;
        uint256 openedAt;
        bytes32 reasonHash;
    }

    address public immutable settlement;
    address public immutable resolver;
    IERC20 public immutable bondToken;
    /// @notice Bonds currently held; equals this contract's bond-token balance from disputes.
    uint256 public totalBondsHeld;

    mapping(bytes32 => mapping(uint256 => Dispute)) private _disputes;

    event DeliveryDisputed(bytes32 indexed allocationId, uint256 indexed providerIndex,
        address indexed agent, uint256 bond, bytes32 reasonHash);
    event DeliveryDisputeResolved(bytes32 indexed allocationId, uint256 indexed providerIndex,
        State outcome, address bondRecipient, uint256 bond);

    error NotResolver();
    error NotAgent();
    error NotDisputable(bytes32 allocationId, uint256 providerIndex);
    error DisputeWindowClosed(bytes32 allocationId, uint256 providerIndex);
    error DisputeNotOpen(bytes32 allocationId, uint256 providerIndex);
    error ResolutionPeriodEnded(bytes32 allocationId, uint256 providerIndex);
    error ResolutionPeriodActive(bytes32 allocationId, uint256 providerIndex);
    error BondTransferMismatch(uint256 expected, uint256 received);

    constructor(address settlement_, address resolver_, address bondToken_) {
        require(settlement_ != address(0) && resolver_ != address(0) && bondToken_ != address(0), "Zero address");
        settlement = settlement_;
        resolver = resolver_;
        bondToken = IERC20(bondToken_);
    }

    /// @notice Bond for a row amount: BOND_BPS rounded up, so any nonzero row needs a nonzero bond.
    function bondFor(uint256 amount) public pure returns (uint256) {
        return (amount * BOND_BPS + BPS_DENOMINATOR - 1) / BPS_DENOMINATOR;
    }

    /// @notice Whether settlement may pay an earned row recorded at `recordedAt`.
    function releasable(bytes32 allocationId, uint256 providerIndex, uint256 recordedAt)
        external view returns (bool) {
        State state = _disputes[allocationId][providerIndex].state;
        if (state == State.REJECTED || state == State.TIMED_OUT) return true;
        if (state != State.NONE) return false;
        return block.timestamp >= recordedAt + DISPUTE_WINDOW;
    }

    function getDispute(bytes32 allocationId, uint256 providerIndex) external view returns (Dispute memory) {
        return _disputes[allocationId][providerIndex];
    }

    /// @notice Open a dispute on an earned, unpaid row. Allowed while settlement is paused.
    function openDispute(bytes32 allocationId, uint256 providerIndex, bytes32 reasonHash)
        external nonReentrant {
        IComposedSettlement s = IComposedSettlement(settlement);
        IComposedSettlement.EarnedDeliveryV3 memory earned = s.getEarnedDeliveryV3(allocationId, providerIndex);
        IComposedSettlement.ProviderAlloc memory row = s.getProviderAlloc(allocationId, providerIndex);
        address agent = s.getComposedAllocation(allocationId).agent;
        if (msg.sender != agent) revert NotAgent();
        Dispute storage d = _disputes[allocationId][providerIndex];
        if (!earned.accepted || row.claimed || d.state != State.NONE ||
            IDisputeRefundTarget(settlement).refundedProviderShareV3(allocationId, providerIndex)) {
            revert NotDisputable(allocationId, providerIndex);
        }
        if (block.timestamp >= earned.recordedAt + DISPUTE_WINDOW) {
            revert DisputeWindowClosed(allocationId, providerIndex);
        }
        uint256 bond = bondFor(row.amount);
        _disputes[allocationId][providerIndex] =
            Dispute(State.OPEN, agent, row.provider, bond, block.timestamp, reasonHash);
        totalBondsHeld += bond;
        uint256 before = bondToken.balanceOf(address(this));
        // msg.sender == agent (checked above); pulling only from the caller.
        bondToken.safeTransferFrom(msg.sender, address(this), bond);
        uint256 received = bondToken.balanceOf(address(this)) - before;
        if (received != bond) revert BondTransferMismatch(bond, received);
        emit DeliveryDisputed(allocationId, providerIndex, agent, bond, reasonHash);
    }

    /// @notice Resolver decision before the deadline: uphold refunds the agent, reject releases payment.
    function resolve(bytes32 allocationId, uint256 providerIndex, bool uphold) external nonReentrant {
        if (msg.sender != resolver) revert NotResolver();
        Dispute storage d = _disputes[allocationId][providerIndex];
        if (d.state != State.OPEN) revert DisputeNotOpen(allocationId, providerIndex);
        if (block.timestamp >= d.openedAt + RESOLUTION_PERIOD) {
            revert ResolutionPeriodEnded(allocationId, providerIndex);
        }
        if (uphold) {
            d.state = State.UPHELD;
            IDisputeRefundTarget(settlement).refundUpheldDispute(allocationId, providerIndex);
            _releaseBond(allocationId, providerIndex, d, d.agent);
        } else {
            d.state = State.REJECTED;
            _releaseBond(allocationId, providerIndex, d, d.provider);
        }
    }

    /// @notice After the deadline anyone may finalize: payment is released, bond returns to the agent.
    function finalizeTimeout(bytes32 allocationId, uint256 providerIndex) external nonReentrant {
        Dispute storage d = _disputes[allocationId][providerIndex];
        if (d.state != State.OPEN) revert DisputeNotOpen(allocationId, providerIndex);
        if (block.timestamp < d.openedAt + RESOLUTION_PERIOD) {
            revert ResolutionPeriodActive(allocationId, providerIndex);
        }
        d.state = State.TIMED_OUT;
        _releaseBond(allocationId, providerIndex, d, d.agent);
    }

    function _releaseBond(bytes32 allocationId, uint256 providerIndex, Dispute storage d, address to) private {
        uint256 bond = d.bond;
        totalBondsHeld -= bond;
        bondToken.safeTransfer(to, bond);
        emit DeliveryDisputeResolved(allocationId, providerIndex, d.state, to, bond);
    }
}
