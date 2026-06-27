"""Student and parent views: subject reports, alerts log, leave requests."""

from __future__ import annotations

from datetime import date

from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import services
from db.database import get_connection
from core.nepali_utils import ad_to_bs, bs_to_ad


class SubjectReports(QWidget):
    def __init__(self, student_user_id: int, title: str = "Subject-wise attendance") -> None:
        super().__init__()
        self._student_user_id = student_user_id
        self._out = QTextEdit()
        self._out.setReadOnly(True)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<h3>{title}</h3>"))
        lay.addWidget(
            QLabel(
                "Attendance is tracked per subject and period. Percentages use recorded sessions only; "
                "meet your institution’s minimum (e.g. 75%) per course."
            )
        )
        lay.addWidget(refresh)
        lay.addWidget(self._out)
        self.reload()

    def reload(self) -> None:
        conn = get_connection()
        try:
            stats = services.student_subject_percentages(conn, self._student_user_id)
        finally:
            conn.close()
        lines = []
        for s in stats:
            pct = s["percentage"]
            pct_s = f"{pct}%" if pct is not None else "n/a (no marks yet)"
            lines.append(
                f"<b>{s['code']}</b> {s['name']}<br/>"
                f"Recorded sessions: {s['present_sessions']} present/late/excused of {s['total_marked_sessions']} — "
                f"<b>{pct_s}</b><br/><br/>"
            )
        self._out.setHtml("".join(lines) if lines else "<i>No enrollments found.</i>")


class AlertsLog(QWidget):
    def __init__(self, parent_user_id: int | None, student_user_id: int | None) -> None:
        super().__init__()
        self._parent_uid = parent_user_id
        self._student_uid = student_user_id
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<h3>Absence alerts</h3>"))
        lay.addWidget(
            QLabel(
                "When a teacher marks a student absent for a period, an SMS or in-app notification is queued "
                "for the guardian on file. Production systems connect Twilio or similar; this demo logs deliveries."
            )
        )
        lay.addWidget(refresh)
        lay.addWidget(self._text)
        self.reload()

    def reload(self) -> None:
        conn = get_connection()
        try:
            if self._parent_uid is not None:
                q = """SELECT a.sent_at, a.message, a.status, a.channel FROM absence_alerts a
                       JOIN attendance_records ar ON ar.id = a.attendance_record_id
                       JOIN students s ON s.user_id = ar.student_user_id
                       WHERE s.parent_user_id = ? ORDER BY a.sent_at DESC LIMIT 100"""
                rows = conn.execute(q, (self._parent_uid,)).fetchall()
            elif self._student_uid is not None:
                rows = conn.execute(
                    """SELECT a.sent_at, a.message, a.status, a.channel FROM absence_alerts a
                       JOIN attendance_records ar ON ar.id = a.attendance_record_id
                       WHERE ar.student_user_id = ? ORDER BY a.sent_at DESC LIMIT 100""",
                    (self._student_uid,),
                ).fetchall()
            else:
                rows = []
        finally:
            conn.close()
        lines = [f"{ad_to_bs(r['sent_at'].split('T')[0]) if r['sent_at'] else '—'} [{r['channel']}] {r['status']}: {r['message']}" for r in rows]
        self._text.setPlainText("\n".join(lines) if lines else "No alerts yet.")


