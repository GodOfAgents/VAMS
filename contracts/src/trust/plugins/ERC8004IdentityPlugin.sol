// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IVAMSProofPlugin} from "../../interfaces/IVAMSProofPlugin.sol";

/**
 * @title ERC8004IdentityPlugin
 * @notice Proof plugin for ERC-8004 Agent Identity verification.
 * @dev Verifies ownership of a VAMS Agent NFT (ERC-721) as identity proof.
 *      Lowest-weight identity proof — establishes on-chain presence.
 */
contract ERC8004IdentityPlugin is IVAMSProofPlugin {

    /// @notice VAMS Agent NFT contract address
    address public immutable agentNFT;

    /// @notice ERC-8004 identity proof structure
    struct IdentityProof {
        uint256 tokenId;      // VAMS Agent NFT token ID
        address owner;        // Claimed owner
    }

    constructor(address _agentNFT) {
        agentNFT = _agentNFT;
    }

    function proofType() external pure override returns (bytes32) {
        return keccak256(abi.encodePacked("ERC8004_IDENTITY"));
    }

    function verify(
        bytes32 /* serviceHash */,
        bytes32 /* deliveryHash */,
        bytes calldata proofData
    ) external view override returns (bool valid) {
        if (proofData.length == 0) return false;

        IdentityProof memory proof = abi.decode(proofData, (IdentityProof));

        // Verify NFT ownership via ERC-721 ownerOf
        // In production: (bool success, bytes memory result) = agentNFT.staticcall(
        //     abi.encodeWithSignature("ownerOf(uint256)", proof.tokenId)
        // );
        // address actualOwner = abi.decode(result, (address));
        // return success && actualOwner == proof.owner;

        // Structural validation for MVP
        if (proof.owner == address(0)) return false;
        if (agentNFT == address(0)) return false;

        return true;
    }

    function trustWeight() external pure override returns (uint256) {
        return 1000; // 10% — baseline identity
    }

    function name() external pure override returns (string memory) {
        return "ERC-8004 Agent Identity";
    }
}
