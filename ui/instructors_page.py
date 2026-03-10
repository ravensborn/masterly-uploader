from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QLabel,
    QScrollArea, QFrame,
)
from PyQt6.QtNetwork import QNetworkAccessManager

from ui.instructor_card import InstructorCard
from ui.flow_layout import FlowLayout


class InstructorsPage(QWidget):
    instructor_selected = pyqtSignal(int, str)  # id, name

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.net_manager = QNetworkAccessManager(self)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(400)
        self._search_timer.timeout.connect(self._do_search)
        self._setup_ui()
        self.api_client.instructors_loaded.connect(self._on_instructors_loaded)
        self.api_client.error.connect(self._on_error)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        # Header
        header = QLabel("Instructors")
        header.setStyleSheet("font-size: 26px; font-weight: 700; color: #101828; background: transparent;")
        layout.addWidget(header)

        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search instructors...")
        self.search_input.setFixedHeight(42)
        self.search_input.textChanged.connect(lambda: self._search_timer.start())
        layout.addWidget(self.search_input)

        # Loading / error label
        self.status_label = QLabel("Loading instructors...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; color: #667085; padding: 40px; background: transparent;")
        layout.addWidget(self.status_label)

        # Scroll area with flow layout
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.grid_container = QWidget()
        self.flow_layout = FlowLayout(self.grid_container, spacing=20)
        self.flow_layout.setContentsMargins(4, 4, 4, 4)
        self.scroll_area.setWidget(self.grid_container)

        layout.addWidget(self.scroll_area, stretch=1)

    def load(self):
        self.status_label.setText("Loading instructors...")
        self.status_label.show()
        self.api_client.fetch_instructors()

    def _do_search(self):
        search = self.search_input.text().strip()
        self.status_label.setText("Searching...")
        self.status_label.setStyleSheet("font-size: 14px; color: #667085; padding: 40px; background: transparent;")
        self.status_label.show()
        self.api_client.fetch_instructors(search=search)

    def _on_instructors_loaded(self, instructors: list):
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not instructors:
            self.status_label.setText("No instructors found.")
            self.status_label.show()
            return

        self.status_label.hide()

        for instructor in instructors:
            card = InstructorCard(instructor, self.net_manager, self.grid_container)
            card.clicked.connect(self.instructor_selected.emit)
            self.flow_layout.addWidget(card)

    def _on_error(self, message: str):
        self.status_label.setText(f"Error: {message}")
        self.status_label.show()
        self.status_label.setStyleSheet("font-size: 14px; color: #d32f2f; padding: 40px; background: transparent;")
