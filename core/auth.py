"""Authentication and session model."""

from __future__ import annotations

from dataclasses import dataclass

from db.database import get_connection, verify_password


@dataclass
class UserSession:
    user_id: int
    username: str
    role: str
    full_name: str
    email: str | None
    phone: str | None


def authenticate(username: str, password: str) -> UserSession | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, password_hash, salt, role, full_name, email, phone FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
        if row is None:
            return None
        if not verify_password(password, row["password_hash"], row["salt"]):
            return None
        return UserSession(
            user_id=row["id"],
            username=row["username"],
            role=row["role"],
            full_name=row["full_name"],
            email=row["email"],
            phone=row["phone"],
        )
    finally:
        conn.close()
