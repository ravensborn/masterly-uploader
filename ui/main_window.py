import os

from PySide6.QtWidgets import QMainWindow, QStackedWidget, QVBoxLayout, QLabel, QWidget
from PySide6.QtCore import QSize

from ui.api_client import ApiClient
from ui.instructors_page import InstructorsPage
from ui.courses_page import CoursesPage
from ui.course_detail_page import CourseDetailPage


class MainWindow(QMainWindow):
    def __init__(self, api_base: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video Course Manager")
        self.setMinimumSize(QSize(900, 560))
        self.resize(1200, 760)

        username = os.getenv("API_USERNAME", "admin")
        password = os.getenv("API_PASSWORD", "password")
        self.api_client = ApiClient(api_base, username=username, password=password, parent=self)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bucket = os.environ.get("R2_BUCKET_NAME", "—")
        server_label = QLabel(f"  Server: {api_base}    Bucket: {bucket}")
        server_label.setFixedHeight(28)
        server_label.setStyleSheet(
            "background: #1e293b; color: #94a3b8; font-size: 11px; font-weight: 600; padding: 0 12px;"
        )
        layout.addWidget(server_label)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        self.setCentralWidget(central)

        # Instructors page
        self.instructors_page = InstructorsPage(self.api_client, self)
        self.instructors_page.instructor_selected.connect(self._on_instructor_selected)
        self.stack.addWidget(self.instructors_page)

        # Courses page
        self.courses_page = CoursesPage(self.api_client, self)
        self.courses_page.back_requested.connect(self._show_instructors)
        self.courses_page.course_selected.connect(self._on_course_selected)
        self.stack.addWidget(self.courses_page)

        # Course detail page
        self.detail_page = CourseDetailPage(self.api_client, self)
        self.detail_page.back_requested.connect(self._show_courses)
        self.stack.addWidget(self.detail_page)

        # Load initial data
        self.instructors_page.load()

    def _on_instructor_selected(self, instructor_id: int, name: str):
        self._current_instructor = (instructor_id, name)
        self.courses_page.load(instructor_id, name)
        self.stack.setCurrentWidget(self.courses_page)

    def _show_instructors(self):
        self.stack.setCurrentWidget(self.instructors_page)

    def _on_course_selected(self, course_id: int, title: str):
        self.detail_page.load(course_id, title)
        self.stack.setCurrentWidget(self.detail_page)

    def _show_courses(self):
        self.stack.setCurrentWidget(self.courses_page)
