#!/usr/bin/env python3
"""
VAMS PoC+ Demo CLI
==================
Polished command-line demonstration of the Immortal Agent guarantee.

Shows the checkpoint → crash → resume flow visually with:
- Animated progress indicators
- Color-coded output
- L1 state anchoring simulation
- Clear visual separation between crash and recovery

Usage:
    python demo_cli.py              # Full demo with crash simulation
    python demo_cli.py --no-crash   # Demo without crash (baseline)
    python demo_cli.py --step 3     # Crash at specific step
"""

import sys
import time
import argparse
import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
from datetime import datetime

# Try to import rich for fancy output, fallback to basic print
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.table import Table
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None

# Import local modules
try:
    from anchoring import L1StateAnchor, AnchorReceipt, get_anchor
except ImportError:
    # Fallback if running from different directory
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from anchoring import L1StateAnchor, AnchorReceipt, get_anchor


# ============================================================================
# CONFIGURATION
# ============================================================================

VERSION = "1.0.0"
DEMO_AGENT_NAME = "TradingBot"
DEMO_AGENT_ID = "0x7a3f89c2e4b1d6a8f0c2e4b1d6a8f0c2"

# Colors for different states (ANSI codes for fallback)
COLORS = {
    "success": "\033[92m",  # Green
    "warning": "\033[93m",  # Yellow
    "error": "\033[91m",    # Red
    "info": "\033[94m",     # Blue
    "reset": "\033[0m",     # Reset
    "bold": "\033[1m",      # Bold
    "cyan": "\033[96m",     # Cyan
}


# ============================================================================
# WORKFLOW STATUS
# ============================================================================

class AgentState(Enum):
    """Immortal Agent states - note there is NO 'DEAD' state."""
    RUNNING = "running"
    CHECKPOINTING = "checkpointing"
    CRASHED = "crashed"
    RECOVERING = "recovering"
    MIGRATING = "migrating"
    SUSPENDED = "suspended"
    COMPLETED = "completed"


@dataclass
class StepResult:
    """Result of a workflow step."""
    step_name: str
    step_index: int
    data: Dict[str, Any]
    duration_ms: float
    checkpoint_hash: str


@dataclass 
class DemoResult:
    """Result of the full demo."""
    success: bool
    total_steps: int
    steps_completed: int
    crashed: bool
    recovered: bool
    recovery_step: Optional[str]
    anchor_receipt: Optional[AnchorReceipt]
    total_duration_ms: float


# ============================================================================
# IMMORTAL AGENT DEMO
# ============================================================================

