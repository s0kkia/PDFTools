# PDFTools 2.0

**PDF Toolkit for Windows — Python · PySide6**

PDFTools is a Windows desktop application for everyday PDF document workflows: repair, organize, stamp, compare, OCR, compress, and extract content from PDF files.

> **Project status:** test/development build. Some features are still being implemented and the Windows executable has not yet been validated on a clean Windows 10/11 machine. Always test with copies of important documents.

## Features

- **PDF repair (HotFix):** attempts recovery through available PDF backends.
- **PDF organization:** combine PDF files, split documents, and arrange pages in a visual workspace.
- **Stamps:** place image stamps on PDF pages; manage a reusable stamp library.
- **Watermarks:** add text watermarks to document pages.
- **PDF comparison:** compare rendered pages to identify visual differences.
- **OCR:** recognize text in scanned documents (requires Tesseract OCR and language data).
- **Compression:** optimize PDF structure and reduce file size where supported.
- **Metadata:** view and edit document metadata.
- **Extraction:** extract images and tabular data where detectable.
- **History:** keep a local record of operations.
- **Updates:** check GitHub Releases for newer application versions.

Feature availability depends on installed optional tools and the current build.

## Screenshots

Screenshots will be added after capturing the current Windows application interface. No mock screenshots are used in this repository.

## Requirements

- Windows 10 or Windows 11, 64-bit
- Python 3.13 x64 for running from source
- Dependencies listed in `requirements.txt`
- Tesseract OCR for OCR functionality (optional)
- qpdf or MuPDF tools may improve recovery options (optional)

## Run from source

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Build for Windows

The repository includes a GitHub Actions workflow intended to build a Windows x64 executable and portable archive when a version tag is pushed. The first CI run must complete successfully before downloadable binaries can be considered available.

## Data and privacy

The application is designed for local document processing. Review the implementation and configure optional external utilities before using it with confidential files. Do not upload sensitive documents to public issue reports.

## Disclaimer

PDFTools is provided for testing. PDF repair, OCR, extraction, and compression can alter output or fail on malformed or unusual documents. Keep originals and verify generated files before relying on them.

## License

No license has been specified yet. Until a license is added, the repository should be treated as “all rights reserved”; do not assume permission to redistribute or modify it.
