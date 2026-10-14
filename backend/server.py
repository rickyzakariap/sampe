from fastapi import FastAPI, APIRouter, HTTPException
from starlette.middleware.cors import CORSMiddleware
import os
import logging
import calendar
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, date

from core import db, client, DB_BACKEND, EMERGENT_LLM_KEY, now_iso, Entry, EntryInput, shift_month
from onboarding import router as onboarding_router
from auth import router as auth_router, get_tenant, require_write, init_auth
from lynk import router as lynk_router
from fastapi import Depends

app = FastAPI()
api_router = APIRouter(prefix="/api")


@api_router.get("/health")
async def health():
    try:
        if DB_BACKEND == "postgres":
            await db.query("SELECT 1")
        else:
            await db.command("ping")
    except Exception as exc:
        logging.warning("Database health check failed: %s", type(exc).__name__)
        raise HTTPException(503, "Service unavailable") from None
    return {"status": "ok"}


# ---------------- Helpers ----------------
def safe_div(a, b):
    return (a / b) if b else 0.0


def month_meta(month: str):
    y, m = int(month[:4]), int(month[5:7])
    days_in_month = calendar.monthrange(y, m)[1]
    today = date.today()
    if today.year == y and today.month == m:
        days_elapsed = today.day
    elif (y, m) < (today.year, today.month):
        days_elapsed = days_in_month
    else:
        days_elapsed = 0
    return days_in_month, max(days_elapsed, 0)


def prorate(target: float, month: str):
    days_in_month, days_elapsed = month_meta(month)
    daily = safe_div(target, days_in_month)
    expected = daily * days_elapsed
    return {
        "monthly_target": round(target, 2),
        "daily_target": round(daily, 2),
        "expected_to_date": round(expected, 2),
        "days_in_month": days_in_month,
        "days_elapsed": days_elapsed,
    }


def status_of(achieved, expected):
    if expected <= 0:
        return "green"
    ratio = achieved / expected
    if ratio >= 1.0:
        return "green"
    if ratio >= 0.8:
        return "amber"
    return "red"


# ---------------- Entry routes ----------------
@api_router.get("/entries")
async def list_entries(module: Optional[str] = None, month: Optional[str] = None, p: dict = Depends(get_tenant)):
    q = {"tenant_id": p["tenant_id"]}
    if module:
        q["module"] = module
    if month:
        q["date"] = {"$regex": f"^{month}"}
    docs = await db.entries.find(q, {"_id": 0}).sort("date", -1).to_list(2000)
    return docs


@api_router.post("/entries")
async def create_entry(payload: EntryInput, p: dict = Depends(require_write)):
    d = Entry(**payload.model_dump()).model_dump() | {"tenant_id": p["tenant_id"]}
    await db.entries.insert_one(dict(d))
    return d


@api_router.delete("/entries/{entry_id}")
async def delete_entry(entry_id: str, p: dict = Depends(require_write)):
    res = await db.entries.delete_one({"id": entry_id, "tenant_id": p["tenant_id"]})
    if res.deleted_count == 0:
        raise HTTPException(404, "Entry tidak ditemukan")
    return {"ok": True}


