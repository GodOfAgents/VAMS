"""Contained legacy Celestia availability sampler.

This client does not prove that a requested data root is available. It remains
usable only as an explicit non-live simulation until M5 supplies exact
authenticated sampling and read-back.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Mapping, Optional

import requests

from neuron.runtime_safety import (
    ImmutableRuntimeConfiguration,
    LiveModeSafetyError,
    RuntimePolicy,
    load_runtime_policy,
    resolve_component_mock_mode,
)


logger = logging.getLogger("CelestiaDAS")
CELESTIA_LIGHT_MOCK_VARIABLE = "CELESTIA_LIGHT_MOCK_MODE"


class CelestiaLightClient(ImmutableRuntimeConfiguration):
    _immutable_runtime_fields = frozenset(
        {"rpc_url", "mock_mode", "runtime_policy", "_transport"}
    )

    def __init__(
        self,
        rpc_url: Optional[str] = None,
        mock_mode: Optional[bool] = None,
        *,
        environ: Optional[Mapping[str, str]] = None,
        policy: Optional[RuntimePolicy] = None,
        transport: Any = requests,
    ):
        source = os.environ if environ is None else environ
        self.runtime_policy = policy or load_runtime_policy(source)
        self.mock_mode = resolve_component_mock_mode(
            "CelestiaLightClient",
            CELESTIA_LIGHT_MOCK_VARIABLE,
            mock_mode,
            policy=self.runtime_policy,
            environ=source,
        )
        if self.runtime_policy.is_live:
            raise LiveModeSafetyError(
                "CelestiaLightClient live execution is disabled until exact data-root "
                "sampling and authenticated read-back are implemented in M5"
            )
        self.rpc_url = rpc_url or source.get("CELESTIA_RPC", "https://rpc-mocha.pops.one")
        self._transport = transport
        self._freeze_runtime_configuration()

    def sample_availability(self, root_hash: str) -> bool:
        if self.mock_mode:
            logger.info("Celestia simulated sampling is non-authoritative")
            return bool(root_hash)
        return self._provider_probe(root_hash)

    def _provider_probe(self, root_hash: str) -> bool:
        """Probe provider health without treating network-head presence as root proof."""
        try:
            response = self._transport.post(
                self.rpc_url,
                json={
                    "id": 1,
                    "jsonrpc": "2.0",
                    "method": "header.NetworkHead",
                    "params": [],
                },
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
        except Exception:
            logger.warning("Celestia provider probe failed")
            return False

        # A reachable network head is not proof that root_hash is available.
        return False


if __name__ == "__main__":
    raise SystemExit(
        "CelestiaLightClient is a library surface; use an explicit non-live test"
    )
