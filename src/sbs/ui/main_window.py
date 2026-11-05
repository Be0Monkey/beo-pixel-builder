"""Fenêtre principale (atelier Construction) : docks et barre d'état. Voir 03_Interface_et_parcours.md."""

import base64
from pathlib import Path

from PySide6.QtCore import QByteArray, QMimeData, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget,
    QApplication,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QToolBar,
    QWidget,
)

from sbs import __version__
from sbs.canvas.scene import CanvasScene
from sbs.commands.history import History
from sbs.canvas.view import CanvasView
from sbs.domain.scene import SceneModel
from sbs.services.clipboard_codec import MIME as CLIP_MIME
from sbs.services.exporter import ExportError, export_png
from sbs.services.library import Library
from sbs.services.project_io import (
    EXTENSION,
    ProjectError,
    ProjectMeta,
    load_project,
    save_project,
)
from sbs.services.preferences import Preferences
from sbs.ui.floors_panel import FloorsPanel
from sbs.ui.library_panel import LibraryPanel
from sbs.domain.pixel import PixelDoc
from sbs.domain.pixel_edit import PixelEditor, check_color
from sbs.services.library import LibraryError
from sbs.services.pixel_io import load_doc, png_bytes, save_layers
from sbs.ui.animation_dialog import AnimationDialog
from sbs.services.backgrounds import BACKGROUNDS
from sbs.ui.export_dialog import ExportDialog
from sbs.ui.module_dialog import ModuleDialog
from sbs.ui.preview_dialog import PreviewDialog
from sbs.ui.repeat_dialog import RepeatDialog
from sbs.ui.pixel_editor import PixelEditorDialog
from sbs.ui.session_mixin import SessionMixin
from sbs.ui.guide_dialog import GuideDialog

_B64 = "utf-8"


def _placeholder(text: str) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    return label


