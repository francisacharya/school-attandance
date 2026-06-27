"""Business logic: attendance, alerts, leave, analytics, compliance exports."""

from __future__ import annotations

import csv
import io
import sqlite3
from datetime import date, datetime
from typing import Any

from db.database import get_connection

from core.app_settings import twilio_effective_config
from core.twilio_sms import send_sms


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def teacher_subjects(conn: sqlite3.Connection, teacher_id: int) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """SELECT s.id, s.code, s.name FROM subjects s
               INNER JOIN teacher_subjects ts ON ts.subject_id = s.id
               WHERE ts.teacher_user_id = ? ORDER BY s.code""",
            (teacher_id,),
        ).fetchall()
    )


def roster_for_subject(conn: sqlite3.Connection, subject_id: int) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """SELECT u.id, u.full_name, s.student_code
               FROM users u
               INNER JOIN students s ON s.user_id = u.id
               INNER JOIN enrollments e ON e.student_user_id = u.id
               WHERE e.subject_id = ? ORDER BY u.full_name""",
            (subject_id,),
        ).fetchall()
    )


def periods(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM periods ORDER BY sort_order, id").fetchall())


def get_or_create_attendance(
    conn: sqlite3.Connection,
    *,
    subject_id: int,
    teacher_id: int,
    student_id: int,
    period_id: int,
    attendance_date: str,
    status: str,
    lesson_plan_id: int | None,
    capture_method: str,
) -> tuple[int, int | None]:
    """Returns (record_id, absence_alert_id_if_queued). SMS is sent after commit via deliver_absence_alert_sms."""
    row = conn.execute(
        """SELECT id, status FROM attendance_records
           WHERE subject_id = ? AND student_user_id = ? AND period_id = ? AND attendance_date = ?""",
        (subject_id, student_id, period_id, attendance_date),
    ).fetchone()
    old_status = row["status"] if row else None
    if row:
        conn.execute(
            """UPDATE attendance_records SET status = ?, lesson_plan_id = COALESCE(?, lesson_plan_id),
               marked_at = ?, capture_method = ?
               WHERE id = ?""",
            (status, lesson_plan_id, _now_iso(), capture_method, row["id"]),
        )
        rec_id = row["id"]
    else:
        cur = conn.execute(
            """INSERT INTO attendance_records
               (subject_id, teacher_user_id, student_user_id, period_id, attendance_date,
                status, lesson_plan_id, marked_at, capture_method)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                subject_id,
                teacher_id,
                student_id,
                period_id,
                attendance_date,
                status,
                lesson_plan_id,
                _now_iso(),
                capture_method,
            ),
        )
        rec_id = cur.lastrowid

    alert_id = None
    if status == "absent" and old_status != "absent":
        alert_id = queue_absence_alert(conn, rec_id)

    return rec_id, alert_id


def queue_absence_alert(conn: sqlite3.Connection, attendance_record_id: int) -> int | None:
    """Insert a queued parent alert; call deliver_absence_alert_sms after transaction commit."""
    row = conn.execute(
        """SELECT ar.student_user_id, u.full_name, sub.name AS subj, p.label, p.start_time,
                  par.phone, par.id AS parent_uid
           FROM attendance_records ar
           JOIN users u ON u.id = ar.student_user_id
           JOIN subjects sub ON sub.id = ar.subject_id
           JOIN periods p ON p.id = ar.period_id
           LEFT JOIN students st ON st.user_id = ar.student_user_id
           LEFT JOIN users par ON par.id = st.parent_user_id
           WHERE ar.id = ?""",
        (attendance_record_id,),
    ).fetchone()
    if row is None or not row["phone"]:
        return None
    msg = (
        f"Absence alert: {row['full_name']} marked absent for {row['subj']} "
        f"({row['label']}, {row['start_time']})."
    )
    cur = conn.execute(
        """INSERT INTO absence_alerts (attendance_record_id, channel, recipient, message, sent_at, status)
           VALUES (?, 'sms', ?, ?, ?, 'queued')""",
        (attendance_record_id, row["phone"], msg, _now_iso()),
    )
    return int(cur.lastrowid)


def deliver_absence_alert_sms(alert_id: int) -> tuple[bool, str]:
    """Send Twilio SMS for a queued alert and update row status."""
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT a.id, a.recipient, a.message, a.status
               FROM absence_alerts a WHERE a.id = ?""",
            (alert_id,),
        ).fetchone()
        if row is None:
            return False, "Alert not found."
        if row["status"] not in ("queued", "pending"):
            return True, "Already processed."

        cfg = twilio_effective_config()
        if not cfg["enabled"]:
            conn.execute(
                """UPDATE absence_alerts SET status = 'logged', message = message || ? WHERE id = ?""",
                ("\n[No SMS sent: Twilio disabled — enable in Admin → SMS or TWILIO_ENABLED=1]", alert_id),
            )
            conn.commit()
            return True, "Twilio off; alert kept in-app only."

        ok, detail = send_sms(row["recipient"], row["message"])
        st = "sent" if ok else "failed"
        conn.execute(
            """UPDATE absence_alerts SET status = ?, message = message || ? WHERE id = ?""",
            (st, f"\n[{detail}]", alert_id),
        )
        conn.commit()
        return ok, detail
    finally:
        conn.close()


def deliver_pending_alerts(alert_ids: list[int | None]) -> list[str]:
    """After DB commit, send SMS for each queued absence alert."""
    lines: list[str] = []
    for aid in alert_ids:
        if aid is None:
            continue
        ok, detail = deliver_absence_alert_sms(int(aid))
        lines.append(f"{'OK' if ok else 'Note'}: {detail}")
    return lines


def correct_attendance(
    conn: sqlite3.Connection,
    *,
    record_id: int,
    new_status: str,
    teacher_id: int,
    reason: str,
) -> None:
    row = conn.execute("SELECT status FROM attendance_records WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        raise ValueError("Record not found")
    old = row["status"]
    conn.execute(
        """UPDATE attendance_records SET status = ?, marked_at = ? WHERE id = ?""",
        (new_status, _now_iso(), record_id),
    )
    conn.execute(
        """INSERT INTO attendance_corrections
           (attendance_record_id, old_status, new_status, reason, corrected_by, corrected_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (record_id, old, new_status, reason, teacher_id, _now_iso()),
    )


def student_subject_percentages(conn: sqlite3.Connection, student_user_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT sub.id, sub.code, sub.name,
                  SUM(CASE WHEN ar.status IN ('present', 'late', 'excused') THEN 1 ELSE 0 END) AS presentish,
                  COUNT(ar.id) AS total
           FROM enrollments e
           JOIN subjects sub ON sub.id = e.subject_id
           LEFT JOIN attendance_records ar ON ar.subject_id = e.subject_id AND ar.student_user_id = e.student_user_id
           WHERE e.student_user_id = ?
           GROUP BY sub.id, sub.code, sub.name""",
        (student_user_id,),
    ).fetchall()
    out = []
    for r in rows:
        total = r["total"] or 0
        pres = r["presentish"] or 0
        pct = (pres / total * 100.0) if total else None
        out.append(
            {
                "subject_id": r["id"],
                "code": r["code"],
                "name": r["name"],
                "present_sessions": pres,
                "total_marked_sessions": total,
                "percentage": round(pct, 1) if pct is not None else None,
            }
        )
    return out


def teacher_analytics_skips(conn: sqlite3.Connection, subject_id: int) -> list[sqlite3.Row]:
    """Students with absence counts for a subject (period-granular records)."""
    return list(
        conn.execute(
            """SELECT u.full_name, s.student_code,
                  SUM(CASE WHEN ar.status = 'absent' THEN 1 ELSE 0 END) AS absences,
                  COUNT(ar.id) AS sessions
           FROM enrollments e
           JOIN users u ON u.id = e.student_user_id
           JOIN students s ON s.user_id = u.id
           LEFT JOIN attendance_records ar ON ar.student_user_id = u.id AND ar.subject_id = e.subject_id
           WHERE e.subject_id = ?
           GROUP BY u.id
           ORDER BY absences DESC""",
            (subject_id,),
        ).fetchall()
    )


def lesson_plans_for_day(
    conn: sqlite3.Connection, subject_id: int, teacher_id: int, plan_date: str
) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """SELECT * FROM lesson_plans WHERE subject_id = ? AND teacher_user_id = ? AND plan_date = ?
               ORDER BY id""",
            (subject_id, teacher_id, plan_date),
        ).fetchall()
    )


