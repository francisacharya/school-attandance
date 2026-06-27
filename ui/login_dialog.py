"""Login dialog."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from core.auth import UserSession, authenticate


class LoginDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sign in")
        self._session: UserSession | None = None
        self._username = QLineEdit()
        self._username.setPlaceholderText("Username")
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Password")
        self._error = QLabel("")
        self._error.setStyleSheet("color: #c0392b;")
        self._error.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Username", self._username)
        form.addRow("Password", self._password)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._try_login)
        buttons.rejected.connect(self.reject)

        title_label = QLabel("Attendance Management")
        title_label.setProperty("styleClass", "h1")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.setSpacing(20)
        lay.addWidget(title_label)
        lay.addLayout(form)
        lay.addWidget(self._error)
        lay.addWidget(buttons)
        self.resize(450, 300)

    def session(self) -> UserSession | None:
        return self._session

    def _try_login(self) -> None:
        u = self._username.text().strip()
        p = self._password.text()
        if not u or not p:
            self._error.setText("Enter username and password.")
            return
        sess = authenticate(u, p)
        if sess is None:
            self._error.setText("Invalid credentials.")
            return
        self._session = sess
        self.accept()
