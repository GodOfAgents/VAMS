import logging
from typing import Optional, Dict
from web3 import Web3
from neuron import config

logger = logging.getLogger("SequenceWallet")

class SequenceWalletManager:
    """
    Manages Sequence Session Keys for VAMS Agents.
    Enables a two-layer identity system:
    1. Owner Wallet (EOA/Cold Storage): Holds high-value assets and manages permissions.
    2. Session Wallet (ERC-4337): Temporary, low-value key for autonomous agent signing.
    
    Integrated with Polygon Open Money Stack (OMS).
    """

    def __init__(self, web3: Web3, owner_private_key: str, project_key: str = None):
        self.web3 = web3
        self.owner_account = self.web3.eth.account.from_key(owner_private_key)
        self.project_key = project_key or config.SEQUENCE_PROJECT_KEY
        self.sessions: Dict[str, dict] = {}

    def create_session(self, label: str = "vams_agent_session", duration_sec: int = 86400) -> str:
        """
        Generates a new session key pair.
        Returns the public address (session_id).
        """
        session_account = self.web3.eth.account.create()
        session_id = session_account.address
        
        logger.info(f"Generated new Sequence session key: {session_id} [Label: {label}]")
        
        self.sessions[session_id] = {
            "account": session_account,
            "label": label,
            "duration": duration_sec,
            "authorized": False
        }
        
        return session_id

    def authorize_session(self, session_id: str) -> str:
        """
        Authorizes the session key on-chain (Polygon Amoy).
        In a production environment, this would call the Sequence Wallet Factory
        or the SessionKeyModule to register the key.
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} unknown.")

        logger.info(f"Authorizing session {session_id} using owner {self.owner_account.address}...")
        
        # MOCK: Build and sign an authorization transaction
        # In reality, this would be an ERC-4337 UserOperation or a direct contract call.
        self.sessions[session_id]["authorized"] = True
        
        logger.info(f"Session {session_id} is now AUTHORIZED for agent operations.")
        return session_id

    def sign_transaction(self, session_id: str, tx: dict) -> bytes:
        """
        Signs a transaction using the session key.
        Only works if the session is authorized.
        """
        session = self.sessions.get(session_id)
        if not session or not session["authorized"]:
            raise PermissionError(f"Cannot sign with unauthorized session {session_id}")

        signed_tx = self.web3.eth.account.sign_transaction(tx, session["account"].key)
        return signed_tx.raw_transaction

    def revoke_session(self, session_id: str):
        """
        Invalidates a session key locally and on-chain.
        """
        if session_id in self.sessions:
            logger.info(f"Revoking session {session_id}")
            self.sessions[session_id]["authorized"] = False
            # On-chain revocation logic would go here
            del self.sessions[session_id]

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    w3 = Web3()
    # Dummy owner key
    owner_key = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    manager = SequenceWalletManager(w3, owner_key)
    
    sid = manager.create_session("hft_inference_signing")
    manager.authorize_session(sid)
    
    print(f"Session {sid} Ready: {manager.sessions[sid]['authorized']}")
