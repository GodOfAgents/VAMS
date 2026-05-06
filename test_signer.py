import sys
import os

# Add neuron directory to path
sys.path.insert(0, os.path.abspath('C:\\Users\\aseem\\Desktop\\VAMS-main\\VAMS-main\\neuron'))

from sdk.sequence_wallet import SequenceWalletManager, TrustTier
from sdk.signer import SignerFactory, SessionKeySigner

def test_integration():
    manager = SequenceWalletManager()
    wallet_address = manager.create_wallet("0x123")
    print(f"Created wallet: {wallet_address}")
    
    session_manager = manager.get_session_manager()
    session_data = session_manager.create_session_key(TrustTier.SILVER, ["0xabc"])
    
    print(f"Session data: {session_data}")
    
    signer = SignerFactory.create({
        "smart_wallet_address": wallet_address,
        "session_key": session_data["private_key"]
    })
    
    print(f"Signer address: {signer.address}")
    
    valid_address = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
    tx = {"to": valid_address, "value": 100, "gas": 21000, "gasPrice": 1000000000, "nonce": 0, "chainId": 1}
    signed_tx = signer.sign_transaction(tx)
    print("Signed standard tx")
    
    user_op = manager.build_user_operation("0x123", "0xabc", "0x")
    signed_op = signer.sign_transaction(user_op)
    print("Signed user op")
    
    if "signature" in signed_op:
        print(f"Signature present: {len(signed_op['signature'])} bytes")

if __name__ == "__main__":
    test_integration()
