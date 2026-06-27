import asyncio
import toga
from toga.sources import ListSource
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

import warnings
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", message="unclosed transport")
warnings.filterwarnings("ignore", message="unclosed <socket.socket")

from attendance.utils.api import api_client
import datetime
from attendance.utils.nepali_date import ad_to_bs, bs_to_ad, get_today_bs, NEPALI_MONTHS
from attendance.ui.components import (
    back_button, scrollable, title_label, status_label, stat_card, 
    NepaliDatePicker, m3_card, m3_button, body_label, 
    M3_SURFACE, M3_PRIMARY, M3_ON_SURFACE_VARIANT, M3_SURFACE_VARIANT
)

DAYS_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

class TeacherAttendanceScreen:
    def __init__(self, app, prefill=None):
        self.app = app
        self.prefill = prefill
        # State MUST be initialized before build()
        self.state = {
            "classes": [], 
            "roster": [], 
            "marks": {}, 
            "all_students": [],
            "selected": None, 
            "tab": "attendance", 
            "qr_visible": False,
            "enroll_student_id": None,
        }
        self.container = self.build()

    def build(self):
        root = toga.Box(style=Pack(direction=COLUMN, margin=16, background_color=M3_SURFACE))
        root.add(back_button(self.app))
        root.add(title_label("Day / Period Attendance"))

        # Class selector
        root.add(body_label("SELECT CLASS", style=Pack(font_weight="bold", font_size=11, margin_bottom=4)))
        self.cls_sel = toga.Selection(on_change=self.on_class_change, 
                                      style=Pack(margin_bottom=12, background_color=M3_SURFACE_VARIANT))
        root.add(self.cls_sel)

        # --- Header Row (Date + QR Button) ---
        self.header_row = toga.Box(style=Pack(direction=ROW, align_items="center", margin_bottom=4))
        # Left: Date
        self.date_inp = NepaliDatePicker("Date (BS: YYYY-MM-DD)")
        self.date_inp.box.style.update(flex=1)
        self.header_row.add(self.date_inp.box)
        
        # Right: QR Button (only visible in Attendance tab)
        self.qr_btn = m3_button("QR CODE", on_press=lambda w: asyncio.create_task(self.generate_qr()),
                               variant="tonal", style=Pack(margin_left=8, display="none"))
        self.header_row.add(self.qr_btn)
        root.add(self.header_row)

        # Tabs
        tab_row = toga.Box(style=Pack(direction=ROW, margin_bottom=8))
        self.tab_attn = m3_button("ATTENDANCE", on_press=lambda w: self.set_tab("attendance"), 
                             variant="tonal" if self.state["tab"] == "attendance" else "outlined", 
                             style=Pack(flex=1, margin=2))
        self.tab_roster = m3_button("ROSTER", on_press=lambda w: self.set_tab("roster"), 
                               variant="tonal" if self.state["tab"] == "roster" else "outlined", 
                               style=Pack(flex=1, margin=2))
        tab_row.add(self.tab_attn)
        tab_row.add(self.tab_roster)
        root.add(tab_row)

        # 1. Enrollment UI (persistent but hidden by default)
        self.enroll_box = m3_card(style=Pack(display="none", margin=8))
        self.enroll_box.add(body_label("ENROLL NEW STUDENT", style=Pack(font_weight="bold", margin_bottom=6)))
        
        self.enroll_row = toga.Box(style=Pack(direction=ROW, align_items="center"))
        # Using a formal ListSource for robust data binding
        self.enroll_source = ListSource(accessors=['label', 'student_id'])
        self.enroll_sel = toga.Selection(
            items=self.enroll_source,
            accessor='label',
            style=Pack(flex=1, margin_right=6, background_color=M3_SURFACE_VARIANT)
        )
        self.enroll_row.add(self.enroll_sel)
        self.enroll_row.add(m3_button("ADD", on_press=lambda w: asyncio.create_task(self.enroll_student()), variant="filled"))
        self.enroll_box.add(self.enroll_row)
        root.add(self.enroll_box)

        # 2. QR IMAGE section (hidden by default)
        self.qr_img_box = toga.Box(style=Pack(direction=COLUMN, align_items="center", display="none", margin=4))
        self.qr_img = toga.ImageView(style=Pack(width=160, height=160, margin_bottom=8))
        self.qr_img_box.add(self.qr_img)
        root.add(self.qr_img_box)

        # 3. Student list
        self.list_box = toga.Box(style=Pack(direction=COLUMN, background_color=M3_SURFACE))
        root.add(self.list_box)

        self.save_btn = m3_button("SAVE ATTENDANCE", on_press=lambda w: asyncio.create_task(self.do_save()),
                                  variant="filled", style=Pack(margin=10, margin_top=16))
        root.add(self.save_btn)
        self.status = status_label()
        root.add(self.status)

        asyncio.create_task(self.load_classes())
        return scrollable(root)

    async def load_classes(self):
        self.status.text = "Loading classes..."
        try:
            sched, studs = await asyncio.gather(
                api_client.get("/teacher/schedule"),
                api_client.get("/students")
            )
            
            # Distinct classes based on subject + period
            seen = {}
            for s in sched:
                k = f"{s['subject_id']}__{s['period_id']}"
                if k not in seen:
                    seen[k] = {**s, "days": [], "id": k}
                seen[k]["days"].append(s.get("day_of_week", 0))
            
            self.state["classes"] = list(seen.values())
            self.state["all_students"] = studs
            
            # Update selectors
            cls_items = [
                f"{c['subject_name']} — {c['period_label']} [{'/'.join(DAYS_SHORT[d] for d in c.get('days',[]) if d<7)}]"
                for c in self.state["classes"]
            ]
            self.cls_sel.items = cls_items
            
            self.enroll_source.clear()
            self.enroll_source.append({'label': "- Select Student -", 'student_id': None})
            for s in self.state["all_students"]:
                lbl = f"{s['full_name']} ({s.get('student_code','')})"
                self.enroll_source.append({'label': lbl, 'student_id': s['id']})
            self.enroll_sel.value = self.enroll_source[0]
            
            # Pre-select if navigated from dashboard
            if self.prefill:
                for i, c in enumerate(self.state["classes"]):
                    if c["subject_id"] == self.prefill.get("subject_id") and c["period_id"] == self.prefill.get("period_id"):
                        self.cls_sel.value = cls_items[i]
                        self.state["selected"] = c
                        await self.load_roster(c["subject_id"])
                        break
            elif cls_items:
                self.cls_sel.value = cls_items[0]
                self.state["selected"] = self.state["classes"][0]
                await self.load_roster(self.state["selected"]["subject_id"])
            
            self.status.text = "Ready"
        except Exception as e:
            self.status.text = f"Error: {e}"

    async def load_roster(self, subject_id):
        try:
            self.state["roster"] = await api_client.get(f"/teacher/roster/{subject_id}")
            self.state["marks"] = {str(s["id"]): "present" for s in self.state["roster"]}
            self.render_list()
        except Exception as e:
            self.status.text = f"Roster error: {e}"

    def render_list(self):
        for c in list(self.list_box.children):
            self.list_box.remove(c)
        
        # Toggle UI sections based on tab
        if self.state["tab"] == "roster":
            self.enroll_box.style.display = "pack"
            self.qr_btn.style.display = "none"
            self.qr_img_box.style.display = "none"
        else:
            self.enroll_box.style.display = "none"
            self.qr_btn.style.display = "pack"

        if not self.state["roster"]:
            self.list_box.add(body_label("No students enrolled in this class.", 
                                         style=Pack(margin=24, text_align="center")))
            return

        for s in self.state["roster"]:
            sid = str(s["id"])
            if self.state["tab"] == "attendance":
                card = m3_card(style=Pack(margin=6))
                
                # Header row with Name and Remove button
                header = toga.Box(style=Pack(direction=ROW, align_items="center"))
                info = toga.Box(style=Pack(direction=COLUMN, flex=1))
                info.add(toga.Label(s['full_name'], style=Pack(font_weight="bold", font_size=14, color=M3_PRIMARY)))
                info.add(toga.Label(s.get('student_code',''), style=Pack(font_size=11, color=M3_ON_SURFACE_VARIANT)))
                header.add(info)
                
                # Inline Remove button for quick roster management
                header.add(m3_button("REMOVE", on_press=lambda w, _s=s["id"]: asyncio.create_task(self.remove_student(_s)),
                                    variant="text", style=Pack(color="#ef4444", font_size=10)))
                card.add(header)

                btns = toga.Box(style=Pack(direction=ROW, margin_top=4))
                for lbl, val, col in [("P","present","#10b981"),("A","absent","#ef4444"),("L","late","#f59e0b"),("E","excused","#8b5cf6")]:
                    active = self.state["marks"].get(sid) == val
                    b = toga.Button(lbl, on_press=lambda w, _s=sid, _v=val: self.mark(_s, _v),
                                    style=Pack(width=36, margin=2, font_size=11, font_weight="bold",
                                               background_color=col if active else M3_SURFACE_VARIANT,
                                               color="white" if active else M3_ON_SURFACE_VARIANT))
                    btns.add(b)
                card.add(btns)
                self.list_box.add(card)
            else:
                card = m3_card(style=Pack(margin=6))
                row = toga.Box(style=Pack(direction=ROW, align_items="center"))
                row.add(toga.Label(f"{s['full_name']} ({s.get('student_code','')})", 
                                    style=Pack(flex=1, font_weight="bold", font_size=13)))
                row.add(m3_button("REMOVE", on_press=lambda w, _s=s["id"]: asyncio.create_task(self.remove_student(_s)),
                                   variant="text", style=Pack(color="#ef4444", font_size=11)))
                card.add(row)
                self.list_box.add(card)

    def mark(self, sid, val):
        self.state["marks"][sid] = val
        self.render_list()

    async def remove_student(self, sid):
        cls = self.state["selected"]
        if not cls: return
        try:
            await api_client.delete(f"/teacher/roster/{cls['subject_id']}/{sid}")
            await self.load_roster(cls["subject_id"])
            self.status.text = "Student removed from roster"
        except Exception as e:
            self.status.text = f"Error: {e}"

    async def enroll_student(self):
        cls = self.state["selected"]
        sel_item = self.enroll_sel.value
        
        if not cls or not sel_item:
            self.status.text = "Error: Please select a student from the list"
            return
        
        try:
            idx = -1
            for i, itm in enumerate(self.enroll_source):
                if itm == sel_item:
                    idx = i
                    break
            
            if idx <= 0:
                self.status.text = "Error: Please select a student"
                return

            stud = self.state["all_students"][idx - 1]
            eid = stud["id"]
            name = stud["full_name"]
            
            self.status.text = f"Enrolling {name}..."
            await api_client.post(f"/teacher/roster/{cls['subject_id']}/{eid}", {})
            
            if self.enroll_source:
                self.enroll_sel.value = self.enroll_source[0]
            
            await self.load_roster(cls["subject_id"])
            self.status.text = f"✓ Enrolled {name} successfully."
            self.status.style.color = "#10b981"
        except Exception as e:
            self.status.text = f"Enroll error: {e}"
            self.status.style.color = "#ef4444"

    def on_class_change(self, widget):
        if not widget.value: return
        try:
            val = str(widget.value)
            idx = -1
            for i, c in enumerate(self.state["classes"]):
                lbl = f"{c['subject_name']} — {c['period_label']}"
                if lbl in val:
                    idx = i
                    break
            
            if idx >= 0 and idx < len(self.state["classes"]):
                self.state["selected"] = self.state["classes"][idx]
                asyncio.create_task(self.load_roster(self.state["selected"]["subject_id"]))
        except Exception as e:
            self.status.text = f"Selection error: {e}"

    def set_tab(self, tab):
        self.state["tab"] = tab
        self.state["enroll_student_id"] = None
        if self.enroll_source:
             self.enroll_sel.value = self.enroll_source[0]
        self.render_list()

    async def generate_qr(self):
        cls = self.state["selected"]
        if not cls:
            self.status.text = "Select a class first."
            return
        try:
            date_val = self.date_inp.value
            res = await api_client.post("/teacher/generate_qr", {
                "subject_id": cls["subject_id"],
                "period_id": cls["period_id"],
                "date": date_val
            })
            token = res.get("token", "")
            from attendance.utils.qr_handler import generate_qr_image
            self.qr_img.image = generate_qr_image(token)
            self.qr_img_box.style.display = "pack"
            self.status.text = f"✓ QR for {date_val} generated."
            self.status.style.color = "#10b981"
        except Exception as e:
            self.status.text = f"QR error: {e}"

    async def do_save(self):
        cls = self.state["selected"]
        if not cls or not self.state["roster"]:
            self.status.text = "Select a class first."
            return
        
        self.save_btn.enabled = False
        self.status.text = "Saving attendance..."
        try:
            records = []
            for sid, st in self.state["marks"].items():
                records.append({
                    "student_id": int(sid),
                    "subject_id": cls["subject_id"],
                    "period_id": cls["period_id"],
                    "date": bs_to_ad(self.date_inp.value),
                    "status": st
                })
            
            await api_client.post("/attendance/bulk-mark", {"records": records})
            self.status.text = f"✓ Success: {len(records)} records saved."
            self.status.style.color = "#10b981"
        except Exception as e:
            self.status.text = f"Save error: {e}"
            self.status.style.color = "#ef4444"
        finally:
            self.save_btn.enabled = True


