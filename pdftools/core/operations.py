from __future__ import annotations
from pathlib import Path
import os
from typing import Iterable
import pymupdf as fitz
from pypdf import PdfReader, PdfWriter


def merge_pdfs(inputs: Iterable[str | Path], output: str | Path) -> Path:
    writer = PdfWriter()
    for path in inputs:
        reader = PdfReader(str(path), strict=False)
        for page in reader.pages:
            writer.add_page(page)
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        writer.write(f)
    return out


def split_pdf(source: str | Path, output_dir: str | Path) -> list[Path]:
    src, outdir = Path(source), Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(src)
    outputs = []
    try:
        for index in range(doc.page_count):
            part = fitz.open()
            part.insert_pdf(doc, from_page=index, to_page=index)
            target = outdir / f"{src.stem}_page_{index + 1:04d}.pdf"
            part.save(target, garbage=4, deflate=True)
            part.close()
            outputs.append(target)
    finally:
        doc.close()
    return outputs


def set_metadata(source: str | Path, output: str | Path, metadata: dict[str, str]) -> Path:
    src, dst = Path(source), Path(output)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(src) as doc:
        current = dict(doc.metadata or {})
        current.update({k: v for k, v in metadata.items() if v is not None})
        doc.set_metadata(current)
        doc.save(dst, garbage=4, deflate=True)
    return dst


def add_image_stamp(source: str | Path, image: str | Path, output: str | Path,
                    page_number: int, x: float, y: float, width: float) -> Path:
    """x/y/width are PDF points; x/y define top-left origin on the selected page."""
    src, img, dst = Path(source), Path(image), Path(output)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(src) as doc:
        if page_number < 1 or page_number > doc.page_count:
            raise IndexError("Номер страницы вне диапазона документа")
        page = doc[page_number - 1]
        pix = fitz.Pixmap(str(img))
        ratio = pix.height / pix.width if pix.width else 1
        rect = fitz.Rect(x, y, x + width, y + width * ratio)
        page.insert_image(rect, filename=str(img), overlay=True)
        doc.save(dst, garbage=4, deflate=True)
    return dst


def compare_pdfs(left: str | Path, right: str | Path, output_dir: str | Path,
                 dpi: int = 120) -> list[Path]:
    """Render a visible three-panel comparison: source A, source B, highlighted differences."""
    from PIL import Image, ImageChops, ImageEnhance, ImageDraw

    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    with fitz.open(left) as a, fitz.open(right) as b:
        page_total = max(a.page_count, b.page_count)
        scale = dpi / 72
        for i in range(page_total):
            images = []
            for doc in (a, b):
                if i < doc.page_count:
                    page = doc[i]
                    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, colorspace=fitz.csRGB)
                    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                else:
                    image = None
                images.append(image)

            ia, ib = images
            if ia is None and ib is None:
                continue
            width = max(ia.width if ia else 0, ib.width if ib else 0)
            height = max(ia.height if ia else 0, ib.height if ib else 0)

            def fit_page(image):
                canvas = Image.new("RGB", (width, height), "white")
                if image is not None:
                    canvas.paste(image, (0, 0))
                return canvas

            ia, ib = fit_page(ia), fit_page(ib)
            diff = ImageChops.difference(ia, ib)
            # Increase visibility of small changes and tint them red.
            diff = ImageEnhance.Contrast(diff).enhance(3.0)
            mask = diff.convert("L").point(lambda value: 255 if value > 24 else 0)
            highlighted = ia.copy()
            red_layer = Image.new("RGB", (width, height), (255, 40, 40))
            highlighted.paste(red_layer, (0, 0), mask)

            header_h = 42
            gap = 16
            result = Image.new("RGB", (width * 3 + gap * 4, height + header_h + gap * 2), (238, 241, 245))
            draw = ImageDraw.Draw(result)
            panels = [
                (ia, "PDF A"),
                (ib, "PDF B"),
                (highlighted, "Различия (красным)"),
            ]
            for panel_index, (image, label) in enumerate(panels):
                x = gap + panel_index * (width + gap)
                draw.text((x, 12), label, fill=(25, 35, 50))
                result.paste(image, (x, header_h))
            target = outdir / f"diff_page_{i + 1:04d}.png"
            result.save(target, format="PNG", optimize=True)
            if target.stat().st_size == 0:
                raise RuntimeError(f"Не удалось сформировать изображение сравнения страницы {i + 1}")
            outputs.append(target)

    return outputs

def extract_images(source: str | Path, output_dir: str | Path) -> list[Path]:
    src, outdir = Path(source), Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    outputs = []
    with fitz.open(src) as doc:
        for page_index, page in enumerate(doc):
            for image_index, info in enumerate(page.get_images(full=True), start=1):
                xref = info[0]
                extracted = doc.extract_image(xref)
                ext = extracted.get("ext", "bin")
                target = outdir / f"page_{page_index + 1:04d}_image_{image_index:03d}.{ext}"
                target.write_bytes(extracted["image"])
                outputs.append(target)
    return outputs


def extract_tables(source: str | Path, output_dir: str | Path) -> list[Path]:
    src, outdir = Path(source), Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    outputs = []
    with fitz.open(src) as doc:
        for page_index, page in enumerate(doc):
            if not hasattr(page, "find_tables"):
                continue
            finder = page.find_tables()
            for table_index, table in enumerate(finder.tables, start=1):
                target = outdir / f"page_{page_index + 1:04d}_table_{table_index:02d}.csv"
                rows = table.extract()
                import csv
                with target.open("w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f, delimiter=";")
                    writer.writerows(rows)
                outputs.append(target)
    return outputs


def _unicode_font_path() -> Path | None:
    """Find a system font with Cyrillic glyphs for embedding into the output PDF."""
    candidates = [
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segoeui.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]
    return next((path for path in candidates if path.is_file()), None)


def add_text_watermark(source: str | Path, output: str | Path, text: str,
                       opacity: float = 0.22, fontsize: float = 48,
                       rotation: int = 45, color: tuple[float, float, float] = (0.55, 0.55, 0.55)) -> Path:
    """Adds a centered diagonal text watermark; embeds a Unicode font for Cyrillic text."""
    src, dst = Path(source), Path(output)
    if not text.strip():
        raise ValueError("Текст водяного знака не может быть пустым")
    opacity = max(0.05, min(float(opacity), 1.0))
    fontsize = float(fontsize)
    if fontsize <= 0:
        raise ValueError("Размер шрифта должен быть больше нуля")
    dst.parent.mkdir(parents=True, exist_ok=True)

    font_path = _unicode_font_path() if any(ord(char) > 127 for char in text) else None
    if any(ord(char) > 127 for char in text) and font_path is None:
        raise RuntimeError("Для кириллического водяного знака не найден системный Unicode-шрифт (например, Arial).")

    with fitz.open(src) as doc:
        for page in doc:
            rect = page.rect
            point = fitz.Point(rect.width / 2 - fontsize, rect.height / 2)
            if font_path:
                page.insert_text(point, text, fontsize=fontsize, fontname="PDFToolsUnicode",
                                 fontfile=str(font_path), color=color, fill_opacity=opacity,
                                 rotate=rotation, overlay=True)
            else:
                page.insert_text(point, text, fontsize=fontsize, fontname="helv",
                                 color=color, fill_opacity=opacity, rotate=rotation,
                                 overlay=True)
        doc.save(dst, garbage=4, deflate=True)
    return dst
