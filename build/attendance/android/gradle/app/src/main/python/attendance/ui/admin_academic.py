import asyncio
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from attendance.utils.api import api_client
from attendance.utils.nepali_date import ad_to_bs, bs_to_ad, get_today_bs
from attendance.ui.components import (
    back_button, scrollable, title_label, body_label, status_label, 
    NepaliDatePicker, m3_card, m3_button, 
    M3_SURFACE, M3_PRIMARY, M3_ON_SURFACE_VARIANT, M3_SURFACE_VARIANT
)

class AdminAcademicScreen:
    def __init__(self, app, endpoint, name):
        self.app = app
        self.endpoint = endpoint
        self.name = name
        self.container = self.build()

    def build(self):
        root = toga.Box(style=Pack(direction=COLUMN, margin=16, background_color=M3_SURFACE))
        root.add(back_button(self.app))
        root.add(title_label(self.name))

        FIELD_DEFS = {
            "sessions":  [("label", "Session Label (e.g. 2081/2082)"),
                           ("start_date", "Start Date (B.S.)", True),
                           ("end_date",   "End Date (B.S.)", True)],
            "courses":   [("code", "Course Code"), ("name", "Course Name")],
            "semesters": [("name", "Semester Name")],
            "subjects":  [("code", "Subject Code"), ("name", "Subject Name")],
            "rooms":     [("name", "Room Name"), ("building", "Building")],
            "periods":   [("label", "Label (e.g. P1)"), ("start_time", "Start (HH:MM)"),
                           ("end_time", "End (HH:MM)"), ("sort_order", "Sort Order")],
        }
        fields = FIELD_DEFS.get(self.endpoint, [])
        inputs = {}
        
        form_card = m3_card(style=Pack(margin_bottom=16))
        for f_def in fields:
            fname = f_def[0]
            placeholder = f_def[1]
            is_date = f_def[2] if len(f_def) > 2 else False
            
            if is_date:
                picker = NepaliDatePicker(placeholder)
                form_card.add(picker.box)
                inp = picker
            else:
                form_card.add(body_label(placeholder, style=Pack(font_weight="bold", font_size=11, margin_bottom=4)))
                inp = toga.TextInput(placeholder=placeholder, 
                                     style=Pack(margin_bottom=12, background_color=M3_SURFACE_VARIANT))
                form_card.add(inp)
            inputs[fname] = inp
        root.add(form_card)

        status = status_label()
        list_box = toga.Box(style=Pack(direction=COLUMN, background_color=M3_SURFACE))
        state = {"editing_id": None}

        async def save(w):
            data = {}
            for f_def in fields:
                fname = f_def[0]
                is_date = f_def[2] if len(f_def) > 2 else False
                val = inputs[fname].value
                if is_date: val = bs_to_ad(val)
                data[fname] = val
            is_edit = state["editing_id"] is not None
            action = "Update" if is_edit else "Create"
            if not await self.app.main_window.question_dialog("Confirm", f"Are you sure you want to {action.lower()} this record?"):
                return

            try:
                if is_edit:
                    await api_client.put(f"/academic/{self.endpoint}/{state['editing_id']}", data)
                    state["editing_id"] = None
                    status.text = "✓ Updated successfully."
                else:
                    await api_client.post(f"/academic/{self.endpoint}", data)
                    status.text = "✓ Added successfully."
                status.style.color = "#10b981"
                for i in inputs.values(): i.value = ""
                save_btn.text = f"ADD {self.name.upper()}"
                asyncio.create_task(refresh())
            except Exception as e:
                status.text = f"Error: {e}"
                status.style.color = "#ef4444"

        save_btn = m3_button("SAVE CHANGES", on_press=save, variant="filled", style=Pack(margin=10))
        root.add(save_btn)
        root.add(status)
        
        root.add(title_label("Existing Records", style=Pack(font_size=16, margin_top=16, margin_bottom=8)))
        root.add(list_box)

        async def refresh():
            for c in list(list_box.children): list_box.remove(c)
            try:
                items = await api_client.get(f"/academic/{self.endpoint}")
                for item in items:
                    card = m3_card(style=Pack(margin=4))
                    row = toga.Box(style=Pack(direction=ROW, align_items="center"))
                    
                    # Display primary field(s)
                    label_text = " • ".join([str(item.get(f[0], "")) for f in fields[:2]])
                    row.add(toga.Label(label_text, style=Pack(flex=1, font_weight="bold")))
                    
                    row.add(toga.Button("Edit", on_press=lambda w, i=item: _edit(i), style=Pack(margin=2)))
                    row.add(toga.Button("Del", on_press=lambda w, i=item: asyncio.create_task(do_del(i["id"])), style=Pack(margin=2, color="#ef4444")))
                    
                    card.add(row)
                    list_box.add(card)
                    list_box.add(toga.Box(style=Pack(height=1, background_color="#e2e8f0")))
                if not items:
                    list_box.add(toga.Label("Nothing here yet.", style=Pack(color="#64748b")))
            except Exception as e:
                list_box.add(toga.Label(f"Error: {e}", style=Pack(color="red")))

        def _edit(item):
            state["editing_id"] = item["id"]
            for f_def in fields:
                fname = f_def[0]
                is_date = f_def[2] if len(f_def) > 2 else False
                v = item.get(fname, "")
                if is_date: v = ad_to_bs(v)
                inputs[fname].value = str(v)
            status.text = f"Editing ID {item['id']}. Update fields and hit Save."
            status.style.color = "#3b82f6"
            save_btn.text = "SAVE CHANGES"

        async def do_del(iid):
            if not await self.app.main_window.question_dialog("Confirm", "Are you sure you want to delete this record?"):
                return
            try:
                await api_client._client.delete(
                    f"/academic/{self.endpoint}/{iid}",
                    headers={"Authorization": f"Bearer {api_client.token}"},
                )
                asyncio.create_task(refresh())
            except Exception as e:
                status.text = f"Delete error: {e}"

        asyncio.create_task(refresh())
        return scrollable(root)


