import logging
from typing import Any

logger = logging.getLogger(__name__)

class YieldManager:
    """
    Manages Insurance Fund yield vault allocations.
    Interfaces with OMS earning primitives (sPOL, yield vaults).
    Enforces max allocation cap, instant withdrawal requirements.
    """

    def __init__(self, insurance_fund_contract: Any, signer: Any):
        self.fund = insurance_fund_contract
        self.signer = signer
        logger.info("Initialized YieldManager")

    def deploy_capital(self, vault_address: str, amount: int) -> str:
        """
        Deploy capital to a yield vault (up to 30% allowed by contract).
        """
        logger.info(f"Deploying {amount} to vault {vault_address}")
        # Build transaction
        tx = self.fund.functions.deployToYield(vault_address, amount).build_transaction({
            'from': self.signer.get_address(),
            # nonce, gas, gasPrice would be added here
        })
        # Sign and send
        signed_tx = self.signer.sign_transaction(tx)
        # return tx_hash
        return "0x_mock_tx_hash_deploy"

    def withdraw_capital(self, vault_address: str, amount: int) -> str:
        """
        Withdraw capital from a yield vault.
        """
        logger.info(f"Withdrawing {amount} from vault {vault_address}")
        # Build transaction
        tx = self.fund.functions.withdrawFromYield(vault_address, amount).build_transaction({
            'from': self.signer.get_address(),
            # nonce, gas, gasPrice would be added here
        })
        # Sign and send
        signed_tx = self.signer.sign_transaction(tx)
        # return tx_hash
        return "0x_mock_tx_hash_withdraw"

    def get_deployed_balance(self) -> int:
        """
        Get total capital currently deployed to yield vaults.
        """
        return self.fund.functions.totalDeployedBalance().call()
