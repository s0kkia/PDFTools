from __future__ import annotations
from pathlib import Path
import pymupdf as fitz


def ocr_to_searchable_pdf(source: str | Path, output: str | Path, language: str = "rus+eng", dpi: int = 220) -> Path:
    """Requires pytesseract, Pillow and a separately installed Tesseract executable."""
    try:
        import pytesseract
        from PIL import Image
        from io import BytesIO
    except ImportError as exc:
        raise RuntimeError("Для OCR установите pytesseract и Pillow") from exc
    src, dst = Path(source), Path(output)
    out = fitz.open()
    try:
        with fitz.open(src) as doc:
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
                image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                pdf_bytes = pytesseract.image_to_pdf_or_hocr(image, extension="pdf", lang=language)
                page_doc = fitz.open("pdf", pdf_bytes)
                out.insert_pdf(page_doc)
                page_doc.close()
        dst.parent.mkdir(parents=True, exist_ok=True)
        out.save(dst, garbage=4, deflate=True)
    finally:
        out.close()
    return dst
