"""
VAMS Trust Plugins — Auto-discovery Module
==========================================
Automatically discovers and loads proof plugins from this package.
"""

from .tee_plugin import TEEProofPlugin
from .zkml_plugin import ZKMLProofPlugin
from .output_hash_plugin import OutputHashProofPlugin

__all__ = [
    "TEEProofPlugin",
    "ZKMLProofPlugin",
    "OutputHashProofPlugin",
]


def discover_plugins():
    """Return all available proof plugin instances."""
    return [
        TEEProofPlugin(),
        ZKMLProofPlugin(),
        OutputHashProofPlugin(),
    ]
