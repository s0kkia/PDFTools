from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import shutil
import subprocess
import pymupdf as fitz


@dataclass
class RepairResult:
    src: Path
    ok: bool
    method: str
    pages: int | None
    out_path: Path | None
    verify_msg: str
    log: list[str]


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return path.with_name(f"{path.stem}_{stamp}{path.suffix}")


def verify_pdf(path: Path) -> tuple[bool, str, int | None]:
    try:
        with fitz.open(path) as doc:
            pages = doc.page_count
            if pages < 1:
                return False, "Документ не содержит страниц", pages
            # Force page-tree/page-object access.
            for i in range(pages):
                doc.load_page(i)
            return True, f"Проверено PyMuPDF: {pages} стр.", pages
    except Exception as exc:
        return False, f"Проверка не пройдена: {exc}", None


def _pikepdf(src: Path, dst: Path) -> tuple[bool, str]:
    try:
        import pikepdf
        with pikepdf.open(src, attempt_recovery=True) as pdf:
            pdf.save(dst, recompress_flate=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
        return True, "pikepdf: успешно"
    except Exception as exc:
        return False, f"pikepdf: {exc}"


def _external(executable: str, args: list[str], dst: Path) -> tuple[bool, str]:
    exe = shutil.which(executable)
    if not exe:
        return False, f"{executable}: не найден в PATH"
    try:
        cp = subprocess.run([exe, *args], capture_output=True, timeout=180, check=False)
        if cp.returncode == 0 and dst.exists() and dst.stat().st_size:
            return True, f"{executable}: успешно"
        detail = (cp.stderr or cp.stdout).decode("utf-8", "replace").strip()
        return False, f"{executable}: код {cp.returncode}; {detail}"
    except Exception as exc:
        return False, f"{executable}: {exc}"


def _pypdf(src: Path, dst: Path) -> tuple[bool, str]:
    try:
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(str(src), strict=False)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        with dst.open("wb") as stream:
            writer.write(stream)
        return True, "pypdf: успешно"
    except Exception as exc:
        return False, f"pypdf: {exc}"


def repair_file(source: str | Path, output_path: str | Path | None = None) -> RepairResult:
    src = Path(source).expanduser().resolve()
    dst = Path(output_path) if output_path else src.with_name(f"{src.stem}_fixed.pdf")
    dst.parent.mkdir(parents=True, exist_ok=True)
    logs = []
    methods = [
        ("pikepdf", lambda target: _pikepdf(src, target)),
        ("qpdf", lambda target: _external("qpdf", ["--repair", str(src), str(target)], target)),
        ("mutool", lambda target: _external("mutool", ["clean", "-g", str(src), str(target)], target)),
        ("pypdf", lambda target: _pypdf(src, target)),
    ]
    for method, runner in methods:
        candidate = _unique(dst)
        ok, message = runner(candidate)
        logs.append(message)
        if not ok or not candidate.exists():
            candidate.unlink(missing_ok=True)
            continue
        valid, verify_msg, pages = verify_pdf(candidate)
        logs.append(verify_msg)
        if valid:
            return RepairResult(src, True, method, pages, candidate, verify_msg, logs)
        candidate.unlink(missing_ok=True)
    return RepairResult(src, False, "—", None, None, "Все методы восстановления завершились неудачно", logs)
