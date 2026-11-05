"""Real PostgreSQL 3A integration tests; refuse any target not named test.

All buyer identities and Merchant Key values here are synthetic. Each test
cleans up only rows bearing its unique fixture identifier.
"""

import asyncio
import hashlib
import os
import sys
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from postgres.migrate import validate_test_target
from postgres.access import PolicyDecisionRequired, PostgresAccess


PRODUCTS = [
    ("SAMPE - System Analytic Marketplace", 1),
    ("SAMPE - System Analytic Marketplace (7 Hari)", 7),
    ("SAMPE - System Analytic Marketplace (30 Hari)", 30),
    ("SAMPE - System Analytic Marketplace (365 Hari)", 365),
]
TEST_KEY = "synthetic-3a-merchant-key"


class FailingAccess(PostgresAccess):
    def _after_license_write(self):
        raise RuntimeError("synthetic failure after license write")


class PortingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dsn = os.environ.get("SAMPE_POSTGRES_DSN")
        expected = os.environ.get("SAMPE_POSTGRES_TEST_DB")
        if not dsn or not expected:
            raise unittest.SkipTest("isolated PostgreSQL DSN not configured")
        validate_test_target(os.environ.get("SAMPE_POSTGRES_ENV", ""), expected, expected)
        cls.access = PostgresAccess(dsn)
        with cls.access.connect() as conn:
            actual = conn.execute("SELECT current_database() AS name").fetchone()["name"]
            validate_test_target(os.environ.get("SAMPE_POSTGRES_ENV", ""), actual, expected)
            row = conn.execute("SELECT merchant_key FROM sampe.settings WHERE key='lynk'").fetchone()
            if row:
                raise unittest.SkipTest("test database already contains Lynk settings; refusing overwrite")
            conn.execute("INSERT INTO sampe.settings (key,merchant_key) VALUES ('lynk',%s)", (TEST_KEY,))

    @classmethod
    def tearDownClass(cls):
        with cls.access.connect() as conn:
            conn.execute("DELETE FROM sampe.settings WHERE key='lynk' AND merchant_key=%s", (TEST_KEY,))

    def setUp(self):
        self.tag = "it3a_" + uuid.uuid4().hex
        self.email = self.tag + "@example.test"
        self.ref = self.tag + "_ref"

    def tearDown(self):
        with self.access.connect() as conn:
            conn.execute("DELETE FROM sampe.lynk_orders WHERE ref_id LIKE %s", (self.tag + "%",))
            conn.execute("DELETE FROM sampe.user_sessions WHERE session_token LIKE %s", (self.tag + "%",))
            conn.execute("DELETE FROM sampe.licenses WHERE email LIKE %s", (self.tag + "%",))
            conn.execute("DELETE FROM sampe.members WHERE email LIKE %s", (self.tag + "%",))
            conn.execute("DELETE FROM sampe.lynk_email_locks WHERE email LIKE %s", (self.tag + "%",))

    def payload(self, title=PRODUCTS[0][0], *, ref=None, total=0, email=None, action="SUCCESS"):
        ref = ref or self.ref
        body = {"event": "payment.received", "data": {"message_id": "msg_" + ref,
                "message_action": action, "message_code": 0,
                "message_data": {"refId": ref, "customer": {"email": email or self.email, "name": "Synthetic"},
                                 "items": [{"title": title, "qty": 1}],
                                 "totals": {"totalPrice": 20000, "discount": -20000,
                                            "customerPay": 0, "grandTotal": total}}}}
        sig = hashlib.sha256(f"{total}{ref}msg_{ref}{TEST_KEY}".encode()).hexdigest()
        return body, sig

    def order_and_license(self, ref=None):
        with self.access.connect() as conn:
            row = conn.execute("""SELECT o.*, l.code, l.expires_at, l.activated_at, l.owner_user_id
                                  FROM sampe.lynk_orders o LEFT JOIN sampe.licenses l ON l.id=o.license_id
                                  WHERE o.ref_id=%s""", (ref or self.ref,)).fetchone()
            return row

    def test_four_packages_and_zero_total(self):
        for index, (title, days) in enumerate(PRODUCTS):
            ref = self.ref + str(index)
            body, sig = self.payload(title, ref=ref, email=f"{self.tag}_{index}@example.test")
            result = self.access.receive_webhook(body, sig)
            row = self.order_and_license(ref)
            self.assertTrue(result["processed"])
            self.assertEqual(row["days"], days)
            self.assertEqual(row["status"], "processed")
            self.assertIsNotNone(row["code"])
            self.assertIsNone(row["activated_at"])

    def test_first_activation_and_session_isolation(self):
        body, sig = self.payload()
        self.access.receive_webhook(body, sig)
        before = self.order_and_license()
        uid = self.access.start_session(self.email, "Buyer", self.tag + "_session")
        after = self.order_and_license()
        self.assertEqual(after["owner_user_id"], uid)
        self.assertIsNone(before["activated_at"])
        self.assertIsNotNone(after["activated_at"])
        self.assertAlmostEqual((after["expires_at"] - after["activated_at"]).total_seconds(), 86400, delta=3)
        self.assertEqual(self.access.member_for_session(self.tag + "_session")["user_id"], uid)
        self.assertEqual(self.access.license_for_member(uid)["id"], after["license_id"])
        other = self.tag + "_other@example.test"
        other_uid = self.access.start_session(other, "Other", self.tag + "_other_session")
        self.assertNotEqual(uid, other_uid)
        self.assertIsNone(self.access.license_for_member(other_uid))
        self.assertIsNone(self.access.activation_lookup(other, self.ref))
        self.assertEqual(self.access.activation_lookup(self.email, self.ref)["code"], before["code"])

    def test_existing_session_binds_license_after_webhook(self):
        user_id = self.access.start_session(self.email, "Buyer", self.tag + "_session")
        self.assertIsNone(self.access.ensure_member_license(user_id))
        body, sig = self.payload()
        self.access.receive_webhook(body, sig)
        unbound = self.order_and_license()
        self.assertIsNone(unbound["owner_user_id"])
        bound = self.access.ensure_member_license(user_id)
        self.assertEqual(bound["id"], unbound["license_id"])
        self.assertIsNotNone(bound["activated_at"])
        self.assertEqual(self.access.ensure_member_license(user_id)["activated_at"], bound["activated_at"])

    def test_active_and_expired_renewal_and_duplicate(self):
        body, sig = self.payload()
        self.access.receive_webhook(body, sig)
        self.access.start_session(self.email, "Buyer", self.tag + "_session")
        initial = self.order_and_license()
        ref2 = self.ref + "_renew"
        b2, s2 = self.payload(PRODUCTS[1][0], ref=ref2)
        self.access.receive_webhook(b2, s2)
        renewed = self.order_and_license(ref2)
        self.assertEqual(renewed["license_id"], initial["license_id"])
        self.assertEqual(renewed["code"], initial["code"])
        self.assertAlmostEqual((renewed["expires_at"] - initial["expires_at"]).total_seconds(), 7 * 86400, delta=3)
        self.assertTrue(self.access.receive_webhook(b2, s2)["duplicate"])
        self.assertEqual(self.order_and_license(ref2)["expires_at"], renewed["expires_at"])
        expired = datetime.now(timezone.utc) - timedelta(days=1)
        with self.access.connect() as conn:
            conn.execute("UPDATE sampe.licenses SET expires_at=%s WHERE id=%s", (expired, initial["license_id"]))
        ref3 = self.ref + "_expired"
        b3, s3 = self.payload(PRODUCTS[2][0], ref=ref3)
        self.access.receive_webhook(b3, s3)
        recovered = self.order_and_license(ref3)
        self.assertEqual(recovered["license_id"], initial["license_id"])
        self.assertAlmostEqual((recovered["expires_at"] - datetime.now(timezone.utc)).total_seconds(), 30 * 86400, delta=5)

    def test_parallel_same_ref_and_distinct_refs(self):
        body, sig = self.payload()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.access.receive_webhook(body, sig), range(2)))
        self.assertEqual(sum(not r["duplicate"] for r in results), 1)
        initial = self.order_and_license()
        with self.access.connect() as conn:
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM sampe.lynk_orders WHERE ref_id=%s", (self.ref,)).fetchone()["n"], 1)
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM sampe.licenses WHERE email=%s", (self.email,)).fetchone()["n"], 1)
        self.access.start_session(self.email, "Buyer", self.tag + "_session")
        base = self.order_and_license()["expires_at"]
        pairs = [self.payload(PRODUCTS[1][0], ref=self.ref + "_a"),
                 self.payload(PRODUCTS[2][0], ref=self.ref + "_b")]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda pair: self.access.receive_webhook(*pair), pairs))
        self.assertTrue(all(r["processed"] for r in results))
        self.assertTrue(all(r["license_id"] == initial["license_id"] for r in results))
        self.assertAlmostEqual((self.order_and_license()["expires_at"] - base).total_seconds(), 37 * 86400, delta=5)

    def test_rollback_and_invalid_inputs(self):
        body, sig = self.payload()
        with self.assertRaises(RuntimeError):
            FailingAccess(self.access.dsn).receive_webhook(body, sig)
        self.assertIsNone(self.order_and_license())
        with self.access.connect() as conn:
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM sampe.licenses WHERE email=%s", (self.email,)).fetchone()["n"], 0)
        with self.assertRaises(ValueError):
            self.access.receive_webhook(body, "wrong")
        unknown, signature = self.payload("Other product (30 Hari)")
        self.assertFalse(self.access.receive_webhook(unknown, signature)["processed"])
        self.assertIsNone(self.order_and_license()["license_id"])

    def test_renewal_rollback_keeps_previous_expiration(self):
        body, sig = self.payload()
        self.access.receive_webhook(body, sig)
        self.access.start_session(self.email, "Buyer", self.tag + "_session")
        initial = self.order_and_license()
        ref2 = self.ref + "_failed"
        b2, s2 = self.payload(PRODUCTS[3][0], ref=ref2)
        with self.assertRaises(RuntimeError):
            FailingAccess(self.access.dsn).receive_webhook(b2, s2)
        self.assertIsNone(self.order_and_license(ref2))
        self.assertEqual(self.order_and_license()["expires_at"], initial["expires_at"])

    def test_other_customer_cannot_renew_or_claim_license(self):
        body, sig = self.payload()
        self.access.receive_webhook(body, sig)
        owner_id = self.access.start_session(self.email, "Buyer", self.tag + "_session")
        original = self.order_and_license()
        other_email = self.tag + "_other@example.test"
        other_id = self.access.start_session(other_email, "Other", self.tag + "_other_session")
        with self.assertRaises(PermissionError):
            self.access.claim_license(other_id, original["code"])
        other_ref = self.ref + "_other"
        other_body, other_sig = self.payload(ref=other_ref, email=other_email)
        result = self.access.receive_webhook(other_body, other_sig)
        self.assertTrue(result["processed"])
        self.assertNotEqual(result["license_id"], original["license_id"])
        self.assertEqual(self.order_and_license()["owner_user_id"], owner_id)
        self.assertEqual(self.order_and_license()["expires_at"], original["expires_at"])

    def test_failed_payment_missing_field_and_pending_policy(self):
        body, sig = self.payload(action="FAILED")
        self.assertFalse(self.access.receive_webhook(body, sig)["processed"])
        self.assertIsNone(self.order_and_license())
        missing, _ = self.payload()
        del missing["data"]["message_data"]["refId"]
        with self.assertRaises(ValueError):
            self.access.receive_webhook(missing, sig)
        good, good_sig = self.payload()
        self.access.receive_webhook(good, good_sig)
        second_ref = self.ref + "_unactivated"
        second, second_sig = self.payload(ref=second_ref)
        result = self.access.receive_webhook(second, second_sig)
        self.assertEqual(result["status"], "pending_policy")
        self.assertIsNone(result["license_id"])
        with self.access.connect() as conn:
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM sampe.licenses WHERE email=%s", (self.email,)).fetchone()["n"], 1)

    def test_revoked_license_stops_without_new_policy_or_order(self):
        body, sig = self.payload()
        self.access.receive_webhook(body, sig)
        self.access.start_session(self.email, "Buyer", self.tag + "_session")
        original = self.order_and_license()
        with self.access.connect() as conn:
            conn.execute("UPDATE sampe.licenses SET revoked=true WHERE id=%s", (original["license_id"],))
        ref2 = self.ref + "_revoked"
        second, second_sig = self.payload(ref=ref2)
        with self.assertRaises(PolicyDecisionRequired):
            self.access.receive_webhook(second, second_sig)
        self.assertIsNone(self.order_and_license(ref2))
        with self.access.connect() as conn:
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM sampe.licenses WHERE email=%s", (self.email,)).fetchone()["n"], 1)

    def test_isolated_http_routes_with_real_postgres(self):
        try:
            import httpx
            from postgres.routes import create_postgres_app
        except ImportError:
            self.skipTest("ASGI test dependencies unavailable in this Python environment")

        async def verify_identity(session_id):
            if session_id != "synthetic-google-session":
                raise ValueError("invalid synthetic session")
            return {"email": self.email, "name": "Buyer", "session_token": self.tag + "_session"}

        app = create_postgres_app(self.access, verify_identity)
        body, sig = self.payload()

        async def exercise():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                bad_json = await client.post("/api/webhooks/lynk", content="{broken")
                self.assertEqual(bad_json.status_code, 400)
                bad_sig = await client.post("/api/webhooks/lynk", json=body, headers={"X-Lynk-Signature": "wrong"})
                self.assertEqual(bad_sig.status_code, 401)
                accepted = await client.post("/api/webhooks/lynk", json=body, headers={"X-Lynk-Signature": sig})
                self.assertEqual(accepted.status_code, 200)
                self.assertTrue(accepted.json()["processed"])
                lookup = await client.post("/api/activation/lookup", json={"email": self.email, "ref_id": self.ref})
                self.assertEqual(lookup.status_code, 200)
                code = lookup.json()["code"]
                login = await client.post("/api/auth/google-session", json={"session_id": "synthetic-google-session"})
                self.assertEqual(login.status_code, 200)
                token = login.json()["session_token"]
                mine = await client.get("/api/auth/me", headers={"Authorization": "Bearer " + token})
                self.assertEqual(mine.status_code, 200)
                self.assertEqual(mine.json()["license"]["code"], code)
                self.assertEqual(mine.json()["license"]["status"], "active")
                logout = await client.post("/api/auth/logout", headers={"Authorization": "Bearer " + token})
                self.assertEqual(logout.status_code, 200)
                denied = await client.get("/api/auth/me", headers={"Authorization": "Bearer " + token})
                self.assertEqual(denied.status_code, 401)

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
