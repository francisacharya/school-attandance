import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from attendance.utils.api import api_client
from attendance.ui.login import LoginScreen
from attendance.ui.dashboards import DashboardScreen
import json
import os
import warnings
warnings.filterwarnings("ignore", category=ResourceWarning)

class AttendanceApp(toga.App):
    def startup(self):
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.session = None
        self.current_screen = None
        self.config = self.load_config()
        
        # Initial screen is Login (with pre-filled username if remembered)
        r = self.config.get("remember", False)
        user = self.config.get("username", "") if r else ""
        self.show_login(username=user, remember=r)
        self.main_window.show()

    def show_login(self, username="", remember=False):
        self.current_screen = LoginScreen(self, on_login=self.on_login_success, 
                                          username=username, remember=remember)
        self.main_window.content = self.current_screen.container

    def on_login_success(self, session_data, remember=False):
        self.session = session_data
        self.save_config(remember=remember, username=session_data.get('username'))
        print(f"Logged in as {self.session.get('role')}")
        self.show_dashboard()

    def load_config(self):
        conf_file = self.paths.data / "config.json"
        if conf_file.exists():
            try:
                with open(conf_file, "r") as f:
                    return json.load(f)
            except: pass
        return {"remember": False, "username": ""}

    def save_config(self, remember, username):
        conf_file = self.paths.data / "config.json"
        # Ensure directory exists
        if not conf_file.parent.exists():
            conf_file.parent.mkdir(parents=True)
        
        data = {"remember": remember, "username": username if remember else ""}
        with open(conf_file, "w") as f:
            json.dump(data, f)

    def show_dashboard(self):
        self.current_screen = DashboardScreen(self, role=self.session.get('role'))
        self.main_window.content = self.current_screen.container

    def logout(self):
        self.session = None
        api_client.token = None # Reset token
        self.show_login()

    async def on_exit(self, app=None, **kwargs):
        try:
            await api_client.close()
        except: pass
        return True

def main():
    return AttendanceApp()
