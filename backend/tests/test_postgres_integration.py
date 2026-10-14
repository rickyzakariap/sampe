"""Integration checks for an explicitly named, isolated SAMPE PostgreSQL test DB.

Every inserted fixture is rolled back after its test. The suite skips when the
test connection variables are absent, so MongoDB runtime tests stay offline.
"""

import importlib.util
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path


MIGRATE_PATH = Path(__file__).parents[1] / "postgres" / "migrate.py"
spec = importlib.util.spec_from_file_location("sampe_pg_migrate_integration", MIGRATE_PATH)
migrate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migrate)


class PostgresIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ.get("SAMPE_POSTGRES_DSN")
        cls.confirmed_database = os.environ.get("SAMPE_POSTGRES_TEST_DB")
        if not cls.dsn or not cls.confirmed_database:
            raise unittest.SkipTest("isolated PostgreSQL test connection not configured")
        migrate.validate_test_target(
            os.environ.get("SAMPE_POSTGRES_ENV", ""), cls.confirmed_database, cls.confirmed_database
        )
        import psycopg
        cls.psycopg = psycopg

    def setUp(self):
        self.conn = self.psycopg.connect(self.dsn, connect_timeout=5)
        actual_database = self.conn.execute("SELECT current_database()").fetchone()[0]
        try:
            migrate.validate_test_target(
                os.environ.get("SAMPE_POSTGRES_ENV", ""), actual_database, self.confirmed_database
            )
        except Exception:
            self.conn.close()
            raise

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def insert_fixture(self):
        now = datetime.now(timezone.utc)
        self.conn.execute(
            "INSERT INTO sampe.members (user_id, email, created_at) VALUES (%s, %s, %s)",
            ("synthetic-user", "synthetic@example.test", now),
        )
        self.conn.execute(
            """INSERT INTO sampe.licenses
               (id, code, label, email, source, duration_days, created_at, owner_user_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            ("synthetic-license", "SAMPE-SYNTHETIC", "Synthetic", "synthetic@example.test",
             "lynk", 30, now, "synthetic-user"),
        )
        self.conn.execute(
            """INSERT INTO sampe.lynk_orders
               (ref_id, message_id, email, product, days, created_at, license_id, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            ("synthetic-ref", "synthetic-message", "synthetic@example.test", "Synthetic SAMPE", 30,
             now, "synthetic-license", "processed"),
        )
        self.conn.execute(
            """INSERT INTO sampe.kpi_config
               (id, tenant_id, company_name, month, created_at)
               VALUES (%s, %s, %s, %s, %s)""",
            ("synthetic-config", "synthetic-license", "Synthetic Company", "2026-10", now),
        )
        self.conn.execute(
            """INSERT INTO sampe.entries
               (id, tenant_id, module, date, data, created_at)
               VALUES (%s, %s, %s, %s, %s::jsonb, %s)""",
            ("synthetic-entry", "synthetic-license", "sales", "2026-10-14", '{"sales": 100}', now),
        )
        return now

    def test_eleven_tables_keys_indexes_and_types(self):
        tables = {row[0] for row in self.conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'sampe'"
        )}
        expected = {"users", "members", "user_sessions", "licenses", "lynk_orders",
                    "login_attempts", "kpi_config", "entries", "settings",
                    "lynk_email_locks", "webhook_logs"}
        self.assertEqual(tables, expected)

        constraints = list(self.conn.execute("""
            SELECT rel.relname, con.contype, con.conname,
                   CASE WHEN con.contype = 'f' THEN con.confrelid::regclass::text ELSE NULL END
              FROM pg_constraint con
              JOIN pg_class rel ON rel.oid = con.conrelid
             WHERE con.connamespace = 'sampe'::regnamespace
        """))
        self.assertEqual({table for table, kind, _, _ in constraints if kind == "p"}, expected)
        foreign_keys = {(table, target) for table, kind, _, target in constraints if kind == "f"}
        self.assertEqual(foreign_keys, {
            ("user_sessions", "sampe.members"), ("licenses", "sampe.members"),
            ("lynk_orders", "sampe.licenses"), ("kpi_config", "sampe.licenses"),
            ("entries", "sampe.licenses"),
        })
        indexes = {row[0] for row in self.conn.execute(
            "SELECT indexname FROM pg_indexes WHERE schemaname = 'sampe'"
        )}
        self.assertTrue({
            "users_email_key", "members_email_key", "user_sessions_pkey",
            "licenses_code_unique_idx", "lynk_orders_pkey", "kpi_config_tenant_month_unique",
            "user_sessions_expires_at_idx", "user_sessions_user_id_idx",
            "licenses_email_created_idx", "licenses_owner_created_idx",
            "lynk_orders_email_created_idx", "lynk_orders_license_id_idx",
            "login_attempts_identifier_idx", "kpi_config_tenant_month_desc_idx",
            "entries_tenant_date_idx", "entries_tenant_module_date_idx",
            "webhook_logs_received_at_idx", "webhook_logs_ref_id_idx",
        } <= indexes)
        types = {(table, column): data_type for table, column, data_type in self.conn.execute("""
            SELECT table_name, column_name, data_type
              FROM information_schema.columns WHERE table_schema = 'sampe'
        """)}
        self.assertEqual(types["entries", "data"], "jsonb")
        self.assertEqual(types["settings", "extra"], "jsonb")
        self.assertEqual(types["webhook_logs", "body"], "jsonb")
        self.assertEqual(types["entries", "date"], "date")
        self.assertEqual(types["licenses", "expires_at"], "timestamp with time zone")
        self.assertEqual(types["kpi_config", "target_sales"], "numeric")

    def test_synthetic_account_license_order_and_kpi_join(self):
        self.insert_fixture()
        row = self.conn.execute("""
            SELECT o.ref_id, m.user_id, l.id, c.id, e.data->>'sales'
              FROM sampe.lynk_orders o
              JOIN sampe.licenses l ON l.id = o.license_id
              JOIN sampe.members m ON m.user_id = l.owner_user_id
              JOIN sampe.kpi_config c ON c.tenant_id = l.id
              JOIN sampe.entries e ON e.tenant_id = l.id
             WHERE o.ref_id = 'synthetic-ref'
        """).fetchone()
        self.assertEqual(row, ("synthetic-ref", "synthetic-user", "synthetic-license",
                               "synthetic-config", "100"))

    def test_unique_foreign_key_and_check_constraints_reject_bad_rows(self):
        now = self.insert_fixture()
        cases = (
            (self.psycopg.errors.UniqueViolation,
             "INSERT INTO sampe.lynk_orders (ref_id, message_id, email, product, days, created_at, status) "
             "VALUES (%s, %s, %s, %s, %s, %s, %s)",
             ("synthetic-ref", "other-message", "synthetic@example.test", "Synthetic", 1, now, "processed")),
            (self.psycopg.errors.UniqueViolation,
             "INSERT INTO sampe.licenses (id, code, label, source, duration_days, created_at) "
             "VALUES (%s, %s, %s, %s, %s, %s)",
             ("other-license", "SAMPE-SYNTHETIC", "Synthetic", "lynk", 1, now)),
            (self.psycopg.errors.ForeignKeyViolation,
             "INSERT INTO sampe.lynk_orders (ref_id, message_id, email, product, days, created_at, license_id, status) "
             "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
             ("other-ref", "other-message", "synthetic@example.test", "Synthetic", 1, now,
              "missing-license", "processed")),
            (self.psycopg.errors.UniqueViolation,
             "INSERT INTO sampe.kpi_config (id, tenant_id, company_name, month, created_at) "
             "VALUES (%s, %s, %s, %s, %s)",
             ("other-config", "synthetic-license", "Synthetic", "2026-10", now)),
            (self.psycopg.errors.CheckViolation,
             "INSERT INTO sampe.licenses (id, label, source, duration_days, created_at) "
             "VALUES (%s, %s, %s, %s, %s)",
             ("zero-license", "Synthetic", "lynk", 0, now)),
            (self.psycopg.errors.CheckViolation,
             "INSERT INTO sampe.entries (id, tenant_id, module, date, data, created_at) "
             "VALUES (%s, %s, %s, %s, %s::jsonb, %s)",
             ("bad-entry", "synthetic-license", "sales", "2026-10-14", "[]", now)),
        )
        for error, sql, params in cases:
            with self.subTest(error=error.__name__, sql=sql[:45]):
                with self.assertRaises(error):
                    with self.conn.transaction():
                        self.conn.execute(sql, params)


if __name__ == "__main__":
    unittest.main()
