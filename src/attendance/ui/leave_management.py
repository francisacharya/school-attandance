import asyncio
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from attendance.utils.api import api_client
from attendance.utils.nepali_date import ad_to_bs, bs_to_ad, get_today_bs
from attendance.ui.components import back_button, scrollable, title_label, status_label, NepaliDatePicker

class StudentLeaveScreen:
    def __init__(self, app):
        self.app = app
        self.container = self.build()

    def build(self):
        root = toga.Box(style=Pack(direction=COLUMN, margin=14, background_color="#f8fafc"))
        root.add(back_button(self.app))
        root.add(title_label("Leave Requests"))
        
        self.status = status_label()

        start_inp = NepaliDatePicker("Start Date (B.S.)")
        end_inp = NepaliDatePicker("End Date (B.S.)")
        reason_inp = toga.TextInput(placeholder="Reason for leave", style=Pack(margin_bottom=8))
        
        root.add(start_inp.box)
        root.add(end_inp.box)
        root.add(reason_inp)

        async def submit(w):
            try:
                await api_client.post("/student/leaves", {
                    "start_date": bs_to_ad(start_inp.value),
                    "end_date": bs_to_ad(end_inp.value),
                    "reason": reason_inp.value,
                })
                start_inp.value = ""
                end_inp.value = ""
                reason_inp.value = ""
                self.status.text = "✓ Request submitted."
                self.status.style.color = "#10b981"
                await refresh()
            except Exception as e:
                self.status.text = f"Error: {e}"
                self.status.style.color = "#ef4444"

        root.add(toga.Button("Submit Request", on_press=submit,
                              style=Pack(margin=8, margin_bottom=6)))
        root.add(self.status)
        root.add(title_label("My Requests", style=Pack(font_size=16, margin_top=16, margin_bottom=8)))
        
        self.list_box = toga.Box(style=Pack(direction=COLUMN))
        root.add(self.list_box)

        async def refresh():
            for c in list(self.list_box.children):
                self.list_box.remove(c)
            try:
                leaves = await api_client.get("/student/leaves")
                if not leaves:
                    self.list_box.add(toga.Label("No leave requests yet.", style=Pack(color="#64748b")))
                for l in leaves:
                    card = toga.Box(style=Pack(direction=COLUMN, margin=8, background_color="#ffffff"))
                    s_bs = ad_to_bs(l.get('start_date',''))
                    e_bs = ad_to_bs(l.get('end_date',''))
                    card.add(toga.Label(f"{s_bs} → {e_bs}",
                                         style=Pack(font_weight="bold", font_size=14, color="#1e293b")))
                    card.add(toga.Label(l.get("reason", ""), style=Pack(font_size=11, color="#64748b")))
                    st = l.get("status", "pending").upper()
                    col = "#10b981" if st == "APPROVED" else "#f59e0b" if st == "PENDING" else "#ef4444"
                    card.add(toga.Label(st, style=Pack(font_size=11, font_weight="bold", color=col)))
                    self.list_box.add(card)
                    self.list_box.add(toga.Box(style=Pack(height=4)))
            except Exception as e:
                self.list_box.add(toga.Label(f"Error: {e}", style=Pack(color="red")))

        asyncio.create_task(refresh())
        return scrollable(root)


class AdminLeavesScreen:
    def __init__(self, app):
        self.app = app
        self.container = self.build()

    def build(self):
        root = toga.Box(style=Pack(direction=COLUMN, margin=14, background_color="#f8fafc"))
        root.add(back_button(self.app))
        root.add(title_label("Review Leave Requests"))
        status = status_label()
        root.add(status)
        list_box = toga.Box(style=Pack(direction=COLUMN))
        root.add(list_box)

        async def load():
            for c in list(list_box.children):
                list_box.remove(c)
            try:
                leaves = await api_client.get("/admin/leaves")
                pending = [l for l in leaves if l.get("status") == "pending"]
                status.text = f"{len(pending)} pending"
                for l in leaves:
                    card = toga.Box(style=Pack(direction=COLUMN, margin=8, background_color="#ffffff"))
                    card.add(toga.Label(l.get("student_name", ""), style=Pack(font_weight="bold", font_size=14, color="#0f172a")))
                    s_bs = ad_to_bs(l.get('start_date',''))
                    e_bs = ad_to_bs(l.get('end_date',''))
                    card.add(toga.Label(
                        f"{s_bs} → {e_bs}",
                        style=Pack(font_size=11, color="#64748b", margin_bottom=4)))
                    card.add(toga.Label(l.get("reason", ""), style=Pack(font_size=12, color="#334155")))
                    st = l.get("status", "pending").upper()
                    col = "#10b981" if st == "APPROVED" else "#f59e0b" if st == "PENDING" else "#ef4444"
                    card.add(toga.Label(f"Status: {st}",
                                         style=Pack(font_size=11, font_weight="bold", color=col)))
                    if l.get("status") == "pending":
                        btn_row = toga.Box(style=Pack(direction=ROW, margin_top=6))
                        btn_row.add(toga.Button(
                            "Approve",
                            on_press=lambda w, lid=l["id"]: asyncio.create_task(_review(lid, "approved")),
                            style=Pack(flex=1, margin=4, color="#10b981")))
                        btn_row.add(toga.Button(
                            "Reject",
                            on_press=lambda w, lid=l["id"]: asyncio.create_task(_review(lid, "rejected")),
                            style=Pack(flex=1, margin=4, color="#ef4444")))
                        card.add(btn_row)
                    list_box.add(card)
                    list_box.add(toga.Box(style=Pack(height=4)))
                if not leaves:
                    list_box.add(toga.Label("No leave requests.", style=Pack(color="#64748b")))
            except Exception as e:
                list_box.add(toga.Label(f"Error: {e}", style=Pack(color="red")))

        async def _review(lid, st):
            try:
                await api_client.post("/admin/leave/review", {"id": lid, "status": st})
                await load()
            except Exception as e:
                status.text = f"Error: {e}"

        asyncio.create_task(load())
        return scrollable(root)
