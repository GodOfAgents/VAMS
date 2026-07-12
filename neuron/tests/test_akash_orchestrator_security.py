import os
from unittest.mock import patch

import pytest

from neuron.sdk.akash_orchestrator import AkashOrchestratorError, AkashOrchestratorSDK


def test_live_mode_resolves_configured_cli_to_absolute_path(tmp_path):
    cli_path = tmp_path / "provider-services.exe"
    cli_path.write_bytes(b"test executable placeholder")

    with patch.dict(
        os.environ,
        {"AKASH_MOCK_MODE": "false", "AKASH_CLI_PATH": str(cli_path)},
    ), patch("neuron.sdk.akash_orchestrator.subprocess.run") as run:
        sdk = AkashOrchestratorSDK(timeout=7)

    assert sdk._cli_path == os.path.abspath(cli_path)
    run.assert_called_once_with(
        [os.path.abspath(cli_path), "version"],
        check=True,
        capture_output=True,
        timeout=7,
    )


def test_live_mode_rejects_missing_configured_cli(tmp_path):
    missing_path = tmp_path / "missing-provider-services.exe"

    with patch.dict(
        os.environ,
        {"AKASH_MOCK_MODE": "false", "AKASH_CLI_PATH": str(missing_path)},
    ):
        with pytest.raises(AkashOrchestratorError, match="regular file"):
            AkashOrchestratorSDK()
