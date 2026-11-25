# Отчёт по исследованию исходных EXE

## PDFTools
- Формат: Windows PE32+ x64.
- PyInstaller PKG cookie обнаружен.
- Внутри архива: Python 3.12 (`python312.dll`), главный модуль `VPR`.
- GUI: Tkinter / ttk.
- Заголовок окна: `PDF Tools v0.9.8`.
- Основные классы: `DescriptionFrame`, `PDFStamperFrame`, `PDFProcessorFrame`.
- Основные функции: `process_pdf`, `resource_path`, `on_closing`.
- PDF библиотеки: PyMuPDF (`fitz`), Pillow, PyPDF2.

## HotFix
- Формат: Windows PE32+ x64.
- PyInstaller PKG cookie обнаружен.
- Внутри архива: Python 3.12 (`python312.dll`), главный модуль `hotifx`.
- GUI: Tkinter / ttk.
- Заголовок окна: `PDF Repair GUI (xref fix)`.
- Основные функции: `verify_with_fitz`, `repair_with_pikepdf`, `repair_with_qpdf`, `repair_with_mutool`, `repair_with_pypdf`, `repair_file`.
- Класс GUI: `App`.
- Дополнительно: пакетный список файлов, журнал, экспорт PDF-отчёта.

## Ограничения
- В переданных ZIP только EXE, исходников `.py` нет.
- Извлечение структуры и Python code objects подтверждает имена функций, классов, констант и библиотек, но не означает точное восстановление авторского исходного кода.
- Новый проект — переписанная реализация восстановленного поведения. Сравнение с оригинальными EXE на тестовых документах обязательно.
