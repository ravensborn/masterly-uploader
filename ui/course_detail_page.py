import subprocess
import shutil
import sys

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QCursor, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QPushButton, QGraphicsDropShadowEffect,
    QCheckBox, QFileDialog,
)

from ui.r2_client import R2Client
from ui.video_processor import ProcessingTask
from ui.process_dialog import ProcessDialog
from ui.assign_dialog import AssignDialog


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
        self.setStyleSheet("""
            LessonItem {
                background: #ffffff;
                border: 1px solid #e4e7ec;
                border-radius: 8px;
            }
            LessonItem:hover {
                border: 1px solid #1976d2;
                background: #f5f9ff;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        # Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setStyleSheet("""
            QCheckBox {
                background: transparent;
                spacing: 4px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #98a2b3;
                border-radius: 4px;
                background: #ffffff;
            }
            QCheckBox::indicator:hover {
                border-color: #1976d2;
            }
            QCheckBox::indicator:checked {
                background: #1976d2;
                border-color: #1976d2;
                image: none;
            }
        """)
        self.checkbox.stateChanged.connect(lambda: self.selection_changed.emit())
        layout.addWidget(self.checkbox)

        # Position number
        position = lesson.get("position", 0)
        pos_label = QLabel(str(position))
        pos_label.setFixedSize(28, 28)
        pos_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pos_label.setStyleSheet("""
            background: #e3f2fd;
            color: #1565c0;
            border-radius: 14px;
            font-size: 12px;
            font-weight: 700;
        """)
        layout.addWidget(pos_label)

        # Title
        title_label = QLabel(self.lesson_title)
        title_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #1d2939; background: transparent;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label, stretch=1)

        # Videos count badge
        video_count = len(self.videos)
        if video_count > 0:
            badge = QLabel(f"{video_count} video{'s' if video_count != 1 else ''}")
            badge.setStyleSheet("""
                font-size: 10px; color: #667085; background: #f2f4f7;
                border-radius: 8px; padding: 2px 8px; font-weight: 500;
            """)
            badge.setFixedHeight(20)
            layout.addWidget(badge)

        # Quality badges
        existing = {v.get("quality") for v in self.videos}
        for q in self.expected_qualities:
            q_label = QLabel(str(q))
            if str(q) in existing:
                q_label.setStyleSheet("""
                    font-size: 10px; color: #027a48; background: #ecfdf3;
                    border-radius: 8px; padding: 2px 6px; font-weight: 600;
                """)
            else:
                q_label.setStyleSheet("""
                    font-size: 10px; color: #b42318; background: #fef3f2;
                    border-radius: 8px; padding: 2px 6px; font-weight: 600;
                """)
            q_label.setFixedHeight(20)
            layout.addWidget(q_label)

        # Play button
        play_btn = QPushButton("Play")
        play_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        play_btn.setFixedSize(50, 26)
        play_btn.setStyleSheet("""
            QPushButton {
                background: #e3f2fd; border: none; border-radius: 6px;
                color: #1565c0; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background: #bbdefb; }
        """)
        play_btn.clicked.connect(self._on_play)
        play_btn.setVisible(len(self.videos) > 0)
        layout.addWidget(play_btn)

    def _on_play(self):
        if not self.videos:
            return
        v = next((v for v in self.videos if v.get("quality") == "1080p"), self.videos[0])
        self.play_requested.emit(v.get("storage_path", ""), v.get("filename", ""))

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
                background: #f9fafb;
                border: 1px solid #e4e7ec;
                border-radius: 12px;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8)
        shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 15))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Group header
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        # Select all checkbox
        self.select_all_cb = QCheckBox()
        self.select_all_cb.setStyleSheet("""
            QCheckBox {
                background: transparent;
                spacing: 4px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #98a2b3;
                border-radius: 4px;
                background: #ffffff;
            }
            QCheckBox::indicator:hover {
                border-color: #1976d2;
            }
            QCheckBox::indicator:checked {
                background: #1976d2;
                border-color: #1976d2;
            }
            QCheckBox::indicator:indeterminate {
                background: #bbdefb;
                border-color: #1976d2;
            }
        """)
        self.select_all_cb.stateChanged.connect(self._on_select_all)
        header_row.addWidget(self.select_all_cb)

        position = group.get("position", 0)
        pos_label = QLabel(f"Group {position}")
        pos_label.setStyleSheet("font-size: 11px; color: #667085; font-weight: 600; background: transparent;")
        header_row.addWidget(pos_label)

        title = _localized(group.get("title", ""))
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #101828; background: transparent;")
        title_label.setWordWrap(True)
        header_row.addWidget(title_label, stretch=1)

        lessons = group.get("lessons", [])
        count_label = QLabel(f"{len(lessons)} lesson{'s' if len(lessons) != 1 else ''}")
        count_label.setStyleSheet("""
            font-size: 11px; color: #1976d2; background: #e3f2fd;
            border-radius: 10px; padding: 3px 10px; font-weight: 500;
        """)
        count_label.setFixedHeight(22)
        header_row.addWidget(count_label)

        self.toggle_btn = QPushButton("-")
        self.toggle_btn.setFixedSize(28, 28)
        self.toggle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background: #ffffff; border: 1px solid #d0d5dd;
                border-radius: 14px; font-size: 14px; font-weight: bold; color: #344054;
            }
            QPushButton:hover { background: #f2f4f7; }
        """)
        self.toggle_btn.clicked.connect(self._toggle)
        header_row.addWidget(self.toggle_btn)

        layout.addLayout(header_row)

        # Lessons container
        self.lessons_container = QWidget()
        lessons_layout = QVBoxLayout(self.lessons_container)
        lessons_layout.setContentsMargins(0, 0, 0, 0)
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
        self.toggle_btn.setText("-" if self._expanded else "+")

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
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        # Header row
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        self.back_btn = QPushButton("Back")
        self.back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.back_btn.setFixedHeight(36)
        self.back_btn.setStyleSheet("""
            QPushButton {
                background: #ffffff; border: 1px solid #d0d5dd;
                border-radius: 8px; color: #344054; font-size: 13px;
                font-weight: 600; padding: 0 16px;
            }
            QPushButton:hover {
                background: #f9fafb; border-color: #1976d2; color: #1976d2;
            }
        """)
        self.back_btn.clicked.connect(self.back_requested.emit)
        header_row.addWidget(self.back_btn)

        self.header = QLabel("Course")
        self.header.setStyleSheet("font-size: 26px; font-weight: 700; color: #101828; background: transparent;")
        header_row.addWidget(self.header)
        header_row.addStretch()

        layout.addLayout(header_row)

        # Status
        self.status_label = QLabel("Loading...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; color: #667085; padding: 40px; background: transparent;")
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

        # Action bar (hidden until lessons selected)
        self.action_bar = QFrame()
        self.action_bar.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #e4e7ec;
                border-radius: 12px;
            }
        """)
        action_shadow = QGraphicsDropShadowEffect(self.action_bar)
        action_shadow.setBlurRadius(16)
        action_shadow.setOffset(0, -2)
        action_shadow.setColor(QColor(0, 0, 0, 30))
        self.action_bar.setGraphicsEffect(action_shadow)

        action_layout = QHBoxLayout(self.action_bar)
        action_layout.setContentsMargins(20, 12, 20, 12)
        action_layout.setSpacing(16)

        self.selection_label = QLabel("0 lessons selected")
        self.selection_label.setStyleSheet("font-size: 13px; color: #344054; font-weight: 500; background: transparent;")
        action_layout.addWidget(self.selection_label)

        action_layout.addStretch()

        self.process_btn = QPushButton("Assign Videos & Process")
        self.process_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.process_btn.setFixedHeight(38)
        self.process_btn.setStyleSheet("""
            QPushButton {
                background: #1976d2; border: none; border-radius: 8px;
                color: #ffffff; font-size: 13px; font-weight: 600;
                padding: 0 24px;
            }
            QPushButton:hover { background: #1565c0; }
        """)
        self.process_btn.clicked.connect(self._on_process_clicked)
        action_layout.addWidget(self.process_btn)

        self.action_bar.hide()
        layout.addWidget(self.action_bar)

    def load(self, course_id: int, course_title: str):
        # Clear previous
        self._groups.clear()
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.header.setText(course_title)
        self.status_label.setText("Loading course details...")
        self.status_label.setStyleSheet("font-size: 14px; color: #667085; padding: 40px; background: transparent;")
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
            task = ProcessingTask(
                lesson_id=item.lesson_id,
                lesson_title=item.lesson_title,
                source_file=file_path,
                course_storage_path=item.course_storage_path,
                qualities=qualities,
            )
            tasks.append(task)

        if tasks:
            dialog = ProcessDialog(tasks, self)
            dialog.exec()

    def _on_play_requested(self, storage_path: str, filename: str):
        self.status_label.setText("Generating video URL...")
        self.status_label.setStyleSheet("font-size: 14px; color: #1976d2; padding: 10px; background: transparent;")
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
        self.status_label.setStyleSheet("font-size: 14px; color: #d32f2f; padding: 10px; background: transparent;")

    def _on_error(self, message: str):
        self.status_label.setText(f"Error: {message}")
        self.status_label.show()
        self.status_label.setStyleSheet("font-size: 14px; color: #d32f2f; padding: 40px; background: transparent;")
