import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from attendance.utils.api import api_client
from attendance.ui.components import (
    title_label, body_label, m3_card, m3_button, 
    M3_SURFACE, M3_SURFACE_VARIANT
)

class LoginScreen:
    def __init__(self, app, on_login, username="", remember=False):
        self.app = app
        self.on_login = on_login
        
        # Main layout
        self.container = toga.Box(style=Pack(direction=COLUMN, align_items='center', 
                                             justify_content='center', background_color=M3_SURFACE, flex=1))
        
        # Login Card
        card = m3_card(style=Pack(width=320, margin=24))
        
        card.add(title_label("Sign In", style=Pack(text_align="center", margin_bottom=4)))
        card.add(body_label("Attendance Portal Ecosystem", style=Pack(text_align="center", margin_bottom=32)))
        
        card.add(body_label("USERNAME", style=Pack(font_weight="bold", font_size=11, margin_bottom=4)))
        self.username_input = toga.TextInput(placeholder="Username", value=username,
                                             style=Pack(margin_bottom=16, background_color=M3_SURFACE_VARIANT))
        card.add(self.username_input)
        
        card.add(body_label("PASSWORD", style=Pack(font_weight="bold", font_size=11, margin_bottom=4)))
        self.password_input = toga.PasswordInput(placeholder="Password", 
                                                 style=Pack(margin_bottom=16, background_color=M3_SURFACE_VARIANT))
        card.add(self.password_input)
        
        self.remember_switch = toga.Switch("Remember Login Details", value=remember,
                                            style=Pack(margin_bottom=24))
        card.add(self.remember_switch)
        
        self.login_button = m3_button("LOG IN", on_press=self.handle_login, 
                                      variant="filled", style=Pack(height=48))
        card.add(self.login_button)
        
        self.error_label = toga.Label("", style=Pack(color='#B3261E', margin_top=12, text_align="center", font_size=12))
        card.add(self.error_label)
        
        self.container.add(card)
        
    async def handle_login(self, widget):
        self.error_label.text = ""
        self.login_button.enabled = False
        try:
            username = (self.username_input.value or "").strip()
            password = (self.password_input.value or "").strip()
            
            if not username:
                await self.app.main_window.info_dialog("Login Error", "Please provide a username.")
                return
            if not password:
                await self.app.main_window.info_dialog("Login Error", "Please provide a password.")
                return

            result = await api_client.login(username, password)
            self.on_login(result, remember=self.remember_switch.value)
        except Exception as e:
            msg = str(e)
            if "401" in msg:
                title = "Authentication Failed"
                detail = "The username or password you entered is incorrect. Please try again."
            elif "Connect" in msg:
                title = "Connection Error"
                detail = "Could not connect to the server. Please check your internet connection or server status."
            else:
                title = "Login Issue"
                detail = msg
            
            await self.app.main_window.dialog(toga.InfoDialog(title, detail))
        finally:
            self.login_button.enabled = True
