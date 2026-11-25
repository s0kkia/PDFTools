from pathlib import Path

import pymupdf
from PIL import Image, ImageChops

from pdftools.core.operations import compare_pdfs


def _make_pdf(path: Path, text: str) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=200)
    page.insert_text((40, 80), text, fontsize=24)
    doc.save(path)
    doc.close()


def test_compare_pdfs_creates_visible_nonblank_comparison(tmp_path: Path) -> None:
    left = tmp_path / "left.pdf"
    right = tmp_path / "right.pdf"
    _make_pdf(left, "ORIGINAL")
    _make_pdf(right, "CHANGED")

    outputs = compare_pdfs(left, right, tmp_path / "diff", dpi=72)

    assert len(outputs) == 1
    assert outputs[0].is_file()
    assert outputs[0].stat().st_size > 1000

    image = Image.open(outputs[0]).convert("RGB")
    assert image.width > 3 * 200
    assert image.height > 100
    # A blank white canvas has no color variation; the rendered comparison must.
    extrema = image.getextrema()
    assert any(low != high for low, high in extrema)
