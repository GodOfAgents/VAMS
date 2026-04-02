// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title HardwareClasses
 * @author VAMS Protocol
 * @notice Pre-seeded hardware class identifiers for the VAMS Hardware Registry.
 * @dev Uses bytes32 keccak256 hashes instead of enums for extensibility.
 *      New hardware classes can be added via governance without contract upgrades.
 *
 *      Pattern mirrors Phase 1 proof-plugin identifiers (IVAMSProofPlugin.proofType).
 */
library HardwareClasses {
    // ═══════════════════ GPU Classes ═══════════════════

    /// @notice NVIDIA H100 (FP16 ~1,979 TFLOPS)
    bytes32 internal constant GPU_H100 = keccak256("GPU_H100");

    /// @notice NVIDIA A100 (FP16 ~312 TFLOPS)
    bytes32 internal constant GPU_A100 = keccak256("GPU_A100");

    /// @notice NVIDIA L40S (inference-optimized)
    bytes32 internal constant GPU_L40S = keccak256("GPU_L40S");

    /// @notice Consumer GPU — inference only
    bytes32 internal constant GPU_RTX_4090 = keccak256("GPU_RTX_4090");

    // ═══════════════════ CPU Classes ═══════════════════

    /// @notice AMD EPYC server (128+ cores)
    bytes32 internal constant CPU_EPYC = keccak256("CPU_EPYC");

    /// @notice Intel Xeon server
    bytes32 internal constant CPU_XEON = keccak256("CPU_XEON");

    // ═══════════════════ Storage Classes ═══════════════════

    /// @notice NVMe SSD (>1M IOPS)
    bytes32 internal constant STORAGE_NVME = keccak256("STORAGE_NVME");

    /// @notice HDD archival (high capacity, low IOPS)
    bytes32 internal constant STORAGE_HDD = keccak256("STORAGE_HDD");

    // ═══════════════════ Network Classes ═══════════════════

    /// @notice 10Gbps networking
    bytes32 internal constant NETWORK_10G = keccak256("NETWORK_10G");

    // ═══════════════════ TEE Classes ═══════════════════

    /// @notice Intel SGX TEE enclave
    bytes32 internal constant TEE_SGX = keccak256("TEE_SGX");

    /// @notice AWS Nitro Enclave
    bytes32 internal constant TEE_NITRO = keccak256("TEE_NITRO");

    /// @notice Total number of pre-seeded classes
    uint256 internal constant PRESEEDED_COUNT = 11;
}
