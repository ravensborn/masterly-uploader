import subprocess
import shutil
import sys

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QCursor, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QPushButton, QGraphicsDropShadowEffect,
    QCheckBox, QFileDialog, QMenu,
)

from ui.r2_client import R2Client
from ui.video_processor import ProcessingTask
from ui.process_dialog import ProcessDialog
from ui.assign_dialog import AssignDialog

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

CHECKBOX_STYLE = """
    QCheckBox {
        background: transparent;
        spacing: 0px;
    }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border: 2px solid #cbd5e1;
        border-radius: 5px;
        background: #ffffff;
    }
    QCheckBox::indicator:hover {
        border-color: #3b82f6;
    }
    QCheckBox::indicator:checked {
        background: #3b82f6;
        border-color: #3b82f6;
    }
    QCheckBox::indicator:indeterminate {
        background: #93c5fd;
        border-color: #3b82f6;
    }
"""


def _localized(value):
    if isinstance(value, dict):
        return value.get("ku-b", value.get("ku", value.get("en", str(value))))
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value)


class LessonItem(QFrame):
    """A single lesson row with checkbox."""
    play_requested = Signal(str, str)  # storage_path, filename
    selection_changed = Signal()

    def __init__(self, lesson: dict, course_storage_path: str, parent=None):
        super().__init__(parent)
        self.lesson = lesson
        self.lesson_id = lesson.get("id", 0)
        self.lesson_title = _localized(lesson.get("title", ""))
        self.course_storage_path = course_storage_path
        self.videos = lesson.get("videos", [])
        self.expected_qualities = [str(q) for q in lesson.get("expected_qualities", ["720p", "1080p"])]
        self.is_uploaded = (
            len(self.videos) > 0
            and all(v.get("is_uploaded", False) for v in self.videos)
        )

        if self.is_uploaded:
            border_color = "#bbf7d0"
            hover_border = "#86efac"
            bg = "#f0fdf4"
            hover_bg = "#ecfdf5"
        else:
            border_color = "#fecaca"
            hover_border = "#f87171"
            bg = "#fef2f2"
            hover_bg = "#fee2e2"

        self.setStyleSheet(f"""
            LessonItem {{
                background: {bg};
                border: 1.5px solid {border_color};
                border-radius: 10px;
            }}
            LessonItem:hover {{
                border: 1.5px solid {hover_border};
                background: {hover_bg};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        # Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setStyleSheet(CHECKBOX_STYLE)
        self.checkbox.stateChanged.connect(lambda: self.selection_changed.emit())
        layout.addWidget(self.checkbox)

        # Position number
        position = lesson.get("position", 0)
        pos_label = QLabel(str(position))
        pos_label.setFixedSize(30, 30)
        pos_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pos_label.setStyleSheet("""
            background: #eff6ff;
            color: #2563eb;
            border-radius: 15px;
            font-size: 12px;
            font-weight: 700;
        """)
        layout.addWidget(pos_label)

        # Title
        title_label = QLabel(self.lesson_title)
        title_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #1e293b; background: transparent;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label, stretch=1)

        # Quality badges
        uploaded_qualities = {
            v.get("quality") for v in self.videos if v.get("is_uploaded", False)
        }
        for q in self.expected_qualities:
            q_label = QLabel(str(q))
            if str(q) in uploaded_qualities:
                q_label.setStyleSheet("""
                    font-size: 11px; color: #059669; background: #ecfdf5;
                    border-radius: 10px; padding: 3px 8px; font-weight: 600;
                """)
            else:
                q_label.setStyleSheet("""
                    font-size: 11px; color: #dc2626; background: #fef2f2;
                    border-radius: 10px; padding: 3px 8px; font-weight: 600;
                """)
            q_label.setFixedHeight(22)
            layout.addWidget(q_label)

        # Play dropdown button
        self.play_btn = QPushButton("Play \u25bc")
        self.play_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.play_btn.setFixedSize(70, 28)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background: #eff6ff; border: none; border-radius: 8px;
                color: #2563eb; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background: #dbeafe; }
            QPushButton::menu-indicator { image: none; }
        """)
        self.play_menu = QMenu(self.play_btn)
        self.play_menu.setStyleSheet("""
            QMenu {
                background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px;
                padding: 4px 0;
            }
            QMenu::item {
                padding: 6px 16px; font-size: 12px; color: #1e293b;
            }
            QMenu::item:selected {
                background: #eff6ff; color: #2563eb;
            }
        """)
        for v in self.videos:
            quality = v.get("quality", "unknown")
            action = self.play_menu.addAction(quality)
            action.triggered.connect(lambda checked, vid=v: self.play_requested.emit(
                vid.get("storage_path", ""), vid.get("file_path", "")
            ))
        self.play_btn.setMenu(self.play_menu)
        self.play_btn.setVisible(len(self.videos) > 0)
        layout.addWidget(self.play_btn)

    def is_checked(self):
        return self.checkbox.isChecked()

    def set_checked(self, checked: bool):
        self.checkbox.setChecked(checked)


