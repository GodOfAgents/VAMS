// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import {ActionContextV1} from "./ActionContextV1.sol";
import {RootSignatureV1} from "./RootSignatureV1.sol";
import {IActionEvidenceVerifier} from "./IActionEvidenceVerifier.sol";

interface IEzklFixedVerifierV1 {
    function verifyProof(bytes calldata proof, uint256[] calldata instances) external view returns (bool);
}

/// @notice Adapter for a separately qualified fixed 4-input / 2-output ONNX circuit.
/// @dev Public layout is context[8 u32], input[4 fields], context-copy[8 u32], output[2 fields].
/// Circuit qualification must prove the context-copy constraints and exact model,
/// quantization, field mapping and public tensor layout. No circuit is generated here.
contract EzklActionVerifierV1 is IActionEvidenceVerifier {
    uint256 public constant FIELD = 21888242871839275222246405745257275088548364400416034343698204186575808495617;
    IEzklFixedVerifierV1 public immutable verifier;
    bytes32 public immutable verifierCodeHash;
    bytes32 public immutable modelHash;
    bytes32 public immutable circuitManifestHash;

    constructor(address backend, bytes32 backendHash, bytes32 model, bytes32 circuitManifest) {
        require(backend.code.length > 0 && backend.codehash == backendHash, "Verifier identity mismatch");
        require(model != 0 && circuitManifest != 0, "Missing circuit identity");
        verifier = IEzklFixedVerifierV1(backend); verifierCodeHash = backendHash;
        modelHash = model; circuitManifestHash = circuitManifest;
    }

    function verifyAction(ActionContextV1.Context calldata c, bytes32 outputHash, bytes calldata evidence)
        external view returns (bool) {
        if (!ActionContextV1.valid(c) || c.rootScheme != 1 || c.modelId != modelHash ||
            c.issuedAt > block.timestamp || c.expiresAt <= block.timestamp ||
            c.expiresAt - c.issuedAt > 10 minutes || address(verifier).codehash != verifierCodeHash) return false;
        (bytes memory proof, uint256[4] memory inputs, uint256[2] memory outputs, bytes memory rootSignature) =
            abi.decode(evidence,(bytes,uint256[4],uint256[2],bytes));
        if (keccak256(evidence) != keccak256(abi.encode(proof, inputs, outputs, rootSignature))) return false;
        if (proof.length == 0 || proof.length > 60_000) return false;
        for (uint256 i; i < 4; ++i) if (inputs[i] >= FIELD) return false;
        for (uint256 i; i < 2; ++i) if (outputs[i] >= FIELD) return false;
        if (sha256(abi.encode(inputs)) != c.inputHash || sha256(abi.encode(outputs)) != outputHash) return false;
        bytes32 digest = ActionContextV1.digest(c);
        bytes32 control = sha256(abi.encodePacked("VAMS:EZKL-ROOT-CONTROL:v1",hex"00",
            abi.encode(digest,outputHash,sha256(proof),circuitManifestHash)));
        if (!RootSignatureV1.valid(address(uint160(uint256(c.actorRoot))),control,rootSignature)) return false;
        uint256[] memory instances = new uint256[](22);
        for (uint256 i; i < 8; ++i) {
            uint256 limb = (uint256(digest) >> ((7-i)*32)) & 0xffffffff;
            instances[i] = limb; instances[12+i] = limb;
        }
        for (uint256 i; i < 4; ++i) instances[8+i] = inputs[i];
        instances[20] = outputs[0]; instances[21] = outputs[1];
        try verifier.verifyProof(proof,instances) returns (bool ok) { return ok; }
        catch { return false; }
    }
}
