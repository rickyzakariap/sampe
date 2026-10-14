"""Offline Lynk webhook tests using only Python's standard library and synthetic data.

No application core/auth import, live database, network call, or destructive collection operation.
"""
import asyncio
import copy
import hashlib
import importlib.util
import json
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail
        super().__init__(detail)


class PyMongoError(Exception):
    pass


class DuplicateKeyError(PyMongoError):
    pass


class FakeRouter:
    def __init__(self, **kwargs):
        pass

    def get(self, path):
        return lambda func: func

    def post(self, path):
        return lambda func: func

    def put(self, path):
        return lambda func: func


class BaseModel:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeCollection:
    def __init__(self, database, name):
        self.database, self.name = database, name

    @property
    def docs(self):
        return self.database.data[self.name]

    @staticmethod
    def matches(doc, query):
        for key, value in query.items():
            if key == "$or":
                if not any(FakeCollection.matches(doc, clause) for clause in value):
                    return False
            elif doc.get(key) != value:
                return False
        return True

    async def find_one(self, query, projection=None, sort=None, session=None):
        found = [d for d in self.docs if self.matches(d, query)]
        if sort:
            field, direction = sort[0]
            found.sort(key=lambda d: d.get(field, ""), reverse=direction < 0)
        return copy.deepcopy(found[0]) if found else None

    async def insert_one(self, doc, session=None):
        if self.name == "lynk_orders" and self.database.fail_order_insert:
            raise PyMongoError("synthetic order failure")
        if self.name == "licenses" and self.database.fail_license_insert:
            raise PyMongoError("synthetic license failure")
        if self.name == "lynk_orders" and any(d["ref_id"] == doc["ref_id"] for d in self.docs):
            raise DuplicateKeyError("synthetic unique ref_id")
        self.docs.append(copy.deepcopy(doc))

    async def update_one(self, query, update, upsert=False, session=None):
        if self.name == "licenses" and self.database.fail_license_update:
            raise PyMongoError("synthetic license update failure")
        doc = next((d for d in self.docs if self.matches(d, query)), None)
        if doc is None and upsert:
            doc = copy.deepcopy(query)
            self.docs.append(doc)
        if doc is not None:
            doc.update(copy.deepcopy(update.get("$set", {})))
        return types.SimpleNamespace(matched_count=int(doc is not None))


class FakeTransaction:
    def __init__(self, database):
        self.database = database

    async def __aenter__(self):
        await self.database.lock.acquire()
        self.before = copy.deepcopy(self.database.data)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type:
            self.database.data.clear()
            self.database.data.update(self.before)
        self.database.lock.release()


class FakeSession:
    def __init__(self, database):
        self.database = database

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def start_transaction(self):
        return FakeTransaction(self.database)


class FakeDB:
    NAMES = ("settings", "members", "licenses", "lynk_orders", "lynk_email_locks", "webhook_logs")

    def __init__(self):
        self.data = {name: [] for name in self.NAMES}
        self.data["settings"].append({"key": "lynk", "merchant_key": "offline-fixture-key"})
        self.lock = asyncio.Lock()
        self.fail_order_insert = False
        self.fail_license_insert = False
        self.fail_license_update = False
        self.client = self
        for name in self.NAMES:
            setattr(self, name, FakeCollection(self, name))

    async def start_session(self):
        return FakeSession(self)


class FakeRequest:
    def __init__(self, body, signature=None):
        self.payload = json.dumps(body).encode()
        self.headers = {"X-Lynk-Signature": signature} if signature is not None else {}

    async def body(self):
        return self.payload


def make_request(body, signature=None):
    return FakeRequest(body, signature)


def payload(ref="synthetic-ref-1", email="buyer@example.test", title="SAMPE - System Analytic Marketplace"):
    return {"event": "payment.received", "data": {
        "message_id": "synthetic-message-1", "message_action": "SUCCESS", "message_code": 0,
        "message_data": {"refId": ref, "customer": {"email": email, "name": "Synthetic Buyer"},
                         "items": [{"title": title, "qty": 1}],
                         "totals": {"totalPrice": 20000, "discount": -20000, "customerPay": 0, "grandTotal": 0},
                         "voucherCode": "DINSKON100"}}}


