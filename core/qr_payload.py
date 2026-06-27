"""QR payload format shared by admin QR generator and teacher scanner."""

from __future__ import annotations

import re

PREFIX = "ATTENDANCE:STUDENT:"
# Optional legacy: same prefix with student_code
CODE_PREFIX = "ATTENDANCE:CODE:"

_re_student = re.compile(r"^ATTENDANCE:STUDENT:(\d+)\s*$")
_re_code = re.compile(r"^ATTENDANCE:CODE:(.+)\s*$")


def format_student_qr(user_id: int) -> str:
    return f"{PREFIX}{user_id}"


def parse_qr_payload(text: str) -> tuple[str, int | str] | None:
    """
    Parse scanned text. Returns ('user_id', id) or ('student_code', code) or None.
    """
    raw = text.strip()
    m = _re_student.match(raw)
    if m:
        return ("user_id", int(m.group(1)))
    m = _re_code.match(raw)
    if m:
        return ("student_code", m.group(1).strip())
    return None


def decode_qr_from_image_path(path: str) -> str | None:
    """Read first QR code payload from an image file (requires pyzbar + zbar)."""
    try:
        from PIL import Image
        from pyzbar.pyzbar import decode as zbar_decode
    except ImportError:
        return None
    try:
        img = Image.open(path)
        codes = zbar_decode(img)
        for c in codes:
            return c.data.decode("utf-8", errors="replace")
    except OSError:
        return None
    return None


def resolve_student_user_id(conn, parsed: tuple[str, int | str]) -> int | None:
    """Resolve parse result to users.id for a student account."""
    kind, val = parsed
    if kind == "user_id":
        r = conn.execute(
            "SELECT user_id FROM students WHERE user_id = ?",
            (val,),
        ).fetchone()
        return int(val) if r else None
    r = conn.execute("SELECT user_id FROM students WHERE student_code = ?", (val,)).fetchone()
    return int(r["user_id"]) if r else None
