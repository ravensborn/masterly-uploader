from PyQt6.QtWidgets import QMainWindow, QStackedWidget
from PyQt6.QtCore import QSize

from ui.api_client import ApiClient
from ui.instructors_page import InstructorsPage
from ui.courses_page import CoursesPage


class MainWindow(QMainWindow):
    def __init__(self, api_base: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video Course Manager")
        self.setMinimumSize(QSize(800, 500))
        self.resize(1100, 700)

        self.api_client = ApiClient(api_base, parent=self)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Instructors page
        self.instructors_page = InstructorsPage(self.api_client, self)
        self.instructors_page.instructor_selected.connect(self._on_instructor_selected)
        self.stack.addWidget(self.instructors_page)

        # Courses page
        self.courses_page = CoursesPage(self.api_client, self)
        self.courses_page.back_requested.connect(self._show_instructors)
        self.courses_page.course_selected.connect(self._on_course_selected)
        self.stack.addWidget(self.courses_page)

        # Load initial data
        self.instructors_page.load()

    def _on_instructor_selected(self, instructor_id: int, name: str):
        self.courses_page.load(instructor_id, name)
        self.stack.setCurrentWidget(self.courses_page)

    def _show_instructors(self):
        self.stack.setCurrentWidget(self.instructors_page)

    def _on_course_selected(self, course_id: int, title: str):
        # Placeholder — will navigate to course detail page next
        print(f"Selected course: {title} (ID: {course_id})")
