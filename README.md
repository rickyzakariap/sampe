# SAMPE — System Analytic Marketplace

SAMPE is a KPI dashboard with a FastAPI backend and a React/Vite frontend. The current backend uses **MongoDB**. It is not connected to Supabase; a Supabase project cannot be used as its database until the persistence layer is migrated.

## Requirements

- Python 3.11 or newer
- Node.js 20.19+ or 22.12+ (Vite 8 requirement)
- Corepack/Yarn 1.22.22
- MongoDB running as a **replica set**. Lynk order and license writes use MongoDB transactions, which do not work on a standalone MongoDB server.

## Local setup

1. Create a MongoDB replica set (for local development, a single-node replica set is sufficient) and make sure it is reachable from this machine.
2. Copy `backend/.env.example` to `backend/.env`, then set `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD` for your local environment. Use a long random JWT secret and a unique admin password. Never commit `.env` files.
3. Install backend dependencies and start the API:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   uvicorn server:app --reload --host 127.0.0.1 --port 8000
   ```

   On first startup, SAMPE creates the configured admin account and database indexes. Keep the backend running.

4. In another terminal, configure and start the frontend:

   ```powershell
   cd frontend
   Copy-Item .env.example .env
   corepack yarn install
   corepack yarn start
   ```

   Open `http://localhost:3000`. With `REACT_APP_BACKEND_URL` empty, Vite forwards `/api` requests to `http://127.0.0.1:8000`. For Lynk webhooks or a separately hosted frontend, set this variable to the public HTTPS origin of the backend before starting/building the frontend.

## Required external integrations and deployment notes

- **Google sign-in currently depends on Emergent.** The backend exchanges the Emergent session ID with Emergent's session-data endpoint; this repo does not implement standalone Google OAuth. A new domain must also have the matching login integration, or this auth flow needs a separately scoped replacement.
- **MongoDB is required today.** The code uses Motor and MongoDB collections/indexes. Supabase/Postgres setup alone will not run this version.
- **CORS:** set `CORS_ORIGINS` to the exact frontend origin(s), comma-separated, for example `https://app.example.com`. Do not use `*` with credentialed browser requests.
- **AI analysis:** `EMERGENT_LLM_KEY` is optional for startup but required for the AI analysis endpoint.
- **Lynk:** configure the Merchant Key through SAMPE Admin after deployment. The webhook must be an externally reachable HTTPS URL. Do not put the Merchant Key in frontend variables or source control.
- The repo currently has no frontend lockfile. Dependency versions are declared in `frontend/package.json`; generate and review a Yarn v1 lockfile as a separate dependency-management step before relying on reproducible builds.

## Offline Lynk tests

From the repository root:

```powershell
python -m unittest backend.tests.test_lynk_offline -v
```

These tests use an in-memory fake database and synthetic fixtures. They do not contact Lynk or a live database and do not prove production behavior.

## Configuration examples

- Backend: [`backend/.env.example`](backend/.env.example)
- Frontend: [`frontend/.env.example`](frontend/.env.example)
