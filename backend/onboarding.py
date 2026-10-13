"""User flow & onboarding: setup KPI, pengaturan toko, data demo, reset."""
import calendar
from datetime import date
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from core import db, KpiConfig, ConfigInput, Entry, shift_month
from auth import get_tenant, require_write

router = APIRouter(prefix="/api")


# ---------------- Config routes ----------------
@router.get("/config")
async def get_config(p: dict = Depends(get_tenant)):
    doc = await db.kpi_config.find_one({"tenant_id": p["tenant_id"]}, {"_id": 0}, sort=[("month", -1)])
    return doc


@router.post("/config")
async def save_config(payload: ConfigInput, p: dict = Depends(require_write)):
    existing = await db.kpi_config.find_one({"tenant_id": p["tenant_id"], "month": payload.month})
    doc = KpiConfig(**payload.model_dump()).model_dump() | {"tenant_id": p["tenant_id"]}
    if existing:
        doc["id"] = existing.get("id", doc["id"])
        doc["created_at"] = existing.get("created_at", doc["created_at"])
        await db.kpi_config.replace_one({"_id": existing["_id"]}, doc)
    else:
        await db.kpi_config.insert_one(doc)
    doc.pop("_id", None)
    return doc


class CompanyInput(BaseModel):
    company_name: str = Field(min_length=1, max_length=80)


@router.patch("/config/company")
async def update_company(payload: CompanyInput, p: dict = Depends(require_write)):
    name = payload.company_name.strip()
    if not name:
        raise HTTPException(400, "Nama perusahaan wajib diisi")
    await db.kpi_config.update_many({"tenant_id": p["tenant_id"]}, {"$set": {"company_name": name}})
    return await db.kpi_config.find_one({"tenant_id": p["tenant_id"]}, {"_id": 0}, sort=[("month", -1)])


# ---------------- Seed demo data ----------------
class SeedInput(BaseModel):
    company_name: Optional[str] = None


