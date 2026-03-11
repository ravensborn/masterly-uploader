import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QWidget, QFileDialog, QGraphicsDropShadowEffect,
)


class AssignRow(QFrame):
    def __init__(self, lesson_id: int, lesson_title: str, parent=None):
        super().__init__(parent)
        self.lesson_id = lesson_id
        self.lesson_title = lesson_title
        self.file_path = ""

        self.setStyleSheet("""
            AssignRow {
                background: #ffffff;
                border: 1px solid #e4e7ec;
                border-radius: 10px;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(6)
        shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 15))
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        title = QLabel(lesson_title)
        title.setStyleSheet("font-size: 13px; font-weight: 600; color: #1d2939; background: transparent;")
        title.setWordWrap(True)
        layout.addWidget(title, stretch=1)

        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("font-size: 11px; color: #98a2b3; background: transparent;")
        self.file_label.setMinimumWidth(150)
        layout.addWidget(self.file_label)

        browse_btn = QPushButton("Browse")
        browse_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        browse_btn.setFixedSize(70, 30)
        browse_btn.setStyleSheet("""
            QPushButton {
                background: #f2f4f7; border: 1px solid #d0d5dd;
                border-radius: 6px; color: #344054; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background: #e4e7ec; }
        """)
        browse_btn.clicked.connect(self._browse)
        layout.addWidget(browse_btn)

    def _browse(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"Select Video for: {self.lesson_title}", "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.webm *.flv);;All Files (*)",
        )
        if file_path:
            self.file_path = file_path
            self.file_label.setText(os.path.basename(file_path))
            self.file_label.setStyleSheet("font-size: 11px; color: #027a48; font-weight: 500; background: transparent;")
            self.file_label.setToolTip(file_path)


class AssignDialog(QDialog):
    """Dialog to assign a source video file to each selected lesson."""

    def __init__(self, lessons: list[dict], parent=None):
        """lessons: list of {lesson_id, lesson_title, course_storage_path, expected_qualities}"""
        super().__init__(parent)
        self.setWindowTitle("Assign Videos")
        self.setMinimumSize(650, 400)
        self.resize(750, 500)
        self.setStyleSheet("background: #f0f2f5;")

        self.lessons = lessons
        self.result_map: dict[int, str] = {}  # lesson_id -> file_path

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = QLabel("Assign a video file to each lesson")
        header.setStyleSheet("font-size: 18px; font-weight: 700; color: #101828; background: transparent;")
        layout.addWidget(header)

        hint = QLabel("Each lesson will be encoded to 720p and 1080p, then uploaded to R2.")
        hint.setStyleSheet("font-size: 12px; color: #667085; background: transparent;")
        layout.addWidget(hint)

        # Bulk assign button
        bulk_row = QHBoxLayout()
        bulk_row.addStretch()
        bulk_btn = QPushButton("Assign same file to all")
        bulk_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        bulk_btn.setFixedHeight(32)
        bulk_btn.setStyleSheet("""
            QPushButton {
                background: #e3f2fd; border: none; border-radius: 6px;
                color: #1565c0; font-size: 12px; font-weight: 600; padding: 0 16px;
            }
            QPushButton:hover { background: #bbdefb; }
        """)
        bulk_btn.clicked.connect(self._bulk_assign)
        bulk_row.addWidget(bulk_btn)
        layout.addLayout(bulk_row)

        # Scroll area for rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        self.rows_layout = QVBoxLayout(container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(8)
        self.rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.rows: list[AssignRow] = []
        for lesson in self.lessons:
            row = AssignRow(lesson["lesson_id"], lesson["lesson_title"], container)
            self.rows.append(row)
            self.rows_layout.addWidget(row)

        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.setFixedSize(90, 38)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #ffffff; border: 1px solid #d0d5dd;
                border-radius: 8px; color: #344054; font-size: 13px; font-weight: 600;
            }
            QPushButton:hover { background: #f9fafb; }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self.start_btn = QPushButton("Start Processing")
        self.start_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.start_btn.setFixedSize(150, 38)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: #1976d2; border: none; border-radius: 8px;
                color: #ffffff; font-size: 13px; font-weight: 600;
            }
            QPushButton:hover { background: #1565c0; }
        """)
        self.start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self.start_btn)

        layout.addLayout(btn_row)

    def _bulk_assign(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video for all lessons", "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.webm *.flv);;All Files (*)",
        )
        if file_path:
            for row in self.rows:
                row.file_path = file_path
                row.file_label.setText(os.path.basename(file_path))
                row.file_label.setStyleSheet("font-size: 11px; color: #027a48; font-weight: 500; background: transparent;")
                row.file_label.setToolTip(file_path)

    def _on_start(self):
        # Check all have files assigned
        missing = [r for r in self.rows if not r.file_path]
        if missing:
            titles = ", ".join(r.lesson_title for r in missing[:3])
            if len(missing) > 3:
                titles += f" and {len(missing) - 3} more"
            self.start_btn.setText("Missing files!")
            self.start_btn.setStyleSheet("""
                QPushButton {
                    background: #b42318; border: none; border-radius: 8px;
                    color: #ffffff; font-size: 13px; font-weight: 600;
                }
            """)
            # Reset after a moment
            from PySide6.QtCore import QTimer
            QTimer.singleShot(2000, lambda: (
                self.start_btn.setText("Start Processing"),
                self.start_btn.setStyleSheet("""
                    QPushButton {
                        background: #1976d2; border: none; border-radius: 8px;
                        color: #ffffff; font-size: 13px; font-weight: 600;
                    }
                    QPushButton:hover { background: #1565c0; }
                """),
            ))
            return

        self.result_map = {row.lesson_id: row.file_path for row in self.rows}
        self.accept()
