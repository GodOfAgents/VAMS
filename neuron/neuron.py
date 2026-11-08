#!/usr/bin/env python3
"""
VAMS Neuron v0.5.1
==================
Immortal Agent - Full 4-Layer Stack with TEE

Layer 1 - Data Availability:
  Celestia, EigenDA, Near DA, Avail, Iagon

Layer 2 - Compute:
  io.net, Akash, Render, Bittensor, Phala AI

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
from typing import Mapping, Optional, Tuple

if not __package__:  # PEP 366 bootstrap for direct script execution.
    _neuron_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(_neuron_dir))
    __package__ = "neuron"

from .runtime_safety import (
    ImmutableRuntimeConfiguration,
    LiveModeSafetyError,
    RuntimeConfigurationError,
    RuntimePolicy,
    load_runtime_policy,
    resolve_component_mock_mode,
)

# Load .env file if present (DBOS_SYSTEM_DATABASE_URL, VAMS_PRIVATE_KEY, etc.)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — env vars must be set manually

# DBOS durable workflow engine (optional — degrades gracefully if Postgres not configured)
try:
    from dbos_config import init_dbos, destroy_dbos
    from dbos import DBOS
    _DBOS_AVAILABLE = True
except ImportError:
    _DBOS_AVAILABLE = False

# --- DEPENDENCY CHECK ---
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError as e:
    print("[X] MISSING DEPENDENCIES")
    print(f"Error: {e}")
    print("\nPlease run: pip install -r requirements.txt")
    sys.exit(1)

from .secp256k1 import (
    PrivateKey,
    PublicKey,
    generate_private_key,
    load_private_key_pem,
    private_key_pem,
    public_key_bytes,
    sign_message,
)

from .config import (
    VERSION, VAMS_GATEWAY, HEARTBEAT_INTERVAL,
    IDENTITY_PATH, BANNER,
    DEFAULT_PROVIDER, ENABLE_FAILOVER,
    DA_PROVIDERS, COMPUTE_PROVIDERS, LOGIC_PROVIDERS, TRUST_PROVIDERS
)
from .storage import NeuronStorage
from .providers import ProviderManager, ProviderStatus
from .compute import ComputeManager, ComputeStatus
from .workflows import run_demo_workflow, LogicLayerMonitor
from .trust import TrustManager, TrustStatus

# SDK imports (optional - for real protocol integration)
try:
    from .sdk.celestia import CelestiaDA, check_celestia_health
    from .sdk.bittensor_subnet import BittensorSubnet, check_bittensor_health
    from .sdk.phala_tee import PhalaTEE, check_all_tee_health
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

# AgentOS Cognitive Runtime (optional - graceful degradation)
try:
    from .sdk.semantic_checkpoint import SemanticCheckpointManager, CheckpointTrigger
    from .sdk.semantic_mmu import SemanticMMU, MemoryTier
    from .sdk.interrupt_handler import InterruptVectorTable, InterruptSignal
    from .sdk.cognitive_drift import CognitiveDriftDetector
    AGENTOS_AVAILABLE = True
except ImportError:
    AGENTOS_AVAILABLE = False


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
    parser.add_argument("--provider", "-p", choices=["celestia", "eigenda", "near", "avail", "iagon"],
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
    parser.add_argument("--check-cognitive", action="store_true", help="Check AgentOS Cognitive Runtime health")
    
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


NEURON_MOCK_VARIABLE = "NEURON_MOCK_MODE"


class _NeuronRuntimeDriftError(RuntimeError):
    """Private fixed-message signal for this instance's runtime recheck."""

    def __init__(self):
        super().__init__("Neuron runtime configuration changed; operation denied")


