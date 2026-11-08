"""Local SDK signing adapters, unavailable in staging/testnet/production.

Raw credentials, simulated session signatures and OMS compliance are not governed
action admission. Live signing requires a separately qualified authority/policy
broker. This containment does not implement or qualify that broker.
"""
from abc import ABC, abstractmethod
from typing import Optional, Union, Dict, Any
from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3

from neuron.runtime_safety import (
    ImmutableRuntimeConfiguration,
    LiveModeSafetyError,
    RuntimeConfigurationError,
    load_runtime_policy,
)


def _local_signing_policy():
    policy = load_runtime_policy()
    if policy.is_live:
        raise LiveModeSafetyError(
            "SDK raw-key/session signing is unavailable in live modes; "
            "a qualified governed signing broker is required"
        )
    return policy


class _LocalSigningBoundary(ImmutableRuntimeConfiguration):
    _immutable_runtime_fields = frozenset({"runtime_policy"})

    def _bind_local_signing(self):
        self.runtime_policy = _local_signing_policy()
        self._freeze_runtime_configuration()

    def _require_local_signing(self):
        # Recheck before any credential, compliance, encoding or signing effect.
        # A retained local object cannot be reused after runtime reclassification.
        current = _local_signing_policy()
        if current != self.runtime_policy:
            raise RuntimeConfigurationError(
                "Signer runtime configuration changed; existing credentials "
                "cannot be reclassified in place"
            )

class SignerInterface(ABC):
    """
    Abstract interface for signing transactions and messages.
    """
    
    @property
    @abstractmethod
    def address(self) -> str:
        """Get the public address of the signer."""
        pass
        
    @abstractmethod
    def sign_transaction(self, transaction: Dict[str, Any]) -> Any:
        """Sign a transaction dictionary."""
        pass
        
    @abstractmethod
    def sign_message(self, message: Union[bytes, str]) -> Any:
        """Sign a message."""
        pass

class EOASigner(_LocalSigningBoundary, SignerInterface):
    """
    Signer implementation for standard Externally Owned Accounts (EOA)
    using a raw private key.
    """
    
    def __init__(self, private_key: str):
        self._bind_local_signing()
        if not private_key:
            raise ValueError("Private key must be provided")
        # Ensure it has 0x prefix for eth_account compatibility if it's hex
        if not private_key.startswith("0x") and len(private_key) == 64:
            private_key = f"0x{private_key}"
        self.account: LocalAccount = Account.from_key(private_key)
        
    @property
    def address(self) -> str:
        return self.account.address
        
    def sign_transaction(self, transaction: Dict[str, Any]) -> Any:
        """Sign an EIP-1559 or legacy transaction."""
        self._require_local_signing()
        return self.account.sign_transaction(transaction)
        
    def sign_message(self, message: Union[bytes, str]) -> Any:
        """Sign an EIP-191 message."""
        self._require_local_signing()
        from eth_account.messages import encode_defunct
        
        if isinstance(message, str):
            encoded_msg = encode_defunct(text=message)
        else:
            encoded_msg = encode_defunct(message)
            
        return self.account.sign_message(encoded_msg)


class SessionKeySigner(_LocalSigningBoundary, SignerInterface):
    """
    Signer implementation for ERC-4337 smart wallets using a session key.
    (Stub for Phase 3 OMS Integration)
    """
    
    def __init__(self, smart_wallet_address: str, session_key: str):
        self._bind_local_signing()
        self.smart_wallet_address = Web3.to_checksum_address(smart_wallet_address)
        self.session_key_signer = EOASigner(session_key)
        
    @property
    def address(self) -> str:
        # Returns the smart wallet address, not the session key EOA
        return self.smart_wallet_address
        
    def sign_transaction(self, transaction: Dict[str, Any]) -> Any:
        """
        Sign a UserOperation for ERC-4337 using the session key.
        (Simulated for Phase 3: handles standard tx or user ops with session key)
        """
        self._require_local_signing()
        # If it's a UserOperation (has sender), we sign the hash of the UserOp
        if "sender" in transaction:
            # We would typically hash the UserOp fields here
            user_op_hash = "0x" + "00" * 32 # Simulated hash
            # Delegate to session key for signing the UserOp hash
            signed_hash = self.session_key_signer.sign_message(user_op_hash)
            transaction["signature"] = signed_hash.signature.hex()
            return transaction
            
        # In a real ERC-4337 flow, standard txs would be wrapped in a UserOperation
        # For simulation, we delegate to the session key.
        if "from" in transaction and transaction["from"] != self.session_key_signer.address:
            # eth_account requires from to match the private key
            transaction["from"] = self.session_key_signer.address
        elif "from" not in transaction:
            transaction["from"] = self.session_key_signer.address
            
        return self.session_key_signer.sign_transaction(transaction)
        
    def sign_message(self, message: Union[bytes, str]) -> Any:
        """
        Sign a message (e.g. for EIP-1271 validation) using the session key.
        """
        self._require_local_signing()
        # EIP-1271: The session key signs, and the smart wallet verifies it.
        return self.session_key_signer.sign_message(message)

class OMSSigner(_LocalSigningBoundary, SignerInterface):
    """
    Signer implementation that wraps another signer and enforces OMS compliance
    before signing transactions or messages.
    """
    
    def __init__(self, inner_signer: SignerInterface, identity_verifier: Optional[Any] = None):
        self._bind_local_signing()
        self.inner_signer = inner_signer
        # Lazy import to avoid circular dependency
        from neuron.sdk.oms_identity import OMSIdentityVerifier
        self.identity_verifier = identity_verifier or OMSIdentityVerifier()
        
    @property
    def address(self) -> str:
        return self.inner_signer.address
        
    def sign_transaction(self, transaction: Dict[str, Any]) -> Any:
        self._require_local_signing()
        # Check compliance for recipient
        to_address = transaction.get("to")
        if to_address and not self.identity_verifier.is_compliance_verified(to_address):
            # Also allow verifying sender (self.address)
            if not self.identity_verifier.is_compliance_verified(self.address):
                raise PermissionError(
                    "OMS Signer: Compliance check failed for sender and recipient."
                )
        return self.inner_signer.sign_transaction(transaction)
        
    def sign_message(self, message: Union[bytes, str]) -> Any:
        self._require_local_signing()
        # Check compliance for sender
        if not self.identity_verifier.is_compliance_verified(self.address):
            raise PermissionError("OMS Signer: Compliance check failed for sender.")
        return self.inner_signer.sign_message(message)

class SignerFactory:
    """Factory to create the appropriate signer based on configuration."""
    
    @staticmethod
    def create(config: Dict[str, Any]) -> SignerInterface:
        _local_signing_policy()
        if "session_key" in config and "smart_wallet_address" in config:
            signer = SessionKeySigner(
                smart_wallet_address=config["smart_wallet_address"],
                session_key=config["session_key"]
            )
        elif "private_key" in config:
            signer = EOASigner(private_key=config["private_key"])
        else:
            raise ValueError("Invalid signer configuration. Must provide private_key OR (session_key AND smart_wallet_address).")
            
        if config.get("oms_compliance", False):
            from neuron.sdk.oms_identity import OMSIdentityVerifier
            verifier_config = config.get("oms_verifier_config", {})
            verifier = OMSIdentityVerifier(
                api_url=verifier_config.get("api_url"),
                api_key=verifier_config.get("api_key")
            )
            signer = OMSSigner(inner_signer=signer, identity_verifier=verifier)
            
        return signer
