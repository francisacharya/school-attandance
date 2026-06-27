"""SQLite schema, connection, and seed data for the attendance system."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import date
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "attendance.db"


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
        dklen=32,
    ).hex()


def hash_password_new(password: str) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    return _hash_password(password, salt), salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    return secrets.compare_digest(_hash_password(password, salt), stored_hash)


def get_connection() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _execmany(conn: sqlite3.Connection, sql: str, rows: list[tuple]) -> None:
    conn.executemany(sql, rows)


def init_database() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        
        # Migration: Add course_id to timetable if it doesn't exist
        try:
            conn.execute("ALTER TABLE timetable ADD COLUMN course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE")
            conn.commit()
        except sqlite3.OperationalError:
            pass # Column already exists
            
        # Migration: Add session_id to timetable if it doesn't exist
        try:
            conn.execute("ALTER TABLE timetable ADD COLUMN session_id INTEGER REFERENCES session_years(id) ON DELETE CASCADE")
            conn.commit()
        except sqlite3.OperationalError:
            pass # Column already exists
            
        # Migration: Add semester_id to timetable if it doesn't exist
        try:
            conn.execute("ALTER TABLE timetable ADD COLUMN semester_id INTEGER REFERENCES semesters(id) ON DELETE CASCADE")
            conn.commit()
        except sqlite3.OperationalError:
            pass # Column already exists
            
        try:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS class_qr_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
                period_id INTEGER NOT NULL REFERENCES periods(id) ON DELETE CASCADE,
                attendance_date TEXT NOT NULL,
                created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """)
            conn.commit()
        except sqlite3.OperationalError:
            pass
            
        _seed_if_empty(conn)
        conn.commit()
    finally:
        conn.close()


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    cur = conn.execute("SELECT COUNT(*) AS c FROM users")
    if cur.fetchone()["c"] > 0:
        return

    admin_h, admin_s = hash_password_new("admin")
    conn.execute(
        """INSERT INTO users (username, password_hash, salt, role, full_name, email, phone)
           VALUES (?, ?, ?, 'admin', 'System Administrator', 'admin@school.edu', '')""",
        ("admin", admin_h, admin_s),
    )

    t1_h, t1_s = hash_password_new("teacher1")
    conn.execute(
        """INSERT INTO users (username, password_hash, salt, role, full_name, email, phone)
           VALUES (?, ?, ?, 'teacher', 'Dr. Alice Smith', 'alice@school.edu', '')""",
        ("teacher1", t1_h, t1_s),
    )
    t2_h, t2_s = hash_password_new("teacher2")
    conn.execute(
        """INSERT INTO users (username, password_hash, salt, role, full_name, email, phone)
           VALUES (?, ?, ?, 'teacher', 'Mr. Bob Jones', 'bob@school.edu', '')""",
        ("teacher2", t2_h, t2_s),
    )

    s_h, s_s = hash_password_new("student1")
    conn.execute(
        """INSERT INTO users (username, password_hash, salt, role, full_name, email, phone)
           VALUES (?, ?, ?, 'student', 'Charlie Student', 'charlie@school.edu', '')""",
        ("student1", s_h, s_s),
    )
    p_h, p_s = hash_password_new("parent1")
    conn.execute(
        """INSERT INTO users (username, password_hash, salt, role, full_name, email, phone)
           VALUES (?, ?, ?, 'parent', 'Pat Parent', 'parent@example.com', '+15550001')""",
        ("parent1", p_h, p_s),
    )
    conn.commit()

    cur = conn.execute("SELECT id FROM users WHERE username = 'student1'")
    student_uid = cur.fetchone()["id"]
    cur = conn.execute("SELECT id FROM users WHERE username = 'parent1'")
    parent_uid = cur.fetchone()["id"]
    conn.execute(
        "INSERT INTO students (user_id, student_code, parent_user_id) VALUES (?, ?, ?)",
        (student_uid, "STU-2026-001", parent_uid),
    )

    conn.executemany(
        "INSERT INTO subjects (code, name) VALUES (?, ?)",
        [("MATH101", "Calculus I"), ("ENG101", "English Composition")],
    )
    conn.executemany(
        "INSERT INTO rooms (name, building) VALUES (?, ?)",
        [("A-101", "North Hall"), ("B-205", "South Hall")],
    )
    conn.executemany(
        "INSERT INTO periods (label, start_time, end_time, sort_order) VALUES (?, ?, ?, ?)",
        [
            ("Period 1", "09:00", "10:00", 1),
            ("Period 2", "10:15", "11:15", 2),
            ("Period 3", "11:30", "12:30", 3),
        ],
    )

    cur = conn.execute("SELECT id FROM users WHERE username = 'teacher1'")
    t1 = cur.fetchone()["id"]
    cur = conn.execute("SELECT id FROM users WHERE username = 'teacher2'")
    t2 = cur.fetchone()["id"]
    cur = conn.execute("SELECT id FROM subjects WHERE code = 'MATH101'")
    math_id = cur.fetchone()["id"]
    cur = conn.execute("SELECT id FROM subjects WHERE code = 'ENG101'")
    eng_id = cur.fetchone()["id"]

    conn.execute(
        "INSERT INTO teacher_subjects (teacher_user_id, subject_id) VALUES (?, ?)",
        (t1, math_id),
    )
    conn.execute(
        "INSERT INTO teacher_subjects (teacher_user_id, subject_id) VALUES (?, ?)",
        (t2, eng_id),
    )

    conn.execute("INSERT INTO enrollments (student_user_id, subject_id) VALUES (?, ?)", (student_uid, math_id))
    conn.execute("INSERT INTO enrollments (student_user_id, subject_id) VALUES (?, ?)", (student_uid, eng_id))

    cur = conn.execute("SELECT id FROM rooms LIMIT 1")
    r1 = cur.fetchone()["id"]
    cur = conn.execute("SELECT id FROM rooms ORDER BY id DESC LIMIT 1")
    r2 = cur.fetchone()["id"]
    p1 = conn.execute("SELECT id FROM periods ORDER BY sort_order LIMIT 1").fetchone()["id"]
    p2 = conn.execute("SELECT id FROM periods ORDER BY sort_order LIMIT 1 OFFSET 1").fetchone()["id"]

    conn.executemany(
        """INSERT INTO timetable (subject_id, teacher_user_id, room_id, day_of_week, period_id)
           VALUES (?, ?, ?, ?, ?)""",
        [
            (math_id, t1, r1, 0, p1),
            (math_id, t1, r1, 2, p1),
            (eng_id, t2, r2, 1, p2),
            (eng_id, t2, r2, 3, p2),
        ],
    )

    conn.execute(
        """INSERT INTO geofence_settings (id, campus_lat, campus_lng, radius_meters, classroom_only)
           VALUES (1, 40.7128, -74.0060, 150, 0)"""
    )

    conn.executemany(
        """INSERT INTO multimodal_devices (device_type, name, room_id, is_active) VALUES (?, ?, ?, 1)""",
        [
            ("qr_station", "QR Kiosk — Room A-101", r1),
            ("rfid_reader", "RFID — Main entrance", None),
            ("biometric", "Fingerprint — Lab B", r2),
        ],
    )

    today = date.today().isoformat()
    conn.execute(
        """INSERT INTO lesson_plans (subject_id, teacher_user_id, plan_date, title, milestone, description)
           VALUES (?, ?, ?, 'Limits and continuity', 'Unit 1 — Week 2', 'Introduce epsilon-delta intuition.')""",
        (math_id, t1, today),
    )


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'teacher', 'student', 'parent')),
    full_name TEXT NOT NULL,
    email TEXT,
    phone TEXT
);

