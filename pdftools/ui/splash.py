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

        # Фон и декоративные элементы рисуются напрямую: внешние PNG не требуются.
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0.0, QColor("#101b2b"))
        gradient.setColorAt(0.55, QColor("#18364a"))
        gradient.setColorAt(1.0, QColor("#087f83"))
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(self.rect(), 22, 22)

        painter.setBrush(QColor(255, 255, 255, 13))
        painter.drawEllipse(520, -115, 330, 330)
        painter.drawEllipse(-130, 245, 280, 280)

        painter.setPen(QColor("#54d6c5"))
        painter.setFont(QFont("Arial", 15, QFont.Bold))
        painter.drawText(48, 62, "PDFTOOLS")

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Arial", 36, QFont.Bold))
        painter.drawText(46, 145, "Работаем с PDF")
        
        painter.setPen(QColor("#b8d4df"))
        painter.setFont(QFont("Arial", 15))
        painter.drawText(49, 181, "Инструменты для документов — в одном месте")

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Arial", 17, QFont.DemiBold))
        message_rect = self.rect().adjusted(48, 218, -48, -58)
        painter.drawText(message_rect, Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap, self._message)

        painter.setPen(QColor(255, 255, 255, 105))
        painter.setFont(QFont("Arial", 9))
        painter.drawText(49, self.height() - 24, f"PDFTools  •  версия {__version__}")
        painter.end()