class VamsNeuron(ImmutableRuntimeConfiguration):
    """VAMS Neuron Client v0.5 - 4-Layer Stack + TEE"""

    _immutable_runtime_fields = frozenset(
        {"mock_mode", "runtime_policy", "use_sdk"}
    )
    
    def __init__(
        self, 
        provider_name: str = "celestia", 
        enable_failover: bool = True,
        mock_mode: Optional[bool] = None,
        use_sdk: bool = False,
        *,
        environ: Optional[Mapping[str, str]] = None,
        policy: Optional[RuntimePolicy] = None,
    ):
        ambient_policy = load_runtime_policy(os.environ)
        if policy is not None:
            if not isinstance(policy, RuntimePolicy):
                raise RuntimeConfigurationError(
                    "Malformed supplied runtime policy for VamsNeuron"
                )
            if policy != ambient_policy:
                raise RuntimeConfigurationError(
                    "Conflicting runtime policy for VamsNeuron; supplied policy "
                    "must match the actual process"
                )

        source = os.environ if environ is None else environ
        if environ is not None:
            if not isinstance(environ, Mapping):
                raise RuntimeConfigurationError(
                    "Malformed supplied environment policy for VamsNeuron"
                )
            supplied_policy = load_runtime_policy(environ)
            if supplied_policy != ambient_policy:
                raise RuntimeConfigurationError(
                    "Conflicting environment policy for VamsNeuron; supplied "
                    "environment must match the actual process"
                )

        effective_mock = resolve_component_mock_mode(
            "VamsNeuron",
            NEURON_MOCK_VARIABLE,
            mock_mode,
            policy=ambient_policy,
            environ=os.environ,
        )
        if environ is not None:
            supplied_mock = resolve_component_mock_mode(
                "VamsNeuron",
                NEURON_MOCK_VARIABLE,
                mock_mode,
                policy=ambient_policy,
                environ=source,
            )
            if supplied_mock != effective_mock:
                raise RuntimeConfigurationError(
                    "Conflicting mock selection for VamsNeuron; supplied "
                    "environment must match the actual process"
                )
        if ambient_policy.is_live:
            raise LiveModeSafetyError(
                "VamsNeuron live startup is disabled until payment, bridge, recovery, "
                "legacy DA routing, and provider effects are authoritative"
            )
        self.runtime_policy = ambient_policy
        self.mock_mode = effective_mock
        mock_mode = effective_mock
        self.use_sdk = use_sdk and SDK_AVAILABLE
        self.sk: Optional[PrivateKey] = None
        self.vk: Optional[PublicKey] = None
        self.node_id: str = ""
        current_policy = load_runtime_policy(os.environ)
        if current_policy != self.runtime_policy:
            raise RuntimeConfigurationError(
                "VamsNeuron runtime configuration changed during initialization"
            )
        current_mock = resolve_component_mock_mode(
            "VamsNeuron",
            NEURON_MOCK_VARIABLE,
            self.mock_mode,
            policy=current_policy,
            environ=os.environ,
        )
        if current_mock != self.mock_mode:
            raise RuntimeConfigurationError(
                "VamsNeuron mock selection changed during initialization"
            )

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
            from .compute import BittensorProvider, IoNetProvider, AkashProvider, RenderProvider, PhalaComputeProvider
            providers = [
                IoNetProvider(),  # Uses HTTP which is OK
                AkashProvider(),
                RenderProvider(),
                BittensorProvider(mock_mode=True),  # Use mock mode
                PhalaComputeProvider()
            ]
            self.compute_manager = ComputeManager(providers=providers)
        else:
            self.compute_manager = ComputeManager()
        
        # Layer 3
        self.logic_monitor = LogicLayerMonitor()
        
        # Phase D: Decentralized Storage & Queue (Pillars 4, 5)
        try:
            from .storage import ArweaveStorage, KwilStorage
            from .request_queue import RequestQueue
            self.arweave = ArweaveStorage(key=os.getenv("VAMS_IRYS_KEY"))
            self.kwil = KwilStorage(db_id=os.getenv("VAMS_KWIL_DB"))
            self.queue = RequestQueue()
            self.log(f"Decentralized Storage & Queue initialized", "INFO")
        except ImportError:
            self.log("Storage/Queue modules missing or failed to load", "WARN")
            self.queue = None

        # Sequence Wallet Manager
        try:
            from .sdk.sequence_wallet import SequenceWalletManager
            self.sequence_wallet_manager = SequenceWalletManager(
                mock_mode=mock_mode,
                runtime_policy=self.runtime_policy,
                environ=source,
            )
            self.log("Sequence Wallet Manager initialized", "INFO")
        except ImportError:
            self.sequence_wallet_manager = None
            self.log("Sequence Wallet module not found", "WARN")

        # Phase E: Gateway & Economics
        try:
            from .gateway.client import GatewayClient
            from .payments.x402 import X402Client
            from .economic.circuit_breaker import CircuitBreaker
            self.gateway = GatewayClient(
                base_url=VAMS_GATEWAY,
                runtime_policy=self.runtime_policy,
                environ=source,
            )
            self.breaker = CircuitBreaker()
            self.x402 = X402Client(
                private_key=source.get("VAMS_PRIVATE_KEY"),
                session_key=source.get("VAMS_SESSION_KEY"),
                smart_wallet_address=source.get("VAMS_SMART_WALLET_ADDRESS"),
                circuit_breaker=self.breaker,
                mock_mode=mock_mode,
                environ=source,
                policy=self.runtime_policy,
            )
            self.log("Gateway & Economic Layer 5 initialized", "INFO")
        except ImportError as e:
            self.log(f"Economic modules failed: {e}", "WARN")

        # Layer 4
        self.trust_manager = TrustManager(mock_mode=mock_mode)
        
        # AgentOS Cognitive Runtime (Layer 3 Enhancement)
        self.agentos_enabled = False
        if AGENTOS_AVAILABLE:
            try:
                from .config import (
                    CID_EPSILON, CID_MIN_INTERVAL, CID_MAX_INTERVAL,
                    SMMU_L1_CAPACITY, SMMU_L2_PROVIDER, SMMU_L3_PROVIDER,
                    IVT_TIMEOUT_MS, IVT_MAX_RETRIES,
                    DRIFT_THETA, DRIFT_GAMMA
                )
                self.semantic_manager = SemanticCheckpointManager(
                    epsilon=CID_EPSILON,
                    min_interval=CID_MIN_INTERVAL,
                    max_interval=CID_MAX_INTERVAL
                )
                self.memory = SemanticMMU(
                    l1_capacity=SMMU_L1_CAPACITY,
                    l2_provider=SMMU_L2_PROVIDER,
                    l3_provider=SMMU_L3_PROVIDER
                )
                self.ivt = InterruptVectorTable(
                    agent_id=self.node_id or "initializing",
                    mock_mode=mock_mode,
                    timeout_ms=IVT_TIMEOUT_MS,
                    max_retries=IVT_MAX_RETRIES,
                    environ=source,
                    policy=self.runtime_policy,
                )
                self.drift_detector = CognitiveDriftDetector(
                    theta=DRIFT_THETA,
                    gamma=DRIFT_GAMMA,
                    mock_mode=mock_mode,
                    environ=source,
                    policy=self.runtime_policy,
                )
                self.agentos_enabled = True
                self.log("AgentOS Cognitive Runtime initialized", "INFO")
            except Exception as e:
                self.log(f"AgentOS init skipped: {e}", "WARN")
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        self._freeze_runtime_configuration()

        # ── DBOS durable workflow engine ──────────────────────────────────────
        self._dbos_active = False
        if _DBOS_AVAILABLE and os.environ.get("DBOS_SYSTEM_DATABASE_URL"):
            try:
                init_dbos()
                DBOS.launch()
                self._dbos_active = True
                self.log("DBOS durable workflow engine: ACTIVE", "L3")
            except Exception as _dbos_err:
                self.log(f"DBOS init failed (workflows will be unavailable): {_dbos_err}", "WARN")
        else:
            self.log(
                "DBOS_SYSTEM_DATABASE_URL not set — workflow engine disabled. "
                "See neuron/.env.example to configure Postgres.",
                "WARN"
            )
    
    def _signal_handler(self, signum, frame):
        self.running = False
        self.log("Shutdown signal received...", "INFO")
        if self._dbos_active and _DBOS_AVAILABLE:
            destroy_dbos()
    
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
    
    def _assert_current_runtime(self) -> None:
        """Reject process-mode or bound-mock drift without exposing parser text."""

        try:
            if type(self.runtime_policy) is not RuntimePolicy or type(self.mock_mode) is not bool:
                raise _NeuronRuntimeDriftError()
            current_policy = load_runtime_policy(os.environ)
            if (
                type(current_policy) is not RuntimePolicy
                or current_policy.is_live
                or self.runtime_policy.is_live
                or current_policy != self.runtime_policy
            ):
                raise _NeuronRuntimeDriftError()
            current_mock = resolve_component_mock_mode(
                "VamsNeuron",
                NEURON_MOCK_VARIABLE,
                self.mock_mode,
                policy=current_policy,
                environ=os.environ,
            )
            if current_mock != self.mock_mode:
                raise _NeuronRuntimeDriftError()
        except _NeuronRuntimeDriftError:
            raise
        except Exception:
            raise _NeuronRuntimeDriftError() from None

    def _read_file_with_runtime_checks(self, file_obj, failure_message: str):
        """Read and close one acquired file while preserving policy denial."""

        contents = None
        read_error = None
        guard_error = None
        try:
            self._assert_current_runtime()
            contents = file_obj.read()
            self._assert_current_runtime()
        except _NeuronRuntimeDriftError as exc:
            guard_error = exc
        except BaseException as exc:
            read_error = exc
            try:
                self._assert_current_runtime()
            except _NeuronRuntimeDriftError as drift:
                guard_error = drift
            except BaseException as check_error:
                if not isinstance(check_error, Exception) and isinstance(read_error, Exception):
                    read_error = check_error

        close_error = None
        try:
            file_obj.close()
        except BaseException as exc:
            close_error = exc

        final_guard_error = None
        try:
            self._assert_current_runtime()
        except _NeuronRuntimeDriftError as exc:
            final_guard_error = exc
        except BaseException as exc:
            final_guard_error = exc

        errors = (guard_error, final_guard_error, read_error, close_error)
        private_guard = next(
            (error for error in errors if isinstance(error, _NeuronRuntimeDriftError)),
            None,
        )
        if private_guard is not None:
            raise private_guard
        control_error = next(
            (error for error in (read_error, close_error, final_guard_error)
             if error is not None and not isinstance(error, Exception)),
            None,
        )
        if control_error is not None:
            raise control_error
        if any(error is not None for error in errors):
            raise RuntimeError(failure_message) from None
        return contents

    def load_or_generate_identity(self):
        self._assert_current_runtime()
        self.log("Loading VAMS Identity (Standard v1.0)...", "CRYPTO")
        
        # 1. Load Profile (The Soul)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        profile_path = os.path.join(base_dir, "profile.json")
        if os.path.exists(profile_path):
            try:
                self._assert_current_runtime()
                profile_file = open(profile_path, "r")
                profile_text = self._read_file_with_runtime_checks(
                    profile_file, "Unable to read Neuron profile"
                )
                self.profile = json.loads(profile_text)
                self._assert_current_runtime()
                self.log(f"Profile loaded: {self.profile.get('identity', {}).get('name', 'Unknown')}", "SUCCESS")
            except _NeuronRuntimeDriftError:
                raise
            except LiveModeSafetyError:
                self._assert_current_runtime()
                raise RuntimeError("Profile loading was refused") from None
            except Exception:
                self._assert_current_runtime()
                self.log("Failed to parse profile.json; using defaults", "ERROR")
                self.profile = {}
        else:
            self.log("No profile.json found - using default Identity Standard", "WARN")
            self.profile = {"identity": {"name": "Anon-Agent"}, "capabilities": []}

        # 2. Load Keys (The Wallet). Only failure to open the exact path because
        # it is absent allows first-time generation; read/parse errors fail closed.
        self._assert_current_runtime()
        try:
            key_file = open(IDENTITY_PATH, "rb")
        except _NeuronRuntimeDriftError:
            raise
        except FileNotFoundError:
            if (
                getattr(self, "sk", None) is not None
                or getattr(self, "vk", None) is not None
                or getattr(self, "node_id", "")
            ):
                raise RuntimeError(
                    "Neuron identity file is missing for an initialized identity"
                ) from None
            self._generate_new_identity()
        except Exception:
            self._assert_current_runtime()
            raise RuntimeError("Unable to read existing Neuron identity") from None
        else:
            key_bytes = self._read_file_with_runtime_checks(
                key_file, "Unable to read existing Neuron identity"
            )
            self._assert_current_runtime()
            try:
                candidate_key = load_private_key_pem(key_bytes)
            except _NeuronRuntimeDriftError:
                raise
            except Exception:
                self._assert_current_runtime()
                raise RuntimeError("Existing Neuron identity is invalid") from None
            self._assert_current_runtime()
            self.sk = candidate_key
            self.log(f"Keys loaded from {IDENTITY_PATH}", "SUCCESS")

        self._assert_current_runtime()
        try:
            candidate_public_key = self.sk.public_key()
        except _NeuronRuntimeDriftError:
            raise
        except Exception:
            self._assert_current_runtime()
            raise RuntimeError("Unable to derive Neuron public identity") from None
        self._assert_current_runtime()
        try:
            candidate_node_id = public_key_bytes(candidate_public_key).hex()[:16]
        except _NeuronRuntimeDriftError:
            raise
        except Exception:
            self._assert_current_runtime()
            raise RuntimeError("Unable to encode Neuron public identity") from None
        self._assert_current_runtime()
        self.vk = candidate_public_key
        self.node_id = candidate_node_id
        self._assert_current_runtime()
        try:
            self.storage.set_node_info("node_id", candidate_node_id)
        except _NeuronRuntimeDriftError:
            raise
        except Exception:
            self._assert_current_runtime()
            raise RuntimeError("Unable to persist Neuron node identity") from None
        self._assert_current_runtime()
        
        # 3. Print Identity Summary
        self.log(f"Node ID: {Fore.GREEN}{self.node_id}{Style.RESET_ALL}", "INFO")
        caps = len(self.profile.get("capabilities", []))
        self.log(f"Capabilities: {caps} skills loaded", "INFO")
    
    def _generate_new_identity(self):
        self._assert_current_runtime()
        if (
            getattr(self, "sk", None) is not None
            or getattr(self, "vk", None) is not None
            or getattr(self, "node_id", "")
        ):
            raise RuntimeError("Neuron identity is already initialized")
        self.log("Generating new Secp256k1 keypair...", "CRYPTO")
        self._assert_current_runtime()
        try:
            candidate_key = generate_private_key()
            self._assert_current_runtime()
            key_bytes = private_key_pem(candidate_key)
            self._assert_current_runtime()
        except _NeuronRuntimeDriftError:
            raise
        except Exception:
            self._assert_current_runtime()
            raise RuntimeError("Unable to prepare new Neuron identity") from None
        self._assert_current_runtime()
        try:
            key_file = open(
                IDENTITY_PATH,
                "xb",
                opener=lambda path, flags: os.open(path, flags, 0o600),
            )
        except _NeuronRuntimeDriftError:
            raise
        except Exception:
            self._assert_current_runtime()
            raise RuntimeError("Unable to create Neuron identity exclusively") from None

        primary_error = None
        try:
            self._assert_current_runtime()
            written = key_file.write(key_bytes)
            self._assert_current_runtime()
            if written != len(key_bytes):
                raise OSError("short identity write")
            key_file.flush()
            self._assert_current_runtime()
        except BaseException as exc:
            primary_error = exc
            try:
                self._assert_current_runtime()
            except _NeuronRuntimeDriftError as drift:
                primary_error = drift
            except BaseException as check_error:
                if not isinstance(check_error, Exception) and isinstance(primary_error, Exception):
                    primary_error = check_error

        close_error = None
        try:
            key_file.close()
        except BaseException as exc:
            close_error = exc

        final_guard_error = None
        try:
            self._assert_current_runtime()
        except BaseException as exc:
            final_guard_error = exc

        # A guard denial wins over write/close failures, including process
        # control exceptions. Otherwise preserve the first control exception.
        errors = (primary_error, close_error, final_guard_error)
        guard_error = next(
            (error for error in errors if isinstance(error, _NeuronRuntimeDriftError)),
            None,
        )
        if guard_error is not None:
            raise guard_error
        control_error = next(
            (error for error in errors if error is not None and not isinstance(error, Exception)),
            None,
        )
        if control_error is not None:
            raise control_error
        if any(error is not None for error in errors):
            raise RuntimeError("Unable to persist new Neuron identity") from None

        self._assert_current_runtime()
        self.sk = candidate_key
        self.log(f"New identity saved to {IDENTITY_PATH}", "SUCCESS")
        self._assert_current_runtime()
    
    def sign_telemetry(self, block_height: int, provider: str) -> Tuple[str, str]:
        self._assert_current_runtime()
        payload = json.dumps({
            "type": "VAMS_HEARTBEAT", "version": VERSION,
            "node_id": self.node_id, "block_height": block_height,
            "provider": provider, "timestamp": time.time(),
            "nonce": os.urandom(8).hex()
        }, separators=(',', ':'))
        self._assert_current_runtime()
        try:
            signature = sign_message(self.sk, payload.encode()).hex()
        except _NeuronRuntimeDriftError:
            raise
        except Exception:
            self._assert_current_runtime()
            raise RuntimeError("Unable to sign Neuron telemetry") from None
        self._assert_current_runtime()
        return payload, signature
    
    def send_heartbeat(self, block_info) -> bool:
        self._assert_current_runtime()
        payload, signature = self.sign_telemetry(block_info.height, block_info.provider)
        self._assert_current_runtime()
        try:
            self.storage.store_heartbeat(self.node_id, block_info.height, block_info.network, payload, signature)
        except _NeuronRuntimeDriftError:
            raise
        except Exception:
            self._assert_current_runtime()
            raise RuntimeError("Unable to persist Neuron heartbeat") from None
        self._assert_current_runtime()
        
        colors = {"celestia": Fore.LIGHTBLUE_EX, "eigenda": Fore.LIGHTGREEN_EX,
                  "near": Fore.LIGHTYELLOW_EX, "avail": Fore.LIGHTMAGENTA_EX, "iagon": Fore.LIGHTCYAN_EX}
        c = colors.get(block_info.provider, Fore.WHITE)
        self.log(f"Block: #{block_info.height} [{c}{block_info.provider.upper()}{Style.RESET_ALL}]", "NET")
        self.log(f"Signature: {signature[:24]}...", "CRYPTO")
        
        self._assert_current_runtime()
        try:
            success = False
            if hasattr(self, 'gateway') and self.gateway:
                self._assert_current_runtime()
                success = self.gateway.send_heartbeat(payload, signature)
                self._assert_current_runtime()
            
            if success:
                self.gateway_available = True
                self.log("Gateway sync: SUCCESS", "SUCCESS")
                return True
        except _NeuronRuntimeDriftError:
            raise
        except LiveModeSafetyError:
            self._assert_current_runtime()
            raise RuntimeError("Gateway declined Neuron heartbeat") from None
        except Exception:
            self._assert_current_runtime()
            pass
        self._assert_current_runtime()
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
        if self.agentos_enabled:
            self.check_cognitive_health()
    
    def check_l4_health(self):
        print()
        self.log("LAYER 4: Endpoint Observations (Unverified)", "L4")
        print()
        for name, info in self.trust_manager.check_all_status().items():
            simulated = getattr(info, "simulated", None)
            scope = getattr(info, "verification_scope", None)
            classification = getattr(info, "evidence_classification", None)
            if simulated is True and scope == "fixture" and classification == "non-authoritative":
                c, s, state = Fore.YELLOW, "[!!]", "simulated fixture; unverified"
            elif (
                info.status == TrustStatus.HEALTHY
                and simulated is False
                and scope == "http_reachability"
                and classification == "non-authoritative"
            ):
                c, s, state = Fore.YELLOW, "[!!]", "HTTP reachable; unverified"
            else:
                c, s, state = Fore.YELLOW, "[??]", "unknown/unverified"
            technology = info.technology if type(info.technology) is str else "unknown target"
            latency = info.latency_ms if type(info.latency_ms) in (int, float) else 0.0
            if not (latency >= 0 and latency < float("inf")):
                latency = 0.0
            print(
                f"  {c}{s}{Style.RESET_ALL} {name.upper():10} "
                f"{latency:>6.0f}ms | target: {technology} | {state}"
            )
        print()
    
    def check_full_health(self):
        self.check_l1_health()
        self.check_l2_health()
        self.check_l3_health()
        self.check_l4_health()
    
    def check_sdk_health(self):
        """Display endpoint observations without claiming protocol verification."""
        if not SDK_AVAILABLE:
            self.log("SDK modules not available. Install with: pip install -r requirements.txt", "ERROR")
            return
        
        print()
        self.log("SDK Endpoint Observations (Unverified)", "INFO")
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
        except Exception:
            print(f"  {Fore.RED}[XX]{Style.RESET_ALL} CELESTIA    Provider data unavailable")
        
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
            
            # Subnet counts are useful only after the provider health check
            # succeeds; failed health must not be followed by fixture counts.
            if health["status"] == "healthy":
                sn1 = bt.get_subnet_info(1)
                if sn1:
                    if sn1.simulated:
                        source_label = "simulated fixture; non-authoritative"
                    else:
                        source_label = "provider observation; unverified"
                    print(
                        f"       +-- SN1 [{source_label}] ({sn1.name[:25]}): "
                        f"{sn1.miners} miners, {sn1.validators} validators"
                    )
        except Exception:
            print(f"  {Fore.RED}[XX]{Style.RESET_ALL} BITTENSOR   Provider data unavailable")
        
        print()
        
        # Layer 4: TEE Providers
        print(f"  {Fore.MAGENTA}--- Layer 4: Provider HTTP Reachability (Unverified) ---{Style.RESET_ALL}")
        try:
            tee_health = check_all_tee_health()
            for provider, health in tee_health.items():
                has_provenance = (
                    health.get("verification_scope") == "http_reachability"
                    and health.get("evidence_classification") == "non-authoritative"
                )
                if has_provenance and health.get("status") == "healthy":
                    c, s, state = Fore.GREEN, "[OK]", "HTTP reachable"
                elif has_provenance and health.get("status") == "degraded":
                    c, s, state = Fore.YELLOW, "[!!]", "HTTP degraded"
                elif has_provenance and health.get("status") == "offline":
                    c, s, state = Fore.RED, "[XX]", "HTTP unavailable"
                else:
                    c, s, state = Fore.YELLOW, "[??]", "unknown/unverified"
                target = health.get("technology", "provider endpoint")
                print(
                    f"  {c}{s}{Style.RESET_ALL} {provider.upper():10} "
                    f"{health.get('latency_ms', 0):>6.0f}ms | target: {target} | "
                    f"{state}; non-authoritative"
                )
        except Exception:
            print(f"  {Fore.RED}[XX]{Style.RESET_ALL} Provider HTTP status unavailable")
        
        print()
        print(f"  {Fore.CYAN}Tip:{Style.RESET_ALL} For Celestia, run a light node: celestia light start --p2p.network mocha")
        print(f"  {Fore.CYAN}Tip:{Style.RESET_ALL} For Bittensor, install: pip install bittensor")
        print()
    
    def run_workflow_demo(self):
        self._assert_current_runtime()
        print()
        self.log("DBOS-Style Crash-Proof Workflow Demo", "WORKFLOW")
        
        # Fallback to local SQLite system database if Postgres is not configured
        local_dbos = False
        workflow_error = None
        if not self._dbos_active and _DBOS_AVAILABLE:
            self._assert_current_runtime()
            try:
                self.log("Initializing local SQLite system database for demo...", "INFO")
                import sqlalchemy as sa
                self._assert_current_runtime()
                DBOS.destroy()
                self._assert_current_runtime()
                DBOS(config={
                    "name": "vams-demo-app",
                    "system_database_url": "sqlite:///dbos_demo_workflows.db",
                    "db_engine_kwargs": {
                        "poolclass": sa.NullPool
                    }
                })
                local_dbos = True
                self._assert_current_runtime()
                DBOS.reset_system_database()
                self._assert_current_runtime()
                DBOS.launch()
                self._dbos_active = True
                self._assert_current_runtime()
            except BaseException as exc:
                if isinstance(exc, _NeuronRuntimeDriftError):
                    workflow_error = exc
                elif isinstance(exc, LiveModeSafetyError):
                    try:
                        self._assert_current_runtime()
                    except BaseException as guard_exc:
                        workflow_error = guard_exc
                    if workflow_error is None:
                        workflow_error = RuntimeError("Local workflow initialization was refused")
                elif isinstance(exc, Exception):
                    try:
                        self._assert_current_runtime()
                    except BaseException as guard_exc:
                        workflow_error = guard_exc
                    if workflow_error is None:
                        try:
                            self.log("Failed to initialize local SQLite DBOS", "ERROR")
                            self._assert_current_runtime()
                        except BaseException as log_error:
                            workflow_error = log_error
                    if workflow_error is None:
                        if local_dbos:
                            workflow_error = RuntimeError("Local workflow initialization failed")
                else:
                    workflow_error = exc
        
        if workflow_error is None:
            try:
                self._assert_current_runtime()
                run_demo_workflow(lambda m: print(f"  {m}"))
                self._assert_current_runtime()
            except BaseException as exc:
                workflow_error = exc

        cleanup_error = None
        final_guard_error = None
        if local_dbos:
            try:
                DBOS.destroy()
                self._dbos_active = False
                if os.path.exists("dbos_demo_workflows.db"):
                    os.remove("dbos_demo_workflows.db")
            except BaseException as exc:
                cleanup_error = exc
            try:
                self._assert_current_runtime()
            except BaseException as exc:
                final_guard_error = exc

        errors = (workflow_error, cleanup_error, final_guard_error)
        guard_error = next(
            (error for error in errors if isinstance(error, _NeuronRuntimeDriftError)),
            None,
        )
        if guard_error is not None:
            raise guard_error
        control_error = next(
            (error for error in errors if error is not None and not isinstance(error, Exception)),
            None,
        )
        if control_error is not None:
            raise control_error
        if workflow_error is not None:
            if isinstance(workflow_error, LiveModeSafetyError):
                self._assert_current_runtime()
                raise RuntimeError("Neuron workflow was refused") from None
            self._assert_current_runtime()
            raise RuntimeError("Neuron workflow failed") from None
        if isinstance(cleanup_error, LiveModeSafetyError):
            self._assert_current_runtime()
            raise RuntimeError("Local workflow cleanup was refused") from None
        print()
    
    def check_cognitive_health(self):
        """Check AgentOS Cognitive Runtime status."""
        print()
        self.log("AGENTOS COGNITIVE RUNTIME", "L3")
        print()
        
        if not self.agentos_enabled:
            print(f"  {Fore.YELLOW}[--]{Style.RESET_ALL} AgentOS not enabled")
            print(f"       Install: sdk/semantic_checkpoint.py, sdk/interrupt_handler.py")
            print()
            return
        
        # Semantic Checkpoint Manager
        cp_stats = self.semantic_manager.get_stats()
        print(f"  {Fore.GREEN}[OK]{Style.RESET_ALL} CID Checkpoint  eps={cp_stats['epsilon']} | {cp_stats['efficiency']}")
        
        # S-MMU Memory Hierarchy
        mmu_stats = self.memory.get_stats()
        print(f"  {Fore.GREEN}[OK]{Style.RESET_ALL} S-MMU Memory    L1={mmu_stats['l1_pages']}/{mmu_stats['l1_capacity']} | Hit: {mmu_stats['hit_rate']}")
        
        # Interrupt Vector Table
        ivt_stats = self.ivt.get_stats()
        mode = "MOCK" if ivt_stats['mock_mode'] else "LIVE"
        print(f"  {Fore.GREEN}[OK]{Style.RESET_ALL} IVT ({mode:4})     IRQs={ivt_stats['total_interrupts']} | Cost={ivt_stats['total_cost_vams']:.3f} VAMS")
        
        # Cognitive Drift Detector
        drift_stats = self.drift_detector.get_stats()
        print(f"  {Fore.GREEN}[OK]{Style.RESET_ALL} Drift Detector  theta={drift_stats['theta']} | CSPs={drift_stats['csp_triggered']} | Agents={drift_stats['tracked_agents']}")
        
        print()
    
    def run(self, heartbeat_interval: int = HEARTBEAT_INTERVAL):
        self._assert_current_runtime()
        self.print_banner()
        print()
        self.load_or_generate_identity()
        print()
        
        self._assert_current_runtime()
        self.log("Checking DA providers...", "L1")
        self.provider_manager.check_all_health()
        
        self._assert_current_runtime()
        block_info = self.provider_manager.get_latest_block()
        self._assert_current_runtime()
        if block_info:
            self.log(f"Connected to {block_info.provider.upper()} at block #{block_info.height}", "SUCCESS")
        
        print()
        self.log(f"Starting heartbeat loop (interval: {heartbeat_interval}s)", "INFO")
        print(" " + "-" * 60)
        print()
        
        while self.running:
            try:
                self._assert_current_runtime()
                # Circuit Breaker Check
                if hasattr(self, 'breaker'):
                    breaker_active = self.breaker.is_active()
                    self._assert_current_runtime()
                    if not breaker_active:
                        self.log(f"HALTED: {self.breaker.trip_reason} (Next check in 10s)", "ERROR")
                        time.sleep(10)
                        continue

                self._assert_current_runtime()
                block_info = self.provider_manager.get_latest_block()
                self._assert_current_runtime()
                if block_info:
                    self.blocks_seen += 1
                    self.send_heartbeat(block_info)
                    if self.blocks_seen % 5 == 0:
                        stats = self.storage.get_stats()
                        self.log(f"Blocks: {self.blocks_seen} | Pending: {stats['pending_sync']}", "STATS")
                time.sleep(heartbeat_interval)
            except _NeuronRuntimeDriftError:
                raise
            except LiveModeSafetyError:
                self._assert_current_runtime()
                raise RuntimeError("Neuron loop operation was refused") from None
            except Exception:
                self._assert_current_runtime()
                self.log("Neuron loop operation failed", "ERROR")
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
    from .clr_router import CLRouter, TransactionIntent, TrustTier
    
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
        print("Using configured routing metrics (non-authoritative simulation)...")
        decision = router.route(intent, agent_tier)
        
        print(f"\n{Fore.GREEN}SIMULATED ROUTING DECISION{Style.RESET_ALL}")
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


