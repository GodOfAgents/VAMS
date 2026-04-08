"""
DA Adapter Base Class
=====================
Abstract interface that every DA layer adapter must implement.
"""

from abc import ABC, abstractmethod
from typing import Optional

from neuron.da.models import DAProtocol, DAReceipt


class DAAdapter(ABC):
    """
    Interface every DA layer must implement for performance auditing.

    Adapters handle the transport-level details of submitting and
    retrieving blobs from their respective DA networks.
    """

    protocol: DAProtocol
    name: str

    def __init__(self, rpc_url: str, namespace: bytes = b"vams-perf-v1", mock_mode: bool = False):
        self.rpc_url = rpc_url
        self.namespace = namespace
        self.mock_mode = mock_mode

    @abstractmethod
    async def submit_blob(self, data: bytes, namespace: Optional[bytes] = None) -> DAReceipt:
        """
        Submit a blob to this DA layer.

        Args:
            data: Raw bytes to submit.
            namespace: Optional namespace override.

        Returns:
            DAReceipt with protocol, blob_id, height, commitment.
        """
        ...

    @abstractmethod
    async def verify_blob(self, receipt: DAReceipt) -> bool:
        """
        Verify that a previously submitted blob is still available.

        Args:
            receipt: The DAReceipt from a prior submit_blob call.

        Returns:
            True if the blob is verifiably available.
        """
        ...

    @abstractmethod
    async def get_blob(self, blob_id: str) -> Optional[bytes]:
        """
        Retrieve a blob by its identifier.

        Args:
            blob_id: The unique blob reference from the DA layer.

        Returns:
            Raw blob bytes, or None if not found.
        """
        ...

    async def health_check(self) -> bool:
        """Check if the DA layer RPC endpoint is reachable."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(self.rpc_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    return resp.status < 500
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} protocol={self.protocol.value} rpc={self.rpc_url}>"
