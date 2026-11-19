import os
import sys

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
from PySide6.QtWidgets import QApplication
from meck_ai.ui import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("TURTLE")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
