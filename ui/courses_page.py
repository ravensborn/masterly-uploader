from PySide6.QtCore import Qt, Signal, QSize, QUrl
from PySide6.QtGui import QPixmap, QCursor, QColor, QPainter, QPainterPath, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QPushButton,
    QGraphicsDropShadowEffect,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from ui.flow_layout import FlowLayout

BACK_BTN_STYLE = """
    QPushButton {
        background: #ffffff;
        border: 1.5px solid #e2e8f0;
        border-radius: 10px;
        color: #475569;
        font-size: 13px;
        font-weight: 600;
        padding: 0 18px;
    }
    QPushButton:hover {
        background: #f8fafc;
        border-color: #93c5fd;
        color: #3b82f6;
    }
"""


class CourseCard(QFrame):
    clicked = Signal(int, str)  # course_id, title

    def __init__(self, course: dict, net_manager: QNetworkAccessManager, parent=None):
        super().__init__(parent)
        self.course_id = course["id"]
        self.title = self._localized(course.get("title", ""))
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._setup_style()
        self._setup_ui(course)
        self._load_thumbnail(course.get("thumbnail_url"), net_manager)

    def _localized(self, value):
        if isinstance(value, dict):
            return value.get("ku-b", value.get("ku", value.get("en", str(value))))
        if isinstance(value, list):
            return str(value[0]) if value else ""
        return str(value)

    def _setup_style(self):
        self.setFixedSize(260, 250)
        self.setStyleSheet("""
            CourseCard {
                background: #ffffff;
                border: 1.5px solid #f1f5f9;
                border-radius: 20px;
            }
            CourseCard:hover {
                border: 1.5px solid #93c5fd;
                background: #fafbff;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(15, 23, 42, 20))
        self.setGraphicsEffect(shadow)

    def _setup_ui(self, course):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 16)

        # Thumbnail
        self.thumb_label = QLabel()
        self.thumb_label.setFixedHeight(130)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #dbeafe, stop:1 #bfdbfe);
            border-top-left-radius: 20px;
            border-top-right-radius: 20px;
            color: #2563eb;
            font-size: 24px;
            font-weight: bold;
        """)
        self.thumb_label.setText(self.title[:3].upper() if self.title else "?")
        layout.addWidget(self.thumb_label)

        # Title
        title_label = QLabel(self.title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("""
            font-size: 14px; font-weight: 600; color: #0f172a;
            padding: 0 16px; background: transparent;
        """)
        layout.addWidget(title_label)

        # Lessons count badge
        lessons_count = course.get("lessons_count", "0")
        count_label = QLabel(f"{lessons_count} lessons")
        count_label.setStyleSheet("""
            font-size: 12px;
            color: #3b82f6;
            background: #eff6ff;
            border-radius: 12px;
            padding: 4px 12px;
            font-weight: 500;
            margin-left: 16px;
        """)
        count_label.setFixedHeight(26)
        layout.addWidget(count_label, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch()

    def _load_thumbnail(self, url, net_manager: QNetworkAccessManager):
        if not url:
            return
        request = QNetworkRequest(QUrl(url))
        reply = net_manager.get(request)
        reply.finished.connect(lambda: self._on_thumb_loaded(reply))

    def _on_thumb_loaded(self, reply: QNetworkReply):
        if reply.error() == QNetworkReply.NetworkError.NoError:
            pixmap = QPixmap()
            pixmap.loadFromData(reply.readAll())
            if not pixmap.isNull():
                w, h = 260, 130
                scaled = pixmap.scaled(
                    QSize(w, h),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = (scaled.width() - w) // 2
                y = (scaled.height() - h) // 2
                cropped = scaled.copy(max(0, x), max(0, y), w, h)

                # Round the top corners
                rounded = QPixmap(w, h)
                rounded.fill(Qt.GlobalColor.transparent)
                painter = QPainter(rounded)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                path = QPainterPath()
                radius = 20.0
                path.moveTo(0, h)
                path.lineTo(0, radius)
                path.arcTo(0, 0, radius * 2, radius * 2, 180, -90)
                path.lineTo(w - radius, 0)
                path.arcTo(w - radius * 2, 0, radius * 2, radius * 2, 90, -90)
                path.lineTo(w, h)
                path.closeSubpath()
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, cropped)
                painter.end()

                self.thumb_label.setPixmap(rounded)
                self.thumb_label.setStyleSheet("background: transparent;")
        reply.deleteLater()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.course_id, self.title)
        super().mousePressEvent(event)


class CoursesPage(QWidget):
    course_selected = Signal(int, str)  # course_id, title
    back_requested = Signal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.net_manager = QNetworkAccessManager(self)
        self._setup_ui()
        self.api_client.courses_loaded.connect(self._on_courses_loaded)
        self.api_client.error.connect(self._on_error)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 40, 48, 32)
        layout.setSpacing(0)

        # Header row with back button
        header_row = QHBoxLayout()
        header_row.setSpacing(16)

        self.back_btn = QPushButton("\u2190  Back")
        self.back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.back_btn.setFixedHeight(38)
        self.back_btn.setStyleSheet(BACK_BTN_STYLE)
        self.back_btn.clicked.connect(self.back_requested.emit)
        header_row.addWidget(self.back_btn)

        self.header = QLabel("Courses")
        self.header.setStyleSheet("font-size: 28px; font-weight: 700; color: #0f172a; background: transparent;")
        header_row.addWidget(self.header)
        header_row.addStretch()

        layout.addLayout(header_row)

        layout.addSpacing(28)

        # Status label
        self.status_label = QLabel("Loading courses...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; color: #94a3b8; padding: 60px 0; background: transparent;")
        layout.addWidget(self.status_label)

        # Scroll area for cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.grid_container = QWidget()
        self.flow_layout = FlowLayout(self.grid_container, spacing=24)
        self.flow_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_area.setWidget(self.grid_container)

        layout.addWidget(self.scroll_area, stretch=1)

    def load(self, instructor_id: int, instructor_name: str):
        # Clear previous cards immediately before showing the page
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.header.setText(f"Courses \u2014 {instructor_name}")
        self.status_label.setText("Loading courses...")
        self.status_label.setStyleSheet("font-size: 14px; color: #94a3b8; padding: 60px 0; background: transparent;")
        self.status_label.show()
        self.scroll_area.hide()
        self.api_client.fetch_courses(instructor_id)

    def _on_courses_loaded(self, courses: list):
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not courses:
            self.status_label.setText("No courses found.")
            self.status_label.show()
            return

        self.status_label.hide()
        self.scroll_area.show()

        for course in courses:
            card = CourseCard(course, self.net_manager, self.grid_container)
            card.clicked.connect(self.course_selected.emit)
            self.flow_layout.addWidget(card)

    def _on_error(self, message: str):
        self.status_label.setText(f"Error: {message}")
        self.status_label.show()
        self.status_label.setStyleSheet("font-size: 14px; color: #ef4444; padding: 60px 0; background: transparent;")