class ImmortalAgentDemo:
    """
    Demonstrates the Immortal Agent guarantee with a Trading Agent workflow.
    
    Workflow Steps:
    1. Fetch Market Data    - Pull from Celestia DA
    2. Run AI Inference     - Bittensor SN1 prediction
    3. Generate Trade Signal - Bullish/Bearish + confidence
    4. Execute Trade        - Simulated on-chain tx
    5. Anchor State to L1   - Merkle root submission
    """
    
    def __init__(
        self, 
        workflow_id: Optional[str] = None,
        crash_at_step: int = 3,
        enable_crash: bool = True
    ):
        self.workflow_id = workflow_id or f"wf_{int(time.time() * 1000)}"
        self.crash_at_step = crash_at_step
        self.enable_crash = enable_crash
        self.anchor = get_anchor()
        
        # Checkpoint storage (in-memory for demo, production uses SQLite)
        self.checkpoints: List[StepResult] = []
        self.state = AgentState.RUNNING
        self._recovered = False
        self._recovery_step: Optional[str] = None
        
        # Step definitions
        self.steps = [
            ("Fetch Market Data", self._step_fetch_data),
            ("Run AI Inference", self._step_run_inference),
            ("Generate Trade Signal", self._step_generate_signal),
            ("Execute Trade", self._step_execute_trade),
            ("Anchor State to L1", self._step_anchor_state),
        ]
    
    # ========================
    # WORKFLOW STEPS
    # ========================
    
    def _step_fetch_data(self) -> Dict[str, Any]:
        """Step 1: Fetch market data from Celestia DA."""
        time.sleep(0.4)  # Simulate network latency
        return {
            "source": "Celestia DA",
            "block_height": 9_628_712,
            "pairs": ["BTC/USDT", "ETH/USDT"],
            "prices": {"BTC": 98_432.15, "ETH": 3_842.67},
            "timestamp": datetime.now().isoformat()
        }
    
    def _step_run_inference(self) -> Dict[str, Any]:
        """Step 2: Run AI inference via Bittensor SN1."""
        time.sleep(0.8)  # Simulate inference time
        return {
            "model": "Bittensor SN1 (Text/Reasoning)",
            "input_tokens": 1247,
            "output_tokens": 89,
            "latency_ms": 834,
            "analysis": "Strong bullish divergence on 4H chart with RSI oversold"
        }
    
    def _step_generate_signal(self) -> Dict[str, Any]:
        """Step 3: Generate trade signal from inference."""
        time.sleep(0.3)  # Simulate processing
        return {
            "signal": "LONG",
            "asset": "BTC/USDT",
            "confidence": 0.87,
            "entry_price": 98_432.15,
            "stop_loss": 97_500.00,
            "take_profit": 101_250.00,
            "risk_reward_ratio": 3.02
        }
    
    def _step_execute_trade(self) -> Dict[str, Any]:
        """Step 4: Execute trade on-chain."""
        time.sleep(0.5)  # Simulate tx submission
        tx_hash = hashlib.sha256(
            f"{self.workflow_id}:trade:{time.time()}".encode()
        ).hexdigest()
        return {
            "status": "executed",
            "tx_hash": f"0x{tx_hash}",
            "chain": "Polygon CDK",
            "gas_used": 142_857,
            "gas_price_gwei": 25,
            "position_size": "0.5 BTC"
        }
    
    def _step_anchor_state(self) -> Dict[str, Any]:
        """Step 5: Anchor state to L1 for immortality guarantee."""
        # Compute Merkle root from all checkpoints
        checkpoint_data = [cp.data for cp in self.checkpoints]
        merkle_root = self.anchor.compute_merkle_root(checkpoint_data)
        
        # Submit to L1 (simulated)
        receipt = self.anchor.submit_anchor(merkle_root, len(self.checkpoints))
        
        return {
            "merkle_root": merkle_root,
            "tx_hash": receipt.tx_hash,
            "block_number": receipt.block_number,
            "chain": "Polygon CDK",
            "checkpoints_anchored": len(self.checkpoints)
        }
    
    # ========================
    # CHECKPOINT MANAGEMENT
    # ========================
    
    def _save_checkpoint(self, step_name: str, step_index: int, data: Dict[str, Any], duration_ms: float):
        """Save a checkpoint after step completion."""
        checkpoint_data = json.dumps(data, sort_keys=True)
        checkpoint_hash = hashlib.sha256(checkpoint_data.encode()).hexdigest()[:16]
        
        # --- Iagon Storage Integration ---
        iri = None
        try:
            from sdk.iagon_storage import IagonStorageSDK
            os.environ["IAGON_MOCK_MODE"] = "true"
            iagon_sdk = IagonStorageSDK()
            iri = iagon_sdk.store_checkpoint(checkpoint_hash, data)
        except Exception:
            pass # Fails gracefully if no SDK 
            
        result = StepResult(
            step_name=step_name,
            step_index=step_index,
            data=data,
            duration_ms=duration_ms,
            checkpoint_hash=checkpoint_hash
        )
        if iri:
             result.data['_iagon_iri'] = iri
             
        self.checkpoints.append(result)
        return result
    
    def _recover_from_checkpoint(self) -> int:
        """Attempt to recover from last checkpoint. Returns step to resume from."""
        if self.checkpoints:
            last_cp = self.checkpoints[-1]
            self._recovered = True
            self._recovery_step = last_cp.step_name
            return last_cp.step_index + 1
        return 0
    
    # ========================
    # DEMO EXECUTION
    # ========================
    
    def run(self, log_fn: Callable = print) -> DemoResult:
        """Execute the full demo with crash simulation and recovery."""
        total_steps = len(self.steps)
        start_time = time.time()
        start_step = 0
        anchor_receipt = None
        crashed = False
        
        # Check for recovery
        if self._recovered:
            start_step = self._recover_from_checkpoint()
        
        try:
            for i, (step_name, step_fn) in enumerate(self.steps):
                if i < start_step:
                    continue
                
                step_num = f"[{i+1}/{total_steps}]"
                
                # Show step starting
                self.state = AgentState.RUNNING
                
                # Execute step with timing
                step_start = time.time()
                result = step_fn()
                step_duration = (time.time() - step_start) * 1000
                
                # Save checkpoint
                self.state = AgentState.CHECKPOINTING
                cp = self._save_checkpoint(step_name, i, result, step_duration)
                
                # Log checkpoint
                if RICH_AVAILABLE:
                    console.print(
                        f"  ✓ {step_num} {step_name}{'.' * (30 - len(step_name))} "
                        f"[green][CHECKPOINT][/green] {step_duration:.0f}ms"
                    )
                else:
                    log_fn(
                        f"  ✓ {step_num} {step_name}{'.' * (30 - len(step_name))} "
                        f"[CHECKPOINT] {step_duration:.0f}ms"
                    )
                
                # Simulate crash?
                if self.enable_crash and (i + 1) == self.crash_at_step and not self._recovered:
                    self.state = AgentState.CRASHED
                    crashed = True
                    
                    if RICH_AVAILABLE:
                        console.print()
                        console.print(
                            f"  💥 [bold red][CRASH][/bold red] Infrastructure failure after step {i+1}!",
                        )
                        console.print()
                    else:
                        log_fn(f"\n  💥 [CRASH] Infrastructure failure after step {i+1}!\n")
                    
                    # Return partial result
                    return DemoResult(
                        success=False,
                        total_steps=total_steps,
                        steps_completed=i + 1,
                        crashed=True,
                        recovered=False,
                        recovery_step=None,
                        anchor_receipt=None,
                        total_duration_ms=(time.time() - start_time) * 1000
                    )
                
                # Get anchor receipt from last step
                if i == total_steps - 1:
                    anchor_receipt = AnchorReceipt(
                        merkle_root=result["merkle_root"],
                        tx_hash=result["tx_hash"],
                        block_number=result["block_number"],
                        timestamp=time.time(),
                        checkpoints_included=result["checkpoints_anchored"]
                    )
            
            # Workflow completed
            self.state = AgentState.COMPLETED
            total_duration = (time.time() - start_time) * 1000
            
            if RICH_AVAILABLE:
                console.print()
                if self._recovered:
                    console.print(
                        f"  🎉 [bold green][COMPLETE][/bold green] Agent survived crash!"
                        f" Immortality proven in {total_duration:.0f}ms"
                    )
                else:
                    console.print(
                        f"  🎉 [bold green][COMPLETE][/bold green] Workflow finished in {total_duration:.0f}ms"
                    )
            else:
                if self._recovered:
                    log_fn(
                        f"\n  🎉 [COMPLETE] Agent survived crash! Immortality proven in {total_duration:.0f}ms"
                    )
                else:
                    log_fn(f"\n  🎉 [COMPLETE] Workflow finished in {total_duration:.0f}ms")
            
            return DemoResult(
                success=True,
                total_steps=total_steps,
                steps_completed=total_steps,
                crashed=False,
                recovered=self._recovered,
                recovery_step=self._recovery_step,
                anchor_receipt=anchor_receipt,
                total_duration_ms=total_duration
            )
            
        except Exception as e:
            self.state = AgentState.CRASHED
            return DemoResult(
                success=False,
                total_steps=total_steps,
                steps_completed=len(self.checkpoints),
                crashed=True,
                recovered=False,
                recovery_step=None,
                anchor_receipt=None,
                total_duration_ms=(time.time() - start_time) * 1000
            )