class LessonGroupWidget(QFrame):
    """A collapsible group of lessons."""
    play_requested = Signal(str, str)
    selection_changed = Signal()

    def __init__(self, group: dict, course_storage_path: str, parent=None):
        super().__init__(parent)
        self._expanded = True
        self.course_storage_path = course_storage_path
        self.setStyleSheet("""
            LessonGroupWidget {
                background: #ffffff;
                border: 1.5px solid #f1f5f9;
                border-radius: 16px;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(15, 23, 42, 15))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # Group header
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        # Select all checkbox
        self.select_all_cb = QCheckBox()
        self.select_all_cb.setStyleSheet(CHECKBOX_STYLE)
        self.select_all_cb.stateChanged.connect(self._on_select_all)
        header_row.addWidget(self.select_all_cb)

        title = _localized(group.get("title", ""))
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #0f172a; background: transparent;")
        title_label.setWordWrap(True)
        header_row.addWidget(title_label, stretch=1)

        lessons = group.get("lessons", [])
        count_label = QLabel(f"{len(lessons)} lesson{'s' if len(lessons) != 1 else ''}")
        count_label.setStyleSheet("""
            font-size: 12px; color: #3b82f6; background: #eff6ff;
            border-radius: 12px; padding: 4px 12px; font-weight: 500;
        """)
        count_label.setFixedHeight(26)
        header_row.addWidget(count_label)

        self.toggle_btn = QPushButton("\u2212")
        self.toggle_btn.setFixedSize(32, 32)
        self.toggle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background: #f8fafc; border: 1.5px solid #e2e8f0;
                border-radius: 16px; font-size: 16px; font-weight: bold; color: #64748b;
            }
            QPushButton:hover { background: #f1f5f9; border-color: #cbd5e1; }
        """)
        self.toggle_btn.clicked.connect(self._toggle)
        header_row.addWidget(self.toggle_btn)

        layout.addLayout(header_row)

        # Lessons container
        self.lessons_container = QWidget()
        self.lessons_container.setStyleSheet("background: transparent;")
        lessons_layout = QVBoxLayout(self.lessons_container)
        lessons_layout.setContentsMargins(0, 4, 0, 0)
        lessons_layout.setSpacing(6)

        self.lesson_items: list[LessonItem] = []
        sorted_lessons = sorted(lessons, key=lambda l: l.get("position", 0))
        for lesson in sorted_lessons:
            item = LessonItem(lesson, course_storage_path, self.lessons_container)
            item.play_requested.connect(self.play_requested.emit)
            item.selection_changed.connect(self._on_lesson_selection_changed)
            item.selection_changed.connect(self.selection_changed.emit)
            self.lesson_items.append(item)
            lessons_layout.addWidget(item)

        layout.addWidget(self.lessons_container)

    def _toggle(self):
        self._expanded = not self._expanded
        self.lessons_container.setVisible(self._expanded)
        self.toggle_btn.setText("\u2212" if self._expanded else "+")

    def _on_select_all(self, state):
        checked = Qt.CheckState(state) == Qt.CheckState.Checked
        for item in self.lesson_items:
            item.set_checked(checked)

    def _on_lesson_selection_changed(self):
        all_checked = all(item.is_checked() for item in self.lesson_items)
        none_checked = not any(item.is_checked() for item in self.lesson_items)
        self.select_all_cb.blockSignals(True)
        if all_checked:
            self.select_all_cb.setCheckState(Qt.CheckState.Checked)
        elif none_checked:
            self.select_all_cb.setCheckState(Qt.CheckState.Unchecked)
        else:
            self.select_all_cb.setCheckState(Qt.CheckState.PartiallyChecked)
        self.select_all_cb.blockSignals(False)

    def get_selected_lessons(self) -> list[LessonItem]:
        return [item for item in self.lesson_items if item.is_checked()]


