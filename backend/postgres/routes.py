"""Separate, opt-in ASGI app for PostgreSQL 3A integration testing.

The default MongoDB server does not import or mount this app. A caller must
inject an identity verifier; this module never calls the live OAuth provider.
"""

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from license_rules import license_status, public_license
from postgres.access import PolicyDecisionRequired, PostgresAccess


class SessionIn(BaseModel):
    session_id: str


class ClaimIn(BaseModel):
    code: str


class LookupIn(BaseModel):
    email: str
    ref_id: str


def create_postgres_app(access: PostgresAccess, verify_identity):
    """Build an isolated app; verifier returns trusted identity/session data."""
    app = FastAPI()

    def bearer(request: Request):
        header = request.headers.get("Authorization", "")
        return header[7:] if header.startswith("Bearer ") else request.cookies.get("session_token")

    @app.post("/api/auth/google-session")
    async def google_session(payload: SessionIn, response: Response):
        try:
            identity = await verify_identity(payload.session_id)
            token = identity["session_token"]
            await run_in_threadpool(access.start_session, identity["email"], identity.get("name") or "",
                                    token, picture=identity.get("picture"))
        except (KeyError, ValueError, PermissionError):
            raise HTTPException(401, "Login gagal")
        response.set_cookie("session_token", token, httponly=True, secure=True,
                            samesite="none", path="/", max_age=7 * 86400)
        return {"session_token": token}

    @app.get("/api/auth/me")
    async def me(request: Request):
        token = bearer(request)
        member = await run_in_threadpool(access.member_for_session, token) if token else None
        if not member:
            raise HTTPException(401, "Sesi habis, silakan login ulang")
        lic = await run_in_threadpool(access.ensure_member_license, member["user_id"])
        renew_url = await run_in_threadpool(access.renew_url)
        return {"user": {k: member.get(k) for k in ("user_id", "email", "name", "picture")},
                "license": public_license(lic) if lic else None,
                "writable": bool(lic) and license_status(lic) == "active", "renew_url": renew_url}

    @app.post("/api/auth/claim")
    async def claim(payload: ClaimIn, request: Request):
        token = bearer(request)
        member = await run_in_threadpool(access.member_for_session, token) if token else None
        if not member:
            raise HTTPException(401, "Silakan login terlebih dahulu")
        try:
            lic = await run_in_threadpool(access.claim_license, member["user_id"], payload.code)
        except PermissionError:
            raise HTTPException(409, "Kode ini sudah terhubung ke akun lain")
        except ValueError:
            raise HTTPException(404, "Kode lisensi tidak valid")
        return public_license(lic)

    @app.post("/api/auth/logout")
    async def logout(request: Request, response: Response):
        token = bearer(request)
        if token:
            await run_in_threadpool(access.end_session, token)
        response.delete_cookie("session_token", path="/", secure=True, samesite="none")
        return {"ok": True}

    @app.post("/api/webhooks/lynk")
    async def webhook(request: Request):
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(400, "Payload JSON tidak valid")
        try:
            return await run_in_threadpool(access.receive_webhook, body,
                                           request.headers.get("X-Lynk-Signature", ""))
        except ValueError as exc:
            if str(exc) == "Invalid signature":
                raise HTTPException(401, "Signature tidak valid")
            raise HTTPException(400, "Payload transaksi tidak valid")
        except PolicyDecisionRequired:
            raise HTTPException(409, "Order memerlukan keputusan kebijakan lisensi")
        except Exception:
            raise HTTPException(503, "Order gagal diproses sementara; aman untuk retry")

    @app.post("/api/activation/lookup")
    async def activation_lookup(payload: LookupIn):
        try:
            found = await run_in_threadpool(access.activation_lookup, payload.email, payload.ref_id)
        except RuntimeError:
            raise HTTPException(409, "Lisensi terkait order tidak tersedia")
        if not found:
            raise HTTPException(404, "Order tidak ditemukan")
        if not found.get("code"):
            raise HTTPException(409, "Order belum memiliki lisensi")
        return found

    return app
