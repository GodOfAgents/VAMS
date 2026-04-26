import json
import os
import time
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VAMSRegistry")

class AgentRegistryClient:
    """Client for interacting with VAMSAgentRegistry smart contract."""
    
    def __init__(self, rpc_url=None, contract_address=None, private_key=None):
        self.rpc_url = rpc_url or os.getenv("VAMS_RPC_URL", "http://localhost:8545")
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        # Add PoA middleware for Polygon/Sepolia
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        if not self.w3.is_connected():
            logger.warning(f"Failed to connect to RPC: {self.rpc_url}")
            
        self.contract_address = contract_address or os.getenv("VAMS_REGISTRY_ADDRESS")
        self.private_key = private_key or os.getenv("VAMS_PRIVATE_KEY")
        
        if self.private_key:
            self.account = Account.from_key(self.private_key)
            self.address = self.account.address
        else:
            self.account = None
            self.address = None

        # Load ABI
        abi_path = os.path.join(os.path.dirname(__file__), "abi.json")
        if os.path.exists(abi_path):
            with open(abi_path, "r") as f:
                self.abi = json.load(f)
        else:
            logger.error(f"ABI file not found at {abi_path}")
            self.abi = []
            
        if self.contract_address and self.abi:
            self.contract = self.w3.eth.contract(address=self.contract_address, abi=self.abi)
        else:
            self.contract = None

    def register_agent(self, stake_amount: int, metadata_uri: str) -> str:
        """Register the agent on-chain."""
        if not self.contract or not self.account:
            raise ValueError("Contract or account not initialized")
            
        logger.info(f"Registering agent with stake {stake_amount} VAMS...")
        
        # Get public key hash (basic implementation)
        # In prod, this should come from the actual key pair used for signing
        pub_key_hash = self.w3.keccak(text=self.address)
        
        tx = self.contract.functions.registerAgent(
            pub_key_hash,
            stake_amount,
            metadata_uri
        ).build_transaction({
            'from': self.address,
            'nonce': self.w3.eth.get_transaction_count(self.address),
            'gas': 2000000,
            'gasPrice': self.w3.eth.gas_price
        })
        
        return self._submit_tx(tx)

    def submit_checkpoint(self, merkle_root: bytes, agent_id: bytes) -> str:
        """Submit a state checkpoint (Merkle root)."""
        if not self.contract:
            raise ValueError("Contract not initialized")
            
        logger.info(f"Submitting checkpoint {merkle_root.hex()} for agent {agent_id.hex()}...")
        
        tx = self.contract.functions.submitMerkleRoot(
            agent_id,
            merkle_root
        ).build_transaction({
            'from': self.address,
            'nonce': self.w3.eth.get_transaction_count(self.address),
            'gas': 500000,
            'gasPrice': self.w3.eth.gas_price
        })
        
        return self._submit_tx(tx)

    def _submit_tx(self, tx) -> str:
        """Standardized transaction submission with receipt waiting."""
        signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        logger.info(f"TX sent: {tx_hash.hex()}, waiting for receipt...")
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        if receipt.status != 1:
            raise Exception(f"Transaction failed! Hash: {tx_hash.hex()}")
            
        logger.info(f"TX confirmed in block {receipt.blockNumber}")
        return tx_hash.hex()

    def get_agent_status(self, agent_id: bytes):
        """Get agent status from registry."""
        if not self.contract:
            return None
        return self.contract.functions.getAgent(agent_id).call()

if __name__ == "__main__":
    # Test script
    client = AgentRegistryClient()
    if client.w3.is_connected():
        print(f"Connected to {client.rpc_url}")
        print(f"Block number: {client.w3.eth.block_number}")
    else:
        print("Not connected")
