"""Teacher-facing pages: portal, period marking, corrections, analytics, lesson plans, roster/leave."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

# Before matplotlib imports (cache directory)
os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(__file__).resolve().parents[1] / ".matplotlib"),
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import services
from core.qr_payload import decode_qr_from_image_path, parse_qr_payload, resolve_student_user_id
from db.database import get_connection
from core.nepali_utils import ad_to_bs, bs_to_ad


class TeacherSubjectPortal(QWidget):
    def __init__(self, teacher_id: int) -> None:
        super().__init__()
        self._teacher_id = teacher_id
        self._list = QTextEdit()
        self._list.setReadOnly(True)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<h3>Your subject portals</h3>"))
        lay.addWidget(
            QLabel(
                "Each subject below is restricted to your account. Open <b>Period marking</b> to take attendance "
                "for a specific time slot and date."
            )
        )
        lay.addWidget(refresh)
        lay.addWidget(self._list)
        self.reload()

    def reload(self) -> None:
        conn = get_connection()
        try:
            subs = services.teacher_subjects(conn, self._teacher_id)
        finally:
            conn.close()
        lines = []
        for s in subs:
            lines.append(f"<b>{s['code']}</b> — {s['name']} (ID {s['id']})")
        self._list.setHtml("<br/>".join(lines) if lines else "<i>No subjects assigned.</i>")


class TeacherPeriodMarking(QWidget):
    def __init__(self, teacher_id: int) -> None:
        super().__init__()
        self._teacher_id = teacher_id
        self._subject = QComboBox()
        self._period = QComboBox()
        self._date = QDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDate(date.today())
        self._lesson = QComboBox()
        self._lesson.addItem("(none)", None)
        self._capture = QComboBox()
        self._capture.addItems(["manual", "qr", "rfid", "biometric", "geofence"])
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Student", "Code", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(0, 200)

        self._subject.currentIndexChanged.connect(self._reload_roster)
        self._period.currentIndexChanged.connect(self._reload_roster)
        self._date.dateChanged.connect(self._reload_roster)
        self._reload_subjects()
        reload_btn = QPushButton("Load roster & existing marks")
        reload_btn.clicked.connect(self._reload_roster)
        save_btn = QPushButton("Save attendance for this period")
        save_btn.clicked.connect(self._save)

        self._nepali_date_lbl = QLabel()
        self._nepali_date_lbl.setStyleSheet("color: #89b4fa; font-weight: bold; margin-left: 10px;")
        self._date.dateChanged.connect(self._update_nepali_label)
        self._update_nepali_label()

        top = QGridLayout()
        top.addWidget(QLabel("Subject"), 0, 0)
        top.addWidget(self._subject, 0, 1)
        top.addWidget(QLabel("Period"), 0, 2)
        top.addWidget(self._period, 0, 3)
        top.addWidget(QLabel("Date"), 1, 0)
        
        date_lay = QHBoxLayout()
        date_lay.addWidget(self._date)
        date_lay.addWidget(self._nepali_date_lbl)
        date_lay.addStretch()
        top.addLayout(date_lay, 1, 1)

        top.addWidget(QLabel("Lesson plan"), 1, 2)
        top.addWidget(self._lesson, 1, 3)
        top.addWidget(QLabel("Capture method"), 2, 0)
        top.addWidget(self._capture, 2, 1)

    def _update_nepali_label(self) -> None:
        d = self._date.date().toString("yyyy-MM-dd")
        self._nepali_date_lbl.setText(f"({ad_to_bs(d)})")

        qr_box = QGroupBox("QR scan-to-mark (uses subject, period, date & lesson plan above)")
        self._qr_input = QLineEdit()
        self._qr_input.setPlaceholderText("Scan or paste ATTENDANCE:STUDENT:<id> (or ATTENDANCE:CODE:<student_code>)")
        self._qr_input.returnPressed.connect(self._apply_qr_scan)
        qr_go = QPushButton("Mark present from scan")
        qr_go.clicked.connect(self._apply_qr_scan)
        qr_img = QPushButton("Decode QR from image…")
        qr_img.clicked.connect(self._decode_qr_image)
        self._qr_status = QLabel("")
        self._qr_status.setWordWrap(True)
        qr_row = QHBoxLayout()
        qr_row.addWidget(self._qr_input, 1)
        qr_row.addWidget(qr_go)
        qr_row.addWidget(qr_img)
        qb = QVBoxLayout(qr_box)
        qb.addLayout(qr_row)
        qb.addWidget(self._qr_status)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<h3>Period-wise attendance</h3>"))
        lay.addLayout(top)
        lay.addWidget(qr_box)
        lay.addWidget(reload_btn)
        lay.addWidget(self._table)
        lay.addWidget(save_btn)

        self._load_periods()
        self._reload_subjects()

    def _load_periods(self) -> None:
        self._period.clear()
        conn = get_connection()
        try:
            for p in services.periods(conn):
                self._period.addItem(f"{p['label']} ({p['start_time']}–{p['end_time']})", p["id"])
        finally:
            conn.close()

    def _reload_subjects(self) -> None:
        self._subject.clear()
        conn = get_connection()
        try:
            for s in services.teacher_subjects(conn, self._teacher_id):
                self._subject.addItem(f"{s['code']} — {s['name']}", s["id"])
        finally:
            conn.close()
        self._reload_roster()

    def _reload_roster(self) -> None:
        sid = self._subject.currentData()
        if sid is None:
            return
        d = self._date.date().toString("yyyy-MM-dd")
        conn = get_connection()
        try:
            roster = services.roster_for_subject(conn, sid)
            lp = services.lesson_plans_for_day(conn, sid, self._teacher_id, d)
        finally:
            conn.close()
        self._lesson.clear()
        self._lesson.addItem("(none)", None)
        for row in lp:
            self._lesson.addItem(row["title"], row["id"])

        self._table.setRowCount(len(roster))
        pid = self._period.currentData()
        conn = get_connection()
        try:
            status_map = {}
            if pid is not None:
                for row in conn.execute(
                    """SELECT student_user_id, status FROM attendance_records
                       WHERE subject_id = ? AND period_id = ? AND attendance_date = ?""",
                    (sid, pid, d),
                ):
                    status_map[row["student_user_id"]] = row["status"]
        finally:
            conn.close()
        for i, st in enumerate(roster):
            self._table.setItem(i, 0, QTableWidgetItem(st["full_name"]))
            self._table.setItem(i, 1, QTableWidgetItem(st["student_code"] or ""))
            status = QComboBox()
            status.addItems(["present", "absent", "late", "excused"])
            if st["id"] in status_map:
                status.setCurrentText(status_map[st["id"]])
            self._table.setCellWidget(i, 2, status)

    def _apply_qr_scan(self) -> None:
        raw = self._qr_input.text().strip()
        if not raw:
            return
        parsed = parse_qr_payload(raw)
        if not parsed:
            QMessageBox.warning(
                self,
                "Invalid QR",
                "Expected payload like ATTENDANCE:STUDENT:123 or ATTENDANCE:CODE:STU-2026-001",
            )
            return
        sid = self._subject.currentData()
        pid = self._period.currentData()
        d = self._date.date().toString("yyyy-MM-dd")
        lp = self._lesson.currentData()
        if sid is None or pid is None:
            QMessageBox.warning(self, "Context", "Select subject and period first.")
            return
        conn = get_connection()
        try:
            uid = resolve_student_user_id(conn, parsed)
            if uid is None:
                QMessageBox.warning(self, "Unknown", "No student matches this QR payload.")
                return
            roster_ids = {r["id"] for r in services.roster_for_subject(conn, sid)}
            if uid not in roster_ids:
                QMessageBox.warning(self, "Roster", "This student is not enrolled in the selected subject.")
                return
            _, aid = services.get_or_create_attendance(
                conn,
                subject_id=sid,
                teacher_id=self._teacher_id,
                student_id=uid,
                period_id=pid,
                attendance_date=d,
                status="present",
                lesson_plan_id=lp,
                capture_method="qr",
            )
            conn.commit()
        finally:
            conn.close()
        services.deliver_pending_alerts([aid])
        c2 = get_connection()
        try:
            row = c2.execute("SELECT full_name FROM users WHERE id = ?", (uid,)).fetchone()
            label = row["full_name"] if row else str(uid)
        finally:
            c2.close()
        self._qr_input.clear()
        self._qr_status.setText(f"Marked {label} present (QR).")
        self._reload_roster()

    def _decode_qr_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "QR image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All files (*)",
        )
        if not path:
            return
        text = decode_qr_from_image_path(path)
        if not text:
            QMessageBox.warning(
                self,
                "Decode",
                "Could not read a QR code. Install pyzbar and system zbar (e.g. brew install zbar on macOS), "
                "or paste the payload manually.",
            )
            return
        self._qr_input.setText(text.strip())
        self._apply_qr_scan()

    def _save(self) -> None:
        sid = self._subject.currentData()
        pid = self._period.currentData()
        if sid is None or pid is None:
            return
        d = self._date.date().toString("yyyy-MM-dd")
        lp = self._lesson.currentData()
        cap = self._capture.currentText()
        conn = get_connection()
        pending_alerts: list[int | None] = []
        try:
            roster = services.roster_for_subject(conn, sid)
            for i, st in enumerate(roster):
                w = self._table.cellWidget(i, 2)
                assert isinstance(w, QComboBox)
                stat = w.currentText()
                _, aid = services.get_or_create_attendance(
                    conn,
                    subject_id=sid,
                    teacher_id=self._teacher_id,
                    student_id=st["id"],
                    period_id=pid,
                    attendance_date=d,
                    status=stat,
                    lesson_plan_id=lp,
                    capture_method=cap,
                )
                pending_alerts.append(aid)
            conn.commit()
        finally:
            conn.close()
        delivery = services.deliver_pending_alerts(pending_alerts)
        msg = "Attendance saved."
        if delivery:
            msg += "\n\nAbsence alerts:\n" + "\n".join(delivery[:12])
        QMessageBox.information(self, "Saved", msg)


class TeacherCorrections(QWidget):
    def __init__(self, teacher_id: int) -> None:
        super().__init__()
        self._teacher_id = teacher_id
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Record ID", "Date", "Student", "Period", "Status", "Subject"]
        )
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(2, 200)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._new_status = QComboBox()
        self._new_status.addItems(["present", "absent", "late", "excused"])
        self._reason = QLineEdit()
        self._reason.setPlaceholderText("Reason for correction (audit)")
        apply_btn = QPushButton("Apply correction to selected row")
        apply_btn.clicked.connect(self._apply)
        refresh = QPushButton("Refresh list")
        refresh.clicked.connect(self._load)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<h3>Attendance corrections</h3>"))
        lay.addWidget(
            QLabel("Amend mistaken marks; each change is logged for auditors with reason and timestamp.")
        )
        lay.addWidget(refresh)
        lay.addWidget(self._table)
        row = QHBoxLayout()
        row.addWidget(QLabel("New status"))
        row.addWidget(self._new_status)
        row.addWidget(self._reason)
        row.addWidget(apply_btn)
        lay.addLayout(row)
        self._load()

    def _load(self) -> None:
        conn = get_connection()
        try:
            rows = conn.execute(
                """SELECT ar.id, ar.attendance_date, u.full_name, p.label, ar.status, sub.name
                   FROM attendance_records ar
                   JOIN users u ON u.id = ar.student_user_id
                   JOIN periods p ON p.id = ar.period_id
                   JOIN subjects sub ON sub.id = ar.subject_id
                   WHERE ar.teacher_user_id = ?
                   ORDER BY ar.attendance_date DESC, ar.id DESC LIMIT 200""",
                (self._teacher_id,),
            ).fetchall()
        finally:
            conn.close()
        self._table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, v in enumerate(
                [r["id"], r["attendance_date"], r["full_name"], r["label"], r["status"], r["name"]]
            ):
                self._table.setItem(i, j, QTableWidgetItem(str(v)))

    def _apply(self) -> None:
        items = self._table.selectedItems()
        if not items:
            QMessageBox.information(self, "Select", "Select a row first.")
            return
        row = items[0].row()
        rid = int(self._table.item(row, 0).text())
        reason = self._reason.text().strip()
        if not reason:
            QMessageBox.warning(self, "Reason", "Enter a reason for the correction.")
            return
        conn = get_connection()
        try:
            services.correct_attendance(
                conn,
                record_id=rid,
                new_status=self._new_status.currentText(),
                teacher_id=self._teacher_id,
                reason=reason,
            )
            conn.commit()
        finally:
            conn.close()
        self._reason.clear()
        self._load()
        QMessageBox.information(self, "Updated", "Correction recorded.")


class TeacherAnalytics(QWidget):
    def __init__(self, teacher_id: int) -> None:
        super().__init__()
        self._teacher_id = teacher_id
        self._subject = QComboBox()
        self._figure = Figure(figsize=(5, 3))
        self._canvas = FigureCanvas(self._figure)
        load = QPushButton("Load subject analytics")
        load.clicked.connect(self._plot)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<h3>Subject analytics</h3>"))
        lay.addWidget(
            QLabel("Compare absence frequency across your roster for the selected subject (period-level data).")
        )
        lay.addWidget(self._subject)
        lay.addWidget(load)
        lay.addWidget(self._canvas)
        self._reload_subjects()

    def _reload_subjects(self) -> None:
        self._subject.clear()
        conn = get_connection()
        try:
            for s in services.teacher_subjects(conn, self._teacher_id):
                self._subject.addItem(f"{s['code']} — {s['name']}", s["id"])
        finally:
            conn.close()

    def _plot(self) -> None:
        sid = self._subject.currentData()
        if sid is None:
            return
        conn = get_connection()
        try:
            rows = services.teacher_analytics_skips(conn, sid)
        finally:
            conn.close()
        self._figure.clear()
        ax = self._figure.add_subplot(111)
        names = [r["full_name"] for r in rows][:12]
        absences = [r["absences"] or 0 for r in rows][:12]
        if not names:
            ax.text(0.5, 0.5, "No attendance data yet.", ha="center", va="center")
        else:
            ax.barh(names[::-1], absences[::-1], color="#2980b9")
            ax.set_xlabel("Absent period marks")
            ax.set_title("Absence counts by student")
        self._canvas.draw()


class TeacherLessonPlans(QWidget):
    def __init__(self, teacher_id: int) -> None:
        super().__init__()
        self._teacher_id = teacher_id
        self._subject = QComboBox()
        self._date = QDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDate(date.today())
        self._title = QLineEdit()
        self._milestone = QLineEdit()
        self._desc = QTextEdit()
        save = QPushButton("Save lesson plan")
        save.clicked.connect(self._save)
        self._list = QTextEdit()
        self._list.setReadOnly(True)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<h3>Lesson plans & milestones</h3>"))
        lay.addWidget(
            QLabel("Link attendance sessions to curriculum milestones; picks appear when marking a period.")
        )
        lay.addWidget(self._subject)
        self._reload_subjects()
        form = QFormLayout()
        form.addRow("Date", self._date)
        form.addRow("Title", self._title)
        form.addRow("Milestone", self._milestone)
        lay.addLayout(form)
        lay.addWidget(QLabel("Description"))
        lay.addWidget(self._desc)
        lay.addWidget(save)
        lay.addWidget(QLabel("Plans for selected date"))
        lay.addWidget(self._list)
        self._subject.currentIndexChanged.connect(self._show_plans)
        self._date.dateChanged.connect(self._show_plans)
        self._show_plans()

    def _reload_subjects(self) -> None:
        self._subject.clear()
        conn = get_connection()
        try:
            for s in services.teacher_subjects(conn, self._teacher_id):
                self._subject.addItem(f"{s['code']} — {s['name']}", s["id"])
        finally:
            conn.close()

    def _show_plans(self) -> None:
        sid = self._subject.currentData()
        if sid is None:
            return
        d = self._date.date().toString("yyyy-MM-dd")
        conn = get_connection()
        try:
            rows = services.lesson_plans_for_day(conn, sid, self._teacher_id, d)
        finally:
            conn.close()
        lines = [f"{r['title']} — {r['milestone'] or ''}\n{r['description'] or ''}" for r in rows]
        self._list.setPlainText("\n\n".join(lines) if lines else "No plans for this date.")

    def _save(self) -> None:
        sid = self._subject.currentData()
        if sid is None:
            return
        d = self._date.date().toString("yyyy-MM-dd")
        title = self._title.text().strip()
        if not title:
            QMessageBox.warning(self, "Title", "Enter a title.")
            return
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO lesson_plans (subject_id, teacher_user_id, plan_date, title, milestone, description)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    sid,
                    self._teacher_id,
                    d,
                    title,
                    self._milestone.text().strip() or None,
                    self._desc.toPlainText().strip() or None,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        self._title.clear()
        self._milestone.clear()
        self._desc.clear()
        self._show_plans()
        QMessageBox.information(self, "Saved", "Lesson plan added.")


class TeacherRosterLeave(QWidget):
    def __init__(self, teacher_id: int) -> None:
        super().__init__()
        self._teacher_id = teacher_id
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        refresh = QPushButton("Refresh leave queue")
        refresh.clicked.connect(self._load)
        approve = QPushButton("Approve selected (use ID in external workflow)")
        approve.setEnabled(False)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<h3>Roster — leave visibility</h3>"))
        lay.addWidget(
            QLabel(
                "Leave requests submitted by students/parents appear here when they concern your subjects. "
                "Approve or reject in your SIS; this view is for roster awareness."
            )
        )
        lay.addWidget(refresh)
        lay.addWidget(self._text)
        self._load()

    def _load(self) -> None:
        conn = get_connection()
        try:
            rows = services.pending_leave_for_teacher_subjects(conn, self._teacher_id)
        finally:
            conn.close()
        lines = []
        for r in rows:
            sub = r["subject_name"] or "All subjects"
            lines.append(
                f"#{r['id']} | {r['student_name']} | {sub} | {r['start_date']} → {r['end_date']} | {r['reason'] or ''}"
            )
        self._text.setPlainText("\n".join(lines) if lines else "No pending leave for your subjects.")


class TeacherTimetable(QWidget):
    def __init__(self, teacher_id: int) -> None:
        super().__init__()
        self._teacher_id = teacher_id
        self._days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        self._table = QTableWidget(0, 9)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Session", "Course", "Semester", "Subject", "Room", "Day", "Period", "Time"]
        )
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(4, 200)
        self._table.setColumnHidden(0, True)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        refresh = QPushButton("Refresh list")
        refresh.clicked.connect(self._load)
        export_btn = QPushButton("Export My Timetable (PDF)")
        export_btn.clicked.connect(self._export_pdf)
        
        btn_lay = QHBoxLayout()
        btn_lay.addWidget(refresh)
        btn_lay.addWidget(export_btn)
        btn_lay.addStretch()
        
        lay = QVBoxLayout(self)
        title = QLabel("My Timetable")
        title.setProperty("styleClass", "h1")
        lay.addWidget(title)
        lay.addWidget(QLabel("View and export your personalized weekly schedule."))
        lay.addLayout(btn_lay)
        lay.addWidget(self._table)
        self._load()

    def _load(self) -> None:
        conn = get_connection()
        try:
            rows = conn.execute(
                """SELECT t.id, COALESCE(sy.label, '—') AS sess_name, c.name AS course_name,
                          sem.name AS sem_name, sub.name AS subj, COALESCE(r.name,'') AS room,
                          t.day_of_week, p.label, p.start_time || ' – ' || p.end_time AS slot
                   FROM timetable t
                   LEFT JOIN session_years sy ON sy.id = t.session_id
                   JOIN courses c ON c.id = t.course_id
                   JOIN semesters sem ON sem.id = t.semester_id
                   JOIN subjects sub ON sub.id = t.subject_id
                   LEFT JOIN rooms r ON r.id = t.room_id
                   JOIN periods p ON p.id = t.period_id
                   WHERE t.teacher_user_id = ?
                   ORDER BY t.day_of_week, p.sort_order""",
                (self._teacher_id,),
            ).fetchall()
        finally:
            conn.close()
        self._table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            dow = self._days[int(r["day_of_week"]) % 7]
            vals = [r["id"], r["sess_name"], r["course_name"], r["sem_name"], r["subj"], r["room"], dow, r["label"], r["slot"]]
            for j, v in enumerate(vals):
                self._table.setItem(i, j, QTableWidgetItem(str(v)))

    def _export_pdf(self) -> None:
        export_dir = Path("timetables")
        export_dir.mkdir(exist_ok=True)
        
        conn = get_connection()
        try:
            t_row = conn.execute("SELECT full_name FROM users WHERE id = ?", (self._teacher_id,)).fetchone()
            teacher_name = t_row["full_name"] if t_row else "Teacher"
            
            rows = conn.execute(
                """SELECT t.id, COALESCE(sy.label, '—') AS sess_name, c.name AS course_name,
                          sem.name AS sem_name, sub.name AS subj, COALESCE(r.name,'') AS room,
                          t.day_of_week, p.label, p.start_time || ' – ' || p.end_time AS slot
                   FROM timetable t
                   LEFT JOIN session_years sy ON sy.id = t.session_id
                   JOIN courses c ON c.id = t.course_id
                   JOIN semesters sem ON sem.id = t.semester_id
                   JOIN subjects sub ON sub.id = t.subject_id
                   LEFT JOIN rooms r ON r.id = t.room_id
                   JOIN periods p ON p.id = t.period_id
                   WHERE t.teacher_user_id = ?
                   ORDER BY t.day_of_week, p.sort_order""",
                (self._teacher_id,),
            ).fetchall()
        finally:
            conn.close()
            
        filename = f"timetable_{teacher_name.replace(' ', '_')}.pdf"
        default_path = str(export_dir / filename)
        path, _ = QFileDialog.getSaveFileName(self, "Export Timetable", default_path, "PDF Files (*.pdf)")
        if not path:
            return
            
        from PyQt6.QtPrintSupport import QPrinter
        from PyQt6.QtGui import QTextDocument
        
        html = "<html><head><style>"
        html += "table { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 10pt; margin-bottom: 25px; }"
        html += "th { background-color: #333333; color: white; border: 1px solid #555555; padding: 6px; text-align: left; }"
        html += "td { border: 1px solid #cccccc; padding: 6px; color: #111111; }"
        html += "h2 { font-family: sans-serif; color: #111111; font-size: 16pt; margin-bottom: 5px; }"
        html += "h3 { font-family: sans-serif; color: #444444; font-size: 12pt; margin-top: 5px; margin-bottom: 10px; }"
        html += ".day-header { background-color: #f2f2f2; font-weight: bold; border: 1px solid #cccccc; padding: 6px; font-size: 11pt; color: #333333; font-family: sans-serif; margin-bottom: 0px; margin-top: 15px; }"
        html += "</style></head><body>"
        html += "<h2>Personal Timetable</h2>"
        html += f"<h3>Teacher: {teacher_name}</h3>"
        
        days_map = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for d_idx, day_name in enumerate(days_map):
            day_rows = [r for r in rows if int(r["day_of_week"]) == d_idx]
            if not day_rows:
                continue
            html += f"<div class='day-header'>{day_name}</div>"
            html += "<table><thead><tr>"
            html += "<th>Period</th><th>Time</th><th>Subject</th><th>Course</th><th>Room</th>"
            html += "</tr></thead><tbody>"
            for r in day_rows:
                html += f"<tr><td>{r['label']}</td><td>{r['slot']}</td><td>{r['subj']}</td><td>{r['course_name']}</td><td>{r['room']}</td></tr>"
            html += "</tbody></table>"
        html += "</body></html>"
        
        doc = QTextDocument()
        doc.setHtml(html)
        printer = QPrinter()
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        doc.print(printer)
        QMessageBox.information(self, "Export Successful", f"Timetable exported to PDF at {path}")


def build_teacher_stack(teacher_id: int) -> list[tuple[str, QWidget]]:
    return [
        ("Subject portals", TeacherSubjectPortal(teacher_id)),
        ("My Timetable", TeacherTimetable(teacher_id)),
        ("Period marking", TeacherPeriodMarking(teacher_id)),
        ("Corrections", TeacherCorrections(teacher_id)),
        ("Analytics", TeacherAnalytics(teacher_id)),
        ("Lesson plans", TeacherLessonPlans(teacher_id)),
        ("Roster & leave", TeacherRosterLeave(teacher_id)),
    ]
