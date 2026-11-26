from __future__ import annotations

import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from pdftools.ui.splash import StartupSplash


def main() -> None:
    # Создаём и показываем заставку до импорта тяжёлых модулей PDFTools.
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    splash = StartupSplash()
    splash.show()
    app.processEvents()

    # Только теперь загружаем основное приложение и PDF-библиотеки.
    from pdftools.ui.theme import DARK_QSS
    app.setStyleSheet(DARK_QSS)
    from pdftools.app import MainWindow

    window = MainWindow()
    window.show()
    app.processEvents()

    # Заставка остаётся ещё 2 секунды после отображения главного окна.
    QTimer.singleShot(2000, splash.close)
    QTimer.singleShot(3500, window.check_auto_updates)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
