"""Pure Lynk payload, entitlement and signature rules shared by database paths."""

import hashlib
import hmac
import math
import re
from email.utils import parseaddr
from typing import Optional


SAMPE_PRODUCT = "SAMPE - System Analytic Marketplace"
LYNK_STORE_URL = "https://lynk.id/katalogsatset"


def renew_url(configured: Optional[str]) -> str:
    return configured or LYNK_STORE_URL


SAMPE_PRODUCT_DAYS = {
    SAMPE_PRODUCT.casefold(): 1,
    f"{SAMPE_PRODUCT} (7 Hari)".casefold(): 7,
    f"{SAMPE_PRODUCT} (30 Hari)".casefold(): 30,
    f"{SAMPE_PRODUCT} (365 Hari)".casefold(): 365,
}


def valid_buyer_email(value: str) -> bool:
    if not value or len(value) > 254 or any(char.isspace() for char in value):
        return False
    if parseaddr(value)[1] != value:
        return False
    local, separator, domain = value.rpartition("@")
    if not separator or not local or len(local) > 64 or "." not in domain:
        return False
    if not (local.startswith('"') and local.endswith('"')):
        atoms = local.split(".")
        if any(not atom or any(not (char.isalnum() or char in "!#$%&'*+/=?^_`{|}~-") for char in atom) for atom in atoms):
            return False
    try:
        labels = domain.encode("idna").decode("ascii").split(".")
    except UnicodeError:
        return False
    return all(len(label) <= 63 and re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label)
               for label in labels)


def _pick(data: dict, *keys):
    for key in keys:
        if isinstance(data, dict) and data.get(key) not in (None, ""):
            return data[key]
    return None


def parse_payload(body: dict) -> dict:
    if not isinstance(body, dict):
        raise ValueError("Payload bukan objek")
    data = body.get("data") or {}
    if not isinstance(data, dict):
        raise ValueError("Data bukan objek")
    md = data.get("message_data") or {}
    if not isinstance(md, dict):
        raise ValueError("Message data bukan objek")
    cust = md.get("customer") or {}
    totals = md.get("totals") or {}
    items = md.get("items") or []
    if not isinstance(cust, dict) or not isinstance(totals, dict) or not isinstance(items, list):
        raise ValueError("Struktur transaksi tidak valid")
    parsed_items = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Item bukan objek")
        try:
            qty = int(item.get("qty", 1))
        except (TypeError, ValueError) as exc:
            raise ValueError("Kuantitas item tidak valid") from exc
        if qty < 1:
            raise ValueError("Kuantitas item tidak valid")
        parsed_items.append({"title": str(item.get("title") or item.get("name") or ""), "qty": qty})
    return {
        "ref_id": str(_pick(md, "refId", "ref_id", "order_id") or "").strip(),
        "message_id": str(_pick(data, "message_id", "messageId") or "").strip(),
        "email": str(_pick(cust, "email") or _pick(md, "email") or "").strip().lower(),
        "name": str(_pick(cust, "name") or _pick(md, "name") or ""),
        "phone": str(_pick(cust, "phone") or ""),
        "items": parsed_items,
        "grand_total": totals.get("grandTotal"),
        "event": body.get("event"),
        "message_action": data.get("message_action"),
        "message_code": data.get("message_code"),
    }


def signature_amount(value) -> Optional[str]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            if not math.isfinite(value):
                return None
            return str(int(value)) if value == int(value) else str(value)
        except (OverflowError, ValueError):
            return None
    if isinstance(value, str):
        return value.strip() or None
    return None


def signature_ok(parsed: dict, signature: str, key: str) -> bool:
    amount = signature_amount(parsed["grand_total"])
    if not signature or amount is None or not parsed["ref_id"] or not parsed["message_id"] or not key:
        return False
    expected = hashlib.sha256(
        f"{amount}{parsed['ref_id']}{parsed['message_id']}{key}".encode()
    ).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


def product_days(items: list[dict]) -> tuple[int, bool]:
    days = 0
    includes_sampe = False
    for item in items:
        title = item["title"].strip()
        duration = SAMPE_PRODUCT_DAYS.get(title.casefold())
        if duration is not None:
            days += duration * item["qty"]
            includes_sampe = True
    return days, includes_sampe
