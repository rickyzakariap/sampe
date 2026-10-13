"""Integrasi Lynk.id: webhook order paid -> lisensi otomatis, halaman aktivasi, pengaturan admin."""
import hashlib
import hmac
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core import db
from auth import (get_admin, new_license, new_code, extend_fields, public_license, license_status,
                  check_lock, record_fail, client_ip)

router = APIRouter(prefix="/api")
log = logging.getLogger("lynk")


def days_from_title(title: str) -> Optional[int]:
    t = (title or "").lower()
    if re.search(r"\b(1|satu)\s*tahun\b", t) or re.search(r"\b365\s*hari\b", t):
        return 365
    m = re.search(r"\b(30|7|1)\s*hari\b", t)
    return int(m.group(1)) if m else None


async def lynk_settings() -> dict:
    return await db.settings.find_one({"key": "lynk"}, {"_id": 0}) or {"key": "lynk"}


def _pick(d: dict, *keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return None


def parse_payload(body: dict) -> dict:
    data = body.get("data") or body
    md = data.get("message_data") or data
    cust = md.get("customer") or {}
    items = md.get("items") or []
    totals = md.get("totals") or {}
    return {
        "ref_id": str(_pick(md, "ref_id", "refId", "order_id") or ""),
        "message_id": str(_pick(data, "message_id", "messageId") or _pick(md, "message_id") or ""),
        "email": str(_pick(cust, "email") or _pick(md, "email") or "").strip().lower(),
        "name": _pick(cust, "name") or _pick(md, "name") or "",
        "phone": _pick(cust, "phone") or "",
        "items": [{"title": i.get("title") or i.get("name") or "", "qty": int(i.get("qty") or 1)} for i in items],
        "amounts": [str(v) for v in (totals.get("grandTotal"), totals.get("grand_total"), md.get("amount")) if v is not None],
        "event": body.get("event") or "",
    }


def signature_ok(p: dict, sig: str, key: str) -> bool:
    if not sig:
        return False
    for amt in p["amounts"] + [str(int(float(a))) for a in p["amounts"] if a.replace(".", "", 1).isdigit()]:
        expected = hashlib.sha256(f"{amt}{p['ref_id']}{p['message_id']}{key}".encode()).hexdigest()
        if hmac.compare_digest(expected, sig.strip().lower()):
            return True
    return False


async def grant_license(email: str, name: str, days: int) -> tuple[dict, str]:
    owner = await db.members.find_one({"email": email}, {"_id": 0, "user_id": 1})
    q = {"revoked": False, "$or": [{"email": email}] + ([{"owner_user_id": owner["user_id"]}] if owner else [])}
    lic = await db.licenses.find_one(q, {"_id": 0}, sort=[("created_at", -1)])
    if lic:
        upd = extend_fields(lic, days)
        await db.licenses.update_one({"id": lic["id"]}, {"$set": upd})
        return lic | upd, "extended"
    lic = new_license(name or email, days, email, "lynk") | {"code": await new_code()}
    await db.licenses.insert_one(dict(lic))
    return lic, "created"


async def _log(status: str, reason: str, request: Request, raw: str, ref_id: str = ""):
    await db.webhook_logs.insert_one({"received_at": datetime.now(timezone.utc).isoformat(), "status": status, "reason": reason,
                                      "ref_id": ref_id, "has_signature": bool(request.headers.get("X-Lynk-Signature") or request.headers.get("X-Signature")),
                                      "header_names": sorted(k for k in request.headers.keys() if k.lower().startswith("x-")),
                                      "body": raw[:3000]})
    ids = [d["_id"] async for d in db.webhook_logs.find({}, {"_id": 1}).sort("received_at", -1).skip(50)]
    if ids:
        await db.webhook_logs.delete_many({"_id": {"$in": ids}})


@router.get("/webhooks/lynk")
async def lynk_webhook_ping():
    return {"ok": True, "service": "SAMPE webhook Lynk.id"}


@router.post("/webhooks/lynk")
async def lynk_webhook(request: Request):
    raw = (await request.body()).decode("utf-8", "ignore")
    try:
        body = json.loads(raw) if raw.strip() else {}
    except ValueError:
        await _log("ignored", "Body bukan JSON (tes koneksi)", request, raw)
        return {"ok": True, "processed": False, "reason": "test/ping diterima"}
    p = parse_payload(body if isinstance(body, dict) else {})
    key = (await lynk_settings()).get("merchant_key")
    if not key:
        await _log("ignored", "Merchant key belum diatur — webhook diterima tapi tidak diproses", request, raw, p["ref_id"])
        return {"ok": True, "processed": False, "reason": "merchant key belum diatur"}
    if not p["ref_id"] or not p["email"]:
        await _log("ignored", "Payload tanpa ref_id/email (kemungkinan tes dari Lynk)", request, raw, p["ref_id"])
        return {"ok": True, "processed": False, "reason": "payload tes / tidak lengkap"}
    if p["event"] and p["event"] != "payment.received":
        await _log("ignored", f"Event {p['event']} tidak diproses", request, raw, p["ref_id"])
        return {"ok": True, "processed": False}
    sig = request.headers.get("X-Lynk-Signature") or request.headers.get("X-Signature") or ""
    if not signature_ok(p, sig, key):
        log.warning("Lynk signature mismatch ref=%s", p["ref_id"])
        await _log("rejected", "Signature tidak cocok — cek Merchant Key", request, raw, p["ref_id"])
        raise HTTPException(401, "Signature tidak valid")
    if await db.lynk_orders.find_one({"ref_id": p["ref_id"]}):
        await _log("duplicate", "Order sudah pernah diproses", request, raw, p["ref_id"])
        return {"ok": True, "duplicate": True}
    order = await process_order(p)
    await _log(order["status"], f"{order['action'] or 'produk tidak dikenali'} · {order['days']} hari", request, raw, p["ref_id"])
    return {"ok": True, "status": order["status"], "action": order["action"]}


async def process_order(p: dict) -> dict:
    default_days = (await lynk_settings()).get("default_days")
    days = sum((days_from_title(i["title"]) or default_days or 0) * i["qty"] for i in p["items"])
    order = {"ref_id": p["ref_id"], "email": p["email"], "name": p["name"], "phone": p["phone"],
             "product": ", ".join(i["title"] for i in p["items"]), "days": days,
             "created_at": datetime.now(timezone.utc).isoformat(), "license_id": None, "action": None,
             "status": "unmatched"}
    if days:
        lic, action = await grant_license(p["email"], p["name"], days)
        order |= {"license_id": lic["id"], "action": action, "status": "processed"}
    await db.lynk_orders.insert_one(dict(order))
    return order


@router.post("/admin/webhook-logs/process")
async def reprocess_log(received_at: str, _: dict = Depends(get_admin)):
    entry = await db.webhook_logs.find_one({"received_at": received_at}, {"_id": 0})
    if not entry:
        raise HTTPException(404, "Log tidak ditemukan")
    try:
        p = parse_payload(json.loads(entry["body"]))
    except ValueError:
        raise HTTPException(400, "Isi webhook bukan JSON")
    if not p["ref_id"] or not p["email"]:
        raise HTTPException(400, "Webhook ini bukan order (tanpa Ref ID/email)")
    if await db.lynk_orders.find_one({"ref_id": p["ref_id"], "status": "processed"}):
        raise HTTPException(409, "Order ini sudah diproses")
    await db.lynk_orders.delete_one({"ref_id": p["ref_id"]})
    order = await process_order(p)
    await db.webhook_logs.update_many({"ref_id": p["ref_id"]}, {"$set": {"status": order["status"], "reason": f"Diproses manual oleh admin · {order['action'] or 'produk tidak dikenali'} · {order['days']} hari"}})
    if order["status"] != "processed":
        raise HTTPException(409, "Durasi produk tidak dikenali. Atur 'Durasi default' dulu lalu coba lagi.")
    return order


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
        raise HTTPException(409, "Order diterima tapi produknya belum dikenali. Admin akan memproses manual.")
    lic = await db.licenses.find_one({"id": order["license_id"]}, {"_id": 0})
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
