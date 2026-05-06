from typing import Dict, Optional, Any
from web3 import Web3

class PayoutMode:
    VAMS_ONLY = 0
    STABLECOIN = 1
    HYBRID = 2

class StablecoinPayoutManager:
    """
    Manages provider preferences for stablecoin payouts.
    Providers can opt-in to auto-convert $VAMS rewards to USDC/USDT using OMS rails.
    """

    def __init__(self, web3: Web3, reward_distributor_address: str, private_key: str):
        self.web3 = web3
        self.reward_distributor_address = reward_distributor_address
        self.private_key = private_key
        self.account = self.web3.eth.account.from_key(private_key)
        
        # Minimal ABI for RewardDistributor's setPayoutPreference
        self.abi = [
            {
                "inputs": [{"internalType": "enum RewardDistributor.PayoutMode", "name": "mode", "type": "uint8"}],
                "name": "setPayoutPreference",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "address", "name": "", "type": "address"}],
                "name": "payoutPreference",
                "outputs": [{"internalType": "enum RewardDistributor.PayoutMode", "name": "", "type": "uint8"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
        self.contract = self.web3.eth.contract(address=reward_distributor_address, abi=self.abi)

    def set_preference(self, mode: int) -> str:
        """
        Sets the payout preference on the RewardDistributor contract.
        """
        nonce = self.web3.eth.get_transaction_count(self.account.address)
        
        txn = self.contract.functions.setPayoutPreference(mode).build_transaction({
            'from': self.account.address,
            'nonce': nonce,
            'gas': 100000,
            'gasPrice': self.web3.eth.gas_price
        })
        
        signed_txn = self.account.sign_transaction(txn)
        tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        return tx_hash.hex()

    def get_preference(self, provider_address: str) -> int:
        """
        Gets the current payout preference for a provider.
        """
        return self.contract.functions.payoutPreference(provider_address).call()

    def opt_in_to_stablecoin(self) -> str:
        """
        Convenience method to opt-in to 100% stablecoin payouts.
        """
        return self.set_preference(PayoutMode.STABLECOIN)

    def opt_in_to_hybrid(self) -> str:
        """
        Convenience method to opt-in to 50/50 VAMS/Stablecoin payouts.
        """
        return self.set_preference(PayoutMode.HYBRID)
