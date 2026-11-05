# PostgreSQL foundation

MongoDB remains the default runtime. PostgreSQL is selected only through an
explicit environment setting; schema migration does not move customer data.

## Source mapping

The first migration covers all 11 collections used by the backend:

| MongoDB collection | PostgreSQL table | Application identity |
| --- | --- | --- |
| `users` | `sampe.users` | `id` |
| `members` | `sampe.members` | `user_id` |
| `user_sessions` | `sampe.user_sessions` | `session_token` |
| `licenses` | `sampe.licenses` | `id` |
| `lynk_orders` | `sampe.lynk_orders` | `ref_id` |
| `login_attempts` | `sampe.login_attempts` | generated row ID |
| `kpi_config` | `sampe.kpi_config` | `id` |
| `entries` | `sampe.entries` | `id` |
| `settings` | `sampe.settings` | `key` |
| `lynk_email_locks` | `sampe.lynk_email_locks` | email (`_id` in MongoDB) |
| `webhook_logs` | `sampe.webhook_logs` | generated row ID |

`mongo_id` is an optional unique text column on tables whose source documents
have a separate MongoDB `_id`. It is reserved for a later, reviewed data move.
Application-facing IDs stay as text so existing references can be preserved.
`entries.data` uses JSONB because KPI entry data varies by module. `settings.extra`
and `webhook_logs.body` can retain optional legacy fields after separate review.

Important constraints reflect the source: unique account emails, session tokens,
license codes when present, and Lynk Ref IDs. `lynk_orders.license_id`,
`licenses.owner_user_id`, and tenant IDs are foreign keys. One KPI config per
tenant/month is the intended application behavior, though MongoDB does not
currently enforce that uniqueness. A later data migration must audit duplicate
configs, missing IDs, orphan references, malformed dates, and numeric precision
before inserting old records. Do not copy raw historic webhook bodies without a
separate privacy review.

## Running on an isolated test database

Install the separate `requirements.txt`, then set `SAMPE_POSTGRES_DSN` through a
secure local environment mechanism and set `SAMPE_POSTGRES_ENV=testing`. The
runner requires an exact database name containing `test` or `testing`; verify
the host and database yourself before running it. It never prints the DSN.

```text
python backend/postgres/migrate.py up --confirm-db sampe_test
python backend/postgres/migrate.py down --confirm-db sampe_test
```

Each direction runs inside one PostgreSQL transaction, guarded by a migration
lock. `down` removes only the `sampe` tables and schema created by the most
recent migration. It leaves the migration-history table in `public`. It is
destructive to data in those test tables; never run it on a shared or production
database. The runner also permits `up` on an explicitly named staging database
when `SAMPE_POSTGRES_ENV=staging`, `SAMPE_POSTGRES_TARGET_DB` matches
`--confirm-db`, and the database name contains a staging label. Staging `down`
and production migrations remain disabled by this command.

## 3A opt-in integration path

`access.py` implements member/session binding, license claim, Lynk order and
renewal transactions, and activation lookup using PostgreSQL. `routes.py`
exposes a separate ASGI app factory for testing those flows. Its identity
verifier must be supplied by the caller; the test suite uses a synthetic
verifier and never calls the live OAuth provider. No default server imports or
mounts this app.

Set `SAMPE_POSTGRES_TEST_DB` to the exact isolated database name as well as the
testing environment and DSN above, then run `test_postgres_porting.py`. The
suite validates the actual connected database before writing synthetic rows
and cleans up only its own fixtures. HTTP route testing also requires FastAPI
and HTTPX in the selected Python environment.

## 3B local application selection

The default is still MongoDB. For an isolated PostgreSQL application run,
explicitly set `SAMPE_DB_BACKEND=postgres`, `SAMPE_POSTGRES_ENV=testing`,
`SAMPE_POSTGRES_TARGET_DB` to the exact connected database name, and
`SAMPE_POSTGRES_DSN` through a secure environment mechanism. Startup checks
the connected database name and refuses a mismatch. Staging uses
`SAMPE_POSTGRES_ENV=staging` with an explicit target name. Production requires
`SAMPE_POSTGRES_ENV=production` and refuses a test or staging target name.
Selecting PostgreSQL for production still requires deployment approval.

`compat.py` maps the existing endpoint data operations to the 11 PostgreSQL
tables. The main application selects one backend for the process; it never
falls back when PostgreSQL configuration or connection fails. `auth.py` and
`lynk.py` use the transaction-safe 3A account and webhook operations in
PostgreSQL mode. `onboarding.py` replaces seed data and resets a tenant in a
single PostgreSQL transaction. The default MongoDB path remains separate.

`test_postgres_main_app.py` exercises the real FastAPI app on an isolated test
database using synthetic identities and payment fixtures. The live OAuth
provider, live Lynk delivery, external AI integration, and frontend browser
are outside this local test. Production enablement, customer-data migration,
and deployment require separate approval and validation.

## Fresh production database preparation

Use only the empty, dedicated `satsetdi_sampe` database after its private user
and DSN are configured. Verify its identity and emptiness before running:

```text
SAMPE_POSTGRES_ENV=production
SAMPE_POSTGRES_TARGET_DB=satsetdi_sampe
SAMPE_POSTGRES_DSN=<private DSN; never store in Git>
python backend/postgres/migrate.py up --confirm-db satsetdi_sampe --allow-production
```

The runner checks the connected database name and refuses production DOWN or
any existing user tables. It creates the empty SAMPE schema only. The first
admin is provisioned at application startup from private `ADMIN_EMAIL` and
`ADMIN_PASSWORD` values (at least 12 characters), only when no admin exists;
later restarts never reset that password. `JWT_SECRET` is also required.
