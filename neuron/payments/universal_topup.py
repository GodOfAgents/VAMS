import logging
from typing import Dict, Any, Optional

from .coinme_client import CoinmeClient

logger = logging.getLogger(__name__)

class UniversalTopUpManager:
    """
    Orchestrates fiat -> $VAMS conversion flow.
    Accepts credit card / bank transfer via Coinme.
    Auto-converts to $VAMS and deposits to agent's ComposedSettlement escrow.
    Applies gas abstraction premium (2-7%).
    """

    def __init__(self, coinme_client: CoinmeClient, settlement_contract: Any, premium_bps: int = 500):
        """
        premium_bps: Gas abstraction premium (e.g. 500 = 5%)
        """
        self.coinme = coinme_client
        self.settlement = settlement_contract
        self.premium_bps = premium_bps

    def initiate_top_up(self, agent_id: str, dest_address: str, amount_fiat: float, currency: str = "USD") -> Dict[str, Any]:
        """
        Initiates a top-up session.
        """
        # Apply premium to the amount required from user to cover gas/fees
        premium_amount = amount_fiat * (self.premium_bps / 10000.0)
        total_fiat = amount_fiat + premium_amount

        logger.info(f"Initiating top-up for {agent_id}. Fiat: {amount_fiat}, Premium: {premium_amount}, Total: {total_fiat}")

        checkout_session = self.coinme.create_checkout(total_fiat, currency, dest_address)
        
        return {
            "agent_id": agent_id,
            "session": checkout_session,
            "premium_applied_fiat": premium_amount,
            "net_amount_fiat": amount_fiat
        }

    def process_webhook_deposit(self, payload: str, signature: str) -> bool:
        """
        Process the successful top-up and deposit to settlement.
        """
        if self.coinme.handle_webhook(payload, signature):
            logger.info("Webhook verified. Processing deposit to ComposedSettlement.")
            # Here we would interface with the smart contract to deposit the tokens
            # that the on-ramp provider has delivered to the holding address.
            # self.settlement.functions.deposit(...).transact(...)
            return True
        return False
