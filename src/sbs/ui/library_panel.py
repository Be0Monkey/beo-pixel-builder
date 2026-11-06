"""Panneau Bibliothèque : recherche, catégories, miniatures, import du kit (en arrière-plan)."""

import threading
from pathlib import Path

from PySide6.QtCore import QMimeData, QObject, QSize, Qt, QThread, Signal, Slot
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QInputDialog,
    QMenu,
    QFileDialog,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from sbs.canvas.mime import ASSET_MIME
from sbs.services.batch_import import FORMATS, BatchReport, collect_files, import_images
from sbs.services.kit_importer import ImportReport, KitError, import_kit
from sbs.services.library import Library, LibraryError

ASSET_ROLE = Qt.ItemDataRole.UserRole


class AssetList(QListWidget):
    """Liste de miniatures dont les éléments peuvent être glissés vers le canevas."""

    def mimeTypes(self) -> list[str]:
        return [ASSET_MIME]

    def mimeData(self, items) -> QMimeData:
        mime = QMimeData()
        if items:
            mime.setData(ASSET_MIME, items[0].data(ASSET_ROLE).encode("utf-8"))
        return mime


class ImportWorker(QObject):
    progress = Signal(int, int)
    finished = Signal(object)  # ImportReport ou message d'erreur (str)

    def __init__(self, library: Library, kit_dir: Path):
        super().__init__()
        self.library, self.kit_dir = library, kit_dir
        self.cancel_event = threading.Event()

    def run(self) -> None:
        try:
            result = import_kit(
                self.library, self.kit_dir,
                progress=lambda i, n: self.progress.emit(i, n),
                cancelled=self.cancel_event.is_set,
            )
        except KitError as exc:
            result = str(exc)
        self.finished.emit(result)


class ImagesWorker(QObject):
    """Import d'images (fichiers ou dossiers) en arrière-plan, avec progression et annulation."""

    progress = Signal(int, int)
    finished = Signal(object)  # BatchReport ou message d'erreur (str)

    def __init__(self, library: Library, paths: list[Path], category: str):
        super().__init__()
        self.library, self.paths, self.category = library, paths, category
        self.cancel_event = threading.Event()

    def run(self) -> None:
        try:
            files, ignored = collect_files(self.paths)
            if not files:
                self.finished.emit("Aucune image PNG, GIF, BMP ou WebP trouvée.")
                return
            report = import_images(self.library, files, self.category,
                                   progress=lambda i, n: self.progress.emit(i, n),
                                   cancelled=self.cancel_event.is_set)
            report.ignored = ignored
            self.finished.emit(report)
        except Exception as exc:  # jamais de thread qui meurt sans prévenir
            self.finished.emit(f"Import interrompu : {exc}")


