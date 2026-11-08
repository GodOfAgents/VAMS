import pytest
from datetime import datetime, timedelta, timezone
from neuron.sdk.sequence_wallet import SequenceWalletManager, SessionKeyManager, TrustTier

def test_wallet_creation():
    manager = SequenceWalletManager(mock_mode=True)
    owner = "0x1234567890123456789012345678901234567890"
    wallet = manager.create_wallet(owner)
    
    assert wallet.startswith("0x")
    assert len(wallet) == 42
    assert owner in manager.wallets

def test_session_key_creation():
    manager = SequenceWalletManager(config={"core_contracts": ["0xContract1", "0xContract2"]})
    session_mgr = manager.get_session_manager()
    
    allowed = ["0xContract1", "0xContract2"]
    session_created_before = datetime.now(timezone.utc).timestamp()
    session = session_mgr.create_session_key(TrustTier.SILVER, allowed, validity_hours=24)
    
    assert "private_key" in session
    assert "session_key_address" in session
    assert session["max_value_per_tx"] == 1000
    assert session["allowed_contracts"] == [address.lower() for address in allowed]
    now = datetime.now(timezone.utc).timestamp()
    assert session["expires_at"] > now
    assert 0 < session["expires_at"] - now <= 24 * 60 * 60
    assert session["expires_at"] <= session_created_before + 24 * 60 * 60 + 1

def test_session_scope_verification():
    manager = SequenceWalletManager(config={"core_contracts": ["0xContract1", "0xContract2"]})
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
    manager = SequenceWalletManager(config={"core_contracts": ["0xContract"]})
    session_mgr = manager.get_session_manager()
    
    with pytest.raises(ValueError, match="between 1 and 24"):
        session_mgr.create_session_key(
            TrustTier.BRONZE, ["0xContract"], validity_hours=-1
        )

def test_expired_session_is_rejected():
    manager = SequenceWalletManager(config={"core_contracts": ["0xCore"]})
    session_mgr = manager.get_session_manager()
    session = session_mgr.create_session_key(TrustTier.GOLD, ["0xCore"])
    session["expires_at"] = datetime.now(timezone.utc).timestamp() - 1

    assert session_mgr.verify_session_scope(
        session["session_key_address"], "0xCore", 0
    ) is False



def test_session_is_rejected_at_exact_expiry(monkeypatch):
    manager = SequenceWalletManager(config={"core_contracts": ["0xCore"]})
    session_mgr = manager.get_session_manager()
    session = session_mgr.create_session_key(TrustTier.GOLD, ["0xCore"])
    expires_at = session["expires_at"]

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromtimestamp(expires_at, tz=tz or timezone.utc)

    monkeypatch.setattr("neuron.sdk.sequence_wallet.datetime", FrozenDatetime)

    assert session_mgr.verify_session_scope(
        session["session_key_address"], "0xCore", 0
    ) is False

def test_trust_tier_mapping():
    contracts = ["0xBronze", "0xSilver", "0xGold", "0xPlatinum"]
    manager = SequenceWalletManager(config={"core_contracts": contracts})
    session_mgr = manager.get_session_manager()
    
    s_bronze = session_mgr.create_session_key(TrustTier.BRONZE, [contracts[0]])
    assert s_bronze["max_value_per_tx"] == 100
    
    s_silver = session_mgr.create_session_key(TrustTier.SILVER, [contracts[1]])
    assert s_silver["max_value_per_tx"] == 1000
    
    s_gold = session_mgr.create_session_key(TrustTier.GOLD, [contracts[2]])
    assert s_gold["max_value_per_tx"] == 50000
    
    s_platinum = session_mgr.create_session_key(TrustTier.PLATINUM, [contracts[3]])
    assert s_platinum["max_value_per_tx"] == float('inf')


def test_session_key_rejects_more_than_24_hours():
    manager = SequenceWalletManager(config={"core_contracts": ["0xCore"]})
    with pytest.raises(ValueError, match="between 1 and 24"):
        manager.get_session_manager().create_session_key(
            TrustTier.GOLD, ["0xCore"], validity_hours=25
        )


def test_session_key_rejects_unconfigured_vams_core_whitelist():
    manager = SequenceWalletManager(config={})
    with pytest.raises(ValueError, match="not configured"):
        manager.get_session_manager().create_session_key(
            TrustTier.GOLD, ["0xCore"]
        )


def test_session_key_rejects_empty_or_non_core_allowlist():
    manager = SequenceWalletManager(config={"core_contracts": ["0xCore"]})
    session_mgr = manager.get_session_manager()
    with pytest.raises(ValueError, match="non-empty"):
        session_mgr.create_session_key(TrustTier.GOLD, [])
    with pytest.raises(PermissionError, match="outside"):
        session_mgr.create_session_key(TrustTier.GOLD, ["0xAttacker"])
