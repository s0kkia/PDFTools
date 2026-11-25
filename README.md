# PDFTools test-1

Отдельная тестовая ветка развития PDFTools для Windows 10/11 x64. Проект написан на Python с интерфейсом PySide6.

Сборка и тестирование Windows EXE автоматизированы через GitHub Actions. См. [README_test-1.md](README_test-1.md) и [журнал изменений](CHANGELOG_test-1.md).

**Статус:** предварительная тестовая версия. Перед использованием на рабочих документах проверяйте результаты на копиях файлов. OCR требует установленного Tesseract OCR; для дополнительных методов восстановления могут понадобиться qpdf или mutool.

## Запуск из исходников

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```