class BulkAttendanceScreen:
    def __init__(self, app):
        self.app = app
        self.container = self.build()

    def build(self):
        root = toga.Box(style=Pack(direction=COLUMN, margin=16, background_color=M3_SURFACE))
        root.add(back_button(self.app))
        root.add(title_label("Bulk Attendance Grid"))

        # ── selectors ──
        sel_row = toga.Box(style=Pack(direction=ROW, margin_bottom=12))
        self.cls_sel = toga.Selection(on_change=lambda w: asyncio.create_task(self.fetch_grid()), 
                                      style=Pack(flex=1, margin_right=6, background_color=M3_SURFACE_VARIANT))
        self.month_sel = toga.Selection(items=[f"{m} 2081" for m in NEPALI_MONTHS],
                                        on_change=lambda w: asyncio.create_task(self.fetch_grid()),
                                        style=Pack(width=130, background_color=M3_SURFACE_VARIANT))
        sel_row.add(self.cls_sel)
        sel_row.add(self.month_sel)
        root.add(sel_row)

        # ── the grid ──
        self.grid_container = toga.ScrollContainer(horizontal=True, vertical=True, 
                                                   style=Pack(flex=1, background_color=M3_SURFACE))
        self.grid_box = toga.Box(style=Pack(direction=COLUMN, background_color=M3_SURFACE))
        self.grid_container.content = self.grid_box
        root.add(self.grid_container)

        self.status = status_label()
        root.add(self.status)

        self.save_btn = m3_button("SAVE MONTH CHANGES", on_press=lambda w: asyncio.create_task(self.save_bulk()),
                                  variant="filled", style=Pack(margin=10))
        root.add(self.save_btn)

        self.state = {
            "classes": [], "roster": [], "attendance": {}, "pending": {},
            "selected_class": None, "days": []
        }

        asyncio.create_task(self.load_initial())
        return root

    async def load_initial(self):
        try:
            sched = await api_client.get("/teacher/schedule")
            seen = {}
            for s in sched:
                k = f"{s['subject_id']}__{s['period_id']}"
                if k not in seen:
                    seen[k] = s
            self.state["classes"] = list(seen.values())
            self.cls_sel.items = [f"{c['subject_name']} ({c['period_label']})" for c in self.state["classes"]]
            
            # Default month to today
            m_idx = int(get_today_bs().split("-")[1]) - 1
            self.month_sel.value = self.month_sel.items[m_idx]
        except Exception as e:
            self.status.text = f"Init error: {e}"

    async def fetch_grid(self):
        if not self.cls_sel.value: return
        self.status.text = "Loading grid..."
        try:
            val_cls = str(self.cls_sel.value)
            idx = -1
            for i, c in enumerate(self.state["classes"]):
                if c["subject_name"] in val_cls and c["period_label"] in val_cls:
                    idx = i
                    break
            
            if idx < 0:
                self.status.text = "Error: Selected class not found."
                return

            cls = self.state["classes"][idx]
            self.state["selected_class"] = cls
            
            val_month = str(self.month_sel.value)
            m_idx = 1
            for i, m in enumerate(NEPALI_MONTHS):
                if m in val_month:
                    m_idx = i + 1
                    break
            
            self.state["roster"] = await api_client.get(f"/teacher/roster/{cls['subject_id']}")
            
            import nepali_datetime
            days = []
            for d in range(1, 33):
                try:
                    nd = nepali_datetime.date(2081, m_idx, d)
                    days.append(nd.strftime("%Y-%m-%d"))
                except ValueError: break
            self.state["days"] = days
            
            start = bs_to_ad(days[0])
            end = bs_to_ad(days[-1])
            att = await api_client.get(f"/teacher/attendance/range?subject_id={cls['subject_id']}&start_date={start}&end_date={end}")
            
            self.state["attendance"] = {f"{r['student_user_id']}_{r['attendance_date']}": r['status'] for r in att}
            self.state["pending"] = {}
            self.render_grid()
            self.status.text = f"Total students: {len(self.state['roster'])}"
        except Exception as e:
            self.status.text = f"Fetch error: {e}"

    def render_grid(self):
        for c in list(self.grid_box.children): self.grid_box.remove(c)
        if not self.state["roster"]: return

        # Header Row
        hdr = toga.Box(style=Pack(direction=ROW, background_color=M3_PRIMARY, height=44, align_items="center"))
        hdr.add(toga.Label("STUDENT NAME", style=Pack(width=160, color="white", font_weight="bold", margin=10, font_size=10)))
        for d in self.state["days"]:
            day_num = d.split("-")[2]
            hdr.add(toga.Label(day_num, style=Pack(width=36, color="white", text_align="center", font_size=10, font_weight="bold")))
        self.grid_box.add(hdr)

        STATUS_MAP = {"present":"P", "absent":"A", "late":"L", "excused":"E"}
        COLORS = {"present":"#10b981", "absent":"#ef4444", "late":"#f59e0b", "excused":"#8b5cf6"}

        for s in self.state["roster"]:
            row = toga.Box(style=Pack(direction=ROW, height=44, align_items="center"))
            row.add(toga.Label(s["full_name"], style=Pack(width=160, font_weight="bold", margin=10, font_size=11, color=M3_PRIMARY)))
            
            for d in self.state["days"]:
                key = f"{s['id']}_{bs_to_ad(d)}"
                status = self.state["pending"].get(key) or self.state["attendance"].get(key)
                
                btn = toga.Button(STATUS_MAP.get(status, "-"), 
                                  on_press=lambda w, _s=s["id"], _d=d: self.cycle_status(_s, _d),
                                  style=Pack(width=36, margin=0, font_size=10, font_weight="bold"))
                if status:
                    btn.style.background_color = COLORS.get(status)
                    btn.style.color = "white"
                else:
                    btn.style.color = M3_ON_SURFACE_VARIANT
                row.add(btn)
            self.grid_box.add(row)
            self.grid_box.add(toga.Box(style=Pack(height=1, background_color=M3_SURFACE_VARIANT)))

    def cycle_status(self, sid, day_bs):
        key = f"{sid}_{bs_to_ad(day_bs)}"
        current = self.state["pending"].get(key) or self.state["attendance"].get(key)
        order = [None, "present", "absent", "late", "excused"]
        try:
            nxt = order[(order.index(current) + 1) % len(order)]
        except ValueError: nxt = "present"
        
        if nxt == self.state["attendance"].get(key):
            if key in self.state["pending"]: del self.state["pending"][key]
        else:
            self.state["pending"][key] = nxt
        self.render_grid()

    async def save_bulk(self):
        if not self.state["pending"]:
            self.status.text = "No changes to save."
            return
        cls = self.state["selected_class"]
        self.save_btn.enabled = False
        self.status.text = "Saving changes..."
        try:
            records = []
            for key, st in self.state["pending"].items():
                sid, d_ad = key.split("_")
                records.append({
                    "student_id": int(sid),
                    "subject_id": cls["subject_id"],
                    "period_id": cls["period_id"],
                    "date": d_ad,
                    "status": st
                })
            await api_client.post("/attendance/bulk-mark", {"records": records})
            self.state["attendance"].update(self.state["pending"])
            self.state["pending"] = {}
            self.status.text = f"✓ Saved {len(records)} changes."
            self.status.style.color = "#10b981"
            self.render_grid()
        except Exception as e:
            self.status.text = f"Save error: {e}"
        finally:
            self.save_btn.enabled = True


