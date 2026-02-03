// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/**
 * @title MockVAMSToken
 * @notice Mock VAMS token for testing purposes
 * @dev Extends ERC20 with mint/burn capabilities for testing
 */
contract MockVAMSToken is ERC20 {
    uint8 private _decimals = 18;
    
    constructor() ERC20("VAMS Token", "VAMS") {
        // Mint initial supply to deployer for testing
        _mint(msg.sender, 1_000_000_000 * 10**18);
    }
    
    /**
     * @notice Mint tokens to any address (for testing)
     * @param to Recipient address
     * @param amount Amount to mint
     */
    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
    
    /**
     * @notice Burn tokens from any address (for testing)
     * @param from Address to burn from
     * @param amount Amount to burn
     */
    function burn(address from, uint256 amount) external {
        _burn(from, amount);
    }
    
    /**
     * @notice Set custom decimals (for edge case testing)
     * @param newDecimals New decimal value
     */
    function setDecimals(uint8 newDecimals) external {
        _decimals = newDecimals;
    }
    
    function decimals() public view override returns (uint8) {
        return _decimals;
    }
}
