"""Key-value settings in SQLite (Twilio and other integration config)."""

from __future__ import annotations

import os
from typing import Any

from db.database import get_connection

KEY_TWILIO_ACCOUNT_SID = "twilio_account_sid"
KEY_TWILIO_AUTH_TOKEN = "twilio_auth_token"
KEY_TWILIO_FROM_NUMBER = "twilio_from_number"
KEY_TWILIO_ENABLED = "twilio_enabled"


def get_setting(key: str, default: str | None = None) -> str | None:
    conn = get_connection()
    try:
        r = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        if r:
            return r["value"]
        return default
    finally:
        conn.close()


def set_setting(key: str, value: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def twilio_effective_config() -> dict[str, Any]:
    """Merge environment variables (highest) with DB settings."""
    return {
        "enabled": _truthy(os.environ.get("TWILIO_ENABLED", "")) or _truthy(get_setting(KEY_TWILIO_ENABLED, "") or ""),
        "account_sid": (os.environ.get("TWILIO_ACCOUNT_SID") or get_setting(KEY_TWILIO_ACCOUNT_SID, "") or "").strip(),
        "auth_token": (os.environ.get("TWILIO_AUTH_TOKEN") or get_setting(KEY_TWILIO_AUTH_TOKEN, "") or "").strip(),
        "from_number": (os.environ.get("TWILIO_FROM_NUMBER") or get_setting(KEY_TWILIO_FROM_NUMBER, "") or "").strip(),
    }


def _truthy(s: str) -> bool:
    return s.lower() in ("1", "true", "yes", "on")
