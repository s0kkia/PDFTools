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


def test_stamp_insert_respects_visual_orientation_on_rotated_pages(tmp_path: Path) -> None:
    from pdftools.core.operations import insert_image_at_visual_rect

    # A wide stamp is placed in the visible coordinate system of the page.
    stamp = tmp_path / "wide_stamp.png"
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 300, 100), False)
    pix.clear_with(255)
    pix.save(stamp)

    for rotation in (0, 90, 180, 270):
        source = tmp_path / f"source_{rotation}.pdf"
        output = tmp_path / f"stamped_{rotation}.pdf"
        doc = pymupdf.open()
        page = doc.new_page(width=600, height=800)
        page.set_rotation(rotation)
        visible = page.rect
        # Keep the target rectangle safely inside each page's displayed bounds.
        rect = pymupdf.Rect(
            visible.width * 0.15,
            visible.height * 0.15,
            visible.width * 0.65,
            visible.height * 0.15 + 100,
        )
        insert_image_at_visual_rect(page, stamp, rect)
        doc.save(source)
        doc.close()

        with pymupdf.open(source) as check:
            page = check[0]
            pixmap = page.get_pixmap()
            # The inserted image remains landscape (wide) in the rendered page,
            # independent of the page's /Rotate value.
            image_rects = page.get_image_rects(page.get_images()[0][0])
            assert image_rects
            rendered_rect = image_rects[0] * page.rotation_matrix
            assert rendered_rect.width > rendered_rect.height
