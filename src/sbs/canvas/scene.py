"""Scène graphique : reflète le SceneModel. Toute modification du document passe par le modèle."""

from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QGraphicsScene

from sbs.canvas.pixmaps import PixmapCache
from sbs.domain.scene import Instance, SceneModel
from sbs.services.library import Library

SCENE_HALF = 4096


class InstanceItem(QGraphicsPixmapItem):
    def __init__(self, inst_id: str, pixmap, pivot: tuple[int, int]):
        super().__init__(pixmap)
        self.inst_id = inst_id
        self.pivot = pivot
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
    def __init__(self, model: SceneModel, library: Library):
        super().__init__()
        self.model = model
        self.library = library
        self.pixmaps = PixmapCache(library)
        self.items_by_id: dict[str, InstanceItem] = {}
        self.setSceneRect(-SCENE_HALF, -SCENE_HALF, 2 * SCENE_HALF, 2 * SCENE_HALF)

    # --- construction des items ------------------------------------------
    def _make_item(self, inst: Instance) -> InstanceItem:
        asset = self.library.get(inst.asset_uuid)
        pivot = (asset.pivot_x, asset.pivot_y) if asset else (0, 0)
        item = InstanceItem(inst.id, self.pixmaps.get(asset), pivot)
        item.place_pivot_at(inst.x, inst.y)
        self.addItem(item)
        self.items_by_id[inst.id] = item
        return item

    def rebuild(self) -> None:
        """Reconstruit tout depuis le modèle (chargement d'un projet, jalon J1c)."""
        self.clear()
        self.items_by_id.clear()
        for inst in self.model.all():
            self._make_item(inst)
        self.refresh_z()

    # --- opérations ----------------------------------------------------------
    def add_asset(self, asset_uuid: str, x: int, y: int) -> Instance | None:
        if self.library.get(asset_uuid) is None:
            return None
        inst = self.model.add(asset_uuid, int(x), int(y))
        item = self._make_item(inst)
        self.refresh_z()
        self.clearSelection()
        item.setSelected(True)
        return inst

    def selected_ids(self) -> list[str]:
        return [i.inst_id for i in self.selectedItems() if isinstance(i, InstanceItem)]

    def remove_selected(self) -> int:
        ids = self.selected_ids()
        for inst_id in ids:
            item = self.items_by_id.pop(inst_id, None)
            if item is not None:
                self.removeItem(item)
        self.model.remove(ids)
        return len(ids)

    def move_selected(self, dx: int, dy: int) -> None:
        for inst_id in self.selected_ids():
            item = self.items_by_id[inst_id]
            item.setPos(item.pos().x() + dx, item.pos().y() + dy)
        self.commit_positions()

    def commit_positions(self) -> bool:
        """Reporte dans le modèle les positions modifiées à la souris/clavier."""
        changed = False
        for inst_id, item in self.items_by_id.items():
            x, y = item.pivot_position()
            inst = self.model.get(inst_id)
            if (inst.x, inst.y) != (x, y):
                self.model.set_position(inst_id, x, y)
                changed = True
        if changed:
            self.refresh_z()
        return changed

    def shift_z_selected(self, delta: int) -> int:
        """Z manuel : +1 = devant, -1 = derrière (prime sur la profondeur automatique)."""
        ids = self.selected_ids()
        for inst_id in ids:
            self.model.set_z_manual(inst_id, self.model.get(inst_id).z_manual + delta)
        if ids:
            self.refresh_z()
        return len(ids)

    def reset_z_selected(self) -> int:
        """Retour à l'ordre automatique (Z manuel = 0)."""
        ids = self.selected_ids()
        for inst_id in ids:
            self.model.set_z_manual(inst_id, 0)
        if ids:
            self.refresh_z()
        return len(ids)

    def refresh_z(self) -> None:
        for rank, inst_id in enumerate(self.model.draw_order()):
            item = self.items_by_id.get(inst_id)
            if item is not None:
                item.setZValue(rank)
