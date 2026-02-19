import unittest
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from economic.circuit_breaker import CircuitBreaker

class TestCircuitBreaker(unittest.TestCase):
    
    def setUp(self):
        self.breaker = CircuitBreaker()
        # Reset config for consistent testing (if configurable, else relying on defaults)
        
    def test_exposure_limit(self):
        # Default max is 1000
        self.breaker.update_exposure(500)
        self.assertEqual(self.breaker.state, "ARMED")
        
        self.breaker.update_exposure(1500)
        self.assertEqual(self.breaker.state, "TRIPPED")
        self.assertIn("Max exposure", self.breaker.trip_reason)
        
    def test_price_floor(self):
        self.breaker.check_market_conditions(0.60) # > 0.50
        self.assertEqual(self.breaker.state, "ARMED")
        
        self.breaker.check_market_conditions(0.40) # < 0.50
        self.assertEqual(self.breaker.state, "TRIPPED")
        self.assertIn("Price crash", self.breaker.trip_reason)

    def test_consecutive_failures(self):
        # Default fails = 5
        for i in range(4):
            self.breaker.record_failure("test failure")
            self.assertEqual(self.breaker.state, "ARMED")
            
        self.breaker.record_failure("final straw")
        self.assertEqual(self.breaker.state, "TRIPPED")
        
    def test_recovery(self):
        # Trip it
        self.breaker.trip("Manual trip")
        self.assertEqual(self.breaker.state, "TRIPPED")
        self.assertFalse(self.breaker.is_active())
        
        # Simulate cooldown passage
        self.breaker.last_trip_time = time.time() - 1000 # Way in past
        
        # Check health -> Should transition to ARMED (Auto-reset)
        # is_active() triggers _attempt_recovery if cooldown passed
        self.breaker.is_active() 
        self.assertEqual(self.breaker.state, "ARMED")

if __name__ == '__main__':
    unittest.main()
