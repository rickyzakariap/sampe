"""PostgreSQL data access for the existing SAMPE FastAPI endpoint contracts.

This is deliberately a small, explicit adapter for the query shapes used by
SAMPE, not a general MongoDB emulator. Unknown fields/operators fail closed.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import os
import re

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


TABLES = {
    "users": ("id", {"id", "mongo_id", "email", "password_hash", "name", "role", "created_at"}),
    "members": ("user_id", {"user_id", "mongo_id", "email", "name", "picture", "created_at"}),
    "user_sessions": ("session_token", {"session_token", "mongo_id", "user_id", "expires_at", "created_at"}),
    "licenses": ("id", {"id", "mongo_id", "code", "label", "email", "source", "duration_days", "created_at", "activated_at", "expires_at", "last_login_at", "revoked", "owner_user_id", "lynk_ref_id"}),
    "lynk_orders": ("ref_id", {"ref_id", "mongo_id", "message_id", "email", "name", "phone", "product", "days", "created_at", "license_id", "action", "status"}),
    "login_attempts": ("id", {"id", "mongo_id", "identifier", "count", "locked_until"}),
    "kpi_config": ("id", {"id", "mongo_id", "tenant_id", "company_name", "month", "target_sales", "budget_ads", "budget_branding", "budget_campaign", "budget_kol", "target_kol_count", "live_team_count", "target_live_hours", "target_live_revenue", "created_at"}),
    "entries": ("id", {"id", "mongo_id", "tenant_id", "module", "date", "data", "created_at"}),
    "settings": ("key", {"key", "mongo_id", "merchant_key", "renew_url", "default_days", "extra"}),
    "lynk_email_locks": ("email", {"email", "touched_at"}),
    "webhook_logs": ("id", {"id", "mongo_id", "received_at", "status", "reason", "ref_id", "has_signature", "body"}),
}
JSON_FIELDS = {"data", "extra", "body"}


def _plain(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


@dataclass
class WriteResult:
    matched_count: int = 0
    deleted_count: int = 0
    inserted_id: object = None


class PgSession:
    def __init__(self, database):
        self.database = database
        self.conn = None

    async def __aenter__(self):
        self.conn = await self.database.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.conn.close()

    def start_transaction(self):
        return self.conn.transaction()


class PgClient:
    def __init__(self, database):
        self.database = database

    async def start_session(self):
        return PgSession(self.database)

    def close(self):
        pass


class PgCursor:
    def __init__(self, collection, query, projection):
        self.collection, self.query, self.projection = collection, query, projection
        self.order = None

    def sort(self, field, direction=None):
        self.order = [(field, direction)] if isinstance(field, str) else field
        return self

    async def to_list(self, length):
        return await self.collection._select(self.query, self.projection, self.order, length)


class PgCollection:
    def __init__(self, database, name):
        self.database, self.name = database, name
        self.pk, self.fields = TABLES[name]
        self.table = f"sampe.{name}"

    def _column(self, field):
        column = self.pk if field == "_id" else field
        if column not in self.fields:
            raise ValueError(f"Unsupported {self.name} field: {field}")
        return column

    def _where(self, query):
        parts, args = [], []
        for field, value in (query or {}).items():
            if field == "$or":
                clauses = [self._where(item) for item in value]
                if not clauses:
                    parts.append("FALSE")
                else:
                    parts.append("(" + " OR ".join(expr for expr, _ in clauses) + ")")
                    for _, values in clauses:
                        args.extend(values)
                continue
            column = self._column(field)
            if isinstance(value, dict):
                for operator, operand in value.items():
                    if operator == "$lte":
                        parts.append(f"{column} <= %s")
                        args.append(operand)
                    elif operator == "$in":
                        parts.append(f"{column} = ANY(%s)")
                        args.append(list(operand))
                    elif operator == "$regex" and isinstance(operand, str) and re.fullmatch(r"\^[0-9]{4}-[0-9]{2}", operand):
                        parts.append(f"{column}::text LIKE %s")
                        args.append(operand[1:] + "%")
                    else:
                        raise ValueError(f"Unsupported query operator: {operator}")
            elif value is None:
                parts.append(f"{column} IS NULL")
            else:
                parts.append(f"{column} = %s")
                args.append(value)
        return " AND ".join(parts) if parts else "TRUE", args

    def _order(self, sort):
        if not sort:
            return ""
        return " ORDER BY " + ", ".join(f"{self._column(field)} {'DESC' if direction == -1 else 'ASC'}" for field, direction in sort)

    def _project(self, row, projection):
        if row is None:
            return None
        result = _plain(dict(row))
        if projection is None or projection.get("_id") != 0:
            result["_id"] = result[self.pk]
        if projection:
            included = {key for key, enabled in projection.items() if enabled and key != "_id"}
            if included:
                result = {key: value for key, value in result.items() if key in included or (key == "_id" and projection.get("_id") != 0)}
            else:
                result = {key: value for key, value in result.items() if projection.get(key) != 0}
        return result

    async def _select(self, query, projection, sort, limit, session=None):
        where, args = self._where(query)
        sql = f"SELECT * FROM {self.table} WHERE {where}{self._order(sort)} LIMIT %s"
        args.append(limit)
        rows = await self.database.query(sql, args, session=session, all_rows=True)
        return [self._project(row, projection) for row in rows]

    async def find_one(self, query, projection=None, sort=None, session=None):
        rows = await self._select(query, projection, sort, 1, session)
        return rows[0] if rows else None

    def find(self, query=None, projection=None):
        return PgCursor(self, query, projection)

    def _insert_sql(self, document):
        fields = {self._column(key): value for key, value in document.items() if key != "_id"}
        if not fields:
            raise ValueError("Empty insert")
        keys = list(fields)
        args = [Jsonb(fields[key]) if key in JSON_FIELDS and fields[key] is not None else fields[key] for key in keys]
        sql = f"INSERT INTO {self.table} ({', '.join(keys)}) VALUES ({', '.join(['%s'] * len(keys))}) RETURNING {self.pk}"
        return sql, args

    async def insert_one(self, document, session=None):
        sql, args = self._insert_sql(document)
        row = await self.database.query(sql, args, session=session)
        return WriteResult(inserted_id=row[self.pk])

    async def insert_many(self, documents, session=None):
        for document in documents:
            await self.insert_one(document, session=session)

    def _update_sql(self, update):
        assignments, args = [], []
        for operator, fields in update.items():
            if operator not in ("$set", "$inc"):
                raise ValueError(f"Unsupported update operator: {operator}")
            for field, value in fields.items():
                column = self._column(field)
                if column == self.pk:
                    raise ValueError("Primary key update prohibited")
                if operator == "$set":
                    assignments.append(f"{column} = %s")
                    args.append(Jsonb(value) if column in JSON_FIELDS and value is not None else value)
                else:
                    assignments.append(f"{column} = COALESCE({column}, 0) + %s")
                    args.append(value)
        if not assignments:
            raise ValueError("Empty update")
        return ", ".join(assignments), args

    async def update_one(self, query, update, upsert=False, session=None):
        sets, values = self._update_sql(update)
        where, args = self._where(query)
        row = await self.database.query(f"UPDATE {self.table} SET {sets} WHERE {self.pk} = "
                                        f"(SELECT {self.pk} FROM {self.table} WHERE {where} LIMIT 1) RETURNING {self.pk}",
                                        values + args, session=session)
        if row:
            return WriteResult(matched_count=1)
        if not upsert:
            return WriteResult()
        doc = {key: value for key, value in query.items() if key != "$or" and not isinstance(value, dict)}
        doc.update(update.get("$set", {}))
        for key, delta in update.get("$inc", {}).items():
            doc[key] = delta
        if "_id" in doc:
            doc[self.pk] = doc.pop("_id")
        await self.insert_one(doc, session=session)
        return WriteResult()

    async def update_many(self, query, update, session=None):
        sets, values = self._update_sql(update)
        where, args = self._where(query)
        return await self.database.execute(f"UPDATE {self.table} SET {sets} WHERE {where}", values + args, session=session)

    async def find_one_and_update(self, query, update, upsert=False, return_document=None, session=None):
        await self.update_one(query, update, upsert=upsert, session=session)
        return await self.find_one(query, session=session)

    async def replace_one(self, query, document, session=None):
        pk_value = query.get("_id", query.get(self.pk))
        if pk_value is None:
            raise ValueError("Replacement requires primary key")
        fields = {self._column(key): value for key, value in document.items() if key != "_id" and self._column(key) != self.pk}
        sets = ", ".join(f"{key}=%s" for key in fields)
        args = [Jsonb(value) if key in JSON_FIELDS and value is not None else value for key, value in fields.items()]
        return await self.database.execute(f"UPDATE {self.table} SET {sets} WHERE {self.pk}=%s", args + [pk_value], session=session)

    async def delete_one(self, query, session=None):
        where, args = self._where(query)
        count = await self.database.execute(f"DELETE FROM {self.table} WHERE {self.pk} IN (SELECT {self.pk} FROM {self.table} WHERE {where} LIMIT 1)", args, session=session)
        return WriteResult(deleted_count=count)

    async def delete_many(self, query, session=None):
        where, args = self._where(query)
        count = await self.database.execute(f"DELETE FROM {self.table} WHERE {where}", args, session=session)
        return WriteResult(deleted_count=count)

    async def count_documents(self, query):
        where, args = self._where(query)
        row = await self.database.query(f"SELECT count(*) AS n FROM {self.table} WHERE {where}", args)
        return row["n"]

    async def distinct(self, field, query=None):
        column = self._column(field)
        where, args = self._where(query)
        rows = await self.database.query(f"SELECT DISTINCT {column} AS value FROM {self.table} WHERE {where}", args, all_rows=True)
        return [_plain(row["value"]) for row in rows]

    async def create_index(self, *args, **kwargs):
        # PostgreSQL migrations own all indexes; never mutate schema at startup.
        return None


class PgDatabase:
    backend = "postgres"

    def __init__(self, dsn):
        if not dsn:
            raise RuntimeError("SAMPE_POSTGRES_DSN is required for PostgreSQL backend")
        self.dsn = dsn
        self.client = PgClient(self)
        self.collections = {name: PgCollection(self, name) for name in TABLES}

    def __getattr__(self, name):
        try:
            return self.collections[name]
        except KeyError:
            raise AttributeError(name) from None

    async def connect(self):
        return await AsyncConnection.connect(self.dsn, connect_timeout=5, row_factory=dict_row)

    async def validate_target(self):
        environment = os.environ.get("SAMPE_POSTGRES_ENV")
        expected = os.environ.get("SAMPE_POSTGRES_TARGET_DB")
        if not expected:
            raise RuntimeError("SAMPE_POSTGRES_TARGET_DB is required")
        if environment == "testing":
            from postgres.migrate import validate_test_target
            validate_test_target(environment, expected, expected)
        elif environment == "production":
            if re.search(r"(^|[_-])(test|testing|stag|staging)($|[_-])", expected, re.IGNORECASE):
                raise RuntimeError("Production PostgreSQL target must not be a test or staging database")
        elif environment != "staging":
            raise RuntimeError("PostgreSQL runtime requires testing, staging, or production")
        row = await self.query("SELECT current_database() AS name")
        if row["name"] != expected:
            raise RuntimeError("Connected PostgreSQL database differs from explicit target")

    async def query(self, sql, args=(), *, session=None, all_rows=False):
        if session:
            cursor = await session.conn.execute(sql, args)
            return await cursor.fetchall() if all_rows else await cursor.fetchone()
        async with await self.connect() as conn:
            cursor = await conn.execute(sql, args)
            return await cursor.fetchall() if all_rows else await cursor.fetchone()

    async def execute(self, sql, args=(), *, session=None):
        if session:
            cursor = await session.conn.execute(sql, args)
            return cursor.rowcount
        async with await self.connect() as conn:
            cursor = await conn.execute(sql, args)
            return cursor.rowcount

    async def bootstrap_admin(self, email, password_hash, admin_id, created_at):
        """Create the first admin once, serialized across Passenger workers."""
        async with await self.connect() as conn:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(hashtext('sampe_first_admin'))")
                existing = await conn.execute("SELECT 1 FROM sampe.users WHERE role='admin' LIMIT 1")
                if await existing.fetchone():
                    return False
                duplicate = await conn.execute("SELECT 1 FROM sampe.users WHERE email=%s", (email,))
                if await duplicate.fetchone():
                    raise RuntimeError("Admin bootstrap email already belongs to another account")
                await conn.execute(
                    "INSERT INTO sampe.users (id,email,password_hash,name,role,created_at) "
                    "VALUES (%s,%s,%s,'Admin','admin',%s)",
                    (admin_id, email, password_hash, created_at),
                )
                return True

    async def save_kpi_config(self, document):
        """One statement preserves the existing config identity on updates."""
        keys = [key for key in document if key in TABLES["kpi_config"][1]]
        updates = [key for key in keys if key not in ("id", "tenant_id", "month", "created_at")]
        sql = (f"INSERT INTO sampe.kpi_config ({', '.join(keys)}) VALUES ({', '.join(['%s'] * len(keys))}) "
               f"ON CONFLICT (tenant_id, month) DO UPDATE SET "
               + ", ".join(f"{key}=EXCLUDED.{key}" for key in updates)
               + " RETURNING *")
        row = await self.query(sql, [document[key] for key in keys])
        return _plain(row)

    async def replace_tenant_demo(self, tenant_id, config, entries):
        """Delete old demo data and insert its replacement atomically."""
        async with await self.connect() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM sampe.entries WHERE tenant_id=%s", (tenant_id,))
                await conn.execute("DELETE FROM sampe.kpi_config WHERE tenant_id=%s", (tenant_id,))
                sql, args = self.kpi_config._insert_sql(config)
                await conn.execute(sql, args)
                for entry in entries:
                    sql, args = self.entries._insert_sql(entry)
                    await conn.execute(sql, args)

    async def reset_tenant(self, tenant_id):
        async with await self.connect() as conn:
            async with conn.transaction():
                entries = await conn.execute("DELETE FROM sampe.entries WHERE tenant_id=%s", (tenant_id,))
                config = await conn.execute("DELETE FROM sampe.kpi_config WHERE tenant_id=%s", (tenant_id,))
                return {"ok": True, "deleted_config": config.rowcount, "deleted_entries": entries.rowcount}

    async def record_login_failure(self, identifier, max_fails, lock_minutes):
        """Serialize rate-limit increments for one identifier."""
        async with await self.connect() as conn:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("login:" + identifier,))
                cursor = await conn.execute("""SELECT id,count FROM sampe.login_attempts
                                               WHERE identifier=%s ORDER BY id LIMIT 1 FOR UPDATE""", (identifier,))
                row = await cursor.fetchone()
                count = (row["count"] if row else 0) + 1
                locked_until = None
                if count >= max_fails:
                    count = 0
                    locked_until = datetime.now(timezone.utc) + timedelta(minutes=lock_minutes)
                if row:
                    await conn.execute("UPDATE sampe.login_attempts SET count=%s,locked_until=%s WHERE id=%s",
                                       (count, locked_until, row["id"]))
                else:
                    await conn.execute("""INSERT INTO sampe.login_attempts (identifier,count,locked_until)
                                          VALUES (%s,%s,%s)""", (identifier, count, locked_until))