def pending_leave_for_teacher_subjects(conn: sqlite3.Connection, teacher_id: int) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """SELECT lr.*, u.full_name AS student_name, sub.name AS subject_name
               FROM leave_requests lr
               JOIN users u ON u.id = lr.student_user_id
               LEFT JOIN subjects sub ON sub.id = lr.subject_id
               WHERE lr.status = 'pending' AND (
                   lr.subject_id IS NULL OR lr.subject_id IN (
                       SELECT subject_id FROM teacher_subjects WHERE teacher_user_id = ?
                   )
               )
               ORDER BY lr.created_at DESC""",
            (teacher_id,),
        ).fetchall()
    )


def compliance_report_csv(conn: sqlite3.Connection, start: str, end: str) -> str:
    """Audit-oriented export: one row per attendance fact."""
    from core.nepali_utils import ad_to_bs
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "record_id",
            "date_ad",
            "date_bs",
            "period_label",
            "start_time",
            "end_time",
            "subject_code",
            "subject_name",
            "student_code",
            "student_name",
            "teacher_name",
            "status",
            "capture_method",
            "marked_at",
            "room",
        ]
    )
    # ... query ...
    rows = conn.execute(
        """SELECT ar.id, ar.attendance_date, p.label, p.start_time, p.end_time,
                  sub.code, sub.name, st.student_code, su.full_name AS student_name,
                  tu.full_name AS teacher_name, ar.status, ar.capture_method, ar.marked_at,
                  COALESCE(r.name, '') AS room
           FROM attendance_records ar
           JOIN periods p ON p.id = ar.period_id
           JOIN subjects sub ON sub.id = ar.subject_id
           JOIN users su ON su.id = ar.student_user_id
           JOIN students st ON st.user_id = su.id
           JOIN users tu ON tu.id = ar.teacher_user_id
           LEFT JOIN timetable t ON t.subject_id = ar.subject_id AND t.period_id = ar.period_id
               AND t.day_of_week = (CAST(strftime('%w', ar.attendance_date) AS INTEGER) + 6) % 7
           LEFT JOIN rooms r ON r.id = t.room_id
           WHERE ar.attendance_date >= ? AND ar.attendance_date <= ?
           ORDER BY ar.attendance_date, p.sort_order, sub.code""",
        (start, end),
    ).fetchall()
    
    for row in rows:
        # Convert sqlite Row to list and insert BS date at index 2 (after AD date)
        data = list(row)
        data.insert(2, ad_to_bs(row["attendance_date"]))
        w.writerow(data)
    return buf.getvalue()


