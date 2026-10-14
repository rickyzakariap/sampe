"""Pure license rules shared by the existing MongoDB and opt-in PostgreSQL paths."""

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional


CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def license_status(lic: dict) -> str:
    if lic.get("revoked"):
        return "revoked"
    if not lic.get("activated_at"):
        return "unused"
    return "active" if _parse(lic["expires_at"]) > _now() else "expired"


def public_license(lic: dict) -> dict:
    keys = ("id", "code", "label", "email", "source", "duration_days", "created_at",
            "activated_at", "expires_at", "last_login_at", "revoked")
    return {key: lic.get(key) for key in keys} | {"status": license_status(lic)}


def activate_fields(lic: dict) -> dict:
    now = _now()
    return {"activated_at": now.isoformat(),
            "expires_at": (now + timedelta(days=lic["duration_days"])).isoformat()}


def extend_fields(lic: dict, days: int) -> dict:
    if not lic.get("activated_at"):
        return {"duration_days": lic["duration_days"] + days}
    base = max(_parse(lic["expires_at"]), _now())
    return {"expires_at": (base + timedelta(days=days)).isoformat()}


def renewal_expires_at(lic: dict, days: int, success_time: datetime) -> str:
    existing = lic["expires_at"]
    if isinstance(existing, str):
        existing = datetime.fromisoformat(existing)
    if not isinstance(existing, datetime):
        raise ValueError("Tanggal kedaluwarsa lisensi tidak valid")
    if existing.tzinfo is None:
        existing = existing.replace(tzinfo=timezone.utc)
    return (max(existing, success_time) + timedelta(days=days)).isoformat()


def new_license(label: str, days: int, email: Optional[str] = None, source: str = "admin") -> dict:
    return {"id": str(uuid.uuid4()), "code": None, "label": label,
            "email": (email or "").strip().lower() or None,
            "source": source, "duration_days": days,
            "created_at": _now().isoformat(), "activated_at": None,
            "expires_at": None, "last_login_at": None, "revoked": False,
            "owner_user_id": None}


def generate_license_code() -> str:
    return "SAMPE-" + "-".join(
        "".join(secrets.choice(CODE_ALPHABET) for _ in range(4)) for _ in range(3)
    )