class AdminUsersScreen:
    def __init__(self, app):
        self.app = app
        self.state = {"editing_id": None}
        self.container = self.build()

    def build(self):
        root = toga.Box(style=Pack(direction=COLUMN, margin=14, background_color="#f8fafc"))
        root.add(back_button(self.app))
        root.add(title_label("Users & Roles"))

        name_inp = toga.TextInput(placeholder="Full Name", style=Pack(margin_bottom=8))
        user_inp = toga.TextInput(placeholder="Username", style=Pack(margin_bottom=8))
        pass_inp = toga.PasswordInput(placeholder="Password (leave blank to keep existing during edit)", style=Pack(margin_bottom=8))
        role_sel = toga.Selection(items=["teacher", "student", "parent", "admin"], style=Pack(margin_bottom=8))
        status = status_label()
        list_box = toga.Box(style=Pack(direction=COLUMN))

        root.add(name_inp)
        root.add(user_inp)
        root.add(pass_inp)
        root.add(role_sel)

        async def save_user(w):
            if not name_inp.value or not user_inp.value:
                status.text = "Error: Name and Username are required."
                status.style.color = "#ef4444"
                return

            is_edit = self.state["editing_id"] is not None
            action = "Update" if is_edit else "Create"
            
            if not await self.app.main_window.question_dialog("Confirm", f"Are you sure you want to {action.lower()} this user?"):
                return

            try:
                payload = {
                    "full_name": name_inp.value, "username": user_inp.value,
                    "password": pass_inp.value, "role": role_sel.value, "email": "",
                }
                if is_edit:
                    await api_client.put(f"/admin/users/{self.state['editing_id']}", payload)
                    status.text = "✓ User updated."
                else:
                    await api_client.post("/admin/users", payload)
                    status.text = "✓ User created."
                
                name_inp.value = ""
                user_inp.value = ""
                pass_inp.value = ""
                self.state["editing_id"] = None
                save_btn.text = "CREATE USER"
                
                status.style.color = "#10b981"
                asyncio.create_task(refresh())
            except Exception as e:
                status.text = f"Error: {e}"
                status.style.color = "#ef4444"

        save_btn = toga.Button("Create User", on_press=save_user, style=Pack(margin=8, margin_bottom=10))
        root.add(save_btn)
        root.add(status)
        root.add(toga.Label("All Users:", style=Pack(font_size=16, font_weight="bold", color="#334155", margin_bottom=8)))
        root.add(list_box)

        def _edit(u):
            self.state["editing_id"] = u["id"]
            name_inp.value = u["full_name"]
            user_inp.value = u["username"]
            pass_inp.value = ""
            role_sel.value = u["role"]
            save_btn.text = "UPDATE USER"
            status.text = f"Editing user: {u['username']}"
            status.style.color = "#3b82f6"

        async def refresh():
            for c in list(list_box.children):
                list_box.remove(c)
            try:
                users = await api_client.get("/admin/users/all")
                for u in users:
                    row = toga.Box(style=Pack(direction=ROW, margin=6, background_color="#ffffff", align_items="center"))
                    row.add(toga.Label(u["full_name"], style=Pack(flex=1, font_size=14, font_weight="bold", color="#1e293b")))
                    row.add(toga.Label(u.get("role", ""), style=Pack(width=70, font_size=11, color="#6366f1")))
                    
                    row.add(toga.Button("Edit", 
                                        on_press=lambda w, user=u: _edit(user),
                                        style=Pack(margin=4)))
                    
                    row.add(toga.Button("Del",
                                         on_press=lambda w, uid=u["id"]: asyncio.create_task(do_del(uid)),
                                         style=Pack(margin=4, color="#ef4444")))
                    list_box.add(row)
                    list_box.add(toga.Box(style=Pack(height=1, background_color="#e2e8f0")))
            except Exception as e:
                list_box.add(toga.Label(f"Error: {e}", style=Pack(color="red")))
            except Exception as e:
                list_box.add(toga.Label(f"Error: {e}", style=Pack(color="red")))

        async def do_del(uid):
            if not await self.app.main_window.question_dialog("Confirm", "Are you sure you want to delete this user?"):
                return
            try:
                await api_client._client.delete(
                    f"/admin/users/{uid}",
                    headers={"Authorization": f"Bearer {api_client.token}"},
                )
                asyncio.create_task(refresh())
            except Exception as e:
                status.text = f"Error: {e}"

        asyncio.create_task(refresh())
        return scrollable(root)


