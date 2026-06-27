"""Send SMS via Twilio when configured."""

from __future__ import annotations

from core.app_settings import twilio_effective_config


def send_sms(to_e164: str, body: str) -> tuple[bool, str]:
    """
    Send an SMS. Returns (success, detail_message_for_logs).
    If Twilio is not enabled or incomplete, returns (False, reason) without raising.
    """
    cfg = twilio_effective_config()
    if not cfg["enabled"]:
        return False, "Twilio disabled (set TWILIO_ENABLED=1 or enable in Admin → SMS)."
    if not cfg["account_sid"] or not cfg["auth_token"] or not cfg["from_number"]:
        return False, "Twilio incomplete (need account SID, auth token, and from number)."
    if not to_e164.strip():
        return False, "No recipient phone number."

    try:
        from twilio.rest import Client
    except ImportError:
        return False, "twilio package not installed (pip install twilio)."

    try:
        client = Client(cfg["account_sid"], cfg["auth_token"])
        msg = client.messages.create(
            body=body[:1600],
            from_=cfg["from_number"],
            to=to_e164.strip(),
        )
        return True, f"Twilio sid={msg.sid}"
    except Exception as e:
        return False, f"Twilio error: {e}"
