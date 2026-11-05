"""Animations : liste d'images (modules), durées, aperçu, export et import de planches."""

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from sbs.canvas.scene import CanvasScene
from sbs.domain.animation import Animation, Frame, frame_index_at, total_ticks, validate_animation
from sbs.domain.ids import new_id
from sbs.services.animation_tools import export_animation, import_sheet
from sbs.services.library import LibraryError
from sbs.services.spritesheet import SheetError


class AnimationDialog(QDialog):
    def __init__(self, scene: CanvasScene, library_selection=None, parent: QWidget | None = None):
        """library_selection : fonction sans argument qui renvoie l'uuid du module choisi dans la bibliothèque."""
        super().__init__(parent)
        self.scene = scene
        self.library = scene.library
        self.library_selection = library_selection or (lambda: None)
        self.anims: dict[str, Animation] = scene.model.animations_copy()
        self._t = 0
        self.setWindowTitle("Animations")
        self.resize(780, 520)

        self.combo = QComboBox()
        new_b, ren_b, del_b = QPushButton("Nouvelle"), QPushButton("Renommer"), QPushButton("Supprimer")
        new_b.clicked.connect(self.new_animation)
        ren_b.clicked.connect(self.rename_animation)
        del_b.clicked.connect(self.delete_animation)
        top = QHBoxLayout()
        for w in (QLabel("Animation"), self.combo, new_b, ren_b, del_b):
            top.addWidget(w)
        top.addStretch(1)

        self.frames = QListWidget()
        self.frames.setIconSize(QSize(48, 48))
        self.frames.currentRowChanged.connect(self._row_changed)
        self.hold = QSpinBox()
        self.hold.setRange(1, 100)
        self.hold.valueChanged.connect(self._hold_changed)
        self.fps = QSpinBox()
        self.fps.setRange(1, 60)
        self.fps.setSuffix(" images/s")
        self.fps.valueChanged.connect(self._fps_changed)
        self.loop = QCheckBox("Boucle")
        self.loop.toggled.connect(self._loop_changed)
        btns = QGridLayout()
        for n, (text, fn) in enumerate([
            ("+ depuis la bibliothèque", self.add_from_library), ("+ depuis les objets sélectionnés", self.add_from_selection),
            ("Retirer", self.remove_frame), ("Dupliquer", self.duplicate_frame),
            ("Monter", lambda: self.move_frame(-1)), ("Descendre", lambda: self.move_frame(1))]):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, f=fn: f())
            btns.addWidget(b, n // 2, n % 2)
        left = QVBoxLayout()
        left.addWidget(QLabel("Images (dans l'ordre)"))
        left.addWidget(self.frames, 1)
        left.addLayout(btns)
        opts = QHBoxLayout()
        for w in (QLabel("Durée de l'image"), self.hold, self.fps, self.loop):
            opts.addWidget(w)
        left.addLayout(opts)

        self.preview = QLabel()
        self.preview.setMinimumSize(200, 200)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("background: #888")
        self.zoom = QSpinBox()
        self.zoom.setRange(1, 16)
        self.zoom.setValue(4)
        self.zoom.setSuffix(" ×")
        self.play = QPushButton("▶ Lire")
        self.play.setCheckable(True)
        self.play.toggled.connect(self._toggle_play)
        exp, imp = QPushButton("Exporter la planche…"), QPushButton("Importer une planche…")
        exp.clicked.connect(self.export_sheet)
        imp.clicked.connect(self.import_sheet)
        right = QVBoxLayout()
        right.addWidget(self.preview, 1)
        row = QHBoxLayout()
        row.addWidget(self.play)
        row.addWidget(QLabel("Zoom"))
        row.addWidget(self.zoom)
        right.addLayout(row)
        right.addWidget(exp)
        right.addWidget(imp)
        self.info = QLabel("")
        right.addWidget(self.info)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        mid = QHBoxLayout()
        mid.addLayout(left, 3)
        mid.addLayout(right, 2)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addLayout(mid, 1)
        lay.addWidget(bb)

        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._tick)
        self.combo.currentIndexChanged.connect(self._anim_changed)
        self._reload_combo()

    # --- état ------------------------------------------------------------------------------------------
    @property
    def current(self) -> Animation | None:
        key = self.combo.currentData()
        return self.anims.get(key) if key else None

    def _reload_combo(self, select: str | None = None) -> None:
        self.combo.blockSignals(True)
        self.combo.clear()
        for a in self.anims.values():
            self.combo.addItem(a.name, a.id)
        if select:
            self.combo.setCurrentIndex(max(0, self.combo.findData(select)))
        self.combo.blockSignals(False)
        self._anim_changed()

    def _anim_changed(self) -> None:
        a = self.current
        for w in (self.fps, self.loop):
            w.blockSignals(True)
        self.fps.setValue(a.fps if a else 8)
        self.loop.setChecked(a.loop if a else True)
        for w in (self.fps, self.loop):
            w.blockSignals(False)
        self._reload_frames()

    def _reload_frames(self, row: int | None = None) -> None:
        a = self.current
        self.frames.blockSignals(True)
        self.frames.clear()
        for i, f in enumerate(a.frames if a else []):
            asset = self.library.get(f.asset_uuid)
            it = QListWidgetItem(f"{i + 1}. {asset.name if asset else '(absent)'}"
                                 f"{' / ' + f.variant if f.variant else ''}  ×{f.hold}")
            thumb = self.library.thumbnail_path(f.asset_uuid)
            if thumb.exists():
                from PySide6.QtGui import QIcon
                it.setIcon(QIcon(QPixmap(str(thumb))))
            self.frames.addItem(it)
        if row is not None and self.frames.count():
            self.frames.setCurrentRow(min(row, self.frames.count() - 1))
        self.frames.blockSignals(False)
        self._row_changed(self.frames.currentRow())
        n = len(a.frames) if a else 0
        self.info.setText(f"{n} image(s), {total_ticks(a) if a else 0} top(s)" if a else "Aucune animation.")
        self._show_frame(0)

    def _row_changed(self, row: int) -> None:
        a = self.current
        self.hold.blockSignals(True)
        self.hold.setValue(a.frames[row].hold if a and 0 <= row < len(a.frames) else 1)
        self.hold.blockSignals(False)

    # --- édition -----------------------------------------------------------------------------------------
    def new_animation(self) -> None:
        name, ok = QInputDialog.getText(self, "Nouvelle animation", "Nom :", text=f"Animation {len(self.anims) + 1}")
        if ok and name.strip():
            a = Animation(new_id(), name.strip()[:80])
            self.anims[a.id] = a
            self._reload_combo(a.id)

    def rename_animation(self) -> None:
        a = self.current
        if a is None:
            return
        name, ok = QInputDialog.getText(self, "Renommer", "Nom :", text=a.name)
        if ok and name.strip():
            a.name = name.strip()[:80]
            self._reload_combo(a.id)

    def delete_animation(self) -> None:
        a = self.current
        if a is not None:
            del self.anims[a.id]
            self._reload_combo()

    def _add(self, frames: list[Frame]) -> None:
        a = self.current
        if a is None:
            self.info.setText("Crée d'abord une animation.")
            return
        a.frames.extend(frames)
        self._reload_frames(len(a.frames) - 1)

    def add_from_library(self) -> None:
        uuid = self.library_selection()
        if uuid:
            self._add([Frame(uuid)])
        else:
            self.info.setText("Choisis un module dans la bibliothèque.")

    def add_from_selection(self) -> None:
        sel = self.scene.selection_in_model_order()
        if not sel:
            self.info.setText("Sélectionne des objets dans la scène.")
            return
        self._add([Frame(i.asset_uuid, i.variant) for i in sel])

    def remove_frame(self) -> None:
        a, r = self.current, self.frames.currentRow()
        if a and 0 <= r < len(a.frames):
            del a.frames[r]
            self._reload_frames(r)

    def duplicate_frame(self) -> None:
        a, r = self.current, self.frames.currentRow()
        if a and 0 <= r < len(a.frames):
            a.frames.insert(r + 1, deepcopy(a.frames[r]))
            self._reload_frames(r + 1)

    def move_frame(self, d: int) -> None:
        a, r = self.current, self.frames.currentRow()
        if a and 0 <= r < len(a.frames) and 0 <= r + d < len(a.frames):
            a.frames[r], a.frames[r + d] = a.frames[r + d], a.frames[r]
            self._reload_frames(r + d)

    def _hold_changed(self, v: int) -> None:
        a, r = self.current, self.frames.currentRow()
        if a and 0 <= r < len(a.frames):
            a.frames[r].hold = v
            self._reload_frames(r)

    def _fps_changed(self, v: int) -> None:
        if self.current:
            self.current.fps = v

    def _loop_changed(self, v: bool) -> None:
        if self.current:
            self.current.loop = v

    # --- aperçu --------------------------------------------------------------------------------------------
    def _show_frame(self, index: int) -> None:
        a = self.current
        if a is None or not (0 <= index < len(a.frames)):
            self.preview.clear()
            return
        f = a.frames[index]
        asset = self.library.get(f.asset_uuid)
        if asset is None:
            self.preview.setText("(image absente)")
            return
        pm = QPixmap(str(self.library.abs_path(asset.image_for(f.variant))))
        z = self.zoom.value()
        self.preview.setPixmap(pm.scaled(pm.width() * z, pm.height() * z, Qt.AspectRatioMode.IgnoreAspectRatio,
                                         Qt.TransformationMode.FastTransformation))

    def _toggle_play(self, on: bool) -> None:
        self.play.setText("■ Arrêter" if on else "▶ Lire")
        self._t = 0
        self.timer.start() if on else self.timer.stop()

    def _tick(self) -> None:
        a = self.current
        if a:
            self._t += self.timer.interval()
            self._show_frame(frame_index_at(a, self._t))

    # --- planches ----------------------------------------------------------------------------------------
    def export_sheet(self) -> bool:
        a = self.current
        if a is None or not a.frames:
            self.info.setText("Rien à exporter.")
            return False
        path, _ = QFileDialog.getSaveFileName(self, "Exporter la planche", f"{a.name}.png", "Images PNG (*.png)")
        if not path:
            return False
        cols, ok = QInputDialog.getInt(self, "Planche", "Nombre de colonnes :", len(a.frames), 1, len(a.frames))
        if not ok:
            return False
        try:
            export_animation(self.library, a, Path(path), cols)
        except (SheetError, OSError) as exc:
            QMessageBox.warning(self, "Export impossible", str(exc))
            return False
        self.info.setText(f"Planche exportée (et {Path(path).with_suffix('.json').name}).")
        return True

    def import_sheet(self) -> bool:
        path, _ = QFileDialog.getOpenFileName(self, "Importer une planche", "", "Images PNG (*.png)")
        if not path:
            return False
        from sbs.services.spritesheet import read_meta
        cell = None
        if read_meta(Path(path)) is None:
            w, ok = QInputDialog.getInt(self, "Case", "Largeur d'une case (px) :", 32, 1, 512)
            if not ok:
                return False
            h, ok = QInputDialog.getInt(self, "Case", "Hauteur d'une case (px) :", 32, 1, 512)
            if not ok:
                return False
            cell = (w, h)
        try:
            anim = import_sheet(self.library, Path(path), Path(path).stem, cell)
        except (SheetError, LibraryError, ValueError) as exc:
            QMessageBox.warning(self, "Import impossible", str(exc))
            return False
        self.anims[anim.id] = anim
        self._reload_combo(anim.id)
        return True

    def accept(self) -> None:
        self.timer.stop()
        try:
            for a in self.anims.values():
                validate_animation(a)
        except ValueError as exc:
            self.info.setText(str(exc))
            return
        if self.anims != self.scene.model.animations:
            err = self.scene.set_animations(self.anims)
            if err:
                self.info.setText(err)
                return
        super().accept()

    def reject(self) -> None:
        self.timer.stop()
        super().reject()