class MainWindow(SessionMixin, QMainWindow):
    def __init__(self, prefs: Preferences, library: Library):
        super().__init__()
        self.prefs = prefs
        self.library = library
        self.setWindowTitle("Sprite Builder Studio")
        self.resize(1400, 850)

        self.meta = ProjectMeta()
        self.path: Path | None = None
        self._paste_n = 0
        self.scene_model = SceneModel()
        self.history = History(self.scene_model)
        self.history.add_listener(self._on_history_changed)
        self.scene_model.add_listener(lambda: self._update_status())
        self.canvas_scene = CanvasScene(self.scene_model, library, self.history)
        self.canvas = CanvasView(self.canvas_scene)
        self.setCentralWidget(self.canvas)
        self.docks: dict[str, QDockWidget] = {}
        self.library_panel = LibraryPanel(library)
        self._add_dock("library", "Bibliothèque", Qt.DockWidgetArea.LeftDockWidgetArea,
                       self.library_panel)
        self._add_dock("properties", "Propriétés", Qt.DockWidgetArea.RightDockWidgetArea,
                       "Propriétés\n(jalon J1b)")
        self.floors_panel = FloorsPanel(self.canvas_scene)
        self._add_dock("floors", "Étages / Calques", Qt.DockWidgetArea.RightDockWidgetArea,
                       self.floors_panel)

        self.library_panel.asset_activated.connect(self.canvas.add_asset_at_center)
        self.pos_label = QLabel()
        self.statusBar().addPermanentWidget(self.pos_label)
        self.canvas.mouse_moved.connect(lambda x, y: self._update_status(x, y))
        self.canvas.zoom_changed.connect(lambda z: self._update_status())
        self._mouse = (0, 0)
        self._init_session()
        self._build_menus()
        self._build_toolbar()
        self._collect_actions()
        self.apply_shortcuts()
        self.statusBar().showMessage("Prêt")
        self._update_status()
        self._on_history_changed()
        self._update_title()
        self._load_view_prefs()
        self.canvas_scene.add_context_listener(self._update_status)
        QApplication.clipboard().dataChanged.connect(lambda: setattr(self, "_paste_n", 0))
        self._default_state = self.saveState()
        self._default_geometry = self.saveGeometry()
        self._restore_layout()

    # --- construction -------------------------------------------------
    def _add_dock(self, key: str, title: str, area: Qt.DockWidgetArea, content: str | QWidget) -> None:
        dock = QDockWidget(title, self)
        dock.setObjectName(f"dock_{key}")  # obligatoire pour saveState()
        dock.setWidget(_placeholder(content) if isinstance(content, str) else content)
        self.addDockWidget(area, dock)
        self.docks[key] = dock

    def _build_menus(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("&Fichier")
        file_menu.addAction(QAction("&Nouveau", self, shortcut="Ctrl+N", triggered=self.new_project))
        file_menu.addAction(QAction("Nouveau &sprite…", self, shortcut="Ctrl+Shift+N", triggered=self.new_sprite))
        file_menu.addAction(QAction("&Ouvrir…", self, shortcut="Ctrl+O", triggered=self.open_dialog))
        file_menu.addAction(QAction("&Enregistrer", self, shortcut="Ctrl+S", triggered=self.save))
        file_menu.addAction(QAction("Enregistrer &sous…", self, shortcut="Ctrl+Shift+S",
                                    triggered=self.save_as))
        file_menu.addAction(QAction("&Versions et récupération…", self, triggered=self.open_versions_dialog))
        file_menu.addSeparator()
        file_menu.addAction(QAction("E&xporter en PNG…", self, shortcut="Ctrl+E",
                                    triggered=lambda: self.export_dialog(False)))
        file_menu.addAction(QAction("Exporter en PNG a&grandi…", self,
                                    triggered=lambda: self.export_dialog(True)))
        file_menu.addAction(QAction("Exporter pour &Godot 4…", self, triggered=lambda: self.open_export("godot4")))
        file_menu.addAction(QAction("Exporter en &JSON…", self, triggered=lambda: self.open_export("json")))
        file_menu.addSeparator()
        file_menu.addAction(QAction("&Options…", self, shortcut="Ctrl+,", triggered=self.open_options))
        file_menu.addAction(QAction("&Quitter", self, shortcut="Ctrl+Q", triggered=self.close))

        edit_menu = bar.addMenu("&Édition")
        self.act_undo = QAction("&Annuler", self, shortcut="Ctrl+Z", triggered=self.canvas_scene.undo)
        self.act_undo.setObjectName("edit_undo")
        self.act_redo = QAction("&Rétablir", self, triggered=self.canvas_scene.redo)
        self.act_redo.setObjectName("edit_redo")
        self.act_redo.setShortcuts(["Ctrl+Y", "Ctrl+Shift+Z"])
        edit_menu.addAction(self.act_undo)
        edit_menu.addAction(self.act_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(QAction("&Copier", self, shortcut="Ctrl+C", triggered=self.copy_selection))
        edit_menu.addAction(QAction("Co&uper", self, shortcut="Ctrl+X", triggered=self.cut_selection))
        edit_menu.addAction(QAction("C&oller", self, shortcut="Ctrl+V", triggered=self.paste))
        edit_menu.addAction(QAction("Dupli&quer", self, shortcut="Ctrl+D",
                                    triggered=self.duplicate_selection))
        edit_menu.addSeparator()
        edit_menu.addAction(QAction("&Supprimer", self, shortcut="Delete",
                                    triggered=self.canvas_scene.remove_selected))
        edit_menu.addSeparator()
        self.act_group = QAction("&Grouper", self, shortcut="Ctrl+G", triggered=self.group_selection)
        self.act_ungroup = QAction("Dég&rouper", self, shortcut="Ctrl+Shift+G",
                                   triggered=self.canvas_scene.ungroup_selected)
        edit_menu.addAction(self.act_group)
        edit_menu.addAction(self.act_ungroup)
        edit_menu.addAction(QAction("&Répéter…", self, shortcut="Ctrl+R", triggered=self.open_repeat))
        edit_menu.addAction(QAction("&Animations…", self, shortcut="F7", triggered=self.open_animations))
        edit_menu.addAction(QAction("&Modifier les pixels…", self, shortcut="F6",
                                    triggered=self.edit_pixels))
        edit_menu.addAction(QAction("&Propriétés du module…", self, shortcut="F4",
                                    triggered=self.edit_module_properties))
        self.variant_menu = edit_menu.addMenu("&Variante")
        self.variant_menu.aboutToShow.connect(self._fill_variant_menu)
        edit_menu.addAction(QAction("Sélectionner les objets à image &manquante", self,
                                    triggered=self.check_references))
        edit_menu.addAction(QAction("&Sortir du groupe", self, triggered=self.canvas_scene.exit_group))
        edit_menu.addSeparator()
        edit_menu.addAction(QAction("Mettre &devant", self, shortcut="Ctrl+]",
                                    triggered=lambda: self.canvas_scene.shift_z_selected(1)))
        edit_menu.addAction(QAction("Mettre d&errière", self, shortcut="Ctrl+[",
                                    triggered=lambda: self.canvas_scene.shift_z_selected(-1)))
        edit_menu.addAction(QAction("Ordre &automatique", self, shortcut="Ctrl+\\",
                                    triggered=self.canvas_scene.reset_z_selected))

        view_menu = bar.addMenu("&Vue")
        view_menu.addAction(QAction("Zoom +", self, shortcut="Ctrl++", triggered=self.canvas.zoom_in))
        view_menu.addAction(QAction("Zoom −", self, shortcut="Ctrl+-", triggered=self.canvas.zoom_out))
        view_menu.addAction(QAction("Zoom 200 %", self, shortcut="Ctrl+0", triggered=self.canvas.zoom_reset))
        self.act_grid = QAction("Afficher la &grille", self, checkable=True, shortcut="G")
        self.act_grid.toggled.connect(self._grid_visible_toggled)
        self.act_snap_grid = QAction("Aimant : grille", self, checkable=True)
        self.act_snap_edges = QAction("Aimant : bords", self, checkable=True)
        self.act_snap_anchors = QAction("Aimant : ancrages", self, checkable=True)
        self.act_snap_anchors.toggled.connect(self._snap_changed)
        self.act_snap_grid.toggled.connect(self._snap_changed)
        self.act_snap_edges.toggled.connect(self._snap_changed)
        view_menu.addAction(self.act_grid)
        view_menu.addAction(self.act_snap_grid)
        view_menu.addAction(self.act_snap_edges)
        view_menu.addAction(self.act_snap_anchors)
        bg_menu = view_menu.addMenu("Fond de l'espace de travail")
        bg_menu.addAction(QAction("Damier (par défaut)", self, triggered=lambda: self._set_background(None)))
        for key, (label, top, bottom) in BACKGROUNDS.items():
            bg_menu.addAction(QAction(label, self, triggered=lambda _=False, k=key: self._set_background(k)))
        view_menu.addAction(QAction("Aperçu &éclairé (simulation)…", self, shortcut="F8", triggered=self.open_preview))
        size_menu = view_menu.addMenu("Taille de la grille")
        for px in (8, 16, 32, 64):
            size_menu.addAction(QAction(f"{px} px", self, triggered=lambda _=False, v=px: self._set_grid_size(v)))
        view_menu.addSeparator()
        for dock in self.docks.values():
            view_menu.addAction(dock.toggleViewAction())
        view_menu.addSeparator()
        self.workspace_menu = view_menu.addMenu("&Espaces de travail")
        self.workspace_menu.aboutToShow.connect(self._fill_workspace_menu)
        view_menu.addAction(
            QAction("Réinitialiser les panneaux", self, triggered=self.reset_layout)
        )

        help_menu = bar.addMenu("&Aide")
        help_menu.addAction(QAction("&Guide utilisateur", self, shortcut="F1", triggered=self.open_guide))
        help_menu.addAction(QAction("&Raccourcis clavier…", self,
                                    triggered=lambda: self.open_options(start_tab=1)))
        help_menu.addAction(QAction("À propos", self, triggered=self._about))

    def _build_toolbar(self) -> None:
        tb = QToolBar("Outils", self)
        tb.setObjectName("toolbar_main")
        tb.setMovable(True)
        self.addToolBar(tb)
        for act in (self.act_grid, self.act_snap_grid, self.act_snap_edges, self.act_snap_anchors):
            act.setToolTip(act.text().replace("&", "") + " (Alt pendant un glissement : aimant coupé)")
            tb.addAction(act)
        tb.addSeparator()
        tb.addAction(self.act_group)
        tb.addAction(self.act_ungroup)

    def _update_status(self, x: int | None = None, y: int | None = None) -> None:
        if x is not None:
            self._mouse = (x, y)
        self.pos_label.setText(
            f"X: {self._mouse[0]}  Y: {self._mouse[1]}  |  Zoom: {round(self.canvas.zoom * 100)} %"
            f"  |  Aimant : {self.snap_label()}"
            + (f"  |  Groupe : {' > '.join(self.canvas_scene.group_path())}"
               if self.canvas_scene.entered_group else "")
            + f"  |  {len(self.scene_model)} objet(s)"
        )

    # --- document ---------------------------------------------------------------------------
    @property
    def dirty(self) -> bool:
        return self.history.dirty

    @dirty.setter
    def dirty(self, value: bool) -> None:
        if value:
            self.history.mark_dirty()
        else:
            self.history.mark_saved()

    def _on_history_changed(self) -> None:
        self._update_title()
        self._update_status()
        if hasattr(self, "act_undo"):
            h = self.history
            self.act_undo.setEnabled(h.can_undo)
            self.act_redo.setEnabled(h.can_redo)
            self.act_undo.setText(f"&Annuler : {h.undo_name}" if h.can_undo else "&Annuler")
            self.act_redo.setText(f"&Rétablir : {h.redo_name}" if h.can_redo else "&Rétablir")

    def _update_title(self) -> None:
        name = self.path.stem if self.path else self.meta.name
        self.setWindowTitle(f"{name}{' *' if self.dirty else ''} — Sprite Builder Studio")

    def _confirm_discard(self) -> bool:
        """True si on peut continuer (rien à perdre, enregistré, ou abandon accepté)."""
        if not self.dirty:
            return True
        box = QMessageBox.question(
            self, "Modifications non enregistrées",
            "Enregistrer les modifications avant de continuer ?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if box == QMessageBox.StandardButton.Save:
            return self.save()
        return box == QMessageBox.StandardButton.Discard

    def new_project(self) -> bool:
        if not self._confirm_discard():
            return False
        self._apply(ProjectMeta(), [], None)
        return True

    def _apply(self, meta: ProjectMeta, instances, path: Path | None, floors=None, groups=None,
               animations=None) -> None:
        if meta.id != self.meta.id:
            self.recovery.clear(self.meta.id)  # l'ancien travail est fermé (enregistré ou abandonné)
        self.scene_model.replace(instances, floors, groups, animations)  # la scène se synchronise sur le modèle
        self.history.clear()
        self.meta, self.path = meta, path
        self._update_title()
        self._update_status()

    def open_dialog(self) -> None:
        if not self._confirm_discard():
            return
        file, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir un projet", "", f"Projet Sprite Builder Studio (*{EXTENSION})"
        )
        if file:
            self.open_path(Path(file))

    def open_path(self, path: Path) -> bool:
        """Charge un projet. En cas d'erreur, le projet actuel reste intact."""
        try:
            result = load_project(path, self.library)
        except ProjectError as exc:
            QMessageBox.critical(self, "Ouverture impossible", str(exc))
            return False
        self._apply(result.meta, result.instances, Path(path), result.floors, result.groups,
                    result.animations)
        notes = []
        if result.missing_assets:
            notes.append(f"{len(result.missing_assets)} image(s) absente(s) de la bibliothèque : "
                         "les objets concernés sont conservés et affichés en rose avec un « ? ».")
        if result.remapped:
            notes.append(f"{result.remapped} objet(s) rattaché(s) à la bibliothèque de cet ordinateur.")
        if notes:
            QMessageBox.information(self, "Projet ouvert", "\n".join(notes))
        return True

    def save(self) -> bool:
        if self.path is None:
            return self.save_as()
        return self.save_to(self.path)

    def save_as(self) -> bool:
        file, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le projet sous", f"{self.meta.name}{EXTENSION}",
            f"Projet Sprite Builder Studio (*{EXTENSION})",
        )
        if not file:
            return False
        path = Path(file)
        if path.suffix.lower() != EXTENSION:
            path = path.with_name(path.name + EXTENSION)
        return self.save_to(path)

    def save_to(self, path: Path) -> bool:
        self.canvas_scene.commit_positions()
        try:
            if self.path is None or Path(path) != self.path:
                self.meta.name = Path(path).stem
            save_project(Path(path), self.meta, self.scene_model, self.library)
        except (OSError, ProjectError) as exc:
            QMessageBox.critical(
                self, "Enregistrement impossible",
                f"{exc}\n\nLe fichier précédent n'a pas été modifié.",
            )
            return False
        self.path = Path(path)
        self.history.mark_saved()
        self._after_saved(self.path)
        self._update_title()
        self.statusBar().showMessage(f"Enregistré : {path}", 4000)
        return True

    # --- aimantation, grille, groupes ---------------------------------------------------------
    def _set_background(self, key: str | None) -> None:
        if key is None:
            self.canvas.set_background(None)
        else:
            _, top, bottom = BACKGROUNDS[key]
            self.canvas.set_background(tuple((a + b) // 2 for a, b in zip(top, bottom)))
        self.prefs.set("view.background", key)

    def open_preview(self) -> None:
        if len(self.scene_model) == 0:
            self.statusBar().showMessage("La scène est vide : rien à prévisualiser.", 5000)
            return
        PreviewDialog(self.canvas_scene, self).exec()

    def open_export(self, kind: str) -> None:
        if len(self.scene_model) == 0:
            self.statusBar().showMessage("La scène est vide : rien à exporter.", 5000)
            return
        ExportDialog(self.canvas_scene, kind, self.meta.name, self).exec()

    def _load_view_prefs(self) -> None:
        key = self.prefs.get("view.background")
        if key in BACKGROUNDS:
            self._set_background(key)
        snap = self.canvas_scene.snap
        snap.grid_size = int(self.prefs.get("snap.grid_size", 32) or 32)
        for act, key in ((self.act_grid, "view.grid"), (self.act_snap_grid, "snap.grid"),
                         (self.act_snap_edges, "snap.edges"), (self.act_snap_anchors, "snap.anchors")):
            act.setChecked(bool(self.prefs.get(key, False)))
        self._snap_changed()

    def _grid_visible_toggled(self, on: bool) -> None:
        self.canvas.set_grid_visible(on)
        self.prefs.set("view.grid", bool(on))

    def _snap_changed(self) -> None:
        snap = self.canvas_scene.snap
        snap.grid, snap.edges = self.act_snap_grid.isChecked(), self.act_snap_edges.isChecked()
        snap.anchors = self.act_snap_anchors.isChecked()
        self.prefs.set("snap.anchors", snap.anchors)
        self.prefs.set("snap.grid", snap.grid)
        self.prefs.set("snap.edges", snap.edges)
        self._update_status()

    def _set_grid_size(self, px: int) -> None:
        self.canvas_scene.snap.grid_size = px
        self.prefs.set("snap.grid_size", px)
        self.canvas.viewport().update()

    def snap_label(self) -> str:
        parts = [n for n, on in (("Grille", self.canvas_scene.snap.grid),
                                 ("Bords", self.canvas_scene.snap.edges),
                                 ("Ancrages", self.canvas_scene.snap.anchors)) if on]
        return "+".join(parts) if parts else "aucun"

    # --- atelier Pixel Art ----------------------------------------------------------------------
    def _palette(self) -> list | None:
        try:
            raw = self.prefs.get("pixel.palette")
            return [check_color(c) for c in raw] if raw else None
        except (ValueError, TypeError):
            return None

    def _save_palette(self, editor: PixelEditor) -> None:
        self.prefs.set("pixel.palette", [list(c) for c in editor.palette])

    def edit_pixels(self) -> bool:
        """Ouvre l'atelier sur le module sélectionné ; au retour, demande la portée avant d'appliquer."""
        asset, variant, ids = self.canvas_scene.pixel_target()
        if asset is None:
            self.statusBar().showMessage(ids, 5000)
            return False
        try:
            doc = load_doc(self.library, asset.uuid, variant)
        except LibraryError as exc:
            QMessageBox.warning(self, "Retouche impossible", str(exc))
            return False
        editor = PixelEditor(doc, self._palette())
        uses = self.canvas_scene.count_uses(asset.uuid)
        note = f"{asset.name}{' / ' + variant if variant else ''} — utilisé {uses} fois"
        dlg = PixelEditorDialog(editor, f"Atelier Pixel Art — {asset.name}", note, self)
        accepted = dlg.exec() == PixelEditorDialog.DialogCode.Accepted
        self._save_palette(editor)
        if not accepted or not editor.modified:
            return False
        box = QMessageBox(self)
        box.setWindowTitle("Appliquer la retouche à…")
        box.setText(f"Ce module est utilisé {uses} fois dans la scène.\nOù appliquer la retouche ?")
        only = box.addButton(f"Cette sélection seulement ({len(ids)})", QMessageBox.ButtonRole.AcceptRole)
        everywhere = box.addButton(f"Toutes les utilisations ({uses})", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(only)
        box.exec()
        clicked = box.clickedButton()
        if clicked not in (only, everywhere):
            return False
        err, uuid = self.canvas_scene.apply_pixels("instance" if clicked is only else "source", png_bytes(doc))
        if err:
            QMessageBox.warning(self, "Retouche impossible", err)
            return False
        save_layers(self.library, uuid, variant, doc)
        self.library_panel.reload_categories()
        self.library_panel.refresh()
        self.statusBar().showMessage("Retouche appliquée (annulable avec Ctrl+Z).", 5000)
        return True

    def new_sprite(self) -> bool:
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QSpinBox
        d = QDialog(self)
        d.setWindowTitle("Nouveau sprite")
        name = QLineEdit("sprite_neuf")
        w, h = QSpinBox(), QSpinBox()
        for sp in (w, h):
            sp.setRange(1, 512)
            sp.setValue(32)
        form = QFormLayout(d)
        form.addRow("Nom", name)
        form.addRow("Largeur (px)", w)
        form.addRow("Hauteur (px)", h)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        form.addRow(bb)
        if d.exec() != QDialog.DialogCode.Accepted:
            return False
        doc = PixelDoc(w.value(), h.value())
        editor = PixelEditor(doc, self._palette())
        dlg = PixelEditorDialog(editor, f"Nouveau sprite — {name.text()}", "Le pivot sera au bas, au centre.", self)
        accepted = dlg.exec() == PixelEditorDialog.DialogCode.Accepted
        self._save_palette(editor)
        if not accepted:
            return False
        try:
            asset = self.library.create_asset(name.text(), png_bytes(doc), (w.value() // 2, h.value() - 1))
        except LibraryError as exc:
            QMessageBox.warning(self, "Création impossible", str(exc))
            return False
        save_layers(self.library, asset.uuid, None, doc)
        self.library_panel.reload_categories()
        self.library_panel.refresh()
        self.canvas.add_asset_at_center(asset.uuid)
        return True

    # --- répétition et animations ---------------------------------------------------------------
    def open_repeat(self) -> bool:
        sel = self.canvas_scene.selection_in_model_order()
        if sel:
            uuid, variant, origin = sel[0].asset_uuid, sel[0].variant, (sel[0].x + 32, sel[0].y)
        else:
            uuid, variant, origin = self.library_panel.current_asset_uuid(), None, self.canvas.visible_center()
        if not uuid or self.library.get(uuid) is None:
            self.statusBar().showMessage("Sélectionne un objet ou un module de la bibliothèque à répéter.", 5000)
            return False
        self._repeat_dialog = RepeatDialog(self.canvas_scene, uuid, variant, origin, self)
        self._repeat_dialog.show()  # non bloquant : l'aperçu reste visible sur le canevas
        return True

    def open_animations(self) -> None:
        AnimationDialog(self.canvas_scene, self.library_panel.current_asset_uuid, self).exec()

    def edit_module_properties(self) -> None:
        if self.canvas_scene.selected_asset() is None:
            self.statusBar().showMessage("Sélectionne un ou plusieurs objets du même module.", 5000)
            return
        ModuleDialog(self.canvas_scene, self).exec()

    def _fill_variant_menu(self) -> None:
        self.variant_menu.clear()
        asset = self.canvas_scene.selected_asset()
        if asset is None or not asset.variants:
            self.variant_menu.addAction("(aucune variante disponible)").setEnabled(False)
            return
        sc = self.canvas_scene
        self.variant_menu.addAction("(base)", lambda: sc.set_variant_selected(None))
        for v in asset.variants:
            self.variant_menu.addAction(v.name, lambda n=v.name: sc.set_variant_selected(n))

    def check_references(self) -> int:
        missing = self.canvas_scene.missing_instances()
        n = self.canvas_scene.select_missing()
        if not missing:
            self.statusBar().showMessage("Toutes les images sont présentes.", 5000)
        else:
            reasons = sorted({r for _, r in missing})
            self.statusBar().showMessage(f"{n} objet(s) sélectionné(s) : " + " ; ".join(reasons), 8000)
        return len(missing)

    def group_selection(self) -> bool:
        error = self.canvas_scene.group_selected()
        if error:
            self.statusBar().showMessage(error, 5000)
        return error is None

    # --- copier / coller / dupliquer -----------------------------------------------------------
    def copy_selection(self) -> bool:
        text = self.canvas_scene.copy_payload()
        if text is None:
            return False
        mime = QMimeData()
        mime.setData(CLIP_MIME, text.encode("utf-8"))
        mime.setText(text)
        QApplication.clipboard().setMimeData(mime)
        self._paste_n = 0
        return True

    def cut_selection(self) -> bool:
        if not self.copy_selection():
            return False
        self.canvas_scene.remove_selected()
        return True

    def paste(self) -> int:
        mime = QApplication.clipboard().mimeData()
        if mime is None or not mime.hasFormat(CLIP_MIME):
            return 0
        text = bytes(mime.data(CLIP_MIME)).decode("utf-8", errors="replace")
        self._paste_n += 1
        step = 8 * self._paste_n  # décalage croissant : on voit les copies
        try:
            pasted, skipped = self.canvas_scene.paste_payload(text, step, step)
        except ValueError:
            self.statusBar().showMessage("Le presse-papiers ne contient pas d'objets de l'atelier.", 4000)
            return 0
        if skipped:
            self.statusBar().showMessage(f"{skipped} objet(s) ignoré(s) : image absente de la bibliothèque.", 5000)
        return pasted

    def duplicate_selection(self) -> int:
        return self.canvas_scene.duplicate_selected(8)

    # --- export -------------------------------------------------------------------------------
    def export_dialog(self, ask_scale: bool) -> None:
        scale = 1
        if ask_scale:
            scale, ok = QInputDialog.getInt(
                self, "Exporter en PNG agrandi", "Facteur d'agrandissement (entier) :", 2, 1, 16
            )
            if not ok:
                return
        file, _ = QFileDialog.getSaveFileName(
            self, "Exporter en PNG", f"{self.meta.name}.png", "Image PNG (*.png)"
        )
        if file:
            path = Path(file)
            if path.suffix.lower() != ".png":
                path = path.with_name(path.name + ".png")
            self.export_to(path, scale)

    def export_to(self, path: Path, scale: int = 1) -> bool:
        self.canvas_scene.commit_positions()
        try:
            r = export_png(Path(path), self.scene_model.draw_instances(), self.library, scale=scale)
        except ExportError as exc:
            QMessageBox.critical(self, "Export impossible", str(exc))
            return False
        msg = f"PNG exporté : {r.width}×{r.height} px (×{r.scale}), {r.count} objet(s)."
        if r.skipped:
            QMessageBox.warning(
                self, "Export incomplet",
                f"{msg}\n\n{len(r.skipped)} objet(s) non dessiné(s) (image absente ou illisible).",
            )
        self.statusBar().showMessage(msg, 6000)
        return True

    # --- disposition --------------------------------------------------
    def _restore_layout(self) -> None:
        geo = self.prefs.get("window.geometry")
        state = self.prefs.get("window.state")
        try:
            if geo:
                self.restoreGeometry(QByteArray(base64.b64decode(geo)))
            if state:
                self.restoreState(QByteArray(base64.b64decode(state)))
        except (ValueError, TypeError):
            self.reset_layout()

    def reset_layout(self) -> None:
        """Remet les panneaux par défaut (jamais de panneau définitivement perdu)."""
        self.restoreState(self._default_state)
        for dock in self.docks.values():
            dock.show()
            dock.setFloating(False)

    def save_layout(self) -> None:
        self.prefs.set("window.geometry", base64.b64encode(bytes(self.saveGeometry())).decode(_B64))
        self.prefs.set("window.state", base64.b64encode(bytes(self.saveState())).decode(_B64))
        self.prefs.save()

    def closeEvent(self, event) -> None:
        if not self._confirm_discard():
            event.ignore()
            return
        self.recovery.clear(self.meta.id)  # fermeture normale : pas de récupération à proposer
        try:
            self.save_layout()
        except OSError as exc:
            QMessageBox.warning(self, "Préférences", f"Impossible d'enregistrer la disposition : {exc}")
        super().closeEvent(event)

    def open_guide(self) -> None:
        GuideDialog(self).exec()

    def _about(self) -> None:
        QMessageBox.about(
            self, "À propos",
            f"Sprite Builder Studio {__version__}\nApplication locale, sans IA.",
        )


__all__ = ["MainWindow", "QWidget"]
