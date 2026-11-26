"""Rotate short messages on the native PyInstaller one-file splash screen."""
import random
import threading
import time

_MESSAGES = (
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
)

try:
    import pyi_splash
except Exception:
    pyi_splash = None


def _rotate_messages():
    if pyi_splash is None:
        return
    current = _MESSAGES[0]
    while True:
        time.sleep(2.6)
        try:
            if not pyi_splash.is_alive():
                return
            choices = [message for message in _MESSAGES if message != current]
            current = random.choice(choices)
            pyi_splash.update_text(current)
        except Exception:
            return


if pyi_splash is not None:
    try:
        if pyi_splash.is_alive():
            pyi_splash.update_text(_MESSAGES[0])
            threading.Thread(target=_rotate_messages, name="PDFToolsSplashMessages", daemon=True).start()
    except Exception:
        pass
