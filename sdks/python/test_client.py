import os
import unittest
from unittest.mock import patch

from pesaguard_client import PesaGuardClient


class EnvironmentIsolationTests(unittest.TestCase):
    def test_sandbox_key_cannot_be_selected_for_production(self):
        with self.assertRaisesRegex(ValueError, "pg_live_"):
            PesaGuardClient(api_key="pg_sandbox_example", environment="production")

    def test_production_key_cannot_be_selected_for_sandbox(self):
        with self.assertRaisesRegex(ValueError, "pg_sandbox_"):
            PesaGuardClient(api_key="pg_live_example", environment="sandbox")

    def test_base_url_override_must_match_environment_host(self):
        with patch.dict(os.environ, {"PESAGUARD_BASE_URL": "https://sandbox-api.pesaguard.co.ke"}):
            with self.assertRaisesRegex(ValueError, "does not match"):
                PesaGuardClient(api_key="pg_live_example", environment="production")

    def test_valid_sandbox_configuration_uses_sandbox_origin(self):
        with patch.dict(os.environ, {}, clear=True):
            client = PesaGuardClient(api_key="pg_sandbox_example", environment="sandbox")
        self.assertEqual(client.base_url, "https://sandbox-api.pesaguard.co.ke/")


if __name__ == "__main__":
    unittest.main()
