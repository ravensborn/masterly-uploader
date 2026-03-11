import os

from PySide6.QtCore import Qt, QTimer
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
                border: 1.5px solid #f1f5f9;
                border-radius: 12px;
            }
            AssignRow:hover {
                border-color: #e2e8f0;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8)
        shadow.setOffset(0, 1)
        shadow.setColor(QColor(15, 23, 42, 10))
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        title = QLabel(lesson_title)
        title.setStyleSheet("font-size: 13px; font-weight: 600; color: #1e293b; background: transparent;")
        title.setWordWrap(True)
        layout.addWidget(title, stretch=1)

        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("font-size: 12px; color: #94a3b8; background: transparent;")
        self.file_label.setMinimumWidth(160)
        layout.addWidget(self.file_label)

        browse_btn = QPushButton("Browse")
        browse_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        browse_btn.setFixedSize(80, 32)
        browse_btn.setStyleSheet("""
            QPushButton {
                background: #f8fafc; border: 1.5px solid #e2e8f0;
                border-radius: 8px; color: #475569; font-size: 12px; font-weight: 600;
            }
            QPushButton:hover { background: #f1f5f9; border-color: #cbd5e1; }
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
            self.file_label.setStyleSheet("font-size: 12px; color: #059669; font-weight: 500; background: transparent;")
            self.file_label.setToolTip(file_path)


class AssignDialog(QDialog):
    """Dialog to assign a source video file to each selected lesson."""

    def __init__(self, lessons: list[dict], parent=None):
        """lessons: list of {lesson_id, lesson_title, course_storage_path, expected_qualities}"""
        super().__init__(parent)
        self.setWindowTitle("Assign Videos")
        self.setMinimumSize(700, 440)
        self.resize(800, 540)
        self.setStyleSheet("background: #f8fafc;")

        self.lessons = lessons
        self.result_map: dict[int, str] = {}  # lesson_id -> file_path

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(0)

        header = QLabel("Assign a video file to each lesson")
        header.setStyleSheet("font-size: 20px; font-weight: 700; color: #0f172a; background: transparent;")
        layout.addWidget(header)

        layout.addSpacing(4)

        hint = QLabel("Each lesson will be encoded to 720p and 1080p, then uploaded to R2.")
        hint.setStyleSheet("font-size: 13px; color: #64748b; background: transparent;")
        layout.addWidget(hint)

        layout.addSpacing(20)

        # Bulk assign button
        bulk_row = QHBoxLayout()
        bulk_row.addStretch()
        bulk_btn = QPushButton("Assign same file to all")
        bulk_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        bulk_btn.setFixedHeight(34)
        bulk_btn.setStyleSheet("""
            QPushButton {
                background: #eff6ff; border: none; border-radius: 8px;
                color: #2563eb; font-size: 12px; font-weight: 600; padding: 0 18px;
            }
            QPushButton:hover { background: #dbeafe; }
        """)
        bulk_btn.clicked.connect(self._bulk_assign)
        bulk_row.addWidget(bulk_btn)
        layout.addLayout(bulk_row)

        layout.addSpacing(16)

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

        layout.addSpacing(20)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.setSpacing(12)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.setFixedSize(100, 40)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #ffffff; border: 1.5px solid #e2e8f0;
                border-radius: 10px; color: #475569; font-size: 13px; font-weight: 600;
            }
            QPushButton:hover { background: #f8fafc; border-color: #cbd5e1; }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self.start_btn = QPushButton("Start Processing")
        self.start_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.start_btn.setFixedSize(160, 40)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6; border: none; border-radius: 10px;
                color: #ffffff; font-size: 13px; font-weight: 600;
            }
            QPushButton:hover { background: #2563eb; }
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
                row.file_label.setStyleSheet("font-size: 12px; color: #059669; font-weight: 500; background: transparent;")
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
                    background: #ef4444; border: none; border-radius: 10px;
                    color: #ffffff; font-size: 13px; font-weight: 600;
                }
            """)
            # Reset after a moment
            QTimer.singleShot(2000, lambda: (
                self.start_btn.setText("Start Processing"),
                self.start_btn.setStyleSheet("""
                    QPushButton {
                        background: #3b82f6; border: none; border-radius: 10px;
                        color: #ffffff; font-size: 13px; font-weight: 600;
                    }
                    QPushButton:hover { background: #2563eb; }
                """),
            ))
            return

        self.result_map = {row.lesson_id: row.file_path for row in self.rows}
        self.accept()