class ScanScreen:
    def __init__(self, app):
        self.app = app
        self.container = self.build()

    def build(self):
        root = toga.Box(style=Pack(direction=COLUMN, margin=24, align_items="center", background_color="#f8fafc"))
        root.add(back_button(self.app))
        root.add(title_label("Scan Class QR"))
        root.add(toga.Label("Point your camera at the teacher's QR code to mark attendance.",
                             style=Pack(font_size=12, color="#64748b", margin_bottom=24, text_align="center")))

        status = status_label()

        async def handle_photo(photo):
            if not photo:
                status.text = "Cancelled."
                return
            status.text = "Decoding QR…"
            import io, tempfile, os
            buf = io.BytesIO()
            photo.save(buf, format="PNG")
            buf.seek(0)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(buf.read())
                tmp = f.name
            
            from attendance.utils.qr_handler import decode_qr_from_file
            token = decode_qr_from_file(tmp)
            os.unlink(tmp)
            
            if token == "ERROR_LIB_NOT_FOUND":
                status.text = "Driver Issue: Please install 'zbar' (brew install zbar)."
                status.style.color = "#ef4444"
                return
            elif not token:
                status.text = "Could not find a QR code. Hold steady and try again."
                status.style.color = "#f59e0b"
                return

            try:
                await api_client.post("/student/checkin", {"token": token})
                status.text = "✓ Attendance marked as Present!"
                status.style.color = "#10b981"
            except Exception as e:
                status.text = f"Check-in Error: {e}"
                status.style.color = "#ef4444"

        async def scan(widget):
            print(f"DEBUG: Starting scan. Camera object: {self.app.camera}")
            status.text = "Checking camera permission…"
            status.style.color = "#6b7280"
            try:
                # has_permission: True = granted, False = denied, None = not yet asked
                has_perm = self.app.camera.has_permission
                print(f"DEBUG: Initial permission state: {has_perm}")
                if not has_perm:
                    print("DEBUG: Requesting permission...")
                    has_perm = await self.app.camera.request_permission()
                    print(f"DEBUG: Permission result: {has_perm}")

                if not has_perm:
                    try:
                        # Use native Android AlertDialog if Toga's dialog is hanging
                        from java import jimport
                        AlertDialog = jimport("android.app.AlertDialog")
                        builder = AlertDialog.Builder(self.app._impl.native)
                        builder.setTitle("Camera Permission Required")
                        builder.setMessage("We need camera access to scan QR codes. Would you like to open App Settings to enable it manually?")
                        
                        def on_yes(dialog, which):
                            # Ensure we run this back in the Toga event loop
                            self.app.add_background_task(lambda a: open_settings(None))
                        
                        builder.setPositiveButton("YES", on_yes)
                        builder.setNegativeButton("NO", None)
                        builder.show()
                    except Exception as dialog_err:
                        # Fallback if native dialog fails
                        print(f"Native dialog failed: {dialog_err}")
                        await open_settings(None)
                    return

                grant_btn.style.display = "none"
                settings_btn.style.display = "none"
                status.text = "Opening camera…"
                print("DEBUG: Calling take_photo()...")
                photo = await self.app.camera.take_photo()
                print(f"DEBUG: Photo result: {photo}")
                await handle_photo(photo)
            except Exception as e:
                import traceback
                traceback.print_exc()
                err = str(e)
                print(f"DEBUG: Caught exception: {err}")
                if "permission" in err.lower() or "photo" in err.lower():
                    status.text = "Camera permission denied. Tap 'GRANT IN SETTINGS' to enable manually."
                    grant_btn.style.display = "pack"
                    settings_btn.style.display = "pack"
                    # Try opening settings automatically as requested
                    await open_settings(widget)
                else:
                    status.text = f"Camera Error: {err}"
                status.style.color = "#ef4444"

        async def open_settings(widget):
            try:
                # Use Chaquopy to invoke a native Android Intent to open app settings
                from java import jimport
                Intent = jimport("android.content.Intent")
                Settings = jimport("android.provider.Settings")
                Uri = jimport("android.net.Uri")
                
                intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
                # com.attendance.attendance
                uri = Uri.fromParts("package", self.app.app_id, None)
                intent.setData(uri)
                # self.app._impl.native is the MainActivity in toga-android
                self.app._impl.native.startActivity(intent)
                status.text = "Opening settings... please enable 'Camera' there."
                status.style.color = "#6366f1"
            except Exception as e:
                status.text = f"Could not open settings: {e}"
                status.style.color = "#ef4444"

        async def request_permission_manual(widget):
            try:
                print("DEBUG: Manual permission request...")
                granted = await self.app.camera.request_permission()
                print(f"DEBUG: Manual result: {granted}")
                if granted:
                    grant_btn.style.display = "none"
                    settings_btn.style.display = "none"
                    status.text = "✓ Permission granted! Tap 'Open Camera & Scan' to continue."
                    status.style.color = "#10b981"
                else:
                    status.text = "Still denied. Tap 'GRANT IN SETTINGS' to enable manually."
                    status.style.color = "#f59e0b"
                    settings_btn.style.display = "pack"
            except Exception as e:
                status.text = f"Could not request permission: {e}"
                status.style.color = "#ef4444"

        async def upload(widget):
            try:
                res = await self.app.main_window.open_file_dialog(
                    "Select QR Code Image",
                    multiselect=False,
                    file_types=["png", "jpg", "jpeg"]
                )
                if not res:
                    return
                path = res[0] if isinstance(res, list) else res
                status.text = "Reading file…"
                from attendance.utils.qr_handler import decode_qr_from_file
                token = decode_qr_from_file(str(path))

                if not token:
                    status.text = "No QR code found in this image."
                    status.style.color = "#ef4444"
                else:
                    await api_client.post("/student/checkin", {"token": token})
                    status.text = "✓ Success: Attendance marked from file!"
                    status.style.color = "#10b981"
            except Exception as e:
                status.text = f"File Error: {e}"
                status.style.color = "#ef4444"

        root.add(m3_button("OPEN CAMERA & SCAN", on_press=scan,
                           style=Pack(width=280, margin=8)))
        root.add(m3_button("OR SELECT IMAGE FILE", on_press=upload,
                           variant="outlined", style=Pack(width=280, margin=8)))

        # Only visible when camera permission is denied
        grant_btn = m3_button("GRANT CAMERA PERMISSION", on_press=request_permission_manual,
                              variant="filled",
                              style=Pack(width=280, margin=8, display="none",
                                        background_color="#f59e0b"))
        
        # New Settings button
        settings_btn = m3_button("GRANT IN SETTINGS", on_press=open_settings,
                                 variant="filled",
                                 style=Pack(width=280, margin=8, display="none",
                                           background_color="#6366f1"))
        
        root.add(grant_btn)
        root.add(settings_btn)
        root.add(status)
        return root


