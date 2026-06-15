import pytest
from datetime import datetime, timedelta, timezone
from neuron.sdk.sequence_wallet import SequenceWalletManager, SessionKeyManager, TrustTier

def test_wallet_creation():
    manager = SequenceWalletManager()
    owner = "0x1234567890123456789012345678901234567890"
    wallet = manager.create_wallet(owner)
    
    assert wallet.startswith("0x")
    assert len(wallet) == 42
    assert owner in manager.wallets

def test_session_key_creation():
    manager = SequenceWalletManager()
    session_mgr = manager.get_session_manager()
    
    allowed = ["0xContract1", "0xContract2"]
    session = session_mgr.create_session_key(TrustTier.SILVER, allowed, validity_hours=24)
    
    assert "private_key" in session
    assert "session_key_address" in session
    assert session["max_value_per_tx"] == 1000
    assert session["allowed_contracts"] == allowed
    assert session["expires_at"] > datetime.now(timezone.utc).timestamp()

def test_session_scope_verification():
    manager = SequenceWalletManager()
    session_mgr = manager.get_session_manager()
    
    allowed = ["0xContract1", "0xContract2"]
    session = session_mgr.create_session_key(TrustTier.GOLD, allowed, validity_hours=24)
    addr = session["session_key_address"]
    
    # Valid
    assert session_mgr.verify_session_scope(addr, "0xContract1", 1000) == True
    
    # Invalid contract
    assert session_mgr.verify_session_scope(addr, "0xContract3", 1000) == False
    
    # Value too high
    assert session_mgr.verify_session_scope(addr, "0xContract1", 60000) == False

def test_session_expiry():
    manager = SequenceWalletManager()
    session_mgr = manager.get_session_manager()
    
    session = session_mgr.create_session_key(TrustTier.BRONZE, ["0xContract"], validity_hours=-1) # Already expired
    addr = session["session_key_address"]
    
    assert session_mgr.verify_session_scope(addr, "0xContract", 10) == False

def test_trust_tier_mapping():
    manager = SequenceWalletManager()
    session_mgr = manager.get_session_manager()
    
    s_bronze = session_mgr.create_session_key(TrustTier.BRONZE, [])
    assert s_bronze["max_value_per_tx"] == 100
    
    s_silver = session_mgr.create_session_key(TrustTier.SILVER, [])
    assert s_silver["max_value_per_tx"] == 1000
    
    s_gold = session_mgr.create_session_key(TrustTier.GOLD, [])
    assert s_gold["max_value_per_tx"] == 50000
    
    s_platinum = session_mgr.create_session_key(TrustTier.PLATINUM, [])
    assert s_platinum["max_value_per_tx"] == float('inf')
