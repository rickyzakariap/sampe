# SAMPE deployment preparation

This repository is prepared for a reviewed staging deployment. Nothing in this
file activates PostgreSQL, changes Lynk, or deploys the application.

## Host decision before deployment

The current WarnaHost cPanel exposes PostgreSQL and Application Manager using
Phusion Passenger. The `backend/passenger_wsgi.py` adapter runs the existing
FastAPI app through `a2wsgi.ASGIMiddleware`; local WSGI smoke tests cover
PostgreSQL startup and `/api/health`. Passenger execution on this account is
still unverified. No isolated staging domain is registered in cPanel, so do
not register the app on the production SAMPE domain for a smoke test.

For an approved WarnaHost deployment, set the application path to `backend/`
and the Passenger Python startup file to `passenger_wsgi.py` with callable
`application`. Install `backend/requirements.txt` into the Python environment
selected by the host. The entrypoint calls the application's startup before
serving requests and rejects non-PostgreSQL configuration. Confirm the account
offers a compatible Python version, a private way to inject the variables
below, and usable application logs before registration. The current cPanel
registration form does not expose environment variable fields; a host-supported
private configuration method is required. Do not put secrets in the source,
document root, frontend bundle, or Passenger startup file.

One compatible backend option is a Render Python web service. Render documents
FastAPI with Uvicorn and lists its smallest paid web-service compute at
US$7/month on a US$0 Hobby workspace (pricing checked 2026-10-14). This is a
proposal, not an approved purchase or deployment. Its connection to the
existing WarnaHost PostgreSQL database must be verified before use. If remote
database access is unavailable, a separate database service would be needed;
Render lists paid PostgreSQL starting at US$6/month. Do not create it without
approval. Sources: https://render.com/docs/deploy-fastapi and
https://render.com/pricing.

## Runtime layout

- Serve the Vite bundle from `frontend/build/` over HTTPS at
  `https://sampe.satsetdigital.id`, with SPA fallback to `index.html`.
- For a split deployment, use an approved HTTPS backend origin such as
  `https://api.sampe.satsetdigital.id`; frontend calls that origin's `/api`.
  The Lynk webhook path remains `/api/webhooks/lynk`. Do not change the live
  webhook until the backend, database, and activation flow are verified.
- Start the backend from `backend/` with
  `uvicorn server:app --host 0.0.0.0 --port $PORT` on a host that sets `PORT`.
  The ASGI entrypoint is `server:app`. Set the process port to the value required by the selected
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
`npm ci` then `npm run build` using the committed lockfile. `build/` is
excluded from Git. A split frontend/backend origin requires an HTTPS backend
URL and matching `CORS_ORIGINS` before building. Upload the generated `build/`
contents to the WarnaHost document root for the SAMPE subdomain and configure
SPA fallback to `index.html` for routes such as `/aktivasi`. These hosting
changes require deployment approval.

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

The Lynk store URL is `https://lynk.id/katalogsatset`. The purchase button
uses the `renew_url` saved in SAMPE Admin; an empty value falls back to this
store URL. Before release, inspect the saved setting and preserve any valid
product-specific URL. A changed store URL alone does not imply a new Merchant
Key. Do not alter the Lynk webhook or Merchant Key before a reviewed cutover.

Retain and back up the existing MongoDB data. An empty PostgreSQL schema does
not contain old accounts, orders, or licenses. Any customer-data move, count
reconciliation, and production cutover need a separate approved procedure.

Before deployment, confirm the chosen host runs this WSGI adapter persistently,
provides HTTPS, PostgreSQL connectivity, private environment variables,
application logs, and backups. These capabilities are not assumed from the
presence of a hosting account.
