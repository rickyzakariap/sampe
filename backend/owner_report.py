"""Read-only KPI report scoped by a revocable bearer link."""

import hashlib
import hmac
import base64
import os
import re
import secrets
import unicodedata
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from auth import require_write
from core import DB_BACKEND, db

router = APIRouter(prefix="/api/owner-report", tags=["owner-report"])
MODULES = ("sales", "ads", "livestream", "branding", "campaign", "kol")
MONTH = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])\Z")
LINK = re.compile(r"([a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?)-([A-Za-z0-9_-]{43})\Z")


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"


def _require_postgres() -> None:
    if DB_BACKEND != "postgres":
        raise HTTPException(503, "Owner Report memerlukan PostgreSQL")


def _secret() -> bytes:
    value = os.environ.get("OWNER_REPORT_SECRET", "")
    if len(value) < 32:
        raise HTTPException(503, "Owner Report belum dikonfigurasi")
    return value.encode("utf-8")


def _slug(company_name: str) -> str:
    text = unicodedata.normalize("NFKD", company_name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80].strip("-")
    if not slug:
        raise HTTPException(409, "Nama toko diperlukan sebelum membuat link laporan")
    return slug


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _token(seed: bytes) -> str:
    digest = hmac.new(_secret(), seed, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


async def _manager(request: Request, p: dict = Depends(require_write)) -> dict:
    if not request.headers.get("Authorization", "").startswith("Bearer "):
        raise HTTPException(401, "Sesi akun diperlukan")
    return p


async def _rate_limit(request: Request, bucket: str, limit: int) -> None:
    peer = request.client.host if request.client else "unknown"
    key = hmac.new(_secret(), (bucket + ":" + peer).encode("utf-8"), hashlib.sha256).hexdigest()
    row = await db.query(
        "INSERT INTO sampe.owner_report_rate_limits(bucket,hits,window_started_at) "
        "VALUES (%s,1,now()) ON CONFLICT (bucket) DO UPDATE SET "
        "hits=CASE WHEN sampe.owner_report_rate_limits.window_started_at < now()-interval '1 minute' "
        "THEN 1 ELSE sampe.owner_report_rate_limits.hits+1 END, "
        "window_started_at=CASE WHEN sampe.owner_report_rate_limits.window_started_at < now()-interval '1 minute' "
        "THEN now() ELSE sampe.owner_report_rate_limits.window_started_at END RETURNING hits",
        (key,),
    )
    if row["hits"] > limit:
        raise HTTPException(429, "Terlalu banyak permintaan laporan")


async def _link(request: Request) -> str:
    _require_postgres()
    match = LINK.fullmatch(request.headers.get("X-Owner-Report-Link", ""))
    if not match:
        await _rate_limit(request, "invalid", 60)
        raise HTTPException(404, "Laporan tidak tersedia")
    slug, token = match.groups()
    token_hash = _hash(token)
    await _rate_limit(request, token_hash, 120)
    row = await db.query(
        "SELECT l.tenant_id FROM sampe.owner_report_links l "
        "JOIN sampe.licenses lic ON lic.id=l.tenant_id "
        "WHERE l.slug=%s AND l.link_hash=%s AND lic.revoked=false",
        (slug, token_hash),
    )
    if not row:
        raise HTTPException(404, "Laporan tidak tersedia")
    return row["tenant_id"]


async def _company_slug(tenant_id: str) -> str:
    config = await db.kpi_config.find_one({"tenant_id": tenant_id}, {"company_name": 1}, sort=[("month", -1)])
    if not config:
        raise HTTPException(409, "Nama toko belum diatur")
    return _slug(config["company_name"])


@router.get("/manage")
async def manage(response: Response, p: dict = Depends(_manager)):
    _require_postgres()
    _no_store(response)
    row = await db.query("SELECT slug,token_seed,link_hash FROM sampe.owner_report_links WHERE tenant_id=%s", (p["tenant_id"],))
    if not row:
        return {"enabled": False, "slug": None}
    token = _token(row["token_seed"])
    if not hmac.compare_digest(_hash(token), row["link_hash"]):
        raise HTTPException(503, "Link laporan perlu diganti")
    return {"enabled": True, "slug": row["slug"], "token": token}


@router.post("/manage")
async def create_link(response: Response, p: dict = Depends(_manager)):
    _require_postgres()
    _no_store(response)
    slug, seed = await _company_slug(p["tenant_id"]), secrets.token_bytes(32)
    token = _token(seed)
    async with await db.connect() as conn:
        row = await (await conn.execute(
            "INSERT INTO sampe.owner_report_links(tenant_id,slug,token_seed,link_hash) VALUES (%s,%s,%s,%s) "
            "ON CONFLICT (tenant_id) DO NOTHING RETURNING slug",
            (p["tenant_id"], slug, seed, _hash(token)),
        )).fetchone()
    if not row:
        return await manage(response, p)
    return {"enabled": True, "slug": slug, "token": token}


@router.post("/rotate")
async def rotate_link(response: Response, p: dict = Depends(_manager)):
    _require_postgres()
    _no_store(response)
    slug, seed = await _company_slug(p["tenant_id"]), secrets.token_bytes(32)
    token = _token(seed)
    row = await db.query(
        "UPDATE sampe.owner_report_links SET slug=%s,token_seed=%s,link_hash=%s,rotated_at=now() "
        "WHERE tenant_id=%s RETURNING tenant_id", (slug, seed, _hash(token), p["tenant_id"]),
    )
    if not row:
        raise HTTPException(404, "Link laporan belum dibuat")
    return {"enabled": True, "slug": slug, "token": token}


@router.delete("/manage")
async def revoke_link(response: Response, p: dict = Depends(_manager)):
    _require_postgres()
    _no_store(response)
    await db.execute("DELETE FROM sampe.owner_report_links WHERE tenant_id=%s", (p["tenant_id"],))
    return {"enabled": False}


@router.get("/data")
async def report_data(month: str, request: Request, response: Response):
    _no_store(response)
    if not MONTH.fullmatch(month):
        raise HTTPException(422, "Periode tidak valid")
    tenant_id = await _link(request)
    from ai_analysis import cached_analysis, source_fingerprint
    from server import build_summary, build_compare

    summary = await build_summary(month, tenant_id)
    compare = await build_compare(month, tenant_id)
    entries = await db.entries.find({"tenant_id": tenant_id, "date": {"$regex": f"^{month}"}}, {"_id": 0}) \
        .sort("date", -1).to_list(5000)
    entries = [{"module": item["module"], "date": item["date"], "data": item["data"]}
               for item in entries if item["module"] in MODULES]
    config_months = await db.kpi_config.distinct("month", {"tenant_id": tenant_id})
    entry_dates = await db.entries.distinct("date", {"tenant_id": tenant_id})
    months = sorted(set(config_months) | {day[:7] for day in entry_dates if day} | {month}, reverse=True)
    latest = await db.query(
        "SELECT greatest((SELECT max(created_at) FROM sampe.entries WHERE tenant_id=%s), "
        "(SELECT max(created_at) FROM sampe.kpi_config WHERE tenant_id=%s)) AS latest",
        (tenant_id, tenant_id),
    )
    analysis = await cached_analysis(tenant_id, month, await source_fingerprint(tenant_id, month))
    return {"summary": summary, "compare": compare, "entries": entries, "months": months,
            "latest_created_at": latest["latest"].isoformat() if latest["latest"] else None,
            "fetched_at": datetime.now(timezone.utc).isoformat(), "ai_analysis": analysis}