class LibraryPanel(QWidget):
    asset_activated = Signal(str)  # uuid (double-clic), utilisé par le canvas au jalon J1b

    def __init__(self, library: Library, parent: QWidget | None = None):
        super().__init__(parent)
        self.library = library
        self._thread: QThread | None = None
        self._worker: ImportWorker | None = None
        self._dialog: QProgressDialog | None = None

        self.search = QLineEdit(placeholderText="Rechercher…", clearButtonEnabled=True)
        self.category = QComboBox()
        self.tag_filter = QComboBox()
        self.fav_only = QCheckBox("Favoris seulement")
        self.list = AssetList()
        self.list.setViewMode(QListView.ViewMode.IconMode)
        self.list.setResizeMode(QListView.ResizeMode.Adjust)
        self.list.setMovement(QListView.Movement.Static)
        # APRÈS setMovement : Qt coupe le glisser (dragEnabled) quand le mouvement est « Static »
        self.list.setDragDropMode(QListView.DragDropMode.DragOnly)
        self.list.setDragEnabled(True)
        self.list.setIconSize(QSize(96, 96))
        self.list.setGridSize(QSize(116, 128))
        self.list.setWordWrap(True)
        self.list.setUniformItemSizes(True)
        self.count_label = QLabel()
        self.import_button = QPushButton("Importer le kit de sprites…")
        self.images_button = QPushButton("Importer des images…")
        self.images_menu = QMenu(self.images_button)
        self.images_menu.addAction("Choisir des fichiers…", self.choose_images)
        self.images_menu.addAction("Choisir un dossier (sous-dossiers inclus)…", self.choose_images_folder)
        self.images_button.setMenu(self.images_menu)

        lay = QVBoxLayout(self)
        lay.addWidget(self.search)
        lay.addWidget(self.category)
        lay.addWidget(self.tag_filter)
        lay.addWidget(self.fav_only)
        lay.addWidget(self.list, 1)
        lay.addWidget(self.count_label)
        lay.addWidget(self.import_button)
        lay.addWidget(self.images_button)

        self.search.textChanged.connect(self.refresh)
        self.category.currentIndexChanged.connect(self.refresh)
        self.tag_filter.currentIndexChanged.connect(self.refresh)
        self.fav_only.toggled.connect(self.refresh)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._context_menu)
        self.import_button.clicked.connect(self.choose_and_import)
        self.list.itemDoubleClicked.connect(lambda it: self.asset_activated.emit(it.data(ASSET_ROLE)))
        self.reload_categories()
        self.refresh()

    # --- affichage ------------------------------------------------------
    def reload_categories(self) -> None:
        current = self.category.currentData()
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem("Toutes les catégories", None)
        for c in self.library.categories():
            self.category.addItem(c, c)
        idx = self.category.findData(current)
        self.category.setCurrentIndex(max(0, idx))
        self.category.blockSignals(False)
        cur_tag = self.tag_filter.currentData()
        self.tag_filter.blockSignals(True)
        self.tag_filter.clear()
        self.tag_filter.addItem("Tous les mots-clés", None)
        for t in self.library.all_tags():
            self.tag_filter.addItem(t, t)
        self.tag_filter.setCurrentIndex(max(0, self.tag_filter.findData(cur_tag)))
        self.tag_filter.blockSignals(False)

    def refresh(self) -> None:
        assets = self.library.list_assets(self.search.text(), self.category.currentData(),
                                          self.fav_only.isChecked(), self.tag_filter.currentData())
        self.list.clear()
        for a in assets:
            item = QListWidgetItem(("★ " if a.favorite else "") + a.name)
            thumb = self.library.thumbnail_path(a.uuid)
            if thumb.exists():
                item.setIcon(QIcon(QPixmap(str(thumb))))
            item.setData(ASSET_ROLE, a.uuid)
            tip = f"{a.name}\n{a.description}\n{a.width}×{a.height} px · pivot ({a.pivot_x}, {a.pivot_y})"
            if a.tags:
                tip += "\nMots-clés : " + ", ".join(a.tags)
            if a.variants:
                tip += "\nVariantes : " + ", ".join(v.name for v in a.variants)
            item.setToolTip(tip)
            self.list.addItem(item)
        total = self.library.count()
        if total == 0:
            self.count_label.setText("Bibliothèque vide : importe ton kit de sprites.")
        else:
            self.count_label.setText(f"{len(assets)} affiché(s) sur {total}")

    def current_asset_uuid(self) -> str | None:
        item = self.list.currentItem()
        return item.data(ASSET_ROLE) if item else None

    # --- organisation (clic droit) -------------------------------------------------------
    def _context_menu(self, pos) -> None:
        item = self.list.itemAt(pos)
        if item is None:
            return
        uuid = item.data(ASSET_ROLE)
        asset = self.library.get(uuid)
        if asset is None:
            return
        menu = QMenu(self)
        menu.addAction("Retirer des favoris" if asset.favorite else "Ajouter aux favoris",
                       lambda: self.toggle_favorite(uuid))
        menu.addAction("Mots-clés…", lambda: self.edit_tags(uuid))
        menu.addAction("Changer de catégorie…", lambda: self.edit_category(uuid))
        menu.exec(self.list.mapToGlobal(pos))

    def toggle_favorite(self, uuid: str) -> None:
        asset = self.library.get(uuid)
        if asset is not None:
            self.library.set_favorite(uuid, not asset.favorite)
            self.refresh()

    def edit_tags(self, uuid: str) -> None:
        asset = self.library.get(uuid)
        if asset is None:
            return
        text, ok = QInputDialog.getText(self, "Mots-clés", "Mots-clés séparés par des virgules :",
                                        text=", ".join(asset.tags))
        if ok:
            try:
                self.library.set_tags(uuid, text.split(","))
            except LibraryError as exc:
                QMessageBox.warning(self, "Mots-clés", str(exc))
            self.reload_categories()
            self.refresh()

    def edit_category(self, uuid: str) -> None:
        asset = self.library.get(uuid)
        if asset is None:
            return
        cats = self.library.categories()
        text, ok = QInputDialog.getItem(self, "Catégorie", "Choisis ou écris une catégorie :",
                                        cats, max(0, cats.index(asset.category)) if asset.category in cats else 0, True)
        if ok:
            try:
                self.library.set_category(uuid, text)
            except LibraryError as exc:
                QMessageBox.warning(self, "Catégorie", str(exc))
            self.reload_categories()
            self.refresh()

    # --- import ---------------------------------------------------------
    def choose_and_import(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choisir le dossier du kit de sprites")
        if folder:
            self.start_import(Path(folder))

    def choose_images(self) -> None:
        exts = " ".join(f"*{e}" for e in FORMATS)
        files, _ = QFileDialog.getOpenFileNames(self, "Choisir des images", "", f"Images ({exts})")
        if files:
            self.start_images_import([Path(f) for f in files])

    def choose_images_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choisir un dossier d'images")
        if folder:
            self.start_images_import([Path(folder)])

    def start_images_import(self, paths: list[Path], category: str = "importé") -> None:
        if self._thread is not None:
            return
        self._start(ImagesWorker(self.library, [Path(p) for p in paths], category), "Import des images…")

    def start_import(self, kit_dir: Path) -> None:
        if self._thread is not None:
            return
        self._start(ImportWorker(self.library, kit_dir), "Import du kit…")

    def _start(self, worker, title: str) -> None:
        self.import_button.setEnabled(False)
        self.images_button.setEnabled(False)
        dialog = QProgressDialog(title, "Annuler", 0, 0, self)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        # Slots du panneau (objet du thread GUI) : les signaux du worker sont mis en file
        # et exécutés dans le thread de l'interface. Une lambda s'exécuterait dans le thread
        # du worker (interface touchée hors thread GUI, et thread.wait() sur lui-même).
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)
        dialog.canceled.connect(worker.cancel_event.set)
        self._thread, self._worker, self._dialog = thread, worker, dialog
        thread.start()

    @Slot(int, int)
    def _on_progress(self, i: int, n: int) -> None:
        if self._dialog is not None:
            self._dialog.setMaximum(n)
            self._dialog.setValue(i)

    @Slot(object)
    def _on_finished(self, result: object) -> None:
        if self._dialog is not None:
            self._dialog.close()
        thread = self._thread
        if thread is not None:
            thread.quit()
            thread.wait()
        self._thread = self._worker = self._dialog = None
        self.import_button.setEnabled(True)
        self.images_button.setEnabled(True)
        self.reload_categories()
        self.refresh()
        if isinstance(result, str):
            QMessageBox.warning(self, "Import impossible", result)
            return
        if isinstance(result, BatchReport):
            self._show_batch_report(result)
        else:
            self._show_report(result)

    def _show_batch_report(self, r: BatchReport) -> None:
        lines = [f"{len(r.imported)} image(s) importée(s)."]
        if r.duplicates:
            lines.append(f"{r.duplicates} déjà présente(s) (même contenu : ignorées, aucun doublon).")
        if r.ignored:
            lines.append(f"{r.ignored} fichier(s) d'un autre format ignoré(s).")
        if r.cancelled:
            lines.append("Import annulé : ce qui est déjà importé est conservé.")
        if r.errors:
            lines.append(f"{len(r.errors)} erreur(s) :\n- " + "\n- ".join(r.errors[:10]))
        box = QMessageBox.warning if r.errors else QMessageBox.information
        box(self, "Import d'images", "\n".join(lines))

    def _show_report(self, r: ImportReport) -> None:
        lines = [f"{r.imported} module(s) importé(s)."]
        if r.already_present:
            lines.append(f"{r.already_present} déjà présent(s) (ignorés, aucun doublon).")
        if r.cancelled:
            lines.append("Import annulé : ce qui est déjà importé est conservé.")
        if r.errors:
            lines.append(f"{len(r.errors)} erreur(s) :\n- " + "\n- ".join(r.errors[:10]))
        if r.warnings:
            lines.append(f"{len(r.warnings)} avertissement(s).")
        box = QMessageBox.warning if r.errors else QMessageBox.information
        box(self, "Import du kit", "\n".join(lines))
