from pathlib import Path

import pymupdf
import pytest

from pdftools.core.operations import add_text_watermark, split_pdf, _unicode_font_path


def _make_pdf(path: Path, pages: int = 1) -> None:
    doc = pymupdf.open()
    for index in range(pages):
        page = doc.new_page(width=300, height=200)
        page.insert_text((30, 60), f"PAGE {index + 1}")
    doc.save(path)
    doc.close()


def test_cyrillic_watermark_is_embedded_and_extractable(tmp_path: Path) -> None:
    if _unicode_font_path() is None:
        pytest.skip("No supported system Unicode font available")
    source = tmp_path / "source.pdf"
    output = tmp_path / "watermarked.pdf"
    _make_pdf(source)

    add_text_watermark(source, output, "КОПИЯ")

    with pymupdf.open(output) as doc:
        assert "КОПИЯ" in doc[0].get_text()


def test_split_pdf_does_not_overwrite_existing_pages(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    outdir = tmp_path / "split"
    _make_pdf(source, pages=2)
    outdir.mkdir()
    existing = outdir / "source_page_0001.pdf"
    existing.write_bytes(b"keep-me")

    outputs = split_pdf(source, outdir)

    assert len(outputs) == 2
    assert existing.read_bytes() == b"keep-me"
    assert outputs[0].name == "source_page_0001_2.pdf"
    assert all(path.is_file() for path in outputs)
