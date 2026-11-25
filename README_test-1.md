# PDFTools test-1 — отдельный проект

## Зафиксированные решения
- Windows 10/11 x64.
- Python 3.13 x64 для разработки.
- PySide6 GUI.
- Установщик Windows через Inno Setup 6.
- Дополнительно предусмотрен Portable ZIP.
- Хранение данных: AppData по умолчанию; локальный режим `UserData` предусмотрен через `storage_mode` в `%APPDATA%/PDFTools/settings.json`.
- GitHub Releases — целевой канал обновлений.

## Исходная база
Отдельная копия последнего подготовленного проекта `PDFTools_2.0_stamp_autoplace.zip`. Исходный PDFTools 2.0 не изменяется.

## Запуск разработки
```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Сборка
Запустить `build_windows.ps1` из PowerShell. Для установщика дополнительно требуется Inno Setup 6 и компиляция `installer/PDFTools_test-1.iss`.

## Ограничения переходной сборки
Это отдельная рабочая копия и каркас перехода. Новые модули из утверждённого плана ещё не реализованы. Автообновление пока не завершено: текущий код проверяет GitHub Releases, но не выполняет безопасную установку с прогрессом, updater helper и откатом. До публикации нужно завершить эти функции, проверить GUI на Windows 10/11, прогнать тесты и исправить ошибки.


## Публикация Windows-сборки

При отправке тега вида `v1.0.0-test1` workflow `.github/workflows/windows-release.yml`
собирает приложение на Windows x64 и публикует в GitHub Release:
- `PDFTools.exe` — автономный EXE;
- `PDFTools_test-1_Portable_Windows_x64.zip` — portable ZIP с EXE и README;
- `SHA256SUMS.txt` — контрольная сумма EXE.

Workflow запускает pytest перед сборкой. Успешная сборка CI не заменяет ручную проверку GUI
и PDF-операций на Windows 10/11. До публикации стабильной версии указывайте статус
предварительного тестирования.
