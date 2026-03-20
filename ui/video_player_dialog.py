from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider, QWidget,
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget


class VideoPlayerDialog(QDialog):
    def __init__(self, url: str, title: str = "Video Player", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(800, 500)
        self.resize(960, 600)
        self.setStyleSheet("background: #0f172a;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Video widget
        self.video_widget = QVideoWidget()
        layout.addWidget(self.video_widget, stretch=1)

        # Controls bar
        controls = QWidget()
        controls.setFixedHeight(48)
        controls.setStyleSheet("background: #1e293b;")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(12, 0, 12, 0)
        controls_layout.setSpacing(10)

        # Play/Pause button
        self.play_pause_btn = QPushButton("\u25b6")
        self.play_pause_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.play_pause_btn.setFixedSize(36, 32)
        self.play_pause_btn.setStyleSheet("""
            QPushButton {
                background: #334155; border: none; border-radius: 6px;
                color: #e2e8f0; font-size: 14px;
            }
            QPushButton:hover { background: #475569; }
        """)
        self.play_pause_btn.clicked.connect(self._toggle_play)
        controls_layout.addWidget(self.play_pause_btn)

        # Time label
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setStyleSheet("color: #94a3b8; font-size: 11px; background: transparent;")
        self.time_label.setFixedWidth(100)
        controls_layout.addWidget(self.time_label)

        # Seek slider
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px; background: #334155; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 12px; height: 12px; margin: -4px 0;
                background: #3b82f6; border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #3b82f6; border-radius: 2px;
            }
        """)
        self.seek_slider.sliderMoved.connect(self._seek)
        controls_layout.addWidget(self.seek_slider, stretch=1)

        # Volume slider
        vol_label = QLabel("\U0001f50a")
        vol_label.setStyleSheet("color: #94a3b8; font-size: 13px; background: transparent;")
        controls_layout.addWidget(vol_label)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px; background: #334155; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 10px; height: 10px; margin: -3px 0;
                background: #94a3b8; border-radius: 5px;
            }
            QSlider::sub-page:horizontal {
                background: #64748b; border-radius: 2px;
            }
        """)
        self.volume_slider.valueChanged.connect(self._set_volume)
        controls_layout.addWidget(self.volume_slider)

        layout.addWidget(controls)

        # Media player setup
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(0.8)

        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)

        self.player.setSource(QUrl(url))
        self.player.play()

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_pause_btn.setText("\u23f8")
        else:
            self.play_pause_btn.setText("\u25b6")

    def _on_duration_changed(self, duration):
        self.seek_slider.setRange(0, duration)
        self._update_time_label()

    def _on_position_changed(self, position):
        if not self.seek_slider.isSliderDown():
            self.seek_slider.setValue(position)
        self._update_time_label()

    def _seek(self, position):
        self.player.setPosition(position)

    def _set_volume(self, value):
        self.audio_output.setVolume(value / 100.0)

    def _update_time_label(self):
        pos = self.player.position() // 1000
        dur = self.player.duration() // 1000
        self.time_label.setText(f"{pos // 60}:{pos % 60:02d} / {dur // 60}:{dur % 60:02d}")

    def closeEvent(self, event):
        self.player.stop()
        super().closeEvent(event)
