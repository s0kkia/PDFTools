from __future__ import annotations

import os
import random
import shutil
import sqlite3
from html import escape
from pathlib import Path

import pymupdf as fitz
from PySide6.QtCore import QEvent, QEventLoop, QObject, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QListView,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
)

import pdftools as pdftools_module
import pdftools.app as app_module
from pdftools.app import MainWindow, StampEditorDialog
from pdftools.core import history as history_module
from pdftools.core import operations as operations_module

app_module.__version__ = getattr(
    pdftools_module, "__version__", app_module.__version__
)

UPDATE_CONFIRM_NOTE = (
    "После обновления приложение будет перезагружаться. Это может занять "
    "некоторое время: Фиксики стараются, но они не волшебники. Скоро "
    "заработает — ожидайте."
)


class BusyPlaque(QFrame):
    MESSAGES = (
        "Ну я думаю… вроде.",
        "Секунду. Почти.",
        "Оно работает. Наверное.",
        "Ещё чуть-чуть. Честно.",
        "Не трогай, оно думает.",
        "Где-то здесь был прогресс…",
        "Уже почти. Как всегда.",
        "Всё под контролем. Скорее всего.",
        "Подожди, я прикидываю.",
        "Это не зависло. Это стиль.",
        "Считаю до бесконечности. Досчитаю — скажу.",
        "Ещё немного магии.",
        "Почти готово. В теории.",
        "Не смотри так, я стараюсь.",
        "Обрабатываю. Медленно, но с душой.",
        "Сейчас всё будет. Наверное.",
        "Терпение — тоже функция.",
        "Я не тормоз, я вдумчивый.",
    )

    def __init__(self, parent):
        super().__init__(
            parent,
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint,
        )
        self.setObjectName("busyPlaque")
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowModality(Qt.ApplicationModal)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedWidth(430)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)

        self.card = QFrame(self)
        self.card.setObjectName("busyCard")
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(Qt.black)
        self.card.setGraphicsEffect(shadow)
        outer.addWidget(self.card)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(18, 13, 18, 13)
        card_layout.setSpacing(8)

        self.title = QLabel("PDFTools", self.card)
        self.title.setObjectName("busyTitle")
        self.message = QLabel("", self.card)
        self.message.setObjectName("busyMessage")
        self.message.setWordWrap(True)
        self.bar = QProgressBar(self.card)
        self.bar.setRange(0, 0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(5)

        card_layout.addWidget(self.title)
        card_layout.addWidget(self.message)
        card_layout.addWidget(self.bar)

        self.setStyleSheet(
            """
            #busyCard {
                background: #1f2633;
                border: 1px solid #3d6fd8;
                border-radius: 10px;
            }
            #busyTitle {
                color: #8fb4ff;
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 1px;
            }
            #busyMessage {
                color: #e8eefb;
                font-size: 13px;
            }
            QProgressBar {
                background: #131822;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: #4a8cff;
                border-radius: 2px;
            }
            """
        )

        self._last_message = -1
        self._timer = QTimer(self)
        self._timer.setInterval(1100)
        self._timer.timeout.connect(self._rotate)

        if parent is not None:
            parent.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() in (
            QEvent.Move,
            QEvent.Resize,
            QEvent.Show,
        ):
            QTimer.singleShot(0, self._reposition)
        return False

    def _rotate(self):
        if len(self.MESSAGES) < 2:
            return
        index = self._last_message
        while index == self._last_message:
            index = random.randrange(len(self.MESSAGES))
        self._last_message = index
        self.message.setText(self.MESSAGES[index])

    def _reposition(self):
        parent = self.parentWidget()
        if parent is None or not self.isVisible():
            return
        geometry = parent.frameGeometry()
        self.adjustSize()
        x = geometry.center().x() - self.width() // 2
        y = geometry.bottom() - self.height() - 26
        screen = parent.screen()
        if screen is not None:
            available = screen.availableGeometry()
            x = max(
                available.left() + 8,
                min(x, available.right() - self.width() - 8),
            )
            y = max(
                available.top() + 8,
                min(y, available.bottom() - self.height() - 8),
            )
        self.move(x, y)

    def start(self, caption=None):
        self.title.setText(str(caption) if caption else "PDFTools")
        self._rotate()
        self.show()
        self.raise_()
        self._reposition()
        QApplication.processEvents()
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self.hide()
        QApplication.processEvents()


def _active_window():
    app = QApplication.instance()
    if app is None:
        return None
    window = app.activeWindow()
    if isinstance(window, MainWindow):
        return window
    for widget in app.topLevelWidgets():
        if isinstance(widget, MainWindow) and widget.isVisible():
            return widget
    return None


def _plaque_for(window):
    plaque = getattr(window, "_busy_plaque", None)
    if plaque is None:
        plaque = BusyPlaque(window)
        window._busy_plaque = plaque
    return plaque


def _pump():
    app = QApplication.instance()
    if app is not None:
        app.processEvents()


class _Busy:
    def __init__(self, caption=None, window=None):
        self.caption = caption
        self.window = window
        self.plaque = None

    def __enter__(self):
        window = self.window or _active_window()
        if window is not None:
            self.plaque = _plaque_for(window)
            self.plaque.start(self.caption)
        return self

    def __exit__(self, exc_type, exc, traceback):
        if self.plaque is not None:
            try:
                self.plaque.stop()
            except RuntimeError:
                pass
        return False


class _CallWorker(QThread):
    done = Signal(object, object)

    def __init__(self, function, args, kwargs):
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.done.emit(self.function(*self.args, **self.kwargs), None)
        except Exception as exc:  # noqa: BLE001 - re-raised in the GUI thread
            self.done.emit(None, exc)


def _run_busy(caption, function, *args, **kwargs):
    window = _active_window()
    if window is None:
        return function(*args, **kwargs)

    plaque = _plaque_for(window)
    plaque.start(caption)
    loop = QEventLoop()
    worker = _CallWorker(function, args, kwargs)
    outcome = {}

    def on_done(result, exc):
        outcome["result"] = result
        outcome["exc"] = exc
        loop.quit()

    worker.done.connect(on_done)
    try:
        worker.start()
        loop.exec()
        worker.wait()
    finally:
        try:
            plaque.stop()
        except RuntimeError:
            pass

    if outcome.get("exc") is not None:
        raise outcome["exc"]
    return outcome.get("result")


class _WorkspaceDropFilter(QObject):
    """Reorders workspace thumbnails explicitly instead of relying on QListWidget."""

    def __init__(self, workspace):
        super().__init__(workspace)
        self._workspace = workspace
        self._viewport = workspace.viewport()

    def eventFilter(self, watched, event):
        if watched is not self._workspace and watched is not self._viewport:
            return False
        if event.type() == QEvent.Drop:
            self._drop(event)
            return True
        return False

    def _drop(self, event):
        workspace = self._workspace
        selected = workspace.selectedItems()
        if not selected:
            current = workspace.currentItem()
            if current is None:
                event.ignore()
                return
            selected = [current]

        rows = sorted({workspace.row(item) for item in selected})
        items = [workspace.item(row) for row in rows]
        point = event.position().toPoint()
        target = workspace.indexAt(point).row()
        if target < 0:
            target = workspace.count()
        if target in rows:
            event.setDropAction(Qt.CopyAction)
            event.accept()
            return
        if target < workspace.count():
            rect = workspace.visualItemRect(workspace.item(target))
            if workspace.flow() == QListView.LeftToRight:
                drop_after = point.x() > rect.center().x()
            else:
                drop_after = point.y() > rect.center().y()
            if drop_after:
                target += 1

        insert_at = target - sum(1 for row in rows if row < target)
        for row in reversed(rows):
            workspace.takeItem(row)
        for offset, item in enumerate(items):
            workspace.insertItem(insert_at + offset, item)
        if items:
            workspace.setCurrentItem(items[0])
        event.setDropAction(Qt.CopyAction)
        event.accept()


def _configure_workspace(workspace):
    workspace.setDragDropMode(QAbstractItemView.InternalMove)
    workspace.setDefaultDropAction(Qt.MoveAction)
    workspace.setDragEnabled(True)
    workspace.setAcceptDrops(True)
    workspace.setDropIndicatorShown(True)
    workspace.setDragDropOverwriteMode(False)
    workspace.viewport().setAcceptDrops(True)
    for index in range(workspace.count()):
        item = workspace.item(index)
        item.setFlags(
            item.flags() | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
        )


class _ClosingConnection:
    def __init__(self, connection):
        self._connection = connection

    def __enter__(self):
        return self._connection.__enter__()

    def __exit__(self, exc_type, exc, traceback):
        try:
            return self._connection.__exit__(exc_type, exc, traceback)
        finally:
            self._connection.close()

    def __getattr__(self, name):
        return getattr(self._connection, name)


def _patch_history():
    def _connect(self):
        return _ClosingConnection(sqlite3.connect(self.db_path))

    history_module.HistoryStore._connect = _connect


def _patch_operations():
    original_merge_pdfs = operations_module.merge_pdfs
    original_compare_pdfs = operations_module.compare_pdfs
    original_add_text_watermark = operations_module.add_text_watermark
    original_extract_images = getattr(operations_module, "extract_images", None)
    original_extract_tables = getattr(operations_module, "extract_tables", None)
    original_add_image_stamp = getattr(operations_module, "add_image_stamp", None)

    def merge_pdfs(inputs, output):
        output_path = Path(output).resolve()
        input_paths = {Path(item).resolve() for item in inputs}
        if output_path in input_paths:
            raise ValueError("Выходной файл совпадает с одним из входных PDF.")
        return _run_busy("Сшивание PDF", original_merge_pdfs, inputs, output)

    def split_pdf(source, output_dir):
        src = Path(source)
        outdir = Path(output_dir)
        outdir.mkdir(parents=True, exist_ok=True)
        doc = fitz.open(src)
        outputs = []
        try:
            with _Busy("Разделение PDF"):
                for index in range(doc.page_count):
                    part = fitz.open()
                    try:
                        part.insert_pdf(doc, from_page=index, to_page=index)
                        base = outdir / f"{src.stem}_page_{index + 1:04d}.pdf"
                        target = base
                        suffix_number = 2
                        while target.exists():
                            target = base.with_name(
                                f"{base.stem}_{suffix_number}{base.suffix}"
                            )
                            suffix_number += 1
                        part.save(target, garbage=4, deflate=True)
                    finally:
                        part.close()
                    outputs.append(target)
                    _pump()
        finally:
            doc.close()
        return outputs

    def set_metadata(source, output, metadata):
        src = Path(source)
        dst = Path(output)
        dst.parent.mkdir(parents=True, exist_ok=True)

        def work():
            doc = fitz.open(src)
            try:
                current = dict(doc.metadata or {})
                current.update(
                    {key: value for key, value in metadata.items() if value is not None}
                )
                doc.set_metadata(current)
                if src.resolve() == dst.resolve():
                    temporary = dst.with_name(dst.stem + "_metadata_tmp.pdf")
                    try:
                        doc.save(temporary, garbage=4, deflate=True)
                        doc.close()
                        doc = None
                        os.replace(temporary, dst)
                    finally:
                        try:
                            temporary.unlink(missing_ok=True)
                        except OSError:
                            pass
                else:
                    doc.save(dst, garbage=4, deflate=True)
            finally:
                if doc is not None:
                    doc.close()
            return dst

        return _run_busy("Метаданные PDF", work)

    def compare_pdfs(left, right, output_dir, dpi=120, tolerance_px=3, ink_threshold=210):
        with fitz.open(left) as left_doc, fitz.open(right) as right_doc:
            if left_doc.page_count == 0 or right_doc.page_count == 0:
                raise ValueError("Один из PDF не содержит страниц.")
            scale = dpi / 72.0
            left_width = max((page.rect.width for page in left_doc), default=0.0)
            right_width = max((page.rect.width for page in right_doc), default=0.0)
            left_height = max((page.rect.height for page in left_doc), default=0.0)
            right_height = max((page.rect.height for page in right_doc), default=0.0)
            pixel_width = max(left_width, right_width) * scale
            pixel_height = max(left_height, right_height) * scale
            # Four full-page RGB images plus intermediate masks are retained.
            estimated_bytes = int(pixel_width * pixel_height * 12)
            if estimated_bytes > 512 * 1024 * 1024:
                raise ValueError(
                    "Сравнение при выбранном DPI требует слишком много памяти. "
                    "Уменьшите DPI или сравните документы меньшего размера."
                )
        return _run_busy(
            "Сравнение PDF",
            original_compare_pdfs,
            left,
            right,
            output_dir,
            dpi,
            tolerance_px,
            ink_threshold,
        )

    def add_text_watermark(source, output, text, opacity=0.22, fontsize=48,
                          rotation=45, color=(0.55, 0.55, 0.55)):
        text = str(text)
        if not text.strip():
            raise ValueError("Текст водяного знака не может быть пустым")
        opacity = max(0.05, min(float(opacity), 1.0))
        fontsize = float(fontsize)
        if fontsize <= 0:
            raise ValueError("Размер шрифта должен быть больше нуля")

        src = Path(source)
        dst = Path(output)
        dst.parent.mkdir(parents=True, exist_ok=True)

        has_cyrillic = any("\u0400" <= char <= "\u04ff" for char in text)
        font_path = operations_module._unicode_font_path() if has_cyrillic else None
        if has_cyrillic and font_path is None:
            raise RuntimeError(
                "Для кириллического водяного знака не найден системный Unicode-шрифт "
                "(например, Arial)."
            )

        with _Busy("Водяной знак"):
            doc = fitz.open(src)
            try:
                for page in doc:
                    rect = page.rect
                    text_width = 0.0
                    font_name = "PDFToolsUnicode" if font_path else "helv"
                    try:
                        text_width = page.get_text_length(
                            text, fontname=font_name, fontsize=fontsize,
                            fontfile=str(font_path) if font_path else None,
                        )
                    except Exception:
                        text_width = fontsize * 0.5 * len(text)
                    point = fitz.Point(
                        max(0.0, (rect.width - text_width) / 2.0),
                        rect.height / 2.0,
                    )
                    if font_path:
                        page.insert_text(
                            point, text, fontsize=fontsize, fontname="PDFToolsUnicode",
                            fontfile=str(font_path), color=color, fill_opacity=opacity,
                            morph=(point, fitz.Matrix(rotation)), overlay=True,
                        )
                    else:
                        page.insert_text(
                            point, text, fontsize=fontsize, fontname="helv",
                            color=color, fill_opacity=opacity,
                            morph=(point, fitz.Matrix(rotation)), overlay=True,
                        )
                    _pump()
                doc.save(dst, garbage=4, deflate=True)
            finally:
                doc.close()
        return dst

    if original_extract_images is not None:
        def extract_images(source, output_dir):
            return _run_busy(
                "Извлечение изображений",
                original_extract_images,
                source,
                output_dir,
            )

        operations_module.extract_images = extract_images
        app_module.extract_images = extract_images

    if original_extract_tables is not None:
        def extract_tables(source, output_dir):
            return _run_busy(
                "Извлечение таблиц",
                original_extract_tables,
                source,
                output_dir,
            )

        operations_module.extract_tables = extract_tables
        app_module.extract_tables = extract_tables

    if original_add_image_stamp is not None:
        def add_image_stamp(source, image, output, page_number, x, y, width):
            return _run_busy(
                "Штамп",
                original_add_image_stamp,
                source,
                image,
                output,
                page_number,
                x,
                y,
                width,
            )

        operations_module.add_image_stamp = add_image_stamp
        app_module.add_image_stamp = add_image_stamp

    operations_module.merge_pdfs = merge_pdfs
    operations_module.split_pdf = split_pdf
    operations_module.set_metadata = set_metadata
    operations_module.compare_pdfs = compare_pdfs
    operations_module.add_text_watermark = add_text_watermark

    # app.py imported these names by value, so update them too.
    app_module.merge_pdfs = merge_pdfs
    app_module.split_pdf = split_pdf
    app_module.set_metadata = set_metadata
    app_module.compare_pdfs = compare_pdfs
    app_module.add_text_watermark = add_text_watermark


def _patch_app():
    original_commit_stamp_at = StampEditorDialog.commit_stamp_at
    original_write_log = MainWindow.write_log
    original_batch_page = MainWindow._batch_page
    update_dialog = getattr(app_module, "UpdateDialog", None)
    original_update_download_finished = (
        update_dialog.on_download_finished if update_dialog is not None else None
    )
    original_update_dialog_init = (
        update_dialog.__init__ if update_dialog is not None else None
    )
    original_update_dialog_on_release = (
        update_dialog.on_release if update_dialog is not None else None
    )

    class _RepairWorker(QThread):
        finished_result = Signal(object, object)

        def __init__(self, pdf_path):
            super().__init__()
            self.pdf_path = pdf_path

        def run(self):
            try:
                from pdftools.core.repair import repair_file
                self.finished_result.emit(repair_file(self.pdf_path), None)
            except Exception as exc:  # noqa: BLE001 - reported to the GUI
                self.finished_result.emit(None, exc)

    def run_repair(self):
        if not (self.selected_pdf and self.selected_pdf.exists()):
            QMessageBox.information(
                self, "HotFix", "Сначала выберите PDF на главной странице."
            )
            return

        self.save_fixed_btn.setEnabled(False)
        self.repair_table.setRowCount(0)
        worker = _RepairWorker(self.selected_pdf)
        self._repair_worker = worker
        plaque = _plaque_for(self)
        plaque.start("Восстановление PDF")

        def on_finished(result, exc):
            self._repair_worker = None
            try:
                plaque.stop()
            except RuntimeError:
                pass
            if exc is not None:
                QMessageBox.critical(self, "HotFix", str(exc))
                return
            row = self.repair_table.rowCount()
            self.repair_table.insertRow(row)
            values = [
                str(result.src),
                "OK" if result.ok else "FAIL",
                str(result.method),
                str(result.pages) if result.pages else "—",
                str(result.out_path) if result.out_path else "—",
            ]
            for column, value in enumerate(values):
                from PySide6.QtWidgets import QTableWidgetItem
                self.repair_table.setItem(row, column, QTableWidgetItem(value))

            self.history.add(
                "HotFix",
                str(result.src),
                str(result.out_path) if result.out_path else "",
                "OK" if result.ok else "FAIL",
                " | ".join(result.log),
            )
            self.write_log(
                f"{values[1]} · {self.selected_pdf} · {result.method}"
            )

            if result.ok and result.out_path:
                self.fixed_pdf = Path(result.out_path)
                self.save_fixed_btn.setEnabled(True)
                QMessageBox.information(
                    self, "HotFix",
                    "Восстановление завершено. Теперь нажмите «Сохранить исправленный PDF».",
                )
            else:
                QMessageBox.warning(
                    self, "HotFix",
                    "Не удалось восстановить документ. Подробности находятся в журнале.",
                )

        worker.finished_result.connect(on_finished)
        try:
            worker.start()
        except Exception:
            self._repair_worker = None
            try:
                plaque.stop()
            except RuntimeError:
                pass
            raise

    def save_copy(self):
        if not self.placements:
            QMessageBox.information(
                self, "Сохранение", "Сначала разместите штамп на страницах."
            )
            return
        target = self.pdf_path.with_name(self.pdf_path.stem + "_ВПР.pdf")
        if target.exists():
            number = 2
            while self.pdf_path.with_name(
                f"{self.pdf_path.stem}_ВПР_{number}.pdf"
            ).exists():
                number += 1
            target = self.pdf_path.with_name(
                f"{self.pdf_path.stem}_ВПР_{number}.pdf"
            )
        try:
            self._save_to(target)
            self.saved_path = target
            self.accept()
        except Exception as exc:  # noqa: BLE001 - shown in the dialog
            QMessageBox.critical(self, "Ошибка сохранения копии", str(exc))

    def save_overwrite(self):
        if not self.placements:
            QMessageBox.information(
                self, "Сохранение", "Сначала разместите штамп на страницах."
            )
            return
        answer = QMessageBox.question(
            self, "Перезаписать PDF",
            "Сохранить изменения поверх текущего документа? Рекомендуется сначала сделать копию.",
        )
        if answer != QMessageBox.Yes:
            return

        temporary = self.pdf_path.with_name(self.pdf_path.stem + "_stamped_tmp.pdf")
        try:
            self._save_to(temporary)
            if getattr(self, "doc", None) is not None:
                self.doc.close()
                self.doc = None
            shutil.move(str(temporary), str(self.pdf_path))
            self.saved_path = self.pdf_path
            self.accept()
        except Exception as exc:  # noqa: BLE001 - shown in the dialog
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            try:
                if self.pdf_path.exists() and getattr(self, "doc", None) is None:
                    self.doc = fitz.open(self.pdf_path)
            except Exception:
                pass
            QMessageBox.critical(self, "Ошибка сохранения", str(exc))

    def undo_stamp(self):
        if getattr(self, "placement_active", False):
            self.placement_active = False
            self.ghost_item = None
            self.render_page()
            self.status_label.setText("Режим размещения отменён.")
            return

        stack = getattr(self, "_undo_stack", None)
        if not stack:
            return
        page_index, placement = stack.pop()
        page_items = self.placements.get(page_index)
        if page_items is not None and placement in page_items:
            page_items.remove(placement)
            if not page_items:
                self.placements.pop(page_index, None)
        self.page_index = page_index
        self.render_page()
        self.status_label.setText("Последнее размещение штампа отменено.")

    def commit_stamp_at(self, scene_pos):
        if not (
            getattr(self, "placement_active", False)
            and getattr(self, "current_stamp_path", None)
            and getattr(self, "ghost_item", None) is not None
        ):
            return

        page_rect = self.scene.sceneRect()
        ghost_rect = self.ghost_item.sceneBoundingRect()
        x_scene = scene_pos.x() - ghost_rect.width() / 2.0
        y_scene = scene_pos.y() - ghost_rect.height() / 2.0
        x_scene = max(
            0.0,
            min(x_scene, page_rect.width() - ghost_rect.width()),
        )
        y_scene = max(
            0.0,
            min(y_scene, page_rect.height() - ghost_rect.height()),
        )
        width_scene = ghost_rect.width()

        placement = {
            "path": str(self.current_stamp_path),
            "x": x_scene / self.render_scale,
            "y": y_scene / self.render_scale,
            "width": width_scene / self.render_scale,
        }
        self.placements.setdefault(self.page_index, []).append(placement)
        self._undo_stack = getattr(self, "_undo_stack", [])
        self._undo_stack.append((self.page_index, placement))
        self.undo_state = (self.page_index, placement)
        self.stamp_item = None

        if self.page_index < self.doc.page_count - 1:
            self.page_index += 1
            self.render_page()
            self.status_label.setText(
                "Штамп установлен на странице "
                + str(self.page_index)
                + ". Тот же штамп следует за курсором — щёлкните для следующей страницы."
            )
            return

        self.placement_active = False
        self.ghost_item = None
        self.render_page()
        total = sum(len(items) for items in self.placements.values())
        QMessageBox.information(
            self, "Штампование завершено",
            "Все страницы документа проштампованы.\nРазмещено штампов: "
            + str(total) + ".",
        )

    def closeEvent(self, event):
        placements = getattr(self, "placements", None)
        unsaved = bool(placements) and str(
            getattr(self, "saved_path", None)
        ) != str(getattr(self, "pdf_path", None))
        if unsaved:
            answer = QMessageBox.question(
                self, "Закрытие",
                "Есть несохранённые штампы. Закрыть без сохранения?",
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
        if getattr(self, "doc", None) is not None:
            self.doc.close()
        super(StampEditorDialog, self).closeEvent(event)

    def write_log(self, message):
        self.log.appendPlainText(message)
        document = self.log.document()
        if document.blockCount() > 5000:
            cursor = QTextCursor(document)
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(
                QTextCursor.Down, QTextCursor.KeepAnchor,
                document.blockCount() - 5000,
            )
            cursor.removeSelectedText()

    def _batch_page(self):
        page = original_batch_page(self)
        workspace = getattr(self, "pdf_workspace", None)
        if workspace is not None:
            old_filter = getattr(self, "_workspace_drop_filter", None)
            if old_filter is not None:
                try:
                    workspace.removeEventFilter(old_filter)
                    workspace.viewport().removeEventFilter(old_filter)
                except RuntimeError:
                    pass
                old_filter.deleteLater()
            _configure_workspace(workspace)
            drop_filter = _WorkspaceDropFilter(workspace)
            workspace.installEventFilter(drop_filter)
            workspace.viewport().installEventFilter(drop_filter)
            self._workspace_drop_filter = drop_filter
        return page

    def add_pdfs_to_workspace(self, paths=None):
        workspace = getattr(self, "pdf_workspace", None)
        if workspace is None:
            return

        if paths is None:
            paths, _ = QFileDialog.getOpenFileNames(
                self, "Добавить PDF-документы", "", "PDF (*.pdf)"
            )
        if not paths:
            return

        try:
            with _Busy("Добавление PDF"):
                for path in paths:
                    document = fitz.open(path)
                    try:
                        for page_no in range(document.page_count):
                            page = document.load_page(page_no)
                            pixmap = page.get_pixmap(
                                matrix=fitz.Matrix(0.34, 0.34),
                                alpha=False,
                            )
                            image = QImage(
                                pixmap.samples,
                                pixmap.width,
                                pixmap.height,
                                pixmap.stride,
                                QImage.Format_RGB888,
                            ).copy()
                            item = QListWidgetItem(
                                QIcon(QPixmap.fromImage(image)),
                                f"{Path(path).name}\nСтраница {page_no + 1}",
                            )
                            item.setData(
                                Qt.UserRole,
                                (str(Path(path).resolve()), page_no),
                            )
                            item.setToolTip(str(Path(path).resolve()))
                            item.setFlags(
                                item.flags()
                                | Qt.ItemIsDragEnabled
                                | Qt.ItemIsDropEnabled
                            )
                            workspace.addItem(item)
                            _pump()
                    finally:
                        document.close()
        except Exception as exc:  # noqa: BLE001 - reported to the GUI
            QMessageBox.critical(self, "Ошибка чтения PDF", str(exc))
            return

        _configure_workspace(workspace)
        update_count = getattr(self, "update_workspace_count", None)
        if callable(update_count):
            update_count()
        self.write_log(f"Добавлено PDF: {len(paths)}")

    def save_pdf_workspace(self):
        workspace = getattr(self, "pdf_workspace", None)
        if workspace is None or workspace.count() == 0:
            QMessageBox.information(
                self, "Сохранение PDF",
                "Сначала добавьте хотя бы один PDF-документ.",
            )
            return

        target, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить собранный PDF",
            "Объединённый документ.pdf",
            "PDF (*.pdf)",
        )
        if not target:
            return
        if not target.lower().endswith(".pdf"):
            target += ".pdf"

        result = None
        cache = {}
        try:
            with _Busy("Сборка PDF"):
                result = fitz.open()
                for index in range(workspace.count()):
                    source_path, page_no = workspace.item(index).data(Qt.UserRole)
                    source_path = Path(source_path)
                    if source_path not in cache:
                        cache[source_path] = fitz.open(source_path)
                    result.insert_pdf(
                        cache[source_path],
                        from_page=page_no,
                        to_page=page_no,
                    )
                    _pump()
                result.save(target, garbage=4, deflate=True)

            sources = []
            for index in range(workspace.count()):
                source_path, _ = workspace.item(index).data(Qt.UserRole)
                if source_path not in sources:
                    sources.append(source_path)
            self.history.add(
                "Сборка PDF",
                "; ".join(sources),
                target,
                f"{workspace.count()} страниц",
                "",
            )
            self.write_log(f"Собран PDF: {target}")
            QMessageBox.information(
                self, "Сохранение PDF",
                f"PDF сохранён:\n{target}",
            )
        except Exception as exc:  # noqa: BLE001 - reported to the GUI
            QMessageBox.critical(self, "Ошибка сохранения PDF", str(exc))
        finally:
            if result is not None:
                try:
                    result.close()
                except Exception:
                    pass
            for document in cache.values():
                try:
                    document.close()
                except Exception:
                    pass

    def update_dialog_init(self, *args, **kwargs):
        original_update_dialog_init(self, *args, **kwargs)
        self.setMinimumWidth(620)
        self.setMinimumHeight(360)
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(28)
        self.detail.setWordWrap(True)
        self.detail.setMinimumHeight(170)
        self.detail.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        layout = self.layout()
        if layout is not None:
            layout.setStretchFactor(self.detail, 1)
        self.resize(620, 360)

    def update_dialog_on_release(self, result):
        original_update_dialog_on_release(self, result)
        phrase = "Настройки, история и библиотека штампов сохраняются."
        text = self.detail.text()
        if phrase in text:
            text = escape(text).replace(
                escape(phrase), f"<b>{escape(phrase)}</b>"
            )
            self.detail.setTextFormat(Qt.RichText)
            self.detail.setText(text)
        self.setMinimumWidth(620)
        self.setMinimumHeight(360)
        self.resize(620, 360)

    def on_download_finished(self, result):
        original_question = QMessageBox.question

        def question(parent, title, text, *args, **kwargs):
            if not (
                isinstance(text, str)
                and "Архив загружен и SHA256 совпадает." in text
            ):
                return original_question(parent, title, text, *args, **kwargs)

            prefix = "Архив загружен и SHA256 совпадает.\n\nФайл: "
            if text.startswith(prefix):
                archive = text[len(prefix):].split("\n\nПродолжить?")[0]
                text = (
                    "<div style='font-size:15pt; font-weight:700;'>"
                    "Архив загружен и SHA256 совпадает.<br><br>"
                    f"Файл: {escape(archive)}<br><br>"
                    f"{escape(UPDATE_CONFIRM_NOTE)}<br><br>"
                    "Продолжить?"
                    "</div>"
                )
            else:
                text = text.replace(
                    "\n\nПродолжить?",
                    f"\n\n{UPDATE_CONFIRM_NOTE}\n\nПродолжить?",
                )

            box = QMessageBox(parent)
            box.setWindowTitle(title)
            box.setIcon(QMessageBox.Question)
            box.setTextFormat(Qt.RichText)
            box.setText(text)
            app = QApplication.instance()
            base_style = app.styleSheet() if app is not None else ""
            if not base_style:
                base_style = getattr(app_module, "DARK_QSS", "")
            box.setStyleSheet(
                base_style
                + """
                QMessageBox { background: #171a21; }
                QMessageBox QLabel { color: #e8eaf0; }
                QMessageBox QPushButton {
                    min-width: 120px;
                    text-align: center;
                    font-size: 10pt;
                    font-weight: 600;
                }
                """
            )
            yes_button = box.addButton("Продолжить", QMessageBox.YesRole)
            box.addButton("Отмена", QMessageBox.NoRole)
            box.setDefaultButton(yes_button)
            box.exec()
            if box.clickedButton() is yes_button:
                return QMessageBox.Yes
            return QMessageBox.No

        QMessageBox.question = question
        try:
            return original_update_download_finished(self, result)
        finally:
            QMessageBox.question = original_question

    MainWindow._batch_page = _batch_page
    MainWindow.add_pdfs_to_workspace = add_pdfs_to_workspace
    MainWindow.save_pdf_workspace = save_pdf_workspace
    MainWindow.run_repair = run_repair
    MainWindow.write_log = write_log
    if update_dialog is not None:
        update_dialog.__init__ = update_dialog_init
        update_dialog.on_release = update_dialog_on_release
        update_dialog.on_download_finished = on_download_finished
    StampEditorDialog.save_copy = save_copy
    StampEditorDialog.save_overwrite = save_overwrite
    StampEditorDialog.undo_stamp = undo_stamp
    StampEditorDialog.commit_stamp_at = commit_stamp_at
    StampEditorDialog.closeEvent = closeEvent


_patch_history()
_patch_operations()
_patch_app()
