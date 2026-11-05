"""Scène graphique : reflète le SceneModel. Toute modification du document passe par une commande
(annulable) exécutée par l'historique ; la scène se resynchronise sur le modèle."""

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QGraphicsScene

from sbs.canvas.pixmaps import PixmapCache
from sbs.commands.history import History
from sbs.commands.instances import MoveInstances, PlaceInstances, RemoveInstances, SetZ
from sbs.domain.ids import new_id
from sbs.domain.scene import Instance, SceneModel
from sbs.services.clipboard_codec import decode_instances, encode_instances
from sbs.services.library import Library

SCENE_HALF = 4096


class InstanceItem(QGraphicsPixmapItem):
    def __init__(self, inst_id: str, pixmap, pivot: tuple[int, int], asset_uuid: str = "",
                 variant: str | None = None):
        super().__init__(pixmap)
        self.inst_id = inst_id
        self.pivot = pivot
        self.asset_uuid = asset_uuid
        self.variant = variant
        self.setTransformationMode(Qt.TransformationMode.FastTransformation)  # pixels nets
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            return QPointF(round(value.x()), round(value.y()))  # toujours au pixel entier
        return super().itemChange(change, value)

    def pivot_position(self) -> tuple[int, int]:
        return round(self.pos().x()) + self.pivot[0], round(self.pos().y()) + self.pivot[1]

    def place_pivot_at(self, x: int, y: int) -> None:
        self.setPos(x - self.pivot[0], y - self.pivot[1])