@router.post("/seed")
async def seed_demo(payload: Optional[SeedInput] = None, p: dict = Depends(require_write)):
    tid = p["tenant_id"]
    company = ((payload.company_name if payload else None) or "").strip() or "Toko Demo"
    today = date.today()
    month = f"{today.year}-{today.month:02d}"
    await db.kpi_config.delete_many({"tenant_id": tid})
    await db.entries.delete_many({"tenant_id": tid})

    cfg = KpiConfig(
        company_name=company[:80],
        month=month,
        target_sales=500_000_000,
        budget_ads=60_000_000,
        budget_branding=25_000_000,
        budget_campaign=30_000_000,
        budget_kol=40_000_000,
        target_kol_count=12,
        live_team_count=4,
        target_live_hours=180,
        target_live_revenue=150_000_000,
    )
    await db.kpi_config.insert_one(cfg.model_dump() | {"tenant_id": tid})

    import random
    random.seed(7)
    days_elapsed = min(today.day, 20)
    platforms = ["TikTok", "Shopee", "Tokopedia", "WhatsApp", "Meta", "Lazada", "Website", "Offline"]
    streamers = ["Rani", "Dewi", "Agus", "Sari"]
    entries = []
    for d in range(1, days_elapsed + 1):
        ds = f"{month}-{d:02d}"
        for p in platforms:
            base = {"TikTok": 4_500_000, "Shopee": 6_000_000, "Tokopedia": 3_500_000,
                    "WhatsApp": 2_000_000, "Meta": 1_500_000, "Lazada": 1_800_000,
                    "Website": 1_200_000, "Offline": 2_500_000}[p]
            omzet = int(base * random.uniform(0.6, 1.2))
            entries.append(Entry(module="sales", date=ds, data={"account": f"{p} Official", "platform": p, "omzet": omzet}).model_dump())
        # ads
        for p in ["TikTok", "Shopee", "Meta"]:
            spend = int(random.uniform(1_000_000, 2_200_000))
            rev = int(spend * random.uniform(1.8, 4.5))
            entries.append(Entry(module="ads", date=ds, data={"account": f"{p} Ads", "platform": p, "spend": spend, "revenue": rev, "roi": round(rev/spend, 2), "start_date": ds, "end_date": ds}).model_dump())
        # livestream
        for s in streamers[:2]:
            dur = round(random.uniform(2, 4), 1)
            entries.append(Entry(module="livestream", date=ds, data={"streamer": s, "start_time": "19:00", "end_time": "22:30", "duration_hours": dur, "omzet": int(random.uniform(2_000_000, 7_000_000))}).model_dump())
    # branding
    for t in ["Awareness", "Consideration", "Aktifasi Offline", "Buzzer/Clipper"]:
        entries.append(Entry(module="branding", date=f"{month}-05", data={"type": t, "spend": int(random.uniform(2_000_000, 5_000_000)), "note": t}).model_dump())
    # campaign
    for c in ["Flash Sale 6.6", "Voucher Gratis Ongkir", "Tanggal Kembar 7.7"]:
        entries.append(Entry(module="campaign", date=f"{month}-06", data={"name": c, "duration_days": 3, "budget": int(random.uniform(5_000_000, 9_000_000))}).model_dump())
    # kol
    events = ["Flash Sale 6.6", "Review Produk", "Unboxing", "Live Collab", "Giveaway"]
    products = ["Produk Best Seller", "Produk Baru", "Paket Bundling", "Produk Promo"]
    for i in range(1, 8):
        entries.append(Entry(module="kol", date=f"{month}-0{min(i,9)}", data={"name": f"KOL Micro {i}", "budget": int(random.uniform(2_000_000, 5_000_000)), "event": events[i % len(events)], "product": products[i % len(products)]}).model_dump())
    # previous 2 months (for month comparison)
    for back in (1, 2):
        pm = shift_month(month, -back)
        pdays = calendar.monthrange(int(pm[:4]), int(pm[5:7]))[1]
        factor = 0.85 if back == 1 else 0.7
        for d in range(1, pdays + 1):
            ds = f"{pm}-{d:02d}"
            for p, base in [("TikTok", 5_500_000), ("Shopee", 7_000_000), ("Tokopedia", 4_000_000), ("Offline", 3_000_000)]:
                entries.append(Entry(module="sales", date=ds, data={"account": f"{p} Official", "platform": p, "omzet": int(base * factor * random.uniform(0.7, 1.2))}).model_dump())
            spend = int(random.uniform(1_500_000, 2_500_000) * factor)
            entries.append(Entry(module="ads", date=ds, data={"account": "Meta Ads", "platform": "Meta", "spend": spend, "revenue": int(spend * 3), "roi": 3.0, "start_date": ds, "end_date": ds}).model_dump())
            entries.append(Entry(module="livestream", date=ds, data={"streamer": streamers[d % 4], "start_time": "19:00", "end_time": "22:00", "duration_hours": 3, "omzet": int(random.uniform(3_000_000, 6_000_000) * factor)}).model_dump())

    if entries:
        await db.entries.insert_many([e | {"tenant_id": tid} for e in entries])
    return {"ok": True, "month": month, "entries": len(entries)}


@router.post("/reset")
async def reset_all(p: dict = Depends(require_write)):
    cfg = await db.kpi_config.delete_many({"tenant_id": p["tenant_id"]})
    ent = await db.entries.delete_many({"tenant_id": p["tenant_id"]})
    return {"ok": True, "deleted_config": cfg.deleted_count, "deleted_entries": ent.deleted_count}


TARGET_FIELDS = ["target_sales", "budget_ads", "budget_branding", "budget_campaign", "budget_kol",
                 "target_kol_count", "live_team_count", "target_live_hours", "target_live_revenue"]


@router.get("/config/history")
async def config_history(p: dict = Depends(get_tenant)):
    docs = await db.kpi_config.find({"tenant_id": p["tenant_id"]}, {"_id": 0}).sort("month", 1).to_list(120)
    out, prev = [], None
    for d in docs:
        row = {"month": d["month"], "values": {k: d.get(k, 0) for k in TARGET_FIELDS}, "change_pct": {}}
        for k in TARGET_FIELDS:
            pv = prev["values"][k] if prev else None
            row["change_pct"][k] = round((d.get(k, 0) - pv) / pv * 100, 1) if pv else None
        out.append(row)
        prev = row
    return out
