import os

files = [
    r"C:\Users\aseem\Desktop\VAMS-main\VAMS-main\contracts\test\VAMSAgentRegistry.t.sol",
    r"C:\Users\aseem\Desktop\VAMS-main\VAMS-main\contracts\test\registry\VAMSAgentRegistry_Identity.t.sol",
    r"C:\Users\aseem\Desktop\VAMS-main\VAMS-main\contracts\test\integration\AgentLifecycleIntegration.t.sol"
]

for file in files:
    with open(file, "r") as f:
        content = f.read()

    # Replaces
    content = content.replace("registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA)", "registry.registerAgent(TEST_PUBLIC_KEY_HASH, 1000 ether, TEST_METADATA, address(0))")
    content = content.replace("registry.registerAgent(TEST_PUBLIC_KEY_HASH, 500 ether, TEST_METADATA)", "registry.registerAgent(TEST_PUBLIC_KEY_HASH, 500 ether, TEST_METADATA, address(0))")
    content = content.replace("registry.registerAgent(TEST_PUBLIC_KEY_HASH, stake, TEST_METADATA)", "registry.registerAgent(TEST_PUBLIC_KEY_HASH, stake, TEST_METADATA, address(0))")
    content = content.replace("agentRegistry.registerAgent(publicKeyHash, stake, metadata)", "agentRegistry.registerAgent(publicKeyHash, stake, metadata, address(0))")

    # Multi-line cases in VAMSAgentRegistry.t.sol
    content = content.replace(
'''        bytes32 agent1 = registry.registerAgent(
            keccak256("pubkey1"),
            1000 ether,
            "ipfs://1"
        );''',
'''        bytes32 agent1 = registry.registerAgent(
            keccak256("pubkey1"),
            1000 ether,
            "ipfs://1",
            address(0)
        );''')
        
    content = content.replace(
'''        bytes32 agent2 = registry.registerAgent(
            keccak256("pubkey2"),
            1000 ether,
            "ipfs://2"
        );''',
'''        bytes32 agent2 = registry.registerAgent(
            keccak256("pubkey2"),
            1000 ether,
            "ipfs://2",
            address(0)
        );''')

    # Multi-line in VAMSAgentRegistry_Identity.t.sol
    content = content.replace(
'''        agentId = registry.registerAgent(
            TEST_PUBLIC_KEY_HASH,
            1000 ether,
            TEST_METADATA
        );''',
'''        agentId = registry.registerAgent(
            TEST_PUBLIC_KEY_HASH,
            1000 ether,
            TEST_METADATA,
            address(0)
        );''')

    with open(file, "w") as f:
        f.write(content)
