import asyncio
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from attendance.utils.api import api_client
from attendance.ui.components import (
    back_button, scrollable, title_label, body_label, status_label,
    m3_card, m3_button, M3_SURFACE, M3_PRIMARY, M3_ON_SURFACE,
    M3_ON_SURFACE_VARIANT, M3_SURFACE_VARIANT
)

FULL_DAYS   = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAYS_SHORT  = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ── helpers ─────────────────────────────────────────────────────────────────

def _lbl(text, **kw):
    return toga.Label(text, style=Pack(**kw))

def _row(**kw):
    return toga.Box(style=Pack(direction=ROW, **kw))

def _col(**kw):
    return toga.Box(style=Pack(direction=COLUMN, **kw))

# ── main screen ──────────────────────────────────────────────────────────────

class AdminTimetableScreen:
    def __init__(self, app):
        self.app = app
        self.state = {
            "entries":         [],   # raw data from API
            "lookups": {
                "sessions": [], "courses": [], "semesters": [],
                "subjects": [], "teachers": [], "rooms": [], "periods": []
            },
            "filters":         {"session_id": "", "course_id": "", "semester_id": "", "teacher_id": ""},
            "search_day":      -1,   # -1 = all days; 0-6 = Mon-Sun
            "search_text":     "",   # text search (subject / teacher / room)
            "view_mode":       "list",
            "editing_id":      None,
            "is_archived_view": False
        }
        # widget refs populated in build()
        self.filter_box       = None
        self.add_form_parent  = None
        self.content_box      = None
        self.status_lbl       = None
        self.btn_list         = None
        self.btn_grid         = None
        self.search_input     = None
        self.day_filter_btns  = []   # day filter buttons (8: All + 7 days)
        self.form_widgets     = {}
        self.day_state        = [False] * 7
        self.day_btns         = []

        self.container = self._build()
        asyncio.create_task(self._load_data())

    # ── UI scaffold ──────────────────────────────────────────────────────────

    def _build(self):
        # ── IMPORTANT: create the scroll container and attach the empty root
        # BEFORE adding any children. This matches the DashboardScreen pattern
        # and prevents a Toga Cocoa crash where widget.refresh() is called on
        # a widget not yet attached to a window ('NoneType' has no _impl).
        root = _col(margin=16, background_color=M3_SURFACE)
        sc = toga.ScrollContainer(horizontal=False, style=Pack(flex=1, background_color=M3_SURFACE))
        sc.content = root  # root is EMPTY here — no children to traverse, so no crash

        root.add(back_button(self.app))

        # ── header row ──
        header = _row(align_items="center", margin_bottom=12)
        self.title_lbl = title_label("Master Schedule", style=Pack(flex=1, margin_bottom=0))
        header.add(self.title_lbl)
        
        self.btn_list = m3_button("LIST", on_press=lambda w: self._set_view("list"),
                                  variant="tonal", style=Pack(margin=4))
        self.btn_grid = m3_button("GRID", on_press=lambda w: self._set_view("grid"),
                                  variant="outlined", style=Pack(margin=4))
        self.archived_switch = toga.Switch("Archived", on_change=lambda w: self._toggle_archived(),
                                           style=Pack(margin=6, font_size=10))
        export_btn = m3_button("EXPORT", on_press=lambda w: self._handle_export(),
                                 variant="filled", style=Pack(margin=4, background_color="#10b981"))
        header.add(self.btn_list)
        header.add(self.btn_grid)
        header.add(self.archived_switch)
        header.add(export_btn)
        root.add(header)

        # ── lookup filters ──
        self.filter_box = _row(margin_bottom=8)
        root.add(self.filter_box)

        # ── search bar ──
        search_row = _row(align_items="center", margin_bottom=12)
        self.search_input = toga.TextInput(placeholder="Subject / Teacher / Room",
                                           style=Pack(flex=1, margin_right=8, background_color=M3_SURFACE_VARIANT))
        search_row.add(self.search_input)
        search_btn  = m3_button("SEARCH", on_press=lambda w: self._apply_search(),
                                   variant="filled")
        reset_btn   = m3_button("RESET",  on_press=lambda w: self._reset_search(),
                                   variant="text")
        search_row.add(search_btn)
        search_row.add(reset_btn)
        root.add(search_row)

        # ── day filter buttons ─────────────────────────────────────────────────
        # NOTE: We use a plain Box here instead of a nested ScrollContainer.
        # Setting .content on a ScrollContainer before it is added to a window
        # triggers a premature layout refresh (Toga Cocoa bug) causing an
        # AttributeError: 'NoneType' object has no attribute '_impl'.
        day_box = _row(background_color=M3_SURFACE, margin_bottom=12)
        
        self.day_filter_btns = []
        for i, d in enumerate(["ALL"] + DAYS_SHORT):
            btn = toga.Button(d, on_press=lambda w, idx=i-1: self._filter_day(idx),
                              style=Pack(width=42, margin=2, font_size=10, font_weight="bold"))
            self.day_filter_btns.append(btn)
            day_box.add(btn)
        root.add(day_box)

        # ── add / edit form ──
        self.add_form_parent = _col(margin_bottom=16)
        root.add(self.add_form_parent)

        # ── entry list / grid ──
        self.content_box = _col(background_color=M3_SURFACE)
        root.add(self.content_box)
        root.add(toga.Box(style=Pack(height=20)))
        
        self.status_lbl = status_label()
        root.add(self.status_lbl)

        # ── floating FAB style add button ──
        add_btn = m3_button("+ ADD NEW ENTRY", on_press=lambda w: self._show_add_form(),
                            variant="filled", style=Pack(margin=10, height=48))
        root.add(add_btn)

        return sc

    # ── data loading ─────────────────────────────────────────────────────────

    async def _load_data(self):
        self.status_lbl.text = "Loading schedule..."
        try:
            s, c, sem, sub, u, r, p = await asyncio.gather(
                api_client.get("/academic/sessions"),
                api_client.get("/academic/courses"),
                api_client.get("/academic/semesters"),
                api_client.get("/academic/subjects"),
                api_client.get("/admin/users/all"),
                api_client.get("/academic/rooms"),
                api_client.get("/academic/periods")
            )
            self.state["lookups"] = {
                "sessions": s, "courses": c, "semesters": sem, "subjects": sub,
                "teachers": [x for x in u if x.get("role") == "teacher"],
                "rooms": r, "periods": p
            }
            await self._refresh_list()
            self._render_filters()
            self._render_add_form()
            self.status_lbl.text = "Ready"
        except Exception as e:
            self.status_lbl.text = f"Load error: {e}"

    async def _refresh_list(self):
        try:
            params = {**self.state["filters"],
                      "is_archived": "1" if self.state["is_archived_view"] else "0"}
            query = "&".join(f"{k}={v}" for k, v in params.items() if v)
            self.state["entries"] = await api_client.get(f"/admin/timetable/all?{query}")
            self._render_content()
        except Exception as e:
            print(f"Refresh error: {e}")

    # ── search / day filter ───────────────────────────────────────────────────

    def _apply_search(self):
        self.state["search_text"] = (self.search_input.value or "").strip().lower()
        self._render_content()

    def _reset_search(self):
        self.search_input.value = ""
        self.state["search_text"] = ""
        self.state["search_day"] = -1
        self._render_content()

    def _filter_day(self, day_idx):
        self.state["search_day"] = day_idx
        self._render_content()

    def _filtered_entries(self):
        entries = self.state["entries"]
        # day filter
        if self.state["search_day"] >= 0:
            entries = [e for e in entries if e.get("day_of_week") == self.state["search_day"]]
        # text search
        q = self.state["search_text"]
        if q:
            entries = [e for e in entries if
                       q in (e.get("subject") or "").lower() or
                       q in (e.get("teacher") or "").lower() or
                       q in (e.get("room") or "").lower() or
                       q in FULL_DAYS[e["day_of_week"]].lower()]
        return entries

    # ── view toggle ───────────────────────────────────────────────────────────

    def _set_view(self, mode):
        self.state["view_mode"] = mode
        self._render_content()

    def _toggle_archived(self):
        self.state["is_archived_view"] = self.archived_switch.value
        self.title_lbl.text = "Master Schedule (Archived)" if self.archived_switch.value else "Master Schedule"
        asyncio.create_task(self._refresh_list())

    # ── lookup filters ────────────────────────────────────────────────────────

    def _render_filters(self):
        for c in list(self.filter_box.children):
            self.filter_box.remove(c)
        l = self.state["lookups"]

        def _on_change(w):
            def _get_id(items, val, key="name"):
                for x in items:
                    if x.get(key) == val: return x["id"]
                return ""

            self.state["filters"] = {
                "session_id":  _get_id(l["sessions"], s_sel.value, "label"),
                "course_id":   _get_id(l["courses"],  c_sel.value),
                "semester_id": _get_id(l["semesters"],sem_sel.value),
                "teacher_id":  _get_id(l["teachers"], t_sel.value, "full_name"),
            }
            asyncio.create_task(self._refresh_list())

        s_sel   = toga.Selection(items=["Session"]  + [x["label"]     for x in l["sessions"]],  on_change=_on_change, style=Pack(width=100, margin_right=4))
        c_sel   = toga.Selection(items=["Course"]   + [x["name"]      for x in l["courses"]],   on_change=_on_change, style=Pack(width=110, margin_right=4))
        sem_sel = toga.Selection(items=["Semester"] + [x["name"]      for x in l["semesters"]], on_change=_on_change, style=Pack(width=100, margin_right=4))
        t_sel   = toga.Selection(items=["Teacher"]  + [x["full_name"] for x in l["teachers"]],  on_change=_on_change, style=Pack(width=120, margin_right=4))
        rst     = toga.Button("Reset Filters", on_press=lambda w: self._reset_filters(), style=Pack())

        for w in (s_sel, c_sel, sem_sel, t_sel, rst):
            self.filter_box.add(w)

    def _reset_filters(self):
        self.state["filters"] = {"session_id": "", "course_id": "", "semester_id": "", "teacher_id": ""}
        self._render_filters()
        asyncio.create_task(self._refresh_list())

    # ── add / edit form ───────────────────────────────────────────────────────

    def _show_add_form(self):
        self.state["editing_id"] = None
        self._render_add_form()

    def _show_edit_form(self, ent):
        self.state["editing_id"] = ent["id"]
        self._render_add_form()
        # Logic to populate form fields...

    def _render_add_form(self):
        for c in list(self.add_form_parent.children):
            self.add_form_parent.remove(c)

        is_edit  = bool(self.state["editing_id"])
        card     = m3_card(style=Pack(margin=8))
        card.add(_lbl("Edit Timetable Slot" if is_edit else "Add New Timetable Slots",
                       font_weight="bold", color=M3_PRIMARY, margin_bottom=8))

        l = self.state["lookups"]

        def _sel(label, items, display_key="name"):
            box = _col(margin=4, flex=1)
            box.add(_lbl(label, font_size=10, color=M3_ON_SURFACE_VARIANT))
            sel = toga.Selection(items=["- Select -"] + [x[display_key] for x in items],
                                  style=Pack(flex=1))
            box.add(sel)
            return box, sel

        self.form_widgets = {}
        row1 = _row()
        s_b, s_s    = _sel("Session",  l["sessions"],  "label")
        c_b, c_s    = _sel("Course",   l["courses"])
        sem_b, sem_s = _sel("Semester", l["semesters"])
        sub_b, sub_s = _sel("Subject",  l["subjects"])
        self.form_widgets.update({"session": s_s, "course": c_s, "semester": sem_s, "subject": sub_s})
        for w in (s_b, c_b, sem_b, sub_b): row1.add(w)
        card.add(row1)

        row2 = _row()
        tea_b, tea_s = _sel("Teacher", l["teachers"], "full_name")
        rom_b, rom_s = _sel("Room",    l["rooms"])
        per_b, per_s = _sel("Period",  l["periods"],  "label")
        self.form_widgets.update({"teacher": tea_s, "room": rom_s, "period": per_s})
        for w in (tea_b, rom_b, per_b): row2.add(w)
        card.add(row2)

        # Day selector
        self.day_state = [False] * 7
        self.day_btns  = []
        day_box = _row(background_color=M3_SURFACE)
        
        def _toggle_day(w, idx):
            self.day_state[idx] = not self.day_state[idx]
            if self.day_state[idx]:
                w.style.background_color = M3_PRIMARY
                w.style.color = "white"
            else:
                del w.style.background_color
                del w.style.color

        for i, d in enumerate(DAYS_SHORT):
            btn = toga.Button(d, on_press=lambda w, i=i: _toggle_day(w, i),
                               style=Pack(width=42, margin=2))
            self.day_btns.append(btn)
            day_box.add(btn)
        card.add(day_box)

        # Save
        async def _do_save(w):
            try:
                def _get_id(items, val, key="name"):
                    res = [x["id"] for x in items if x[key] == val]
                    return res[0] if res else None

                v_s   = _get_id(l["sessions"],  s_s.value,   "label")
                v_c   = _get_id(l["courses"],   c_s.value)
                v_sem = _get_id(l["semesters"], sem_s.value)
                v_sub = _get_id(l["subjects"],  sub_s.value)
                v_tea = _get_id(l["teachers"],  tea_s.value, "full_name")
                v_per = _get_id(l["periods"],   per_s.value, "label")
                v_rom = _get_id(l["rooms"],     rom_s.value)
                v_days = [i for i, v in enumerate(self.day_state) if v]

                if not all([v_s, v_c, v_sem, v_sub, v_tea, v_per, v_days]):
                    self.status_lbl.text = "Error: Fill all required fields"
                    return

                self.status_lbl.text = "Saving..."
                if self.state["editing_id"]:
                    await api_client.put(f"/admin/timetable/{self.state['editing_id']}", {
                        "session_id": v_s, "course_id": v_c, "semester_id": v_sem,
                        "subject_id": v_sub, "teacher_user_id": v_tea, "room_id": v_rom,
                        "period_id": v_per, "day_of_week": v_days[0]
                    })
                    self.state["editing_id"] = None
                else:
                    await api_client.post("/admin/timetable", {
                        "session_id": v_s, "course_id": v_c, "semester_id": v_sem,
                        "subject_id": v_sub, "teacher_user_id": v_tea, "room_id": v_rom,
                        "period_id": v_per, "days": v_days
                    })

                await self._refresh_list()
                self._render_add_form()
                self.status_lbl.text = "Success: Timetable saved"
            except Exception as e:
                self.status_lbl.text = f"Save error: {e}"

        card.add(m3_button("Save" if not is_edit else "Update",
                              on_press=_do_save,
                              variant="filled", style=Pack(margin=10)))
        self.add_form_parent.add(card)

    # ── content rendering ─────────────────────────────────────────────────────

    def _render_content(self):
        for c in list(self.content_box.children):
            self.content_box.remove(c)
        if self.state["view_mode"] == "list":
            self._render_list()
        else:
            self._render_grid()

    # ── list view ─────────────────────────────────────────────────────────────

    def _render_list(self):
        entries = self._filtered_entries()
        if not entries:
            self.content_box.add(body_label("No timetable entries found.", 
                                           style=Pack(margin=32, text_align="center")))
            return

        for ent in entries:
            card = m3_card(style=Pack(margin=6))
            
            top = _row(align_items="center")
            top.add(toga.Label(ent.get("subject", "???"),
                               style=Pack(flex=1, font_size=15, font_weight="bold", color=M3_PRIMARY)))
            top.add(toga.Label(ent.get("period",""),
                               style=Pack(font_size=11, font_weight="bold", color=M3_ON_SURFACE_VARIANT)))
            card.add(top)
            
            card.add(body_label(f"{FULL_DAYS[ent['day_of_week']]} | {ent.get('time','')}",
                                 style=Pack(margin_top=2)))
            
            meta = _row(margin_top=8)
            meta.add(toga.Label(f"📍 {ent.get('room','')}", style=Pack(font_size=10, margin_right=12, color=M3_ON_SURFACE_VARIANT)))
            meta.add(toga.Label(f"👤 {ent.get('teacher','')}", style=Pack(font_size=10, margin_right=12, color=M3_ON_SURFACE_VARIANT)))
            meta.add(toga.Label(f"🎓 {ent.get('course','')}", style=Pack(font_size=10, color=M3_PRIMARY, font_weight="bold")))
            card.add(meta)
            
            # Actions
            act = _row(margin_top=10)
            if not self.state["is_archived_view"]:
                act.add(m3_button("EDIT", on_press=lambda w, _e=ent: self._handle_edit_start(_e), variant="text", style=Pack(font_size=10)))
                act.add(m3_button("ARCHIVE", on_press=lambda w, _e=ent: asyncio.create_task(self._handle_archive(_e["id"])), variant="text", style=Pack(font_size=10)))
                act.add(m3_button("DELETE", on_press=lambda w, _e=ent: asyncio.create_task(self._handle_delete(_e["id"])), variant="text", style=Pack(font_size=10, color="#ef4444")))
            else:
                act.add(m3_button("RESTORE", on_press=lambda w, _e=ent: asyncio.create_task(self._handle_unarchive(_e["id"])), variant="text", style=Pack(font_size=10)))
                act.add(m3_button("DELETE", on_press=lambda w, _e=ent: asyncio.create_task(self._handle_delete(_e["id"])), variant="text", style=Pack(font_size=10, color="#ef4444")))
            card.add(act)
            
            self.content_box.add(card)
            self.content_box.add(toga.Box(style=Pack(height=4)))

    # ── grid view ─────────────────────────────────────────────────────────────

    def _render_grid(self):
        periods = sorted(self.state["lookups"]["periods"], key=lambda x: x.get("sort_order", 0))
        entries = self._filtered_entries()

        # Compute minimum height: header (40px) + each period row (52px) + padding
        ROW_H = 52
        min_h = 40 + ROW_H * max(len(periods), 1) + 20

        # Full bi-directional scroll; height grows with content
        grid_scroll = toga.ScrollContainer(
            horizontal=True, vertical=True,
            style=Pack(height=min_h, background_color=M3_SURFACE)
        )
        grid_box = _col(background_color=M3_SURFACE)
        grid_scroll.content = grid_box
        self.content_box.add(grid_scroll)

        # Filter to only relevant days when day filter active
        day_range = range(7) if self.state["search_day"] < 0 else [self.state["search_day"]]
        visible_days = list(day_range)

        # Header Row
        hdr = _row(background_color=M3_PRIMARY, height=40, align_items="center")
        hdr.add(toga.Box(style=Pack(width=80))) # period spacer
        for d in visible_days:
            hdr.add(toga.Label(DAYS_SHORT[d], style=Pack(width=110, color="white", text_align="center", font_weight="bold", font_size=10)))
        grid_box.add(hdr)

        for p in periods:
            p_row = _row(margin_top=1)
            # Period info col
            p_info = _col(width=80, margin=4, background_color=M3_SURFACE_VARIANT)
            p_info.add(toga.Label(p["label"], style=Pack(font_weight="bold", font_size=10, color=M3_ON_SURFACE)))
            p_info.add(toga.Label(p["start_time"], style=Pack(font_size=8, color=M3_ON_SURFACE_VARIANT)))
            p_row.add(p_info)

            for d_idx in visible_days:
                cell = _col(width=110, margin=2, background_color=M3_SURFACE)
                
                # Compute entries for this specific (period, day) cell
                cell_entries = [
                    e for e in entries
                    if e.get("period_id") == p.get("id") and e.get("day_of_week") == d_idx
                ]
                
                if cell_entries:
                    for ent in cell_entries:
                        inner = _col(margin=4, background_color=M3_SURFACE_VARIANT)
                        inner.add(toga.Label(ent.get("subject_name", ent.get("subject", "")),
                                             style=Pack(font_weight="bold", font_size=9, color=M3_PRIMARY)))
                        inner.add(toga.Label(ent.get("teacher_name", ent.get("teacher", "")),
                                             style=Pack(font_size=8, color=M3_ON_SURFACE_VARIANT)))
                        inner.add(toga.Label(ent.get("room_name", ent.get("room", "")),
                                             style=Pack(font_size=8, font_weight="bold")))
                        cell.add(inner)
                        cell.add(toga.Box(style=Pack(height=2)))
                else:
                    cell.add(toga.Box(style=Pack(height=40)))  # empty cell
                
                p_row.add(cell)
            grid_box.add(p_row)
            grid_box.add(toga.Box(style=Pack(height=1, background_color=M3_SURFACE_VARIANT)))

    # ── CRUD handlers ─────────────────────────────────────────────────────────

    def _handle_edit_start(self, ent):
        self.state["editing_id"] = ent["id"]
        self._render_add_form()
        fw = self.form_widgets
        try:
            fw["session"].value  = ent.get("session", "- Select -")
            fw["course"].value   = ent.get("course",  "- Select -")
            fw["semester"].value = ent.get("semester","- Select -")
            fw["subject"].value  = ent.get("subject", "- Select -")
            fw["teacher"].value  = ent.get("teacher", "- Select -")
            fw["room"].value     = ent.get("room") or "- Select -"
            fw["period"].value   = ent.get("period",  "- Select -")
        except Exception: pass

        # Activate the correct day button
        dow = ent.get("day_of_week", 0)
        for i in range(7):
            self.day_state[i] = (i == dow)
            if self.day_state[i]:
                self.day_btns[i].style.background_color = M3_PRIMARY
                self.day_btns[i].style.color = "white"
            else:
                del self.day_btns[i].style.background_color
                del self.day_btns[i].style.color

        self.status_lbl.text = f"Editing Slot ID: {ent['id']}"

    async def _handle_delete(self, id):
        confirmed = await self.app.main_window.dialog(
            toga.QuestionDialog("Confirm Delete", "Delete this timetable slot permanently?"))
        if confirmed:
            try:
                await api_client.delete(f"/admin/timetable/{id}")
                await self._refresh_list()
                self.status_lbl.text = "Success: Entry deleted"
            except Exception as e:
                self.status_lbl.text = f"Delete error: {e}"

    async def _handle_archive(self, id):
        try:
            await api_client.put(f"/admin/timetable/{id}/archive", {})
            await self._refresh_list()
            self.status_lbl.text = "Success: Entry archived"
        except Exception as e:
            self.status_lbl.text = f"Archive error: {e}"

    async def _handle_unarchive(self, id):
        try:
            await api_client.put(f"/admin/timetable/{id}/unarchive", {})
            await self._refresh_list()
            self.status_lbl.text = "Success: Entry restored"
        except Exception as e:
            self.status_lbl.text = f"Unarchive error: {e}"

    def _handle_export(self):
        import tempfile
        import webbrowser
        import os
        from datetime import datetime

        entries = self._filtered_entries()
        if not entries:
            self.status_lbl.text = "Error: No entries to export"
            return
            
        l = self.state["lookups"]
        is_grid = self.state["view_mode"] == "grid"
        
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Master Schedule - {"Grid" if is_grid else "List"}</title>
<style>
    @page {{ size: landscape; margin: 12mm; }}
    body {{ font-family: sans-serif; color: #1e293b; margin: 0; padding: 20px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
    th, td {{ border: 1px solid #e2e8f0; padding: 8px; text-align: left; font-size: 12px; }}
    th {{ background: #6750A4; color: white; }}
    .slot {{ background: #f3edf7; font-weight: 600; }}
    .entry {{ background: #eaddff; border: 1px solid #d0bcff; border-radius: 4px; padding: 6px; margin-bottom: 4px; }}
    .subject {{ color: #21005d; font-weight: 700; margin-bottom: 2px; }}
    .meta {{ color: #49454f; font-size: 10px; }}
</style></head>
<body>
    <h2>Master Schedule</h2>
    <div style="font-size:12px;color:#64748b;">Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
    <table>
"""

        if is_grid:
            periods = sorted(l["periods"], key=lambda x: x.get("sort_order", 0))
            html += "<thead><tr><th>Period / Time</th>"
            for d in DAYS_SHORT: html += f"<th>{d}</th>"
            html += "</tr></thead><tbody>"

            for p in periods:
                html += f"<tr><td class='slot'><b>{p['label']}</b><br><small>{p['start_time']}</small></td>"
                for i in range(7):
                    day_entries = [e for e in entries if e.get("day_of_week") == i and e.get("period") == p["label"]]
                    cell_html = ""
                    for ent in day_entries:
                        cell_html += f"""<div class="entry">
                            <div class="subject">{ent.get('subject')}</div>
                            <div class="meta">{ent.get('teacher')} | {ent.get('room') or ''}</div>
                        </div>"""
                    html += f"<td>{cell_html or '&nbsp;'}</td>"
                html += "</tr>"
        else:
            html += "<thead><tr><th>Day</th><th>Time</th><th>Subject</th><th>Teacher</th><th>Course</th><th>Room</th></tr></thead><tbody>"
            for ent in entries:
                html += f"<tr><td>{FULL_DAYS[ent['day_of_week']]}</td><td>{ent.get('time')}</td><td>{ent.get('subject')}</td><td>{ent.get('teacher')}</td><td>{ent.get('course')}</td><td>{ent.get('room')}</td></tr>"

        html += "</tbody></table></body></html>"

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
                f.write(html.encode("utf-8"))
                tmp_path = f.name
            webbrowser.open("file://" + os.path.abspath(tmp_path))
            self.status_lbl.text = "Success: Exported to HTML"
        except Exception as e:
            self.status_lbl.text = f"Export error: {e}"