# ---------------- Dashboard aggregation ----------------
async def build_summary(month: str, tid: str):
    config = await db.kpi_config.find_one({"tenant_id": tid, "month": month}, {"_id": 0})
    if not config:
        config = await db.kpi_config.find_one({"tenant_id": tid, "month": {"$lte": month}}, {"_id": 0}, sort=[("month", -1)]) \
            or await db.kpi_config.find_one({"tenant_id": tid}, {"_id": 0}, sort=[("month", 1)])
    if not config:
        raise HTTPException(404, "Konfigurasi KPI belum di-setup")

    entries = await db.entries.find({"tenant_id": tid, "date": {"$regex": f"^{month}"}}, {"_id": 0}).to_list(5000)

    def sum_mod(mod, key):
        return sum(float(e["data"].get(key, 0) or 0) for e in entries if e["module"] == mod)

    sales_total = sum_mod("sales", "omzet")
    ads_spend = sum_mod("ads", "spend")
    ads_revenue = sum_mod("ads", "revenue")
    branding_spend = sum_mod("branding", "spend")
    campaign_spend = sum_mod("campaign", "budget")
    live_hours = sum_mod("livestream", "duration_hours")
    live_omzet = sum_mod("livestream", "omzet")
    kol_spend = sum_mod("kol", "budget")
    kol_names = {e["data"].get("name") for e in entries if e["module"] == "kol" and e["data"].get("name")}
    kol_realized = len(kol_names)

    today_s = date.today().isoformat()
    missing_today = []
    if today_s.startswith(month):
        filled = {e["module"] for e in entries if e["date"] == today_s}
        missing_today = [m for m in ("sales", "ads", "livestream") if m not in filled]

    # daily sales series for trend + chart
    daily_sales: Dict[str, float] = {}
    for e in entries:
        if e["module"] == "sales":
            daily_sales[e["date"]] = daily_sales.get(e["date"], 0) + float(e["data"].get("omzet", 0) or 0)
    series = sorted(daily_sales.items())

    # trend: last day vs previous day with data
    trend = {"abs": 0, "pct": 0, "direction": "flat"}
    if len(series) >= 2:
        prev_v, last_v = series[-2][1], series[-1][1]
        abs_change = last_v - prev_v
        trend = {
            "abs": round(abs_change, 2),
            "pct": round(safe_div(abs_change, prev_v) * 100, 1),
            "direction": "up" if abs_change > 0 else ("down" if abs_change < 0 else "flat"),
        }

    # ---- breakdowns per module (kontribusi detail) ----
    def ctr(v, base):
        return round(safe_div(v, base) * 100, 1)

    channel: Dict[str, float] = {}
    for e in entries:
        if e["module"] == "sales":
            p = e["data"].get("platform", "Lainnya")
            channel[p] = channel.get(p, 0) + float(e["data"].get("omzet", 0) or 0)
    channel_list = [
        {"platform": k, "omzet": round(v, 2),
         "pct_of_target": ctr(v, config["target_sales"]),
         "pct_of_total": ctr(v, sales_total)}
        for k, v in sorted(channel.items(), key=lambda x: -x[1])
    ]

    ads_grp: Dict[str, Dict[str, float]] = {}
    for e in entries:
        if e["module"] == "ads":
            p = e["data"].get("platform", "Lainnya")
            g = ads_grp.setdefault(p, {"spend": 0, "revenue": 0})
            g["spend"] += float(e["data"].get("spend", 0) or 0)
            g["revenue"] += float(e["data"].get("revenue", 0) or 0)
    ads_period: Dict[str, List[str]] = {}
    for e in entries:
        if e["module"] == "ads":
            d = e["data"]
            p = d.get("platform", "Lainnya")
            ads_period.setdefault(p, []).extend(x for x in [d.get("start_date"), d.get("end_date")] if x)
    ads_bd = [
        {"label": k, "value": round(v["spend"], 2), "revenue": round(v["revenue"], 2),
         "period": f"{min(ads_period[k])} s/d {max(ads_period[k])}" if ads_period.get(k) else None,
         "roi": round(safe_div(v["revenue"], v["spend"]), 2),
         "pct_of_target": ctr(v["spend"], config["budget_ads"]),
         "pct_of_total": ctr(v["spend"], ads_spend)}
        for k, v in sorted(ads_grp.items(), key=lambda x: -x[1]["spend"])
    ]

    def group_sum(mod, key_field, val_field, target):
        g: Dict[str, float] = {}
        for e in entries:
            if e["module"] == mod:
                k = e["data"].get(key_field) or "Lainnya"
                g[k] = g.get(k, 0) + float(e["data"].get(val_field, 0) or 0)
        total = sum(g.values())
        return [
            {"label": k, "value": round(v, 2),
             "pct_of_target": ctr(v, target), "pct_of_total": ctr(v, total)}
            for k, v in sorted(g.items(), key=lambda x: -x[1])
        ]

    breakdowns = {
        "sales": [{"label": c["platform"], "value": c["omzet"],
                   "pct_of_target": c["pct_of_target"], "pct_of_total": c["pct_of_total"]} for c in channel_list],
        "ads": ads_bd,
        "live_revenue": group_sum("livestream", "streamer", "omzet", config["target_live_revenue"]),
        "live_hours": group_sum("livestream", "streamer", "duration_hours", config["target_live_hours"]),
        "branding": group_sum("branding", "type", "spend", config["budget_branding"]),
        "campaign": group_sum("campaign", "name", "budget", config["budget_campaign"]),
        "kol": group_sum("kol", "name", "budget", config["budget_kol"]),
    }

    team: Dict[str, Dict[str, float]] = {}
    for e in entries:
        if e["module"] == "livestream":
            s = e["data"].get("streamer") or "Lainnya"
            t = team.setdefault(s, {"sessions": 0, "hours": 0, "omzet": 0})
            t["sessions"] += 1
            t["hours"] += float(e["data"].get("duration_hours", 0) or 0)
            t["omzet"] += float(e["data"].get("omzet", 0) or 0)
    live_team = [
        {"streamer": k, "sessions": int(v["sessions"]), "hours": round(v["hours"], 1),
         "omzet": round(v["omzet"], 2), "omzet_per_hour": round(safe_div(v["omzet"], v["hours"]), 2),
         "pct_of_target": ctr(v["omzet"], config["target_live_revenue"]),
         "pct_of_total": ctr(v["omzet"], live_omzet)}
        for k, v in sorted(team.items(), key=lambda x: -x[1]["omzet"])
    ]

    def metric(target, achieved):
        pr = prorate(target, month)
        pr["achieved"] = round(achieved, 2)
        pr["achieved_pct"] = round(safe_div(achieved, target) * 100, 1)
        pr["pace_pct"] = round(safe_div(achieved, pr["expected_to_date"]) * 100, 1) if pr["expected_to_date"] else 0
        pr["status"] = status_of(achieved, pr["expected_to_date"])
        pr["gap"] = round(pr["expected_to_date"] - achieved, 2)
        remaining_days = pr["days_in_month"] - pr["days_elapsed"]
        remaining_target = max(target - achieved, 0)
        pr["needed_per_day"] = round(safe_div(remaining_target, remaining_days), 2) if remaining_days > 0 else 0
        return pr

    return {
        "config": config,
        "has_config": config.get("month") == month,
        "month_meta": dict(zip(["days_in_month", "days_elapsed"], month_meta(month))),
        "sales": metric(config["target_sales"], sales_total),
        "ads": {
            **metric(config["budget_ads"], ads_spend),
            "revenue": round(ads_revenue, 2),
            "roi": round(safe_div(ads_revenue, ads_spend), 2),
            "cpa": round(safe_div(ads_spend, max(len([e for e in entries if e['module'] == 'ads']), 1)), 2),
        },
        "branding": metric(config["budget_branding"], branding_spend),
        "campaign": metric(config["budget_campaign"], campaign_spend),
        "live_hours": metric(config["target_live_hours"], live_hours),
        "live_revenue": {**metric(config["target_live_revenue"], live_omzet)},
        "kol": {
            **metric(config["budget_kol"], kol_spend),
            "target_count": config["target_kol_count"],
            "realized_count": kol_realized,
        },
        "trend": trend,
        "sales_series": [{"date": d, "omzet": round(v, 2)} for d, v in series],
        "channel_breakdown": channel_list,
        "breakdowns": breakdowns,
        "live_team": live_team,
        "missing_today": missing_today,
    }