class CourseDetailPage(QWidget):
    back_requested = Signal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.r2_client = R2Client(self)
        self.r2_client.url_ready.connect(self._on_url_ready)
        self.r2_client.error.connect(self._on_r2_error)
        self._groups: list[LessonGroupWidget] = []
        self._course_storage_path = ""
        self._setup_ui()
        self.api_client.course_detail_loaded.connect(self._on_detail_loaded)
        self.api_client.error.connect(self._on_error)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 40, 48, 24)
        layout.setSpacing(0)

        # Header row
        header_row = QHBoxLayout()
        header_row.setSpacing(16)

        self.back_btn = QPushButton("\u2190  Back")
        self.back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.back_btn.setFixedHeight(38)
        self.back_btn.setStyleSheet(BACK_BTN_STYLE)
        self.back_btn.clicked.connect(self.back_requested.emit)
        header_row.addWidget(self.back_btn)

        self.header = QLabel("Course")
        self.header.setStyleSheet("font-size: 28px; font-weight: 700; color: #0f172a; background: transparent;")
        header_row.addWidget(self.header)
        header_row.addStretch()

        layout.addLayout(header_row)

        layout.addSpacing(24)

        # Status
        self.status_label = QLabel("Loading...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; color: #94a3b8; padding: 60px 0; background: transparent;")
        layout.addWidget(self.status_label)

        # Scroll area for groups
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(16)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.content)

        layout.addWidget(self.scroll_area, stretch=1)

        layout.addSpacing(16)

        # Action bar (hidden until lessons selected)
        self.action_bar = QFrame()
        self.action_bar.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1.5px solid #e2e8f0;
                border-radius: 14px;
            }
        """)
        action_shadow = QGraphicsDropShadowEffect(self.action_bar)
        action_shadow.setBlurRadius(24)
        action_shadow.setOffset(0, -4)
        action_shadow.setColor(QColor(15, 23, 42, 20))
        self.action_bar.setGraphicsEffect(action_shadow)

        action_layout = QHBoxLayout(self.action_bar)
        action_layout.setContentsMargins(24, 14, 24, 14)
        action_layout.setSpacing(16)

        self.selection_label = QLabel("0 lessons selected")
        self.selection_label.setStyleSheet("font-size: 14px; color: #475569; font-weight: 500; background: transparent;")
        action_layout.addWidget(self.selection_label)

        action_layout.addStretch()

        self.process_btn = QPushButton("Assign Videos & Process")
        self.process_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.process_btn.setFixedHeight(40)
        self.process_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6; border: none; border-radius: 10px;
                color: #ffffff; font-size: 13px; font-weight: 600;
                padding: 0 28px;
            }
            QPushButton:hover { background: #2563eb; }
        """)
        self.process_btn.clicked.connect(self._on_process_clicked)
        action_layout.addWidget(self.process_btn)

        self.action_bar.hide()
        layout.addWidget(self.action_bar)

    def load(self, course_id: int, course_title: str = ""):
        self._current_course_id = course_id
        self._current_course_title = course_title or self.header.text()
        # Clear previous
        self._groups.clear()
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.header.setText(course_title)
        self.status_label.setText("Loading course details...")
        self.status_label.setStyleSheet("font-size: 14px; color: #94a3b8; padding: 60px 0; background: transparent;")
        self.status_label.show()
        self.scroll_area.hide()
        self.action_bar.hide()
        self.api_client.fetch_course_detail(course_id)

    def _on_detail_loaded(self, data: dict):
        self._groups.clear()
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._course_storage_path = data.get("storage_path", "")

        lesson_groups = data.get("lesson_groups", [])
        if not lesson_groups:
            self.status_label.setText("No lesson groups found.")
            self.status_label.show()
            return

        self.status_label.hide()
        self.scroll_area.show()

        title = _localized(data.get("title", ""))
        if title:
            self.header.setText(title)

        sorted_groups = sorted(lesson_groups, key=lambda g: g.get("position", 0))
        for group in sorted_groups:
            widget = LessonGroupWidget(group, self._course_storage_path, self.content)
            widget.play_requested.connect(self._on_play_requested)
            widget.selection_changed.connect(self._update_action_bar)
            self._groups.append(widget)
            self.content_layout.addWidget(widget)

    def _update_action_bar(self):
        selected = self._get_selected_lessons()
        count = len(selected)
        if count > 0:
            self.selection_label.setText(f"{count} lesson{'s' if count != 1 else ''} selected")
            self.action_bar.show()
        else:
            self.action_bar.hide()

    def _get_selected_lessons(self) -> list[LessonItem]:
        selected = []
        for group in self._groups:
            selected.extend(group.get_selected_lessons())
        return selected

    def _on_process_clicked(self):
        selected = self._get_selected_lessons()
        if not selected:
            return

        # Build lesson info for the assign dialog
        lesson_infos = []
        for item in selected:
            lesson_infos.append({
                "lesson_id": item.lesson_id,
                "lesson_title": item.lesson_title,
                "course_storage_path": item.course_storage_path,
                "expected_qualities": item.expected_qualities,
            })

        assign = AssignDialog(lesson_infos, self)
        if assign.exec() != AssignDialog.DialogCode.Accepted:
            return

        tasks = []
        for item in selected:
            file_path = assign.result_map.get(item.lesson_id)
            if not file_path:
                continue
            qualities = item.expected_qualities if item.expected_qualities else ["720p", "1080p"]
            video_ids = {v.get("quality"): v.get("id") for v in item.videos if v.get("quality") and v.get("id")}
            task = ProcessingTask(
                lesson_id=item.lesson_id,
                lesson_title=item.lesson_title,
                source_file=file_path,
                course_storage_path=item.course_storage_path,
                qualities=qualities,
                video_ids=video_ids,
            )
            tasks.append(task)

        if tasks:
            dialog = ProcessDialog(
                tasks,
                api_base_url=self.api_client.base_url,
                api_auth_header=self.api_client._auth_header,
                parent=self,
            )
            dialog.exec()
            # Reload course data to reflect updated upload status
            self.load(self._current_course_id)

    def _on_play_requested(self, storage_path: str, filename: str):
        self.status_label.setText("Generating video URL...")
        self.status_label.setStyleSheet("font-size: 14px; color: #3b82f6; padding: 12px 0; background: transparent;")
        self.status_label.show()
        self.r2_client.generate_url(storage_path, filename)

    def _on_url_ready(self, url: str):
        self.status_label.hide()
        if shutil.which("vlc"):
            subprocess.Popen(["vlc", url])
        elif shutil.which("mpv"):
            subprocess.Popen(["mpv", url])
        elif sys.platform == "linux":
            subprocess.Popen(["xdg-open", url])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", url])
        else:
            QDesktopServices.openUrl(QUrl(url))

    def _on_r2_error(self, message: str):
        self.status_label.setText(f"Error: {message}")
        self.status_label.show()
        self.status_label.setStyleSheet("font-size: 14px; color: #ef4444; padding: 12px 0; background: transparent;")

    def _on_error(self, message: str):
        self.status_label.setText(f"Error: {message}")
        self.status_label.show()
        self.status_label.setStyleSheet("font-size: 14px; color: #ef4444; padding: 60px 0; background: transparent;")
