"""Administrator pages: dashboard, users, timetable, compliance, multi-modal, geofence."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import services
from core.app_settings import (
    KEY_TWILIO_ACCOUNT_SID,
    KEY_TWILIO_AUTH_TOKEN,
    KEY_TWILIO_ENABLED,
    KEY_TWILIO_FROM_NUMBER,
    get_setting,
    set_setting,
)
from core.qr_payload import format_student_qr
from core.twilio_sms import send_sms
from db.database import get_connection, hash_password_new
from core.nepali_utils import ad_to_bs, bs_to_ad, get_nepali_month_name


class AdminDashboard(QWidget):
    def __init__(self) -> None:
        super().__init__()
        
        self._cards_layout = QGridLayout()
        self._cards_layout.setHorizontalSpacing(20)
        self._cards_layout.setVerticalSpacing(20)
        
        self._lbl_users = self._make_card("Total Users")
        self._lbl_teachers = self._make_card("Total Teachers")
        self._lbl_rooms = self._make_card("Total Rooms")
        self._lbl_subjects = self._make_card("Total Subjects")
        self._lbl_courses = self._make_card("Total Courses")
        self._lbl_sessions = self._make_card("Total Sessions")
        self._lbl_semesters = self._make_card("Total Semesters")
        self._lbl_records = self._make_card("Attendance Today")
        self._lbl_leave = self._make_card("Pending Leaves")
        
        self._cards_layout.addWidget(self._lbl_users, 0, 0)
        self._cards_layout.addWidget(self._lbl_teachers, 0, 1)
        self._cards_layout.addWidget(self._lbl_rooms, 1, 0)
        self._cards_layout.addWidget(self._lbl_subjects, 1, 1)
        self._cards_layout.addWidget(self._lbl_courses, 2, 0)
        self._cards_layout.addWidget(self._lbl_sessions, 2, 1)
        self._cards_layout.addWidget(self._lbl_semesters, 3, 0)
        self._cards_layout.addWidget(self._lbl_records, 3, 1)
        self._cards_layout.addWidget(self._lbl_leave, 4, 0)

        refresh = QPushButton("Refresh Dashboard")
        refresh.clicked.connect(self.reload)
        
        title = QLabel("Administrator Overview")
        title.setProperty("styleClass", "h1")
        
        desc = QLabel("Use the navigation list for timetables, compliance exports, capture devices, and geofence policy.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #a6adc8; margin-bottom: 20px;")
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 30, 30, 30)
        lay.setSpacing(10)
        
        lay.addWidget(title)
        lay.addWidget(desc)
        lay.addLayout(self._cards_layout)
        lay.addSpacing(20)
        
        btn_lay = QHBoxLayout()
        btn_lay.addWidget(refresh)
        btn_lay.addStretch()
        lay.addLayout(btn_lay)
        lay.addStretch()

        self.reload()

    def _make_card(self, title: str) -> QLabel:
        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setProperty("styleClass", "dashboardCard")
        lbl.setFixedWidth(250)
        lbl.setText(f"<div style='margin-bottom: 4px; font-size: 11pt; color: #a6adc8;'>{title}</div><div style='font-size: 22pt; font-weight: bold; color: #89b4fa;'>--</div>")
        return lbl

    def reload(self) -> None:
        conn = get_connection()
        try:
            s = services.admin_stats(conn)
        finally:
            conn.close()
            
        def update_card(lbl: QLabel, title: str, value: int):
            lbl.setText(f"<div style='margin-bottom: 4px; font-size: 11pt; color: #a6adc8;'>{title}</div><div style='font-size: 22pt; font-weight: bold; color: #89b4fa;'>{value}</div>")
            
        update_card(self._lbl_users, "Total Users", s['users'])
        update_card(self._lbl_teachers, "Total Teachers", s['teachers'])
        update_card(self._lbl_rooms, "Total Rooms", s['rooms'])
        update_card(self._lbl_subjects, "Total Subjects", s['subjects'])
        update_card(self._lbl_courses, "Total Courses", s['courses'])
        update_card(self._lbl_sessions, "Total Sessions", s['sessions'])
        update_card(self._lbl_semesters, "Total Semesters", s['semesters'])
        update_card(self._lbl_records, "Attendance Today", s['today_records'])
        update_card(self._lbl_leave, "Pending Leaves", s['pending_leave'])


class AdminUsers(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["ID", "Username", "Role", "Full name", "Email"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(3, 200)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self._new_user = QLineEdit()
        self._new_pass = QLineEdit()
        self._new_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_name = QLineEdit()
        self._new_role = QComboBox()
        self._new_role.addItems(["teacher", "student", "parent"])
        add_btn = QPushButton("Create user")
        add_btn.clicked.connect(self._add_user)

        form = QFormLayout()
        form.addRow("Username", self._new_user)
        form.addRow("Password", self._new_pass)
        form.addRow("Full name", self._new_name)
        form.addRow("Role", self._new_role)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<h3>Users & roles</h3>"))
        lay.addLayout(form)
        lay.addWidget(add_btn)
        lay.addWidget(self._table)
        self._load()

    def _load(self) -> None:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, username, role, full_name, email FROM users ORDER BY role, username"
            ).fetchall()
        finally:
            conn.close()
        self._table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, key in enumerate(["id", "username", "role", "full_name", "email"]):
                self._table.setItem(i, j, QTableWidgetItem(str(r[key] or "")))

    def _add_user(self) -> None:
        u = self._new_user.text().strip()
        p = self._new_pass.text()
        name = self._new_name.text().strip()
        role = self._new_role.currentText()
        if not u or not p or not name:
            QMessageBox.warning(self, "Missing data", "Fill username, password, and full name.")
            return
        ph, salt = hash_password_new(p)
        conn = get_connection()
        try:
            cur = conn.execute(
                """INSERT INTO users (username, password_hash, salt, role, full_name, email, phone)
                   VALUES (?, ?, ?, ?, ?, '', '')""",
                (u, ph, salt, role, name),
            )
            uid = cur.lastrowid
            if role == "student":
                code = f"STU-{uid}"
                conn.execute(
                    "INSERT INTO students (user_id, student_code, parent_user_id) VALUES (?, ?, NULL)",
                    (uid, code),
                )
            conn.commit()
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Error", "Username already exists.")
            return
        finally:
            conn.close()
        self._new_user.clear()
        self._new_pass.clear()
        self._new_name.clear()
        self._load()
        QMessageBox.information(self, "Created", f"User {u} created.")


class TimetableEntryDialog(QDialog):
    """Create or edit one timetable row (subject, teacher, room, day, period)."""

    def __init__(self, parent: QWidget, entry_id: int | None = None) -> None:
        super().__init__(parent)
        self._entry_id = entry_id
        self.setWindowTitle("Edit timetable entry" if entry_id else "Add timetable entry")
        self._session = QComboBox()
        self._course = QComboBox()
        self._semester = QComboBox()
        self._subject = QComboBox()
        self._teacher = QComboBox()
        self._room = QComboBox()
        self._days_group = QWidget()
        dl = QHBoxLayout(self._days_group)
        dl.setContentsMargins(0, 0, 0, 0)
        self._day_checkboxes: list[QCheckBox] = []
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, d in enumerate(days):
            cb = QCheckBox(d)
            cb.setProperty("day_index", i)
            self._day_checkboxes.append(cb)
            dl.addWidget(cb)
        self._period = QComboBox()
        self._fill_combos()
        if entry_id is not None:
            self._load_entry(entry_id)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("Session Year", self._session)
        form.addRow("Course", self._course)
        form.addRow("Semester", self._semester)
        form.addRow("Subject", self._subject)
        form.addRow("Teacher", self._teacher)
        form.addRow("Room", self._room)
        form.addRow("Days", self._days_group)
        form.addRow("Period", self._period)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(buttons)

    def _fill_combos(self) -> None:
        conn = get_connection()
        try:
            for r in conn.execute("SELECT id, label FROM session_years ORDER BY label DESC").fetchall():
                self._session.addItem(r["label"], r["id"])
            for r in conn.execute("SELECT id, name FROM semesters ORDER BY name").fetchall():
                self._semester.addItem(r["name"], r["id"])
            for r in conn.execute("SELECT id, code, name FROM courses ORDER BY code").fetchall():
                self._course.addItem(f"{r['code']} — {r['name']}", r["id"])
            for r in conn.execute("SELECT id, code, name FROM subjects ORDER BY code").fetchall():
                self._subject.addItem(f"{r['code']} — {r['name']}", r["id"])
            for r in conn.execute(
                "SELECT id, full_name FROM users WHERE role = 'teacher' ORDER BY full_name"
            ).fetchall():
                self._teacher.addItem(r["full_name"], r["id"])
            self._room.addItem("(none)", None)
            for r in conn.execute("SELECT id, name, building FROM rooms ORDER BY name").fetchall():
                b = r["building"] or ""
                self._room.addItem(f"{r['name']} ({b})".strip(), r["id"])
            for r in conn.execute("SELECT id, label, start_time, end_time, sort_order FROM periods ORDER BY sort_order, id").fetchall():
                self._period.addItem(
                    f"{r['label']} ({r['start_time']}–{r['end_time']})", r["id"]
                )
        finally:
            conn.close()

    def _load_entry(self, entry_id: int) -> None:
        conn = get_connection()
        try:
            row = conn.execute("SELECT * FROM timetable WHERE id = ?", (entry_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            return
        if "session_id" in row.keys() and row["session_id"]:
            self._set_combo_data(self._session, row["session_id"])
        if "semester_id" in row.keys() and row["semester_id"]:
            self._set_combo_data(self._semester, row["semester_id"])
        if "course_id" in row.keys() and row["course_id"]:
            self._set_combo_data(self._course, row["course_id"])
        self._set_combo_data(self._subject, row["subject_id"])
        self._set_combo_data(self._teacher, row["teacher_user_id"])
        self._set_combo_data(self._room, row["room_id"])
        dow = int(row["day_of_week"]) % 7
        for cb in self._day_checkboxes:
            cb.setChecked(cb.property("day_index") == dow)
        self._set_combo_data(self._period, row["period_id"])

    @staticmethod
    def _set_combo_data(box: QComboBox, value: object) -> None:
        if value is None:
            if box.itemData(0) is None:
                box.setCurrentIndex(0)
            return
        for i in range(box.count()):
            if box.itemData(i) == value:
                box.setCurrentIndex(i)
                return

    def _save(self) -> None:
        sess_id = self._session.currentData()
        cid = self._course.currentData()
        sem_id = self._semester.currentData()
        sid = self._subject.currentData()
        tid = self._teacher.currentData()
        rid = self._room.currentData()
        dows = [cb.property("day_index") for cb in self._day_checkboxes if cb.isChecked()]
        pid = self._period.currentData()
        
        if sess_id is None or cid is None or sem_id is None or sid is None or tid is None or not dows or pid is None:
            QMessageBox.warning(self, "Incomplete", "Select session, course, semester, subject, teacher, at least one day, and period.")
            return
            
        conn = get_connection()
        try:
            if self._entry_id is None:
                for dow in dows:
                    conn.execute(
                        """INSERT INTO timetable (session_id, course_id, semester_id, subject_id, teacher_user_id, room_id, day_of_week, period_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (sess_id, cid, sem_id, sid, tid, rid, int(dow), pid),
                    )
            else:
                conn.execute(
                    """UPDATE timetable SET session_id=?, course_id=?, semester_id=?, subject_id=?, teacher_user_id=?, room_id=?, day_of_week=?, period_id=?
                       WHERE id=?""",
                    (sess_id, cid, sem_id, sid, tid, rid, int(dows[0]), pid, self._entry_id),
                )
                for dow in dows[1:]:
                    conn.execute(
                        """INSERT INTO timetable (session_id, course_id, semester_id, subject_id, teacher_user_id, room_id, day_of_week, period_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (sess_id, cid, sem_id, sid, tid, rid, int(dow), pid),
                    )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            QMessageBox.critical(
                self,
                "Conflict",
                "That subject already has an entry for one of these days and periods. Resolve conflicts first.",
            )
            return
        finally:
            conn.close()
        self.accept()


class TimetableExportDialog(QDialog):
    """Dialogue to pick which session, course, and semester to export."""
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Timetable PDF")
        
        self._session = QComboBox()
        self._course = QComboBox()
        self._semester = QComboBox()
        self._teacher = QComboBox()
        
        self._fill_combos()
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        form = QFormLayout()
        form.addRow("Session Year", self._session)
        form.addRow("Course", self._course)
        form.addRow("Semester", self._semester)
        form.addRow("Teacher", self._teacher)
        
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<h3>Configure Export Parameters</h3>"))
        lay.addLayout(form)
        lay.addWidget(buttons)

    def _fill_combos(self) -> None:
        conn = get_connection()
        try:
            self._session.addItem("All Sessions", None)
            for r in conn.execute("SELECT id, label FROM session_years ORDER BY label DESC").fetchall():
                self._session.addItem(r["label"], r["id"])
            
            self._semester.addItem("All Semesters", None)
            for r in conn.execute("SELECT id, name FROM semesters ORDER BY name").fetchall():
                self._semester.addItem(r["name"], r["id"])
                
            self._course.addItem("All Courses", None)
            for r in conn.execute("SELECT id, code, name FROM courses ORDER BY code").fetchall():
                self._course.addItem(f"{r['code']} — {r['name']}", r["id"])
                
            self._teacher.addItem("All Teachers", None)
            for r in conn.execute("SELECT id, full_name FROM users WHERE role = 'teacher' ORDER BY full_name").fetchall():
                self._teacher.addItem(r["full_name"], r["id"])
        finally:
            conn.close()

    def result_data(self) -> dict[str, object]:
        return {
            "sess_id": self._session.currentData(),
            "sess_text": self._session.currentText(),
            "course_id": self._course.currentData(),
            "course_text": self._course.currentText(),
            "sem_id": self._semester.currentData(),
            "sem_text": self._semester.currentText(),
            "teacher_id": self._teacher.currentData(),
            "teacher_text": self._teacher.currentText(),
        }


class AdminTimetable(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        self._table = QTableWidget(0, 10)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Session", "Course", "Semester", "Subject", "Teacher", "Room", "Day", "Period", "Time"]
        )
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(4, 200)
        self._table.setColumnHidden(0, True)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        note = QLabel(
            "Master schedule maps subjects to teachers, rooms, weekday (Mon=0), and period. "
            "Each subject can appear once per day/period slot."
        )
        note.setWordWrap(True)
        add_btn = QPushButton("Add entry")
        add_btn.clicked.connect(self._add)
        edit_btn = QPushButton("Edit selected")
        edit_btn.clicked.connect(self._edit)
        del_btn = QPushButton("Delete selected")
        del_btn.clicked.connect(self._delete)
        refresh = QPushButton("Reload")
        refresh.clicked.connect(self._load)

        self._filter_session = QComboBox()
        self._filter_session.currentIndexChanged.connect(self._load)
        self._filter_course = QComboBox()
        self._filter_course.currentIndexChanged.connect(self._load)
        self._filter_semester = QComboBox()
        self._filter_semester.currentIndexChanged.connect(self._load)
        self._populate_filters()

        export_btn = QPushButton("Export PDF")
        export_btn.clicked.connect(self._export_pdf)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        filter_row.addWidget(self._filter_session)
        filter_row.addWidget(self._filter_course)
        filter_row.addWidget(self._filter_semester)
        filter_row.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addWidget(add_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(del_btn)
        btn_row.addWidget(refresh)
        btn_row.addWidget(export_btn)
        btn_row.addStretch()

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<h3>Timetable & room mapping</h3>"))
        lay.addWidget(note)
        lay.addLayout(filter_row)
        lay.addLayout(btn_row)
        lay.addWidget(self._table)
        self._load()

    def _selected_id(self) -> int | None:
        items = self._table.selectedItems()
        if not items:
            return None
        r = items[0].row()
        item = self._table.item(r, 0)
        return int(item.text()) if item else None

    def _add(self) -> None:
        dlg = TimetableEntryDialog(self, None)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._load()

    def _edit(self) -> None:
        tid = self._selected_id()
        if tid is None:
            QMessageBox.information(self, "Select", "Select a row to edit.")
            return
        dlg = TimetableEntryDialog(self, tid)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._load()

    def _delete(self) -> None:
        tid = self._selected_id()
        if tid is None:
            QMessageBox.information(self, "Select", "Select a row to delete.")
            return
        if (
            QMessageBox.question(self, "Delete", "Remove this timetable entry?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            != QMessageBox.StandardButton.Yes
        ):
            return
        conn = get_connection()
        try:
            conn.execute("DELETE FROM timetable WHERE id = ?", (tid,))
            conn.commit()
        finally:
            conn.close()
        self._load()

    def _populate_filters(self) -> None:
        self._filter_session.blockSignals(True)
        self._filter_course.blockSignals(True)
        self._filter_semester.blockSignals(True)
        self._filter_session.clear()
        self._filter_course.clear()
        self._filter_semester.clear()
        self._filter_session.addItem("All Sessions", None)
        self._filter_course.addItem("All Courses", None)
        self._filter_semester.addItem("All Semesters", None)
        conn = get_connection()
        try:
            for r in conn.execute("SELECT id, label FROM session_years ORDER BY label DESC").fetchall():
                self._filter_session.addItem(r["label"], r["id"])
            for r in conn.execute("SELECT id, code, name FROM courses ORDER BY code").fetchall():
                self._filter_course.addItem(f"{r['code']} — {r['name']}", r["id"])
            for r in conn.execute("SELECT id, name FROM semesters ORDER BY name").fetchall():
                self._filter_semester.addItem(r["name"], r["id"])
        finally:
            conn.close()
        self._filter_session.blockSignals(False)
        self._filter_course.blockSignals(False)
        self._filter_semester.blockSignals(False)

    def _load(self) -> None:
        sess_id = self._filter_session.currentData()
        course_id = self._filter_course.currentData()
        sem_id = self._filter_semester.currentData()
        
        query = """SELECT t.id, COALESCE(sy.label, '—') AS sess_name, COALESCE(c.name, '—') AS course_name,
                          COALESCE(sem.name, '—') AS sem_name, sub.name AS subj, tu.full_name AS teacher, COALESCE(r.name,'') AS room,
                          t.day_of_week, p.label, p.start_time || ' – ' || p.end_time AS slot
                   FROM timetable t
                   LEFT JOIN session_years sy ON sy.id = t.session_id
                   LEFT JOIN courses c ON c.id = t.course_id
                   LEFT JOIN semesters sem ON sem.id = t.semester_id
                   JOIN subjects sub ON sub.id = t.subject_id
                   JOIN users tu ON tu.id = t.teacher_user_id
                   LEFT JOIN rooms r ON r.id = t.room_id
                   JOIN periods p ON p.id = t.period_id
                   WHERE 1=1"""
        params = []
        if sess_id is not None:
            query += " AND t.session_id = ?"
            params.append(sess_id)
        if course_id is not None:
            query += " AND t.course_id = ?"
            params.append(course_id)
        if sem_id is not None:
            query += " AND t.semester_id = ?"
            params.append(sem_id)
        query += " ORDER BY t.day_of_week, p.sort_order, sy.label DESC, c.code, sem.name, sub.code"

        conn = get_connection()
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()
        self._table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            dow = self._days[int(r["day_of_week"]) % 7]
            vals = [r["id"], r["sess_name"], r["course_name"], r["sem_name"], r["subj"], r["teacher"], r["room"], dow, r["label"], r["slot"]]
            for j, v in enumerate(vals):
                self._table.setItem(i, j, QTableWidgetItem(str(v)))

    def _export_pdf(self) -> None:
        # Pre-export "Ask" dialog for parameters
        dlg = TimetableExportDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
            
        data = dlg.result_data()
        sess_id = data["sess_id"]
        course_id = data["course_id"]
        sem_id = data["sem_id"]
        teacher_id = data["teacher_id"]
        
        sess_text = data["sess_text"]
        course_text = data["course_text"]
        sem_text = data["sem_text"]
        teacher_text = data["teacher_text"]

        # Ensure timetables directory exists
        export_dir = Path("timetables")
        export_dir.mkdir(exist_ok=True)
        
        fname_parts = [sess_text, course_text, sem_text]
        if teacher_id is not None:
            fname_parts.append(teacher_text)
            
        filename = "timetable_" + "_".join(fname_parts)
        filename = filename.replace("/", "_").replace(" ", "_").replace("All_Sessions", "All").replace("All_Courses", "All").replace("All_Semesters", "All").replace("All_Teachers", "All") + ".pdf"
        default_path = str(export_dir / filename)

        path, _ = QFileDialog.getSaveFileName(self, "Export Timetable", default_path, "PDF Files (*.pdf)")
        if not path:
            return
            
        from PyQt6.QtPrintSupport import QPrinter
        from PyQt6.QtGui import QTextDocument
        
        # We need the data for this specific query
        query = """SELECT t.id, COALESCE(sy.label, '—') AS sess_name, COALESCE(c.name, '—') AS course_name,
                          COALESCE(sem.name, '—') AS sem_name, sub.name AS subj, tu.full_name AS teacher, COALESCE(r.name,'') AS room,
                          t.day_of_week, p.label, p.start_time || ' – ' || p.end_time AS slot
                   FROM timetable t
                   LEFT JOIN session_years sy ON sy.id = t.session_id
                   LEFT JOIN courses c ON c.id = t.course_id
                   LEFT JOIN semesters sem ON sem.id = t.semester_id
                   JOIN subjects sub ON sub.id = t.subject_id
                   JOIN users tu ON tu.id = t.teacher_user_id
                   LEFT JOIN rooms r ON r.id = t.room_id
                   JOIN periods p ON p.id = t.period_id
                   WHERE 1=1"""
        params = []
        if sess_id is not None:
            query += " AND t.session_id = ?"
            params.append(sess_id)
        if course_id is not None:
            query += " AND t.course_id = ?"
            params.append(course_id)
        if sem_id is not None:
            query += " AND t.semester_id = ?"
            params.append(sem_id)
        if teacher_id is not None:
            query += " AND t.teacher_user_id = ?"
            params.append(teacher_id)
        query += " ORDER BY t.day_of_week, p.sort_order, sy.label DESC, c.code, sem.name, sub.code"

        conn = get_connection()
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()

        # Build HTML string for table conversion
        html = "<html><head><style>"
        html += "table { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 10pt; margin-bottom: 25px; }"
        html += "th { background-color: #333333; color: white; border: 1px solid #555555; padding: 6px; text-align: left; }"
        html += "td { border: 1px solid #cccccc; padding: 6px; color: #111111; }"
        html += "h2 { font-family: sans-serif; color: #111111; font-size: 16pt; margin-bottom: 5px; }"
        html += "h3 { font-family: sans-serif; color: #444444; font-size: 12pt; margin-top: 5px; margin-bottom: 10px; }"
        html += ".day-header { background-color: #f2f2f2; font-weight: bold; border: 1px solid #cccccc; padding: 6px; font-size: 11pt; color: #333333; font-family: sans-serif; margin-bottom: 0px; margin-top: 15px; }"
        html += ".col-period { width: 10%; }"
        html += ".col-time { width: 22%; }"
        html += ".col-room { width: 15%; }"
        html += "</style></head><body>"
        html += "<h2>Timetable</h2>"
        header_info = [f"Session: {sess_text}", f"Course: {course_text}", f"Semester: {sem_text}"]
        if teacher_id is not None:
            header_info.append(f"Teacher: {teacher_text}")
        html += f"<h3>{' | '.join(header_info)}</h3>"
        
        show_teacher_col = (teacher_id is None)
        
        days_map = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        # Group rows by day for separate tables
        for d_idx, day_name in enumerate(days_map):
            day_rows = [r for r in rows if int(r["day_of_week"]) == d_idx]
            if not day_rows:
                continue
                
            html += f"<div class='day-header'>{day_name}</div>"
            html += "<table><thead><tr>"
            html += "<th class='col-period'>Period</th><th class='col-time'>Time</th><th>Subject</th>"
            if show_teacher_col:
                html += "<th>Teacher</th>"
            html += "<th class='col-room'>Room</th>"
            html += "</tr></thead><tbody>"
            
            for r in day_rows:
                html += f"<tr>"
                html += f"<td>{r['label']}</td>"
                html += f"<td>{r['slot']}</td>"
                html += f"<td>{r['subj']}</td>"
                if show_teacher_col:
                    html += f"<td>{r['teacher']}</td>"
                html += f"<td>{r['room']}</td>"
                html += "</tr>"
                
            html += "</tbody></table>"
            
        html += "</body></html>"
        
        doc = QTextDocument()
        doc.setHtml(html)
        
        printer = QPrinter()
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        
        doc.print(printer)
        QMessageBox.information(self, "Export Successful", f"Timetable exported to PDF at {path}")


class AdminCompliance(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._start = QDateEdit()
        self._end = QDateEdit()
        self._start.setCalendarPopup(True)
        self._end.setCalendarPopup(True)
        self._start.setDate(date.today().replace(day=1))
        self._start.dateChanged.connect(self._update_nepali_labels)
        self._end.dateChanged.connect(self._update_nepali_labels)
        
        self._nepali_start_lbl = QLabel()
        self._nepali_end_lbl = QLabel()
        self._nepali_start_lbl.setStyleSheet("color: #89b4fa; font-weight: bold;")
        self._nepali_end_lbl.setStyleSheet("color: #89b4fa; font-weight: bold;")

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<h3>Compliance reporting</h3>"))
        lay.addWidget(
            QLabel(
                "Generates audit-ready, row-level attendance suitable for funding and regulatory review. "
                "Includes period times, subject, student identifiers, teacher, status, capture method, and room."
            )
        )
        
        row = QHBoxLayout()
        row.addWidget(QLabel("From"))
        row.addWidget(self._start)
        row.addWidget(self._nepali_start_lbl)
        row.addWidget(QLabel("To"))
        row.addWidget(self._end)
        row.addWidget(self._nepali_end_lbl)
        row.addWidget(export_btn)
        lay.addLayout(row)
        lay.addWidget(self._preview)
        
        self._update_nepali_labels()

    def _update_nepali_labels(self) -> None:
        s = self._start.date().toString("yyyy-MM-dd")
        e = self._end.date().toString("yyyy-MM-dd")
        self._nepali_start_lbl.setText(f"({ad_to_bs(s)})")
        self._nepali_end_lbl.setText(f"({ad_to_bs(e)})")

    def _export(self) -> None:
        start = self._start.date().toString("yyyy-MM-dd")
        end = self._end.date().toString("yyyy-MM-dd")
        conn = get_connection()
        try:
            csv_text = services.compliance_report_csv(conn, start, end)
        finally:
            conn.close()
        self._preview.setPlainText(csv_text[:8000] + ("\n…" if len(csv_text) > 8000 else ""))
        path, _ = QFileDialog.getSaveFileName(
            self, "Save compliance CSV", "", "CSV files (*.csv);;All files (*)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(csv_text)
            QMessageBox.information(self, "Saved", f"Wrote {path}")


class AdminMultimodal(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._student_pick = QComboBox()
        self._qr_label = QLabel()
        self._qr_label.setMinimumSize(220, 220)
        self._rfid = QLineEdit()
        self._rfid.setPlaceholderText("Simulate RFID scan (student code)")
        self._devices = QTextEdit()
        self._devices.setReadOnly(True)
        gen = QPushButton("Generate student QR")
        gen.clicked.connect(self._gen_qr)
        sim = QPushButton("Log simulated RFID check-in")
        sim.clicked.connect(self._sim_rfid)
        bio = QPushButton("Simulate biometric OK")
        bio.clicked.connect(lambda: QMessageBox.information(
            self, "Biometric",
            "Hardware integration: connect fingerprint or face SDK; this demo only confirms operator action.",
        ))
        self._load_students()
        self._load_devices()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<h3>Multi-modal capture</h3>"))
        lay.addWidget(
            QLabel(
                "QR codes encode the student identity for kiosk swipes. RFID and biometric readers "
                "typically POST to the same service; here we log intent and tie to manual attendance workflows."
            )
        )
        row = QHBoxLayout()
        row.addWidget(QLabel("Student for QR"))
        row.addWidget(self._student_pick)
        row.addWidget(gen)
        lay.addLayout(row)
        lay.addWidget(self._qr_label)
        lay.addWidget(QLabel("RFID simulation"))
        lay.addWidget(self._rfid)
        lay.addWidget(sim)
        lay.addWidget(bio)
        lay.addWidget(QLabel("Registered devices"))
        lay.addWidget(self._devices)

    def _load_students(self) -> None:
        self._student_pick.clear()
        conn = get_connection()
        try:
            rows = conn.execute(
                """SELECT u.id, u.full_name, s.student_code FROM users u
                   JOIN students s ON s.user_id = u.id ORDER BY u.full_name"""
            ).fetchall()
        finally:
            conn.close()
        for r in rows:
            self._student_pick.addItem(f"{r['full_name']} ({r['student_code']})", r["id"])

    def _load_devices(self) -> None:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT device_type, name, is_active FROM multimodal_devices ORDER BY id"
            ).fetchall()
        finally:
            conn.close()
        lines = [f"{r['device_type']}: {r['name']} — {'active' if r['is_active'] else 'off'}" for r in rows]
        self._devices.setPlainText("\n".join(lines) if lines else "No devices.")

    def _gen_qr(self) -> None:
        try:
            import qrcode
        except ImportError:
            QMessageBox.warning(self, "qrcode", "Install the qrcode package: pip install qrcode[pil]")
            return
        uid = self._student_pick.currentData()
        if uid is None:
            return
        payload = format_student_qr(int(uid))
        img = qrcode.make(payload)
        buf = img.convert("RGB")
        data = buf.tobytes("raw", "RGB")
        qimg = QImage(data, buf.width, buf.height, QImage.Format.Format_RGB888)
        self._qr_label.setPixmap(QPixmap.fromImage(qimg).scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio))

    def _sim_rfid(self) -> None:
        code = self._rfid.text().strip()
        if not code:
            QMessageBox.information(self, "RFID", "Enter a student code to simulate.")
            return
        QMessageBox.information(
            self, "RFID",
            f"Reader would resolve {code} to a student and open the period attendance screen with capture_method=rfid.",
        )


class AdminGeofence(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._lat = QLineEdit()
        self._lng = QLineEdit()
        self._radius = QSpinBox()
        self._radius.setRange(10, 5000)
        self._radius.setSuffix(" m")
        self._class_only = QComboBox()
        self._class_only.addItems(["Campus-wide", "Require classroom beacon"])
        save = QPushButton("Save policy")
        save.clicked.connect(self._save)
        self._load()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<h3>Geofencing (mobile check-in)</h3>"))
        lay.addWidget(
            QLabel(
                "Mobile clients should send GPS fixes; the server accepts check-ins only when "
                "distance to campus (or room beacon) is within radius. This panel stores policy parameters."
            )
        )
        form = QFormLayout()
        form.addRow("Campus latitude", self._lat)
        form.addRow("Campus longitude", self._lng)
        form.addRow("Radius", self._radius)
        form.addRow("Strictness", self._class_only)
        lay.addLayout(form)
        lay.addWidget(save)
        lay.addStretch()

    def _load(self) -> None:
        conn = get_connection()
        try:
            r = conn.execute("SELECT campus_lat, campus_lng, radius_meters, classroom_only FROM geofence_settings WHERE id = 1").fetchone()
        finally:
            conn.close()
        if r:
            self._lat.setText(str(r["campus_lat"] or ""))
            self._lng.setText(str(r["campus_lng"] or ""))
            self._radius.setValue(int(r["radius_meters"] or 100))
            self._class_only.setCurrentIndex(1 if r["classroom_only"] else 0)

    def _save(self) -> None:
        try:
            lat = float(self._lat.text())
            lng = float(self._lng.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid", "Enter numeric latitude and longitude.")
            return
        r = self._radius.value()
        c_only = 1 if self._class_only.currentIndex() == 1 else 0
        conn = get_connection()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO geofence_settings (id, campus_lat, campus_lng, radius_meters, classroom_only)
                   VALUES (1, ?, ?, ?, ?)""",
                (lat, lng, float(r), c_only),
            )
            conn.commit()
        finally:
            conn.close()
        QMessageBox.information(self, "Saved", "Geofence policy updated.")