class SettingsScreen:
    def __init__(self, app):
        self.app = app
        self.container = self.build()

    def build(self):
        root = toga.Box(style=Pack(direction=COLUMN, margin=14, background_color="#f8fafc"))
        root.add(back_button(self.app))
        root.add(title_label("Rules & Settings"))
        status = status_label()
        root.add(status)

        # Geofence
        root.add(toga.Label("Geofencing Policy", style=Pack(font_size=16, font_weight="bold", color="#334155", margin_bottom=8)))
        lat_inp = toga.TextInput(placeholder="Campus Latitude", style=Pack(margin_bottom=8))
        lng_inp = toga.TextInput(placeholder="Campus Longitude", style=Pack(margin_bottom=8))
        rad_inp = toga.TextInput(placeholder="Radius (meters)", style=Pack(margin_bottom=8))
        root.add(lat_inp)
        root.add(lng_inp)
        root.add(rad_inp)

        async def save_geo(w):
            try:
                await api_client.post("/admin/rules/geofence", {
                    "lat": float(lat_inp.value or 0), "lng": float(lng_inp.value or 0),
                    "radius": int(rad_inp.value or 100), "class_only": False,
                })
                status.text = "✓ Geofence saved."
                status.style.color = "#10b981"
            except Exception as e:
                status.text = f"Error: {e}"

        root.add(toga.Button("Save Geofence", on_press=save_geo, style=Pack(margin=8, margin_bottom=16)))

        # SMS
        root.add(toga.Label("SMS Alerts (Twilio)", style=Pack(font_size=16, font_weight="bold", color="#334155", margin_bottom=8)))
        sid_inp = toga.TextInput(placeholder="Twilio SID", style=Pack(margin_bottom=8))
        tok_inp = toga.TextInput(placeholder="Auth Token", style=Pack(margin_bottom=8))
        num_inp = toga.TextInput(placeholder="From Number (+1555…)", style=Pack(margin_bottom=8))
        root.add(sid_inp)
        root.add(tok_inp)
        root.add(num_inp)

        async def save_sms(w):
            try:
                await api_client.post("/admin/rules/sms", {
                    "enabled": True, "sid": sid_inp.value,
                    "token": tok_inp.value, "from_num": num_inp.value,
                })
                status.text = "✓ SMS config saved."
                status.style.color = "#10b981"
            except Exception as e:
                status.text = f"Error: {e}"

        root.add(toga.Button("Save SMS Config", on_press=save_sms, style=Pack(margin=8)))

        async def load():
            try:
                sms = await api_client.get("/admin/rules/sms")
                sid_inp.value = sms.get("sid", "")
                tok_inp.value = sms.get("token", "")
                num_inp.value = sms.get("from_num", "")
            except Exception:
                pass

        asyncio.create_task(load())
        return scrollable(root)
