from enum import IntEnum
from typing import Dict, List, Optional, Any, Mapping
from datetime import datetime, timedelta, timezone
import math
import os
from eth_account import Account
import secrets

from neuron.runtime_safety import (
    ImmutableRuntimeConfiguration,
    LiveModeSafetyError,
    RuntimeConfigurationError,
    RuntimePolicy,
    load_runtime_policy,
)

class TrustTier(IntEnum):
    BRONZE = 1
    SILVER = 2
    GOLD = 3
    PLATINUM = 4

class SessionKeyManager:
    MAX_VALIDITY_HOURS = 24

    def __init__(self, manager: 'SequenceWalletManager'):
        self.manager = manager
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    def _require_local_credential_creation(self) -> None:
        # No authenticated live session-grant/credential broker is implemented.
        # Do not mistake local scope metadata or an unavailable wallet backend
        # for permission to generate and release a live credential.
        if type(self.manager) is not SequenceWalletManager:
            raise LiveModeSafetyError("Session creation requires the configured wallet manager")
        observed = load_runtime_policy()
        if self.manager.runtime_policy.is_live or observed.is_live:
            raise LiveModeSafetyError("Unqualified session credential creation cannot run in live mode")
        
    def create_session_key(self, trust_tier: TrustTier, allowed_contracts: List[str], validity_hours: int = 24) -> Dict[str, Any]:
        """
        Creates a scoped local session key; live issuance is unqualified.
        """
        self._require_local_credential_creation()
        if (
            isinstance(validity_hours, bool)
            or not isinstance(validity_hours, int)
            or validity_hours < 1
            or validity_hours > self.MAX_VALIDITY_HOURS
        ):
            raise ValueError("session key validity must be between 1 and 24 hours")
        if not allowed_contracts or any(
            not isinstance(address, str) or not address.strip()
            for address in allowed_contracts
        ):
            raise ValueError("session keys require a non-empty contract allowlist")
        normalized_contracts = list(
            dict.fromkeys(address.strip().lower() for address in allowed_contracts)
        )
        configured_contracts = self.manager.core_contracts
        if not configured_contracts:
            raise ValueError("VAMS core contract whitelist is not configured")
        unapproved = set(normalized_contracts) - configured_contracts
        if unapproved:
            raise PermissionError(
                "session key requested contracts outside the VAMS core whitelist"
            )
        max_value_map = {
            TrustTier.BRONZE: 100,
            TrustTier.SILVER: 1000,
            TrustTier.GOLD: 50000,
            TrustTier.PLATINUM: float('inf')
        }
        
        # Input normalization may call user-defined Python methods. Recheck
        # the runtime before entropy/key operations and before releasing data.
        self._require_local_credential_creation()
        # Generate a new random session key
        private_key = "0x" + secrets.token_hex(32)
        account = Account.from_key(private_key)
        
        session_data = {
            "private_key": private_key,
            "session_key_address": account.address,
            "max_value_per_tx": max_value_map.get(trust_tier, 0),
            "allowed_contracts": normalized_contracts,
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=validity_hours)).timestamp()
        }
        
        self._require_local_credential_creation()
        self.active_sessions[account.address] = session_data
        return session_data

    def verify_session_scope(self, session_address: str, contract_address: str, value: float) -> bool:
        # This cached local predicate is not live policy/epoch/root authority.
        # Deny before looking up even a populated or adversarial local cache.
        if type(self.manager) is SequenceWalletManager and self.manager.runtime_policy.is_live:
            return False
        try:
            if load_runtime_policy().is_live:
                return False
        except RuntimeConfigurationError:
            return False
        if session_address not in self.active_sessions:
            return False
            
        session = self.active_sessions[session_address]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or value < 0
            or (isinstance(value, float) and not math.isfinite(value))
        ):
            return False
        
        expires_at = session.get("expires_at")
        if (
            isinstance(expires_at, bool)
            or not isinstance(expires_at, (int, float))
            or (isinstance(expires_at, float) and not math.isfinite(expires_at))
        ):
            return False

        # The expiry instant is outside the session validity window.
        if datetime.now(timezone.utc).timestamp() >= expires_at:
            return False
            
        max_value_per_tx = session.get("max_value_per_tx")
        if (
            isinstance(max_value_per_tx, bool)
            or not isinstance(max_value_per_tx, (int, float))
            or (isinstance(max_value_per_tx, float) and math.isnan(max_value_per_tx))
            or max_value_per_tx < 0
        ):
            return False

        if value > max_value_per_tx:
            return False
            
        allowed_contracts = session.get("allowed_contracts")
        if (
            not isinstance(allowed_contracts, list)
            or not allowed_contracts
            or any(
                not isinstance(address, str) or not address.strip()
                for address in allowed_contracts
            )
        ):
            return False
        if not isinstance(contract_address, str) or not contract_address.strip():
            return False
        if contract_address.strip().lower() not in allowed_contracts:
            return False
            
        return True

class SequenceWalletManager(ImmutableRuntimeConfiguration):
    """Session-key interfaces plus explicitly local simulated wallet operations."""

    _immutable_runtime_fields = frozenset({"runtime_policy", "mock_mode"})

    def __init__(
        self,
        config: Optional[Dict] = None,
        mock_mode: bool = False,
        *,
        runtime_policy: Optional[RuntimePolicy] = None,
        environ: Optional[Mapping[str, str]] = None,
    ):
        source = os.environ if environ is None else environ
        observed = load_runtime_policy(source)
        if runtime_policy is not None and runtime_policy != observed:
            raise RuntimeConfigurationError(
                "Conflicting runtime policy for SequenceWalletManager"
            )
        self.runtime_policy = runtime_policy if runtime_policy is not None else observed
        self.mock_mode = self.runtime_policy.authorize_component_mock(
            "SequenceWalletManager", mock_mode
        )
        self.config = config or {}
        configured_contracts = self.config.get("core_contracts", [])
        if not isinstance(configured_contracts, list):
            raise ValueError("core_contracts must be a list")
        self.core_contracts = {
            address.strip().lower()
            for address in configured_contracts
            if isinstance(address, str) and address.strip()
        }
        self.session_manager = SessionKeyManager(self)
        self.wallets: Dict[str, str] = {}
        self._freeze_runtime_configuration()

    def _require_mock_wallet_operation(self) -> None:
        if not self.mock_mode:
            raise LiveModeSafetyError(
                "SequenceWalletManager real wallet/bundler backend is not implemented"
            )

    def create_wallet(self, owner_address: str) -> str:
        """Create a synthetic wallet address in explicit non-live mock mode."""
        self._require_mock_wallet_operation()
        # Local simulation only; no Sequence API or wallet deployment occurs.
        wallet_address = "0x" + secrets.token_hex(20)
        self.wallets[owner_address] = wallet_address
        return wallet_address

    def build_user_operation(self, sender: str, to: str, data: str, value: int = 0) -> Dict[str, Any]:
        """Build a placeholder operation in explicit non-live mock mode."""
        self._require_mock_wallet_operation()
        # Simulated UserOp structure; not a signed or executable operation.
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
        """Return a synthetic operation hash in explicit non-live mock mode."""
        self._require_mock_wallet_operation()
        # No eth_sendUserOperation or bundler submission occurs.
        simulated_user_op_hash = "0x" + secrets.token_hex(32)
        return simulated_user_op_hash

    def get_session_manager(self) -> SessionKeyManager:
        return self.session_manager