@api_router.get("/compare")
async def compare_months(month: str, count: int = 3, p: dict = Depends(get_tenant)):
    tid = p["tenant_id"]
    fallback = await db.kpi_config.find_one({"tenant_id": tid}, {"_id": 0}, sort=[("month", -1)])
    out = []
    for i in range(count - 1, -1, -1):
        mo = shift_month(month, -i)
        cfg = await db.kpi_config.find_one({"tenant_id": tid, "month": mo}, {"_id": 0}) or fallback or {}
        ents = await db.entries.find({"tenant_id": tid, "date": {"$regex": f"^{mo}"}, "module": {"$in": ["sales", "ads", "livestream"]}}, {"_id": 0}).to_list(5000)

        def s(mod, key):
            return sum(float(e["data"].get(key, 0) or 0) for e in ents if e["module"] == mod)

        sales = s("sales", "omzet")
        target = float(cfg.get("target_sales", 0) or 0)
        out.append({
            "month": mo,
            "sales": round(sales, 2),
            "ads_spend": round(s("ads", "spend"), 2),
            "live_omzet": round(s("livestream", "omzet"), 2),
            "target_sales": target,
            "achieved_pct": round(safe_div(sales, target) * 100, 1),
        })
    return out


@api_router.get("/dashboard")
async def dashboard(month: str, p: dict = Depends(get_tenant)):
    return await build_summary(month, p["tenant_id"])


@api_router.get("/months")
async def list_months(p: dict = Depends(get_tenant)):
    cfg_months = await db.kpi_config.distinct("month", {"tenant_id": p["tenant_id"]})
    entry_dates = await db.entries.distinct("date", {"tenant_id": p["tenant_id"]})
    entry_months = {d[:7] for d in entry_dates if d}
    months = sorted(set(cfg_months) | entry_months, reverse=True)
    today = date.today()
    cur = f"{today.year}-{today.month:02d}"
    if cur not in months:
        months = sorted(set(months) | {cur}, reverse=True)
    return months


# ---------------- AI Analysis ----------------
class AiRequest(BaseModel):
    month: str