class AdminSmsSettings(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._enabled = QCheckBox("Enable Twilio SMS for absence alerts")
        self._sid = QLineEdit()
        self._token = QLineEdit()
        self._token.setEchoMode(QLineEdit.EchoMode.Password)
        self._from_num = QLineEdit()
        self._from_num.setPlaceholderText("E.164 e.g. +15551234567")
        self._test_to = QLineEdit()
        self._test_to.setPlaceholderText("Test recipient +1555…")
        save = QPushButton("Save SMS settings")
        save.clicked.connect(self._save)
        test = QPushButton("Send test SMS")
        test.clicked.connect(self._test)
        self._hint = QLabel("")
        self._hint.setWordWrap(True)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<h3>SMS (Twilio)</h3>"))
        lay.addWidget(
            QLabel(
                "Credentials can be set here or via environment variables "
                "(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, TWILIO_ENABLED). "
                "A .env file in the app folder is loaded automatically if python-dotenv is installed."
            )
        )
        lay.addWidget(self._enabled)
        form = QFormLayout()
        form.addRow("Account SID", self._sid)
        form.addRow("Auth token", self._token)
        form.addRow("From number", self._from_num)
        lay.addLayout(form)
        lay.addWidget(save)
        lay.addWidget(QLabel("Test delivery"))
        tf = QHBoxLayout()
        tf.addWidget(self._test_to)
        tf.addWidget(test)
        lay.addLayout(tf)
        lay.addWidget(self._hint)
        lay.addStretch()
        self._load()

    def _load(self) -> None:
        self._enabled.setChecked((get_setting(KEY_TWILIO_ENABLED, "") or "") in ("1", "true", "yes"))
        self._sid.setText(get_setting(KEY_TWILIO_ACCOUNT_SID, "") or "")
        self._token.setText(get_setting(KEY_TWILIO_AUTH_TOKEN, "") or "")
        self._from_num.setText(get_setting(KEY_TWILIO_FROM_NUMBER, "") or "")

    def _persist(self) -> None:
        set_setting(KEY_TWILIO_ENABLED, "1" if self._enabled.isChecked() else "0")
        set_setting(KEY_TWILIO_ACCOUNT_SID, self._sid.text().strip())
        set_setting(KEY_TWILIO_AUTH_TOKEN, self._token.text().strip())
        set_setting(KEY_TWILIO_FROM_NUMBER, self._from_num.text().strip())

    def _save(self) -> None:
        self._persist()
        QMessageBox.information(self, "Saved", "SMS settings stored in the local database.")

    def _test(self) -> None:
        to = self._test_to.text().strip()
        if not to:
            QMessageBox.warning(self, "Recipient", "Enter a test phone number (E.164).")
            return
        self._persist()
        ok, detail = send_sms(to, "Attendance app: test message.")
        self._hint.setText(detail)
        if ok:
            QMessageBox.information(self, "Twilio", detail)
        else:
            QMessageBox.warning(self, "Twilio", detail)


class AdminSubjects(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["ID", "Code", "Name"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(2, 200)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.itemSelectionChanged.connect(self._on_select)

        self._new_code = QLineEdit()
        self._new_code.setPlaceholderText("Code e.g. PHY101")
        self._new_name = QLineEdit()
        self._new_name.setPlaceholderText("Name e.g. Intro to Physics")
        
        add_btn = QPushButton("Add Subject")
        add_btn.clicked.connect(self._add)
        
        upd_btn = QPushButton("Update Selected")
        upd_btn.clicked.connect(self._update)
        
        del_btn = QPushButton("Delete Selected")
        del_btn.clicked.connect(self._delete)
        
        ref_btn = QPushButton("Reload")
        ref_btn.clicked.connect(self._load)

        form = QFormLayout()
        form.addRow("Subject Code", self._new_code)
        form.addRow("Subject Name", self._new_name)
        
        row = QHBoxLayout()
        row.addWidget(add_btn)
        row.addWidget(upd_btn)
        row.addWidget(del_btn)
        row.addWidget(ref_btn)
        row.addStretch()

        lay = QVBoxLayout(self)
        title = QLabel("Subjects Directory")
        title.setProperty("styleClass", "h1")
        lay.addWidget(title)
        lay.addLayout(form)
        lay.addLayout(row)
        lay.addWidget(self._table)
        self._load()

    def _selected_id(self) -> int | None:
        items = self._table.selectedItems()
        if not items:
            return None
        r = items[0].row()
        item = self._table.item(r, 0)
        return int(item.text()) if item else None

    def _on_select(self) -> None:
        items = self._table.selectedItems()
        if not items:
            self._new_code.clear()
            self._new_name.clear()
            return
        r = items[0].row()
        code_item = self._table.item(r, 1)
        name_item = self._table.item(r, 2)
        if code_item and name_item:
            self._new_code.setText(code_item.text())
            self._new_name.setText(name_item.text())

    def _load(self) -> None:
        conn = get_connection()
        try:
            rows = conn.execute("SELECT id, code, name FROM subjects ORDER BY code").fetchall()
        finally:
            conn.close()
        self._table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, key in enumerate(["id", "code", "name"]):
                self._table.setItem(i, j, QTableWidgetItem(str(r[key] or "")))

    def _add(self) -> None:
        code = self._new_code.text().strip()
        name = self._new_name.text().strip()
        if not code or not name:
            QMessageBox.warning(self, "Input Error", "Both code and name are required.")
            return
        conn = get_connection()
        try:
            conn.execute("INSERT INTO subjects (code, name) VALUES (?, ?)", (code, name))
            conn.commit()
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Conflict", "Subject code already exists.")
            return
        finally:
            conn.close()
        self._new_code.clear()
        self._new_name.clear()
        self._load()

    def _update(self) -> None:
        sid = self._selected_id()
        if sid is None:
            QMessageBox.warning(self, "Selection Required", "Select a subject from the table to update.")
            return
        code = self._new_code.text().strip()
        name = self._new_name.text().strip()
        if not code or not name:
            QMessageBox.warning(self, "Input Error", "Enter the new code and name before updating.")
            return
        conn = get_connection()
        try:
            conn.execute("UPDATE subjects SET code = ?, name = ? WHERE id = ?", (code, name, sid))
            conn.commit()
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Conflict", "Another subject with that code already exists.")
            return
        finally:
            conn.close()
        self._new_code.clear()
        self._new_name.clear()
        self._load()

    def _delete(self) -> None:
        sid = self._selected_id()
        if sid is None:
            QMessageBox.warning(self, "Selection Required", "Select a subject from the table to delete.")
            return
        res = QMessageBox.question(
            self, "Confirm Deletion",
            "Are you sure? This will cascade and delete all timetables, enrollments, and attendance records linked to this subject.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res != QMessageBox.StandardButton.Yes:
            return
        conn = get_connection()
        try:
            conn.execute("DELETE FROM subjects WHERE id = ?", (sid,))
            conn.commit()
        finally:
            conn.close()
        self._new_code.clear()
        self._new_name.clear()
        self._load()


class AdminRooms(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["ID", "Name", "Building"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(1, 200)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.itemSelectionChanged.connect(self._on_select)

        self._new_name = QLineEdit()
        self._new_name.setPlaceholderText("Room Name e.g. A-101")
        self._new_building = QLineEdit()
        self._new_building.setPlaceholderText("Building e.g. North Hall")
        
        add_btn = QPushButton("Add Room")
        add_btn.clicked.connect(self._add)
        
        upd_btn = QPushButton("Update Selected")
        upd_btn.clicked.connect(self._update)
        
        del_btn = QPushButton("Delete Selected")
        del_btn.clicked.connect(self._delete)
        
        ref_btn = QPushButton("Reload")
        ref_btn.clicked.connect(self._load)

        form = QFormLayout()
        form.addRow("Room Name", self._new_name)
        form.addRow("Building", self._new_building)
        
        row = QHBoxLayout()
        row.addWidget(add_btn)
        row.addWidget(upd_btn)
        row.addWidget(del_btn)
        row.addWidget(ref_btn)
        row.addStretch()

        lay = QVBoxLayout(self)
        title = QLabel("Rooms Directory")
        title.setProperty("styleClass", "h1")
        lay.addWidget(title)
        lay.addLayout(form)
        lay.addLayout(row)
        lay.addWidget(self._table)
        self._load()

    def _selected_id(self) -> int | None:
        items = self._table.selectedItems()
        if not items:
            return None
        r = items[0].row()
        item = self._table.item(r, 0)
        return int(item.text()) if item else None

    def _on_select(self) -> None:
        items = self._table.selectedItems()
        if not items:
            self._new_name.clear()
            self._new_building.clear()
            return
        r = items[0].row()
        name_item = self._table.item(r, 1)
        bldg_item = self._table.item(r, 2)
        if name_item and bldg_item:
            self._new_name.setText(name_item.text())
            self._new_building.setText(bldg_item.text())

    def _load(self) -> None:
        conn = get_connection()
        try:
            rows = conn.execute("SELECT id, name, building FROM rooms ORDER BY name").fetchall()
        finally:
            conn.close()
        self._table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, key in enumerate(["id", "name", "building"]):
                self._table.setItem(i, j, QTableWidgetItem(str(r[key] or "")))

    def _add(self) -> None:
        name = self._new_name.text().strip()
        bldg = self._new_building.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Room name is required.")
            return
        conn = get_connection()
        try:
            conn.execute("INSERT INTO rooms (name, building) VALUES (?, ?)", (name, bldg))
            conn.commit()
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Error", "Database constraint failed.")
            return
        finally:
            conn.close()
        self._new_name.clear()
        self._new_building.clear()
        self._load()

    def _update(self) -> None:
        rid = self._selected_id()
        if rid is None:
            QMessageBox.warning(self, "Selection Required", "Select a room from the table to update.")
            return
        name = self._new_name.text().strip()
        bldg = self._new_building.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Room name is required.")
            return
        conn = get_connection()
        try:
            conn.execute("UPDATE rooms SET name = ?, building = ? WHERE id = ?", (name, bldg, rid))
            conn.commit()
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Error", "Database constraint failed.")
            return
        finally:
            conn.close()
        self._new_name.clear()
        self._new_building.clear()
        self._load()

    def _delete(self) -> None:
        rid = self._selected_id()
        if rid is None:
            QMessageBox.warning(self, "Selection Required", "Select a room from the table to delete.")
            return
        res = QMessageBox.question(
            self, "Confirm Deletion",
            "Are you sure? This action might cascade into associated Timetables and devices.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res != QMessageBox.StandardButton.Yes:
            return
        conn = get_connection()
        try:
            conn.execute("DELETE FROM rooms WHERE id = ?", (rid,))
            conn.commit()
        finally:
            conn.close()
        self._new_building.clear()
        self._load()


class AdminPeriods(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["ID", "Label", "Start Time", "End Time", "Sort Order"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(1, 200)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.itemSelectionChanged.connect(self._on_select)

        self._new_label = QLineEdit()
        self._new_label.setPlaceholderText("Label e.g. Period 1")
        self._new_start = QLineEdit()
        self._new_start.setPlaceholderText("Start e.g. 09:00")
        self._new_end = QLineEdit()
        self._new_end.setPlaceholderText("End e.g. 10:00")
        self._new_sort = QSpinBox()
        self._new_sort.setRange(0, 999)
        
        add_btn = QPushButton("Add Period")
        add_btn.clicked.connect(self._add)
        
        upd_btn = QPushButton("Update Selected")
        upd_btn.clicked.connect(self._update)
        
        del_btn = QPushButton("Delete Selected")
        del_btn.clicked.connect(self._delete)
        
        ref_btn = QPushButton("Reload")
        ref_btn.clicked.connect(self._load)

        form = QFormLayout()
        form.addRow("Label", self._new_label)
        form.addRow("Start Time", self._new_start)
        form.addRow("End Time", self._new_end)
        form.addRow("Sort Order", self._new_sort)
        
        row = QHBoxLayout()
        row.addWidget(add_btn)
        row.addWidget(upd_btn)
        row.addWidget(del_btn)
        row.addWidget(ref_btn)
        row.addStretch()

        lay = QVBoxLayout(self)
        title = QLabel("Periods Directory")
        title.setProperty("styleClass", "h1")
        lay.addWidget(title)
        lay.addLayout(form)
        lay.addLayout(row)
        lay.addWidget(self._table)
        self._load()

    def _selected_id(self) -> int | None:
        items = self._table.selectedItems()
        if not items:
            return None
        r = items[0].row()
        item = self._table.item(r, 0)
        return int(item.text()) if item else None

    def _on_select(self) -> None:
        items = self._table.selectedItems()
        if not items:
            self._new_label.clear()
            self._new_start.clear()
            self._new_end.clear()
            self._new_sort.setValue(0)
            return
        r = items[0].row()
        lbl_item = self._table.item(r, 1)
        st_item = self._table.item(r, 2)
        end_item = self._table.item(r, 3)
        sort_item = self._table.item(r, 4)
        if lbl_item and st_item and end_item and sort_item:
            self._new_label.setText(lbl_item.text())
            self._new_start.setText(st_item.text())
            self._new_end.setText(end_item.text())
            try:
                self._new_sort.setValue(int(sort_item.text()))
            except ValueError:
                self._new_sort.setValue(0)

    def _load(self) -> None:
        conn = get_connection()
        try:
            rows = conn.execute("SELECT id, label, start_time, end_time, sort_order FROM periods ORDER BY sort_order, id").fetchall()
        finally:
            conn.close()
        self._table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, key in enumerate(["id", "label", "start_time", "end_time", "sort_order"]):
                self._table.setItem(i, j, QTableWidgetItem(str(r[key] if r[key] is not None else "")))

    def _add(self) -> None:
        lbl = self._new_label.text().strip()
        st = self._new_start.text().strip()
        end = self._new_end.text().strip()
        sort = self._new_sort.value()
        if not lbl or not st or not end:
            QMessageBox.warning(self, "Input Error", "Label, Start Time, and End Time are required.")
            return
        conn = get_connection()
        try:
            conn.execute("INSERT INTO periods (label, start_time, end_time, sort_order) VALUES (?, ?, ?, ?)", (lbl, st, end, sort))
            conn.commit()
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Error", "Database constraint failed.")
            return
        finally:
            conn.close()
        self._new_label.clear()
        self._new_start.clear()
        self._new_end.clear()
        self._new_sort.setValue(0)
        self._load()

    def _update(self) -> None:
        pid = self._selected_id()
        if pid is None:
            QMessageBox.warning(self, "Selection Required", "Select a period from the table to update.")
            return
        lbl = self._new_label.text().strip()
        st = self._new_start.text().strip()
        end = self._new_end.text().strip()
        sort = self._new_sort.value()
        if not lbl or not st or not end:
            QMessageBox.warning(self, "Input Error", "Label, Start Time, and End Time are required.")
            return
        conn = get_connection()
        try:
            conn.execute("UPDATE periods SET label = ?, start_time = ?, end_time = ?, sort_order = ? WHERE id = ?", (lbl, st, end, sort, pid))
            conn.commit()
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Error", "Database constraint failed.")
            return
        finally:
            conn.close()
        self._new_label.clear()
        self._new_start.clear()
        self._new_end.clear()
        self._new_sort.setValue(0)
        self._load()

    def _delete(self) -> None:
        pid = self._selected_id()
        if pid is None:
            QMessageBox.warning(self, "Selection Required", "Select a period from the table to delete.")
            return
        res = QMessageBox.question(
            self, "Confirm Deletion",
            "Are you sure? This action will cascade into associated Timetables and Attendance Records.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res != QMessageBox.StandardButton.Yes:
            return
        conn = get_connection()
        try:
            conn.execute("DELETE FROM periods WHERE id = ?", (pid,))
            conn.commit()
        finally:
            conn.close()
        self._new_label.clear()
        self._new_start.clear()
        self._new_end.clear()
        self._new_sort.setValue(0)
        self._load()


class AdminCourses(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["ID", "Code", "Name"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(2, 200)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.itemSelectionChanged.connect(self._on_select)

        self._new_code = QLineEdit()
        self._new_code.setPlaceholderText("Code e.g. CS101")
        self._new_name = QLineEdit()
        self._new_name.setPlaceholderText("Name e.g. Computer Science BSc")
        
        add_btn = QPushButton("Add Course")
        add_btn.clicked.connect(self._add)
        
        upd_btn = QPushButton("Update Selected")
        upd_btn.clicked.connect(self._update)
        
        del_btn = QPushButton("Delete Selected")
        del_btn.clicked.connect(self._delete)
        
        ref_btn = QPushButton("Reload")
        ref_btn.clicked.connect(self._load)

        form = QFormLayout()
        form.addRow("Course Code", self._new_code)
        form.addRow("Course Name", self._new_name)
        
        row = QHBoxLayout()
        row.addWidget(add_btn)
        row.addWidget(upd_btn)
        row.addWidget(del_btn)
        row.addWidget(ref_btn)
        row.addStretch()

        lay = QVBoxLayout(self)
        title = QLabel("Courses Directory")
        title.setProperty("styleClass", "h1")
        lay.addWidget(title)
        lay.addLayout(form)
        lay.addLayout(row)
        lay.addWidget(self._table)
        self._load()

    def _selected_id(self) -> int | None:
        items = self._table.selectedItems()
        if not items:
            return None
        r = items[0].row()
        item = self._table.item(r, 0)
        return int(item.text()) if item else None

    def _on_select(self) -> None:
        items = self._table.selectedItems()
        if not items:
            self._new_code.clear()
            self._new_name.clear()
            return
        r = items[0].row()
        code_item = self._table.item(r, 1)
        name_item = self._table.item(r, 2)
        if code_item and name_item:
            self._new_code.setText(code_item.text())
            self._new_name.setText(name_item.text())

    def _load(self) -> None:
        conn = get_connection()
        try:
            rows = conn.execute("SELECT id, code, name FROM courses ORDER BY code").fetchall()
        finally:
            conn.close()
        self._table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, key in enumerate(["id", "code", "name"]):
                self._table.setItem(i, j, QTableWidgetItem(str(r[key] or "")))

    def _add(self) -> None:
        code = self._new_code.text().strip()
        name = self._new_name.text().strip()
        if not code or not name:
            QMessageBox.warning(self, "Input Error", "Both code and name are required.")
            return
        conn = get_connection()
        try:
            conn.execute("INSERT INTO courses (code, name) VALUES (?, ?)", (code, name))
            conn.commit()
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Conflict", "Course code already exists.")
            return
        finally:
            conn.close()
        self._new_code.clear()
        self._new_name.clear()
        self._load()

    def _update(self) -> None:
        sid = self._selected_id()
        if sid is None:
            QMessageBox.warning(self, "Selection Required", "Select a course from the table to update.")
            return
        code = self._new_code.text().strip()
        name = self._new_name.text().strip()
        if not code or not name:
            QMessageBox.warning(self, "Input Error", "Enter the new code and name before updating.")
            return
        conn = get_connection()
        try:
            conn.execute("UPDATE courses SET code = ?, name = ? WHERE id = ?", (code, name, sid))
            conn.commit()
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Conflict", "Another course with that code already exists.")
            return
        finally:
            conn.close()
        self._new_code.clear()
        self._new_name.clear()
        self._load()

    def _delete(self) -> None:
        sid = self._selected_id()
        if sid is None:
            QMessageBox.warning(self, "Selection Required", "Select a course from the table to delete.")
            return
        res = QMessageBox.question(
            self, "Confirm Deletion",
            "Are you sure? This will cascade and delete all timetables linked to this course.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res != QMessageBox.StandardButton.Yes:
            return
        conn = get_connection()
        try:
            conn.execute("DELETE FROM courses WHERE id = ?", (sid,))
            conn.commit()
        finally:
            conn.close()
        self._new_code.clear()
        self._new_name.clear()
        self._load()


class AdminSemesters(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["ID", "Name"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(1, 200)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.itemSelectionChanged.connect(self._on_select)

        self._new_name = QLineEdit()
        self._new_name.setPlaceholderText("Name e.g. Semester 1")
        
        add_btn = QPushButton("Add Semester")
        add_btn.clicked.connect(self._add)
        
        upd_btn = QPushButton("Update Selected")
        upd_btn.clicked.connect(self._update)
        
        del_btn = QPushButton("Delete Selected")
        del_btn.clicked.connect(self._delete)
        
        ref_btn = QPushButton("Reload")
        ref_btn.clicked.connect(self._load)

        form = QFormLayout()
        form.addRow("Semester Name", self._new_name)
        
        row = QHBoxLayout()
        row.addWidget(add_btn)
        row.addWidget(upd_btn)
        row.addWidget(del_btn)
        row.addWidget(ref_btn)
        row.addStretch()

        lay = QVBoxLayout(self)
        title = QLabel("Semesters Directory")
        title.setProperty("styleClass", "h1")
        lay.addWidget(title)
        lay.addLayout(form)
        lay.addLayout(row)
        lay.addWidget(self._table)
        self._load()

    def _selected_id(self) -> int | None:
        items = self._table.selectedItems()
        if not items:
            return None
        r = items[0].row()
        item = self._table.item(r, 0)
        return int(item.text()) if item else None

    def _on_select(self) -> None:
        items = self._table.selectedItems()
        if not items:
            self._new_name.clear()
            return
        r = items[0].row()
        name_item = self._table.item(r, 1)
        if name_item:
            self._new_name.setText(name_item.text())

    def _load(self) -> None:
        conn = get_connection()
        try:
            rows = conn.execute("SELECT id, name FROM semesters ORDER BY name").fetchall()
        finally:
            conn.close()
        self._table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, key in enumerate(["id", "name"]):
                self._table.setItem(i, j, QTableWidgetItem(str(r[key] or "")))

    def _add(self) -> None:
        name = self._new_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Semester name is required.")
            return
        conn = get_connection()
        try:
            conn.execute("INSERT INTO semesters (name) VALUES (?)", (name,))
            conn.commit()
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Conflict", "Semester name already exists.")
            return
        finally:
            conn.close()
        self._new_name.clear()
        self._load()

    def _update(self) -> None:
        sid = self._selected_id()
        if sid is None:
            QMessageBox.warning(self, "Selection Required", "Select a semester from the table to update.")
            return
        name = self._new_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Enter the new name before updating.")
            return
        conn = get_connection()
        try:
            conn.execute("UPDATE semesters SET name = ? WHERE id = ?", (name, sid))
            conn.commit()
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Conflict", "Another semester with that name already exists.")
            return
        finally:
            conn.close()
        self._new_name.clear()
        self._load()

    def _delete(self) -> None:
        sid = self._selected_id()
        if sid is None:
            QMessageBox.warning(self, "Selection Required", "Select a semester from the table to delete.")
            return
        res = QMessageBox.question(
            self, "Confirm Deletion",
            "Are you sure? This will cascade and delete all timetables linked to this semester.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res != QMessageBox.StandardButton.Yes:
            return
        conn = get_connection()
        try:
            conn.execute("DELETE FROM semesters WHERE id = ?", (sid,))
            conn.commit()
        finally:
            conn.close()
        self._new_name.clear()
        self._load()


class AdminSessions(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["ID", "Label", "Start Date", "End Date"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(1, 200)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.itemSelectionChanged.connect(self._on_select)

        self._new_label = QLineEdit()
        self._new_label.setPlaceholderText("Label e.g. 2026/2027 Fall")
        self._new_start = QDateEdit()
        self._new_start.setCalendarPopup(True)
        self._new_start.setDate(date.today())
        self._new_end = QDateEdit()
        self._new_end.setCalendarPopup(True)
        self._new_end.setDate(date.today())
        
        add_btn = QPushButton("Add Session")
        add_btn.clicked.connect(self._add)
        
        upd_btn = QPushButton("Update Selected")
        upd_btn.clicked.connect(self._update)
        
        del_btn = QPushButton("Delete Selected")
        del_btn.clicked.connect(self._delete)
        
        ref_btn = QPushButton("Reload")
        ref_btn.clicked.connect(self._load)

        form = QFormLayout()
        form.addRow("Label", self._new_label)
        form.addRow("Start Date", self._new_start)
        form.addRow("End Date", self._new_end)
        
        row = QHBoxLayout()
        row.addWidget(add_btn)
        row.addWidget(upd_btn)
        row.addWidget(del_btn)
        row.addWidget(ref_btn)
        row.addStretch()

        lay = QVBoxLayout(self)
        title = QLabel("Session Years")
        title.setProperty("styleClass", "h1")
        lay.addWidget(title)
        lay.addLayout(form)
        lay.addLayout(row)
        lay.addWidget(self._table)
        self._load()

    def _selected_id(self) -> int | None:
        items = self._table.selectedItems()
        if not items:
            return None
        r = items[0].row()
        item = self._table.item(r, 0)
        return int(item.text()) if item else None

    def _on_select(self) -> None:
        items = self._table.selectedItems()
        if not items:
            self._new_label.clear()
            self._new_start.setDate(date.today())
            self._new_end.setDate(date.today())
            return
        r = items[0].row()
        label_item = self._table.item(r, 1)
        start_item = self._table.item(r, 2)
        end_item = self._table.item(r, 3)
        if label_item and start_item and end_item:
            self._new_label.setText(label_item.text())
            try:
                self._new_start.setDate(date.fromisoformat(start_item.text()))
            except ValueError:
                self._new_start.setDate(date.today())
            try:
                self._new_end.setDate(date.fromisoformat(end_item.text()))
            except ValueError:
                self._new_end.setDate(date.today())

    def _load(self) -> None:
        conn = get_connection()
        try:
            rows = conn.execute("SELECT id, label, start_date, end_date FROM session_years ORDER BY id DESC").fetchall()
        finally:
            conn.close()
        self._table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, key in enumerate(["id", "label", "start_date", "end_date"]):
                self._table.setItem(i, j, QTableWidgetItem(str(r[key] or "")))

    def _add(self) -> None:
        lbl = self._new_label.text().strip()
        sd = self._new_start.date().toString(Qt.DateFormat.ISODate)
        ed = self._new_end.date().toString(Qt.DateFormat.ISODate)
        if not lbl:
            QMessageBox.warning(self, "Input Error", "Session Label is required.")
            return
        if self._new_start.date() > self._new_end.date():
            QMessageBox.warning(self, "Input Error", "Start Date must be before End Date.")
            return
        conn = get_connection()
        try:
            conn.execute("INSERT INTO session_years (label, start_date, end_date) VALUES (?, ?, ?)", (lbl, sd, ed))
            conn.commit()
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Conflict", "Session label already exists.")
            return
        finally:
            conn.close()
        self._new_label.clear()
        self._load()

    def _update(self) -> None:
        sid = self._selected_id()
        if sid is None:
            QMessageBox.warning(self, "Selection Required", "Select a session from the table to update.")
            return
        lbl = self._new_label.text().strip()
        sd = self._new_start.date().toString(Qt.DateFormat.ISODate)
        ed = self._new_end.date().toString(Qt.DateFormat.ISODate)
        if not lbl:
            QMessageBox.warning(self, "Input Error", "Session Label is required.")
            return
        if self._new_start.date() > self._new_end.date():
            QMessageBox.warning(self, "Input Error", "Start Date must be before End Date.")
            return
        conn = get_connection()
        try:
            conn.execute("UPDATE session_years SET label = ?, start_date = ?, end_date = ? WHERE id = ?", (lbl, sd, ed, sid))
            conn.commit()
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Conflict", "Another session with that label already exists.")
            return
        finally:
            conn.close()
        self._new_label.clear()
        self._load()

    def _delete(self) -> None:
        sid = self._selected_id()
        if sid is None:
            QMessageBox.warning(self, "Selection Required", "Select a session from the table to delete.")
            return
        res = QMessageBox.question(
            self, "Confirm Deletion",
            "Are you sure? This will cascade and delete all timetables linked to this session.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res != QMessageBox.StandardButton.Yes:
            return
        conn = get_connection()
        try:
            conn.execute("DELETE FROM session_years WHERE id = ?", (sid,))
            conn.commit()
        finally:
            conn.close()
        self._new_label.clear()
        self._load()


def build_admin_pages() -> list[tuple[str, QWidget]]:
    return [
        ("Overview", AdminDashboard()),
        ("Session Years", AdminSessions()),
        ("Courses", AdminCourses()),
        ("Semesters", AdminSemesters()),
        ("Subjects", AdminSubjects()),
        ("Rooms", AdminRooms()),
        ("Periods", AdminPeriods()),
        ("Users & roles", AdminUsers()),
        ("Timetable & rooms", AdminTimetable()),
        ("SMS (Twilio)", AdminSmsSettings()),
        ("Compliance export", AdminCompliance()),
        ("Multi-modal capture", AdminMultimodal()),
        ("Geofencing", AdminGeofence()),
    ]
