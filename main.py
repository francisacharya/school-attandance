#!/usr/bin/env python3
"""Attendance management desktop app (PyQt6 + SQLite)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from PyQt6.QtWidgets import QMainWindow, QSplitter, QVBoxLayout,QHBoxLayout, QWidget # Add QVBoxLayout here
_root = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv

    load_dotenv(_root / ".env")
except ImportError:
    pass

# Local matplotlib cache (avoids permission issues on locked-down home dirs)
os.environ.setdefault("MPLCONFIGDIR", str(_root / ".matplotlib"))

from PyQt6.QtWidgets import QApplication

from db.database import init_database
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow


def main() -> None:
    init_database()
    app = QApplication(sys.argv)
    app.setApplicationName("Attendance")
    
    # Load and apply QSS theme
    style_path = _root / "ui" / "style.qss"
    if style_path.exists():
        app.setStyleSheet(style_path.read_text(encoding="utf-8"))
        
    dlg = LoginDialog()
    if dlg.exec() != LoginDialog.DialogCode.Accepted:
        sys.exit(0)
    session = dlg.session()
    if session is None:
        sys.exit(1)
    win = MainWindow(session)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
