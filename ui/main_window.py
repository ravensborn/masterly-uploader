from PySide6.QtWidgets import QMainWindow, QStackedWidget
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
