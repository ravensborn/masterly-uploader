from PySide6.QtCore import Qt, Signal, QSize, QUrl
from PySide6.QtGui import QPixmap, QCursor, QPainter, QPainterPath, QColor
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QGraphicsDropShadowEffect
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply


class InstructorCard(QFrame):
    clicked = Signal(int, str)  # instructor_id, display_name

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
            return value.get("ku-b", value.get("ku", value.get("en", str(value))))
        if isinstance(value, list):
            return str(value[0]) if value else ""
        return str(value)

    def _setup_style(self):
        self.setFixedSize(220, 280)
        self.setStyleSheet("""
            InstructorCard {
                background: #ffffff;
                border: 1.5px solid #f1f5f9;
                border-radius: 20px;
            }
            InstructorCard:hover {
                border: 1.5px solid #93c5fd;
                background: #fafbff;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(15, 23, 42, 20))
        self.setGraphicsEffect(shadow)

    def _setup_ui(self, instructor):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 28, 20, 24)

        # Photo placeholder
        self.photo_label = QLabel()
        self.photo_label.setFixedSize(96, 96)
        self.photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo_label.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #dbeafe, stop:1 #bfdbfe);
            border-radius: 48px;
            color: #2563eb;
            font-size: 28px;
            font-weight: bold;
        """)
        self.photo_label.setText(self.display_name[:2].upper() if self.display_name else "?")
        layout.addWidget(self.photo_label, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(4)

        # Name
        name_label = QLabel(self.display_name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        name_label.setStyleSheet("font-size: 15px; font-weight: 600; color: #0f172a; background: transparent;")
        layout.addWidget(name_label)

        # Courses count badge
        courses_count = instructor.get("courses_count", "0")
        count_label = QLabel(f"{courses_count} courses")
        count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_label.setStyleSheet("""
            font-size: 12px;
            color: #3b82f6;
            background: #eff6ff;
            border-radius: 12px;
            padding: 4px 14px;
            font-weight: 500;
        """)
        count_label.setFixedHeight(26)
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
                    QSize(96, 96),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = (scaled.width() - 96) // 2
                y = (scaled.height() - 96) // 2
                cropped = scaled.copy(x, y, 96, 96)

                # Make circular
                rounded = QPixmap(96, 96)
                rounded.fill(Qt.GlobalColor.transparent)
                painter = QPainter(rounded)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                path = QPainterPath()
                path.addEllipse(0, 0, 96, 96)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, cropped)
                painter.end()

                self.photo_label.setPixmap(rounded)
                self.photo_label.setStyleSheet("background: transparent;")
        reply.deleteLater()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.instructor_id, self.display_name)
        super().mousePressEvent(event)