CREATE TABLE IF NOT EXISTS students (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    student_code TEXT UNIQUE,
    parent_user_id INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS semesters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS session_years (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT UNIQUE NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    building TEXT
);

CREATE TABLE IF NOT EXISTS periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS teacher_subjects (
    teacher_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    PRIMARY KEY (teacher_user_id, subject_id)
);

CREATE TABLE IF NOT EXISTS enrollments (
    student_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    PRIMARY KEY (student_user_id, subject_id)
);

CREATE TABLE IF NOT EXISTS timetable (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES session_years(id) ON DELETE CASCADE,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    semester_id INTEGER REFERENCES semesters(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    teacher_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    room_id INTEGER REFERENCES rooms(id),
    day_of_week INTEGER NOT NULL,
    period_id INTEGER NOT NULL REFERENCES periods(id) ON DELETE CASCADE,
    UNIQUE (subject_id, day_of_week, period_id)
);

CREATE TABLE IF NOT EXISTS lesson_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    teacher_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_date TEXT NOT NULL,
    title TEXT NOT NULL,
    milestone TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS attendance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    teacher_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    student_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    period_id INTEGER NOT NULL REFERENCES periods(id) ON DELETE CASCADE,
    attendance_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('present', 'absent', 'late', 'excused')),
    lesson_plan_id INTEGER REFERENCES lesson_plans(id),
    marked_at TEXT NOT NULL,
    notes TEXT,
    capture_method TEXT DEFAULT 'manual',
    UNIQUE (subject_id, student_user_id, period_id, attendance_date)
);

CREATE TABLE IF NOT EXISTS attendance_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attendance_record_id INTEGER NOT NULL REFERENCES attendance_records(id) ON DELETE CASCADE,
    old_status TEXT,
    new_status TEXT NOT NULL,
    reason TEXT,
    corrected_by INTEGER NOT NULL REFERENCES users(id),
    corrected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leave_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id INTEGER REFERENCES subjects(id),
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    reason TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    submitted_by_user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    reviewed_by INTEGER REFERENCES users(id),
    reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS absence_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attendance_record_id INTEGER NOT NULL REFERENCES attendance_records(id) ON DELETE CASCADE,
    channel TEXT DEFAULT 'sms',
    recipient TEXT,
    message TEXT,
    sent_at TEXT NOT NULL,
    status TEXT DEFAULT 'queued'
);

CREATE TABLE IF NOT EXISTS geofence_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    campus_lat REAL,
    campus_lng REAL,
    radius_meters REAL,
    classroom_only INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS multimodal_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_type TEXT NOT NULL,
    name TEXT NOT NULL,
    room_id INTEGER REFERENCES rooms(id),
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attendance_date_subject ON attendance_records(attendance_date, subject_id);
CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance_records(student_user_id);
CREATE INDEX IF NOT EXISTS idx_leave_student ON leave_requests(student_user_id);

CREATE TABLE IF NOT EXISTS class_qr_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT UNIQUE NOT NULL,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    period_id INTEGER NOT NULL REFERENCES periods(id) ON DELETE CASCADE,
    attendance_date TEXT NOT NULL,
    created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""


def fetch_all(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    return list(conn.execute(sql, params).fetchall())


def fetch_one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> sqlite3.Row | None:
    return conn.execute(sql, params).fetchone()
