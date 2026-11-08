import logging
from typing import Any

from neuron.runtime_safety import LiveModeSafetyError

logger = logging.getLogger(__name__)

class YieldManager:
    """
    Read-only fund query wrapper; yield transaction submission is unavailable.

    Restricted testnet keeps real yield disabled. The former write methods built
    and signed transactions but returned fabricated hashes without broadcasting
    or confirming anything. No authenticated write/recovery backend exists here.
    """

    def __init__(self, insurance_fund_contract: Any, signer: Any):
        self.fund = insurance_fund_contract
        self.signer = signer
        logger.info("Initialized YieldManager")

    def deploy_capital(self, vault_address: str, amount: int) -> str:
        """
        Reject unsupported yield writes before accessing the fund or signer.
        """
        raise LiveModeSafetyError("Yield deployment is disabled; transaction submission is unavailable")

    def withdraw_capital(self, vault_address: str, amount: int) -> str:
        """
        Reject the incomplete write path; this does not implement recovery.
        """
        raise LiveModeSafetyError("Yield withdrawal submission is unavailable; no recovery backend is qualified")

    def get_deployed_balance(self) -> int:
        """
        Pass through the supplied contract's read; not authenticated custody evidence.
        """
        return self.fund.functions.totalDeployedBalance().call()
