# SAMPE deployment preparation

This repository is prepared for a reviewed staging deployment. Nothing in this
file activates PostgreSQL, changes Lynk, or deploys the application.

## Runtime layout

- Serve the Vite bundle from `frontend/build/` over HTTPS at
  `https://sampe.satsetdigital.id`, with SPA fallback to `index.html`.
- Route `/api/*` on the same origin to the persistent FastAPI process. The Lynk
  webhook path remains `/api/webhooks/lynk`. Keep the backend behind a trusted
  HTTPS reverse proxy and restrict direct public access to its port.
- Start the backend from `backend/` with
  `uvicorn server:app --host 0.0.0.0 --port 8000`. The ASGI entrypoint is
  `server:app`. Set the process port to the value required by the selected
  host. Send stdout and stderr to the host's protected application logs.
- `GET /api/health` checks database connectivity and returns only `status`.
  A failed check returns HTTP 503 without connection details.

## Environment

Inject values through the host's secret manager. Do not put real values in
Git, frontend variables, or deployment logs.

| Variable | Purpose |
| --- | --- |
| `SAMPE_DB_BACKEND=postgres` | Explicitly select PostgreSQL; default remains MongoDB. |
| `SAMPE_POSTGRES_ENV=staging` or `production` | Explicit runtime environment. |
| `SAMPE_POSTGRES_DSN` | PostgreSQL connection, supplied privately. |
| `SAMPE_POSTGRES_TARGET_DB` | Exact database name checked at startup. Production refuses test/staging names. |
| `JWT_SECRET` | Admin token signing secret. |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Admin bootstrap identity, supplied privately. |
| `CORS_ORIGINS` | Comma-separated exact HTTPS origins, for example `https://sampe.satsetdigital.id`. |
| `EMERGENT_LLM_KEY` | Required only for the existing AI analysis feature. |

The Lynk Merchant Key stays in SAMPE admin settings in PostgreSQL. Set it only
through the approved admin procedure after staging verification. Never put it
in the frontend bundle or migration files. Do not copy production keys to
staging. Do not mix MongoDB and PostgreSQL data in a running process.

For a same-origin deployment, leave `REACT_APP_BACKEND_URL` empty at **build
time** so frontend calls `/api`. Set `REACT_APP_ADMIN_PATH` to the intended
public admin route, or use the existing `/admin` default. Both are compile-time
settings; neither is an authentication secret. Build from `frontend/` with
`yarn build` after installing the locked frontend dependencies. `build/` is
excluded from Git. A split frontend/backend origin requires an HTTPS backend
URL and matching `CORS_ORIGINS` before building.

## New staging database

Create a separate empty PostgreSQL database whose name contains `staging`.
Verify its host and database name independently. Set
`SAMPE_POSTGRES_ENV=staging`, `SAMPE_POSTGRES_TARGET_DB` to that exact name,
and provide its DSN privately. Then run, from the repository root:

```text
python backend/postgres/migrate.py up --confirm-db <exact_staging_db_name>
```

The runner checks the connected database name, applies versioned SQL in one
transaction, and records migration history. It refuses staging rollback and
all production migrations. Verify the 11 tables and run synthetic staging
checks before any production release. Production schema application and any
customer-data migration require a separate reviewed procedure and approval;
do not point staging settings at an existing production database.

Before deployment, confirm the chosen host provides a persistent ASGI process,
HTTPS reverse proxy, PostgreSQL connectivity, private environment variables,
application logs, and backups. These capabilities are not assumed from the
presence of a hosting account.
