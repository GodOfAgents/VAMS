#!/usr/bin/env python3
"""
VAMS Neuron v0.5.1
==================
Immortal Agent - Full 4-Layer Stack with TEE

Layer 1 - Data Availability:
  Celestia, EigenDA, Near DA, Avail

Layer 2 - Compute:
  io.net, Akash, Render, Bittensor

Layer 3 - Logic:
  DBOS-style workflows, Kwil, WeaveDB, Glacier

Layer 4 - Trust:
  Phala (SGX), Marlin (Nitro), Automata (1RPC)

This is a REAL node client with TEE-ready architecture.
"""

import sys
import os
import time
import json
import argparse
import signal
from datetime import datetime
from typing import Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- DEPENDENCY CHECK ---
try:
    import requests
    from ecdsa import SigningKey, VerifyingKey, SECP256k1
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError as e:
    print("[X] MISSING DEPENDENCIES")
    print(f"Error: {e}")
    print("\nPlease run: pip install -r requirements.txt")
    sys.exit(1)

from config import (
    VERSION, VAMS_GATEWAY, HEARTBEAT_INTERVAL,
    IDENTITY_PATH, BANNER,
    DEFAULT_PROVIDER, ENABLE_FAILOVER,
    DA_PROVIDERS, COMPUTE_PROVIDERS, LOGIC_PROVIDERS, TRUST_PROVIDERS
)
from storage import NeuronStorage
from providers import ProviderManager, ProviderStatus
from compute import ComputeManager, ComputeStatus
from workflows import run_demo_workflow, LogicLayerMonitor
from trust import TrustManager, TrustStatus

