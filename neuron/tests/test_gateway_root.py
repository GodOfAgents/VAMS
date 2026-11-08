import sys
import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

# We want 'gateway' to resolve to the ROOT 'gateway' folder.
# The root folder is two levels up from this file's folder (neuron/tests/test_gateway_root.py).
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Insert root_dir at index 0 of sys.path
sys.path.insert(0, root_dir)

os.environ["GATEWAY_ADMIN_PASSWORD"] = "SecureTestPassword123!"
os.environ["VAMS_ENV"] = "test"

from gateway.server import app
from neuron.tests.m2_gateway_helpers import (
    AUDIENCE,
    SIGNER,
    compact_json,
    signed_headers,
)

class TestGatewayRoot(unittest.TestCase):
    
    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "VAMS_ENV": "test",
                "GATEWAY_ADMIN_PASSWORD": "SecureTestPassword123!",
                "GATEWAY_ADMIN_DID": SIGNER,
                "GATEWAY_AUTH_AUDIENCE": AUDIENCE,
            },
            clear=False,
        )
        self.environment.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.environment.stop()

    # spec=True mirrors the real composer, so Python 3.12 permits its
    # assert_simulation_available() method on the mock.
    @patch("gateway.server.composer", spec=True)
    def test_compose_endpoint_premium(self, mock_composer):
        """Test `/compose` endpoint returns premium details in the JSON response from the root gateway server."""
        from neuron.composer.models import InstanceBlueprint, ComputeSpec, GPUType, AllocationPlan, ProvisionedInstance, ResourceAssignment
        import time

        # Mock blueprint
        bp = InstanceBlueprint(
            name="ServiceBlock_OMS_v1",
            compute=ComputeSpec(gpu_type=GPUType.ANY),
            required_service_blocks=["ServiceBlock_OMS_v1"]
        )

        # Mock allocation plan
        plan = AllocationPlan(
            blueprint_hash="0x123",
            assignments=[
                ResourceAssignment(
                    node_id="n1",
                    provider="0xPROVIDER",
                    hw_class="ANY",
                    region="us-east-1",
                    allocated_units=1,
                    hourly_cost=100.0,
                    score=1.0
                )
            ],
            total_hourly_cost=100.0,
            total_nodes=1
        )

        # Mock provisioned instance
        instance = ProvisionedInstance(
            instance_id="vams-test-instance",
            blueprint=bp,
            allocation=plan,
            expires_at=time.time() + 3600
        )

        mock_composer.provision_blueprint.return_value = instance

        # Call the compose endpoint
        payload = {"blueprint_name": "ServiceBlock_OMS_v1"}
        body = compact_json(payload)
        response = self.client.post(
            "/compose",
            content=body,
            headers=signed_headers("POST", "/compose", body=body),
        )

        # Assertions
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        # M1 containment: composition output is an explicitly labelled,
        # non-authoritative simulation, never a provisioning claim.
        self.assertEqual(json_data["status"], "simulated")
        self.assertIs(json_data["simulation"], True)
        self.assertEqual(json_data["evidence_classification"], "non-authoritative")
        self.assertEqual(json_data["base_hourly_cost"], 100.0)
        self.assertEqual(json_data["premium_rate_bps"], 700) # 2% base + 5% OMS = 7%
        self.assertEqual(json_data["premium_hourly_cost"], 7.0)
        self.assertEqual(json_data["total_hourly_cost"], 107.0)

if __name__ == "__main__":
    unittest.main()
