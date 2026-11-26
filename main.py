from __future__ import annotations

import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication


def _close_boot_splash() -> None:
    """Close PyInstaller's bootloader splash after the main window is visible."""
    try:
        import pyi_splash
        if pyi_splash.is_alive():
            pyi_splash.close()
    except Exception:
        pass


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    from pdftools.ui.theme import DARK_QSS
    app.setStyleSheet(DARK_QSS)
    from pdftools.app import MainWindow

    window = MainWindow()
    window.show()
    # Keep the bootloader splash for two seconds after the application window appears.
    QTimer.singleShot(2000, _close_boot_splash)
    QTimer.singleShot(3500, window.check_auto_updates)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