# SDK imports (optional - for real protocol integration)
try:
    from sdk.celestia import CelestiaDA, check_celestia_health
    from sdk.bittensor_subnet import BittensorSubnet, check_bittensor_health
    from sdk.phala_tee import PhalaTEE, check_all_tee_health
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="VAMS Neuron - Immortal Agent (4-Layer Stack + TEE)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python neuron.py                     # Run with default DA provider
  python neuron.py --full-health       # Check all 4 layers
  python neuron.py --check-trust       # Check Layer 4 (TEE) status
  python neuron.py --demo-workflow     # Run crash-proof workflow demo
        """
    )
    
    # Layer 1 options
    parser.add_argument("--provider", "-p", choices=["celestia", "eigenda", "near", "avail"],
                        default=DEFAULT_PROVIDER, help="Primary DA provider")
    parser.add_argument("--list-providers", "-l", action="store_true", help="List DA providers")
    parser.add_argument("--check-health", action="store_true", help="Check Layer 1 health")
    parser.add_argument("--no-failover", action="store_true", help="Disable failover")
    
    # Layer 2 options
    parser.add_argument("--check-compute", action="store_true", help="Check Layer 2 health")
    parser.add_argument("--list-compute", action="store_true", help="List compute providers")
    
    # Layer 3 options
    parser.add_argument("--check-logic", action="store_true", help="Check Layer 3 health")
    parser.add_argument("--list-logic", action="store_true", help="List logic providers")
    parser.add_argument("--demo-workflow", action="store_true", help="Run crash-proof workflow demo")
    
    # Layer 4 options
    parser.add_argument("--check-trust", action="store_true", help="Check Layer 4 (TEE) health")
    parser.add_argument("--list-trust", action="store_true", help="List trust providers")
    
    # CLR Router options
    parser.add_argument("--route", action="store_true", help="Run CLR routing logic")
    parser.add_argument("--value", type=float, default=100.0, help="Transaction value in USD")
    parser.add_argument("--latency", type=int, default=60000, help="Max latency in ms")
    parser.add_argument("--privacy", action="store_true", help="Require privacy (TEE/ZK)")
    parser.add_argument("--sovereign", action="store_true", help="Require sovereign chain")
    parser.add_argument("--tier", type=str, default="BRONZE", choices=["UNVERIFIED", "BRONZE", "SILVER", "GOLD", "PLATINUM"], 
                        help="Agent Trust Tier (Access Control)")
    
    # x402 Arguments
    parser.add_argument("--x402", action="store_true", help="Run x402 Payment Protocol demo")
    parser.add_argument("--service-provider", type=str, help="Provider address for x402 channel")
    parser.add_argument("--deposit", type=float, help="Initial channel deposit (VAMS)")

    parser.add_argument("--gateway-server", action="store_true", help="Launch VAMS Gateway Server")

    # Agent Comms
    parser.add_argument("--comms", action="store_true", help="Run Agent Communication demo")
    parser.add_argument("--send-to", type=str, help="Recipient Node ID")
    parser.add_argument("--msg", type=str, help="Message payload")

    # Combined
    parser.add_argument("--full-health", action="store_true", help="Check all 4 layers")
    
    # General
    parser.add_argument("--interval", "-i", type=int, default=HEARTBEAT_INTERVAL,
                        help=f"Heartbeat interval (default: {HEARTBEAT_INTERVAL}s)")
    parser.add_argument("--dry-run", action="store_true", 
                        help="Run with mock providers (no real network calls)")
    parser.add_argument("--use-sdk", action="store_true",
                        help="Use real SDK integrations (Celestia, Bittensor, Phala)")
    parser.add_argument("--sdk-health", action="store_true",
                        help="Check health using real SDK providers")
    parser.add_argument("--version", "-v", action="version", version=f"VAMS Neuron {VERSION}")
    
    return parser.parse_args()


class VamsNeuron:
    """VAMS Neuron Client v0.5 - 4-Layer Stack + TEE"""
    
    def __init__(
        self, 
        provider_name: str = "celestia", 
        enable_failover: bool = True,
        mock_mode: bool = False,
        use_sdk: bool = False
    ):
        self.mock_mode = mock_mode
        self.use_sdk = use_sdk and SDK_AVAILABLE
        self.sk: Optional[SigningKey] = None
        self.vk: Optional[VerifyingKey] = None
        self.node_id: str = ""
        self.session = requests.Session()
        self.storage = NeuronStorage()
        self.running = True
        self.gateway_available = False
        self.blocks_seen = 0
        self.start_time = time.time()
        
        # Layer 1
        self.provider_manager = ProviderManager()
        self.provider_manager.set_primary(provider_name)
        self.provider_manager.enable_failover(enable_failover)
        
        # Layer 2 - Pass mock_mode to BittensorProvider
        if mock_mode:
            from compute import BittensorProvider, IoNetProvider, AkashProvider, RenderProvider
            providers = [
                IoNetProvider(),  # Uses HTTP which is OK
                AkashProvider(),
                RenderProvider(),
                BittensorProvider(mock_mode=True)  # Use mock mode
            ]
            self.compute_manager = ComputeManager(providers=providers)
        else:
            self.compute_manager = ComputeManager()
        
        # Layer 3
        self.logic_monitor = LogicLayerMonitor()
        
        # Phase D: Decentralized Storage & Queue (Pillars 4, 5)
        try:
            from storage import ArweaveStorage, KwilStorage
            from request_queue import RequestQueue
            self.arweave = ArweaveStorage(key=os.getenv("VAMS_IRYS_KEY"))
            self.kwil = KwilStorage(db_id=os.getenv("VAMS_KWIL_DB"))
            self.queue = RequestQueue()
            self.log(f"Decentralized Storage & Queue initialized", "INFO")
        except ImportError:
            self.log("Storage/Queue modules missing or failed to load", "WARN")
            self.queue = None

        # Phase E: Gateway & Economics
        try:
            from gateway.client import GatewayClient
            from payments.x402 import X402Client
            from economic.circuit_breaker import CircuitBreaker
            self.gateway = GatewayClient(base_url=VAMS_GATEWAY)
            self.breaker = CircuitBreaker()
            self.x402 = X402Client(private_key=os.getenv("VAMS_PRIVATE_KEY"), circuit_breaker=self.breaker)
            self.log("Gateway & Economic Layer 5 initialized", "INFO")
        except ImportError as e:
            self.log(f"Economic modules failed: {e}", "WARN")

        # Layer 4
        self.trust_manager = TrustManager(mock_mode=mock_mode)
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        self.running = False
        self.log("Shutdown signal received...", "INFO")
    
    def log(self, msg: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {
            "INFO": Fore.CYAN, "NET": Fore.BLUE + Style.BRIGHT,
            "CRYPTO": Fore.MAGENTA, "SUCCESS": Fore.GREEN + Style.BRIGHT,
            "WARN": Fore.YELLOW, "ERROR": Fore.RED + Style.BRIGHT,
            "STATS": Fore.WHITE + Style.DIM,
            "L1": Fore.LIGHTBLUE_EX, "L2": Fore.LIGHTYELLOW_EX,
            "L3": Fore.LIGHTGREEN_EX, "L4": Fore.LIGHTMAGENTA_EX,
            "WORKFLOW": Fore.LIGHTCYAN_EX
        }
        color = colors.get(level, Fore.WHITE)
        print(f"{Fore.LIGHTBLACK_EX}[{timestamp}] {color}[{level:^8}]{Style.RESET_ALL} {msg}")
    
    def print_banner(self):
        print(Fore.GREEN + Style.BRIGHT + BANNER + Style.RESET_ALL)
        print(f" {Fore.CYAN}Version:{Style.RESET_ALL}  {VERSION}")
        provider = self.provider_manager.get_current_provider()
        print(f" {Fore.CYAN}DA Layer:{Style.RESET_ALL} {provider.name.upper()} ({provider.network})")
        print(f" {Fore.CYAN}Gateway:{Style.RESET_ALL}  {VAMS_GATEWAY}")
        print(" " + "-" * 60)
    
    def load_or_generate_identity(self):
        self.log("Loading VAMS Identity (Standard v1.0)...", "CRYPTO")
        
        # 1. Load Profile (The Soul)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        profile_path = os.path.join(base_dir, "profile.json")
        if os.path.exists(profile_path):
            try:
                with open(profile_path, "r") as f:
                    self.profile = json.load(f)
                self.log(f"Profile loaded: {self.profile.get('identity', {}).get('name', 'Unknown')}", "SUCCESS")
            except Exception as e:
                self.log(f"Failed to parse profile.json: {e}", "ERROR")
                self.profile = {}
        else:
            self.log("No profile.json found - using default Identity Standard", "WARN")
            self.profile = {"identity": {"name": "Anon-Agent"}, "capabilities": []}

        # 2. Load Keys (The Wallet)
        if os.path.exists(IDENTITY_PATH):
            try:
                with open(IDENTITY_PATH, "rb") as f:
                    self.sk = SigningKey.from_pem(f.read())
                self.log(f"Keys loaded from {IDENTITY_PATH}", "SUCCESS")
            except Exception:
                self._generate_new_identity()
        else:
            self._generate_new_identity()
        
        self.vk = self.sk.verifying_key
        self.node_id = self.vk.to_string().hex()[:16]
        self.storage.set_node_info("node_id", self.node_id)
        
        # 3. Print Identity Summary
        self.log(f"Node ID: {Fore.GREEN}{self.node_id}{Style.RESET_ALL}", "INFO")
        caps = len(self.profile.get("capabilities", []))
        self.log(f"Capabilities: {caps} skills loaded", "INFO")
    
    def _generate_new_identity(self):
        self.log("Generating new Secp256k1 keypair...", "CRYPTO")
        self.sk = SigningKey.generate(curve=SECP256k1)
        with open(IDENTITY_PATH, "wb") as f:
            f.write(self.sk.to_pem())
        self.log(f"New identity saved to {IDENTITY_PATH}", "SUCCESS")
    
    def sign_telemetry(self, block_height: int, provider: str) -> Tuple[str, str]:
        payload = json.dumps({
            "type": "VAMS_HEARTBEAT", "version": VERSION,
            "node_id": self.node_id, "block_height": block_height,
            "provider": provider, "timestamp": time.time(),
            "nonce": os.urandom(8).hex()
        }, separators=(',', ':'))
        return payload, self.sk.sign(payload.encode()).hex()
    
    def send_heartbeat(self, block_info) -> bool:
        payload, signature = self.sign_telemetry(block_info.height, block_info.provider)
        self.storage.store_heartbeat(self.node_id, block_info.height, block_info.network, payload, signature)
        
        colors = {"celestia": Fore.LIGHTBLUE_EX, "eigenda": Fore.LIGHTGREEN_EX,
                  "near": Fore.LIGHTYELLOW_EX, "avail": Fore.LIGHTMAGENTA_EX}
        c = colors.get(block_info.provider, Fore.WHITE)
        self.log(f"Block: #{block_info.height} [{c}{block_info.provider.upper()}{Style.RESET_ALL}]", "NET")
        self.log(f"Signature: {signature[:24]}...", "CRYPTO")
        
        try:
            success = False
            if hasattr(self, 'gateway') and self.gateway:
                success = self.gateway.send_heartbeat(payload, signature)
            else:
                # Fallback if gateway module failed to load but imports exist (unlikely)
                r = self.session.post(f"{VAMS_GATEWAY}/heartbeat", json={"payload": payload, "signature": signature}, timeout=5)
                success = r.status_code == 200
            
            if success:
                self.gateway_available = True
                self.log("Gateway sync: SUCCESS", "SUCCESS")
                return True
        except Exception as e:
            # self.log(f"Gateway error: {e}", "WARN") # Optional verbosity
            pass
        self.gateway_available = False
        self.log("Gateway offline - stored locally", "INFO")
        return False
    
    def check_l1_health(self):
        print()
        self.log("LAYER 1: Data Availability Providers", "L1")
        print()
        for name, status in self.provider_manager.check_all_health().items():
            if status.status == ProviderStatus.HEALTHY:
                c, s = Fore.GREEN, "[OK]"
            elif status.status == ProviderStatus.DEGRADED:
                c, s = Fore.YELLOW, "[!!]"
            else:
                c, s = Fore.RED, "[XX]"
            block = f"Block #{status.last_block}" if status.last_block else "N/A"
            print(f"  {c}{s}{Style.RESET_ALL} {name.upper():10} {status.latency_ms:>6.0f}ms | {block}")
        print()
    
    def check_l2_health(self):
        print()
        self.log("LAYER 2: Compute Providers", "L2")
        print()
        for name, info in self.compute_manager.check_all_status().items():
            if info.status == ComputeStatus.HEALTHY:
                c, s = Fore.GREEN, "[OK]"
            elif info.status == ComputeStatus.DEGRADED:
                c, s = Fore.YELLOW, "[!!]"
            else:
                c, s = Fore.RED, "[XX]"
            print(f"  {c}{s}{Style.RESET_ALL} {name.upper():12} {info.latency_ms:>6.0f}ms")
        print()
    
    def check_l3_health(self):
        print()
        self.log("LAYER 3: Logic Providers", "L3")
        print()
        for name, info in self.logic_monitor.check_all().items():
            if info["status"] == "healthy":
                c, s = Fore.GREEN, "[OK]"
            elif info["status"] == "degraded":
                c, s = Fore.YELLOW, "[!!]"
            else:
                c, s = Fore.RED, "[XX]"
            print(f"  {c}{s}{Style.RESET_ALL} {name.upper():10} {info['latency_ms']:>6.0f}ms | {info['description']}")
        print()
    
    def check_l4_health(self):
        print()
        self.log("LAYER 4: Trust Providers (TEE)", "L4")
        print()
        for name, info in self.trust_manager.check_all_status().items():
            if info.status == TrustStatus.HEALTHY:
                c, s = Fore.GREEN, "[OK]"
            elif info.status == TrustStatus.DEGRADED:
                c, s = Fore.YELLOW, "[!!]"
            else:
                c, s = Fore.RED, "[XX]"
            print(f"  {c}{s}{Style.RESET_ALL} {name.upper():10} {info.latency_ms:>6.0f}ms | {info.technology}")
        print()
    
    def check_full_health(self):
        self.check_l1_health()
        self.check_l2_health()
        self.check_l3_health()
        self.check_l4_health()
    
    def check_sdk_health(self):
        """Check health using real SDK integrations."""
        if not SDK_AVAILABLE:
            self.log("SDK modules not available. Install with: pip install -r requirements.txt", "ERROR")
            return
        
        print()
        self.log("SDK Health Check - Real Protocol Integrations", "INFO")
        print()
        
        # Layer 1: Celestia DA
        print(f"  {Fore.CYAN}--- Layer 1: Data Availability ---{Style.RESET_ALL}")
        try:
            celestia = CelestiaDA()
            health = celestia.check_health()
            if health["status"] == "healthy":
                c, s = Fore.GREEN, "[OK]"
            elif health["status"] == "degraded":
                c, s = Fore.YELLOW, "[!!]"
            else:
                c, s = Fore.RED, "[XX]"
            block = health.get("block_height", "N/A")
            print(f"  {c}{s}{Style.RESET_ALL} CELESTIA    {health.get('latency_ms', 0):>6.0f}ms | Block #{block}")
        except Exception as e:
            print(f"  {Fore.RED}[XX]{Style.RESET_ALL} CELESTIA    Error: {str(e)[:40]}")
        
        print()
        
        # Layer 2: Bittensor
        print(f"  {Fore.YELLOW}--- Layer 2: Compute (Bittensor) ---{Style.RESET_ALL}")
        try:
            bt = BittensorSubnet()
            health = bt.check_health()
            if health["status"] == "healthy":
                c, s = Fore.GREEN, "[OK]"
            elif health["status"] == "unavailable":
                c, s = Fore.YELLOW, "[!!]"
            else:
                c, s = Fore.RED, "[XX]"
            block = health.get("block", "N/A")
            print(f"  {c}{s}{Style.RESET_ALL} BITTENSOR   {health.get('latency_ms', 0):>6.0f}ms | Network: {health.get('network', 'N/A')}")
            
            # Show subnet info
            sn1 = bt.get_subnet_info(1)
            if sn1:
                print(f"       +-- SN1 ({sn1.name[:25]}): {sn1.miners} miners, {sn1.validators} validators")
        except Exception as e:
            print(f"  {Fore.RED}[XX]{Style.RESET_ALL} BITTENSOR   Error: {str(e)[:40]}")
        
        print()
        
        # Layer 4: TEE Providers
        print(f"  {Fore.MAGENTA}--- Layer 4: Trust (TEE) ---{Style.RESET_ALL}")
        try:
            tee_health = check_all_tee_health()
            for provider, health in tee_health.items():
                if health["status"] == "healthy":
                    c, s = Fore.GREEN, "[OK]"
                elif health["status"] == "degraded":
                    c, s = Fore.YELLOW, "[!!]"
                else:
                    c, s = Fore.RED, "[XX]"
                tech = health.get("technology", "N/A")
                print(f"  {c}{s}{Style.RESET_ALL} {provider.upper():10} {health.get('latency_ms', 0):>6.0f}ms | {tech}")
        except Exception as e:
            print(f"  {Fore.RED}[XX]{Style.RESET_ALL} TEE         Error: {str(e)[:40]}")
        
        print()
        print(f"  {Fore.CYAN}Tip:{Style.RESET_ALL} For Celestia, run a light node: celestia light start --p2p.network mocha")
        print(f"  {Fore.CYAN}Tip:{Style.RESET_ALL} For Bittensor, install: pip install bittensor")
        print()
    
    def run_workflow_demo(self):
        print()
        self.log("DBOS-Style Crash-Proof Workflow Demo", "WORKFLOW")
        run_demo_workflow(lambda m: print(f"  {m}"))
        print()
    
    def run(self, heartbeat_interval: int = HEARTBEAT_INTERVAL):
        self.print_banner()
        print()
        self.load_or_generate_identity()
        print()
        
        self.log("Checking DA providers...", "L1")
        self.provider_manager.check_all_health()
        
        block_info = self.provider_manager.get_latest_block()
        if block_info:
            self.log(f"Connected to {block_info.provider.upper()} at block #{block_info.height}", "SUCCESS")
        
        print()
        self.log(f"Starting heartbeat loop (interval: {heartbeat_interval}s)", "INFO")
        print(" " + "-" * 60)
        print()
        
        while self.running:
            try:
                # Circuit Breaker Check
                if hasattr(self, 'breaker') and not self.breaker.is_active():
                    self.log(f"HALTED: {self.breaker.trip_reason} (Next check in 10s)", "ERROR")
                    time.sleep(10)
                    continue

                block_info = self.provider_manager.get_latest_block()
                if block_info:
                    self.blocks_seen += 1
                    self.send_heartbeat(block_info)
                    if self.blocks_seen % 5 == 0:
                        stats = self.storage.get_stats()
                        self.log(f"Blocks: {self.blocks_seen} | Pending: {stats['pending_sync']}", "STATS")
                time.sleep(heartbeat_interval)
            except Exception as e:
                self.log(f"Error: {e}", "ERROR")
                time.sleep(5)
        
        print()
        self.log("Shutdown complete", "SUCCESS")


def list_da_providers():
    print(f"\n{Fore.CYAN}LAYER 1: Data Availability{Style.RESET_ALL}\n" + "-" * 40)
    for n, c in DA_PROVIDERS.items():
        print(f"\n  {Fore.GREEN}{n.upper()}{Style.RESET_ALL}\n    {c['description']}")

def list_compute_providers():
    print(f"\n{Fore.YELLOW}LAYER 2: Compute{Style.RESET_ALL}\n" + "-" * 40)
    for n, c in COMPUTE_PROVIDERS.items():
        print(f"\n  {Fore.GREEN}{n.upper()}{Style.RESET_ALL}\n    {c['description']}")

def list_logic_providers():
    print(f"\n{Fore.GREEN}LAYER 3: Logic{Style.RESET_ALL}\n" + "-" * 40)
    for n, c in LOGIC_PROVIDERS.items():
        print(f"\n  {Fore.GREEN}{n.upper()}{Style.RESET_ALL}\n    {c['description']}")

def list_trust_providers():
    print(f"\n{Fore.MAGENTA}LAYER 4: Trust (TEE){Style.RESET_ALL}\n" + "-" * 40)
    for n, c in TRUST_PROVIDERS.items():
        print(f"\n  {Fore.GREEN}{n.upper()}{Style.RESET_ALL} [{c['technology']}]\n    {c['description']}")



def run_routing_logic(args):
    """Execute CLR routing logic."""
    from colorama import Fore, Style
    from clr_router import CLRouter, TransactionIntent, TrustTier
    
    print(f"\n{Fore.CYAN}VAMS Conditional L1 Router (CLR){Style.RESET_ALL}")
    print("=" * 40)
    
    # Map tier string to enum
    tier_map = {
        "UNVERIFIED": TrustTier.UNVERIFIED,
        "BRONZE": TrustTier.BRONZE,
        "SILVER": TrustTier.SILVER,
        "GOLD": TrustTier.GOLD,
        "PLATINUM": TrustTier.PLATINUM
    }
    agent_tier = tier_map.get(args.tier.upper(), TrustTier.UNVERIFIED)
    
    intent = TransactionIntent(
        value_usd=args.value,
        max_latency_ms=args.latency,
        requires_privacy=args.privacy,
        requires_sovereignty=args.sovereign
    )
    
    print(f"Intent: Value=${args.value:,.2f} | Latency<{args.latency}ms | Privacy={args.privacy} | Tier={agent_tier.name}")
    print("-" * 40)
    
    try:
        router = CLRouter()
        print(f"Fetching live metrics from 10 chains...")
        decision = router.route(intent, agent_tier)
        
        print(f"\n{Fore.GREEN}✅ ROUTING SUCCESS{Style.RESET_ALL}")
        print(f"Target Chain:   {Style.BRIGHT}{decision.chain}{Style.RESET_ALL}")
        print(f"Bridge:         {decision.target_bridge}")
        print(f"Est Fee:        ${decision.fee_estimate_usd:.4f}")
        print(f"Block Time:     {decision.metrics.block_time_ms} ms")
        print(f"Reason:         {decision.reason}")
        
    except PermissionError as e:
        print(f"\n{Fore.RED}❌ ACCESS DENIED (Policy Violation){Style.RESET_ALL}")
        print(f"Reason: {str(e)}")
    except ValueError as e:
        print(f"\n{Fore.YELLOW}⚠️ UNROUTABLE (Hard Constraint){Style.RESET_ALL}")
        print(f"Reason: {str(e)}")
    except Exception as e:
        print(f"\n{Fore.RED}❌ ERROR{Style.RESET_ALL}")
        print(f"{str(e)}")
    print()


def main():
    args = parse_args()
    
    if args.gateway_server:
        from gateway.server import start_server
        print(f"🚀 Starting VAMS Gateway Server on port 8000...")
        start_server()
        return

    if args.comms:
        from colorama import Fore, Style
        from agent_comms import AgentCommunicator
        from ecdsa import SigningKey, SECP256k1
        from config import IDENTITY_PATH
        
        # Load Identity
        try:
            with open(IDENTITY_PATH, "rb") as f:
                sk = SigningKey.from_pem(f.read())
                node_id = sk.verifying_key.to_string().hex()[:16]
                print(f"Identity loaded: {Fore.GREEN}{node_id}{Style.RESET_ALL} from {IDENTITY_PATH}")
        except FileNotFoundError:
            print(f"{Fore.RED}Identity not found. Run without args first to generate.{Style.RESET_ALL}")
            return

        comms = AgentCommunicator(sk, node_id)
        
        if args.send_to and args.msg:
            print(f"[*] Sending message to {args.send_to}...")
            msg = comms.create_message(args.send_to, {"text": args.msg})
            print(f"{Fore.CYAN}Signed Message:{Style.RESET_ALL} {msg.signature[:16]}...")
            
            # Simulate Receive (Loopback)
            print(f"[*] Simulating network transmission...")
            from dataclasses import asdict
            comms.receive_message(asdict(msg), sk.verifying_key.to_string().hex())
            print(f"\n{Fore.GREEN}✅ Message logged to audit.log{Style.RESET_ALL}")
        else:
            print("Listening for messages... (Mock Mode)")
            print("Use --send-to <id> --msg <text> to test.")
        return

    if args.route: run_routing_logic(args); return
    
    if args.x402:
        from colorama import Fore, Style
        from payments.x402 import X402Client
        
        from economic.circuit_breaker import CircuitBreaker
        
        print(f"\n{Fore.CYAN}VAMS x402 Payment Protocol{Style.RESET_ALL}")
        print("=" * 40)
        
        breaker = CircuitBreaker()
        client = X402Client(circuit_breaker=breaker)
        provider = args.service_provider or "0xProviderAddress"
        deposit = args.deposit or 100.0
        
        print(f"Agent:    {client.address}")
        print(f"Provider: {provider}")
        print(f"Goal:     Purchase 'inference-01' service")
        print("-" * 40)
        
        # 1. Open Channel
        print(f"[*] Opening Payment Channel (Cap: {deposit} VAMS)...")
        channel_id = client.open_channel(provider, deposit)
        
        if channel_id:
            print(f"\n{Fore.GREEN}✅ Channel Open: {channel_id}{Style.RESET_ALL}")
            
            # 2. Simulate 402 Challenge
            print(f"[*] Requesting Service...")
            print(f"    < HTTP 402 Payment Required")
            headers = {
                "WWW-Authenticate": f'x402 chain=80002 contract="{provider}" amount="5.0" service="inference-01"'
            }
            print(f"    < WWW-Authenticate: {headers['WWW-Authenticate']}")
            
            # 3. Generate Payment
            token = client.handle_402(headers, "http://provider/api/v1/infer")
            
            if token:
                print(f"\n{Fore.GREEN}✅ Payment Generated{Style.RESET_ALL}")
                print(f"    > Authorization: x402 {token[:20]}...")
                
                # Decode for display
                import base64
                import json
                decoded = json.loads(base64.b64decode(token).decode())
                print(f"    - Nonce:     {decoded['payment'][3]}")
                print(f"    - Signature: {decoded['signature']}")
                
                # 4. Verify Balance
                balance = client.get_channel_balance(channel_id)
                print(f"[*] Remaining Channel Balance: {balance / 10**18:.2f} VAMS")
            else:
                print(f"{Fore.RED}❌ Payment Generation Failed{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}❌ Channel Creation Failed{Style.RESET_ALL}")
        return

    if args.list_providers: list_da_providers(); return
    if args.list_compute: list_compute_providers(); return
    if args.list_logic: list_logic_providers(); return
    if args.list_trust: list_trust_providers(); return
    
    # Create node with mock_mode if --dry-run is specified
    node = VamsNeuron(
        provider_name=args.provider, 
        enable_failover=not args.no_failover,
        mock_mode=args.dry_run,
        use_sdk=args.use_sdk
    )
    
    if args.dry_run:
        node.log("Running in DRY-RUN mode (mock providers)", "WARN")
    
    if args.use_sdk:
        node.log("Using real SDK integrations", "INFO")
    
    if args.sdk_health: node.check_sdk_health(); return
    if args.full_health: node.check_full_health(); return
    if args.check_health: node.check_l1_health(); return
    if args.check_compute: node.check_l2_health(); return
    if args.check_logic: node.check_l3_health(); return
    if args.check_trust: node.check_l4_health(); return
    if args.demo_workflow: node.run_workflow_demo(); return
    
    print()
    node.run(args.interval)


if __name__ == "__main__":
    main()
