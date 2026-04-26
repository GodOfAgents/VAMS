"""
Tests for Enhanced CLR v3.1, MEV Protection, and Bridge Executor
=================================================================
"""

import sys
import os
import io
import logging

# Fix Windows console encoding
# if sys.platform == "win32":
#     sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
#     sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(level=logging.WARNING)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


# ─────────────────────────────────────────────────────────────────
# 1. CLR v3.1 Decision Tree
# ─────────────────────────────────────────────────────────────────

def test_p0_compliance_privacy():
    """P0: Compliance Privacy -> Midnight."""
    from clr_router import CLRouter, TransactionIntent, TrustTier, RoutingPriority
    router = CLRouter()
    intent = TransactionIntent(
        value_usd=5000, max_latency_ms=60000,
        requires_privacy=True, requires_compliance_privacy=True,
    )
    d = router.route(intent, TrustTier.SILVER)
    assert d.chain == "Midnight", f"Expected Midnight, got {d.chain}"
    assert d.priority == RoutingPriority.P0_COMPLIANCE_PRIVACY
    print(f"  [PASS] P0 Compliance Privacy -> {d.chain} ({d.target_bridge})")


def test_p1_confidential_compute():
    """P1: Confidential Compute -> Phala."""
    from clr_router import CLRouter, TransactionIntent, TrustTier, RoutingPriority
    router = CLRouter()
    intent = TransactionIntent(
        value_usd=200, max_latency_ms=10000,
        requires_privacy=True, requires_confidential_compute=True,
    )
    d = router.route(intent, TrustTier.GOLD)
    assert d.chain == "Phala", f"Expected Phala, got {d.chain}"
    assert d.priority == RoutingPriority.P1_CONFIDENTIAL_COMPUTE
    print(f"  [PASS] P1 Confidential Compute -> {d.chain} ({d.target_bridge})")


def test_p2_high_value_security():
    """P2: High value (>$10K) -> Ethereum."""
    from clr_router import CLRouter, TransactionIntent, TrustTier, RoutingPriority
    router = CLRouter()
    intent = TransactionIntent(
        value_usd=50000, max_latency_ms=30000, requires_privacy=False,
    )
    d = router.route(intent, TrustTier.GOLD)
    assert d.chain == "Ethereum", f"Expected Ethereum, got {d.chain}"
    assert d.priority == RoutingPriority.P2_HIGH_VALUE_SECURITY
    print(f"  [PASS] P2 High Value (${intent.value_usd:,}) -> {d.chain}")


def test_p4_formal_verification():
    """P4: Formal Verification -> Cardano."""
    from clr_router import CLRouter, TransactionIntent, TrustTier, RoutingPriority
    router = CLRouter()
    intent = TransactionIntent(
        value_usd=2000, max_latency_ms=60000,
        requires_privacy=False, requires_formal_verification=True,
    )
    d = router.route(intent, TrustTier.GOLD)
    assert d.chain == "Cardano", f"Expected Cardano, got {d.chain}"
    assert d.priority == RoutingPriority.P4_FORMAL_VERIFICATION
    print(f"  [PASS] P4 Formal Verification -> {d.chain} ({d.target_bridge})")


def test_p5_velocity_hydra():
    """P5a: Sub-second settlement -> Hydra."""
    from clr_router import CLRouter, TransactionIntent, TrustTier, RoutingPriority
    router = CLRouter()
    intent = TransactionIntent(
        value_usd=100, max_latency_ms=500,
        requires_privacy=False, requires_sub_second_settle=True,
        use_case_id="high_freq_trading",
    )
    d = router.route(intent, TrustTier.GOLD)
    assert d.chain == "Hydra", f"Expected Hydra, got {d.chain}"
    assert d.priority == RoutingPriority.P5_VELOCITY
    print(f"  [PASS] P5a Sub-Second -> {d.chain} (fee=${d.fee_estimate_usd:.4f})")


def test_p5_velocity_sei():
    """P5b: EVM fast lane -> SEI."""
    from clr_router import CLRouter, TransactionIntent, TrustTier, RoutingPriority
    router = CLRouter()
    intent = TransactionIntent(
        value_usd=50, max_latency_ms=800,
        requires_privacy=False, use_case_id="defi_swap",
    )
    d = router.route(intent, TrustTier.BRONZE)
    assert d.chain == "SEI", f"Expected SEI, got {d.chain}"
    assert d.priority == RoutingPriority.P5_VELOCITY
    print(f"  [PASS] P5b EVM Fast Lane -> {d.chain} ({d.target_bridge})")


