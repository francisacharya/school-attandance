import asyncio
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from attendance.utils.api import api_client
from attendance.ui.components import (
    back_button, scrollable, title_label, status_label, 
    m3_card, m3_button, body_label, 
    M3_SURFACE, M3_PRIMARY, M3_ON_SURFACE_VARIANT, M3_SURFACE_VARIANT
)

class TimetableScreen:
    def __init__(self, app):
        self.app = app
        self.container = self.build()

    def build(self):
        root = toga.Box(style=Pack(direction=COLUMN, margin=16, background_color=M3_SURFACE))
        root.add(back_button(self.app))
        root.add(title_label("My Schedule"))

        import datetime
        self.state = {"schedule": [], "day": datetime.date.today().weekday()}

        # Day Tabs
        self.day_row = toga.Box(style=Pack(direction=ROW, margin_bottom=16))
        root.add(self.day_row)
        self.day_btns = []

        for i, d in enumerate(["MON","TUE","WED","THU","FRI","SAT","SUN"]):
            btn = toga.Button(d, on_press=lambda w, idx=i: self._sel_day(idx),
                               style=Pack(flex=1, margin=1, font_size=10, font_weight="bold"))
            self.day_btns.append(btn)
            self.day_row.add(btn)

        self.content = toga.Box(style=Pack(direction=COLUMN, background_color=M3_SURFACE))
        root.add(self.content)

        self.status = status_label()
        root.add(self.status)

        asyncio.create_task(self.load())
        return scrollable(root)

    def render(self):
        for c in list(self.content.children):
            self.content.remove(c)
        
        # Update button colors (Segmented style)
        for i, btn in enumerate(self.day_btns):
            if i == self.state["day"]:
                btn.style.background_color = M3_PRIMARY
                btn.style.color = "white"
            else:
                btn.style.background_color = M3_SURFACE_VARIANT
                btn.style.color = M3_ON_SURFACE_VARIANT

        day_cls = [s for s in self.state["schedule"] if s.get("day_of_week") == self.state["day"]]
        day_name = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"][self.state["day"]]
        
        self.content.add(toga.Label(day_name.upper(), 
                                    style=Pack(font_size=12, font_weight="bold", color=M3_PRIMARY, margin_bottom=12)))

        if not day_cls:
            self.content.add(body_label("No classes scheduled for today.", 
                                        style=Pack(margin=32, text_align="center")))
            return

        for cls in sorted(day_cls, key=lambda x: x.get("start_time", "")):
            card = m3_card(style=Pack(margin=6))
            
            row1 = toga.Box(style=Pack(direction=ROW, align_items="center"))
            row1.add(toga.Label(cls.get("subject_name", ""), 
                                style=Pack(flex=1, font_size=14, font_weight="bold", color=M3_PRIMARY)))
            row1.add(toga.Label(cls.get("period_label",""), 
                                style=Pack(font_size=11, font_weight="bold", color=M3_ON_SURFACE_VARIANT)))
            card.add(row1)

            card.add(body_label(f"{cls.get('start_time','')} — {cls.get('end_time','')}", 
                                 style=Pack(font_size=12, margin_top=4)))
            
            meta_box = toga.Box(style=Pack(direction=ROW, margin_top=10))
            room = cls.get("room_name", "")
            if room:
                meta_box.add(toga.Label(f"📍 {room}", style=Pack(font_size=10, font_weight="bold", margin_right=12, color=M3_ON_SURFACE_VARIANT)))
            
            course = cls.get("course_name", "")
            if course:
                meta_box.add(toga.Label(f"🎓 {course}", style=Pack(font_size=10, color=M3_PRIMARY, font_weight="bold")))
            
            card.add(meta_box)
            self.content.add(card)
            self.content.add(toga.Box(style=Pack(height=4)))

    def _sel_day(self, idx):
        self.state["day"] = idx
        self.render()

    async def load(self):
        self.status.text = "Loading schedule..."
        try:
            role = self.app.session.get("role", "teacher")
            ep = "/teacher/schedule" if role in ("teacher", "admin") else "/student/schedule"
            self.state["schedule"] = await api_client.get(ep)
            self.render()
            self.status.text = f"Updated: {len(self.state['schedule'])} sessions found"
        except Exception as e:
            self.status.text = f"Load error: {e}"

    def _sel_day(self, idx):
        self.state["day"] = idx
        self.render()

    async def load(self):
        self.status.text = "Loading schedule..."
        try:
            role = self.app.session.get("role", "teacher")
            ep = "/teacher/schedule" if role in ("teacher", "admin") else "/student/schedule"
            self.state["schedule"] = await api_client.get(ep)
            self.render()
            self.status.text = f"Found {len(self.state['schedule'])} weekly sessions"
        except Exception as e:
            self.status.text = f"Load error: {e}"
