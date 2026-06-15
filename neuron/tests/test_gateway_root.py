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

# Clear any already loaded 'gateway' modules from sys.modules to prevent cross-contamination
for mod in list(sys.modules.keys()):
    if mod.startswith("gateway"):
        del sys.modules[mod]

from gateway.server import app

class TestGatewayRoot(unittest.TestCase):
    
    def setUp(self):
        self.client = TestClient(app)

    @patch("gateway.server.composer")
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
        auth = ("admin", "vams2026")
        payload = {"blueprint_name": "ServiceBlock_OMS_v1"}
        response = self.client.post("/compose", json=payload, auth=auth)

        # Assertions
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["status"], "provisioned")
        self.assertEqual(json_data["base_hourly_cost"], 100.0)
        self.assertEqual(json_data["premium_rate_bps"], 700) # 2% base + 5% OMS = 7%
        self.assertEqual(json_data["premium_hourly_cost"], 7.0)
        self.assertEqual(json_data["total_hourly_cost"], 107.0)

if __name__ == "__main__":
    unittest.main()