def parent_child_user_id(conn: sqlite3.Connection, parent_user_id: int) -> int | None:
    r = conn.execute(
        "SELECT user_id FROM students WHERE parent_user_id = ? LIMIT 1", (parent_user_id,)
    ).fetchone()
    return r["user_id"] if r else None


def admin_stats(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        "users": conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"],
        "teachers": conn.execute("SELECT COUNT(*) AS c FROM users WHERE role = 'teacher'").fetchone()["c"],
        "subjects": conn.execute("SELECT COUNT(*) AS c FROM subjects").fetchone()["c"],
        "rooms": conn.execute("SELECT COUNT(*) AS c FROM rooms").fetchone()["c"],
        "courses": conn.execute("SELECT COUNT(*) AS c FROM courses").fetchone()["c"],
        "sessions": conn.execute("SELECT COUNT(*) AS c FROM session_years").fetchone()["c"],
        "semesters": conn.execute("SELECT COUNT(*) AS c FROM semesters").fetchone()["c"],
        "today_records": conn.execute(
            "SELECT COUNT(*) AS c FROM attendance_records WHERE attendance_date = ?",
            (date.today().isoformat(),),
        ).fetchone()["c"],
        "pending_leave": conn.execute(
            "SELECT COUNT(*) AS c FROM leave_requests WHERE status = 'pending'"
        ).fetchone()["c"],
    }
def get_student_enrollments(conn: sqlite3.Connection, student_id: int) -> list[int]:
    rows = conn.execute("SELECT subject_id FROM enrollments WHERE student_user_id = ?", (student_id,)).fetchall()
    return [r["subject_id"] for r in rows]


def apply_leave_to_attendance(conn: sqlite3.Connection, leave_id: int):
    """Marks all scheduled classes for a student as 'excused' during an approved leave period."""
    leave = conn.execute(
        "SELECT student_user_id, start_date, end_date FROM leave_requests WHERE id = ?", (leave_id,)
    ).fetchone()
    if not leave:
        return

    student_id = leave["student_user_id"]
    from datetime import timedelta

    start = datetime.strptime(leave["start_date"], "%Y-%m-%d").date()
    end = datetime.strptime(leave["end_date"], "%Y-%m-%d").date()

    curr = start
    while curr <= end:
        # Day of week mapping: 0=Monday, 1=Tuesday, ..., 6=Sunday
        # weekday() in Python: 0=Monday
        dow = curr.weekday()
        date_str = curr.isoformat()

        # Find what the student should have attended today
        rows = conn.execute(
            """SELECT t.subject_id, t.teacher_user_id, t.period_id 
               FROM timetable t
               JOIN enrollments e ON e.subject_id = t.subject_id
               WHERE e.student_user_id = ? AND t.day_of_week = ?""",
            (student_id, dow),
        ).fetchall()

        for r in rows:
            get_or_create_attendance(
                conn,
                subject_id=r["subject_id"],
                teacher_id=r["teacher_user_id"],
                student_id=student_id,
                period_id=r["period_id"],
                attendance_date=date_str,
                status="excused",
                lesson_plan_id=None,
                capture_method="system_leave",
            )
        curr += timedelta(days=1)
def clear_leave_attendance(conn: sqlite3.Connection, leave_id: int):
    """Removes 'excused' records marked by the leave system for a specific student and date range."""
    leave = conn.execute(
        "SELECT student_user_id, start_date, end_date FROM leave_requests WHERE id = ?", (leave_id,)
    ).fetchone()
    if not leave:
        return
    
    conn.execute(
        """DELETE FROM attendance_records 
           WHERE student_user_id = ? 
             AND attendance_date BETWEEN ? AND ? 
             AND capture_method = 'system_leave'""",
        (leave["student_user_id"], leave["start_date"], leave["end_date"]),
    )
