from __future__ import annotations

import random
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QFont, QLinearGradient
from PySide6.QtWidgets import QApplication, QWidget

from pdftools import __version__


class StartupSplash(QWidget):
    """Самодостаточная заставка PDFTools: фон рисуется кодом, фразы меняются автоматически."""

    MESSAGES = [
        "Ну потерпи ещё чуточку…",
        "Загружаем тяжёлую артиллерию для PDF",
        "Проверяем, не убежали ли ваши документы",
        "Собираем пиксели в кучку",
        "Почти готово. Не переключайтесь!",
        "PDFTools просыпается. Кофе ему не предлагать!",
        "Ещё немного — и можно работать!",
        "Раскладываем ваши PDF по полочкам",
        "УПС… задумались. Уже исправляем!",
        "Солтех на связи. Наводим порядок!",
        "Подготавливаем инструменты для работы",
        "Сейчас всё будет красиво!",
    ]

    def __init__(self):
        super().__init__(None, Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setFixedSize(720, 360)
        self.setWindowTitle("PDFTools")
        self._message = random.choice(self.MESSAGES)
        self.message_timer = QTimer(self)
        self.message_timer.timeout.connect(self._change_message)
        self.message_timer.start(2600)

        screen = QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.move(area.center() - self.rect().center())

    def _change_message(self):
        choices = [message for message in self.MESSAGES if message != self._message]
        self._message = random.choice(choices)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Та же палитра и компоновка, что у основного окна PDFTools.
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#171a21"))
        painter.drawRoundedRect(self.rect(), 12, 12)

        # Левая панель повторяет Sidebar основного приложения.
        painter.setBrush(QColor("#202530"))
        painter.drawRoundedRect(0, 0, 205, self.height(), 12, 12)
        painter.setBrush(QColor("#171a21"))
        painter.drawRect(193, 0, 12, self.height())

        painter.setPen(QColor("#e8eaf0"))
        painter.setFont(QFont("Segoe UI", 23, QFont.Bold))
        painter.drawText(28, 68, "PDFTools")
        painter.setPen(QColor("#9ca7b8"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(29, 91, "РАБОЧЕЕ ПРОСТРАНСТВО")
        painter.setPen(QColor("#356fe5"))
        painter.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        painter.drawText(29, 143, "PDF")
        painter.setPen(QColor("#9ca7b8"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(29, 165, f"Версия {__version__}")

        # Правая область повторяет рабочую часть главного окна.
        painter.setPen(QColor("#e8eaf0"))
        painter.setFont(QFont("Segoe UI", 21, QFont.Bold))
        painter.drawText(239, 65, "Главная")
        painter.setPen(QColor("#394355"))
        painter.drawLine(239, 84, self.width() - 30, 84)

        painter.setPen(QColor("#e8eaf0"))
        painter.setFont(QFont("Segoe UI", 18, QFont.DemiBold))
        message_rect = self.rect().adjusted(239, 105, -30, -95)
        painter.drawText(message_rect, Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap, self._message)

        painter.setPen(QColor("#9ca7b8"))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(239, self.height() - 38, "Подготавливаем рабочее пространство PDFTools…")
        painter.end()

