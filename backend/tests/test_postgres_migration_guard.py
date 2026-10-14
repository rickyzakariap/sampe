"""Offline safety checks for the separate PostgreSQL migration command."""

import importlib.util
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


POSTGRES_DIR = Path(__file__).parents[1] / "postgres"
spec = importlib.util.spec_from_file_location("sampe_pg_migrate", POSTGRES_DIR / "migrate.py")
migrate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migrate)


class MigrationGuardTests(unittest.TestCase):
    def test_postgres_configuration_cannot_silently_start_mongo(self):
        env = os.environ.copy()
        env.update({"SAMPE_DB_BACKEND": "mongo", "SAMPE_POSTGRES_ENV": "staging"})
        result = subprocess.run([sys.executable, "-c", "import core"], cwd=POSTGRES_DIR.parent,
                                env=env, text=True, capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PostgreSQL configuration is set", result.stderr)

    def test_only_an_exactly_confirmed_test_database_is_accepted(self):
        migrate.validate_test_target("testing", "sampe_test", "sampe_test")
        for env, actual, confirmed in (
            ("", "sampe_test", "sampe_test"),
            ("production", "sampe_test", "sampe_test"),
            ("testing", "sampe", "sampe"),
            ("testing", "sampe_test", "another_test"),
        ):
            with self.subTest(env=env, actual=actual, confirmed=confirmed):
                with self.assertRaises(RuntimeError):
                    migrate.validate_test_target(env, actual, confirmed)

    def test_every_forward_migration_has_a_rollback(self):
        self.assertEqual(migrate.migration_versions(), ["0001_initial"])

    def test_unlabeled_target_is_refused_before_driver_connection(self):
        with patch.dict("os.environ", {"SAMPE_POSTGRES_DSN": "unused", "SAMPE_POSTGRES_ENV": "production"}):
            with self.assertRaises(RuntimeError):
                migrate.migrate("up", "sampe_test")

    def test_staging_up_requires_exact_target_and_down_is_refused(self):
        migrate.validate_migration_target("up", "staging", "sampe_staging", "sampe_staging", "sampe_staging")
        for direction, actual, confirmed, configured in (
            ("down", "sampe_staging", "sampe_staging", "sampe_staging"),
            ("up", "sampe_staging", "sampe_staging", None),
            ("up", "sampe_staging", "other_staging", "other_staging"),
            ("up", "sampe", "sampe", "sampe"),
        ):
            with self.subTest(direction=direction, actual=actual):
                with self.assertRaises(RuntimeError):
                    migrate.validate_migration_target(direction, "staging", actual, confirmed, configured)

    def test_production_up_requires_explicit_flag_and_exact_non_test_target(self):
        migrate.validate_migration_target("up", "production", "satsetdi_sampe", "satsetdi_sampe",
                                          "satsetdi_sampe", True)
        for direction, actual, confirmed, configured, allowed in (
            ("up", "satsetdi_sampe", "satsetdi_sampe", "satsetdi_sampe", False),
            ("down", "satsetdi_sampe", "satsetdi_sampe", "satsetdi_sampe", True),
            ("up", "sampe_test", "sampe_test", "sampe_test", True),
            ("up", "other_sampe", "satsetdi_sampe", "satsetdi_sampe", True),
        ):
            with self.subTest(direction=direction, actual=actual, allowed=allowed):
                with self.assertRaises(RuntimeError):
                    migrate.validate_migration_target(direction, "production", actual, confirmed,
                                                      configured, allowed)

    def test_all_created_tables_are_named_in_rollback(self):
        up = (POSTGRES_DIR / "migrations" / "0001_initial.up.sql").read_text(encoding="utf-8")
        down = (POSTGRES_DIR / "migrations" / "0001_initial.down.sql").read_text(encoding="utf-8")
        created = set(re.findall(r"CREATE TABLE sampe\.([a-z_]+)", up))
        dropped = set(re.findall(r"DROP TABLE sampe\.([a-z_]+)", down))
        self.assertEqual(len(created), 11)
        self.assertEqual(created, dropped)


if __name__ == "__main__":
    unittest.main()
