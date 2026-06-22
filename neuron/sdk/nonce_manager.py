import os
import json
import threading
from typing import Dict

class NonceManager:
    """
    Monotonic nonce manager that persists nonces to disk.
    Ensures unique, increasing nonces per (agent, provider) pair
    or globally per agent to prevent double-spends and replay attacks.
    """
    def __init__(self, agent_id: str, persistence_path: str = None):
        self.agent_id = agent_id
        if persistence_path is None:
            self.persistence_path = os.path.join(".data", "nonces", f"{agent_id}.json")
        else:
            self.persistence_path = persistence_path
            
        self.lock = threading.Lock()
        self._nonces: Dict[str, int] = {}
        self._load()

    def _load(self):
        """Load persisted nonces from disk."""
        if os.path.exists(self.persistence_path):
            try:
                os.makedirs(os.path.dirname(self.persistence_path), exist_ok=True)
                with open(self.persistence_path, 'r') as f:
                    self._nonces = json.load(f)
            except Exception:
                # If corrupt or unreadable, start fresh
                self._nonces = {}
        else:
            # Create directories if not existing
            os.makedirs(os.path.dirname(self.persistence_path), exist_ok=True)
            self._nonces = {}

    def _save(self):
        """Save nonces to disk."""
        try:
            os.makedirs(os.path.dirname(self.persistence_path), exist_ok=True)
            with open(self.persistence_path, 'w') as f:
                json.dump(self._nonces, f, indent=2)
        except Exception as e:
            # In production, we'd log this, but let's raise or handle gracefully
            pass

    def next_nonce(self, provider: str = "global") -> int:
        """Atomically increment and return the next nonce for a provider."""
        with self.lock:
            current = self._nonces.get(provider, 0)
            next_val = current + 1
            self._nonces[provider] = next_val
            self._save()
            return next_val

    def current_nonce(self, provider: str = "global") -> int:
        """Read current nonce without incrementing."""
        with self.lock:
            return self._nonces.get(provider, 0)
