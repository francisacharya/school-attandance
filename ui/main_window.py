"""Main shell: left navigation by role, right-hand content stack."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QWidget,
)

from core.auth import UserSession
from ui.pages_admin import build_admin_pages
from ui.pages_student import build_parent_pages, build_student_pages
from ui.pages_teacher import build_teacher_stack


class MainWindow(QMainWindow):
    def __init__(self, session: UserSession) -> None:
        super().__init__()
        self._session = session
        self.setWindowTitle(f"Attendance — {session.full_name} ({session.role})")
        self.resize(1100, 720)

        self._nav = QListWidget()
        self._nav.setMinimumWidth(220)
        self._stack = QStackedWidget()
        
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidget(self._stack)

        self._nav_wrapper = self._wrap_nav()
        
        self._toggle_btn = QPushButton("☰ Toggle Sidebar")
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(True)
        self._toggle_btn.clicked.connect(self._toggle_sidebar)
        self._toggle_btn.setFixedWidth(150)
        self._toggle_btn.setStyleSheet("margin: 5px;")

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._nav_wrapper)
        self._splitter.addWidget(self._scroll)
        self._splitter.setStretchFactor(1, 1)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        top_bar = QHBoxLayout()
        top_bar.addWidget(self._toggle_btn)
        top_bar.addStretch()
        
        main_layout.addLayout(top_bar)
        main_layout.addWidget(self._splitter)
        
        central = QWidget()
        central.setLayout(main_layout)
        self.setCentralWidget(central)

        self._pages: dict[str, QWidget] = {}
        if session.role == "admin":
            self._build_admin()
        elif session.role == "teacher":
            self._build_teacher()
        elif session.role == "student":
            self._build_student()
        elif session.role == "parent":
            self._build_parent()
        else:
            QLabel("Unsupported role")

        if self._nav.count() > 0:
            self._nav.setCurrentRow(0)

    def _wrap_nav(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        v = QVBoxLayout()
        v.setContentsMargins(10, 20, 10, 20)
        v.setSpacing(10)
        title = QLabel("Features")
        title.setProperty("styleClass", "h1")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        v.addWidget(title)
        v.addWidget(self._nav)
        logout = QPushButton("Sign out")
        logout.clicked.connect(self._logout)
        v.addWidget(logout)
        lay.addLayout(v, 1)
        self._nav.currentRowChanged.connect(self._on_nav)
        return w

    def _toggle_sidebar(self) -> None:
        self._nav_wrapper.setVisible(self._toggle_btn.isChecked())

    def _on_nav(self, row: int) -> None:
        if row < 0:
            return
        item = self._nav.item(row)
        if item is None:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if key is None:
            return
        idx = self._stack.indexOf(self._pages[key])
        if idx >= 0:
            self._stack.setCurrentIndex(idx)

    def _add_page(self, key: str, widget: QWidget) -> None:
        self._pages[key] = widget
        self._stack.addWidget(widget)
        item = QListWidgetItem(key)
        item.setData(Qt.ItemDataRole.UserRole, key)
        self._nav.addItem(item)

    def _build_admin(self) -> None:
        for k, w in build_admin_pages():
            self._add_page(k, w)

    def _build_teacher(self) -> None:
        for k, w in build_teacher_stack(self._session.user_id):
            self._add_page(k, w)

    def _build_student(self) -> None:
        for k, w in build_student_pages(self._session.user_id):
            self._add_page(k, w)

    def _build_parent(self) -> None:
        for k, w in build_parent_pages(self._session.user_id):
            self._add_page(k, w)

    def _logout(self) -> None:
        reply = QMessageBox.question(
            self,
            "Sign out",
            "Sign out now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.close()
