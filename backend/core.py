from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
import uuid
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Dict, Any
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]


EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')


# ---------------- Models ----------------
def now_iso():
    return datetime.now(timezone.utc).isoformat()


class KpiConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_name: str
    month: str  # YYYY-MM
    target_sales: float = 0
    budget_ads: float = 0
    budget_branding: float = 0
    budget_campaign: float = 0
    budget_kol: float = 0
    target_kol_count: int = 0
    live_team_count: int = 0
    target_live_hours: float = 0
    target_live_revenue: float = 0
    created_at: str = Field(default_factory=now_iso)


class ConfigInput(BaseModel):
    company_name: str
    month: str
    target_sales: float = 0
    budget_ads: float = 0
    budget_branding: float = 0
    budget_campaign: float = 0
    budget_kol: float = 0
    target_kol_count: int = 0
    live_team_count: int = 0
    target_live_hours: float = 0
    target_live_revenue: float = 0


class Entry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    module: str  # sales | ads | branding | campaign | livestream | kol
    date: str  # YYYY-MM-DD
    data: Dict[str, Any] = {}
    created_at: str = Field(default_factory=now_iso)


class EntryInput(BaseModel):
    module: str
    date: str
    data: Dict[str, Any] = {}



def shift_month(month: str, delta: int) -> str:
    y, m = int(month[:4]), int(month[5:7]) + delta
    while m < 1:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return f"{y}-{m:02d}"