class LeavePortal(QWidget):
    def __init__(self, actor_user_id: int, student_user_id: int, is_parent: bool) -> None:
        super().__init__()
        self._actor = actor_user_id
        self._student = student_user_id
        self._subject = QComboBox()
        self._subject.addItem("All subjects", None)
        self._start = QDateEdit()
        self._end = QDateEdit()
        self._start.setCalendarPopup(True)
        self._end.setCalendarPopup(True)
        self._start.setDate(date.today())
        self._end.setDate(date.today())
        
        self._nepali_start_lbl = QLabel()
        self._nepali_end_lbl = QLabel()
        self._nepali_start_lbl.setStyleSheet("color: #89b4fa; font-weight: bold;")
        self._nepali_end_lbl.setStyleSheet("color: #89b4fa; font-weight: bold;")
        
        self._start.dateChanged.connect(self._update_nepali_labels)
        self._end.dateChanged.connect(self._update_nepali_labels)
        self._update_nepali_labels()

        self._reason = QTextEdit()
        self._reason.setMaximumHeight(100)
        submit = QPushButton("Submit leave request")
        submit.clicked.connect(self._submit)
        self._load_subjects()
        lay = QVBoxLayout(self)
        who = "parent" if is_parent else "student"
        lay.addWidget(QLabel(f"<h3>Leave requests ({who})</h3>"))
        lay.addWidget(
            QLabel("Requests appear on teacher rosters for relevant subjects when pending.")
        )
        form = QFormLayout()
        form.addRow("Subject scope", self._subject)
        
        start_lay = QHBoxLayout()
        start_lay.addWidget(self._start)
        start_lay.addWidget(self._nepali_start_lbl)
        start_lay.addStretch()
        form.addRow("Start", start_lay)
        
        end_lay = QHBoxLayout()
        end_lay.addWidget(self._end)
        end_lay.addWidget(self._nepali_end_lbl)
        end_lay.addStretch()
        form.addRow("End", end_lay)
        
        lay.addLayout(form)
        lay.addWidget(QLabel("Reason"))
        lay.addWidget(self._reason)
        lay.addWidget(submit)
        self._history = QTextEdit()
        self._history.setReadOnly(True)
        lay.addWidget(QLabel("Your recent requests"))
        lay.addWidget(self._history)
        self._refresh_history()

    def _load_subjects(self) -> None:
        conn = get_connection()
        try:
            rows = conn.execute(
                """SELECT s.id, s.code, s.name FROM subjects s
                   JOIN enrollments e ON e.subject_id = s.id WHERE e.student_user_id = ?""",
                (self._student,),
            ).fetchall()
        finally:
            conn.close()
        for r in rows:
            self._subject.addItem(f"{r['code']} — {r['name']}", r["id"])

    def _submit(self) -> None:
        reason = self._reason.toPlainText().strip()
        if not reason:
            QMessageBox.warning(self, "Reason", "Enter a reason.")
            return
        start = self._start.date().toString("yyyy-MM-dd")
        end = self._end.date().toString("yyyy-MM-dd")
        sub = self._subject.currentData()
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO leave_requests
                   (student_user_id, subject_id, start_date, end_date, reason, status, submitted_by_user_id, created_at)
                   VALUES (?, ?, ?, ?, ?, 'pending', ?, datetime('now'))""",
                (self._student, sub, start, end, reason, self._actor),
            )
            conn.commit()
        finally:
            conn.close()
        self._reason.clear()
        self._refresh_history()
        QMessageBox.information(self, "Submitted", "Leave request saved (pending).")

    def _update_nepali_labels(self) -> None:
        s = self._start.date().toString("yyyy-MM-dd")
        e = self._end.date().toString("yyyy-MM-dd")
        self._nepali_start_lbl.setText(f"({ad_to_bs(s)})")
        self._nepali_end_lbl.setText(f"({ad_to_bs(e)})")

    def _refresh_history(self) -> None:
        conn = get_connection()
        try:
            rows = conn.execute(
                """SELECT id, start_date, end_date, status, reason FROM leave_requests
                   WHERE student_user_id = ? ORDER BY id DESC LIMIT 20""",
                (self._student,),
            ).fetchall()
        finally:
            conn.close()
        lines = [f"#{r['id']} {ad_to_bs(r['start_date'])}–{ad_to_bs(r['end_date'])} [{r['status']}] {r['reason'] or ''}" for r in rows]
        self._history.setPlainText("\n".join(lines))


def build_student_pages(user_id: int) -> list[tuple[str, QWidget]]:
    return [
        ("Subject reports", SubjectReports(user_id, "Your attendance by subject")),
        ("Absence alerts", AlertsLog(None, user_id)),
        ("Leave", LeavePortal(user_id, user_id, is_parent=False)),
    ]


def build_parent_pages(parent_user_id: int) -> list[tuple[str, QWidget]]:
    conn = get_connection()
    try:
        child_id = services.parent_child_user_id(conn, parent_user_id)
    finally:
        conn.close()
    if child_id is None:
        empty = QWidget()
        QVBoxLayout(empty).addWidget(
            QLabel("No linked student on file. Ask an administrator to connect your account.")
        )
        return [("Account", empty)]
    return [
        ("Child subject reports", SubjectReports(child_id, "Your child’s attendance by subject")),
        ("Absence alerts", AlertsLog(parent_user_id, None)),
        ("Leave requests", LeavePortal(parent_user_id, child_id, is_parent=True)),
    ]
