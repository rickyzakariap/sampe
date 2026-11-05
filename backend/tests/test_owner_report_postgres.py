"""Disposable PostgreSQL acceptance for Owner Report and saved AI results."""

import asyncio
import logging
import os
import secrets
import sys
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import urlparse

import httpx
import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def guard():
    target = urlparse(os.environ.get("SAMPE_POSTGRES_DSN", ""))
    if (os.environ.get("SAMPE_DB_BACKEND") != "postgres"
            or os.environ.get("SAMPE_POSTGRES_ENV") != "testing"
            or os.environ.get("SAMPE_POSTGRES_TARGET_DB") != "sampe_owner_test"
            or target.hostname != "127.0.0.1" or target.port != 55433
            or target.path != "/sampe_owner_test"):
        raise RuntimeError("Only the dedicated local Owner Report database is permitted")


async def run():
    guard()
    os.environ["OWNER_REPORT_SECRET"] = secrets.token_urlsafe(48)
    os.environ["SUMOPOD_AI_API_KEY"] = secrets.token_urlsafe(32)
    os.environ["SUMOPOD_AI_MODEL"] = "gpt-4o-mini"
    logging.getLogger("httpx").setLevel(logging.WARNING)
    import ai_analysis
    import server

    checks = []

    def check(label, okay):
        if not okay:
            raise AssertionError(label)
        checks.append(label)

    tag = secrets.token_hex(5)
    tenants = [f"owner-{tag}-a", f"owner-{tag}-b"]
    sessions = [secrets.token_urlsafe(32), secrets.token_urlsafe(32)]
    with psycopg.connect(os.environ["SAMPE_POSTGRES_DSN"], row_factory=dict_row) as conn:
        check("isolated database", conn.execute("SELECT current_database() AS d").fetchone()["d"] == "sampe_owner_test")
        tables = {r["tablename"] for r in conn.execute(
            "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='sampe'")}
        check("final tables", {"owner_report_links", "owner_report_rate_limits", "ai_analyses"}.issubset(tables)
              and "owner_report_sessions" not in tables and len(tables) == 14)
        check("migration markers", [r["version"] for r in conn.execute(
            "SELECT version FROM public.sampe_schema_migrations ORDER BY version")]
              == ["0001_initial", "0002_owner_report", "0003_ai_analysis"])
        for index, tenant in enumerate(tenants):
            member = f"member-{tenant}"
            conn.execute("INSERT INTO sampe.members(user_id,email,created_at) VALUES (%s,%s,now())",
                         (member, f"{member}@example.invalid"))
            conn.execute("INSERT INTO sampe.licenses(id,label,source,duration_days,created_at,activated_at,expires_at,owner_user_id) "
                         "VALUES (%s,'Synthetic','test',30,now(),now(),now()+interval '30 days',%s)",
                         (tenant, member))
            conn.execute("INSERT INTO sampe.user_sessions(session_token,user_id,expires_at,created_at) "
                         "VALUES (%s,%s,now()+interval '1 day',now())", (sessions[index], member))
            conn.execute("INSERT INTO sampe.kpi_config(id,tenant_id,company_name,month,created_at) "
                         "VALUES (%s,%s,%s,'2026-10',now())",
                         (f"config-{tenant}", tenant, "Tokopi" if index == 0 else "Toko Dua"))
            conn.execute("INSERT INTO sampe.entries(id,tenant_id,module,date,data,created_at) "
                         "VALUES (%s,%s,'sales','2026-10-16',%s,now())",
                         (f"entry-{tenant}", tenant, Jsonb({"omzet": 11 if index == 0 else 99})))

    transport = httpx.ASGITransport(app=server.app, client=("192.0.2.20", 12000))
    async with httpx.AsyncClient(transport=transport, base_url="https://owner.test") as client:
        bearer_a = {"Authorization": "Bearer " + sessions[0]}
        bearer_b = {"Authorization": "Bearer " + sessions[1]}
        check("manager requires Google session", (await client.post("/api/owner-report/manage")).status_code == 401)
        created_a = await client.post("/api/owner-report/manage", headers=bearer_a)
        check("create tenant A link", created_a.status_code == 200 and created_a.json()["slug"] == "tokopi")
        share_a = created_a.json()["slug"] + "-" + created_a.json()["token"]
        check("256-bit random token", len(created_a.json()["token"]) == 43)
        stored = await server.db.query("SELECT slug,link_hash FROM sampe.owner_report_links WHERE tenant_id=%s",
                                       (tenants[0],))
        check("token hash only", stored["link_hash"] != created_a.json()["token"]
              and stored["link_hash"] == ai_hash(created_a.json()["token"]))
        repeat = await client.get("/api/owner-report/manage", headers=bearer_a)
        check("share again returns identical URL", repeat.status_code == 200
              and repeat.json()["slug"] == created_a.json()["slug"]
              and repeat.json()["token"] == created_a.json()["token"])
        head_a = {"X-Owner-Report-Link": share_a}
        report_a = await client.get("/api/owner-report/data?month=2026-10", headers=head_a)
        check("no login or OTP", report_a.status_code == 200 and len(report_a.json()["entries"]) == 1)
        check("tenant A only", report_a.json()["entries"][0]["data"]["omzet"] == 11)
        check("no-store report", "no-store" in report_a.headers.get("cache-control", ""))
        check("no AI before generation", report_a.json()["ai_analysis"] is None)
        denied = await client.post("/api/entries", headers=head_a,
                                   json={"module": "sales", "date": "2026-10-16", "data": {"omzet": 3}})
        check("share link cannot write KPI", denied.status_code == 401)

        created_b = await client.post("/api/owner-report/manage", headers=bearer_b)
        share_b = created_b.json()["slug"] + "-" + created_b.json()["token"]
        report_b = await client.get("/api/owner-report/data?month=2026-10",
                                    headers={"X-Owner-Report-Link": share_b})
        check("tenant B isolated", report_b.status_code == 200
              and report_b.json()["entries"][0]["data"]["omzet"] == 99)

        calls = []
        async def synthetic_provider(context):
            calls.append(context)
            return "KONDISI SAAT INI: omzet 11 dari data sintetis.", "mock-model"

        with patch.object(ai_analysis, "request_analysis", synthetic_provider):
            generated = await client.post("/api/ai/analyze", json={"month": "2026-10"}, headers=bearer_a)
        check("existing AI endpoint saves result", generated.status_code == 200
              and "omzet 11" in generated.json()["analysis"] and len(calls) == 1)
        refreshed = await client.get("/api/owner-report/data?month=2026-10", headers=head_a)
        check("refresh reads saved AI", refreshed.json()["ai_analysis"]["analysis"] == generated.json()["analysis"]
              and len(calls) == 1 and not refreshed.json()["ai_analysis"]["stale"])
        await server.db.execute("INSERT INTO sampe.entries(id,tenant_id,module,date,data,created_at) "
                                "VALUES (%s,%s,'sales','2026-10-17',%s,now())",
                                (f"entry-new-{tag}", tenants[0], Jsonb({"omzet": 22})))
        newest = await client.get("/api/owner-report/data?month=2026-10", headers=head_a)
        check("refresh returns new KPI data", newest.status_code == 200 and len(newest.json()["entries"]) == 2)
        check("saved AI marked stale, not regenerated", newest.json()["ai_analysis"]["stale"] and len(calls) == 1)
        check("AI tenant isolation", (await client.get("/api/owner-report/data?month=2026-10",
              headers={"X-Owner-Report-Link": share_b})).json()["ai_analysis"] is None)

        rotated = await client.post("/api/owner-report/rotate", headers=bearer_a)
        check("rotate changes token", rotated.status_code == 200 and rotated.json()["token"] != created_a.json()["token"])
        check("old URL rejected", (await client.get("/api/owner-report/data?month=2026-10", headers=head_a)).status_code == 404)
        new_head = {"X-Owner-Report-Link": rotated.json()["slug"] + "-" + rotated.json()["token"]}
        check("new URL works", (await client.get("/api/owner-report/data?month=2026-10", headers=new_head)).status_code == 200)
        await client.delete("/api/owner-report/manage", headers=bearer_a)
        check("revoke immediately denies", (await client.get("/api/owner-report/data?month=2026-10", headers=new_head)).status_code == 404)

        async def invalid():
            return await client.get("/api/owner-report/data?month=2026-10", headers={"X-Owner-Report-Link": "bad"})
        batch = await asyncio.gather(*(invalid() for _ in range(65)))
        check("concurrent invalid-link rate limit", sum(r.status_code == 429 for r in batch) >= 5)

    real_async_client = httpx.AsyncClient
    requests = []
    def fake_transport(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "Synthetic AI result"}}]})
    with patch.object(ai_analysis.httpx, "AsyncClient", side_effect=lambda **kw: real_async_client(
            transport=httpx.MockTransport(fake_transport), **kw)):
        output, model = await ai_analysis.request_analysis("Synthetic KPI context")
    check("mock SumoPod API contract", output == "Synthetic AI result" and model == "gpt-4o-mini"
          and str(requests[0].url) == ai_analysis.ENDPOINT
          and requests[0].headers.get("authorization", "").startswith("Bearer "))
    with patch.object(ai_analysis.httpx, "AsyncClient", side_effect=lambda **kw: real_async_client(
            transport=httpx.MockTransport(lambda request: httpx.Response(401, json={"error": "synthetic"})), **kw)):
        try:
            await ai_analysis.request_analysis("Synthetic KPI context")
        except HTTPException as exc:
            check("provider error sanitized", exc.status_code == 502 and "synthetic" not in exc.detail)
        else:
            raise AssertionError("provider error was accepted")
    print(f"Owner Report + AI PostgreSQL acceptance: {len(checks)} PASS")


def ai_hash(token):
    import hashlib
    return hashlib.sha256(token.encode("ascii")).hexdigest()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run())