@api_router.post("/ai/analyze")
async def ai_analyze(payload: AiRequest, p: dict = Depends(require_write)):
    summary = await build_summary(payload.month, p["tenant_id"])
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    cfg = summary["config"]
    mm = summary["month_meta"]

    def fmt(v):
        return f"{v:,.0f}".replace(",", ".")

    labels = [("sales", "Penjualan", "rp"), ("ads", "Belanja Ads", "rp"),
              ("branding", "Branding", "rp"), ("campaign", "Campaign", "rp"),
              ("live_hours", "Durasi Live", "jam"), ("live_revenue", "Omzet Live", "rp"),
              ("kol", "Budget KOL", "rp")]

    reds = []
    kpi_lines = []
    for key, label, unit in labels:
        m = summary[key]
        pre = "" if unit == "jam" else "Rp"
        suf = " jam" if unit == "jam" else ""
        line = (f"- {label}: tercapai {pre}{fmt(m['achieved'])}{suf} dari target bulan {pre}{fmt(m['monthly_target'])}{suf} "
                f"({m['achieved_pct']:.0f}%), target prorata s/d hari ini {pre}{fmt(m['expected_to_date'])}{suf}, status {m['status']}.")
        if m["gap"] > 0:
            line += f" Kurang {pre}{fmt(m['gap'])}{suf}, perlu {pre}{fmt(m['needed_per_day'])}{suf}/hari."
        kpi_lines.append(line)
        if m.get("status") in ("red", "amber"):
            if m["gap"] > 0:
                reds.append(f"{label}: baru {m['achieved_pct']:.0f}% dari target, kurang {pre}{fmt(m['gap'])}{suf}, perlu {pre}{fmt(m['needed_per_day'])}{suf}/hari.")
            else:
                reds.append(f"{label}: {m['achieved_pct']:.0f}% dari target, hampir tercapai tapi perlu dijaga.")

    channel_txt = "\n".join(
        f"- {c['platform']}: Rp{fmt(c['omzet'])} (baru {c['pct_of_target']:.0f}% dari target penjualan, {c['pct_of_total']:.0f}% dari total omzet toko)"
        for c in summary["channel_breakdown"]
    )
    ads = summary["ads"]
    context = (
        f"Toko: {cfg['company_name']}. Periode {payload.month}, baru jalan {mm['days_elapsed']} dari {mm['days_in_month']} hari "
        f"(sekitar {mm['days_elapsed']/mm['days_in_month']*100:.0f}% bulan sudah lewat).\n\n"
        f"KONDISI KPI:\n" + "\n".join(kpi_lines) + "\n\n"
        f"EFISIENSI IKLAN: tiap Rp1 belanja iklan menghasilkan Rp{ads['roi']:.2f} omzet.\n\n"
        f"KONTRIBUSI PENJUALAN PER CHANNEL:\n{channel_txt}\n\n"
        f"TREN HARIAN: penjualan hari terakhir {summary['trend']['direction']} {abs(summary['trend']['pct']):.0f}% dibanding hari sebelumnya.\n"
        f"KOL: {summary['kol']['realized_count']} aktif dari target {summary['kol']['target_count']} KOL."
    )

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"kpi-{payload.month}-{datetime.now().timestamp()}",
        system_message=(
            "Kamu konsultan bisnis praktis untuk penjual marketplace & UMKM Indonesia yang awam istilah teknis. "
            "Baca data KPI toko di bawah dan beri analisa yang BENAR-BENAR berdasarkan angka nyata di data, bukan saran umum. "
            "Setiap poin WAJIB menyebut angka/channel/selisih dari data (mis. 'Shopee baru 12% dari target', 'kurang Rp5 juta', 'tren turun 22%'). "
            "Pakai bahasa sehari-hari yang sederhana; kalau pakai istilah (omzet, ROI), jelaskan singkat. Hindari jargon seperti pace/AOV/CPA tanpa penjelasan. "
            "Format jawaban dalam Bahasa Indonesia TANPA sapaan pembuka, persis seperti ini:\n\n"
            "KONDISI SAAT INI:\n2-3 kalimat merangkum yang sedang terjadi berdasarkan data (channel mana kuat/lemah, tren, KPI yang bahaya).\n\n"
            "REKOMENDASI AKSI:\n1-5 langkah bernomor yang konkret & bisa langsung dikerjakan seller, tiap langkah sebut angka/channel spesifik + perkiraan dampaknya ke target.\n\n"
            "TARGET REALISTIS:\n1 kalimat berapa yang harus dikejar per hari di sisa bulan agar target tercapai."
        ),
    ).with_model("openai", "gpt-5.4")

    try:
        resp = await chat.send_message(UserMessage(text=context))
    except Exception as e:
        logging.exception("AI error")
        raise HTTPException(500, f"Gagal memanggil AI: {e}")

    return {"analysis": resp, "reds": reds, "generated_at": now_iso()}


app.include_router(api_router)
app.include_router(onboarding_router)
app.include_router(auth_router)
app.include_router(lynk_router)


@app.on_event("startup")
async def startup():
    if DB_BACKEND == "postgres":
        await db.validate_target()
    await init_auth()

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[origin.strip() for origin in os.environ.get('CORS_ORIGINS', 'http://localhost:3000').split(',') if origin.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
