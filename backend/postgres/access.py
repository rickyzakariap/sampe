"""Opt-in PostgreSQL account, license, and Lynk flows.

This module is never imported by the default MongoDB application. Callers must
provide a DSN for an isolated PostgreSQL runtime or test environment.
"""

import uuid
from datetime import datetime, timedelta, timezone

from license_rules import activate_fields, extend_fields, generate_license_code, license_status, new_license, renewal_expires_at
from lynk_contract import parse_payload, product_days, signature_amount, signature_ok, valid_buyer_email


def now():
    return datetime.now(timezone.utc)


class PolicyDecisionRequired(Exception):
    """A purchase cannot be applied without a product-owner rule."""


class PostgresAccess:
    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("PostgreSQL DSN is required")
        self.dsn = dsn

    def connect(self):
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(self.dsn, connect_timeout=5, row_factory=dict_row)

    def _after_license_write(self):
        """Test seam for proving transaction rollback after the license write."""

    def _bind_first_unowned(self, conn, member: dict, at):
        lic = conn.execute("""SELECT * FROM sampe.licenses WHERE email=%s AND owner_user_id IS NULL
                              AND revoked=false ORDER BY created_at DESC FOR UPDATE LIMIT 1""",
                           (member["email"],)).fetchone()
        if not lic:
            return None
        fields = activate_fields(lic) if not lic["activated_at"] else {}
        conn.execute("""UPDATE sampe.licenses SET owner_user_id=%s,activated_at=COALESCE(activated_at,%s),
                        expires_at=COALESCE(expires_at,%s),code=COALESCE(code,%s),last_login_at=%s
                        WHERE id=%s AND owner_user_id IS NULL""",
                     (member["user_id"], fields.get("activated_at"), fields.get("expires_at"),
                      generate_license_code(), at, lic["id"]))
        return lic["id"]

    def start_session(self, email: str, name: str, session_token: str, *, picture=None, at=None):
        """Persist a trusted identity and bind its first unowned license.

        Authentication of the identity and issuance of the session token remain
        the caller's responsibility, as in the existing OAuth flow.
        """
        email = email.strip().lower()
        if not valid_buyer_email(email) or not session_token:
            raise ValueError("Invalid identity or session")
        at = at or now()
        with self.connect() as conn, conn.transaction():
            conn.execute("""INSERT INTO sampe.lynk_email_locks (email,touched_at) VALUES (%s,%s)
                            ON CONFLICT (email) DO UPDATE SET touched_at=EXCLUDED.touched_at""", (email, at))
            member = conn.execute("SELECT * FROM sampe.members WHERE email=%s FOR UPDATE", (email,)).fetchone()
            if member is None:
                member = {"user_id": str(uuid.uuid4()), "email": email, "name": name,
                          "picture": picture, "created_at": at}
                conn.execute("""INSERT INTO sampe.members (user_id,email,name,picture,created_at)
                                VALUES (%(user_id)s,%(email)s,%(name)s,%(picture)s,%(created_at)s)""", member)
            else:
                conn.execute("UPDATE sampe.members SET name=%s,picture=%s WHERE user_id=%s",
                             (name, picture, member["user_id"]))
            conn.execute("""INSERT INTO sampe.user_sessions (session_token,user_id,expires_at,created_at)
                            VALUES (%s,%s,%s,%s)""",
                         (session_token, member["user_id"], at + timedelta(days=7), at))
            owned = conn.execute("SELECT id FROM sampe.licenses WHERE owner_user_id=%s LIMIT 1",
                                 (member["user_id"],)).fetchone()
            if not owned:
                self._bind_first_unowned(conn, member, at)
            return member["user_id"]

    def member_for_session(self, token: str):
        with self.connect() as conn:
            return conn.execute("""SELECT m.* FROM sampe.user_sessions s JOIN sampe.members m ON m.user_id=s.user_id
                                   WHERE s.session_token=%s AND s.expires_at>%s""", (token, now())).fetchone()

    def license_for_member(self, user_id: str):
        with self.connect() as conn:
            return conn.execute("""SELECT * FROM sampe.licenses WHERE owner_user_id=%s
                                   ORDER BY created_at DESC LIMIT 1""", (user_id,)).fetchone()

    def ensure_member_license(self, user_id: str):
        """Match existing /auth/me auto-bind behavior after a later webhook."""
        with self.connect() as conn, conn.transaction():
            member = conn.execute("SELECT * FROM sampe.members WHERE user_id=%s", (user_id,)).fetchone()
            if not member:
                return None
            conn.execute("""INSERT INTO sampe.lynk_email_locks (email,touched_at) VALUES (%s,%s)
                            ON CONFLICT (email) DO UPDATE SET touched_at=EXCLUDED.touched_at""",
                         (member["email"], now()))
            lic = conn.execute("""SELECT * FROM sampe.licenses WHERE owner_user_id=%s
                                  ORDER BY created_at DESC FOR UPDATE LIMIT 1""", (user_id,)).fetchone()
            if not lic:
                license_id = self._bind_first_unowned(conn, member, now())
                lic = conn.execute("SELECT * FROM sampe.licenses WHERE id=%s", (license_id,)).fetchone() if license_id else None
            if lic:
                conn.execute("UPDATE sampe.licenses SET last_login_at=%s WHERE id=%s", (now(), lic["id"]))
                lic = conn.execute("SELECT * FROM sampe.licenses WHERE id=%s", (lic["id"],)).fetchone()
            return lic

    def claim_license(self, user_id: str, code: str):
        """Keep the existing claim-by-code behavior with an ownership guard."""
        with self.connect() as conn, conn.transaction():
            member = conn.execute("SELECT * FROM sampe.members WHERE user_id=%s", (user_id,)).fetchone()
            if not member:
                raise ValueError("Member not found")
            lic = conn.execute("SELECT * FROM sampe.licenses WHERE code=%s FOR UPDATE",
                               (code.strip().upper(),)).fetchone()
            if not lic or lic["revoked"]:
                raise ValueError("License unavailable")
            if lic["owner_user_id"] and lic["owner_user_id"] != user_id:
                raise PermissionError("License belongs to another account")
            fields = activate_fields(lic) if not lic["activated_at"] else {}
            conn.execute("""UPDATE sampe.licenses SET owner_user_id=%s,activated_at=COALESCE(activated_at,%s),
                            expires_at=COALESCE(expires_at,%s),last_login_at=%s WHERE id=%s""",
                         (user_id, fields.get("activated_at"), fields.get("expires_at"), now(), lic["id"]))
            return conn.execute("SELECT * FROM sampe.licenses WHERE id=%s", (lic["id"],)).fetchone()

    def end_session(self, token: str):
        with self.connect() as conn:
            conn.execute("DELETE FROM sampe.user_sessions WHERE session_token=%s", (token,))

    def renew_url(self):
        with self.connect() as conn:
            row = conn.execute("SELECT renew_url FROM sampe.settings WHERE key='lynk'").fetchone()
            return row["renew_url"] if row else None

    def extend_admin_license(self, license_id: str, days: int):
        with self.connect() as conn, conn.transaction():
            lic = conn.execute("SELECT * FROM sampe.licenses WHERE id=%s FOR UPDATE", (license_id,)).fetchone()
            if not lic:
                return None
            fields = extend_fields(lic, days)
            if "expires_at" in fields:
                conn.execute("UPDATE sampe.licenses SET expires_at=%s WHERE id=%s",
                             (fields["expires_at"], license_id))
            else:
                conn.execute("UPDATE sampe.licenses SET duration_days=%s WHERE id=%s",
                             (fields["duration_days"], license_id))
            return conn.execute("SELECT * FROM sampe.licenses WHERE id=%s", (license_id,)).fetchone()

    def receive_webhook(self, body: dict, signature: str):
        """Validate then atomically record a Lynk order and its entitlement."""
        p = parse_payload(body)
        if p["event"] != "payment.received":
            return {"processed": False, "reason": "event"}
        if not p["ref_id"] or not valid_buyer_email(p["email"]) or not p["message_id"] or signature_amount(p["grand_total"]) is None:
            raise ValueError("Required transaction field missing")
        with self.connect() as conn:
            key_row = conn.execute("SELECT merchant_key FROM sampe.settings WHERE key='lynk'").fetchone()
        key = key_row["merchant_key"] if key_row else None
        if not key:
            raise RuntimeError("Merchant key not configured")
        if not signature_ok(p, signature, key):
            raise ValueError("Invalid signature")
        if p["message_action"] != "SUCCESS" or str(p["message_code"]) != "0":
            return {"processed": False, "reason": "payment status"}
        return self._process_order(p)

    def _process_order(self, p: dict):
        days, _ = product_days(p["items"])
        at = now()
        with self.connect() as conn, conn.transaction():
            # The first delivery has no row yet. A transaction-level advisory
            # lock serializes it with concurrent deliveries of the same Ref ID.
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("lynk-ref:" + p["ref_id"],))
            existing = conn.execute("SELECT * FROM sampe.lynk_orders WHERE ref_id=%s FOR UPDATE", (p["ref_id"],)).fetchone()
            if existing:
                return {"processed": existing["status"] == "processed", "duplicate": True,
                        "status": existing["status"], "license_id": existing["license_id"]}
            action, status, license_id = None, "unmatched", None
            if days:
                # This persisted lock row serializes distinct purchases by the
                # same buyer, including when no member/license exists yet.
                conn.execute("""INSERT INTO sampe.lynk_email_locks (email,touched_at) VALUES (%s,%s)
                                ON CONFLICT (email) DO UPDATE SET touched_at=EXCLUDED.touched_at""", (p["email"], at))
                member = conn.execute("SELECT user_id FROM sampe.members WHERE email=%s", (p["email"],)).fetchone()
                owner_id = member["user_id"] if member else None
                lic = conn.execute("""SELECT * FROM sampe.licenses WHERE
                                      (email=%s OR owner_user_id=%s)
                                      AND (owner_user_id IS NULL OR owner_user_id=%s)
                                      ORDER BY created_at DESC FOR UPDATE LIMIT 1""",
                                   (p["email"], owner_id, owner_id)).fetchone()
                if lic:
                    if lic["revoked"]:
                        raise PolicyDecisionRequired("Revoked license renewal needs owner decision")
                    elif lic["activated_at"] and lic["expires_at"]:
                        expires = renewal_expires_at(lic, days, at)
                        conn.execute("UPDATE sampe.licenses SET expires_at=%s WHERE id=%s", (expires, lic["id"]))
                        license_id, action, status = lic["id"], "extended", "processed"
                    else:
                        action, status = "pending_policy", "pending_policy"
                else:
                    lic = new_license(p["name"] or p["email"], days, p["email"], "lynk")
                    lic["code"] = generate_license_code()
                    conn.execute("""INSERT INTO sampe.licenses
                                    (id,code,label,email,source,duration_days,created_at,revoked,lynk_ref_id)
                                    VALUES (%s,%s,%s,%s,%s,%s,%s,false,%s)""",
                                 (lic["id"], lic["code"], lic["label"], lic["email"], lic["source"],
                                  days, lic["created_at"], p["ref_id"]))
                    license_id, action, status = lic["id"], "created", "processed"
                self._after_license_write()
            conn.execute("""INSERT INTO sampe.lynk_orders
                            (ref_id,message_id,email,name,phone,product,days,created_at,license_id,action,status)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                         (p["ref_id"], p["message_id"], p["email"], p["name"], p["phone"],
                          ", ".join(i["title"] for i in p["items"]), days, at, license_id, action, status))
            return {"processed": status == "processed", "duplicate": False,
                    "status": status, "license_id": license_id, "action": action}

    def activation_lookup(self, email: str, ref_id: str):
        with self.connect() as conn:
            order = conn.execute("SELECT * FROM sampe.lynk_orders WHERE email=%s AND ref_id=%s",
                                 (email.strip().lower(), ref_id.strip())).fetchone()
            if not order:
                return None
            if not order["license_id"]:
                return {"status": order["status"], "code": None}
            lic = conn.execute("SELECT * FROM sampe.licenses WHERE id=%s", (order["license_id"],)).fetchone()
            if not lic:
                raise RuntimeError("Order license missing")
            return {"code": lic["code"], "action": order["action"], "days": order["days"],
                    "status": license_status(lic), "expires_at": lic["expires_at"],
                    "duration_days": lic["duration_days"], "email": order["email"]}
