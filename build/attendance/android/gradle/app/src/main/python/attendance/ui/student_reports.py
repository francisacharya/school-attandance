import asyncio
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from attendance.utils.api import api_client
from attendance.ui.components import back_button, scrollable, title_label

class StudentReportsScreen:
    def __init__(self, app):
        self.app = app
        self.container = self.build()

    def build(self):
        root = toga.Box(style=Pack(direction=COLUMN, margin=14, background_color="#f8fafc"))
        root.add(back_button(self.app))
        root.add(title_label("My Attendance Reports"))

        summary_row = toga.Box(style=Pack(direction=ROW, margin_bottom=14))
        root.add(summary_row)

        monthly = toga.Box(style=Pack(direction=COLUMN))
        root.add(toga.Label("Monthly Breakdown", style=Pack(font_size=16, font_weight="bold", color="#334155", margin_bottom=8)))
        root.add(monthly)

        MONTHS = ["Baisakh","Jestha","Ashad","Shrawan","Bhadra","Ashwin",
                  "Kartik","Mangsir","Poush","Magh","Falgun","Chaitra"]

        async def load():
            try:
                summary = await api_client.get("/attendance/summary")
                for s in summary:
                    col = "#10b981" if s.get("status") == "present" else "#ef4444"
                    b = toga.Box(style=Pack(direction=COLUMN, margin=8, flex=1, background_color="#ffffff"))
                    b.add(toga.Label(str(s.get("count", 0)),
                                      style=Pack(font_size=20, font_weight="bold", color=col, margin_bottom=4)))
                    b.add(toga.Label(s.get("status", "").capitalize(),
                                      style=Pack(font_size=11, color="#64748b")))
                    summary_row.add(b)
            except Exception:
                summary_row.add(toga.Label("Could not load summary.", style=Pack(color="red")))

            try:
                data = await api_client.get("/attendance/student_stats_bs")
                for m in data:
                    total = m.get("total", 0)
                    present = m.get("present", 0) + m.get("late", 0) + m.get("excused", 0)
                    pct = f"{int(present / total * 100)}%" if total else "N/A"
                    mn = m.get("month", 1)
                    month_name = MONTHS[mn - 1] if 1 <= mn <= 12 else "?"
                    row = toga.Box(style=Pack(direction=ROW, margin=6, background_color="#ffffff"))
                    row.add(toga.Label(f"{month_name} {m.get('year','')}",
                                        style=Pack(flex=1, font_size=14, font_weight="bold", color="#1e293b")))
                    row.add(toga.Label(
                        f"P:{m.get('present',0)} A:{m.get('absent',0)} L:{m.get('late',0)}",
                        style=Pack(font_size=11, color="#64748b")))
                    row.add(toga.Label(pct, style=Pack(font_weight="bold", margin_left=8, color="#0f172a")))
                    monthly.add(row)
                    monthly.add(toga.Box(style=Pack(height=2)))
                if not data:
                    monthly.add(toga.Label("No monthly data yet.", style=Pack(color="#64748b")))
            except Exception as e:
                monthly.add(toga.Label(f"Error: {e}", style=Pack(color="red")))

        asyncio.create_task(load())
        return scrollable(root)
