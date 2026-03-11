from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QScrollArea, QFrame, QWidget, QGraphicsDropShadowEffect,
)

from ui.video_processor import ProcessingTask, ProcessingWorker


class TaskRow(QFrame):
    def __init__(self, task: ProcessingTask, parent=None):
        super().__init__(parent)
        self.task = task
        self.setStyleSheet("""
            TaskRow {
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Title
        title = QLabel(task.lesson_title)
        title.setStyleSheet("font-size: 13px; font-weight: 600; color: #1d2939; background: transparent;")
        title.setWordWrap(True)
        layout.addWidget(title)

        # Per-quality rows
        self.quality_rows = {}
        for quality in task.qualities:
            row = QHBoxLayout()
            row.setSpacing(10)

            q_label = QLabel(quality)
            q_label.setFixedWidth(50)
            q_label.setStyleSheet("font-size: 11px; font-weight: 700; color: #1976d2; background: transparent;")
            row.addWidget(q_label)

            status_label = QLabel("Waiting...")
            status_label.setFixedWidth(100)
            status_label.setStyleSheet("font-size: 11px; color: #667085; background: transparent;")
            row.addWidget(status_label)

            progress_bar = QProgressBar()
            progress_bar.setFixedHeight(14)
            progress_bar.setRange(0, 100)
            progress_bar.setValue(0)
            progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #e4e7ec;
                    border-radius: 7px;
                    background: #f2f4f7;
                    text-align: center;
                    font-size: 9px;
                    color: #344054;
                }
                QProgressBar::chunk {
                    border-radius: 6px;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #1976d2, stop:1 #42a5f5);
                }
            """)
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
            row["status"].setStyleSheet("font-size: 11px; color: #027a48; font-weight: 600; background: transparent;")
            row["progress"].setStyleSheet("""
                QProgressBar {
                    border: 1px solid #d1fadf;
                    border-radius: 7px;
                    background: #ecfdf3;
                    text-align: center;
                    font-size: 9px;
                    color: #027a48;
                }
                QProgressBar::chunk {
                    border-radius: 6px;
                    background: #12b76a;
                }
            """)
        elif stage == "error":
            row["status"].setStyleSheet("font-size: 11px; color: #b42318; font-weight: 600; background: transparent;")

    def set_error(self, quality: str, message: str):
        row = self.quality_rows.get(quality)
        if row:
            row["status"].setText("Error")
            row["status"].setToolTip(message)
            row["status"].setStyleSheet("font-size: 11px; color: #b42318; font-weight: 600; background: transparent;")


class ProcessDialog(QDialog):
    def __init__(self, tasks: list[ProcessingTask], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Processing Videos")
        self.setMinimumSize(600, 400)
        self.resize(700, 500)
        self.setStyleSheet("background: #f0f2f5;")

        self.tasks = tasks
        self.total_steps = sum(len(t.qualities) for t in tasks)
        self.completed_steps = 0

        self._setup_ui()
        self._start()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header
        header = QLabel("Processing Videos")
        header.setStyleSheet("font-size: 20px; font-weight: 700; color: #101828; background: transparent;")
        layout.addWidget(header)

        # Overall progress
        overall_row = QHBoxLayout()
        self.overall_label = QLabel(f"0 / {self.total_steps} tasks complete")
        self.overall_label.setStyleSheet("font-size: 12px; color: #667085; background: transparent;")
        overall_row.addWidget(self.overall_label)
        overall_row.addStretch()
        layout.addLayout(overall_row)

        self.overall_progress = QProgressBar()
        self.overall_progress.setFixedHeight(20)
        self.overall_progress.setRange(0, self.total_steps)
        self.overall_progress.setValue(0)
        self.overall_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #d0d5dd;
                border-radius: 10px;
                background: #f2f4f7;
                text-align: center;
                font-size: 11px;
                color: #344054;
            }
            QProgressBar::chunk {
                border-radius: 9px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1976d2, stop:1 #42a5f5);
            }
        """)
        layout.addWidget(self.overall_progress)

        # Scroll area for task rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        self.tasks_layout = QVBoxLayout(container)
        self.tasks_layout.setContentsMargins(0, 0, 0, 0)
        self.tasks_layout.setSpacing(10)
        self.tasks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.task_rows: list[TaskRow] = []
        for task in self.tasks:
            row = TaskRow(task, container)
            self.task_rows.append(row)
            self.tasks_layout.addWidget(row)

        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        # Cancel button
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedSize(100, 36)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: #ffffff; border: 1px solid #d0d5dd;
                border-radius: 8px; color: #344054; font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #fef3f2; border-color: #b42318; color: #b42318;
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
                background: #ecfdf3; border: 1px solid #12b76a;
                border-radius: 8px; color: #027a48; font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #d1fadf;
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
