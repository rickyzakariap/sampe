"""SumoPod AI transport and tenant-scoped saved KPI analyses."""

import hashlib
import json
import logging
import os

import httpx
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from psycopg.types.json import Jsonb

from core import db

ENDPOINT = "https://ai.sumopod.com/v1/chat/completions"
SYSTEM_PROMPT = (
    "Kamu konsultan bisnis praktis untuk seller marketplace dan UMKM Indonesia. "
    "Gunakan hanya angka dan periode KPI yang diberikan. Jangan mengarang angka, "
    "channel, sebab, atau dampak. Jika data tidak cukup, nyatakan keterbatasannya. "
    "Jawab singkat dalam Bahasa Indonesia dengan bagian KONDISI SAAT INI, "
    "REKOMENDASI AKSI, dan TARGET REALISTIS. Jelaskan KPI yang tertinggal, "
    "tren yang tersedia, dan langkah yang dapat dikerjakan berdasarkan data."
)


async def source_fingerprint(tenant_id: str, month: str) -> str:
    config = await db.kpi_config.find_one({"tenant_id": tenant_id, "month": month}, {"_id": 0})
    if not config:
        config = await db.kpi_config.find_one({"tenant_id": tenant_id, "month": {"$lte": month}},
                                              {"_id": 0}, sort=[("month", -1)]) \
            or await db.kpi_config.find_one({"tenant_id": tenant_id}, {"_id": 0}, sort=[("month", 1)])
    entries = await db.entries.find({"tenant_id": tenant_id, "date": {"$regex": f"^{month}"}},
                                    {"_id": 0}).to_list(5000)
    payload = {"config": config, "entries": sorted(entries, key=lambda item: item["id"])}
    canonical = json.dumps(jsonable_encoder(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def request_analysis(context: str) -> tuple[str, str]:
    key = os.environ.get("SUMOPOD_AI_API_KEY", "")
    if not key:
        raise HTTPException(503, "Layanan Analisa AI belum dikonfigurasi")
    model = os.environ.get("SUMOPOD_AI_MODEL", "gpt-4o-mini").strip()
    if not model:
        raise HTTPException(503, "Model Analisa AI belum dikonfigurasi")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                ENDPOINT,
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": context},
                ], "temperature": 0.2},
            )
    except httpx.RequestError as exc:
        logging.warning("SumoPod AI network failure: %s", type(exc).__name__)
        raise HTTPException(502, "Layanan Analisa AI tidak dapat dihubungi") from None
    if response.status_code != 200:
        logging.warning("SumoPod AI response status: %s", response.status_code)
        raise HTTPException(502, "Layanan Analisa AI menolak permintaan; periksa konfigurasi provider")
    try:
        analysis = response.json()["choices"][0]["message"]["content"]
        if not isinstance(analysis, str) or not analysis.strip():
            raise ValueError("empty content")
    except (ValueError, KeyError, IndexError, TypeError):
        logging.warning("SumoPod AI returned an invalid response shape")
        raise HTTPException(502, "Respons Analisa AI tidak valid") from None
    return analysis.strip(), model


async def save_analysis(tenant_id: str, month: str, source_hash: str,
                        analysis: str, reds: list[str], model: str) -> dict:
    row = await db.query(
        "INSERT INTO sampe.ai_analyses(tenant_id,month,scope,source_hash,analysis,reds,model) "
        "VALUES (%s,%s,'overall',%s,%s,%s,%s) "
        "ON CONFLICT (tenant_id,month,scope) DO UPDATE SET source_hash=EXCLUDED.source_hash, "
        "analysis=EXCLUDED.analysis,reds=EXCLUDED.reds,model=EXCLUDED.model,generated_at=now() "
        "RETURNING generated_at",
        (tenant_id, month, source_hash, analysis, Jsonb(reds), model),
    )
    return {"analysis": analysis, "reds": reds, "generated_at": row["generated_at"].isoformat()}


async def cached_analysis(tenant_id: str, month: str, current_hash: str) -> dict | None:
    row = await db.query(
        "SELECT analysis,reds,generated_at,source_hash FROM sampe.ai_analyses "
        "WHERE tenant_id=%s AND month=%s AND scope='overall'", (tenant_id, month),
    )
    if not row:
        return None
    return {"analysis": row["analysis"], "reds": row["reds"],
            "generated_at": row["generated_at"].isoformat(),
            "stale": row["source_hash"] != current_hash}