def test_p6_default_routing():
    """P6: Default -> optimal chain via utility scoring."""
    from clr_router import CLRouter, TransactionIntent, TrustTier, RoutingPriority
    router = CLRouter()
    intent = TransactionIntent(
        value_usd=10, max_latency_ms=30000, requires_privacy=False,
    )
    d = router.route(intent, TrustTier.BRONZE)
    assert d.priority == RoutingPriority.P6_DEFAULT
    assert d.feasible_chains > 0
    print(f"  [PASS] P6 Default -> {d.chain} ({d.feasible_chains} feasible)")


def test_access_control_denied():
    """Trust tier enforcement: UNVERIFIED cannot exceed $1K."""
    from clr_router import CLRouter, TransactionIntent, TrustTier
    router = CLRouter()
    intent = TransactionIntent(
        value_usd=5000, max_latency_ms=30000, requires_privacy=False,
    )
    try:
        router.route(intent, TrustTier.UNVERIFIED)
        assert False, "Should have raised PermissionError"
    except PermissionError as e:
        print(f"  [PASS] Access denied: {str(e)[:60]}...")


def test_routing_hash():
    """Routing decisions include hash for ZK proofs."""
    from clr_router import CLRouter, TransactionIntent, TrustTier
    router = CLRouter()
    intent = TransactionIntent(
        value_usd=10, max_latency_ms=30000, requires_privacy=False,
    )
    d = router.route(intent, TrustTier.BRONZE)
    assert len(d.routing_hash) == 16, f"Expected 16-char hash, got {len(d.routing_hash)}"
    print(f"  [PASS] Routing hash: {d.routing_hash}")


# ─────────────────────────────────────────────────────────────────
# 2. MEV Protection
# ─────────────────────────────────────────────────────────────────

def test_encrypted_mempool():
    """Encrypted mempool hides tx content."""
    from mev_protection import EncryptedMempool
    pool = EncryptedMempool()
    tx = pool.submit_transaction(b"swap BTC/USDT 10000", value_usd=10000)
    assert tx.status.value == "committed"
    assert len(tx.commitment_hash) == 64  # SHA-256
    assert tx.encrypted_payload != b"swap BTC/USDT 10000"
    stats = pool.get_stats()
    assert stats["committed"] == 1
    assert stats["mev_prevented"] > 0
    print(f"  [PASS] Encrypted mempool: {tx.tx_id} (MEV prevented: ${stats['mev_prevented']:.2f})")


def test_batch_auction():
    """Batch auction settles at uniform clearing price."""
    from mev_protection import BatchAuctionSettler, BatchPayment
    import time
    settler = BatchAuctionSettler()
    payments = [
        BatchPayment("p1", "agent_1", "provider_1", 1.0, "h1", time.time()),
        BatchPayment("p2", "agent_2", "provider_2", 2.0, "h2", time.time()),
        BatchPayment("p3", "agent_3", "provider_3", 3.0, "h3", time.time()),
    ]
    for p in payments:
        settler.add_payment(p)
    result = settler.settle_batch()
    assert result is not None
    assert result.clearing_price == 2.0  # Median of [1, 2, 3]
    assert result.payments_settled == 3
    print(f"  [PASS] Batch auction: {result.batch_id} at {result.clearing_price} VAMS")


def test_mev_slashing_report():
    """MEV extraction report triggers 25% slash."""
    from mev_protection import MEVProtection
    mev = MEVProtection()
    report = mev.report_mev_extraction(
        tx_hash="0xabc", extractor_id="bad_validator",
        evidence="sandwich detected", estimated_profit=100.0,
    )
    assert report["slash_amount"] == 25.0
    assert report["status"] == "pending_review"
    print(f"  [PASS] MEV slash: {report['slash_amount']} VAMS (25% of {report['estimated_profit']})")


# ─────────────────────────────────────────────────────────────────
# 3. Bridge Executor + ICB
# ─────────────────────────────────────────────────────────────────

def test_icb_build_message():
    """ICB client builds valid bridge messages."""
    from bridge_executor import ICBClient
    icb = ICBClient()
    msg = icb.build_bridge_message("polygon", "cardano", b"test_payload")
    assert msg.source_chain == "polygon"
    assert msg.dest_chain == "cardano"
    assert msg.sequence == 1
    assert len(msg.payload_hash) == 64
    # Build second message: nonce should increment
    msg2 = icb.build_bridge_message("polygon", "cardano", b"second")
    assert msg2.sequence == 2
    print(f"  [PASS] ICB message: seq={msg.sequence}, hash={msg.payload_hash[:12]}...")


