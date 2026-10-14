"""Apply SAMPE schema migrations to an explicitly named database.

This module is deliberately not imported by the MongoDB application runtime.
"""

import argparse
import os
import re
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def migration_versions() -> list[str]:
    versions = sorted(path.name.removesuffix(".up.sql") for path in MIGRATIONS_DIR.glob("*.up.sql"))
    for version in versions:
        if not (MIGRATIONS_DIR / f"{version}.down.sql").is_file():
            raise RuntimeError(f"Rollback file missing for migration {version}")
    return versions


def validate_test_target(environment: str, actual_database: str, confirmed_database: str) -> None:
    if environment != "testing":
        raise RuntimeError("SAMPE_POSTGRES_ENV must be 'testing' for this migration runner")
    if actual_database != confirmed_database:
        raise RuntimeError("The connected database does not match --confirm-db")
    if not re.search(r"(^|[_-])test(ing)?($|[_-])", actual_database, re.IGNORECASE):
        raise RuntimeError("The database name must identify an isolated test database")


def validate_migration_target(direction: str, environment: str, actual_database: str,
                              confirmed_database: str, configured_database: str | None,
                              allow_production: bool = False) -> None:
    if environment == "testing":
        validate_test_target(environment, actual_database, confirmed_database)
        return
    if environment == "production":
        if (direction != "up" or not allow_production or not configured_database
                or actual_database != confirmed_database or configured_database != confirmed_database
                or re.search(r"(^|[_-])(test|testing|stag|staging)($|[_-])", actual_database, re.IGNORECASE)):
            raise RuntimeError("Production migration requires UP, --allow-production, and an exact non-test database target")
        return
    if direction != "up" or environment != "staging":
        raise RuntimeError("Only migration UP is allowed on staging; production is not supported by this runner")
    if not configured_database or configured_database != confirmed_database or actual_database != confirmed_database:
        raise RuntimeError("Staging database must match SAMPE_POSTGRES_TARGET_DB and --confirm-db")
    if not re.search(r"(^|[_-])stag(e|ing)?($|[_-])", actual_database, re.IGNORECASE):
        raise RuntimeError("The database name must identify an isolated staging database")


def migrate(direction: str, confirmed_database: str, allow_production: bool = False) -> None:
    dsn = os.environ.get("SAMPE_POSTGRES_DSN")
    if not dsn:
        raise RuntimeError("SAMPE_POSTGRES_DSN is required")
    environment = os.environ.get("SAMPE_POSTGRES_ENV", "")
    configured_database = os.environ.get("SAMPE_POSTGRES_TARGET_DB")
    # Refuse an unlabeled target before even opening a database connection.
    validate_migration_target(direction, environment, confirmed_database, confirmed_database,
                              configured_database, allow_production)
    versions = migration_versions()
    completed = []

    # Import only when the separate migration command is invoked. Existing MongoDB
    # runtime imports and dependencies remain unchanged.
    import psycopg

    with psycopg.connect(dsn, connect_timeout=5) as conn:
        with conn.transaction():
            actual_database = conn.execute("SELECT current_database()").fetchone()[0]
            validate_migration_target(direction, environment, actual_database, confirmed_database,
                                      configured_database, allow_production)
            conn.execute("SET LOCAL lock_timeout = '5s'")
            conn.execute("SET LOCAL statement_timeout = '30s'")
            conn.execute("SELECT pg_advisory_xact_lock(hashtext('sampe_schema_migrations'))")
            if environment == "production":
                existing_tables = conn.execute(
                    "SELECT 1 FROM pg_catalog.pg_tables "
                    "WHERE schemaname NOT IN ('pg_catalog', 'information_schema') LIMIT 1"
                ).fetchone()
                if existing_tables:
                    raise RuntimeError("Production migration requires an empty database")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS public.sampe_schema_migrations (
                    version text PRIMARY KEY,
                    applied_at timestamptz NOT NULL DEFAULT now()
                )
            """)
            applied = [row[0] for row in conn.execute(
                "SELECT version FROM public.sampe_schema_migrations ORDER BY version"
            ).fetchall()]
            if applied != versions[:len(applied)]:
                raise RuntimeError("Applied migration history does not match the files")

            if direction == "up":
                for version in versions[len(applied):]:
                    conn.execute((MIGRATIONS_DIR / f"{version}.up.sql").read_text(encoding="utf-8"))
                    conn.execute(
                        "INSERT INTO public.sampe_schema_migrations (version) VALUES (%s)",
                        (version,),
                    )
                    completed.append(f"Applied {version}")
            elif applied:
                version = applied[-1]
                conn.execute((MIGRATIONS_DIR / f"{version}.down.sql").read_text(encoding="utf-8"))
                conn.execute("DELETE FROM public.sampe_schema_migrations WHERE version = %s", (version,))
                completed.append(f"Rolled back {version}")
            else:
                completed.append("No migration to roll back")
    for message in completed:
        print(message)


def main() -> None:
    parser = argparse.ArgumentParser(description="SAMPE PostgreSQL schema migrations")
    parser.add_argument("direction", choices=("up", "down"))
    parser.add_argument("--confirm-db", required=True, help="Exact connected database name")
    parser.add_argument("--allow-production", action="store_true", help="Allow UP on an empty, exactly named production database")
    args = parser.parse_args()
    migrate(args.direction, args.confirm_db, args.allow_production)


if __name__ == "__main__":
    main()
