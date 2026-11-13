import sys
from PySide6.QtWidgets import QApplication
from meck_ai.ui import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("TURTLE")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
