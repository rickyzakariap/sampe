"""Offline Passenger adapter smoke test against the isolated PostgreSQL test DB."""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from postgres.migrate import validate_test_target


class PassengerSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dsn = os.environ.get("SAMPE_POSTGRES_DSN")
        expected = os.environ.get("SAMPE_POSTGRES_TEST_DB")
        if not dsn or not expected:
            raise unittest.SkipTest("isolated PostgreSQL test DB not configured")
        validate_test_target(os.environ.get("SAMPE_POSTGRES_ENV", ""), expected, expected)
        import psycopg

        cls.email = "synthetic-passenger-admin@example.test"
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            actual = conn.execute("SELECT current_database()").fetchone()[0]
            validate_test_target("testing", actual, expected)
            if conn.execute("SELECT 1 FROM sampe.users WHERE email=%s", (cls.email,)).fetchone():
                raise unittest.SkipTest("synthetic Passenger fixture already exists")

        os.environ["SAMPE_DB_BACKEND"] = "postgres"
        os.environ["SAMPE_POSTGRES_TARGET_DB"] = expected
        os.environ["ADMIN_EMAIL"] = cls.email
        os.environ["ADMIN_PASSWORD"] = "synthetic-passenger-password-only"
        os.environ["JWT_SECRET"] = "synthetic-passenger-jwt-only"
        import passenger_wsgi
        cls.application = passenger_wsgi.application
        cls.dsn = dsn

    @classmethod
    def tearDownClass(cls):
        import psycopg
        with psycopg.connect(cls.dsn, connect_timeout=5) as conn:
            conn.execute("DELETE FROM sampe.login_attempts WHERE identifier LIKE %s", ("%" + cls.email,))
            conn.execute("DELETE FROM sampe.users WHERE email=%s", (cls.email,))

    def test_health_and_webhook_path_through_wsgi(self):
        import httpx
        with httpx.Client(transport=httpx.WSGITransport(app=self.application), base_url="http://test") as client:
            health = client.get("/api/health")
            self.assertEqual(health.status_code, 200, health.text)
            self.assertEqual(health.json(), {"status": "ok"})
            webhook = client.get("/api/webhooks/lynk")
            self.assertEqual(webhook.status_code, 200, webhook.text)
            self.assertTrue(webhook.json()["ok"])

    def test_lynk_store_fallback_preserves_specific_url(self):
        from lynk_contract import LYNK_STORE_URL, renew_url
        self.assertEqual(renew_url(None), "https://lynk.id/katalogsatset")
        self.assertEqual(renew_url(""), LYNK_STORE_URL)
        self.assertEqual(renew_url("https://lynk.id/katalogsatset/product"),
                         "https://lynk.id/katalogsatset/product")


if __name__ == "__main__":
    unittest.main()
