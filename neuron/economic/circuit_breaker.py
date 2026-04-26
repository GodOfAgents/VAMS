import logging
import time
from typing import Optional, Dict, Any
from config import (
    BREAKER_PRICE_FLOOR, 
    BREAKER_MAX_EXPOSURE, 
    BREAKER_MAX_CONSECUTIVE_FAILURES,
    BREAKER_COOLDOWN_SEC
)

logger = logging.getLogger("VAMS-Breaker")

class CircuitBreaker:
    """
    Security Layer (C4: Black Swan Handling).
    Halts operations if economic or security thresholds are breached.
    
    Monitors:
    1. Critical Price Levels (Flash Crash protection)
    2. Exposure Limits (Max pending funds)
    3. Operational Reliability (Consecutive failures)
    """
    
    def __init__(self):
        self.state = "ARMED"  # ARMED, TRIPPED, RECOVERING
        self.last_trip_time = 0.0
        self.trip_reason = None
        self.consecutive_failures = 0
        
        # Operational Metrics
        self.current_exposure = 0.0
        
    def is_active(self) -> bool:
        """Returns True if operations are allowed."""
        if self.state == "ARMED":
            return True
            
        if self.state == "TRIPPED":
            # Check for auto-recovery cooldown
            if time.time() - self.last_trip_time > BREAKER_COOLDOWN_SEC:
                # OFC05: Enforce health check before auto-reset
                if self._verify_health():
                    self._attempt_recovery()
                    return True
                else:
                    logger.warning("Breaker cooldown elapsed, but health check failed. Still tripped.")
            return False
            
        return True # RECOVERING acts as ARMED but logging is different

    def record_success(self):
        """Reset failure counters on successful operation."""
        if self.consecutive_failures > 0:
            self.consecutive_failures = 0
            
    def record_failure(self, error: str = "Unknown"):
        """Record an operational failure."""
        self.consecutive_failures += 1
        if self.consecutive_failures >= BREAKER_MAX_CONSECUTIVE_FAILURES:
            self.trip(f"Max consecutive failures reached ({self.consecutive_failures})")

    def update_exposure(self, amount: float):
        """Update current financial exposure."""
        self.current_exposure = amount
        if self.current_exposure > BREAKER_MAX_EXPOSURE:
            self.trip(f"Max exposure exceeded: {self.current_exposure} > {BREAKER_MAX_EXPOSURE}")

    def check_market_conditions(self, vams_price_usd: float):
        """Verify market health."""
        if vams_price_usd is None or vams_price_usd <= 0:
            self.trip(f"Invalid market price data: {vams_price_usd}")
            return
            
        if vams_price_usd < BREAKER_PRICE_FLOOR:
            self.trip(f"Price crash protection: ${vams_price_usd} < floor ${BREAKER_PRICE_FLOOR}")

    def trip(self, reason: str):
        """Trigger the circuit breaker."""
        if self.state == "TRIPPED":
            return
            
        self.state = "TRIPPED"
        self.trip_reason = reason
        self.last_trip_time = time.time()
        
        logger.critical(f"🛑 CIRCUIT BREAKER TRIPPED: {reason}")
        logger.critical(f"   System HALTED for {BREAKER_COOLDOWN_SEC}s")

    def _verify_health(self) -> bool:
        """Enforces operational and economic health before auto-reset (OFC05)."""
        try:
            # 1. Exposure must have dropped to safe levels (< 80% max)
            if self.current_exposure > (BREAKER_MAX_EXPOSURE * 0.8):
                logger.warning("Health check failed: Exposure still too high.")
                return False
                
            # 2. Cannot auto-reset if previous failure was consecutive max-out
            if self.consecutive_failures >= BREAKER_MAX_CONSECUTIVE_FAILURES:
                logger.warning("Health check failed: System requires manual intervention due to consecutive failures.")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Health check execution failed: {e}")
            return False

    def _attempt_recovery(self):
        """Try to auto-reset the breaker."""
        self.state = "ARMED"
        self.trip_reason = None
        self.consecutive_failures = 0
        logger.info(f"🟢 Circuit Breaker auto-reset after cooldown. System ARMED.")

    def manual_reset(self):
        """Force reset the breaker."""
        self._attempt_recovery()
        logger.warning("Circuit Breaker MANUALLY reset by operator.")

    def get_status(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "reason": self.trip_reason,
            "failures": self.consecutive_failures,
            "exposure": self.current_exposure,
            "last_trip": self.last_trip_time
        }
