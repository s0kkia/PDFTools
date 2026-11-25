from __future__ import annotations
import sys
import shutil
import os
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QSize, QPointF
from PySide6.QtGui import QPixmap, QImage, QIcon, QPainter
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QStackedWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QPlainTextEdit, QProgressBar, QMessageBox, QLineEdit, QComboBox,
    QFormLayout, QGroupBox, QInputDialog, QDialog, QDialogButtonBox,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsItem, QListWidget, QListWidgetItem,
    QSplitter, QToolButton, QAbstractItemView
)
from pdftools import __version__
from pdftools.core.repair import repair_file
from pdftools.core.operations import (merge_pdfs, split_pdf, set_metadata,
    add_image_stamp, add_text_watermark, compare_pdfs, extract_images, extract_tables)
from pdftools.core.history import HistoryStore
from pdftools.services import updater
from pdftools.services.data_paths import data_dir
from pdftools.ui.theme import DARK_QSS


def resource_path(relative_path: str) -> str:
    """Resolve bundled resources in development and PyInstaller builds."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return str(base / relative_path)


class Job(QThread):
    progress = Signal(int, int)
    log = Signal(str)
    finished_one = Signal(object)

    def __init__(self, task, *args, **kwargs):
        super().__init__()
        self.task, self.args, self.kwargs = task, args, kwargs

    def run(self):
        try:
            result = self.task(*self.args, **self.kwargs)
            self.finished_one.emit(result)
        except Exception as exc:
            self.finished_one.emit(exc)


class UpdateDownloadJob(QThread):
    progress = Signal(int, int)
    finished_one = Signal(object)

    def __init__(self, release):
        super().__init__()
        self.release = release

    def run(self):
        try:
            result = updater.download_and_verify(self.release,
                lambda received, total: self.progress.emit(received, total))
            self.finished_one.emit(result)
        except Exception as exc:
            self.finished_one.emit(exc)


class UpdateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Обновление PDFTools")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        self.status = QLabel("Проверка доступной версии…")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.detail = QLabel("Подключение к GitHub Releases")
        self.detail.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addWidget(self.detail)
        self.action_btn = QPushButton("Скачать и установить")
        self.action_btn.setEnabled(False)
        self.action_btn.clicked.connect(self.download_update)
        layout.addWidget(self.action_btn)
        self.close_btn = QPushButton("Закрыть")
        self.close_btn.clicked.connect(self.reject)
        layout.addWidget(self.close_btn)
        self.release = None
        self.download_job = None
        self.worker = Job(updater.latest_release)
        self.worker.finished_one.connect(self.on_release)
        self.worker.start()

    def on_release(self, result):
        if isinstance(result, Exception):
            self.status.setText("Не удалось проверить обновление")
            self.detail.setText(str(result))
            return
        self.release = result
        latest = result.get("tag_name", "").lstrip("v")
        current = __version__.lstrip("v")
        self.status.setText(f"Установленная версия: {__version__} · Последняя версия: {result.get('tag_name', 'неизвестно')}")
        if not updater.is_newer(latest, current):
            self.detail.setText("У вас установлена последняя версия PDFTools.")
            self.action_btn.setVisible(False)
            self.progress.setValue(100)
            return
        assets = {a.get("name"): a for a in result.get("assets", [])}
        if updater.PACKAGE_NAME not in assets or updater.CHECKSUM_NAME not in assets:
            self.detail.setText("Релиз найден, но в нём отсутствует архив программы или файл контрольной суммы.")
            return
        self.detail.setText("Доступно обновление. Настройки, история и библиотека штампов сохраняются.")
        self.action_btn.setEnabled(True)

    def download_update(self):
        if not self.release:
            return
        self.action_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.status.setText("Загрузка обновления…")
        self.detail.setText("Загрузка архива и проверка SHA256.")
        self.progress.setRange(0, 100)
        self.download_job = UpdateDownloadJob(self.release)
        self.download_job.progress.connect(self.on_download_progress)
        self.download_job.finished_one.connect(self.on_download_finished)
        self.download_job.start()

    def on_download_progress(self, received, total):
        if total > 0:
            self.progress.setValue(int(received * 100 / total))
            self.detail.setText(f"Загружено {received / 1024 / 1024:.1f} из {total / 1024 / 1024:.1f} МБ")
        else:
            self.progress.setRange(0, 0)
            self.detail.setText(f"Загружено {received / 1024 / 1024:.1f} МБ")

    def on_download_finished(self, result):
        if isinstance(result, Exception):
            self.status.setText("Не удалось загрузить обновление")
            self.detail.setText(str(result))
            self.action_btn.setEnabled(True)
            self.close_btn.setEnabled(True)
            return
        self.progress.setValue(100)
        archive_path = result / updater.PACKAGE_NAME
        self.status.setText("Обновление скачано и проверено")
        self.detail.setText(f"Архив сохранён: {archive_path}")
        answer = QMessageBox.question(self, "Установка обновления",
            f"Архив загружен и SHA256 совпадает.\n\nФайл: {archive_path}\n\nПЕРЕЗАПУСК МОЖЕТ ЗАТЯНУТЬСЯ! НЕ ПУГАЙТЕСЬ — PDFTOOLS НЕ ЗАВИС, А ПРОСТО СОБИРАЕТСЯ С НОВЫМИ СИЛАМИ. 😄\n\nПродолжить?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if answer != QMessageBox.Yes:
            updater.cleanup_download(result)
            self.status.setText("Установка отменена. Временные файлы удалены.")
            self.detail.setText("Архив и распакованные файлы удалены. Журнал предыдущих обновлений сохранён.")
            self.close_btn.setEnabled(True)
            return
        try:
            log_path = updater.launch_update(result, Path(sys.executable).resolve().parent, os.getpid())
            self.status.setText("Подготовка установки…")
            self.detail.setText(f"Программа закроется. Журнал установки: {log_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка обновления", str(exc))
            self.close_btn.setEnabled(True)
            return
        self.accept()
        QApplication.quit()


class StampGraphicsView(QGraphicsView):
    mouse_scene_moved = Signal(QPointF)
    mouse_scene_clicked = Signal(QPointF)
    wheel_zoom = Signal(int)

    def mouseMoveEvent(self, event):
        self.mouse_scene_moved.emit(self.mapToScene(event.position().toPoint()))
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.mouse_scene_clicked.emit(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta:
            self.wheel_zoom.emit(1 if delta > 0 else -1)
            event.accept()
            return
        super().wheelEvent(event)


class StampEditorDialog(QDialog):
    """Interactive PDF stamp placement editor with movable stamp and stamp library."""
    def __init__(self, parent, pdf_path: Path):
        super().__init__(parent)
        self.setWindowTitle("PDFTools — Простановка штампа")
        self.resize(1450, 900)
        self.pdf_path = Path(pdf_path)
        self.saved_path = None
        self.doc = None
        self.page_index = 0
        self.render_scale = 1.35
        self.current_stamp_path = None
        self.stamp_item = None
        self.ghost_item = None
        self.placements = {}  # page index -> {path, x, y, width}
        self.last_cursor_pos = QPointF(80, 80)
        self.placement_active = False
        self.undo_state = None
        self.stamp_dir = data_dir("stamps")
        self.stamp_dir.mkdir(parents=True, exist_ok=True)
        self._build_ui()
        self._load_document()
        self._load_stamps()

    def _build_ui(self):
        root = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.prev_btn = QPushButton("◀")
        self.prev_btn.clicked.connect(lambda: self.change_page(-1))
        toolbar.addWidget(self.prev_btn)
        toolbar.addWidget(QLabel("Страница:"))
        self.page_combo = QComboBox()
        self.page_combo.currentIndexChanged.connect(self.goto_page)
        self.page_combo.setMinimumWidth(85)
        toolbar.addWidget(self.page_combo)
        self.page_count_label = QLabel("из ?")
        toolbar.addWidget(self.page_count_label)
        self.next_btn = QPushButton("▶")
        self.next_btn.clicked.connect(lambda: self.change_page(1))
        toolbar.addWidget(self.next_btn)
        toolbar.addSpacing(12)
        toolbar.addWidget(QLabel("Масштаб:"))
        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems(["50%", "75%", "100%", "125%", "150%", "200%"])
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.currentTextChanged.connect(self.render_page)
        toolbar.addWidget(self.zoom_combo)
        toolbar.addSpacing(12)
        toolbar.addWidget(QLabel("Штамп:"))
        self.stamp_scale_combo = QComboBox()
        self.stamp_scale_combo.addItems([f"{v}%" for v in range(0, 101, 10)])
        self.stamp_scale_combo.setCurrentText("70%")
        self.stamp_scale_combo.currentTextChanged.connect(self.update_stamp_scale)
        toolbar.addWidget(self.stamp_scale_combo)
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_overwrite)
        toolbar.addWidget(self.save_btn)
        self.save_copy_btn = QPushButton("Сохранить копию с _ВПР")
        self.save_copy_btn.setObjectName("Primary")
        self.save_copy_btn.clicked.connect(self.save_copy)
        toolbar.addWidget(self.save_copy_btn)
        self.undo_btn = QPushButton("Отменить")
        self.undo_btn.clicked.connect(self.undo_stamp)
        toolbar.addWidget(self.undo_btn)
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.reject)
        toolbar.addWidget(close_btn)
        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal)
        self.scene = QGraphicsScene(self)
        self.view = StampGraphicsView(self.scene)
        self.view.mouse_scene_moved.connect(self.move_ghost)
        self.view.mouse_scene_clicked.connect(self.commit_stamp_at)
        self.view.wheel_zoom.connect(self.zoom_with_wheel)
        self.view.setMouseTracking(True)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.view.setDragMode(QGraphicsView.NoDrag)
        self.view.setBackgroundBrush(Qt.darkGray)
        self.view.setAlignment(Qt.AlignCenter)
        splitter.addWidget(self.view)

        side = QWidget()
        side.setMinimumWidth(210)
        side.setMaximumWidth(300)
        side_layout = QVBoxLayout(side)
        side_layout.addWidget(QLabel("БИБЛИОТЕКА ШТАМПОВ"))
        self.stamp_list = QListWidget()
        self.stamp_list.setViewMode(QListWidget.IconMode)
        self.stamp_list.setIconSize(QSize(110, 90))
        self.stamp_list.setGridSize(QSize(145, 125))
        self.stamp_list.setResizeMode(QListWidget.Adjust)
        self.stamp_list.setMovement(QListWidget.Static)
        self.stamp_list.itemClicked.connect(self.select_stamp_item)
        side_layout.addWidget(self.stamp_list, 1)
        add_btn = QPushButton("＋ Добавить штампы")
        add_btn.clicked.connect(self.add_stamps)
        side_layout.addWidget(add_btn)
        remove_btn = QPushButton("Удалить из библиотеки")
        remove_btn.clicked.connect(self.remove_stamp)
        side_layout.addWidget(remove_btn)
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 1)
        splitter.setSizes([1100, 250])
        root.addWidget(splitter, 1)
        self.status_label = QLabel("Выберите штамп справа. Он будет следовать за курсором; щёлкните для размещения на странице.")
        root.addWidget(self.status_label)

    def _load_document(self):
        try:
            import pymupdf
            self.doc = pymupdf.open(self.pdf_path)
            if self.doc.page_count < 1:
                raise ValueError("PDF не содержит страниц")
            self.page_combo.blockSignals(True)
            self.page_combo.clear()
            self.page_combo.addItems([str(i + 1) for i in range(self.doc.page_count)])
            self.page_combo.blockSignals(False)
            self.page_count_label.setText(f"из {self.doc.page_count}")
            self.render_page()
        except Exception as exc:
            QMessageBox.critical(self, "Не удалось открыть PDF", str(exc))
            self.reject()

    def render_page(self, *_):
        if not self.doc:
            return
        try:
            self.scene.clear()
            self.stamp_item = None
            self.ghost_item = None
            zoom = float(self.zoom_combo.currentText().replace("%", "")) / 100
            self.render_scale = 1.25 * zoom
            page = self.doc.load_page(self.page_index)
            pix = page.get_pixmap(matrix=__import__("pymupdf").Matrix(self.render_scale, self.render_scale), alpha=False)
            image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
            page_item = self.scene.addPixmap(QPixmap.fromImage(image))
            page_item.setZValue(0)
            self.scene.setSceneRect(page_item.boundingRect())

            # Restore already placed stamps on this page.
            for placement in self.placements.get(self.page_index, []):
                stamp_pix = QPixmap(str(placement["path"]))
                if stamp_pix.isNull():
                    continue
                item = QGraphicsPixmapItem(stamp_pix)
                item.setZValue(5)
                item.setAcceptedMouseButtons(Qt.NoButton)
                item.setScale(placement["width"] * self.render_scale / max(1, stamp_pix.width()))
                item.setPos(placement["x"] * self.render_scale, placement["y"] * self.render_scale)
                self.scene.addItem(item)

            self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
            self.prev_btn.setEnabled(self.page_index > 0)
            self.next_btn.setEnabled(self.page_index < self.doc.page_count - 1)
            self.page_combo.blockSignals(True)
            self.page_combo.setCurrentIndex(self.page_index)
            self.page_combo.blockSignals(False)

            if self.placement_active and self.current_stamp_path:
                self._create_ghost()
                self.status_label.setText(
                    f"Страница {self.page_index + 1}/{self.doc.page_count}: щёлкните мышью, чтобы поставить штамп."
                )
            else:
                self.status_label.setText(f"Страница {self.page_index + 1}/{self.doc.page_count}. Выберите штамп справа.")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка отображения страницы", str(exc))

    def zoom_with_wheel(self, direction):
        values = [int(self.zoom_combo.itemText(i).replace("%", "")) for i in range(self.zoom_combo.count())]
        current = int(self.zoom_combo.currentText().replace("%", ""))
        idx = values.index(current) if current in values else 2
        next_idx = max(0, min(len(values)-1, idx + direction))
        if next_idx != idx:
            self.zoom_combo.setCurrentIndex(next_idx)

    def move_ghost(self, scene_pos):
        self.last_cursor_pos = scene_pos
        if self.ghost_item and self.placement_active:
            self.ghost_item.setPos(scene_pos.x() - self.ghost_item.boundingRect().width() * self.ghost_item.scale()/2,
                                   scene_pos.y() - self.ghost_item.boundingRect().height() * self.ghost_item.scale()/2)

    def _create_ghost(self):
        if not self.current_stamp_path:
            return
        pix = QPixmap(str(self.current_stamp_path))
        if pix.isNull():
            return
        self.ghost_item = QGraphicsPixmapItem(pix)
        self.ghost_item.setZValue(20)
        self.ghost_item.setOpacity(0.55)
        self.ghost_item.setAcceptedMouseButtons(Qt.NoButton)
        self.scene.addItem(self.ghost_item)
        self.update_stamp_scale(self.stamp_scale_combo.currentText())
        self.move_ghost(self.last_cursor_pos)

    def commit_stamp_at(self, scene_pos):
        if not self.placement_active or not self.current_stamp_path or not self.ghost_item:
            return
        page_rect = self.scene.sceneRect()
        ghost_rect = self.ghost_item.sceneBoundingRect()
        # Position is based on the center of the ghost under the cursor.
        x_scene = scene_pos.x() - ghost_rect.width()/2
        y_scene = scene_pos.y() - ghost_rect.height()/2
        x_scene = max(0, min(x_scene, page_rect.width() - ghost_rect.width()))
        y_scene = max(0, min(y_scene, page_rect.height() - ghost_rect.height()))
        width_scene = ghost_rect.width()
        placement = {
            "path": str(self.current_stamp_path),
            "x": x_scene / self.render_scale,
            "y": y_scene / self.render_scale,
            "width": width_scene / self.render_scale,
        }
        self.placements.setdefault(self.page_index, []).append(placement)
        self.undo_state = (self.page_index, placement)
        self.stamp_item = None

        if self.page_index < self.doc.page_count - 1:
            self.page_index += 1
            self.render_page()
            self.status_label.setText(
                f"Штамп установлен на странице {self.page_index}. Тот же штамп следует за курсором — щёлкните для следующей страницы."
            )
        else:
            self.placement_active = False
            self.ghost_item = None
            self.render_page()
            total = sum(len(items) for items in self.placements.values())
            QMessageBox.information(
                self, "Штампование завершено",
                f"Все страницы документа проштампованы.\nРазмещено штампов: {total}."
            )

    def change_page(self, delta):
        target = max(0, min(self.doc.page_count - 1, self.page_index + delta))
        self.page_combo.setCurrentIndex(target)

    def goto_page(self, index):
        if index < 0 or not self.doc or index >= self.doc.page_count:
            return
        self.page_index = index
        self.render_page()

    def _load_stamps(self):
        self.stamp_list.clear()
        supported = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
        paths = sorted([p for p in self.stamp_dir.iterdir() if p.suffix.lower() in supported])
        for path in paths:
            pix = QPixmap(str(path))
            if pix.isNull():
                continue
            item = QListWidgetItem(QIcon(pix), path.stem)
            item.setData(Qt.UserRole, str(path))
            item.setToolTip(str(path))
            self.stamp_list.addItem(item)

    def add_stamps(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Добавить изображения штампов", "",
                                                 "Изображения (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)")
        for source in paths:
            src = Path(source)
            target = self.stamp_dir / src.name
            if target.exists():
                target = self.stamp_dir / f"{src.stem}_{len(list(self.stamp_dir.glob(src.stem + '*')))+1}{src.suffix}"
            try:
                import shutil
                shutil.copy2(src, target)
            except Exception as exc:
                QMessageBox.warning(self, "Не удалось добавить штамп", f"{src.name}: {exc}")
        self._load_stamps()

    def remove_stamp(self):
        item = self.stamp_list.currentItem()
        if not item:
            return
        path = Path(item.data(Qt.UserRole))
        answer = QMessageBox.question(self, "Удалить штамп", f"Удалить {path.name} из библиотеки?")
        if answer == QMessageBox.Yes:
            path.unlink(missing_ok=True)
            self._load_stamps()

    def select_stamp_item(self, item):
        self.current_stamp_path = Path(item.data(Qt.UserRole))
        self.place_stamp()

    def place_stamp(self):
        if not self.current_stamp_path or not self.current_stamp_path.is_file():
            return
        self.placement_active = True
        self._create_ghost()
        self.status_label.setText(
            "Штамп привязан к курсору. Щёлкните в нужном месте листа для установки."
        )

    def update_stamp_scale(self, value):
        if not self.ghost_item:
            return
        percent = int(value.replace("%", ""))
        if percent == 0:
            self.ghost_item.setVisible(False)
            self.status_label.setText("Масштаб 0% — предварительный просмотр штампа скрыт.")
            return
        self.ghost_item.setVisible(True)
        pix_width = max(1, self.ghost_item.pixmap().width())
        target_scene_width = 180.0 * percent / 100.0 * self.render_scale
        self.ghost_item.setScale(target_scene_width / pix_width)
        self.move_ghost(self.last_cursor_pos)
        self.status_label.setText(f"Масштаб штампа: {percent}%. Щёлкните для размещения.")

    def undo_stamp(self):
        if self.undo_state:
            page_index, placement = self.undo_state
            page_items = self.placements.get(page_index, [])
            if placement in page_items:
                page_items.remove(placement)
                if not page_items:
                    self.placements.pop(page_index, None)
            self.undo_state = None
            self.page_index = page_index
            self.render_page()
            self.status_label.setText("Последнее размещение штампа отменено.")
        elif self.placement_active:
            self.placement_active = False
            self.ghost_item = None
            self.render_page()
            self.status_label.setText("Режим размещения отменён.")

    def _save_to(self, target: Path):
        if not self.placements:
            raise ValueError("Сначала разместите штамп хотя бы на одной странице.")
        import pymupdf
        out_doc = pymupdf.open(self.pdf_path)
        try:
            for page_index, placements in self.placements.items():
                page = out_doc.load_page(page_index)
                for placement in placements:
                    x, y, width = placement["x"], placement["y"], placement["width"]
                    stamp_pix = QPixmap(placement["path"])
                    if stamp_pix.isNull():
                        raise FileNotFoundError(f"Не найден штамп: {placement['path']}")
                    height = width * stamp_pix.height() / max(1, stamp_pix.width())
                    rect = pymupdf.Rect(x, y, x + width, y + height)
                    page.insert_image(rect, filename=placement["path"], overlay=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            out_doc.save(target, garbage=4, deflate=True)
        finally:
            out_doc.close()
        self.saved_path = target

    def save_overwrite(self):
        if not self.placements:
            QMessageBox.information(self, "Сохранение", "Сначала разместите штамп на страницах.")
            return
        answer = QMessageBox.question(
            self, "Перезаписать PDF",
            "Сохранить изменения поверх текущего документа? Рекомендуется сначала сделать копию."
        )
        if answer != QMessageBox.Yes:
            return
        temp = self.pdf_path.with_name(self.pdf_path.stem + "_stamped_tmp.pdf")
        try:
            self._save_to(temp)
            if self.doc:
                self.doc.close()
                self.doc = None
            import shutil
            shutil.move(str(temp), str(self.pdf_path))
            self.saved_path = self.pdf_path
            self.accept()
        except Exception as exc:
            temp.unlink(missing_ok=True)
            QMessageBox.critical(self, "Ошибка сохранения", str(exc))

    def save_copy(self):
        if not self.placements:
            QMessageBox.information(self, "Сохранение", "Сначала разместите штамп на страницах.")
            return
        target = self.pdf_path.with_name(f"{self.pdf_path.stem}_ВПР.pdf")
        if target.exists():
            target = self.pdf_path.with_name(f"{self.pdf_path.stem}_ВПР_2.pdf")
        try:
            self._save_to(target)
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка сохранения копии", str(exc))

    def closeEvent(self, event):
        if self.doc:
            self.doc.close()
        super().closeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"PDFTools {__version__}")
        self.setWindowIcon(QIcon(resource_path("PDFTools.ico")))
        self.resize(1280, 820)
        self.history = HistoryStore()
        self.job = None
        self.selected_pdf: Path | None = None
        self.fixed_pdf: Path | None = None
        self._build()

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(230)
        side = QVBoxLayout(sidebar)
        brand = QLabel("PDFTools")
        brand.setStyleSheet("font-size:22pt;font-weight:800;padding:14px 8px;")
        side.addWidget(brand)
        side.addWidget(QLabel("РАБОЧЕЕ ПРОСТРАНСТВО"))
        self.stack = QStackedWidget()
        self.pages = {}
        nav = [
            ("Главная", self._dashboard),
            ("HotFix · Восстановление", self._repair_page),
            ("Обработка PDF", self._batch_page),
            ("Штамп", self._stamp_page),
            ("Сравнение PDF", self._compare_page),
            ("История", self._history_page),
        ]
        for name, factory in nav:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked=False, n=name: self.show_page(n))
            side.addWidget(btn)
            self.pages[name] = factory()
            self.stack.addWidget(self.pages[name])
        side.addStretch()
        update_btn = QPushButton("Проверить обновления")
        update_btn.clicked.connect(self.check_updates)
        side.addWidget(update_btn)
        version = QLabel(f"Версия {__version__}")
        version.setObjectName("Muted")
        side.addWidget(version)
        outer.addWidget(sidebar)
        content = QVBoxLayout()
        self.page_title = QLabel("Главная")
        self.page_title.setObjectName("Title")
        content.addWidget(self.page_title)
        content.addWidget(self.stack, 1)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        self.log.setPlaceholderText("Журнал операций")
        content.addWidget(self.log)
        outer.addLayout(content, 1)
        self.show_page("Главная")

    def _simple_page(self, title, description):
        page = QWidget()
        layout = QVBoxLayout(page)
        card = QGroupBox(title)
        form = QVBoxLayout(card)
        label = QLabel(description)
        label.setWordWrap(True)
        form.addWidget(label)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _dashboard(self):
        p = QWidget(); l = QVBoxLayout(p)
        welcome = QLabel("Рабочее пространство для PDF-документов")
        welcome.setStyleSheet("font-size:17pt;font-weight:600;")
        l.addWidget(welcome)
        l.addWidget(QLabel("1. Выберите документ.  2. При необходимости восстановите его через HotFix.  3. Перейдите к штампу или водяному знаку."))
        file_group = QGroupBox("Текущий документ")
        fg = QVBoxLayout(file_group)
        self.selected_pdf_label = QLabel("Документ не выбран")
        self.selected_pdf_label.setWordWrap(True)
        fg.addWidget(self.selected_pdf_label)
        actions = QHBoxLayout()
        choose = QPushButton("Добавить / выбрать PDF")
        choose.setObjectName("Primary")
        choose.clicked.connect(self.choose_main_pdf)
        clear = QPushButton("Очистить выбор")
        clear.clicked.connect(self.clear_main_pdf)
        actions.addWidget(choose); actions.addWidget(clear); actions.addStretch()
        fg.addLayout(actions)
        l.addWidget(file_group)
        row = QHBoxLayout()
        for title, desc, target in [
            ("HotFix", "Восстановить выбранный PDF", "HotFix · Восстановление"),
            ("Штамп", "Поставить подпись или печать", "Штамп"),
        ]:
            box = QGroupBox(title); v = QVBoxLayout(box); v.addWidget(QLabel(desc))
            b = QPushButton("Перейти")
            b.clicked.connect(lambda checked=False, n=target: self.open_selected_page(n))
            v.addWidget(b); row.addWidget(box)
        l.addLayout(row)
        l.addStretch()
        return p

    def choose_main_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать основной PDF", "", "PDF (*.pdf)")
        if path:
            self.set_selected_pdf(path)

    def set_selected_pdf(self, path):
        self.selected_pdf = Path(path).expanduser().resolve()
        if hasattr(self, "selected_pdf_label"):
            self.selected_pdf_label.setText(str(self.selected_pdf))
        if hasattr(self, "stamp_src"):
            self.stamp_src.setText(str(self.selected_pdf))
        if hasattr(self, "watermark_src"):
            self.watermark_src.setText(str(self.selected_pdf))
        if hasattr(self, "compare_a"):
            self.compare_a.setText(str(self.selected_pdf))
        if hasattr(self, "comp_src"):
            self.comp_src.setText(str(self.selected_pdf))
        if hasattr(self, "meta_src"):
            self.meta_src.setText(str(self.selected_pdf))
        if hasattr(self, "extract_src"):
            self.extract_src.setText(str(self.selected_pdf))
        self.write_log(f"Выбран документ: {self.selected_pdf}")

    def clear_main_pdf(self):
        self.selected_pdf = None
        if hasattr(self, "selected_pdf_label"):
            self.selected_pdf_label.setText("Документ не выбран")
        self.write_log("Выбор документа очищен")

    def open_selected_page(self, name):
        if not self.selected_pdf or not self.selected_pdf.exists():
            QMessageBox.information(self, "PDFTools", "Сначала выберите PDF на главной странице.")
            self.show_page("Главная")
            return
        self.show_page(name)

    def _repair_page(self):
        p=QWidget(); l=QVBoxLayout(p)
        self.repair_source_label = QLabel("Основной документ будет взят с главной страницы.")
        self.repair_source_label.setWordWrap(True)
        l.addWidget(self.repair_source_label)
        self.repair_table=QTableWidget(0,5); self.repair_table.setHorizontalHeaderLabels(["Файл","Статус","Метод","Страниц","Результат"])
        self.repair_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        l.addWidget(self.repair_table)
        row=QHBoxLayout()
        add=QPushButton("Выбрать другой PDF"); add.clicked.connect(self.choose_repair_pdf)
        start=QPushButton("Начать HotFix"); start.setObjectName("Primary"); start.clicked.connect(self.run_repair)
        self.save_fixed_btn=QPushButton("Сохранить исправленный PDF")
        self.save_fixed_btn.setEnabled(False)
        self.save_fixed_btn.clicked.connect(self.save_fixed_pdf)
        row.addWidget(add); row.addStretch(); row.addWidget(start); row.addWidget(self.save_fixed_btn); l.addLayout(row)
        return p

    def choose_repair_pdf(self):
        path,_=QFileDialog.getOpenFileName(self,"Выбрать PDF для HotFix","","PDF (*.pdf)")
        if path:
            self.set_selected_pdf(path)
            self.repair_source_label.setText(str(self.selected_pdf))

    def _batch_page(self):
        """Единое рабочее пространство для сборки PDF из страниц разных документов."""
        from pathlib import Path
        p = QWidget()
        root = QVBoxLayout(p)
        root.setContentsMargins(8, 4, 8, 4)
        root.setSpacing(10)

        intro = QLabel("Добавляйте PDF, меняйте порядок страниц перетаскиванием и удаляйте ненужные листы. Итоговый документ сохранится в выбранном порядке.")
        intro.setWordWrap(True)
        root.addWidget(intro)

        toolbar = QHBoxLayout()
        add_btn = QPushButton("＋  Добавить PDF")
        add_btn.setObjectName("Primary")
        add_btn.clicked.connect(lambda: self.add_pdfs_to_workspace())
        remove_btn = QPushButton("Удалить выбранные страницы")
        remove_btn.clicked.connect(self.remove_workspace_pages)
        clear_btn = QPushButton("Очистить список")
        clear_btn.clicked.connect(self.clear_pdf_workspace)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(remove_btn)
        toolbar.addWidget(clear_btn)
        toolbar.addStretch()
        self.workspace_count = QLabel("0 страниц")
        self.workspace_count.setObjectName("Muted")
        toolbar.addWidget(self.workspace_count)
        root.addLayout(toolbar)

        self.pdf_workspace = QListWidget()
        self.pdf_workspace.setViewMode(QListWidget.IconMode)
        self.pdf_workspace.setResizeMode(QListWidget.Adjust)
        self.pdf_workspace.setMovement(QListWidget.Snap)
        self.pdf_workspace.setWrapping(True)
        self.pdf_workspace.setSpacing(14)
        self.pdf_workspace.setIconSize(QSize(142, 184))
        self.pdf_workspace.setGridSize(QSize(178, 244))
        self.pdf_workspace.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.pdf_workspace.setDragDropMode(QAbstractItemView.InternalMove)
        self.pdf_workspace.setDefaultDropAction(Qt.MoveAction)
        self.pdf_workspace.setStyleSheet("QListWidget { background:#202632; border:1px solid #394355; border-radius:9px; padding:12px; } QListWidget::item { background:#2b3342; border:1px solid #394355; border-radius:7px; padding:7px; } QListWidget::item:selected { border:2px solid #4a8cff; background:#354157; }")
        self.pdf_workspace.setToolTip("Перетаскивайте миниатюры мышью, чтобы изменить порядок страниц")
        root.addWidget(self.pdf_workspace, 1)

        footer = QHBoxLayout()
        hint = QLabel("Совет: можно добавить несколько PDF. Страницы каждого файла появятся отдельными миниатюрами.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        footer.addWidget(hint, 1)
        save_btn = QPushButton("Сохранить итоговый PDF")
        save_btn.setObjectName("Primary")
        save_btn.clicked.connect(self.save_pdf_workspace)
        footer.addWidget(save_btn)
        root.addLayout(footer)
        return p

    def add_pdfs_to_workspace(self, paths=None):
        if paths is None:
            paths, _ = QFileDialog.getOpenFileNames(self, "Добавить PDF-документы", "", "PDF (*.pdf)")
        if not paths:
            return
        try:
            import pymupdf as fitz
            for path in paths:
                with fitz.open(path) as doc:
                    for page_no, page in enumerate(doc):
                        pix = page.get_pixmap(matrix=fitz.Matrix(0.34, 0.34), alpha=False)
                        image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
                        thumb = QPixmap.fromImage(image).scaled(142, 184, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        item = QListWidgetItem(QIcon(thumb), f"{Path(path).name}\nСтраница {page_no + 1}")
                        item.setData(Qt.UserRole, (str(Path(path).resolve()), page_no))
                        item.setTextAlignment(Qt.AlignHCenter | Qt.AlignBottom)
                        item.setToolTip(f"{path}\nСтраница {page_no + 1}")
                        self.pdf_workspace.addItem(item)
            self.update_workspace_count()
            self.write_log(f"Добавлено PDF: {len(paths)}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка чтения PDF", str(exc))

    def remove_workspace_pages(self):
        for item in self.pdf_workspace.selectedItems():
            self.pdf_workspace.takeItem(self.pdf_workspace.row(item))
        self.update_workspace_count()

    def clear_pdf_workspace(self):
        self.pdf_workspace.clear()
        self.update_workspace_count()

    def update_workspace_count(self):
        count = self.pdf_workspace.count() if hasattr(self, "pdf_workspace") else 0
        self.workspace_count.setText(f"{count} страниц")

    def save_pdf_workspace(self):
        if not self.pdf_workspace.count():
            QMessageBox.information(self, "Сохранение PDF", "Сначала добавьте хотя бы один PDF-документ.")
            return
        target, _ = QFileDialog.getSaveFileName(self, "Сохранить собранный PDF", "Объединённый документ.pdf", "PDF (*.pdf)")
        if not target:
            return
        if not target.lower().endswith(".pdf"):
            target += ".pdf"
        try:
            import pymupdf as fitz
            result = fitz.open()
            cache = {}
            try:
                for index in range(self.pdf_workspace.count()):
                    data = self.pdf_workspace.item(index).data(Qt.UserRole)
                    source_path, page_no = data
                    if source_path not in cache:
                        cache[source_path] = fitz.open(source_path)
                    result.insert_pdf(cache[source_path], from_page=page_no, to_page=page_no)
                result.save(target, garbage=4, deflate=True)
            finally:
                result.close()
                for source in cache.values():
                    source.close()
            self.history.add("Сборка PDF", "; ".join(dict.fromkeys(self.pdf_workspace.item(i).data(Qt.UserRole)[0] for i in range(self.pdf_workspace.count()))), target, details=f"{self.pdf_workspace.count()} страниц")
            self.write_log(f"Собран PDF: {target}")
            QMessageBox.information(self, "PDFTools", f"Документ сохранён:\n{target}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка сохранения", str(exc))

    def _stamp_page(self):
        p=QWidget(); l=QVBoxLayout(p)
        l.setContentsMargins(8, 4, 8, 4)
        l.addWidget(QLabel("Разместите выбранный штамп непосредственно на странице документа. Перетаскивайте его мышью."))
        self.stamp_src=QLineEdit()
        self.stamp_src.setReadOnly(True)
        self.stamp_src.setPlaceholderText("Документ выбирается на главной странице")
        l.addWidget(self.stamp_src)
        open_editor = QPushButton("Открыть редактор штампов")
        open_editor.setObjectName("Primary")
        open_editor.clicked.connect(self.open_stamp_editor)
        l.addWidget(open_editor)
        l.addStretch()
        return p

    def open_stamp_editor(self):
        if not self.selected_pdf or not self.selected_pdf.is_file():
            QMessageBox.information(self, "Штамп", "Сначала выберите PDF на главной странице.")
            self.show_page("Главная")
            return
        dialog = StampEditorDialog(self, self.selected_pdf)
        if dialog.exec() == QDialog.Accepted and dialog.saved_path:
            self.set_selected_pdf(dialog.saved_path)
            self.write_log(f"Штампованный PDF сохранён: {dialog.saved_path}")

    def _watermark_page(self):
        p=QWidget(); l=QVBoxLayout(p)
        l.addWidget(QLabel("Текстовый водяной знак добавляется на все страницы выбранного PDF."))
        self.watermark_src=QLineEdit(); self.watermark_src.setReadOnly(True)
        row=QHBoxLayout(); row.addWidget(QLabel("Текущий PDF")); row.addWidget(self.watermark_src); l.addLayout(row)
        form=QFormLayout()
        self.watermark_text=QLineEdit("КОПИЯ")
        self.watermark_opacity=QLineEdit("0.22")
        self.watermark_size=QLineEdit("48")
        form.addRow("Текст",self.watermark_text)
        form.addRow("Прозрачность (0.05–1.0)",self.watermark_opacity)
        form.addRow("Размер шрифта",self.watermark_size)
        l.addLayout(form)
        b=QPushButton("Добавить водяной знак"); b.setObjectName("Primary"); b.clicked.connect(self.run_watermark)
        l.addWidget(b); l.addStretch()
        return p

    def _compare_page(self):
        p=QWidget(); l=QVBoxLayout(p)
        self.compare_a=QLineEdit(); self.compare_b=QLineEdit()
        for label,w in [("Исходный PDF",self.compare_a),("Сравниваемый PDF",self.compare_b)]:
            r=QHBoxLayout(); r.addWidget(QLabel(label)); r.addWidget(w); b=QPushButton("Обзор"); b.clicked.connect(lambda _,x=w:self.pick_file(x,"PDF (*.pdf)")); r.addWidget(b); l.addLayout(r)
        b=QPushButton("Сравнить страницы"); b.clicked.connect(self.run_compare); l.addWidget(b); l.addStretch(); return p

    def _metadata_page(self):
        p=QWidget(); l=QFormLayout()
        self.meta_src=QLineEdit(); self.meta_title=QLineEdit(); self.meta_author=QLineEdit(); self.meta_subject=QLineEdit(); self.meta_keywords=QLineEdit()
        r=QHBoxLayout(); r.addWidget(self.meta_src); b=QPushButton("Обзор"); b.clicked.connect(lambda:self.pick_file(self.meta_src,"PDF (*.pdf)")); r.addWidget(b)
        l.addRow("PDF",r); l.addRow("Название",self.meta_title); l.addRow("Автор",self.meta_author); l.addRow("Тема",self.meta_subject); l.addRow("Ключевые слова",self.meta_keywords)
        p=QWidget(); p.setLayout(l); save=QPushButton("Сохранить метаданные в копию"); save.clicked.connect(self.run_metadata); l.addRow(save); return p

    def _extract_page(self):
        p=QWidget(); l=QVBoxLayout(p)
        self.extract_src=QLineEdit(); r=QHBoxLayout(); r.addWidget(self.extract_src); b=QPushButton("Выбрать PDF"); b.clicked.connect(lambda:self.pick_file(self.extract_src,"PDF (*.pdf)")); r.addWidget(b); l.addLayout(r)
        for label, fn in [("Извлечь изображения",self.run_extract_images),("Извлечь таблицы в CSV",self.run_extract_tables)]:
            b=QPushButton(label); b.clicked.connect(fn); l.addWidget(b)
        l.addStretch(); return p

    def _history_page(self):
        p=QWidget(); l=QVBoxLayout(p)
        self.history_table=QTableWidget(0,6); self.history_table.setHorizontalHeaderLabels(["Дата","Операция","Источник","Результат","Статус","Детали"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        l.addWidget(self.history_table)
        b=QPushButton("Обновить историю"); b.clicked.connect(self.refresh_history); l.addWidget(b)
        return p

    def show_page(self, name):
        names=list(self.pages.keys()); idx=names.index(name)
        self.stack.setCurrentIndex(idx); self.page_title.setText(name)
        if name == "Обработка PDF" and self.selected_pdf and self.selected_pdf.is_file():
            existing = {self.pdf_workspace.item(i).data(Qt.UserRole)[0] for i in range(self.pdf_workspace.count())}
            if str(self.selected_pdf) not in existing:
                self.add_pdfs_to_workspace([str(self.selected_pdf)])
        if self.selected_pdf and self.selected_pdf.exists():
            for attr in ("stamp_src", "watermark_src", "compare_a", "meta_src", "extract_src"):
                widget = getattr(self, attr, None)
                if widget is not None and (attr != "compare_a" or not widget.text()):
                    widget.setText(str(self.selected_pdf))
        if name=="HotFix · Восстановление" and self.selected_pdf:
            self.repair_source_label.setText(str(self.selected_pdf))
        if name=="История": self.refresh_history()

    def write_log(self, message):
        self.log.appendPlainText(message)

    def pick_file(self, widget, filter_text):
        path,_=QFileDialog.getOpenFileName(self,"Выбрать файл","",filter_text)
        if path: widget.setText(path)

    def add_files(self, table):
        paths,_=QFileDialog.getOpenFileNames(self,"Выбрать PDF","","PDF (*.pdf)")
        self._add_paths(table,paths)

    def add_folder(self, table):
        folder=QFileDialog.getExistingDirectory(self,"Выбрать папку")
        if folder: self._add_paths(table,[str(p) for p in Path(folder).rglob("*.pdf")])

    def _add_paths(self, table, paths):
        for path in paths:
            row=table.rowCount(); table.insertRow(row); table.setItem(row,0,QTableWidgetItem(path))
            for col in range(1,5): table.setItem(row,col,QTableWidgetItem("Ожидает"))

    def run_repair(self):
        if not self.selected_pdf or not self.selected_pdf.exists():
            QMessageBox.information(self,"HotFix","Сначала выберите PDF на главной странице.")
            return
        self.fixed_pdf = None
        self.save_fixed_btn.setEnabled(False)
        self.repair_table.setRowCount(0)
        try:
            result=repair_file(self.selected_pdf)
            row=self.repair_table.rowCount(); self.repair_table.insertRow(row)
            vals=[str(result.src),"OK" if result.ok else "FAIL",result.method,str(result.pages or "—"),str(result.out_path or "—")]
            for c,v in enumerate(vals): self.repair_table.setItem(row,c,QTableWidgetItem(v))
            self.history.add("HotFix",str(result.src),str(result.out_path or ""), "OK" if result.ok else "FAIL", " | ".join(result.log))
            self.write_log(f"{vals[1]} · {self.selected_pdf} · {result.method}")
            if result.ok and result.out_path:
                self.fixed_pdf = Path(result.out_path)
                self.save_fixed_btn.setEnabled(True)
                QMessageBox.information(self,"HotFix","Восстановление завершено. Теперь нажмите «Сохранить исправленный PDF».")
            else:
                QMessageBox.warning(self,"HotFix","Не удалось восстановить документ. Подробности находятся в журнале.")
        except Exception as exc:
            QMessageBox.critical(self,"HotFix",str(exc))

    def save_fixed_pdf(self):
        if not self.fixed_pdf or not self.fixed_pdf.exists():
            QMessageBox.warning(self,"HotFix","Нет подготовленного исправленного файла.")
            return
        default = self.selected_pdf.with_name(f"{self.selected_pdf.stem}_fixed.pdf")
        out,_=QFileDialog.getSaveFileName(self,"Сохранить исправленный PDF",str(default),"PDF (*.pdf)")
        if not out:
            return
        try:
            shutil.copy2(self.fixed_pdf,out)
            self.set_selected_pdf(out)
            self.history.add("Сохранение после HotFix",str(self.fixed_pdf),out)
            self.write_log(f"Исправленный PDF сохранён: {out}")
            self.show_page("Штамп")
            QMessageBox.information(self,"PDFTools","Исправленный документ сохранён и открыт в разделе «Штамп».")
        except Exception as exc:
            QMessageBox.critical(self,"Ошибка сохранения",str(exc))

    def merge_dialog(self):
        paths,_=QFileDialog.getOpenFileNames(self,"Выбрать PDF","","PDF (*.pdf)")
        if len(paths)<2: return
        out,_=QFileDialog.getSaveFileName(self,"Сохранить объединённый PDF","","PDF (*.pdf)")
        if out:
            try: merge_pdfs(paths,out); self.history.add("Объединение",";".join(paths),out); self.write_log(f"Объединено: {out}")
            except Exception as e: QMessageBox.critical(self,"Ошибка",str(e))

    def split_dialog(self):
        src,_=QFileDialog.getOpenFileName(self,"Выбрать PDF","","PDF (*.pdf)")
        if not src:return
        out=QFileDialog.getExistingDirectory(self,"Папка результата")
        if out:
            try: result=split_pdf(src,out); self.history.add("Разделение",src,out,details=f"{len(result)} страниц"); self.write_log(f"Создано файлов: {len(result)}")
            except Exception as e: QMessageBox.critical(self,"Ошибка",str(e))

    def run_stamp(self):
        try:
            src=Path(self.stamp_src.text())
            img=Path(self.stamp_img.text())
            if not src.is_file() or not img.is_file():
                raise FileNotFoundError("Выберите основной PDF на главной странице и файл изображения штампа.")
            # Prepare a temporary stamped copy; final path is chosen by the explicit Save button.
            temp_dir=Path.home()/"AppData"/"Local"/"PDFTools"/"work"
            temp_dir.mkdir(parents=True,exist_ok=True)
            self.stamped_temp=temp_dir/f"{src.stem}_stamped_preview.pdf"
            add_image_stamp(src,img,self.stamped_temp,int(self.stamp_page.text()),float(self.stamp_x.text()),float(self.stamp_y.text()),float(self.stamp_w.text()))
            self.save_stamp_btn.setEnabled(True)
            self.stamp_status.setText("Штамп применён. Проверьте результат и нажмите «Сохранить с суффиксом _ВПР».")
            self.write_log(f"Штамп подготовлен: {self.stamped_temp}")
        except Exception as e:
            QMessageBox.critical(self,"Ошибка штампа",str(e))

    def save_stamped_pdf(self):
        try:
            if not getattr(self,"stamped_temp",None) or not self.stamped_temp.exists():
                raise FileNotFoundError("Сначала примените штамп.")
            src=Path(self.stamp_src.text())
            default=src.with_name(f"{src.stem}_ВПР.pdf")
            out,_=QFileDialog.getSaveFileName(self,"Сохранить PDF со штампом",str(default),"PDF (*.pdf)")
            if not out:return
            shutil.copy2(self.stamped_temp,out)
            self.history.add("Штамп",str(src),out)
            self.set_selected_pdf(out)
            self.stamp_status.setText(f"Сохранено: {out}")
            self.save_stamp_btn.setEnabled(False)
            self.write_log(f"Файл со штампом сохранён: {out}")
            QMessageBox.information(self,"PDFTools","Файл сохранён с суффиксом _ВПР.")
        except Exception as e:
            QMessageBox.critical(self,"Ошибка сохранения штампа",str(e))

    def run_watermark(self):
        try:
            src=Path(self.watermark_src.text())
            if not src.is_file():
                raise FileNotFoundError("Сначала выберите PDF на главной странице.")
            default=src.with_name(f"{src.stem}_watermark.pdf")
            out,_=QFileDialog.getSaveFileName(self,"Сохранить PDF с водяным знаком",str(default),"PDF (*.pdf)")
            if not out:return
            add_text_watermark(src,out,self.watermark_text.text(),float(self.watermark_opacity.text()),float(self.watermark_size.text()))
            self.history.add("Водяной знак",str(src),out)
            self.write_log(f"Водяной знак сохранён: {out}")
            QMessageBox.information(self,"PDFTools","Водяной знак добавлен.")
        except Exception as e:
            QMessageBox.critical(self,"Ошибка водяного знака",str(e))

    def run_compare(self):
        try:
            out=QFileDialog.getExistingDirectory(self,"Папка для изображений различий")
            if not out:return
            results=compare_pdfs(self.compare_a.text(),self.compare_b.text(),out)
            self.history.add("Сравнение",self.compare_a.text(),out,details=f"{len(results)} страниц")
            QMessageBox.information(self,"Сравнение",f"Создано изображений различий: {len(results)}")
        except Exception as e: QMessageBox.critical(self,"Ошибка сравнения",str(e))

    def run_metadata(self):
        try:
            src=Path(self.meta_src.text()); out,_=QFileDialog.getSaveFileName(self,"Сохранить копию","","PDF (*.pdf)")
            if not out:return
            set_metadata(src,out,{"title":self.meta_title.text(),"author":self.meta_author.text(),"subject":self.meta_subject.text(),"keywords":self.meta_keywords.text()})
            self.history.add("Метаданные",str(src),out); self.write_log(f"Метаданные сохранены: {out}")
        except Exception as e: QMessageBox.critical(self,"Ошибка метаданных",str(e))

    def run_extract_images(self):
        try:
            out=QFileDialog.getExistingDirectory(self,"Папка для изображений")
            if not out:return
            result=extract_images(self.extract_src.text(),out); self.history.add("Извлечение изображений",self.extract_src.text(),out,details=f"{len(result)} файлов")
            self.write_log(f"Извлечено изображений: {len(result)}")
        except Exception as e: QMessageBox.critical(self,"Ошибка",str(e))

    def run_extract_tables(self):
        try:
            out=QFileDialog.getExistingDirectory(self,"Папка для таблиц")
            if not out:return
            result=extract_tables(self.extract_src.text(),out); self.history.add("Извлечение таблиц",self.extract_src.text(),out,details=f"{len(result)} файлов")
            self.write_log(f"Извлечено таблиц: {len(result)}")
        except Exception as e: QMessageBox.critical(self,"Ошибка",str(e))

    def refresh_history(self):
        rows=self.history.recent()
        self.history_table.setRowCount(0)
        for record in rows:
            row=self.history_table.rowCount(); self.history_table.insertRow(row)
            for col,value in enumerate(record):
                self.history_table.setItem(row,col,QTableWidgetItem(str(value or "")))

    def check_updates(self):
        dialog=UpdateDialog(self); dialog.exec()


def main():
    app=QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_QSS)
    window=MainWindow()
    window.show()
    sys.exit(app.exec())
