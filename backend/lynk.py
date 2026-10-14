"""Integrasi Lynk.id: webhook order paid -> lisensi otomatis, halaman aktivasi, pengaturan admin."""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from core import db, DB_BACKEND
if DB_BACKEND == "mongo":
    from pymongo.errors import DuplicateKeyError, PyMongoError
else:
    class PyMongoError(Exception):
        pass

    class DuplicateKeyError(PyMongoError):
        pass
from auth import (get_admin, new_license, new_code, public_license, license_status,
                  check_lock, record_fail, client_ip)
from license_rules import renewal_expires_at
from lynk_contract import (SAMPE_PRODUCT, SAMPE_PRODUCT_DAYS, valid_buyer_email,
                           parse_payload, signature_amount, signature_ok, product_days)

router = APIRouter(prefix="/api")
log = logging.getLogger("lynk")


async def lynk_settings() -> dict:
    return await db.settings.find_one({"key": "lynk"}, {"_id": 0}) or {"key": "lynk"}


async def grant_license(email: str, name: str, days: int, ref_id: str, session) -> tuple[Optional[dict], str]:
    owner = await db.members.find_one({"email": email}, {"_id": 0, "user_id": 1}, session=session)
    q = {"revoked": False, "$or": [{"email": email}] + ([{"owner_user_id": owner["user_id"]}] if owner else [])}
    lic = await db.licenses.find_one(q, {"_id": 0}, sort=[("created_at", -1)], session=session)
    if lic:
        if not lic.get("activated_at") or not lic.get("expires_at"):
            return None, "pending_policy"
        upd = {"expires_at": renewal_expires_at(lic, days, datetime.now(timezone.utc))}
        result = await db.licenses.update_one({"id": lic["id"], "revoked": False}, {"$set": upd}, session=session)
        if result.matched_count != 1:
            raise PyMongoError("Lisensi renewal tidak tersedia")
        return lic | upd, "extended"
    lic = new_license(name or email, days, email, "lynk") | {"code": await new_code(), "lynk_ref_id": ref_id}
    await db.licenses.insert_one(dict(lic), session=session)
    return lic, "created"


async def _log(status: str, reason: str, request: Request, ref_id: str = ""):
    try:
        await db.webhook_logs.insert_one({
            "received_at": datetime.now(timezone.utc).isoformat(),
            "status": status, "reason": reason, "ref_id": ref_id[:80],
            "has_signature": bool(request.headers.get("X-Lynk-Signature")),
            "body": None,
        })
    except Exception as exc:
        log.error("Lynk webhook log write failed: %s", type(exc).__name__)


@router.get("/webhooks/lynk")
async def lynk_webhook_ping():
    return {"ok": True, "service": "SAMPE webhook Lynk.id"}


@router.post("/webhooks/lynk")
async def lynk_webhook(request: Request):
    try:
        body = json.loads(await request.body())
        p = parse_payload(body)
    except (ValueError, UnicodeDecodeError, TypeError):
        await _log("rejected", "Payload JSON tidak valid", request)
        raise HTTPException(400, "Payload JSON tidak valid")
    if p["event"] != "payment.received":
        await _log("ignored", "Event bukan payment.received", request, p["ref_id"])
        return {"ok": True, "processed": False, "reason": "event diabaikan"}
    if not p["ref_id"] or not valid_buyer_email(p["email"]) or not p["message_id"] or signature_amount(p["grand_total"]) is None:
        await _log("rejected", "Field transaksi wajib tidak tersedia", request, p["ref_id"])
        raise HTTPException(400, "Field transaksi wajib tidak tersedia")
    key = (await lynk_settings()).get("merchant_key")
    if not key:
        await _log("failed", "Merchant Key belum dikonfigurasi", request, p["ref_id"])
        raise HTTPException(503, "Merchant Key belum dikonfigurasi")
    sig = request.headers.get("X-Lynk-Signature") or ""
    if not signature_ok(p, sig, key):
        log.warning("Lynk webhook signature mismatch")
        await _log("rejected", "Signature tidak valid", request, p["ref_id"])
        raise HTTPException(401, "Signature tidak valid")
    if p["message_action"] != "SUCCESS" or str(p["message_code"]) != "0":
        await _log("ignored", "Pembayaran belum SUCCESS", request, p["ref_id"])
        return {"ok": True, "processed": False, "reason": "status pembayaran diabaikan"}
    try:
        order, duplicate = await process_order(p)
    except Exception as exc:
        if DB_BACKEND == "postgres":
            from postgres.access import PolicyDecisionRequired
            if isinstance(exc, PolicyDecisionRequired):
                await _log("pending_policy", "Renewal lisensi dicabut menunggu keputusan", request, p["ref_id"])
                raise HTTPException(409, "Order memerlukan keputusan kebijakan lisensi")
        log.error("Lynk order transaction failed: %s", type(exc).__name__)
        await _log("failed", "Transaksi database gagal", request, p["ref_id"])
        raise HTTPException(503, "Order gagal diproses sementara; aman untuk retry")
    if duplicate:
        await _log("duplicate", "Ref ID sudah tercatat", request, p["ref_id"])
        return {"ok": True, "duplicate": True, "processed": order["status"] == "processed"}
    await _log(order["status"], "Order dicatat", request, p["ref_id"])
    return {"ok": True, "processed": order["status"] == "processed", "status": order["status"], "action": order["action"]}


