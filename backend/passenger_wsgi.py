"""Passenger WSGI entrypoint for the existing FastAPI application.

PostgreSQL must be explicitly selected. Startup runs before Passenger can
serve a request, so an invalid database target fails visibly.
"""

import asyncio
import sys
from pathlib import Path

from a2wsgi import ASGIMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import DB_BACKEND  # noqa: E402

if DB_BACKEND != "postgres":
    raise RuntimeError("Passenger entrypoint requires SAMPE_DB_BACKEND=postgres")

from server import app, startup  # noqa: E402

asyncio.run(startup())
_wsgi_app = ASGIMiddleware(app)


def application(environ, start_response):
    """Restore the /api prefix stripped by Passenger's application mount."""
    path = environ.get("PATH_INFO") or "/"
    if path != "/api" and not path.startswith("/api/"):
        environ = environ.copy()
        environ["PATH_INFO"] = "/api" + (path if path.startswith("/") else "/" + path)
    return _wsgi_app(environ, start_response)