class CanvasScene(QGraphicsScene):
    def __init__(self, model: SceneModel, library: Library, history: History | None = None):
        super().__init__()
        self.model = model
        self.library = library
        self.history = history or History(model)
        self.pixmaps = PixmapCache(library)
        self.items_by_id: dict[str, InstanceItem] = {}
        self.setSceneRect(-SCENE_HALF, -SCENE_HALF, 2 * SCENE_HALF, 2 * SCENE_HALF)
        self.model.add_listener(self.sync)

    # --- synchronisation avec le modèle -------------------------------------------------
    def _make_item(self, inst: Instance) -> InstanceItem:
        asset = self.library.get(inst.asset_uuid)
        pivot = (asset.pivot_x, asset.pivot_y) if asset else (0, 0)
        item = InstanceItem(inst.id, self.pixmaps.get(asset, inst.variant), pivot,
                            inst.asset_uuid, inst.variant)
        item.place_pivot_at(inst.x, inst.y)
        self.addItem(item)
        self.items_by_id[inst.id] = item
        return item

    def sync(self) -> None:
        """Aligne les items sur le modèle (ajouts, suppressions, positions, variantes, ordre)."""
        instances = self.model.all()
        present = {i.id for i in instances}
        for inst_id in [k for k in self.items_by_id if k not in present]:
            self.removeItem(self.items_by_id.pop(inst_id))
        for inst in instances:
            item = self.items_by_id.get(inst.id)
            if item is None:
                self._make_item(inst)
                continue
            if (item.asset_uuid, item.variant) != (inst.asset_uuid, inst.variant):
                self.removeItem(item)
                del self.items_by_id[inst.id]
                self._make_item(inst)
                continue
            if item.pivot_position() != (inst.x, inst.y):
                item.place_pivot_at(inst.x, inst.y)
        self.refresh_z()

    def rebuild(self) -> None:
        """Reconstruit tout depuis le modèle."""
        for item in list(self.items_by_id.values()):
            self.removeItem(item)
        self.items_by_id.clear()
        self.sync()

    def select_ids(self, ids: list[str]) -> None:
        self.clearSelection()
        for inst_id in ids:
            item = self.items_by_id.get(inst_id)
            if item is not None:
                item.setSelected(True)

    # --- opérations (toutes annulables) -----------------------------------------------------
    def add_asset(self, asset_uuid: str, x: int, y: int) -> Instance | None:
        asset = self.library.get(asset_uuid)
        if asset is None:
            return None
        inst = Instance(new_id(), asset_uuid, int(x), int(y))
        self.history.execute(PlaceInstances([inst], f"Ajouter {asset.name}"))
        self.select_ids([inst.id])
        return self.model.get(inst.id)

    def selected_ids(self) -> list[str]:
        return [i.inst_id for i in self.selectedItems() if isinstance(i, InstanceItem)]

    def selection_in_model_order(self) -> list[Instance]:
        chosen = set(self.selected_ids())
        return [i for i in self.model.all() if i.id in chosen]

    def remove_selected(self) -> int:
        ids = [i.id for i in self.selection_in_model_order()]
        if ids:
            self.history.execute(RemoveInstances(ids, f"Supprimer {len(ids)} objet(s)"))
        return len(ids)

    def move_selected(self, dx: int, dy: int) -> None:
        for inst_id in self.selected_ids():
            item = self.items_by_id[inst_id]
            item.setPos(item.pos().x() + dx, item.pos().y() + dy)
        self.commit_positions(keyboard=True)

    def commit_positions(self, keyboard: bool = False) -> bool:
        """Transforme les déplacements faits sur la scène en UNE commande annulable."""
        moves = {}
        for inst_id, item in self.items_by_id.items():
            x, y = item.pivot_position()
            inst = self.model.get(inst_id)
            if (inst.x, inst.y) != (x, y):
                moves[inst_id] = (inst.x, inst.y, x, y)
        if not moves:
            return False
        name = "Déplacer au clavier" if keyboard else f"Déplacer {len(moves)} objet(s)"
        self.history.execute(MoveInstances(moves, name, mergeable=keyboard))
        return True

    def shift_z_selected(self, delta: int) -> int:
        """Z manuel : +1 = devant, -1 = derrière (prime sur la profondeur automatique)."""
        sel = self.selection_in_model_order()
        if sel:
            name = "Mettre devant" if delta > 0 else "Mettre derrière"
            self.history.execute(SetZ({i.id: (i.z_manual, i.z_manual + delta) for i in sel}, name))
        return len(sel)

    def reset_z_selected(self) -> int:
        sel = [i for i in self.selection_in_model_order() if i.z_manual != 0]
        if sel:
            self.history.execute(SetZ({i.id: (i.z_manual, 0) for i in sel}, "Ordre automatique"))
        return len(sel)

    def undo(self):
        cmd = self.history.undo()
        if cmd:
            self.select_ids(cmd.affected_ids())
        return cmd

    def redo(self):
        cmd = self.history.redo()
        if cmd:
            self.select_ids(cmd.affected_ids())
        return cmd

    # --- copier / coller -------------------------------------------------------------------
    def copy_payload(self) -> str | None:
        """Texte JSON de la sélection (None si rien de sélectionné)."""
        self.commit_positions()
        items = self.selection_in_model_order()
        return encode_instances(items, self.library) if items else None

    def paste_payload(self, text: str, dx: int, dy: int, name: str = "Coller") -> tuple[int, int]:
        """Colle avec un décalage ; renvoie (collés, ignorés car image inconnue)."""
        entries = decode_instances(text)  # ValueError si le contenu n'est pas le nôtre
        new: list[Instance] = []
        skipped = 0
        for e in entries:
            asset = self.library.get(e.asset_uuid)
            if asset is None and e.origin and e.source_id:
                asset = self.library.find_by_source(e.origin, e.source_id)
            if asset is None:
                skipped += 1
                continue
            new.append(Instance(new_id(), asset.uuid, e.x + dx, e.y + dy, e.z_manual, e.variant))
        if new:
            self.history.execute(PlaceInstances(new, f"{name} ({len(new)} objet(s))"))
            self.select_ids([i.id for i in new])
        return len(new), skipped

    def duplicate_selected(self, offset: int = 8) -> int:
        text = self.copy_payload()
        return self.paste_payload(text, offset, offset, "Dupliquer")[0] if text else 0

    def refresh_z(self) -> None:
        for rank, inst_id in enumerate(self.model.draw_order()):
            item = self.items_by_id.get(inst_id)
            if item is not None:
                item.setZValue(rank)
