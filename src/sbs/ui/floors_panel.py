"""Panneau Étages / Calques : afficher, masquer, verrouiller, renommer, réordonner, dupliquer,
supprimer, déplacer un étage entier. Toutes les actions sont annulables (commandes)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sbs.canvas.scene import CanvasScene
from sbs.domain import structure as S

ROLE = Qt.ItemDataRole.UserRole


class FloorsPanel(QWidget):
    def __init__(self, scene: CanvasScene, parent: QWidget | None = None):
        super().__init__(parent)
        self.scene = scene
        self._building = False

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Étage / calque", "Visible", "Verrouillé"])
        self.tree.setColumnWidth(0, 150)
        self.tree.setRootIsDecorated(True)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.currentItemChanged.connect(self._on_current_changed)

        def button(text: str, tip: str, slot) -> QPushButton:
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False: slot())
            return b

        grid = QGridLayout()
        buttons = [
            button("+ Étage", "Ajouter un étage au-dessus", self.add_floor),
            button("+ Calque", "Ajouter un calque dans l'étage", self.add_layer),
            button("Monter", "Passer devant (étage ou calque)", lambda: self.move(+1)),
            button("Descendre", "Passer derrière (étage ou calque)", lambda: self.move(-1)),
            button("Dupliquer", "Dupliquer l'étage ou le calque avec son contenu", self.duplicate),
            button("Supprimer", "Supprimer l'étage ou le calque (et son contenu)", self.delete),
            button("Sélectionner", "Sélectionner tout le contenu", self.select_content),
            button("Envoyer ici", "Mettre la sélection dans ce calque", self.send_selection_here),
            button("Déplacer…", "Déplacer tout le contenu de l'étage ou du calque", self.move_content),
        ]
        for n, b in enumerate(buttons):
            grid.addWidget(b, n // 3, n % 3)
        lay = QVBoxLayout(self)
        lay.addWidget(self.tree, 1)
        lay.addLayout(grid)

        scene.model.add_listener(self.refresh)
        self.refresh()

    # --- affichage ----------------------------------------------------------------
    def _current(self) -> tuple[str, str | None] | None:
        item = self.tree.currentItem()
        return item.data(0, ROLE) if item else None

    def refresh(self) -> None:
        keep = self._current()
        self._building = True
        try:
            self.tree.clear()
            target = None
            for f in reversed(self.scene.model.floors):  # l'étage le plus haut s'affiche en premier
                fi = QTreeWidgetItem([f.name, "", ""])
                self._style(fi, (f.id, None), f.visible, f.locked)
                self.tree.addTopLevelItem(fi)
                for layer in reversed(f.layers):
                    li = QTreeWidgetItem([layer.name, "", ""])
                    self._style(li, (f.id, layer.id), layer.visible, layer.locked)
                    fi.addChild(li)
                    if keep == (f.id, layer.id):
                        target = li
                if keep == (f.id, None):
                    target = fi
                fi.setExpanded(True)
            if target is None:
                target = self._active_item()
            if target is not None:
                self.tree.setCurrentItem(target)
        finally:
            self._building = False

    def _active_item(self):
        for i in range(self.tree.topLevelItemCount()):
            fi = self.tree.topLevelItem(i)
            for j in range(fi.childCount()):
                if fi.child(j).data(0, ROLE) == (self.scene.active_floor_id, self.scene.active_layer_id):
                    return fi.child(j)
        return self.tree.topLevelItem(0)

    @staticmethod
    def _style(item: QTreeWidgetItem, key, visible: bool, locked: bool) -> None:
        item.setData(0, ROLE, key)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(1, Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked)
        item.setCheckState(2, Qt.CheckState.Checked if locked else Qt.CheckState.Unchecked)

    # --- réactions de l'arbre ---------------------------------------------------------------
    def _on_current_changed(self, current, _prev) -> None:
        if self._building or current is None:
            return
        fid, lid = current.data(0, ROLE)
        if lid is None:
            floor = self.scene.model.find_floor(fid)
            lid = floor.layers[-1].id if floor else None
        if lid is not None:
            self.scene.set_active_target(fid, lid)

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._building:
            return
        fid, lid = item.data(0, ROLE)
        model = self.scene.model
        node = model.find_floor(fid) if lid is None else model.find_layer(fid, lid)
        if node is None:
            return
        if column == 0:
            new = item.text(0).strip()
            if new and new != node.name:
                self._run("Renommer", lambda fl: S.rename(fl, fid, lid, new))
            else:
                self.refresh()
        elif column == 1:
            value = item.checkState(1) == Qt.CheckState.Checked
            if value != node.visible:
                self._run(("Afficher " if value else "Masquer ") + node.name,
                          lambda fl: S.set_visible(fl, fid, lid, value))
        elif column == 2:
            value = item.checkState(2) == Qt.CheckState.Checked
            if value != node.locked:
                self._run(("Verrouiller " if value else "Déverrouiller ") + node.name,
                          lambda fl: S.set_locked(fl, fid, lid, value))

    def _run(self, name: str, fn, remove_ids=None) -> bool:
        try:
            self.scene.edit_structure(name, fn, remove_ids)
            return True
        except ValueError as exc:
            QMessageBox.warning(self, "Action impossible", str(exc))
            self.refresh()
            return False

    # --- actions (boutons) ----------------------------------------------------------------------
    def add_floor(self) -> None:
        cur = self._current()
        n = len(self.scene.model.floors) + 1
        self._run("Ajouter un étage", lambda fl: S.add_floor(fl, f"Étage {n}", cur[0] if cur else None))

    def add_layer(self) -> None:
        cur = self._current() or (self.scene.model.floors[0].id, None)
        n = len(self.scene.model.find_floor(cur[0]).layers) + 1
        self._run("Ajouter un calque", lambda fl: S.add_layer(fl, cur[0], f"Calque {n}"))

    def move(self, delta: int) -> None:
        cur = self._current()
        if cur is None:
            return
        fid, lid = cur
        if lid is None:
            self._run("Déplacer l'étage dans la pile", lambda fl: S.move_floor(fl, fid, delta))
        else:
            self._run("Déplacer le calque dans la pile", lambda fl: S.move_layer(fl, fid, lid, delta))

    def duplicate(self) -> None:
        cur = self._current()
        if cur is None:
            return
        fid, lid = cur
        (self.scene.duplicate_floor(fid) if lid is None else self.scene.duplicate_layer(fid, lid))

    def delete(self, confirm: bool = True) -> bool:
        cur = self._current()
        if cur is None:
            return False
        fid, lid = cur
        ids = [i.id for i in self.scene.instances_in(fid, lid)]
        if ids and confirm:
            ok = QMessageBox.question(
                self, "Supprimer",
                f"Cet élément contient {len(ids)} objet(s) qui seront supprimés (annulable). Continuer ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ok != QMessageBox.StandardButton.Yes:
                return False
        if lid is None:
            return self._run("Supprimer l'étage", lambda fl: S.remove_floor(fl, fid), ids)
        return self._run("Supprimer le calque", lambda fl: S.remove_layer(fl, fid, lid), ids)

    def select_content(self) -> int:
        cur = self._current()
        return self.scene.select_content(*cur) if cur else 0

    def send_selection_here(self) -> int:
        cur = self._current()
        if cur is None:
            return 0
        fid, lid = cur
        if lid is None:
            lid = self.scene.model.find_floor(fid).layers[-1].id
        return self.scene.assign_selection_to_layer(fid, lid)

    def move_content(self) -> int:
        cur = self._current()
        if cur is None:
            return 0
        text, ok = QInputDialog.getText(self, "Déplacer", "Décalage « dx, dy » en pixels :", text="0, -32")
        if not ok:
            return 0
        try:
            dx, dy = (int(v) for v in text.replace(";", ",").split(","))
        except ValueError:
            QMessageBox.warning(self, "Décalage invalide", "Écris deux nombres entiers, par exemple : 0, -32")
            return 0
        return self.scene.move_content(cur[0], cur[1], dx, dy)
