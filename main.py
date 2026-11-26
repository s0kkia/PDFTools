from __future__ import annotations

import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from pdftools.ui.theme import DARK_QSS
    app.setStyleSheet(DARK_QSS)
    from pdftools.app import MainWindow

    window = MainWindow()
    window.show()
    QTimer.singleShot(3500, window.check_auto_updates)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