def _validate_cli_boundary(policy: RuntimePolicy, args: argparse.Namespace) -> None:
    """Reject incomplete executable branches before they can create effects."""

    demo_actions = {
        "agent communications": args.comms,
        "CLR routing": args.route,
        "x402 payment": args.x402,
    }
    selected_demo = next((name for name, enabled in demo_actions.items() if enabled), None)
    if selected_demo and not policy.is_demo:
        raise LiveModeSafetyError(
            f"Neuron {selected_demo} demo requires explicit VAMS_ENV=demo"
        )
    if args.gateway_server and policy.is_live:
        raise LiveModeSafetyError(
            "Legacy neuron gateway is unavailable in live modes until M2 request "
            "authentication and replay protection are implemented"
        )


def main():
    policy = load_runtime_policy()
    args = parse_args()
    _validate_cli_boundary(policy, args)
    
    if args.gateway_server:
        from .gateway.server import start_server
        print(
            "Starting non-live VAMS legacy gateway "
            f"(mode={policy.mode.value}, evidence=non-authoritative)"
        )
        start_server(policy=policy)
        return

    if args.comms:
        from colorama import Fore, Style
        from .agent_comms import AgentCommunicator
        from .config import IDENTITY_PATH
        
        # Load Identity
        try:
            with open(IDENTITY_PATH, "rb") as f:
                sk = load_private_key_pem(f.read())
                node_id = public_key_bytes(sk).hex()[:16]
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
            comms.receive_message(asdict(msg), public_key_bytes(sk).hex())
            print(f"\n{Fore.GREEN}SIMULATED message logged to audit.log{Style.RESET_ALL}")
        else:
            print("Listening for messages... (Mock Mode)")
            print("Use --send-to <id> --msg <text> to test.")
        return

    if args.route: run_routing_logic(args); return
    
    if args.x402:
        from colorama import Fore, Style
        from .payments.x402 import X402Client
        
        from .economic.circuit_breaker import CircuitBreaker
        
        print(f"\n{Fore.CYAN}VAMS x402 Payment Protocol{Style.RESET_ALL}")
        print("=" * 40)
        
        breaker = CircuitBreaker()
        client = X402Client(circuit_breaker=breaker, mock_mode=True, policy=policy)
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
            print(f"\n{Fore.GREEN}SIMULATED Channel Open: {channel_id}{Style.RESET_ALL}")
            
            # 2. Simulate 402 Challenge
            print(f"[*] Requesting Service...")
            print(f"    < HTTP 402 Payment Required")
            headers = {
                "WWW-Authenticate": f'x402 chain=80002 contract="{provider}" amount="5.0" service="inference-01"'
            }
            print(f"    < WWW-Authenticate: {headers['WWW-Authenticate']}")
            
            # 3. Generate Payment
            token = client.handle_402(headers, "https://provider.invalid/api/v1/infer")
            
            if token:
                print(f"\n{Fore.GREEN}SIMULATED Payment Generated{Style.RESET_ALL}")
                print(f"    > Authorization: x402 {token[:20]}...")
                
                # Decode for display
                import base64
                import json
                decoded = json.loads(base64.b64decode(token).decode())
                print(f"    - Nonce:     {decoded['payment'][3]}")
                signature = str(decoded.get("signature", ""))
                print(f"    - Signature: {signature[:12]}... (simulated, redacted)")
                
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
        use_sdk=args.use_sdk,
        policy=policy,
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
    if args.check_cognitive: node.check_cognitive_health(); return
    if args.check_trust: node.check_l4_health(); return
    if args.demo_workflow: node.run_workflow_demo(); return
    
    print()
    node.run(args.interval)


if __name__ == "__main__":
    main()
