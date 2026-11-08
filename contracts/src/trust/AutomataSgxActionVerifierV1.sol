// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {ActionContextV1} from "./ActionContextV1.sol";
import {RootSignatureV1} from "./RootSignatureV1.sol";
import {IActionEvidenceVerifier} from "./IActionEvidenceVerifier.sol";

// ABI-compatible types from Automata's MIT-licensed IQuoteVerifier/CommonStruct.
// Source identities and qualification requirements are retained in the repair ADR.
struct DcapHeaderV1 {
    uint16 version; bytes2 attestationKeyType; bytes4 teeType; bytes2 qeSvn;
    bytes2 pceSvn; bytes16 qeVendorId; bytes20 userData;
}
interface IAutomataQuoteVerifierV1 {
    function quoteVersion() external view returns (uint16);
    function pccsRouter() external view returns (address);
    function verifyQuote(DcapHeaderV1 calldata header, bytes calldata quote, uint32 evaluation)
        external view returns (bool, bytes memory);
}

/// @notice SGX v3 only. No Nitro, TDX or hash-only fallback is implied.
contract AutomataSgxActionVerifierV1 is IActionEvidenceVerifier {
    IAutomataQuoteVerifierV1 public immutable verifier;
    bytes32 public immutable verifierCodeHash;
    address public immutable collateralRouter;
    bytes32 public immutable collateralRouterCodeHash;
    bytes32 public immutable enclaveMeasurement;
    bytes32 public immutable signerMeasurement;
    bytes32 public immutable runtimeId;
    uint16 public immutable minimumSvn;
    uint32 public immutable tcbEvaluation;

    constructor(address backend, bytes32 backendHash, address router, bytes32 routerHash,
        bytes32 enclave, bytes32 signer, bytes32 runtime, uint16 svn, uint32 evaluation) {
        require(backend.code.length > 0 && backend.codehash == backendHash, "Verifier identity mismatch");
        require(router.code.length > 0 && router.codehash == routerHash, "Collateral identity mismatch");
        require(enclave != 0 && signer != 0 && runtime != 0 && evaluation > 0, "Missing attestation policy");
        verifier = IAutomataQuoteVerifierV1(backend);
        require(verifier.quoteVersion() == 3 && verifier.pccsRouter() == router, "Unsupported DCAP backend");
        verifierCodeHash = backendHash; collateralRouter = router; collateralRouterCodeHash = routerHash;
        enclaveMeasurement = enclave; signerMeasurement = signer; runtimeId = runtime;
        minimumSvn = svn; tcbEvaluation = evaluation;
    }

    function verifyAction(ActionContextV1.Context calldata c, bytes32 outputHash, bytes calldata evidence)
        external view returns (bool) {
        if (!ActionContextV1.valid(c) || c.rootScheme != 1 || c.runtimeId != runtimeId || outputHash == 0 ||
            c.issuedAt > block.timestamp || c.expiresAt <= block.timestamp || c.expiresAt - c.issuedAt > 10 minutes ||
            address(verifier).codehash != verifierCodeHash || collateralRouter.codehash != collateralRouterCodeHash ||
            !_backendMetadataMatches()) return false;
        (bytes memory quote, bytes memory rootSignature) = abi.decode(evidence, (bytes, bytes));
        if (keccak256(evidence) != keccak256(abi.encode(quote, rootSignature))) return false;
        return _verifyQuote(c, outputHash, quote, rootSignature);
    }

    /// @dev Code identity does not freeze a backend's storage/configuration.
    ///      These direct links must still match; transitive collateral/TCB and
    ///      actual backend qualification remain separate deployment requirements.
    function _backendMetadataMatches() private view returns (bool) {
        (bool ok, uint256 version) = _backendWord(IAutomataQuoteVerifierV1.quoteVersion.selector);
        if (!ok || version != 3) return false;
        uint256 router;
        (ok, router) = _backendWord(IAutomataQuoteVerifierV1.pccsRouter.selector);
        return ok && router == uint256(uint160(collateralRouter));
    }

    /// @dev Exact canonical ABI word; never copy unbounded getter returndata.
    ///      No fixed gas allowance is invented for an unqualified backend.
    function _backendWord(bytes4 selector) private view returns (bool ok, uint256 value) {
        address target = address(verifier);
        uint256 signature = uint32(selector);
        assembly ("memory-safe") {
            mstore(0, shl(224, signature))
            ok := staticcall(gas(), target, 0, 4, 0, 32)
            ok := and(ok, eq(returndatasize(), 32))
            value := mload(0)
        }
    }

    function _verifyQuote(ActionContextV1.Context memory c, bytes32 outputHash, bytes memory quote,
        bytes memory rootSignature) internal view returns (bool) {
        if (quote.length < 1020 || quote.length > 65_000) return false;
        // Reject unverified trailing quote material accepted by some upstream parsers.
        uint256 authSize = uint8(quote[432]) | (uint256(uint8(quote[433])) << 8) |
            (uint256(uint8(quote[434])) << 16) | (uint256(uint8(quote[435])) << 24);
        if (quote.length != 436 + authSize) return false;
        DcapHeaderV1 memory h;
        h.version = uint16(uint8(quote[0])) | (uint16(uint8(quote[1])) << 8);
        h.attestationKeyType = bytes2(_at(quote, 2)); h.teeType = bytes4(_at(quote, 4));
        h.qeSvn = bytes2(_at(quote, 8)); h.pceSvn = bytes2(_at(quote, 10));
        h.qeVendorId = bytes16(_at(quote, 12)); h.userData = bytes20(_at(quote, 28));
        if (h.version != 3 || h.attestationKeyType != 0x0200 || h.teeType != 0x00000000 ||
            h.qeVendorId != 0x939a7233f79c4ca9940a0db3957f0607) return false;
        (bool ok, bytes memory verified) = verifier.verifyQuote(h, quote, tcbEvaluation);
        // SGX v3 output: BE version[2], body type[2], TCB[1], FMSPC[6], report[384].
        if (!ok || verified.length != 395 || bytes2(_at(verified,0)) != 0x0003 ||
            bytes2(_at(verified,2)) != 0x0001 || uint8(verified[4]) != 0) return false;
        // SGX report attributes.flags is little endian; bit 1 denotes DEBUG.
        if ((uint8(verified[59]) & 2) != 0) return false;
        if (_at(verified,75) != enclaveMeasurement || _at(verified,139) != signerMeasurement) return false;
        uint16 svn = uint16(uint8(verified[269])) | (uint16(uint8(verified[270])) << 8);
        if (svn < minimumSvn) return false;
        bytes32 contextHash = ActionContextV1.digest(c);
        bytes32 binding = sha256(abi.encodePacked("VAMS:SGX-ACTION:v1", hex"00",
            abi.encode(contextHash, c.actorRoot, outputHash)));
        if (_at(verified,331) != binding || _at(verified,363) != 0) return false;
        bytes32 control = sha256(abi.encodePacked("VAMS:SGX-ROOT-CONTROL:v1", hex"00",
            abi.encode(contextHash, outputHash, sha256(quote))));
        return RootSignatureV1.valid(address(uint160(uint256(c.actorRoot))), control, rootSignature);
    }

    function _at(bytes memory data, uint256 offset) private pure returns (bytes32 word) {
        require(offset + 32 <= data.length, "Truncated DCAP data");
        assembly ("memory-safe") { word := mload(add(add(data, 32), offset)) }
    }
}