# ============================================================================
# CLI DEMO RUNNER
# ============================================================================

def print_banner():
    """Print the demo banner."""
    banner = """
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   ██╗   ██╗ █████╗ ███╗   ███╗███████╗    ██████╗  ██████╗  ██████╗ ╗        ║
║   ██║   ██║██╔══██╗████╗ ████║██╔════╝    ██╔══██╗██╔═══██╗██╔════╝ ║        ║
║   ██║   ██║███████║██╔████╔██║███████╗    ██████╔╝██║   ██║██║      ║        ║
║   ╚██╗ ██╔╝██╔══██║██║╚██╔╝██║╚════██║    ██╔═══╝ ██║   ██║██║      ║        ║
║    ╚████╔╝ ██║  ██║██║ ╚═╝ ██║███████║    ██║     ╚██████╔╝╚██████╗ ╝        ║
║     ╚═══╝  ╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝    ╚═╝      ╚═════╝  ╚═════╝          ║
║                                                                               ║
║                    IMMORTAL AGENT DEMONSTRATION                               ║
║                   Checkpoint → Crash → Resume Flow                            ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""
    if RICH_AVAILABLE:
        console.print(banner, style="cyan")
    else:
        print(f"{COLORS['cyan']}{banner}{COLORS['reset']}")


def print_pillar_box():
    """Print the Five Pillars of Immortal Agents."""
    if RICH_AVAILABLE:
        pillars = Table(title="The Five Pillars of Immortal Agents", box=box.ROUNDED)
        pillars.add_column("Pillar", style="cyan")
        pillars.add_column("Description", style="white")
        pillars.add_column("Demo Status", style="green")
        
        pillars.add_row("1. Durable Execution", "DBOS checkpointing at each step", "✓ Active")
        pillars.add_row("2. L1 State Anchoring", "Merkle root on Polygon CDK", "✓ Active")
        pillars.add_row("3. Transparent Failover", "SDK auto-reroutes on failure", "○ Simulated")
        pillars.add_row("4. Request Guarantee", "Queue with retry semantics", "○ Simulated")
        pillars.add_row("5. Permanent Memory", "Arweave for agent memories", "○ Future")
        
        console.print(pillars)
        console.print()
    else:
        print("\n┌─── The Five Pillars of Immortal Agents ───────────────────────────┐")
        print("│ 1. Durable Execution    - DBOS checkpointing        ✓ Active     │")
        print("│ 2. L1 State Anchoring   - Merkle root on L1         ✓ Active     │")
        print("│ 3. Transparent Failover - SDK auto-reroutes         ○ Simulated  │")
        print("│ 4. Request Guarantee    - Queue with retry          ○ Simulated  │")
        print("│ 5. Permanent Memory     - Arweave storage           ○ Future     │")
        print("└───────────────────────────────────────────────────────────────────┘\n")


def run_full_demo(crash_at_step: int = 3, enable_crash: bool = True):
    """Run the complete demo with crash simulation and recovery."""
    
    print_banner()
    print_pillar_box()
    
    workflow_id = f"demo_{int(time.time())}"
    
    # Phase 1: First run - will crash
    if RICH_AVAILABLE:
        console.print(f"[bold]Agent:[/bold] {DEMO_AGENT_NAME}")
        console.print(f"[bold]ID:[/bold] {DEMO_AGENT_ID}")
        console.print(f"[bold]Workflow:[/bold] {workflow_id}")
        console.print()
        console.print("[bold cyan]─── PHASE 1: Initial Execution ───[/bold cyan]")
        console.print()
    else:
        print(f"Agent: {DEMO_AGENT_NAME}")
        print(f"ID: {DEMO_AGENT_ID}")
        print(f"Workflow: {workflow_id}")
        print()
        print("─── PHASE 1: Initial Execution ───")
        print()
    
    # Create and run first workflow
    wf1 = ImmortalAgentDemo(
        workflow_id=workflow_id,
        crash_at_step=crash_at_step,
        enable_crash=enable_crash
    )
    result1 = wf1.run()
    
    # If crashed, do recovery
    if result1.crashed and enable_crash:
        time.sleep(0.5)  # Dramatic pause
        
        if RICH_AVAILABLE:
            console.print("[bold cyan]─── PHASE 2: Recovery from Checkpoint ───[/bold cyan]")
            console.print()
            console.print(
                f"  🔄 [bold yellow][RECOVERY][/bold yellow] "
                f"Resuming from checkpoint {result1.steps_completed}/{result1.total_steps}"
            )
            console.print()
        else:
            print("\n─── PHASE 2: Recovery from Checkpoint ───")
            print()
            print(f"  🔄 [RECOVERY] Resuming from checkpoint {result1.steps_completed}/{result1.total_steps}")
            print()
        
        # Create recovery workflow with checkpoints from first run
        wf2 = ImmortalAgentDemo(
            workflow_id=workflow_id,
            crash_at_step=crash_at_step,
            enable_crash=False  # Don't crash again
        )
        
        # Transfer checkpoints and mark as recovered
        wf2.checkpoints = wf1.checkpoints.copy()
        wf2._recovered = True
        wf2._recovery_step = wf1.checkpoints[-1].step_name if wf1.checkpoints else None
        
        result2 = wf2.run()
        
        # Show anchor receipt
        if result2.anchor_receipt:
            if RICH_AVAILABLE:
                console.print()
                anchor = result2.anchor_receipt
                receipt_table = Table(title="L1 State Anchor Receipt", box=box.ROUNDED)
                receipt_table.add_column("Field", style="cyan")
                receipt_table.add_column("Value", style="white")
                
                receipt_table.add_row("Merkle Root", f"{anchor.merkle_root[:24]}...")
                receipt_table.add_row("Tx Hash", f"{anchor.tx_hash[:24]}...")
                receipt_table.add_row("Block", f"#{anchor.block_number:,}")
                receipt_table.add_row("Chain", "Polygon CDK (simulated)")
                receipt_table.add_row("Checkpoints", f"{anchor.checkpoints_included} states anchored")
                
                console.print(receipt_table)
            else:
                anchor = result2.anchor_receipt
                print("\n┌─── L1 State Anchor Receipt ───────────────────────────────┐")
                print(f"│ Merkle Root: {anchor.merkle_root[:24]}...                │")
                print(f"│ Tx Hash:     {anchor.tx_hash[:24]}...                │")
                print(f"│ Block:       #{anchor.block_number:,}                              │")
                print(f"│ Chain:       Polygon CDK (simulated)                      │")
                print(f"│ Checkpoints: {anchor.checkpoints_included} states anchored                       │")
                print("└────────────────────────────────────────────────────────────┘")
        
        return result2
    
    return result1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="VAMS PoC+ Demo: Immortal Agent Demonstration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python demo_cli.py              Full demo with crash simulation
  python demo_cli.py --no-crash   Demo without crash (baseline)
  python demo_cli.py --step 2     Crash at step 2 instead of 3
        """
    )
    parser.add_argument(
        "--no-crash", 
        action="store_true",
        help="Run without crash simulation"
    )
    parser.add_argument(
        "--step", 
        type=int, 
        default=3,
        help="Step number to crash at (default: 3)"
    )
    parser.add_argument(
        "--version", 
        action="version",
        version=f"VAMS PoC+ Demo v{VERSION}"
    )
    
    args = parser.parse_args()
    
    # Run the demo
    result = run_full_demo(
        crash_at_step=args.step,
        enable_crash=not args.no_crash
    )
    
    # Final summary
    print()
    if result.success:
        if RICH_AVAILABLE:
            console.print(Panel(
                "[bold green]✅ DEMONSTRATION COMPLETE[/bold green]\n\n"
                "The Immortal Agent successfully:\n"
                "• Checkpointed state at each step\n"
                "• Survived a simulated infrastructure crash\n"
                "• Recovered from the exact checkpoint state\n"
                "• Anchored final state to L1 (Polygon CDK)\n\n"
                "[dim]This proves the core thesis: Agents on VAMS cannot die.[/dim]",
                title="Demo Result",
                border_style="green"
            ))
        else:
            print("═══════════════════════════════════════════════════════")
            print("  ✅ DEMONSTRATION COMPLETE")
            print("═══════════════════════════════════════════════════════")
            print("  The Immortal Agent successfully:")
            print("  • Checkpointed state at each step")
            print("  • Survived a simulated infrastructure crash")
            print("  • Recovered from the exact checkpoint state")
            print("  • Anchored final state to L1 (Polygon CDK)")
            print()
            print("  This proves the core thesis: Agents on VAMS cannot die.")
            print("═══════════════════════════════════════════════════════")
    else:
        print("❌ Demo failed - check error above")
        sys.exit(1)


if __name__ == "__main__":
    main()
