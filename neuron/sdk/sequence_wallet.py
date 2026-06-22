from enum import IntEnum
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
from eth_account import Account
import secrets

class TrustTier(IntEnum):
    BRONZE = 1
    SILVER = 2
    GOLD = 3
    PLATINUM = 4

class SessionKeyManager:
    def __init__(self, manager: 'SequenceWalletManager'):
        self.manager = manager
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
    def create_session_key(self, trust_tier: TrustTier, allowed_contracts: List[str], validity_hours: int = 24) -> Dict[str, Any]:
        """
        Creates a scoped session key.
        """
        max_value_map = {
            TrustTier.BRONZE: 100,
            TrustTier.SILVER: 1000,
            TrustTier.GOLD: 50000,
            TrustTier.PLATINUM: float('inf')
        }
        
        # Generate a new random session key
        private_key = "0x" + secrets.token_hex(32)
        account = Account.from_key(private_key)
        
        session_data = {
            "private_key": private_key,
            "session_key_address": account.address,
            "max_value_per_tx": max_value_map.get(trust_tier, 0),
            "allowed_contracts": allowed_contracts,
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=validity_hours)).timestamp()
        }
        
        self.active_sessions[account.address] = session_data
        return session_data

    def verify_session_scope(self, session_address: str, contract_address: str, value: float) -> bool:
        if session_address not in self.active_sessions:
            return False
            
        session = self.active_sessions[session_address]
        
        if datetime.now(timezone.utc).timestamp() > session["expires_at"]:
            return False
            
        if value > session["max_value_per_tx"]:
            return False
            
        if session["allowed_contracts"] and contract_address not in session["allowed_contracts"]:
            return False
            
        return True

class SequenceWalletManager:
    def __init__(self, config: Optional[Dict] = None, mock_mode: bool = False):
        self.config = config or {}
        self.mock_mode = mock_mode
        self.session_manager = SessionKeyManager(self)
        self.wallets: Dict[str, str] = {}
        
    def create_wallet(self, owner_address: str) -> str:
        """
        Creates an ERC-4337 smart wallet for the given owner.
        """
        # In a real implementation, this would interact with the Sequence API
        # For now, we simulate a deterministically derived wallet address
        wallet_address = "0x" + secrets.token_hex(20)
        self.wallets[owner_address] = wallet_address
        return wallet_address

    def build_user_operation(self, sender: str, to: str, data: str, value: int = 0) -> Dict[str, Any]:
        """
        Builds a standard ERC-4337 UserOperation.
        """
        # Simulated UserOp structure for EIP-4337
        return {
            "sender": sender,
            "nonce": "0x0",  # Simulated nonce
            "initCode": "0x",
            "callData": data,
            "callGasLimit": "0x5208", # 21000
            "verificationGasLimit": "0x186a0", # 100000
            "preVerificationGas": "0x5208",
            "maxFeePerGas": "0x0",
            "maxPriorityFeePerGas": "0x0",
            "paymasterAndData": "0x",
            "signature": "0x"
        }
        
    def send_user_operation(self, user_op: Dict[str, Any]) -> str:
        """
        Simulates sending a UserOperation to an ERC-4337 bundler.
        """
        # In a production environment, this calls eth_sendUserOperation on a bundler
        simulated_user_op_hash = "0x" + secrets.token_hex(32)
        return simulated_user_op_hash

    def get_session_manager(self) -> SessionKeyManager:
        return self.session_manager
