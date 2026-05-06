"""
VAMS Neuron - DBOS Configuration
=================================
Centralised DBOS initialisation singleton.

Import pattern across VAMS modules:
    from dbos_config import init_dbos, destroy_dbos

DBOS() must be instantiated exactly once per process before any
@DBOS.workflow() or @DBOS.step() decorated functions are called.
"""

import os
import logging
from typing import Optional

from dbos import DBOS, DBOSConfig

logger = logging.getLogger("vams.dbos_config")

# Module-level singleton — prevents double-initialisation if multiple
# modules try to call init_dbos() during import resolution.
_dbos_instance: Optional[DBOS] = None


def get_dbos_config() -> DBOSConfig:
    """
    Build a DBOSConfig from environment variables.

    Required env var:
        DBOS_SYSTEM_DATABASE_URL — Postgres DSN.
        Examples:
          Local Docker:  postgresql://localhost/vams
          Neon:          postgresql://localhost/vams

    Raises:
        RuntimeError if DBOS_SYSTEM_DATABASE_URL is not set.
    """
    db_url = os.environ.get("DBOS_SYSTEM_DATABASE_URL")
    if not db_url:
        raise RuntimeError(
            "DBOS_SYSTEM_DATABASE_URL is not set. "
            "Copy neuron/.env.example → neuron/.env and fill in your Postgres URL. "
            "For local Docker: docker run -d --name vams-pg "
            "-e POSTGRES_USER=vams -e POSTGRES_PASSWORD=vams_dev_pw "
            "-e POSTGRES_DB=vams_dbos -p 5432:5432 postgres:16"
        )
    return DBOSConfig(
        name="vams-neuron",
        system_database_url=db_url,
    )


def init_dbos() -> DBOS:
    """
    Initialise and return the DBOS singleton.

    Safe to call multiple times — returns the existing instance on
    subsequent calls without re-initialising.
    """
    global _dbos_instance
    if _dbos_instance is None:
        config = get_dbos_config()
        _dbos_instance = DBOS(config=config)
        logger.info("DBOS initialised (system DB: %s)", config["system_database_url"].split("@")[-1])
    return _dbos_instance


def destroy_dbos() -> None:
    """
    Destroy the DBOS instance on shutdown.

    Call from neuron.py shutdown / signal handler to allow DBOS to flush
    pending state to Postgres before the process exits.
    """
    global _dbos_instance
    if _dbos_instance is not None:
        try:
            DBOS.destroy()
            logger.info("DBOS destroyed cleanly.")
        except Exception as exc:
            logger.warning("DBOS destroy error (non-fatal): %s", exc)
        finally:
            _dbos_instance = None
