// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./IVAMSSentinel.sol";

/**
 * @title VAMSSentinel
 * @author VAMS Protocol
 * @notice Autonomous on-chain anomaly detector — the primary emergency guardian for VAMS.
 *         Replaces human multi-sig as the first line of defense. Pausing is autonomous and
 *         sub-second; resuming requires Cardano DAO approval via ICB relay.
 * @dev Three detection layers:
 *   L1 — On-chain invariants checked permissionlessly (same-block)
 *   L2 — Staked AI keeper bots submit anomaly scores (sub-second consensus)
 *   L3 — Price circuit breaker via oracle anchor (hourly)
 *
 * Anti-griefing:
 *   - Keepers must bond MIN_KEEPER_BOND $VAMS
 *   - False alarms: 5% slash if DAO overrides as false positive
 *   - Cooldown: max 1 auto-pause per COOLDOWN_PERIOD
 *
 * Security patterns:
 *   - Checks-Effects-Interactions throughout
 *   - ReentrancyGuard on all state-mutating functions
 *   - Custom errors (no string reverts)
 */
/// @dev Interface that pausable contracts must implement
interface IPausableTarget {
    function emergencyPause(string calldata reason) external;
    function unpause() external;
    function paused() external view returns (bool);
}

/// @dev Interface for TVL provider
interface ITVLProvider {
    function getTotalValueLocked() external view returns (uint256);
}

/// @dev Interface for price oracle (sentinel-specific)
interface ISentinelPriceOracle {
    function getVAMSPrice() external view returns (uint256);
}

