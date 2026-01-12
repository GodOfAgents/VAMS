#!/usr/bin/env python3
"""
VAMS Neuron v0.5.0
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
    
    # Combined
    parser.add_argument("--full-health", action="store_true", help="Check all 4 layers")
    
    # General
    parser.add_argument("--interval", "-i", type=int, default=HEARTBEAT_INTERVAL,
                        help=f"Heartbeat interval (default: {HEARTBEAT_INTERVAL}s)")
    parser.add_argument("--version", "-v", action="version", version=f"VAMS Neuron {VERSION}")
    
    return parser.parse_args()


class VamsNeuron:
    """VAMS Neuron Client v0.5 - 4-Layer Stack + TEE"""
    
    def __init__(self, provider_name: str = "celestia", enable_failover: bool = True):
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
        
        # Layer 2
        self.compute_manager = ComputeManager()
        
        # Layer 3
        self.logic_monitor = LogicLayerMonitor()
        
        # Layer 4
        self.trust_manager = TrustManager()
        
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
        self.log("Loading cryptographic identity...", "CRYPTO")
        if os.path.exists(IDENTITY_PATH):
            try:
                with open(IDENTITY_PATH, "rb") as f:
                    self.sk = SigningKey.from_pem(f.read())
                self.log(f"Identity loaded from {IDENTITY_PATH}", "SUCCESS")
            except Exception:
                self._generate_new_identity()
        else:
            self._generate_new_identity()
        
        self.vk = self.sk.verifying_key
        self.node_id = self.vk.to_string().hex()[:16]
        self.storage.set_node_info("node_id", self.node_id)
        self.log(f"Node ID: {Fore.GREEN}{self.node_id}{Style.RESET_ALL}", "INFO")
    
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
            r = self.session.post(f"{VAMS_GATEWAY}/heartbeat", json={"payload": payload, "signature": signature}, timeout=5)
            if r.status_code == 200:
                self.gateway_available = True
                self.log("Gateway sync: SUCCESS", "SUCCESS")
                return True
        except:
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


def main():
    args = parse_args()
    
    if args.list_providers: list_da_providers(); return
    if args.list_compute: list_compute_providers(); return
    if args.list_logic: list_logic_providers(); return
    if args.list_trust: list_trust_providers(); return
    
    node = VamsNeuron(args.provider, not args.no_failover)
    
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