def fixture_signature(body):
    data = body["data"]
    md = data["message_data"]
    text = f"{md['totals']['grandTotal']}{md['refId']}{data['message_id']}offline-fixture-key"
    return hashlib.sha256(text.encode()).hexdigest()


def send(module, body, signature="valid"):
    if signature == "valid":
        signature = fixture_signature(body)
    return module.lynk_webhook(make_request(body, signature))


class LynkOfflineTests(unittest.TestCase):
    def setUp(self):
        self.database = FakeDB()
        self.previous_modules = {name: sys.modules.get(name) for name in
                                 ("core", "auth", "fastapi", "pydantic", "pymongo", "pymongo.errors")}
        fastapi = types.ModuleType("fastapi")
        fastapi.APIRouter = FakeRouter
        fastapi.Depends = lambda dependency: None
        fastapi.HTTPException = HTTPException
        fastapi.Request = FakeRequest
        pydantic = types.ModuleType("pydantic")
        pydantic.BaseModel = BaseModel
        pydantic.Field = lambda **kwargs: None
        pymongo = types.ModuleType("pymongo")
        errors = types.ModuleType("pymongo.errors")
        errors.DuplicateKeyError = DuplicateKeyError
        errors.PyMongoError = PyMongoError
        pymongo.errors = errors
        core = types.ModuleType("core")
        core.db = self.database
        auth = types.ModuleType("auth")
        auth.get_admin = lambda: {"role": "admin"}
        auth.new_license = lambda name, days, email, source: {
            "id": f"license-{len(self.database.data['licenses']) + 1}", "name": name, "email": email,
            "duration_days": days, "source": source, "revoked": False,
            "activated_at": None, "expires_at": None, "created_at": "2026-01-01T00:00:00+00:00"}
        async def new_code():
            return f"SAMPE-TEST-{len(self.database.data['licenses']) + 1:04d}"
        async def noop(*args, **kwargs):
            return None
        auth.new_code = new_code
        auth.public_license = lambda lic: lic
        auth.license_status = lambda lic: "pending" if lic["activated_at"] is None else "active"
        auth.check_lock = noop
        auth.record_fail = noop
        auth.client_ip = lambda request: "127.0.0.1"
        sys.modules.update({"core": core, "auth": auth, "fastapi": fastapi, "pydantic": pydantic,
                            "pymongo": pymongo, "pymongo.errors": errors})
        spec = importlib.util.spec_from_file_location("sampe_lynk_offline", Path(__file__).parents[1] / "lynk.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def tearDown(self):
        for name, previous in self.previous_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous

    def run_webhook(self, body, signature="valid"):
        return asyncio.run(send(self.module, body, signature))

    def activated_license(self, email="buyer@example.test", ref="synthetic-ref-1", expired=False):
        self.run_webhook(payload(ref=ref, email=email))
        lic = next(lic for lic in self.database.data["licenses"] if lic["email"] == email)
        now = datetime.now(timezone.utc)
        lic["activated_at"] = (now - timedelta(days=3) if expired else now - timedelta(hours=1)).isoformat()
        lic["expires_at"] = (now - timedelta(days=2) if expired else now + timedelta(hours=23)).isoformat()
        return lic

    def test_fixture_signature_and_zero_grand_total(self):
        body = payload()
        result = self.run_webhook(body)
        self.assertTrue(result["processed"])
        self.assertEqual(result["status"], "processed")
        self.assertEqual(len(self.database.data["lynk_orders"]), 1)
        self.assertEqual(len(self.database.data["licenses"]), 1)
        lic = self.database.data["licenses"][0]
        self.assertEqual(lic["duration_days"], 1)
        self.assertIsNone(lic["activated_at"])
        self.assertIsNone(lic["expires_at"])
        self.assertEqual(self.database.data["lynk_orders"][0]["license_id"], lic["id"])

    def test_four_named_sampe_packages_grant_their_own_duration(self):
        packages = (
            ("SAMPE - System Analytic Marketplace", 1),
            ("SAMPE - System Analytic Marketplace (7 Hari)", 7),
            ("SAMPE - System Analytic Marketplace (30 Hari)", 30),
            ("SAMPE - System Analytic Marketplace (365 Hari)", 365),
        )
        for title, days in packages:
            with self.subTest(title=title):
                ref = f"synthetic-ref-{days}"
                result = self.run_webhook(payload(ref=ref, email=f"buyer{days}@example.test", title=title))
                self.assertTrue(result["processed"])
                order = next(order for order in self.database.data["lynk_orders"] if order["ref_id"] == ref)
                lic = next(lic for lic in self.database.data["licenses"] if lic["id"] == order["license_id"])
                self.assertEqual(order["days"], days)
                self.assertEqual(lic["duration_days"], days)
                self.assertIsNone(lic["activated_at"])
                lookup = self.module.ActivationIn(email=f"buyer{days}@example.test", ref_id=ref)
                found = asyncio.run(self.module.activation_lookup(lookup, make_request(payload())))
                self.assertEqual(found["days"], days)
                self.assertEqual(found["duration_days"], days)
        self.assertEqual(len(self.database.data["lynk_orders"]), 4)
        self.assertEqual(len(self.database.data["licenses"]), 4)

    def test_nonzero_grand_total_creates_license(self):
        body = payload(title="SAMPE - System Analytic Marketplace (30 Hari)")
        totals = body["data"]["message_data"]["totals"]
        totals.update({"discount": 0, "customerPay": 20000, "grandTotal": 20000})
        result = self.run_webhook(body)
        self.assertTrue(result["processed"])
        self.assertEqual(len(self.database.data["lynk_orders"]), 1)
        self.assertEqual(len(self.database.data["licenses"]), 1)
        self.assertEqual(self.database.data["licenses"][0]["duration_days"], 30)

    def test_malformed_json_creates_nothing(self):
        request = make_request(payload())
        request.payload = b"{not-json"
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(self.module.lynk_webhook(request))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertFalse(self.database.data["lynk_orders"])
        self.assertFalse(self.database.data["licenses"])

    def test_missing_required_fields_create_nothing(self):
        for field in ("refId", "email", "message_id", "grandTotal"):
            with self.subTest(field=field):
                body = payload()
                data = body["data"]
                md = data["message_data"]
                if field == "email":
                    del md["customer"]["email"]
                elif field == "message_id":
                    del data[field]
                elif field == "grandTotal":
                    del md["totals"][field]
                else:
                    del md[field]
                with self.assertRaises(HTTPException) as ctx:
                    self.run_webhook(body, "synthetic-signature")
                self.assertEqual(ctx.exception.status_code, 400)
                self.assertFalse(self.database.data["lynk_orders"])
                self.assertFalse(self.database.data["licenses"])

    def test_invalid_buyer_email_creates_nothing(self):
        for email in ("not-an-email", "buyer@@example.test", "buyer@bad domain.test", "buyer@.test",
                      ".buyer@example.test", "buyer..tag@example.test", "buyer@example..test"):
            with self.subTest(email=email):
                with self.assertRaises(HTTPException) as ctx:
                    self.run_webhook(payload(email=email), "synthetic-signature")
                self.assertEqual(ctx.exception.status_code, 400)
                self.assertFalse(self.database.data["lynk_orders"])
                self.assertFalse(self.database.data["licenses"])

    def test_valid_tagged_buyer_email_creates_license(self):
        result = self.run_webhook(payload(email="Buyer+tag@Example.test"))
        self.assertTrue(result["processed"])
        self.assertEqual(self.database.data["licenses"][0]["email"], "buyer+tag@example.test")

    def test_wrong_signature_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            self.run_webhook(payload(), "bad-signature")
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertFalse(self.database.data["licenses"])

    def test_missing_signature_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            self.run_webhook(payload(), None)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertFalse(self.database.data["licenses"])

    def test_legacy_header_rejected(self):
        body = payload()
        request = make_request(body)
        request.headers["X-Signature"] = fixture_signature(body)
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(self.module.lynk_webhook(request))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_invalid_event_status_and_code_never_grant(self):
        for field, value in (("event", "refund.received"), ("message_action", "FAILED"), ("message_code", 1)):
            with self.subTest(field=field):
                body = payload(ref=f"synthetic-{field}")
                if field == "event":
                    body[field] = value
                else:
                    body["data"][field] = value
                result = self.run_webhook(body)
                self.assertFalse(result["processed"])
                self.assertFalse(self.database.data["licenses"])
                self.assertFalse(self.database.data["lynk_orders"])

    def test_unknown_product_has_no_license(self):
        result = self.run_webhook(payload(title="Unrelated digital product"))
        self.assertEqual(result["status"], "unmatched")
        self.assertEqual(len(self.database.data["lynk_orders"]), 1)
        self.assertFalse(self.database.data["licenses"])

    def test_other_product_with_duration_text_has_no_license(self):
        result = self.run_webhook(payload(title="Unrelated product 30 Hari"))
        self.assertEqual(result["status"], "unmatched")
        self.assertEqual(len(self.database.data["lynk_orders"]), 1)
        self.assertFalse(self.database.data["licenses"])

    def test_unlisted_sampe_package_has_no_license(self):
        result = self.run_webhook(payload(title="SAMPE - System Analytic Marketplace (14 Hari)"))
        self.assertEqual(result["status"], "unmatched")
        self.assertFalse(self.database.data["licenses"])

    def test_mixed_cart_only_counts_sampe_product(self):
        body = payload()
        body["data"]["message_data"]["items"].append({"title": "Unrelated product 30 Hari", "qty": 1})
        result = self.run_webhook(body)
        self.assertTrue(result["processed"])
        self.assertEqual(self.database.data["licenses"][0]["duration_days"], 1)

    def test_same_ref_retry_is_idempotent(self):
        body = payload()
        self.assertTrue(self.run_webhook(body)["processed"])
        self.assertTrue(self.run_webhook(body)["duplicate"])
        self.assertEqual(len(self.database.data["lynk_orders"]), 1)
        self.assertEqual(len(self.database.data["licenses"]), 1)

    def test_parallel_same_ref_is_idempotent(self):
        body = payload()
        async def run():
            return await asyncio.gather(*(send(self.module, body) for _ in range(12)))
        results = asyncio.run(run())
        self.assertEqual(sum(r.get("duplicate", False) for r in results), 11)
        self.assertEqual(len(self.database.data["lynk_orders"]), 1)
        self.assertEqual(len(self.database.data["licenses"]), 1)

    def test_activation_lookup_finds_email_and_ref(self):
        body = payload()
        self.run_webhook(body)
        lookup = self.module.ActivationIn(email="buyer@example.test", ref_id="synthetic-ref-1")
        result = asyncio.run(self.module.activation_lookup(lookup, make_request(body)))
        self.assertEqual(result["code"], self.database.data["licenses"][0]["code"])
        self.assertEqual(result["days"], 1)
        wrong = self.module.ActivationIn(email="other@example.test", ref_id="synthetic-ref-1")
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(self.module.activation_lookup(wrong, make_request(body)))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_missing_linked_license_returns_409(self):
        body = payload()
        self.run_webhook(body)
        self.database.data["licenses"].clear()
        lookup = self.module.ActivationIn(email="buyer@example.test", ref_id="synthetic-ref-1")
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(self.module.activation_lookup(lookup, make_request(body)))
        self.assertEqual(ctx.exception.status_code, 409)

    def test_partial_failure_rolls_back_order_and_license(self):
        self.database.fail_order_insert = True
        with self.assertRaises(HTTPException) as ctx:
            self.run_webhook(payload())
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertFalse(self.database.data["lynk_orders"])
        self.assertFalse(self.database.data["licenses"])

    def test_license_insert_failure_rolls_back_order(self):
        self.database.fail_license_insert = True
        with self.assertRaises(HTTPException) as ctx:
            self.run_webhook(payload())
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertFalse(self.database.data["lynk_orders"])
        self.assertFalse(self.database.data["licenses"])

    def test_repeat_unactivated_sampe_purchase_waits_for_owner_policy(self):
        self.run_webhook(payload())
        first = copy.deepcopy(self.database.data["licenses"][0])
        result = self.run_webhook(payload(ref="synthetic-ref-2"))
        self.assertEqual(result["status"], "pending_policy")
        self.assertEqual(len(self.database.data["lynk_orders"]), 2)
        self.assertEqual(len(self.database.data["licenses"]), 1)
        self.assertEqual(self.database.data["licenses"][0], first)

    def test_active_renewal_for_all_four_packages_keeps_code(self):
        packages = (
            ("SAMPE - System Analytic Marketplace", 1),
            ("SAMPE - System Analytic Marketplace (7 Hari)", 7),
            ("SAMPE - System Analytic Marketplace (30 Hari)", 30),
            ("SAMPE - System Analytic Marketplace (365 Hari)", 365),
        )
        for title, days in packages:
            with self.subTest(title=title):
                email = f"renew{days}@example.test"
                lic = self.activated_license(email=email, ref=f"first-{days}")
                old_id, old_code = lic["id"], lic["code"]
                old_expiry = datetime.fromisoformat(lic["expires_at"])
                ref = f"renew-{days}"
                result = self.run_webhook(payload(ref=ref, email=email, title=title))
                self.assertTrue(result["processed"])
                self.assertEqual(result["action"], "extended")
                order = next(order for order in self.database.data["lynk_orders"] if order["ref_id"] == ref)
                self.assertEqual(order["license_id"], old_id)
                self.assertEqual(order["days"], days)
                self.assertEqual(datetime.fromisoformat(lic["expires_at"]), old_expiry + timedelta(days=days))
                self.assertEqual(lic["code"], old_code)
                self.assertEqual(sum(item["email"] == email for item in self.database.data["licenses"]), 1)
                lookup = self.module.ActivationIn(email=email, ref_id=ref)
                found = asyncio.run(self.module.activation_lookup(lookup, make_request(payload())))
                self.assertEqual(found["code"], old_code)
                self.assertEqual(found["expires_at"], lic["expires_at"])

    def test_expired_renewal_starts_at_successful_processing_time(self):
        lic = self.activated_license(expired=True)
        old_id, old_code = lic["id"], lic["code"]
        before = datetime.now(timezone.utc)
        result = self.run_webhook(payload(ref="synthetic-ref-renew", title="SAMPE - System Analytic Marketplace (7 Hari)"))
        after = datetime.now(timezone.utc)
        self.assertEqual(result["action"], "extended")
        self.assertEqual(self.database.data["lynk_orders"][-1]["license_id"], old_id)
        self.assertEqual(lic["code"], old_code)
        new_expiry = datetime.fromisoformat(lic["expires_at"])
        self.assertLessEqual(before + timedelta(days=7), new_expiry)
        self.assertLessEqual(new_expiry, after + timedelta(days=7))
        self.assertEqual(len(self.database.data["licenses"]), 1)

    def test_retry_renewal_does_not_extend_twice(self):
        lic = self.activated_license()
        body = payload(ref="synthetic-ref-renew", title="SAMPE - System Analytic Marketplace (30 Hari)")
        self.assertEqual(self.run_webhook(body)["action"], "extended")
        first_expiry = lic["expires_at"]
        self.assertTrue(self.run_webhook(body)["duplicate"])
        self.assertEqual(lic["expires_at"], first_expiry)
        self.assertEqual(len(self.database.data["lynk_orders"]), 2)
        self.assertEqual(len(self.database.data["licenses"]), 1)

    def test_two_distinct_renewals_extend_once_each(self):
        lic = self.activated_license()
        old_expiry = datetime.fromisoformat(lic["expires_at"])
        first = payload(ref="synthetic-ref-renew-1")
        second = payload(ref="synthetic-ref-renew-7", title="SAMPE - System Analytic Marketplace (7 Hari)")
        async def run():
            return await asyncio.gather(send(self.module, first), send(self.module, second))
        results = asyncio.run(run())
        self.assertTrue(all(result["processed"] for result in results))
        self.assertEqual(datetime.fromisoformat(lic["expires_at"]), old_expiry + timedelta(days=8))
        self.assertEqual(len(self.database.data["lynk_orders"]), 3)
        self.assertEqual(len(self.database.data["licenses"]), 1)

    def test_failed_order_insert_rolls_back_renewal(self):
        lic = self.activated_license()
        old_expiry = lic["expires_at"]
        self.database.fail_order_insert = True
        body = payload(ref="synthetic-ref-renew", title="SAMPE - System Analytic Marketplace (7 Hari)")
        with self.assertRaises(HTTPException) as ctx:
            self.run_webhook(body)
        self.assertEqual(ctx.exception.status_code, 503)
        stored = next(item for item in self.database.data["licenses"] if item["id"] == lic["id"])
        self.assertEqual(stored["expires_at"], old_expiry)
        self.assertEqual(len(self.database.data["lynk_orders"]), 1)
        self.database.fail_order_insert = False
        self.assertEqual(self.run_webhook(body)["action"], "extended")
        stored = next(item for item in self.database.data["licenses"] if item["id"] == lic["id"])
        self.assertEqual(datetime.fromisoformat(stored["expires_at"]), datetime.fromisoformat(old_expiry) + timedelta(days=7))

    def test_failed_license_update_leaves_no_renewal_order(self):
        lic = self.activated_license()
        old_expiry = lic["expires_at"]
        self.database.fail_license_update = True
        with self.assertRaises(HTTPException) as ctx:
            self.run_webhook(payload(ref="synthetic-ref-renew"))
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(lic["expires_at"], old_expiry)
        self.assertEqual(len(self.database.data["lynk_orders"]), 1)

    def test_other_buyer_does_not_extend_first_buyers_license(self):
        first = self.activated_license()
        old_expiry = first["expires_at"]
        result = self.run_webhook(payload(ref="other-buyer-ref", email="other@example.test"))
        self.assertEqual(result["action"], "created")
        self.assertEqual(first["expires_at"], old_expiry)
        self.assertEqual(len(self.database.data["licenses"]), 2)

    def test_invalid_signature_does_not_renew(self):
        lic = self.activated_license()
        old_expiry = lic["expires_at"]
        with self.assertRaises(HTTPException) as ctx:
            self.run_webhook(payload(ref="synthetic-ref-renew"), "bad-signature")
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(lic["expires_at"], old_expiry)
        self.assertEqual(len(self.database.data["lynk_orders"]), 1)

    def test_pending_policy_lookup_returns_409(self):
        self.run_webhook(payload())
        self.run_webhook(payload(ref="synthetic-ref-2"))
        lookup = self.module.ActivationIn(email="buyer@example.test", ref_id="synthetic-ref-2")
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(self.module.activation_lookup(lookup, make_request(payload())))
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("pembelian ulang", ctx.exception.detail)

    def test_logs_do_not_store_raw_payload_or_signature(self):
        self.run_webhook(payload())
        log = self.database.data["webhook_logs"][0]
        self.assertIsNone(log["body"])
        self.assertNotIn("email", log)
        self.assertNotIn("signature", log)
        self.assertNotIn("buyer@example.test", json.dumps(log))

    def test_admin_reprocess_is_disabled(self):
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(self.module.reprocess_log("synthetic-time", {}))
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertFalse(self.database.data["licenses"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