async def process_order(p: dict) -> tuple[dict, bool]:
    if DB_BACKEND == "postgres":
        from starlette.concurrency import run_in_threadpool
        from postgres.access import PostgresAccess
        result = await run_in_threadpool(PostgresAccess(db.dsn)._process_order, p)
        return result, result["duplicate"]
    days, _ = product_days(p["items"])
    order = {"ref_id": p["ref_id"], "message_id": p["message_id"], "email": p["email"], "name": p["name"], "phone": p["phone"],
             "product": ", ".join(i["title"] for i in p["items"]), "days": days,
             "created_at": datetime.now(timezone.utc).isoformat(), "license_id": None, "action": None,
             "status": "unmatched"}
    try:
        async with await db.client.start_session() as session:
            async with session.start_transaction():
                existing = await db.lynk_orders.find_one({"ref_id": p["ref_id"]}, {"_id": 0}, session=session)
                if existing:
                    return existing, True
                if days:
                    await db.lynk_email_locks.update_one(
                        {"_id": p["email"]}, {"$set": {"touched_at": datetime.now(timezone.utc).isoformat()}},
                        upsert=True, session=session)
                    lic, action = await grant_license(p["email"], p["name"], days, p["ref_id"], session)
                    if lic:
                        order.update({"license_id": lic["id"], "action": action, "status": "processed"})
                    else:
                        order.update({"action": action, "status": "pending_policy"})
                await db.lynk_orders.insert_one(dict(order), session=session)
                return order, False
    except (DuplicateKeyError, PyMongoError):
        existing = await db.lynk_orders.find_one({"ref_id": p["ref_id"]}, {"_id": 0})
        if existing:
            return existing, True
        raise


@router.post("/admin/webhook-logs/process")
async def reprocess_log(received_at: str, _: dict = Depends(get_admin)):
    raise HTTPException(409, "Rekonsiliasi order memerlukan verifikasi dan persetujuan pemilik; endpoint ini tidak menerbitkan lisensi")


@router.get("/admin/webhook-logs")
async def webhook_logs(_: dict = Depends(get_admin)):
    return await db.webhook_logs.find({}, {"_id": 0}).sort("received_at", -1).to_list(20)


class ActivationIn(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    ref_id: str = Field(min_length=3, max_length=80)


@router.post("/activation/lookup")
async def activation_lookup(payload: ActivationIn, request: Request):
    ident = f"activation:{client_ip(request)}"
    await check_lock(ident)
    order = await db.lynk_orders.find_one({"ref_id": payload.ref_id.strip(), "email": payload.email.strip().lower()}, {"_id": 0})
    if not order:
        await record_fail(ident)
        raise HTTPException(404, "Order tidak ditemukan. Cek lagi email & Ref ID dari Lynk, atau tunggu 1–2 menit setelah bayar.")
    if not order.get("license_id"):
        if order.get("status") == "pending_policy":
            raise HTTPException(409, "Order menunggu keputusan kebijakan pembelian ulang. Hubungi admin.")
        raise HTTPException(409, "Order diterima tapi produknya belum dikenali. Admin akan memproses manual.")
    lic = await db.licenses.find_one({"id": order["license_id"]}, {"_id": 0})
    if not lic:
        raise HTTPException(409, "Lisensi terkait order tidak tersedia. Hubungi admin.")
    return {"code": lic["code"], "action": order["action"], "days": order["days"], "status": license_status(lic),
            "expires_at": lic.get("expires_at"), "duration_days": lic["duration_days"], "email": order["email"]}


class SettingsIn(BaseModel):
    merchant_key: Optional[str] = None
    renew_url: Optional[str] = None
    default_days: Optional[int] = None


@router.get("/admin/lynk")
async def get_lynk(_: dict = Depends(get_admin)):
    s = await lynk_settings()
    key = s.get("merchant_key") or ""
    return {"merchant_key_set": bool(key), "merchant_key_hint": f"…{key[-4:]}" if key else None, "renew_url": s.get("renew_url"), "default_days": s.get("default_days")}


@router.put("/admin/lynk")
async def put_lynk(payload: SettingsIn, _: dict = Depends(get_admin)):
    upd = {}
    if payload.merchant_key is not None and payload.merchant_key.strip():
        upd["merchant_key"] = payload.merchant_key.strip()
    if payload.renew_url is not None:
        url = payload.renew_url.strip()
        if url and not url.startswith("https://"):
            raise HTTPException(400, "Link perpanjang harus diawali https://")
        upd["renew_url"] = url or None
    if payload.default_days is not None:
        if payload.default_days not in (0, 1, 7, 30, 365):
            raise HTTPException(400, "Durasi default harus 1, 7, 30, atau 365 hari")
        upd["default_days"] = payload.default_days or None
    await db.settings.update_one({"key": "lynk"}, {"$set": upd}, upsert=True)
    return await get_lynk(_)


@router.get("/admin/orders")
async def list_orders(_: dict = Depends(get_admin)):
    orders = await db.lynk_orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    for o in orders:
        lic = await db.licenses.find_one({"id": o.get("license_id")}, {"_id": 0}) if o.get("license_id") else None
        o["license"] = public_license(lic) if lic else None
    return orders