def test_icb_verify_proof():
    """ICB proof verification mirrors Aiken contract."""
    from bridge_executor import ICBClient
    icb = ICBClient()
    # Valid proof: >= 64 bytes
    assert icb.verify_bridge_proof(b'\x00' * 64, "abc123") == True
    # Invalid: too short (< 64 bytes)
    assert icb.verify_bridge_proof(b'\x00' * 32, "abc123") == False
    # Invalid: empty hash
    assert icb.verify_bridge_proof(b'\x00' * 64, "") == False
    print(f"  [PASS] ICB verify: 64B=valid, 32B=invalid, empty_hash=invalid")


def test_icb_nonce_replay():
    """ICB blocks nonce replay attacks."""
    from bridge_executor import ICBClient
    icb = ICBClient()
    icb.build_bridge_message("polygon", "cardano", b"msg1")
    # Nonce 1 was used, so nonce 1 should be rejected
    assert icb.verify_nonce(1, "cardano") == False   # Replay
    assert icb.verify_nonce(2, "cardano") == True     # Valid new
    stats = icb.get_stats()
    assert stats["replay_attempts_blocked"] == 1
    print(f"  [PASS] ICB nonce replay blocked: {stats['replay_attempts_blocked']} attempts")


def test_bridge_executor_cardano():
    """Bridge to Cardano uses ICB verification."""
    from bridge_executor import BridgeExecutor, BridgeStatus
    executor = BridgeExecutor(mock_mode=True)
    result = executor.execute("Cardano", b"test_cardano_tx")
    assert result.status == BridgeStatus.VERIFIED
    assert result.icb_message is not None
    assert result.icb_message.dest_chain == "cardano"
    print(f"  [PASS] Bridge->Cardano: {result.transport_used.value} ({result.latency_ms:.1f}ms)")


def test_bridge_executor_solana_ism():
    """Bridge to Solana uses Multi-ISM verification."""
    from bridge_executor import BridgeExecutor, BridgeStatus
    executor = BridgeExecutor(mock_mode=True)
    result = executor.execute("Solana", b"test_solana_tx")
    assert result.status == BridgeStatus.VERIFIED
    assert result.ism_verified == True
    assert result.icb_message is None  # No ICB for Solana
    print(f"  [PASS] Bridge->Solana: {result.transport_used.value}, ISM verified")


def test_bridge_fallback():
    """Fallback handler cascades on failure."""
    from bridge_executor import BridgeFallbackHandler, BridgeStatus
    handler = BridgeFallbackHandler()
    # Valid route should succeed on primary
    result = handler.bridge_with_fallback("Ethereum", b"test_eth")
    assert result.status == BridgeStatus.VERIFIED
    stats = handler.get_stats()
    assert stats["primary_success"] == 1
    print(f"  [PASS] Fallback handler: primary success for Ethereum")


def test_multi_ism_threshold():
    """Multi-ISM requires 2/3 verification."""
    from bridge_executor import MultiISMVerifier
    verifier = MultiISMVerifier(mock_mode=True)
    passed, results = verifier.verify("test_hash_abc")
    assert passed == True
    assert len(results) == 3
    assert sum(1 for r in results if r.verified) >= 2
    print(f"  [PASS] Multi-ISM: {sum(1 for r in results if r.verified)}/3 verified")


# ─────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 60)
    print("  VAMS Enhanced CLR v3.1 - Test Suite")
    print("=" * 60)

    tests = [
        ("CLR v3.1 Decision Tree", [
            test_p0_compliance_privacy,
            test_p1_confidential_compute,
            test_p2_high_value_security,
            test_p4_formal_verification,
            test_p5_velocity_hydra,
            test_p5_velocity_sei,
            test_p6_default_routing,
            test_access_control_denied,
            test_routing_hash,
        ]),
        ("MEV Protection", [
            test_encrypted_mempool,
            test_batch_auction,
            test_mev_slashing_report,
        ]),
        ("Bridge Executor + ICB", [
            test_icb_build_message,
            test_icb_verify_proof,
            test_icb_nonce_replay,
            test_bridge_executor_cardano,
            test_bridge_executor_solana_ism,
            test_bridge_fallback,
            test_multi_ism_threshold,
        ]),
    ]

    total = 0
    passed = 0
    failed = 0

    for section, test_fns in tests:
        print(f"\n[{section}]")
        for fn in test_fns:
            total += 1
            try:
                fn()
                passed += 1
            except Exception as e:
                failed += 1
                print(f"  [FAIL] {fn.__name__}: {e}")

    print()
    print("-" * 60)
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    print("-" * 60)
    print()

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
