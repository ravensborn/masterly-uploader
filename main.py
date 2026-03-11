import os
import sys

from dotenv import load_dotenv
from PySide6.QtWidgets import QApplication

load_dotenv()

from ui.main_window import MainWindow

API_BASE = os.getenv("API_BASE_URL", "https://masterly-api.the-nebula.tech").rstrip("/") + "/api"

STYLESHEET = """
* {
    font-family: "Inter", "SF Pro Display", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
}

QMainWindow {
    background: #f8fafc;
}

QScrollArea {
    background: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background: transparent;
}

QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 4px 0;
}
QScrollBar::handle:vertical {
    background: #cbd5e1;
    border-radius: 3px;
    min-height: 40px;
}
QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

QScrollBar:horizontal {
    background: transparent;
    height: 6px;
    margin: 0 4px;
}
QScrollBar::handle:horizontal {
    background: #cbd5e1;
    border-radius: 3px;
    min-width: 40px;
}
QScrollBar::handle:horizontal:hover {
    background: #94a3b8;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}

QLineEdit {
    padding: 10px 16px;
    border: 1.5px solid #e2e8f0;
    border-radius: 10px;
    font-size: 14px;
    background: #ffffff;
    color: #0f172a;
    selection-background-color: #bfdbfe;
}
QLineEdit:focus {
    border: 1.5px solid #3b82f6;
    background: #ffffff;
}
QLineEdit::placeholder {
    color: #94a3b8;
}

QToolTip {
    background: #1e293b;
    color: #f1f5f9;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}
"""


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    window = MainWindow(api_base=API_BASE)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
