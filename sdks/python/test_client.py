import hashlib
import hmac
import os
import unittest
from unittest.mock import patch

from pesaguard_client import PesaGuardClient, verify_webhook_signature


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

    def test_webhook_signature_validates_raw_body_and_timestamp(self):
        secret = "webhook-test-secret"
        body = b'{"id":"evt_1","type":"webhook.test"}'
        timestamp = 1_800_000_000
        digest = hmac.new(secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256).hexdigest()
        header = f"t={timestamp},v1={digest}"
        self.assertTrue(verify_webhook_signature(secret, body, header, now=timestamp))
        self.assertFalse(verify_webhook_signature(secret, body + b" ", header, now=timestamp))
        self.assertFalse(verify_webhook_signature(secret, body, header, now=timestamp + 301))

    def test_valid_sandbox_configuration_uses_sandbox_origin(self):
        with patch.dict(os.environ, {}, clear=True):
            client = PesaGuardClient(api_key="pg_sandbox_example", environment="sandbox")
        self.assertEqual(client.base_url, "https://sandbox-api.pesaguard.co.ke/")


if __name__ == "__main__":
    unittest.main()
