from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QScrollArea, QFrame, QWidget, QGraphicsDropShadowEffect,
)

from ui.video_processor import ProcessingTask, ProcessingWorker

PROGRESS_STYLE = """
    QProgressBar {
        border: 1.5px solid #e2e8f0;
        border-radius: 8px;
        background: #f1f5f9;
        text-align: center;
        font-size: 10px;
        color: #475569;
    }
    QProgressBar::chunk {
        border-radius: 7px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #3b82f6, stop:1 #60a5fa);
    }
"""

PROGRESS_DONE_STYLE = """
    QProgressBar {
        border: 1.5px solid #bbf7d0;
        border-radius: 8px;
        background: #f0fdf4;
        text-align: center;
        font-size: 10px;
        color: #059669;
    }
    QProgressBar::chunk {
        border-radius: 7px;
        background: #10b981;
    }
"""


class TaskRow(QFrame):
    def __init__(self, task: ProcessingTask, parent=None):
        super().__init__(parent)
        self.task = task
        self.setStyleSheet("""
            TaskRow {
                background: #ffffff;
                border: 1.5px solid #f1f5f9;
                border-radius: 14px;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(15, 23, 42, 12))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel(task.lesson_title)
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #0f172a; background: transparent;")
        title.setWordWrap(True)
        layout.addWidget(title)

        # Per-quality rows
        self.quality_rows = {}
        for quality in task.qualities:
            row = QHBoxLayout()
            row.setSpacing(12)

            q_label = QLabel(quality)
            q_label.setFixedWidth(52)
            q_label.setStyleSheet("font-size: 12px; font-weight: 700; color: #3b82f6; background: transparent;")
            row.addWidget(q_label)

            status_label = QLabel("Waiting...")
            status_label.setFixedWidth(100)
            status_label.setStyleSheet("font-size: 12px; color: #94a3b8; background: transparent;")
            row.addWidget(status_label)

            progress_bar = QProgressBar()
            progress_bar.setFixedHeight(16)
            progress_bar.setRange(0, 100)
            progress_bar.setValue(0)
            progress_bar.setStyleSheet(PROGRESS_STYLE)
            row.addWidget(progress_bar, stretch=1)

            self.quality_rows[quality] = {
                "status": status_label,
                "progress": progress_bar,
            }
            layout.addLayout(row)

    def update_progress(self, quality: str, stage: str, pct: int):
        row = self.quality_rows.get(quality)
        if not row:
            return

        stage_labels = {
            "encoding": "Encoding...",
            "deleting": "Deleting old...",
            "uploading": "Uploading...",
            "done": "Done",
            "error": "Error",
        }
        row["status"].setText(stage_labels.get(stage, stage))
        row["progress"].setValue(pct)

        if stage == "done":
            row["status"].setStyleSheet("font-size: 12px; color: #059669; font-weight: 600; background: transparent;")
            row["progress"].setStyleSheet(PROGRESS_DONE_STYLE)
        elif stage == "error":
            row["status"].setStyleSheet("font-size: 12px; color: #ef4444; font-weight: 600; background: transparent;")

    def set_error(self, quality: str, message: str):
        row = self.quality_rows.get(quality)
        if row:
            row["status"].setText("Error")
            row["status"].setToolTip(message)
            row["status"].setStyleSheet("font-size: 12px; color: #ef4444; font-weight: 600; background: transparent;")


class ProcessDialog(QDialog):
    def __init__(self, tasks: list[ProcessingTask], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Processing Videos")
        self.setMinimumSize(650, 440)
        self.resize(760, 540)
        self.setStyleSheet("background: #f8fafc;")

        self.tasks = tasks
        self.total_steps = sum(len(t.qualities) for t in tasks)
        self.completed_steps = 0

        self._setup_ui()
        self._start()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(0)

        # Header
        header = QLabel("Processing Videos")
        header.setStyleSheet("font-size: 22px; font-weight: 700; color: #0f172a; background: transparent;")
        layout.addWidget(header)

        layout.addSpacing(20)

        # Overall progress
        self.overall_label = QLabel(f"0 / {self.total_steps} tasks complete")
        self.overall_label.setStyleSheet("font-size: 13px; color: #64748b; background: transparent;")
        layout.addWidget(self.overall_label)

        layout.addSpacing(8)

        self.overall_progress = QProgressBar()
        self.overall_progress.setFixedHeight(22)
        self.overall_progress.setRange(0, self.total_steps)
        self.overall_progress.setValue(0)
        self.overall_progress.setStyleSheet("""
            QProgressBar {
                border: 1.5px solid #e2e8f0;
                border-radius: 11px;
                background: #f1f5f9;
                text-align: center;
                font-size: 11px;
                color: #475569;
            }
            QProgressBar::chunk {
                border-radius: 10px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3b82f6, stop:1 #60a5fa);
            }
        """)
        layout.addWidget(self.overall_progress)

        layout.addSpacing(24)

        # Scroll area for task rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        self.tasks_layout = QVBoxLayout(container)
        self.tasks_layout.setContentsMargins(0, 0, 0, 0)
        self.tasks_layout.setSpacing(12)
        self.tasks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.task_rows: list[TaskRow] = []
        for task in self.tasks:
            row = TaskRow(task, container)
            self.task_rows.append(row)
            self.tasks_layout.addWidget(row)

        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        layout.addSpacing(20)

        # Cancel button
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.cancel_btn.setFixedSize(110, 40)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: #ffffff; border: 1.5px solid #e2e8f0;
                border-radius: 10px; color: #475569; font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #fef2f2; border-color: #fca5a5; color: #ef4444;
            }
        """)
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self.cancel_btn)

        layout.addLayout(btn_row)

    def _start(self):
        self.worker = ProcessingWorker(self.tasks, self)
        self.worker.task_progress.connect(self._on_task_progress)
        self.worker.task_error.connect(self._on_task_error)
        self.worker.all_done.connect(self._on_all_done)
        self.worker.start()

    def _on_task_progress(self, task_idx: int, quality: str, stage: str, pct: int):
        if 0 <= task_idx < len(self.task_rows):
            self.task_rows[task_idx].update_progress(quality, stage, pct)

        if stage == "done":
            self.completed_steps += 1
            self.overall_progress.setValue(self.completed_steps)
            self.overall_label.setText(f"{self.completed_steps} / {self.total_steps} tasks complete")

    def _on_task_error(self, task_idx: int, quality: str, message: str):
        if 0 <= task_idx < len(self.task_rows):
            self.task_rows[task_idx].set_error(quality, message)
        self.completed_steps += 1
        self.overall_progress.setValue(self.completed_steps)
        self.overall_label.setText(f"{self.completed_steps} / {self.total_steps} tasks complete")

    def _on_all_done(self):
        self.cancel_btn.setText("Close")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: #f0fdf4; border: 1.5px solid #86efac;
                border-radius: 10px; color: #059669; font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #dcfce7;
            }
        """)
        self.overall_label.setText(f"All {self.total_steps} tasks complete")

    def _on_cancel(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
        self.accept()

    def closeEvent(self, event):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
        super().closeEvent(event)
