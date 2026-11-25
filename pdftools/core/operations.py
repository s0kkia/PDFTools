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
            base = outdir / f"{src.stem}_page_{index + 1:04d}.pdf"
            target = base
            suffix = 2
            while target.exists():
                target = base.with_name(f"{base.stem}_{suffix}{base.suffix}")
                suffix += 1
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
                 dpi: int = 120, tolerance_px: int = 3,
                 ink_threshold: int = 210) -> list[Path]:
    """Compare PDF drawings with spatial tolerance; added lines red, removed lines blue."""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
    if not 36 <= int(dpi) <= 600:
        raise ValueError("Разрешение сравнения должно быть в диапазоне 36–600 DPI")
    if not 0 <= int(tolerance_px) <= 12:
        raise ValueError("Допуск смещения должен быть в диапазоне 0–12 пикселей")
    if not 1 <= int(ink_threshold) <= 254:
        raise ValueError("Порог распознавания линий должен быть в диапазоне 1–254")
    outdir = Path(output_dir); outdir.mkdir(parents=True, exist_ok=True)
    outputs = []
    with fitz.open(left) as a, fitz.open(right) as b:
        scale = dpi / 72
        for i in range(max(a.page_count, b.page_count)):
            imgs = []
            for doc in (a, b):
                if i < doc.page_count:
                    pix = doc[i].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, colorspace=fitz.csRGB)
                    imgs.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
                else: imgs.append(None)
            ia, ib = imgs
            width=max(im.width if im else 0 for im in imgs); height=max(im.height if im else 0 for im in imgs)
            def canvas(im):
                out=Image.new("RGB",(width,height),"white")
                if im is not None: out.paste(im,((width-im.width)//2,(height-im.height)//2))
                return out
            ia,ib=canvas(ia),canvas(ib)
            ma=ia.convert("L").point(lambda v:255 if v<ink_threshold else 0)
            mb=ib.convert("L").point(lambda v:255 if v<ink_threshold else 0)
            kernel=max(3,int(tolerance_px)*2+1)
            near_a=ma.filter(ImageFilter.MaxFilter(kernel)); near_b=mb.filter(ImageFilter.MaxFilter(kernel))
            added=ImageChops.multiply(mb,ImageChops.invert(near_a))
            removed=ImageChops.multiply(ma,ImageChops.invert(near_b))
            if tolerance_px:
                added=added.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
                removed=removed.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
            marked=ib.copy()
            marked.paste(Image.new("RGB",(width,height),(255,35,35)),(0,0),added)
            marked.paste(Image.new("RGB",(width,height),(35,100,255)),(0,0),removed)
            gap,header=16,42
            result=Image.new("RGB",(width*3+gap*4,height+header+gap*2),(238,241,245))
            draw=ImageDraw.Draw(result)
            for n,(im,label) in enumerate([(ia,"PDF A"),(ib,"PDF B"),(marked,f"Добавлено красным · удалено синим · допуск {tolerance_px}px")]):
                x=gap+n*(width+gap); draw.text((x,12),label,fill=(25,35,50)); result.paste(im,(x,header))
            target=outdir/f"diff_page_{i+1:04d}.png"; result.save(target,format="PNG",optimize=True); outputs.append(target)
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
                                 morph=(point, fitz.Matrix(rotation)), overlay=True)
            else:
                page.insert_text(point, text, fontsize=fontsize, fontname="helv",
                                 color=color, fill_opacity=opacity,
                                 morph=(point, fitz.Matrix(rotation)), overlay=True)
        doc.save(dst, garbage=4, deflate=True)
    return dst
