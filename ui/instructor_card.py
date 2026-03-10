from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QCursor
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QGraphicsDropShadowEffect
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QColor


class InstructorCard(QFrame):
    clicked = pyqtSignal(int, str)  # instructor_id, display_name

    def __init__(self, instructor: dict, net_manager: QNetworkAccessManager, parent=None):
        super().__init__(parent)
        self.instructor_id = instructor["id"]
        self.display_name = self._localized(instructor.get("display_name", ""))
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._setup_style()
        self._setup_ui(instructor)
        self._load_photo(instructor.get("photo_url", ""), net_manager)

    def _localized(self, value):
        if isinstance(value, dict):
            return value.get("ar", value.get("en", str(value)))
        if isinstance(value, list):
            return str(value[0]) if value else ""
        return str(value)

    def _setup_style(self):
        self.setFixedSize(200, 260)
        self.setStyleSheet("""
            InstructorCard {
                background: #ffffff;
                border: 1px solid #e4e7ec;
                border-radius: 16px;
            }
            InstructorCard:hover {
                border: 1px solid #1976d2;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 25))
        self.setGraphicsEffect(shadow)

    def _setup_ui(self, instructor):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 20, 16, 20)

        # Photo placeholder
        self.photo_label = QLabel()
        self.photo_label.setFixedSize(100, 100)
        self.photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo_label.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #e3f2fd, stop:1 #bbdefb);
            border-radius: 50px;
            color: #1565c0;
            font-size: 32px;
            font-weight: bold;
        """)
        self.photo_label.setText(self.display_name[:2].upper() if self.display_name else "?")
        layout.addWidget(self.photo_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Name
        name_label = QLabel(self.display_name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        name_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #1d2939; background: transparent;")
        layout.addWidget(name_label)

        # Courses count badge
        courses_count = instructor.get("courses_count", "0")
        count_label = QLabel(f"{courses_count} courses")
        count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_label.setStyleSheet("""
            font-size: 11px;
            color: #1976d2;
            background: #e3f2fd;
            border-radius: 10px;
            padding: 3px 10px;
            font-weight: 500;
        """)
        count_label.setFixedHeight(22)
        layout.addWidget(count_label, alignment=Qt.AlignmentFlag.AlignCenter)

    def _load_photo(self, url: str, net_manager: QNetworkAccessManager):
        if not url:
            return
        request = QNetworkRequest(QUrl(url))
        reply = net_manager.get(request)
        reply.finished.connect(lambda: self._on_photo_loaded(reply))

    def _on_photo_loaded(self, reply: QNetworkReply):
        if reply.error() == QNetworkReply.NetworkError.NoError:
            pixmap = QPixmap()
            pixmap.loadFromData(reply.readAll())
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    QSize(100, 100),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = (scaled.width() - 100) // 2
                y = (scaled.height() - 100) // 2
                cropped = scaled.copy(x, y, 100, 100)
                self.photo_label.setPixmap(cropped)
                self.photo_label.setStyleSheet("border-radius: 50px;")
        reply.deleteLater()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.instructor_id, self.display_name)
        super().mousePressEvent(event)
