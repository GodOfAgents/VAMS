// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Votes.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/Nonces.sol";
import "./IVAMSToken.sol";

/**
 * @title VAMSToken
 * @author VAMS Protocol
 * @notice ERC-20 token powering the VAMS ecosystem
 * @dev Features:
 * - ERC20Burnable: Anyone can burn their tokens
 * - ERC20Permit: Gasless approvals (EIP-2612)
 * - ERC20Votes: Governance voting snapshots
 * - AccessControl: Role-based permissions
 * - Pausable: Emergency pause capability
 * - Anti-whale: Max wallet and daily transfer limits
 *
 * Token Specifications (from TOKENOMICS.md):
 * - Total Supply: 1,000,000,000 (1 billion)
 * - Decimals: 18
 * - Initial Circulating: 100,000,000 (10%) at TGE
 */
contract VAMSToken is 
    ERC20,
    ERC20Burnable,
    ERC20Permit,
    ERC20Votes,
    AccessControl,
    Pausable,
    IVAMSToken
{
    // ============ Constants ============

    /// @notice Role required to mint new tokens (assigned to staking contract)
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");

    /// @notice Role required to pause/unpause transfers
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    /// @notice Initial supply: 1 billion tokens with 18 decimals
    uint256 public constant INITIAL_SUPPLY = 1_000_000_000 * 1e18;

    /// @notice Six months in seconds (anti-whale duration)
    uint256 public constant SIX_MONTHS = 180 days;

    /// @notice Basis points denominator
    uint256 public constant BPS_DENOMINATOR = 10_000;

    /// @notice Maximum setting for maxWalletBps (10%)
    uint256 public constant MAX_WALLET_BPS_LIMIT = 1_000;

    /// @notice Maximum setting for dailyTransferLimitBps (5%)
    uint256 public constant DAILY_LIMIT_BPS_LIMIT = 500;

    /// @notice Annual mint cap: 2.5% of initial supply (25M $VAMS per year)
    uint256 public constant ANNUAL_MINT_CAP = 25_000_000 * 1e18;

    /// @notice Seconds per year (365.25 days)
    uint256 public constant SECONDS_PER_YEAR = 365.25 days;

    // ============ State Variables ============

    /// @inheritdoc IVAMSToken
    bool public override antiWhaleEnabled;

    /// @inheritdoc IVAMSToken
    uint256 public override maxWalletBps;

    /// @inheritdoc IVAMSToken
    uint256 public override dailyTransferLimitBps;

    /// @inheritdoc IVAMSToken
    uint256 public override antiWhaleEndTimestamp;

    /// @notice Mapping of addresses exempt from anti-whale limits
    mapping(address account => bool exempt) private _exemptFromLimits;

    /// @notice Mapping of daily transfer amounts per address
    mapping(address account => uint256 amount) private _dailyTransferAmount;

    /// @notice Mapping of last transfer day per address (day number since TGE)
    mapping(address account => uint256 day) private _lastTransferDay;

    /// @notice Minted amount in the current year
    uint256 public mintedThisYear;

    /// @notice Start timestamp of current minting year
    uint256 public currentMintYearStart;

    /// @notice TGE timestamp (for calculating day number)
    uint256 public immutable tgeTimestamp;

    // ============ Constructor ============

    /**
     * @notice Deploy the VAMS token
     * @param admin Initial admin address (receives DEFAULT_ADMIN_ROLE)
     * @param treasury Address to receive initial supply
     */
    constructor(
        address admin,
        address treasury
    ) ERC20("VAMS", "VAMS") ERC20Permit("VAMS") {
        if (admin == address(0)) revert ZeroAddress();
        if (treasury == address(0)) revert ZeroAddress();

        // Grant roles
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);
        _grantRole(MINTER_ROLE, admin); // Admin can mint initial supply adjustment if needed

        // Set anti-whale parameters
        antiWhaleEnabled = true;
        maxWalletBps = 500; // 5%
        dailyTransferLimitBps = 100; // 1%
        tgeTimestamp = block.timestamp;
        antiWhaleEndTimestamp = block.timestamp + SIX_MONTHS;

        // Exempt key addresses by default
        _exemptFromLimits[admin] = true;
        _exemptFromLimits[treasury] = true;
        _exemptFromLimits[address(0)] = true; // Burn address
        _exemptFromLimits[address(this)] = true;

        // Initialize mint tracking
        currentMintYearStart = block.timestamp;

        // Mint initial supply to treasury
        _mint(treasury, INITIAL_SUPPLY);
    }

    // ============ Minting ============

    /// @inheritdoc IVAMSToken
    function mint(address to, uint256 amount) external override onlyRole(MINTER_ROLE) {
        if (to == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();
        
        // Rotate year if needed — advance by SECONDS_PER_YEAR, not block.timestamp
        // to prevent gap-gaming (skipping years compresses the cap window)
        if (block.timestamp >= currentMintYearStart + SECONDS_PER_YEAR) {
            currentMintYearStart += SECONDS_PER_YEAR;
            mintedThisYear = 0;
        }
        
        // Enforce annual mint cap (2.5% = 25M $VAMS/year)
        if (mintedThisYear + amount > ANNUAL_MINT_CAP) {
            revert AnnualMintCapExceeded(mintedThisYear + amount, ANNUAL_MINT_CAP);
        }
        
        mintedThisYear += amount;
        _mint(to, amount);
    }

    // ============ Pausable ============

    /// @notice Pause all token transfers
    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    /// @notice Unpause token transfers
    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    // ============ Anti-Whale Management ============

    /// @inheritdoc IVAMSToken
    function setAntiWhaleEnabled(bool enabled) external override onlyRole(DEFAULT_ADMIN_ROLE) {
        antiWhaleEnabled = enabled;
        emit AntiWhaleToggled(enabled);
    }

    /// @inheritdoc IVAMSToken
    function addExemptAddress(address account) external override onlyRole(DEFAULT_ADMIN_ROLE) {
        if (account == address(0)) revert ZeroAddress();
        _exemptFromLimits[account] = true;
        emit AddressExempted(account, true);
    }

    /// @inheritdoc IVAMSToken
    function removeExemptAddress(address account) external override onlyRole(DEFAULT_ADMIN_ROLE) {
        if (account == address(0)) revert ZeroAddress();
        _exemptFromLimits[account] = false;
        emit AddressExempted(account, false);
    }

    /// @inheritdoc IVAMSToken
    function setMaxWalletBps(uint256 newMaxBps) external override onlyRole(DEFAULT_ADMIN_ROLE) {
        if (newMaxBps > MAX_WALLET_BPS_LIMIT) {
            revert ExceedsMaxWallet(address(0), newMaxBps, MAX_WALLET_BPS_LIMIT);
        }
        maxWalletBps = newMaxBps;
        emit MaxWalletUpdated(newMaxBps);
    }

    /// @inheritdoc IVAMSToken
    function setDailyTransferLimitBps(uint256 newLimitBps) external override onlyRole(DEFAULT_ADMIN_ROLE) {
        if (newLimitBps > DAILY_LIMIT_BPS_LIMIT) {
            revert ExceedsDailyLimit(address(0), newLimitBps, DAILY_LIMIT_BPS_LIMIT);
        }
        dailyTransferLimitBps = newLimitBps;
        emit DailyLimitUpdated(newLimitBps);
    }

    // ============ View Functions ============

    /// @inheritdoc IVAMSToken
    function isExemptFromLimits(address account) external view override returns (bool) {
        return _exemptFromLimits[account];
    }

    /// @inheritdoc IVAMSToken
    function getDailyTransferAmount(address account) external view override returns (uint256) {
        uint256 currentDay = _getCurrentDay();
        if (_lastTransferDay[account] != currentDay) {
            return 0; // New day, no transfers yet
        }
        return _dailyTransferAmount[account];
    }

    /// @inheritdoc IVAMSToken
    function getLastTransferTimestamp(address account) external view override returns (uint256) {
        return tgeTimestamp + (_lastTransferDay[account] * 1 days);
    }

    /// @inheritdoc IVAMSToken
    function maxWalletAmount() public view override returns (uint256) {
        return (totalSupply() * maxWalletBps) / BPS_DENOMINATOR;
    }

    /// @inheritdoc IVAMSToken
    function dailyTransferLimit() public view override returns (uint256) {
        return (totalSupply() * dailyTransferLimitBps) / BPS_DENOMINATOR;
    }

    // ============ Internal Functions ============

    /**
     * @notice Get current day number since TGE
     * @return Day number (0-indexed)
     */
    function _getCurrentDay() internal view returns (uint256) {
        return (block.timestamp - tgeTimestamp) / 1 days;
    }

    /**
     * @notice Check and enforce anti-whale restrictions
     * @param from Sender address
     * @param to Recipient address
     * @param amount Transfer amount
     */
    function _checkAntiWhale(address from, address to, uint256 amount) internal {
        // Skip if anti-whale is disabled
        if (!antiWhaleEnabled) return;

        // Skip if anti-whale period has ended
        if (block.timestamp >= antiWhaleEndTimestamp) return;

        // Skip if sender is exempt
        if (_exemptFromLimits[from]) return;

        // Skip if recipient is exempt
        if (_exemptFromLimits[to]) return;

        // Check max wallet (recipient)
        if (to != address(0)) {
            uint256 maxWallet = maxWalletAmount();
            uint256 recipientBalance = balanceOf(to) + amount;
            if (recipientBalance > maxWallet) {
                revert ExceedsMaxWallet(to, recipientBalance, maxWallet);
            }
        }

        // Check daily transfer limit (sender)
        if (from != address(0)) {
            uint256 currentDay = _getCurrentDay();
            uint256 limit = dailyTransferLimit();

            // Reset if new day
            if (_lastTransferDay[from] != currentDay) {
                _lastTransferDay[from] = currentDay;
                _dailyTransferAmount[from] = 0;
            }

            uint256 newDailyAmount = _dailyTransferAmount[from] + amount;
            if (newDailyAmount > limit) {
                revert ExceedsDailyLimit(from, newDailyAmount, limit);
            }

            _dailyTransferAmount[from] = newDailyAmount;
        }
    }

    // ============ Overrides ============

    /**
     * @notice Hook called before any token transfer
     * @dev Enforces pause and anti-whale restrictions
     */
    function _update(
        address from,
        address to,
        uint256 amount
    ) internal override(ERC20, ERC20Votes) {
        // Check pause
        if (paused()) {
            // Allow minting even when paused (for staking rewards)
            if (from != address(0)) {
                revert("Pausable: paused");
            }
        }

        // Check anti-whale
        _checkAntiWhale(from, to, amount);

        super._update(from, to, amount);
    }

    /**
     * @notice Returns the current nonce for an account
     * @dev Required by ERC20Permit
     */
    function nonces(address owner) public view override(ERC20Permit, Nonces) returns (uint256) {
        return super.nonces(owner);
    }

    /**
     * @notice Check if contract supports an interface
     * @dev Required for AccessControl
     */
    function supportsInterface(bytes4 interfaceId) 
        public 
        view 
        override(AccessControl) 
        returns (bool) 
    {
        return super.supportsInterface(interfaceId);
    }
}
