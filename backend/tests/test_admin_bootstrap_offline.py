"""Offline checks for first-admin provisioning; no database connection is opened."""

import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

def run_without_io(coroutine):
    """Drive fake-only async methods without opening a Windows event loop."""
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    raise AssertionError("Unexpected external I/O in offline bootstrap test")


class Collection:
    def __init__(self):
        self.admin = None

    async def create_index(self, *args, **kwargs):
        return None

    async def find_one(self, query):
        return self.admin if query == {"role": "admin"} else None


class Database:
    def __init__(self):
        for name in ("users", "members", "user_sessions", "licenses", "lynk_orders",
                     "login_attempts", "kpi_config", "entries"):
            setattr(self, name, Collection())
        self.created = []

    async def bootstrap_admin(self, email, password_hash, admin_id, created_at):
        self.created.append((email, password_hash))
        self.users.admin = {"id": admin_id, "role": "admin"}
        return True


class AdminBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        backend = Path(__file__).parents[1]
        sys.path.insert(0, str(backend))
        spec = importlib.util.spec_from_file_location("sampe_admin_bootstrap_test_auth", backend / "auth.py")
        self.auth = importlib.util.module_from_spec(spec)
        fake_bcrypt = types.SimpleNamespace(
            gensalt=lambda: b"synthetic-salt",
            hashpw=lambda password, salt: b"synthetic-hash-" + password,
            checkpw=lambda password, hashed: hashed == b"synthetic-hash-" + password,
        )
        with patch.dict(sys.modules, {"core": types.SimpleNamespace(db=self.db, DB_BACKEND="postgres"),
                                      "bcrypt": fake_bcrypt}):
            spec.loader.exec_module(self.auth)

    def test_creates_once_and_does_not_rotate_on_restart(self):
        with patch.dict(os.environ, {"ADMIN_EMAIL": "new-admin@example.test", "ADMIN_PASSWORD": "synthetic-private-password"}):
            run_without_io(self.auth.init_auth())
        self.assertEqual(len(self.db.created), 1)
        self.assertEqual(self.db.created[0][0], "new-admin@example.test")
        self.assertNotEqual(self.db.created[0][1], "synthetic-private-password")
        with patch.dict(os.environ, {"ADMIN_EMAIL": "other@example.test", "ADMIN_PASSWORD": "other-private-password"}):
            run_without_io(self.auth.init_auth())
        self.assertEqual(len(self.db.created), 1)

    def test_missing_credentials_fail_on_empty_database(self):
        with patch.dict(os.environ, {"ADMIN_EMAIL": "", "ADMIN_PASSWORD": ""}):
            with self.assertRaisesRegex(RuntimeError, "First admin requires"):
                run_without_io(self.auth.init_auth())
        self.assertEqual(self.db.created, [])


if __name__ == "__main__":
    unittest.main()
