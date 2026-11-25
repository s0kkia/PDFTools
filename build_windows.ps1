$ErrorActionPreference = "Stop"
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller pytest
.\.venv\Scripts\python.exe -m compileall -q .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed --onefile --name PDFTools main.py
Write-Host "EXE: dist\PDFTools.exe"
Write-Host "Next: compile installer\PDFTools_test-1.iss with Inno Setup 6."
