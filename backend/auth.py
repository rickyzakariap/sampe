"""Auth: Google (Emergent) untuk user + lisensi per akun, admin email/password, manajemen lisensi."""
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt
import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from core import db, DB_BACKEND
from license_rules import (_now, _parse, license_status, public_license,
                           activate_fields, extend_fields, new_license,
                           generate_license_code)
from lynk_contract import renew_url, valid_buyer_email

JWT_ALGORITHM = "HS256"
DURATIONS = (1, 7, 30, 365)
MAX_FAILS = 5
LOCK_MINUTES = 15
SESSION_DAYS = 7
EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"

router = APIRouter(prefix="/api")


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    return bcrypt.checkpw(p.encode(), h.encode())


async def new_code() -> str:
    while True:
        code = generate_license_code()
        if not await db.licenses.find_one({"code": code}):
            return code


# ---------------- Session helpers ----------------
def _token(request: Request) -> Optional[str]:
    t = request.cookies.get("session_token")
    h = request.headers.get("Authorization", "")
    if h.startswith("Bearer "):
        t = h[7:]
    return t


async def get_member(request: Request) -> dict:
    t = _token(request)
    if not t:
        raise HTTPException(401, "Silakan login terlebih dahulu")
    s = await db.user_sessions.find_one({"session_token": t}, {"_id": 0})
    if not s or _parse(s["expires_at"]) < _now():
        raise HTTPException(401, "Sesi habis, silakan login ulang")
    m = await db.members.find_one({"user_id": s["user_id"]}, {"_id": 0})
    if not m:
        raise HTTPException(401, "Akun tidak ditemukan")
    return m


async def license_of(member: dict) -> Optional[dict]:
    return await db.licenses.find_one({"owner_user_id": member["user_id"]}, {"_id": 0}, sort=[("created_at", -1)])


async def get_tenant(member: dict = Depends(get_member)) -> dict:
    lic = await license_of(member)
    if not lic:
        raise HTTPException(403, "Akun ini belum punya lisensi")
    if lic.get("revoked"):
        raise HTTPException(403, "Lisensi sudah dicabut. Hubungi admin.")
    return {"tenant_id": lic["id"], "writable": license_status(lic) == "active", "license": lic, "member": member}


async def require_write(p: dict = Depends(get_tenant)) -> dict:
    if not p["writable"]:
        raise HTTPException(403, "Lisensi sudah habis. Data masih bisa dilihat, tapi tidak bisa diubah sampai lisensi diperpanjang.")
    return p