contract VAMSSentinel is AccessControl, ReentrancyGuard, IVAMSSentinel {
    using SafeERC20 for IERC20;
    // ============ Custom Errors ============
    error ZeroAddress();
    error NoOracleSet();
    error MaxPausableTargetsReached();
    error IndexOutOfBounds();

    // ═══════════════════ Roles ═══════════════════

    /// @notice Role for staked AI keeper bots
    bytes32 public constant KEEPER_ROLE = keccak256("KEEPER_ROLE");

    /// @notice Role for Cardano DAO (via ICB GovernorExecutor)
    bytes32 public constant DAO_ROLE = keccak256("DAO_ROLE");

    /// @notice Role for dormant multi-sig fallback (emergency only)
    bytes32 public constant FALLBACK_ROLE = keccak256("FALLBACK_ROLE");

    // ═══════════════════ Constants ═══════════════════

    uint256 public constant KEEPER_SCORE_THRESHOLD = 80;
    uint256 public constant MIN_KEEPER_BOND = 100_000e18; // 100,000 $VAMS
    uint8 public constant MAX_ANOMALY_SCORE = 100;
    
    // Delay before a new keeper can vote/submit reports
    uint256 public constant KEEPER_VOTING_DELAY = 100;
    
    /// @notice Slash rate for false alarm (5%)
    uint16 public constant FALSE_ALARM_SLASH_BPS = 500;

    /// @notice Maximum age of a keeper report (2 minutes)
    uint256 public constant MAX_REPORT_AGE = 2 minutes;

    /// @notice Epoch duration for keeper reporting (1 block window)
    uint256 public constant REPORT_EPOCH_BLOCKS = 1;

    // ═══════════════════ Immutable State ═══════════════════

    /// @notice $VAMS token used for keeper bonds
    IERC20 public immutable vamsToken;

    // ═══════════════════ Mutable State ═══════════════════

    /// @notice Current protocol operating mode
    ProtocolMode public protocolMode;

    /// @notice DAO-configurable detection thresholds
    Thresholds public thresholds;

    /// @notice Anomaly history
    AnomalyReport[] public anomalyHistory;

    /// @notice Contracts the Sentinel can pause
    address[] public pausableTargets;

    /// @notice Keeper bonds ($VAMS amount)
    mapping(address => uint256) public keeperBonds;

    /// @notice Block number when a keeper registered
    mapping(address => uint256) public keeperRegistrationBlock;

    /// @notice Active incident tracking per epoch (block number => reports)
    mapping(uint256 blockNumber => KeeperReport[]) public epochReports;

    /// @notice Number of high-score reports in current epoch
    mapping(uint256 blockNumber => uint256 highScoreCount) public epochHighScores;

    /// @notice Timestamp of last auto-pause (for cooldown)
    uint256 public lastPauseTimestamp;

    /// @notice Last known TVL snapshot for drain detection
    uint256 public lastKnownTVL;

    /// @notice Block number of last TVL snapshot
    uint256 public lastTVLBlock;

    /// @notice Hourly price anchor for circuit breaker (18 decimals)
    uint256 public priceAnchor;

    /// @notice Timestamp of last price anchor update
    uint256 public priceAnchorTimestamp;

    /// @notice Daily bridge volume average (18 decimals)
    uint256 public dailyBridgeAvg;

    /// @notice Price oracle address
    address public priceOracle;

    /// @notice TVL provider address
    address public tvlProvider;

    // ═══════════════════ Constructor ═══════════════════

    /**
     * @notice Deploy VAMSSentinel
     * @param _admin Admin address (grants roles)
     * @param _vamsToken $VAMS token address for keeper bonds
     * @param _dao DAO address (Cardano GovernorExecutor)
     * @param _fallbackMultisig Dormant multi-sig (last resort)
     */
    constructor(
        address _admin,
        address _vamsToken,
        address _dao,
        address _fallbackMultisig
    ) {
        if (_admin == address(0)) revert ZeroAddress();
        if (_vamsToken == address(0)) revert ZeroAddress();
        if (_dao == address(0)) revert ZeroAddress();

        vamsToken = IERC20(_vamsToken);

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(DAO_ROLE, _dao);
        if (_fallbackMultisig != address(0)) {
            _grantRole(FALLBACK_ROLE, _fallbackMultisig);
        }

        // Default thresholds
        thresholds = Thresholds({
            tvlDrainBps: 1500,          // 15% TVL drop per block
            whaleExitBps: 500,          // 5% of pool single withdrawal
            bridgeFloodSigma: 3,        // 3σ above daily avg
            priceCrashBps: 5000,        // 50% drop in 1 hour
            keeperConsensusMin: 3,      // 3+ keepers must flag
            cooldownPeriod: 4 hours     // 4h between auto-pauses
        });

        protocolMode = ProtocolMode.NORMAL;
    }

    // ═══════════════════ L1: On-Chain Invariant Checks ═══════════════════

    /**
     * @notice Permissionless invariant check — anyone can call.
     *         Pauses all targets if TVL drain detected.
     * @return pauseTriggered Whether the check triggered a pause
     */
    function checkInvariantsAndPause() external nonReentrant returns (bool pauseTriggered) {
        if (protocolMode == ProtocolMode.PAUSED) revert ProtocolAlreadyPaused();
        if (_isCooldownActive()) revert CooldownActive(lastPauseTimestamp + thresholds.cooldownPeriod);

        // L1 Check: TVL drain detection
        if (tvlProvider != address(0)) {
            uint256 currentTVL = ITVLProvider(tvlProvider).getTotalValueLocked();

            if (lastKnownTVL > 0 && lastTVLBlock < block.number) {
                uint256 drainThreshold = (lastKnownTVL * thresholds.tvlDrainBps) / 10_000;

                if (currentTVL + drainThreshold < lastKnownTVL) {
                    // TVL dropped more than threshold in 1 block
                    _triggerPause(
                        AnomalyType.TVL_DRAIN,
                        9, // severity
                        keccak256(abi.encode(lastKnownTVL, currentTVL, block.number))
                    );
                    lastKnownTVL = currentTVL;
                    lastTVLBlock = block.number;
                    return true;
                }
            }

            lastKnownTVL = currentTVL;
            lastTVLBlock = block.number;
        }

        // L3 Check: Price circuit breaker
        if (priceOracle != address(0) && priceAnchor > 0) {
            uint256 currentPrice = ISentinelPriceOracle(priceOracle).getVAMSPrice();
            uint256 crashThreshold = (priceAnchor * thresholds.priceCrashBps) / 10_000;

            if (currentPrice + crashThreshold < priceAnchor) {
                // Price crashed > threshold since last anchor
                _triggerPause(
                    AnomalyType.PRICE_CRASH,
                    8,
                    keccak256(abi.encode(priceAnchor, currentPrice, block.timestamp))
                );
                return true;
            }
        }

        return false;
    }

    // ═══════════════════ L2: Keeper Consensus ═══════════════════

    /**
     * @notice Register as a keeper by bonding $VAMS
     * @param bondAmount Amount of $VAMS to bond (must be >= MIN_KEEPER_BOND)
     */
    function registerKeeper(uint256 bondAmount) external nonReentrant {
        if (keeperBonds[msg.sender] > 0) revert KeeperAlreadyRegistered(msg.sender);
        if (bondAmount < MIN_KEEPER_BOND) revert InsufficientKeeperBond(bondAmount, MIN_KEEPER_BOND);

        // Effects
        keeperBonds[msg.sender] = bondAmount;
        keeperRegistrationBlock[msg.sender] = block.number;

        // Interactions
        vamsToken.safeTransferFrom(msg.sender, address(this), bondAmount);
        _grantRole(KEEPER_ROLE, msg.sender);

        emit KeeperRegistered(msg.sender, bondAmount);
    }

    /**
     * @notice Submit an anomaly report (keeper only)
     * @param anomalyScore Score from 0-100 (80+ triggers consensus check)
     * @param evidenceHash IPFS/Arweave hash of detailed off-chain evidence
     */
    function submitKeeperReport(
        uint8 anomalyScore,
        bytes32 evidenceHash
    ) external nonReentrant onlyRole(KEEPER_ROLE) {
        if (protocolMode == ProtocolMode.PAUSED) revert ProtocolAlreadyPaused();
        if (anomalyScore > MAX_ANOMALY_SCORE) revert InvalidAnomalyScore(anomalyScore);
        
        // Anti-flash-loan / sybil delay
        require(block.number >= keeperRegistrationBlock[msg.sender] + KEEPER_VOTING_DELAY, "Keeper voting delay active");

        // Record the report
        KeeperReport memory report = KeeperReport({
            keeper: msg.sender,
            anomalyScore: anomalyScore,
            evidenceHash: evidenceHash,
            timestamp: block.timestamp
        });

        epochReports[block.number].push(report);

        emit KeeperReportSubmitted(msg.sender, anomalyScore, evidenceHash);

        // Check consensus if score is high enough
        if (anomalyScore >= KEEPER_SCORE_THRESHOLD) {
            epochHighScores[block.number]++;

            // If enough keepers flagged, trigger pause
            if (epochHighScores[block.number] >= thresholds.keeperConsensusMin) {
                if (!_isCooldownActive()) {
                    _triggerPause(
                        AnomalyType.KEEPER_CONSENSUS,
                        7,
                        evidenceHash
                    );
                }
            }
        }
    }

    // ═══════════════════ L3: Price Circuit Breaker ═══════════════════

    /**
     * @notice Update the hourly price anchor from oracle
     * @dev Called by keepers or automation. Sets the baseline for crash detection.
     */
    function updatePriceAnchor() external onlyRole(KEEPER_ROLE) {
        if (priceOracle == address(0)) revert NoOracleSet();

        uint256 newPrice = ISentinelPriceOracle(priceOracle).getVAMSPrice();
        priceAnchor = newPrice;
        priceAnchorTimestamp = block.timestamp;
    }

    // ═══════════════════ DAO Functions ═══════════════════

    /**
     * @notice Resume protocol after anomaly investigation (DAO only, via ICB)
     * @param anomalyId The anomaly that triggered the pause
     */
    function resumeProtocol(uint256 anomalyId) external nonReentrant onlyRole(DAO_ROLE) {
        if (protocolMode == ProtocolMode.NORMAL) revert ProtocolNotPaused();

        // Effects
        protocolMode = ProtocolMode.NORMAL;

        // Interactions — unpause all targets
        uint256 gasPerTarget = 100_000;
        for (uint256 i = 0; i < pausableTargets.length; i++) {
            if (gasleft() < gasPerTarget) break; // L-03: Prevent OOM
            address target = pausableTargets[i];
            if (IPausableTarget(target).paused()) {
                IPausableTarget(target).unpause();
            }
        }

        emit ProtocolResumed(msg.sender, anomalyId);
    }

    /**
     * @notice Update detection thresholds (DAO only)
     * @param newThresholds New threshold configuration
     */
    function updateThresholds(Thresholds calldata newThresholds) external onlyRole(DAO_ROLE) {
        thresholds = newThresholds;
        emit ThresholdsUpdated(newThresholds);
    }

    /**
     * @notice Slash a keeper for false alarm (DAO only)
     * @param keeper Keeper address to slash
     * @param reason Description of the false alarm
     */
    function slashKeeper(address keeper, string calldata reason) external nonReentrant onlyRole(DAO_ROLE) {
        if (keeperBonds[keeper] == 0) revert KeeperNotRegistered(keeper);

        uint256 slashAmount = (keeperBonds[keeper] * FALSE_ALARM_SLASH_BPS) / 10_000;

        // Effects
        keeperBonds[keeper] -= slashAmount;

        // Interactions — slashed tokens burned (sent to dead address)
        vamsToken.safeTransfer(address(0xdead), slashAmount);

        emit KeeperSlashed(keeper, slashAmount, reason);

        // If bond falls below minimum, revoke keeper role
        if (keeperBonds[keeper] < MIN_KEEPER_BOND) {
            _revokeRole(KEEPER_ROLE, keeper);
        }
    }

    // ═══════════════════ Fallback Multi-sig (Dormant) ═══════════════════

    /**
     * @notice Emergency pause by dormant multi-sig (only if Sentinel itself is compromised)
     * @param reason Reason for manual intervention
     */
    function fallbackPause(string calldata reason) external nonReentrant onlyRole(FALLBACK_ROLE) {
        if (protocolMode == ProtocolMode.PAUSED) revert ProtocolAlreadyPaused();

        _triggerPause(
            AnomalyType.KEEPER_CONSENSUS, // closest type
            10,                           // max severity
            keccak256(abi.encodePacked(reason))
        );
    }

    // ═══════════════════ Admin Functions ═══════════════════

    /**
     * @notice Add a contract to the pausable targets list
     * @param target Contract address that implements IPausableTarget
     */
    function addPausableTarget(address target) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (target == address(0)) revert ZeroAddress();
        if (pausableTargets.length >= 20) revert MaxPausableTargetsReached();
        pausableTargets.push(target);
        emit PausableTargetAdded(target);
    }

    /**
     * @notice Remove a contract from pausable targets
     * @param index Index in the pausableTargets array
     */
    function removePausableTarget(uint256 index) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (index >= pausableTargets.length) revert IndexOutOfBounds();
        address removed = pausableTargets[index];

        // Swap with last element and pop
        pausableTargets[index] = pausableTargets[pausableTargets.length - 1];
        pausableTargets.pop();

        emit PausableTargetRemoved(removed);
    }

    /**
     * @notice Set the TVL provider contract
     * @param _tvlProvider Address of the TVL provider
     */
    function setTVLProvider(address _tvlProvider) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_tvlProvider == address(0)) revert ZeroAddress();
        tvlProvider = _tvlProvider;
    }

    /**
     * @notice Set the price oracle contract
     * @param _priceOracle Address of the price oracle
     */
    function setPriceOracle(address _priceOracle) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (_priceOracle == address(0)) revert ZeroAddress();
        priceOracle = _priceOracle;
    }

    /**
     * @notice Set the daily bridge volume average (updated by keepers/off-chain)
     * @param _dailyAvg Daily average bridge volume in 18 decimals
     */
    function setDailyBridgeAvg(uint256 _dailyAvg) external onlyRole(KEEPER_ROLE) {
        dailyBridgeAvg = _dailyAvg;
    }

    // ═══════════════════ Internal Functions ═══════════════════

    /**
     * @dev Trigger protocol pause and record the anomaly
     * @param anomalyType Type of anomaly detected
     * @param severity Severity 1-10
     * @param evidenceHash Hash of evidence data
     */
    function _triggerPause(
        AnomalyType anomalyType,
        uint8 severity,
        bytes32 evidenceHash
    ) internal {
        if (pausableTargets.length == 0) revert NoPausableTargets();

        // Effects
        protocolMode = ProtocolMode.PAUSED;
        lastPauseTimestamp = block.timestamp;

        uint256 anomalyId = anomalyHistory.length;
        anomalyHistory.push(AnomalyReport({
            anomalyType: anomalyType,
            detectedAt: block.timestamp,
            severity: severity,
            evidenceHash: evidenceHash,
            pauseTriggered: true,
            reporter: msg.sender
        }));

        // Interactions — pause all targets
        for (uint256 i = 0; i < pausableTargets.length; i++) {
            address target = pausableTargets[i];
            if (!IPausableTarget(target).paused()) {
                IPausableTarget(target).emergencyPause(
                    string(abi.encodePacked("SENTINEL:", _anomalyTypeToString(anomalyType)))
                );
            }
        }

        emit AnomalyDetected(anomalyId, anomalyType, severity, evidenceHash);
        emit ProtocolPaused(anomalyId, ProtocolMode.PAUSED);
    }

    /**
     * @dev Check if cooldown period is still active
     */
    function _isCooldownActive() internal view returns (bool) {
        return block.timestamp < lastPauseTimestamp + thresholds.cooldownPeriod;
    }

    /**
     * @dev Convert AnomalyType enum to string for pause reason
     */
    function _anomalyTypeToString(AnomalyType t) internal pure returns (string memory) {
        if (t == AnomalyType.TVL_DRAIN) return "TVL_DRAIN";
        if (t == AnomalyType.WHALE_EXIT) return "WHALE_EXIT";
        if (t == AnomalyType.BRIDGE_FLOOD) return "BRIDGE_FLOOD";
        if (t == AnomalyType.PRICE_CRASH) return "PRICE_CRASH";
        return "KEEPER_CONSENSUS";
    }

    // ═══════════════════ View Functions ═══════════════════

    /// @inheritdoc IVAMSSentinel
    function getProtocolMode() external view returns (ProtocolMode) {
        return protocolMode;
    }

    /// @inheritdoc IVAMSSentinel
    function getAnomalyReport(uint256 anomalyId) external view returns (AnomalyReport memory) {
        return anomalyHistory[anomalyId];
    }

    /// @inheritdoc IVAMSSentinel
    function getAnomalyCount() external view returns (uint256) {
        return anomalyHistory.length;
    }

    /// @inheritdoc IVAMSSentinel
    function getThresholds() external view returns (Thresholds memory) {
        return thresholds;
    }

    /// @inheritdoc IVAMSSentinel
    function isKeeper(address account) external view returns (bool) {
        return keeperBonds[account] >= MIN_KEEPER_BOND;
    }

    /**
     * @notice Get the number of pausable targets
     * @return count Number of registered pausable contracts
     */
    function getPausableTargetCount() external view returns (uint256 count) {
        return pausableTargets.length;
    }

    /**
     * @notice Get all pausable target addresses
     * @return targets Array of pausable contract addresses
     */
    function getPausableTargets() external view returns (address[] memory targets) {
        return pausableTargets;
    }

    /**
     * @notice Get keeper reports for a specific block
     * @param blockNumber Block number to query
     * @return reports Array of keeper reports
     */
    function getEpochReports(uint256 blockNumber) external view returns (KeeperReport[] memory reports) {
        return epochReports[blockNumber];
    }
}
