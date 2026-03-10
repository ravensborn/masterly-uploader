import os
import sys

from dotenv import load_dotenv
from PyQt6.QtWidgets import QApplication

load_dotenv()

from ui.main_window import MainWindow

API_BASE = "https://masterly-api.the-nebula.tech/api"

STYLESHEET = """
* {
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
}

QMainWindow {
    background: #f0f2f5;
}

QScrollArea {
    background: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background: transparent;
}

QScrollBar:vertical {
    background: #f0f2f5;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #c0c0c0;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #a0a0a0;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QLineEdit {
    padding: 10px 16px;
    border: 1px solid #d0d5dd;
    border-radius: 8px;
    font-size: 14px;
    background: #ffffff;
    color: #1d2939;
}
QLineEdit:focus {
    border: 2px solid #1976d2;
    background: #ffffff;
}
QLineEdit::placeholder {
    color: #98a2b3;
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
