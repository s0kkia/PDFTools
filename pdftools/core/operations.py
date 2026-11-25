from __future__ import annotations
from pathlib import Path
from typing import Iterable
import pymupdf as fitz
import pikepdf
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


def compress_pdf(source: str | Path, output: str | Path, level: str = "balanced") -> Path:
    src, dst = Path(source), Path(output)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if level not in {"light", "balanced", "strong"}:
        raise ValueError("Уровень сжатия должен быть light, balanced или strong")
    with pikepdf.open(src) as pdf:
        if level == "light":
            pdf.save(dst, compress_streams=True)
        elif level == "balanced":
            pdf.save(dst, compress_streams=True, recompress_flate=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
        else:
            pdf.save(dst, compress_streams=True, recompress_flate=True,
                     object_stream_mode=pikepdf.ObjectStreamMode.generate, linearize=True)
    return dst


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
    """Creates visual difference PNGs for matching page indexes."""
    a, b = fitz.open(left), fitz.open(right)
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    outputs = []
    try:
        for i in range(min(a.page_count, b.page_count)):
            pa = a[i].get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
            pb = b[i].get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
            # Normalize render dimensions before pixel comparison.
            from PIL import Image, ImageChops
            ia = Image.frombytes("RGB", (pa.width, pa.height), pa.samples)
            ib = Image.frombytes("RGB", (pb.width, pb.height), pb.samples)
            if ib.size != ia.size:
                ib = ib.resize(ia.size)
            diff = ImageChops.difference(ia, ib)
            target = outdir / f"diff_page_{i + 1:04d}.png"
            diff.save(target)
            outputs.append(target)
        return outputs
    finally:
        a.close()
        b.close()


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


def add_text_watermark(source: str | Path, output: str | Path, text: str,
                       opacity: float = 0.22, fontsize: float = 48,
                       rotation: int = 45, color: tuple[float, float, float] = (0.55, 0.55, 0.55)) -> Path:
    """Adds a centered diagonal text watermark to every page."""
    src, dst = Path(source), Path(output)
    if not text.strip():
        raise ValueError("Текст водяного знака не может быть пустым")
    opacity = max(0.05, min(float(opacity), 1.0))
    dst.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(src) as doc:
        for page in doc:
            rect = page.rect
            point = fitz.Point(rect.width / 2 - fontsize, rect.height / 2)
            page.insert_text(point, text, fontsize=fontsize, fontname="helv",
                             color=color, fill_opacity=opacity, rotate=rotation,
                             overlay=True)
        doc.save(dst, garbage=4, deflate=True)
    return dst
