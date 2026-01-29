import logging
import time
from typing import Dict, Any, Optional

logger = logging.getLogger("VAMSBreaker")

class CircuitBreaker:
    """
    Security Layer (C4: Black Swan Handling).
    Halts operations if economic or security thresholds are breached.
    """
    
    def __init__(self, price_floor: float = 0.5, max_exposure: float = 1000.0):
        self.price_floor = price_floor
        self.max_exposure = max_exposure # Max pending VAMS
        self.triggered = False
        self.reason = None
        logger.info(f"Circuit Breaker armed (Floor: ${price_floor})")

    def check_health(self, current_price: float, pending_exposure: float) -> bool:
        """
        Check vital signs. Returns False if breaker trips.
        """
        if self.triggered:
            return False
            
        if current_price < self.price_floor:
            self._trip(f"Price crash: ${current_price} < ${self.price_floor}")
            return False
            
        if pending_exposure > self.max_exposure:
            self._trip(f"Exposure limit: {pending_exposure} > {self.max_exposure}")
            return False
            
        return True

    def _trip(self, reason: str):
        self.triggered = True
        self.reason = reason
        logger.critical(f"🛑 CIRCUIT BREAKER TRIPPED: {reason}")
        # In real world: Send emergency SMS/Email via Twilio/SNS

    def reset(self):
        self.triggered = False
        self.reason = None
        logger.info("Circuit Breaker manually reset")