async def get_admin(request: Request) -> dict:
    h = request.headers.get("Authorization", "")
    if not h.startswith("Bearer "):
        raise HTTPException(401, "Silakan login admin")
    try:
        payload = jwt.decode(h[7:], os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Sesi admin habis, login ulang")
    if payload.get("type") != "admin":
        raise HTTPException(401, "Token tidak valid")
    user = await db.users.find_one({"id": payload["sub"], "role": "admin"}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(401, "Admin tidak ditemukan")
    return user


# ---------------- Brute force ----------------
async def check_lock(ident: str):
    rec = await db.login_attempts.find_one({"identifier": ident})
    if rec and rec.get("locked_until") and _parse(rec["locked_until"]) > _now():
        raise HTTPException(429, f"Terlalu banyak percobaan gagal. Coba lagi dalam {LOCK_MINUTES} menit.")


async def record_fail(ident: str):
    if DB_BACKEND == "postgres":
        await db.record_login_failure(ident, MAX_FAILS, LOCK_MINUTES)
        return
    rec = await db.login_attempts.find_one_and_update({"identifier": ident}, {"$inc": {"count": 1}}, upsert=True, return_document=True)
    if rec and rec.get("count", 0) >= MAX_FAILS:
        await db.login_attempts.update_one({"identifier": ident}, {"$set": {
            "locked_until": (_now() + timedelta(minutes=LOCK_MINUTES)).isoformat(), "count": 0}})


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")


async def _bind(lic: dict, member: dict) -> dict:
    upd = {"owner_user_id": member["user_id"], "last_login_at": _now().isoformat()}
    if not lic.get("activated_at"):
        upd |= activate_fields(lic)
    if not lic.get("code"):
        upd["code"] = await new_code()
    await db.licenses.update_one({"id": lic["id"]}, {"$set": upd})
    return lic | upd


async def auto_bind(m: dict) -> Optional[dict]:
    lic = await db.licenses.find_one({"email": m["email"], "owner_user_id": None, "revoked": False}, {"_id": 0}, sort=[("created_at", -1)])
    return await _bind(lic, m) if lic else None


# ---------------- User auth routes ----------------
class SessionIn(BaseModel):
    session_id: str


class ClaimIn(BaseModel):
    code: str = Field(min_length=4, max_length=40)


@router.post("/auth/google-session")
async def google_session(payload: SessionIn, response: Response):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": payload.session_id})
    if r.status_code != 200:
        raise HTTPException(401, "Login Google gagal, coba lagi")
    data = r.json()
    email = data["email"].strip().lower()
    if DB_BACKEND == "postgres":
        from postgres.access import PostgresAccess
        from starlette.concurrency import run_in_threadpool
        token = data["session_token"]
        await run_in_threadpool(PostgresAccess(db.dsn).start_session, email, data.get("name") or "",
                                token, picture=data.get("picture"))
        response.set_cookie("session_token", token, httponly=True, secure=True, samesite="none", path="/", max_age=SESSION_DAYS * 86400)
        return {"session_token": token}
    m = await db.members.find_one({"email": email}, {"_id": 0})
    if m:
        await db.members.update_one({"user_id": m["user_id"]}, {"$set": {"name": data.get("name"), "picture": data.get("picture")}})
    else:
        m = {"user_id": f"user_{uuid.uuid4().hex[:12]}", "email": email, "name": data.get("name"),
             "picture": data.get("picture"), "created_at": _now().isoformat()}
        await db.members.insert_one(dict(m))
    token = data["session_token"]
    await db.user_sessions.insert_one({"session_token": token, "user_id": m["user_id"],
                                       "expires_at": (_now() + timedelta(days=SESSION_DAYS)).isoformat(), "created_at": _now().isoformat()})
    response.set_cookie("session_token", token, httponly=True, secure=True, samesite="none", path="/", max_age=SESSION_DAYS * 86400)
    if not await license_of(m):
        await auto_bind(m)
    return {"session_token": token}


@router.get("/auth/me")
async def me(member: dict = Depends(get_member)):
    if DB_BACKEND == "postgres":
        from postgres.access import PostgresAccess
        from starlette.concurrency import run_in_threadpool
        lic = await run_in_threadpool(PostgresAccess(db.dsn).ensure_member_license, member["user_id"])
        s = await db.settings.find_one({"key": "lynk"}, {"_id": 0}) or {}
        return {"user": {k: member.get(k) for k in ("user_id", "email", "name", "picture")},
                "license": public_license(lic) if lic else None,
                "writable": bool(lic) and license_status(lic) == "active", "renew_url": renew_url(s.get("renew_url"))}
    lic = await license_of(member) or await auto_bind(member)
    if lic:
        await db.licenses.update_one({"id": lic["id"]}, {"$set": {"last_login_at": _now().isoformat()}})
    s = await db.settings.find_one({"key": "lynk"}, {"_id": 0}) or {}
    return {"user": {k: member.get(k) for k in ("user_id", "email", "name", "picture")},
            "license": public_license(lic) if lic else None,
            "writable": bool(lic) and license_status(lic) == "active",
            "renew_url": renew_url(s.get("renew_url"))}


@router.post("/auth/claim")
async def claim(payload: ClaimIn, request: Request, member: dict = Depends(get_member)):
    ident = f"claim:{client_ip(request)}"
    await check_lock(ident)
    if DB_BACKEND == "postgres":
        from postgres.access import PostgresAccess
        from starlette.concurrency import run_in_threadpool
        try:
            lic = await run_in_threadpool(PostgresAccess(db.dsn).claim_license, member["user_id"], payload.code)
        except PermissionError:
            raise HTTPException(409, "Kode ini sudah terhubung ke akun Google lain")
        except ValueError:
            await record_fail(ident)
            raise HTTPException(404, "Kode lisensi tidak valid atau sudah dicabut")
        await db.login_attempts.delete_one({"identifier": ident})
        return public_license(lic)
    lic = await db.licenses.find_one({"code": payload.code.strip().upper()}, {"_id": 0})
    if not lic or lic.get("revoked"):
        await record_fail(ident)
        raise HTTPException(404, "Kode lisensi tidak valid atau sudah dicabut")
    if lic.get("owner_user_id") and lic["owner_user_id"] != member["user_id"]:
        raise HTTPException(409, "Kode ini sudah terhubung ke akun Google lain")
    await db.login_attempts.delete_one({"identifier": ident})
    return public_license(await _bind(lic, member))


@router.post("/auth/logout")
async def logout(request: Request, response: Response):
    t = _token(request)
    if t:
        await db.user_sessions.delete_one({"session_token": t})
    response.delete_cookie("session_token", path="/", secure=True, samesite="none")
    return {"ok": True}


# ---------------- Admin ----------------
class AdminLogin(BaseModel):
    email: str
    password: str


@router.post("/auth/admin-login")
async def admin_login(payload: AdminLogin, request: Request):
    email = payload.email.strip().lower()
    ident = f"admin:{client_ip(request)}:{email}"
    await check_lock(ident)
    user = await db.users.find_one({"email": email, "role": "admin"})
    if not user or not verify_password(payload.password, user["password_hash"]):
        await record_fail(ident)
        raise HTTPException(401, "Email atau password salah")
    await db.login_attempts.delete_one({"identifier": ident})
    token = jwt.encode({"sub": user["id"], "type": "admin", "exp": _now() + timedelta(hours=12)}, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)
    return {"token": token, "admin": {"email": user["email"], "name": user.get("name")}}


@router.get("/auth/admin-me")
async def admin_me(admin: dict = Depends(get_admin)):
    return {"email": admin["email"], "name": admin.get("name")}


class LicenseCreate(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    duration_days: int
    email: Optional[str] = None


class LicenseExtend(BaseModel):
    days: int


def _check_duration(d: int):
    if d not in DURATIONS:
        raise HTTPException(400, "Durasi harus 1, 7, 30, atau 365 hari")


async def _get_lic(lid: str) -> dict:
    lic = await db.licenses.find_one({"id": lid}, {"_id": 0})
    if not lic:
        raise HTTPException(404, "Lisensi tidak ditemukan")
    return lic


@router.get("/admin/licenses")
async def list_licenses(_: dict = Depends(get_admin)):
    lics = await db.licenses.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    out = []
    for lic in lics:
        cfg = await db.kpi_config.find_one({"tenant_id": lic["id"]}, {"_id": 0, "company_name": 1}, sort=[("month", -1)])
        owner = await db.members.find_one({"user_id": lic.get("owner_user_id")}, {"_id": 0, "email": 1}) if lic.get("owner_user_id") else None
        n = await db.entries.count_documents({"tenant_id": lic["id"]})
        out.append(public_license(lic) | {"company_name": (cfg or {}).get("company_name"), "entry_count": n,
                                          "google_email": (owner or {}).get("email")})
    return out


@router.post("/admin/licenses")
async def create_license(payload: LicenseCreate, _: dict = Depends(get_admin)):
    _check_duration(payload.duration_days)
    lic = new_license(payload.label.strip(), payload.duration_days, payload.email) | {"code": await new_code()}
    await db.licenses.insert_one(dict(lic))
    return public_license(lic)


@router.post("/admin/licenses/{lid}/extend")
async def extend_license(lid: str, payload: LicenseExtend, _: dict = Depends(get_admin)):
    _check_duration(payload.days)
    if DB_BACKEND == "postgres":
        from postgres.access import PostgresAccess
        from starlette.concurrency import run_in_threadpool
        lic = await run_in_threadpool(PostgresAccess(db.dsn).extend_admin_license, lid, payload.days)
        if not lic:
            raise HTTPException(404, "Lisensi tidak ditemukan")
        return public_license(lic)
    lic = await _get_lic(lid)
    upd = extend_fields(lic, payload.days)
    await db.licenses.update_one({"id": lid}, {"$set": upd})
    return public_license(lic | upd)


@router.post("/admin/licenses/{lid}/revoke")
async def revoke_license(lid: str, _: dict = Depends(get_admin)):
    lic = await _get_lic(lid)
    await db.licenses.update_one({"id": lid}, {"$set": {"revoked": True}})
    return public_license(lic | {"revoked": True})


@router.post("/admin/licenses/{lid}/restore")
async def restore_license(lid: str, _: dict = Depends(get_admin)):
    lic = await _get_lic(lid)
    await db.licenses.update_one({"id": lid}, {"$set": {"revoked": False}})
    return public_license(lic | {"revoked": False})


# ---------------- Startup ----------------
async def init_auth():
    await db.users.create_index("email", unique=True)
    await db.members.create_index("email", unique=True)
    await db.members.create_index("user_id", unique=True)
    await db.user_sessions.create_index("session_token", unique=True)
    await db.licenses.create_index("code", unique=True, partialFilterExpression={"code": {"$type": "string"}})
    await db.licenses.create_index("id", unique=True)
    await db.licenses.create_index("email")
    await db.lynk_orders.create_index("ref_id", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.kpi_config.create_index([("tenant_id", 1), ("month", 1)])
    await db.entries.create_index([("tenant_id", 1), ("date", 1)])
    if DB_BACKEND == "postgres":
        if await db.users.find_one({"role": "admin"}):
            return
        email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
        pwd = os.environ.get("ADMIN_PASSWORD", "")
        if not valid_buyer_email(email) or len(pwd) < 12:
            raise RuntimeError("First admin requires a valid ADMIN_EMAIL and ADMIN_PASSWORD of at least 12 characters")
        await db.bootstrap_admin(email, hash_password(pwd), str(uuid.uuid4()), _now().isoformat())
        return
    email = os.environ["ADMIN_EMAIL"].strip().lower()
    pwd = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": email})
    if not existing:
        await db.users.insert_one({"id": str(uuid.uuid4()), "email": email, "password_hash": hash_password(pwd),
                                   "name": "Admin", "role": "admin", "created_at": _now().isoformat()})
    elif not verify_password(pwd, existing["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(pwd)}})