class AdminAttendanceScreen:
    def __init__(self, app):
        self.app = app
        self.container = self.build()

    def build(self):
        root = toga.Box(style=Pack(direction=COLUMN, margin=0, background_color="#f8fafc"))
        
        # Inner padding container
        content = toga.Box(style=Pack(direction=COLUMN, margin=14))
        root.add(content)
        
        content.add(back_button(self.app))
        content.add(title_label("Attendance Management"))
        
        status_lbl = status_label()
        
        def get_sel_id(sel, lst, offset=1):
            val = sel.value
            if val is None: return None
            try:
                def _get_val(x):
                    if hasattr(x, 'value'): return str(x.value)
                    if hasattr(x, 'text'): return str(x.text)
                    return str(x)
                
                target = _get_val(val)
                idx = -1
                for i, item in enumerate(sel.items):
                    if _get_val(item) == target:
                        idx = i
                        break
                
                if idx == -1: return None
                if offset == 1:
                    return lst[idx-1]["id"] if idx > 0 else None
                return lst[idx]["id"] if idx >= 0 else None
            except:
                return None
        
        # State
        state = {
            "students": [], "subjects": [], "periods": [], "teachers": [],
            "sessions": [], "courses": [], "records": [],
            "stats": {"total": 0, "present": 0, "absent": 0, "late": 0, "excused": 0},
            "editing_id": None
        }

        # --- Statistics Row ---
        self.stat_row = toga.Box(style=Pack(direction=ROW, margin_bottom=14))
        content.add(self.stat_row)

        def update_stats_ui():
            for child in list(self.stat_row.children):
                self.stat_row.remove(child)
            s = state["stats"]
            self.stat_row.add(stat_card("Total", s["total"], "#6366f1"))
            self.stat_row.add(stat_card("Present", s["present"], "#10b981"))
            self.stat_row.add(stat_card("Absent", s["absent"], "#ef4444"))
        
        # --- Filters Section ---
        filter_section = toga.Box(style=Pack(direction=COLUMN, margin_bottom=14))
        content.add(filter_section)

        def create_filt_sel(label_text, width=None):
            box = toga.Box(style=Pack(direction=COLUMN, margin=4, flex=1 if not width else 0))
            box.add(toga.Label(label_text, style=Pack(font_size=10, font_weight="bold", color="#94a3b8", margin_bottom=2)))
            sel = toga.Selection(style=Pack(width=width if width else 150))
            box.add(sel)
            return box, sel

        # Main Filters
        main_filters = toga.Box(style=Pack(direction=ROW))
        f_stu_box, f_stu_sel = create_filt_sel("STUDENT")
        f_sub_box, f_sub_sel = create_filt_sel("SUBJECT")
        main_filters.add(f_stu_box)
        main_filters.add(f_sub_box)
        filter_section.add(main_filters)

        main_filters_2 = toga.Box(style=Pack(direction=ROW, margin_top=4))
        f_df_inp = NepaliDatePicker("FROM (B.S.)")
        f_dt_inp = NepaliDatePicker("TO (B.S.)")
        main_filters_2.add(f_df_inp.box)
        main_filters_2.add(f_dt_inp.box)
        filter_section.add(main_filters_2)

        # Advanced Filters (Toggleable)
        adv_filters_box = toga.Box(style=Pack(direction=COLUMN, margin_top=8))
        f_ses_box, f_ses_sel = create_filt_sel("SESSION")
        f_crs_box, f_crs_sel = create_filt_sel("COURSE")
        f_per_box, f_per_sel = create_filt_sel("PERIOD")
        f_tea_box, f_tea_sel = create_filt_sel("TEACHER")
        f_sta_box, f_sta_sel = create_filt_sel("STATUS")
        f_sta_sel.items = ["Any", "present", "absent", "late", "excused"]

        for b in [f_ses_box, f_crs_box, f_per_box, f_tea_box, f_sta_box]:
            adv_filters_box.add(b)

        adv_visible = [False]
        def toggle_adv(w):
            if adv_visible[0]:
                filter_section.remove(adv_filters_box)
                w.text = "More Filters"
            else:
                filter_section.insert(3, adv_filters_box)
                w.text = "Less Filters"
            adv_visible[0] = not adv_visible[0]

        def reset_filters(w):
            f_stu_sel.value = "Any"
            f_sub_sel.value = "Any"
            f_ses_sel.value = "Any"
            f_crs_sel.value = "Any"
            f_per_sel.value = "Any"
            f_tea_sel.value = "Any"
            f_sta_sel.value = "Any"
            f_df_inp.value = ""
            f_dt_inp.value = ""
            asyncio.create_task(load_records())

        btn_row = toga.Box(style=Pack(direction=ROW, margin_top=8))
        adv_btn = toga.Button("More Filters", on_press=toggle_adv, style=Pack(margin_right=8))
        btn_row.add(adv_btn)
        
        search_btn = toga.Button("Search", on_press=lambda w: asyncio.create_task(load_records()), 
                                 style=Pack(flex=1, background_color="#6366f1", color="white"))
        reset_btn = toga.Button("Reset", on_press=reset_filters, 
                                style=Pack(margin_left=8, background_color="#94a3b8", color="white"))
        
        btn_row.add(search_btn)
        btn_row.add(reset_btn)
        filter_section.add(btn_row)

        # --- Add Record Form (Toggleable) ---
        add_form_parent = toga.Box(style=Pack(direction=COLUMN, margin_bottom=14))
        content.add(add_form_parent)
        
        add_form_inner = toga.Box(style=Pack(direction=COLUMN, margin=8, background_color="#ffffff"))
        add_form_inner.add(toga.Label("Add New Record", style=Pack(font_weight="bold", margin_bottom=10, color="#1e293b")))
        
        a_stu_box, a_stu_sel = create_filt_sel("STUDENT *")
        a_sub_box, a_sub_sel = create_filt_sel("SUBJECT *")
        a_per_box, a_per_sel = create_filt_sel("PERIOD *")
        a_tea_box, a_tea_sel = create_filt_sel("TEACHER *")
        a_sta_box, a_sta_sel = create_filt_sel("STATUS *")
        a_sta_sel.items = ["present", "absent", "late", "excused"]
        
        a_dt_inp = NepaliDatePicker("DATE (B.S.) *")
        add_form_inner.add(a_dt_inp.box)
        
        for b in [a_stu_box, a_sub_box, a_per_box, a_tea_box, a_sta_box]:
            add_form_inner.add(b)
        
        async def do_add(w):
            v_stu = get_sel_id(a_stu_sel, state["students"], 0)
            v_sub = get_sel_id(a_sub_sel, state["subjects"], 0)
            v_per = get_sel_id(a_per_sel, state["periods"], 0)
            v_tea = get_sel_id(a_tea_sel, state["teachers"], 0)
            
            missing = []
            if v_stu is None: missing.append("Student")
            if v_sub is None: missing.append("Subject")
            if v_per is None: missing.append("Period")
            if v_tea is None: missing.append("Teacher")
            if not a_dt_inp.value: missing.append("Date")
            
            if missing:
                status_lbl.text = f"Missing: {', '.join(missing)}"
                status_lbl.style.color = "#ef4444"
                return
            status_lbl.text = "Saving..."
            try:
                await api_client.post("/admin/attendance", {
                    "student_user_id": v_stu, "subject_id": v_sub,
                    "period_id": v_per, "teacher_user_id": v_tea,
                    "attendance_date": bs_to_ad(a_dt_inp.value), "status": a_sta_sel.value
                })
                status_lbl.text = "✓ Record added."
                status_lbl.style.color = "#10b981"
                asyncio.create_task(load_records())
            except Exception as e:
                status_lbl.text = f"Error: {e}"
                status_lbl.style.color = "#ef4444"

        add_form_inner.add(toga.Button("Save Record", on_press=do_add, 
                                       style=Pack(margin_top=10, background_color="#10b981", color="white")))

        add_visible = [False]
        def toggle_add(w):
            if add_visible[0]:
                add_form_parent.remove(add_form_inner)
                w.text = "Add Attendance Record"
            else:
                add_form_parent.add(add_form_inner)
                w.text = "Hide Add Form"
            add_visible[0] = not add_visible[0]

        add_btn = toga.Button("Add Attendance Record", on_press=toggle_add, style=Pack(margin_bottom=8))
        add_form_parent.add(add_btn)

        content.add(status_lbl)

        # --- List view ---
        list_box = toga.Box(style=Pack(direction=COLUMN))
        content.add(list_box)

        # --- Logic ---
        async def load_lookups():
            status_lbl.text = "Loading..."
            try:
                res = await asyncio.gather(
                    api_client.get("/students"), api_client.get("/academic/subjects"),
                    api_client.get("/academic/periods"), api_client.get("/academic/sessions"),
                    api_client.get("/academic/courses"), api_client.get("/admin/users/all")
                )
                state["students"], state["subjects"], state["periods"] = res[0], res[1], res[2]
                state["sessions"], state["courses"] = res[3], res[4]
                state["teachers"] = [u for u in res[5] if u.get("role") == "teacher"]
                
                f_stu_sel.items = ["Any"] + [s["full_name"] for s in state["students"]]
                f_sub_sel.items = ["Any"] + [s["name"] for s in state["subjects"]]
                f_per_sel.items = ["Any"] + [p["label"] for p in state["periods"]]
                f_ses_sel.items = ["Any"] + [s.get("name","") for s in state["sessions"]]
                f_crs_sel.items = ["Any"] + [c.get("name","") for c in state["courses"]]
                f_tea_sel.items = ["Any"] + [t["full_name"] for t in state["teachers"]]
                
                a_stu_sel.items = [s["full_name"] for s in state["students"]]
                a_sub_sel.items = [s["name"] for s in state["subjects"]]
                a_per_sel.items = [p["label"] for p in state["periods"]]
                a_tea_sel.items = [t["full_name"] for t in state["teachers"]]
                
                status_lbl.text = ""
                await load_records()
            except Exception as e:
                status_lbl.text = f"Init Error: {e}"

        async def load_records():
            status_lbl.text = "Refreshing..."
            for c in list(list_box.children): list_box.remove(c)
            
            qs = []
            v_stu = get_sel_id(f_stu_sel, state["students"])
            if v_stu: qs.append(f"student_id={v_stu}")
            v_sub = get_sel_id(f_sub_sel, state["subjects"])
            if v_sub: qs.append(f"subject_id={v_sub}")
            if f_df_inp.value: qs.append(f"date_from={bs_to_ad(f_df_inp.value)}")
            if f_dt_inp.value: qs.append(f"date_to={bs_to_ad(f_dt_inp.value)}")
            
            v_ses = get_sel_id(f_ses_sel, state["sessions"])
            if v_ses: qs.append(f"session_id={v_ses}")
            v_crs = get_sel_id(f_crs_sel, state["courses"])
            if v_crs: qs.append(f"course_id={v_crs}")
            v_per = get_sel_id(f_per_sel, state["periods"])
            if v_per: qs.append(f"period_id={v_per}")
            v_tea = get_sel_id(f_tea_sel, state["teachers"])
            if v_tea: qs.append(f"teacher_id={v_tea}")
            if f_sta_sel.value and str(f_sta_sel.value) != "Any": 
                qs.append(f"status={f_sta_sel.value}")

            try:
                records = await api_client.get(f"/admin/attendance?{'&'.join(qs)}")
                state["records"] = records
                
                state["stats"] = {
                    "total": len(records),
                    "present": len([r for r in records if r["status"] == "present"]),
                    "absent": len([r for r in records if r["status"] == "absent"]),
                    "late": len([r for r in records if r["status"] == "late"]),
                    "excused": len([r for r in records if r["status"] == "excused"]),
                }
                update_stats_ui()

                for r in records[:50]:
                    card = toga.Box(style=Pack(direction=COLUMN, margin=6, background_color="#ffffff"))
                    
                    row1 = toga.Box(style=Pack(direction=ROW))
                    row1.add(toga.Label(ad_to_bs(r.get("attendance_date")), 
                                        style=Pack(font_size=11, font_weight="bold", color="#6366f1", flex=1)))
                    
                    st = r.get("status", "present")
                    cols = {"present": ("#10b981", "#ecfdf5"), "absent": ("#ef4444", "#fef2f2"), 
                            "late": ("#f59e0b", "#fffbeb"), "excused": ("#8b5cf6", "#f5f3ff")}
                    fg, bg = cols.get(st, ("#64748b", "#f1f5f9"))
                    
                    pill = toga.Box(style=Pack(margin_left=8, margin_right=8, background_color=bg))
                    pill.add(toga.Label(st.upper(), style=Pack(font_size=10, font_weight="bold", color=fg)))
                    row1.add(pill)
                    card.add(row1)

                    card.add(toga.Label(r.get("student_name",""), 
                                        style=Pack(font_size=15, font_weight="bold", color="#1e293b", margin_top=4)))
                    card.add(toga.Label(f"{r.get('subject_name','')} | {r.get('period_label','')}", 
                                        style=Pack(font_size=12, color="#64748b")))
                    card.add(toga.Label(f"Teacher: {r.get('teacher_name','')}", 
                                        style=Pack(font_size=11, color="#94a3b8", margin_bottom=6)))

                    if state["editing_id"] == r["id"]:
                        e_row = toga.Box(style=Pack(direction=ROW, margin_top=6))
                        e_sel = toga.Selection(items=["present", "absent", "late", "excused"], 
                                               style=Pack(flex=1, margin_right=6))
                        e_sel.value = st
                        async def save_e(w, rid=r["id"], es=e_sel):
                            await api_client.put(f"/admin/attendance/{rid}", data={"status": es.value})
                            state["editing_id"] = None
                            asyncio.create_task(load_records())
                        e_row.add(e_sel)
                        e_row.add(toga.Button("Save", on_press=save_e, style=Pack(color="#10b981")))
                        e_row.add(toga.Button("X", on_press=lambda w: (state.update({"editing_id": None}), asyncio.create_task(load_records())), 
                                              style=Pack(color="#ef4444")))
                        card.add(e_row)
                    else:
                        act_row = toga.Box(style=Pack(direction=ROW, margin_top=4))
                        act_row.add(toga.Box(style=Pack(flex=1)))
                        act_row.add(toga.Button("Edit", 
                                                on_press=lambda w, rid=r["id"]: (state.update({"editing_id": rid}), asyncio.create_task(load_records())), 
                                                style=Pack(color="#3b82f6", font_size=11)))
                        async def del_r(w, rid=r["id"]):
                            await api_client.delete(f"/admin/attendance/{rid}")
                            asyncio.create_task(load_records())
                        act_row.add(toga.Button("Del", on_press=del_r, 
                                                style=Pack(color="#ef4444", font_size=11, margin_left=6)))
                        card.add(act_row)

                    list_box.add(card)
                    list_box.add(toga.Box(style=Pack(height=4)))
                
                status_lbl.text = f"Found {len(records)} records."
                status_lbl.style.color = "#64748b"
            except Exception as e:
                status_lbl.text = f"Fetch Error: {e}"
        
        asyncio.create_task(load_lookups())
        return scrollable(root)
