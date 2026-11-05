"""Synthetic end-to-end checks of the real SAMPE FastAPI app on sampe_test.

The OAuth provider is replaced by an in-process verifier. No live network,
payment, customer, or production database is used.
"""

import asyncio
import hashlib
import os
import sys
import types
import unittest
import uuid
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from postgres.migrate import validate_test_target


TEST_KEY = "synthetic-main-app-merchant"
ADMIN_EMAIL = "synthetic-3b-admin@example.test"
ADMIN_PASSWORD = "synthetic-3b-admin-only"


class FakeOAuthResponse:
    status_code = 200

    def __init__(self, identity):
        self.identity = identity

    def json(self):
        return self.identity


class FakeOAuthClient:
    def __init__(self, identities):
        self.identities = identities

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def get(self, url, headers):
        identity = self.identities.get(headers.get("X-Session-ID"))
        if identity is None:
            return types.SimpleNamespace(status_code=401)
        return FakeOAuthResponse(identity)


class MainAppPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dsn = os.environ.get("SAMPE_POSTGRES_DSN")
        expected = os.environ.get("SAMPE_POSTGRES_TEST_DB")
        if not dsn or not expected:
            raise unittest.SkipTest("isolated PostgreSQL test DB not configured")
        validate_test_target(os.environ.get("SAMPE_POSTGRES_ENV", ""), expected, expected)
        os.environ["SAMPE_DB_BACKEND"] = "postgres"
        os.environ["SAMPE_POSTGRES_TARGET_DB"] = expected
        os.environ["ADMIN_EMAIL"] = ADMIN_EMAIL
        os.environ["ADMIN_PASSWORD"] = ADMIN_PASSWORD
        os.environ["JWT_SECRET"] = "synthetic-3b-jwt-signing-key-local-only"
        import psycopg
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            actual = conn.execute("SELECT current_database()").fetchone()[0]
            validate_test_target("testing", actual, expected)
            if conn.execute("SELECT 1 FROM sampe.users WHERE email=%s", (ADMIN_EMAIL,)).fetchone():
                raise unittest.SkipTest("synthetic admin fixture already exists")
            if conn.execute("SELECT 1 FROM sampe.settings WHERE key='lynk'").fetchone():
                raise unittest.SkipTest("test DB already has Lynk settings; refusing overwrite")
        import auth
        import server
        cls.auth, cls.server = auth, server
        asyncio.run(server.startup())
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            conn.execute("INSERT INTO sampe.settings (key,merchant_key) VALUES ('lynk',%s)", (TEST_KEY,))

    @classmethod
    def tearDownClass(cls):
        import psycopg
        with psycopg.connect(os.environ["SAMPE_POSTGRES_DSN"], connect_timeout=5) as conn:
            conn.execute("DELETE FROM sampe.login_attempts WHERE identifier LIKE %s", ("%" + ADMIN_EMAIL,))
            conn.execute("DELETE FROM sampe.settings WHERE key='lynk' AND merchant_key=%s", (TEST_KEY,))
            conn.execute("DELETE FROM sampe.users WHERE email=%s", (ADMIN_EMAIL,))

    def setUp(self):
        self.tag = "it3b_" + uuid.uuid4().hex
        self.extra_license_ids = []
        self.email = self.tag + "@example.test"
        self.other_email = self.tag + "_other@example.test"
        self.ref = self.tag + "_ref"
        self.identities = {
            self.tag + "_oauth": {"email": self.email, "name": "Buyer", "picture": None,
                                    "session_token": self.tag + "_session"},
            self.tag + "_other_oauth": {"email": self.other_email, "name": "Other", "picture": None,
                                          "session_token": self.tag + "_other_session"},
        }
        self.original_httpx = self.auth.httpx
        self.auth.httpx = types.SimpleNamespace(AsyncClient=lambda timeout: FakeOAuthClient(self.identities))

    def tearDown(self):
        self.auth.httpx = self.original_httpx
        import psycopg
        with psycopg.connect(os.environ["SAMPE_POSTGRES_DSN"], connect_timeout=5) as conn:
            conn.execute("DELETE FROM sampe.entries WHERE id LIKE %s", (self.tag + "%",))
            conn.execute("DELETE FROM sampe.entries WHERE tenant_id IN (SELECT id FROM sampe.licenses WHERE email LIKE %s)", (self.tag + "%",))
            conn.execute("DELETE FROM sampe.kpi_config WHERE tenant_id IN (SELECT id FROM sampe.licenses WHERE email LIKE %s)", (self.tag + "%",))
            conn.execute("DELETE FROM sampe.lynk_orders WHERE ref_id LIKE %s", (self.tag + "%",))
            conn.execute("DELETE FROM sampe.user_sessions WHERE session_token LIKE %s", (self.tag + "%",))
            for license_id in self.extra_license_ids:
                conn.execute("DELETE FROM sampe.licenses WHERE id=%s", (license_id,))
            conn.execute("DELETE FROM sampe.licenses WHERE email LIKE %s", (self.tag + "%",))
            conn.execute("DELETE FROM sampe.members WHERE email LIKE %s", (self.tag + "%",))
            conn.execute("DELETE FROM sampe.lynk_email_locks WHERE email LIKE %s", (self.tag + "%",))
            conn.execute("DELETE FROM sampe.webhook_logs WHERE ref_id LIKE %s", (self.tag + "%",))
            conn.execute("DELETE FROM sampe.login_attempts WHERE identifier LIKE %s", ("%" + self.tag + "%",))

    def payment(self, ref=None, email=None, product="SAMPE - System Analytic Marketplace (7 Hari)"):
        ref = ref or self.ref
        body = {"event": "payment.received", "data": {"message_id": "msg_" + ref,
                "message_action": "SUCCESS", "message_code": 0,
                "message_data": {"refId": ref, "customer": {"email": email or self.email, "name": "Synthetic"},
                                 "items": [{"title": product, "qty": 1}], "totals": {"grandTotal": 0}}}}
        signature = hashlib.sha256(f"0{ref}msg_{ref}{TEST_KEY}".encode()).hexdigest()
        return body, signature

    def test_main_app_contract_and_tenant_isolation(self):
        import httpx
        body, signature = self.payment()

        async def exercise():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.server.app), base_url="http://test") as client:
                admin_login = await client.post("/api/auth/admin-login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
                self.assertEqual(admin_login.status_code, 200, admin_login.text)
                admin = {"Authorization": "Bearer " + admin_login.json()["token"]}
                self.assertEqual((await client.get("/api/auth/admin-me", headers=admin)).status_code, 200)
                self.assertEqual((await client.get("/api/admin/lynk", headers=admin)).status_code, 200)
                self.assertEqual((await client.put("/api/admin/lynk", json={"renew_url": "https://example.test/renew"}, headers=admin)).status_code, 200)
                self.assertEqual((await client.get("/api/webhooks/lynk")).status_code, 200)

                bad = await client.post("/api/webhooks/lynk", json=body, headers={"X-Lynk-Signature": "wrong"})
                self.assertEqual(bad.status_code, 401)
                webhook = await client.post("/api/webhooks/lynk", json=body, headers={"X-Lynk-Signature": signature})
                self.assertEqual(webhook.status_code, 200, webhook.text)
                self.assertTrue(webhook.json()["processed"])
                duplicate = await client.post("/api/webhooks/lynk", json=body, headers={"X-Lynk-Signature": signature})
                self.assertTrue(duplicate.json()["duplicate"])
                lookup = await client.post("/api/activation/lookup", json={"email": self.email, "ref_id": self.ref})
                self.assertEqual(lookup.status_code, 200, lookup.text)
                code = lookup.json()["code"]

                login = await client.post("/api/auth/google-session", json={"session_id": self.tag + "_oauth"})
                self.assertEqual(login.status_code, 200, login.text)
                user = {"Authorization": "Bearer " + login.json()["session_token"]}
                me = await client.get("/api/auth/me", headers=user)
                self.assertEqual(me.status_code, 200, me.text)
                self.assertEqual(me.json()["license"]["code"], code)
                self.assertEqual(me.json()["license"]["status"], "active")
                before_expiry = me.json()["license"]["expires_at"]
                renewal_ref = self.ref + "_renew"
                renewal_body, renewal_sig = self.payment(ref=renewal_ref,
                    product="SAMPE - System Analytic Marketplace (30 Hari)")
                renewed = await client.post("/api/webhooks/lynk", json=renewal_body,
                                            headers={"X-Lynk-Signature": renewal_sig})
                self.assertEqual(renewed.status_code, 200, renewed.text)
                self.assertEqual(renewed.json()["action"], "extended")
                renewal_lookup = await client.post("/api/activation/lookup",
                                                   json={"email": self.email, "ref_id": renewal_ref})
                self.assertEqual(renewal_lookup.json()["code"], code)
                from datetime import datetime as parsed_datetime
                delta = parsed_datetime.fromisoformat(renewal_lookup.json()["expires_at"]) - parsed_datetime.fromisoformat(before_expiry)
                self.assertAlmostEqual(delta.total_seconds(), 30 * 86400, delta=3)
                retry = await client.post("/api/webhooks/lynk", json=renewal_body,
                                          headers={"X-Lynk-Signature": renewal_sig})
                self.assertTrue(retry.json()["duplicate"])

                config = {"company_name": "Synthetic Store", "month": "2026-10", "target_sales": 100000,
                          "budget_ads": 10000}
                saved = await client.post("/api/config", json=config, headers=user)
                self.assertEqual(saved.status_code, 200, saved.text)
                config_id = saved.json()["id"]
                revised = await client.post("/api/config", json=dict(config, target_sales=120000), headers=user)
                self.assertEqual(revised.status_code, 200, revised.text)
                self.assertEqual(revised.json()["id"], config_id)
                self.assertEqual((await client.get("/api/config", headers=user)).json()["target_sales"], 120000)
                self.assertEqual((await client.get("/api/config/history", headers=user)).status_code, 200)
                updated = await client.patch("/api/config/company", json={"company_name": "Updated Synthetic"}, headers=user)
                self.assertEqual(updated.status_code, 200, updated.text)
                self.assertEqual(updated.json()["company_name"], "Updated Synthetic")
                entry = await client.post("/api/entries", json={"module": "sales", "date": "2026-10-14",
                                  "data": {"platform": "Synthetic", "omzet": 30000}}, headers=user)
                self.assertEqual(entry.status_code, 200, entry.text)
                listed = await client.get("/api/entries?module=sales&month=2026-10", headers=user)
                self.assertEqual(len(listed.json()), 1)
                dashboard = await client.get("/api/dashboard?month=2026-10", headers=user)
                self.assertEqual(dashboard.status_code, 200, dashboard.text)
                self.assertEqual(dashboard.json()["sales"]["achieved"], 30000)
                self.assertEqual((await client.get("/api/compare?month=2026-10", headers=user)).status_code, 200)
                self.assertIn("2026-10", (await client.get("/api/months", headers=user)).json())
                other_body, other_sig = self.payment(ref=self.ref + "_other", email=self.other_email)
                self.assertEqual((await client.post("/api/webhooks/lynk", json=other_body,
                                  headers={"X-Lynk-Signature": other_sig})).status_code, 200)
                other_login = await client.post("/api/auth/google-session", json={"session_id": self.tag + "_other_oauth"})
                self.assertEqual(other_login.status_code, 200, other_login.text)
                other = {"Authorization": "Bearer " + other_login.json()["session_token"]}
                self.assertEqual((await client.get("/api/entries", headers=other)).json(), [])
                self.assertIsNone((await client.get("/api/config", headers=other)).json())
                self.assertEqual((await client.delete("/api/entries/" + entry.json()["id"], headers=other)).status_code, 404)
                self.assertEqual((await client.delete("/api/entries/" + entry.json()["id"], headers=user)).status_code, 200)
                self.assertEqual((await client.get("/api/admin/licenses", headers=user)).status_code, 401)
                self.assertEqual((await client.get("/api/admin/licenses", headers=admin)).status_code, 200)
                self.assertEqual((await client.get("/api/admin/orders", headers=admin)).status_code, 200)
                self.assertEqual((await client.get("/api/admin/webhook-logs", headers=admin)).status_code, 200)
                self.assertEqual((await client.post("/api/admin/webhook-logs/process", params={"received_at": "synthetic"}, headers=admin)).status_code, 409)

                seed = await client.post("/api/seed", json={"company_name": "Synthetic Demo"}, headers=user)
                self.assertEqual(seed.status_code, 200, seed.text)
                self.assertGreater(seed.json()["entries"], 0)
                reset = await client.post("/api/reset", headers=user)
                self.assertEqual(reset.status_code, 200, reset.text)
                self.assertGreater(reset.json()["deleted_entries"], 0)
                self.assertIsNone((await client.get("/api/config", headers=user)).json())
                self.assertEqual((await client.get("/api/entries", headers=user)).json(), [])
                self.assertEqual((await client.post("/api/auth/logout", headers=user)).status_code, 200)
                self.assertEqual((await client.get("/api/auth/me", headers=user)).status_code, 401)

        asyncio.run(exercise())

    def test_four_packages_on_main_webhook(self):
        import httpx
        variants = [("SAMPE - System Analytic Marketplace", 1),
                    ("SAMPE - System Analytic Marketplace (7 Hari)", 7),
                    ("SAMPE - System Analytic Marketplace (30 Hari)", 30),
                    ("SAMPE - System Analytic Marketplace (365 Hari)", 365)]

        async def exercise():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.server.app), base_url="http://test") as client:
                for index, (title, days) in enumerate(variants):
                    ref = self.ref + str(index)
                    email = f"{self.tag}_{index}@example.test"
                    body, sig = self.payment(ref=ref, email=email, product=title)
                    response = await client.post("/api/webhooks/lynk", json=body, headers={"X-Lynk-Signature": sig})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertTrue(response.json()["processed"])
                    lookup = await client.post("/api/activation/lookup", json={"email": email, "ref_id": ref})
                    self.assertEqual(lookup.status_code, 200, lookup.text)
                    self.assertEqual(lookup.json()["days"], days)

        asyncio.run(exercise())

    def test_admin_license_claim_and_management(self):
        import httpx

        async def exercise():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.server.app), base_url="http://test") as client:
                login = await client.post("/api/auth/admin-login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
                self.assertEqual(login.status_code, 200, login.text)
                admin = {"Authorization": "Bearer " + login.json()["token"]}
                created = await client.post("/api/admin/licenses", json={"label": "Synthetic manual", "duration_days": 1}, headers=admin)
                self.assertEqual(created.status_code, 200, created.text)
                lic = created.json()
                self.extra_license_ids.append(lic["id"])
                member_login = await client.post("/api/auth/google-session", json={"session_id": self.tag + "_oauth"})
                self.assertEqual(member_login.status_code, 200, member_login.text)
                member = {"Authorization": "Bearer " + member_login.json()["session_token"]}
                self.assertIsNone((await client.get("/api/auth/me", headers=member)).json()["license"])
                claim = await client.post("/api/auth/claim", json={"code": lic["code"]}, headers=member)
                self.assertEqual(claim.status_code, 200, claim.text)
                self.assertEqual(claim.json()["status"], "active")
                extended = await client.post(f"/api/admin/licenses/{lic['id']}/extend", json={"days": 7}, headers=admin)
                self.assertEqual(extended.status_code, 200, extended.text)
                revoked = await client.post(f"/api/admin/licenses/{lic['id']}/revoke", headers=admin)
                self.assertEqual(revoked.status_code, 200, revoked.text)
                self.assertEqual((await client.get("/api/entries", headers=member)).status_code, 403)
                restored = await client.post(f"/api/admin/licenses/{lic['id']}/restore", headers=admin)
                self.assertEqual(restored.status_code, 200, restored.text)
                self.assertEqual((await client.get("/api/entries", headers=member)).status_code, 200)
                other_login = await client.post("/api/auth/google-session", json={"session_id": self.tag + "_other_oauth"})
                other = {"Authorization": "Bearer " + other_login.json()["session_token"]}
                rejected = await client.post("/api/auth/claim", json={"code": lic["code"]}, headers=other)
                self.assertEqual(rejected.status_code, 409)

        asyncio.run(exercise())

    def test_rate_limit_on_synthetic_admin_identity(self):
        import httpx
        address = self.tag + "_admin@example.test"

        async def exercise():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.server.app), base_url="http://test") as client:
                for _ in range(5):
                    bad = await client.post("/api/auth/admin-login", json={"email": address, "password": "wrong"})
                    self.assertEqual(bad.status_code, 401)
                locked = await client.post("/api/auth/admin-login", json={"email": address, "password": "wrong"})
                self.assertEqual(locked.status_code, 429)

        asyncio.run(exercise())

    def test_onboarding_replace_rolls_back_after_invalid_entry(self):
        body, signature = self.payment()
        # The same validated order path used by the HTTP route creates a tenant.
        from postgres.access import PostgresAccess
        created = PostgresAccess(os.environ["SAMPE_POSTGRES_DSN"]).receive_webhook(body, signature)
        tenant = created["license_id"]
        when = datetime.now(timezone.utc).isoformat()
        old_config = {"id": self.tag + "_config", "tenant_id": tenant,
                      "company_name": "Before", "month": "2026-10", "created_at": when}
        old_entry = {"id": self.tag + "_entry", "tenant_id": tenant, "module": "sales",
                     "date": "2026-10-14", "data": {"omzet": 5}, "created_at": when}
        asyncio.run(self.server.db.save_kpi_config(old_config))
        asyncio.run(self.server.db.entries.insert_one(old_entry))
        replacement = dict(old_config, id=self.tag + "_replacement", company_name="After")
        invalid = dict(old_entry, id=self.tag + "_invalid", date="not-a-date")
        with self.assertRaises(Exception):
            asyncio.run(self.server.db.replace_tenant_demo(tenant, replacement, [invalid]))
        config = asyncio.run(self.server.db.kpi_config.find_one({"tenant_id": tenant}, {"_id": 0}))
        entries = asyncio.run(self.server.db.entries.find({"tenant_id": tenant}, {"_id": 0}).to_list(10))
        self.assertEqual(config["company_name"], "Before")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["id"], old_entry["id"])

    def test_postgres_target_mismatch_fails_closed(self):
        actual = os.environ["SAMPE_POSTGRES_TARGET_DB"]
        os.environ["SAMPE_POSTGRES_TARGET_DB"] = "different_test_database"
        try:
            with self.assertRaises(RuntimeError):
                asyncio.run(self.server.db.validate_target())
        finally:
            os.environ["SAMPE_POSTGRES_TARGET_DB"] = actual

    def test_health_and_production_target_guard(self):
        import httpx

        async def check_health():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.server.app), base_url="http://test") as client:
                response = await client.get("/api/health")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"status": "ok"})

        asyncio.run(check_health())
        original_env = os.environ["SAMPE_POSTGRES_ENV"]
        try:
            os.environ["SAMPE_POSTGRES_ENV"] = "production"
            with self.assertRaisesRegex(RuntimeError, "test or staging"):
                asyncio.run(self.server.db.validate_target())
        finally:
            os.environ["SAMPE_POSTGRES_ENV"] = original_env

    def test_postgres_runtime_has_no_mongo_driver(self):
        self.assertEqual(self.server.DB_BACKEND, "postgres")
        self.assertEqual(self.server.db.backend, "postgres")
        self.assertNotIn("motor", sys.modules)
        self.assertNotIn("motor.motor_asyncio", sys.modules)

    def test_ai_route_contract_with_in_process_provider_stub(self):
        import httpx
        import ai_analysis

        async def fake_provider(context):
            return "Synthetic analysis", "mock-model"
        body, signature = self.payment()

        async def exercise():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.server.app), base_url="http://test") as client:
                self.assertEqual((await client.post("/api/webhooks/lynk", json=body,
                                  headers={"X-Lynk-Signature": signature})).status_code, 200)
                login = await client.post("/api/auth/google-session", json={"session_id": self.tag + "_oauth"})
                bearer = {"Authorization": "Bearer " + login.json()["session_token"]}
                config = await client.post("/api/config", json={"company_name": "Synthetic",
                                           "month": "2026-10", "target_sales": 1000}, headers=bearer)
                self.assertEqual(config.status_code, 200)
                result = await client.post("/api/ai/analyze", json={"month": "2026-10"}, headers=bearer)
                self.assertEqual(result.status_code, 200, result.text)
                self.assertEqual(result.json()["analysis"], "Synthetic analysis")

        with patch.object(ai_analysis, "request_analysis", fake_provider):
            asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
