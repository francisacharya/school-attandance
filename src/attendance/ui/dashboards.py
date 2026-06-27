"""Role-based Dashboards — full feature navigation for all roles."""
import asyncio
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from attendance.utils.api import api_client
from attendance.ui.components import (
    stat_card, m3_card, m3_button, title_label, body_label, 
    M3_SURFACE, M3_PRIMARY, M3_ON_SURFACE_VARIANT
)

# Import segregated screens
from attendance.ui.attendance import (
    TeacherAttendanceScreen, BulkAttendanceScreen, 
    ScanScreen, AdminAttendanceScreen
)
from attendance.ui.timetable import TimetableScreen
from attendance.ui.admin_academic import (
    AdminAcademicScreen, AdminUsersScreen, SettingsScreen
)
from attendance.ui.student_reports import StudentReportsScreen
from attendance.ui.leave_management import StudentLeaveScreen, AdminLeavesScreen

DAYS_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class DashboardScreen:
    def __init__(self, app, role):
        self.app = app
        self.role = role

        scroll = toga.ScrollContainer(horizontal=False, style=Pack(flex=1, background_color=M3_SURFACE))
        root = toga.Box(style=Pack(direction=COLUMN, margin=16, background_color=M3_SURFACE))
        scroll.content = root
        self.container = scroll

        # ── Header ────────────────────────────────────────────────────────────
        hdr = toga.Box(style=Pack(direction=ROW, align_items="center", margin_bottom=8))
        hdr.add(title_label("Attendance Portal", style=Pack(flex=1, margin_bottom=0)))
        hdr.add(m3_button("SIGN OUT", on_press=lambda w: self.app.logout(), variant="text"))
        root.add(hdr)

        uname = app.session.get("full_name", role)
        root.add(body_label(f"Welcome, {uname} • {role.upper()}",
                            style=Pack(margin_bottom=16)))

        # ── Stat cards ────────────────────────────────────────────────────────
        self._stat_row = toga.Box(style=Pack(direction=ROW, margin_bottom=12))
        root.add(self._stat_row)

        # ── Today's schedule ──────────────────────────────────────────────────
        self._schedule_box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=10))
        root.add(self._schedule_box)

        # ── Navigation ────────────────────────────────────────────────────────
        root.add(title_label("Quick Actions", style=Pack(font_size=16, margin_top=8, margin_bottom=8)))
        self._build_nav(root)

        # Load live data
        asyncio.create_task(self._load())

    # ── Nav ───────────────────────────────────────────────────────────────────

    def _build_nav(self, root):
        role = self.role

        def nav(label, fn, variant="tonal"):
            root.add(m3_button(label.upper(), on_press=lambda w: fn(), variant=variant,
                               style=Pack(margin=6)))

        if role == "admin":
            nav("Attendance Records", self._go_admin_attendance)
            nav("Timetable",          self._go_timetable)
            nav("Users & Roles",      self._go_users)
            nav("Leave Requests",     self._go_admin_leaves)
            nav("Settings",           self._go_settings)
            root.add(body_label("ACADEMIC MANAGEMENT",
                                 style=Pack(font_weight="bold", font_size=11,
                                            color=M3_ON_SURFACE_VARIANT, margin_top=16, margin_bottom=8)))
            
            grid = toga.Box(style=Pack(direction=ROW))
            for name, ep in [("SESSIONS", "sessions"), ("COURSES", "courses"),
                              ("SEMESTERS", "semesters"), ("SUBJECTS", "subjects"),
                              ("ROOMS", "rooms"), ("PERIODS", "periods")]:
                root.add(m3_button(name, on_press=lambda w, e=ep, n=name: self._go_entity(e, n), 
                                   variant="outlined", style=Pack(margin=4)))

        elif role == "teacher":
            nav("Take Attendance",   self._go_teacher_attendance)
            nav("Bulk Attendance",   self._go_bulk_attendance)
            nav("My Timetable",      self._go_timetable)

        else:  # student / parent
            if role == "student":
                nav("Scan Class QR", self._go_scan)
            nav("My Reports",        self._go_reports)
            nav("Leave Request",     self._go_student_leave)

    # ── Live data ─────────────────────────────────────────────────────────────

    async def _load(self):
        await self._load_stats()
        await self._load_schedule()

    async def _load_stats(self):
        try:
            if self.role == "admin":
                data = await api_client.get("/admin/stats")
                for label, key, col in [
                    ("Users",    "users",         "#6366f1"),
                    ("Subjects", "subjects",      "#ec4899"),
                    ("Today",    "today_records", "#3b82f6"),
                ]:
                    self._stat_row.add(stat_card(label, data.get(key, "--"), col))

            elif self.role == "teacher":
                data = await api_client.get("/teacher/today-stats")
                for label, key, col in [
                    ("Today",    "today_records", "#6366f1"),
                    ("Present",  "present",       "#10b981"),
                    ("Absent",   "absent",        "#ef4444"),
                    ("Subjects", "total_subjects","#3b82f6"),
                ]:
                    self._stat_row.add(stat_card(label, data.get(key, "--"), col))

            else:
                data = await api_client.get("/attendance/summary")
                for s in data:
                    col = "#10b981" if s.get("status") == "present" else "#ef4444"
                    self._stat_row.add(stat_card(
                        s.get("status", "").capitalize(), s.get("count", 0), col))
        except Exception as e:
            self._stat_row.add(toga.Label(f"Stats error: {e}", style=Pack(color="red")))

    async def _load_schedule(self):
        if self.role not in ("teacher", "student"):
            return
        try:
            ep = "/teacher/schedule" if self.role == "teacher" else "/student/schedule"
            schedule = await api_client.get(ep)
            import nepali_datetime
            today_idx = nepali_datetime.date.today().weekday()
            today_cls = [s for s in schedule if s.get("day_of_week") == today_idx]

            self._schedule_box.add(title_label(
                "Today's Classes" if today_cls else "No classes today",
                style=Pack(font_size=16, margin_bottom=8)))

            for cls in today_cls:
                card = m3_card(style=Pack(margin=6))
                
                row1 = toga.Box(style=Pack(direction=ROW, align_items="center"))
                row1.add(toga.Label(cls.get("subject_name", ""), 
                                    style=Pack(flex=1, font_size=14, font_weight="bold", color=M3_PRIMARY)))
                row1.add(toga.Label(cls.get("period_label",""), 
                                    style=Pack(font_size=11, font_weight="bold", color=M3_ON_SURFACE_VARIANT)))
                card.add(row1)

                card.add(body_label(f"{cls.get('start_time','')} — {cls.get('end_time','')}",
                                     style=Pack(font_size=12, margin_top=2)))
                
                if self.role == "teacher":
                    btn_box = toga.Box(style=Pack(direction=ROW, margin_top=8))
                    btn_box.add(m3_button("TAKE ATTENDANCE", 
                                          on_press=lambda w, c=cls: self._go_attendance_for(c),
                                          variant="tonal", style=Pack(flex=1, margin=2, font_size=10)))
                    card.add(btn_box)
                
                self._schedule_box.add(card)
                self._schedule_box.add(toga.Box(style=Pack(height=4)))
        except Exception as e:
            self._schedule_box.add(toga.Label(f"Schedule error: {e}", style=Pack(color="red")))

    # ── Navigation helpers ────────────────────────────────────────────────────

    def _go_admin_attendance(self):  
        self.app.main_window.content = AdminAttendanceScreen(self.app).container
    def _go_timetable(self):         
        if self.role == "admin":
            from attendance.ui.admin_timetable import AdminTimetableScreen
            self.app.main_window.content = AdminTimetableScreen(self.app).container
        else:
            from attendance.ui.timetable import TimetableScreen
            self.app.main_window.content = TimetableScreen(self.app).container
    def _go_users(self):             
        self.app.main_window.content = AdminUsersScreen(self.app).container
    def _go_admin_leaves(self):      
        self.app.main_window.content = AdminLeavesScreen(self.app).container
    def _go_settings(self):          
        self.app.main_window.content = SettingsScreen(self.app).container
    def _go_teacher_attendance(self):
        self.app.main_window.content = TeacherAttendanceScreen(self.app).container
    def _go_bulk_attendance(self):   
        self.app.main_window.content = BulkAttendanceScreen(self.app).container
    def _go_scan(self):              
        self.app.main_window.content = ScanScreen(self.app).container
    def _go_reports(self):           
        self.app.main_window.content = StudentReportsScreen(self.app).container
    def _go_student_leave(self):     
        self.app.main_window.content = StudentLeaveScreen(self.app).container
    
    def _go_attendance_for(self, cls):
        self.app.main_window.content = TeacherAttendanceScreen(self.app, prefill=cls).container

    def _go_entity(self, endpoint, name):
        self.app.main_window.content = AdminAcademicScreen(self.app, endpoint, name).container
