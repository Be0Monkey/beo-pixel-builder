"""Scène graphique : reflète le SceneModel. Toute modification du document passe par une commande
(annulable) exécutée par l'historique ; la scène se resynchronise sur le modèle."""

from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QGraphicsScene

from sbs.canvas.pixmaps import PixmapCache
from sbs.commands.assets import DetachAndEdit, EditSourceGeometry
from sbs.commands.history import History
from sbs.commands.instances import Macro, MoveInstances, RemoveInstances, SetZ
from sbs.commands.structure import (
    AssignLayer,
    PlaceInstancesWithGroups,
    SetGrouping,
    SetStructure,
)
from sbs.domain import groups as G
from sbs.domain.ids import new_id
from sbs.domain.scene import Group, Instance, SceneModel, validate_grouping
from sbs.domain.snapping import SnapResult, SnapSettings, compute_snap
from sbs.services.clipboard_codec import decode_instances, encode_instances
from sbs.services.library import Library, LibraryError

SCENE_HALF = 4096
DIM_OPACITY = 0.35


class InstanceItem(QGraphicsPixmapItem):
    """Image d'une instance. Le déplacement est géré par la vue (aimantation, groupes)."""

    def __init__(self, inst_id: str, pixmap, pivot: tuple[int, int], asset_uuid: str = "",
                 variant: str | None = None):
        super().__init__(pixmap)
        self.inst_id = inst_id
        self.pivot = pivot
        self.asset_uuid = asset_uuid
        self.variant = variant
        self.editable = True
        self.setTransformationMode(Qt.TransformationMode.FastTransformation)  # pixels nets
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

    def pivot_position(self) -> tuple[int, int]:
        return round(self.pos().x()) + self.pivot[0], round(self.pos().y()) + self.pivot[1]

    def place_pivot_at(self, x: int, y: int) -> None:
        self.setPos(x - self.pivot[0], y - self.pivot[1])

    def box(self) -> tuple[int, int, int, int]:
        r = self.pixmap().rect()
        x, y = round(self.pos().x()), round(self.pos().y())
        return x, y, x + r.width(), y + r.height()


class CanvasScene(QGraphicsScene):
    def __init__(self, model: SceneModel, library: Library, history: History | None = None):
        super().__init__()
        self.model = model
        self.library = library
        self.history = history or History(model)
        self.pixmaps = PixmapCache(library)
        self.items_by_id: dict[str, InstanceItem] = {}
        self.snap = SnapSettings()
        self.guides: list[tuple[str, int]] = []
        self.entered_group: str | None = None
        self.active_floor_id = ""
        self.active_layer_id = ""
        self._context_listeners: list[Callable[[], None]] = []
        self.setSceneRect(-SCENE_HALF, -SCENE_HALF, 2 * SCENE_HALF, 2 * SCENE_HALF)
        self.model.add_listener(self.sync)
        self.library.add_listener(self.refresh_asset)

    def add_context_listener(self, fn: Callable[[], None]) -> None:
        self._context_listeners.append(fn)

    def _context_changed(self) -> None:
        for fn in list(self._context_listeners):
            fn()

    # --- synchronisation avec le modèle ----------------------------------------------
    def _make_item(self, inst: Instance) -> InstanceItem:
        asset = self.library.get(inst.asset_uuid)
        pivot = (asset.pivot_x, asset.pivot_y) if asset else (0, 0)
        item = InstanceItem(inst.id, self.pixmaps.get(asset, inst.variant), pivot,
                            inst.asset_uuid, inst.variant)
        item.place_pivot_at(inst.x, inst.y)
        self.addItem(item)
        self.items_by_id[inst.id] = item
        return item

    def refresh_asset(self, asset_uuid: str) -> None:
        """La ressource a changé (pivot, ancrages) : on reconstruit ses items."""
        for inst_id, item in list(self.items_by_id.items()):
            if item.asset_uuid == asset_uuid:
                self.removeItem(item)
                del self.items_by_id[inst_id]

    def sync(self) -> None:
        """Aligne les items sur le modèle (ajouts, suppressions, positions, état, ordre)."""
        instances = self.model.all()
        present = {i.id for i in instances}
        if self.entered_group is not None and self.entered_group not in self.model.groups:
            self.entered_group = None  # le groupe n'existe plus (annulation, suppression)
            self._context_changed()
        for inst_id in [k for k in self.items_by_id if k not in present]:
            self.removeItem(self.items_by_id.pop(inst_id))
        for inst in instances:
            item = self.items_by_id.get(inst.id)
            if item is not None and (item.asset_uuid, item.variant) != (inst.asset_uuid, inst.variant):
                self.removeItem(item)
                del self.items_by_id[inst.id]
                item = None
            if item is None:
                item = self._make_item(inst)
            elif item.pivot_position() != (inst.x, inst.y):
                item.place_pivot_at(inst.x, inst.y)
            self._apply_state(item, inst)
        self.refresh_z()
        self._fix_active_target()

    def _apply_state(self, item: InstanceItem, inst: Instance) -> None:
        visible = self.model.is_visible(inst)
        in_ctx = G.in_context(self.model, inst.id, self.entered_group)
        item.editable = visible and in_ctx and not self.model.is_locked(inst)
        item.setVisible(visible)
        item.setOpacity(1.0 if in_ctx else DIM_OPACITY)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, item.editable)
        if not item.editable and item.isSelected():
            item.setSelected(False)

    def refresh_state(self) -> None:
        for inst in self.model.all():
            item = self.items_by_id.get(inst.id)
            if item is not None:
                self._apply_state(item, inst)

    def rebuild(self) -> None:
        for item in list(self.items_by_id.values()):
            self.removeItem(item)
        self.items_by_id.clear()
        self.sync()

    def refresh_z(self) -> None:
        for rank, inst_id in enumerate(self.model.draw_order()):
            item = self.items_by_id.get(inst_id)
            if item is not None:
                item.setZValue(rank)

    def _fix_active_target(self) -> None:
        if self.model.find_layer(self.active_floor_id, self.active_layer_id) is None:
            self.active_floor_id, self.active_layer_id = self.model.default_target()

    def set_active_target(self, floor_id: str, layer_id: str) -> None:
        if self.model.find_layer(floor_id, layer_id) is not None:
            self.active_floor_id, self.active_layer_id = floor_id, layer_id
            self._context_changed()

    # --- sélection -----------------------------------------------------------------------
    def selected_ids(self) -> list[str]:
        return [i.inst_id for i in self.selectedItems() if isinstance(i, InstanceItem)]

    def select_ids(self, ids: list[str]) -> None:
        self.clearSelection()
        for inst_id in ids:
            item = self.items_by_id.get(inst_id)
            if item is not None:
                item.setSelected(True)  # sans effet si masqué ou verrouillé

    def selection_in_model_order(self) -> list[Instance]:
        chosen = set(self.selected_ids())
        return [i for i in self.model.all() if i.id in chosen]

    def item_at(self, scene_pos: QPointF) -> InstanceItem | None:
        for it in self.items(scene_pos):
            if isinstance(it, InstanceItem) and it.isVisible() and it.editable:
                return it
        return None

    def unit_ids(self, inst_id: str) -> list[str]:
        """Instances à sélectionner quand on clique celle-ci (tout le groupe, sauf si on y est entré)."""
        unit = G.unit_of(self.model, inst_id, self.entered_group)
        if unit is None:
            return []
        return [i for i in G.leaves(self.model, unit) if self.items_by_id[i].editable]

    def select_unit_of(self, inst_id: str, add: bool = False) -> None:
        if not add:
            self.clearSelection()
        for i in self.unit_ids(inst_id):
            self.items_by_id[i].setSelected(True)

    def expand_selection_to_groups(self) -> None:
        """Après un rectangle de sélection : un objet groupé entraîne tout son groupe."""
        wanted: set[str] = set()
        for inst_id in self.selected_ids():
            wanted.update(self.unit_ids(inst_id))
        for inst_id in wanted:
            self.items_by_id[inst_id].setSelected(True)

    # --- opérations (toutes annulables) -------------------------------------------------
    def add_asset(self, asset_uuid: str, x: int, y: int) -> Instance | None:
        asset = self.library.get(asset_uuid)
        if asset is None:
            return None
        self._fix_active_target()
        inst = Instance(new_id(), asset_uuid, int(x), int(y), floor_id=self.active_floor_id,
                        layer_id=self.active_layer_id, group_id=self.entered_group)
        self.history.execute(PlaceInstancesWithGroups([inst], [], f"Ajouter {asset.name}"))
        self.select_ids([inst.id])
        return self.model.get(inst.id)

    def remove_selected(self) -> int:
        ids = [i.id for i in self.selection_in_model_order()]
        if not ids:
            return 0
        name = f"Supprimer {len(ids)} objet(s)"
        cmds = [RemoveInstances(ids, name)]
        groups, group_of = self.model.grouping_snapshot()
        remaining = {k: v for k, v in group_of.items() if k not in set(ids)}
        pruned = G.prune_empty(groups, remaining)
        if len(pruned) != len(groups):  # des groupes se vident : on les retire aussi
            cmds.append(SetGrouping(pruned, remaining, name))
        self.history.execute(cmds[0] if len(cmds) == 1 else Macro(name, cmds))
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

    # --- aimantation pendant un glissement -----------------------------------------------
    def snap_delta(self, start_boxes: list[tuple[int, int, int, int]], primary_pivot: tuple[int, int],
                   dx: int, dy: int, zoom: float, view_rect: QRectF, selected: set[str]) -> SnapResult:
        if not (self.snap.grid or self.snap.edges):
            return SnapResult()
        l = min(b[0] for b in start_boxes) + dx
        t = min(b[1] for b in start_boxes) + dy
        r = max(b[2] for b in start_boxes) + dx
        b = max(b[3] for b in start_boxes) + dy
        others = []
        if self.snap.edges:
            for it in self.items(view_rect):
                if isinstance(it, InstanceItem) and it.isVisible() and it.inst_id not in selected:
                    others.append(it.box())
        pivot = (primary_pivot[0] + dx, primary_pivot[1] + dy)
        return compute_snap((l, t, r, b), pivot, others, self.snap, zoom)

    # --- groupes ----------------------------------------------------------------------------
    def selected_units(self) -> list[tuple[str, str]]:
        units, seen = [], set()
        for inst in self.selection_in_model_order():
            u = G.unit_of(self.model, inst.id, self.entered_group)
            if u is not None and u not in seen:
                seen.add(u)
                units.append(u)
        return units

    def group_selected(self) -> str | None:
        """Groupe la sélection. Renvoie None si fait, sinon un message d'erreur."""
        units = self.selected_units()
        if len(units) < 2:
            return "Sélectionne au moins deux objets (ou groupes) à regrouper."
        groups, group_of = self.model.grouping_snapshot()
        gid = new_id()
        groups[gid] = Group(gid, f"Groupe {len(groups) + 1}", self.entered_group)
        for kind, ident in units:
            if kind == "g":
                groups[ident].parent_id = gid
            else:
                group_of[ident] = gid
        try:
            validate_grouping(groups, group_of)
        except ValueError as exc:
            return str(exc)
        members = [i for u in units for i in G.leaves(self.model, u)]
        self.history.execute(SetGrouping(groups, group_of, "Grouper", members))
        self.select_ids(members)
        return None

    def ungroup_selected(self) -> int:
        """Dissout les groupes sélectionnés (leurs éléments passent au groupe parent)."""
        dissolve = [ident for kind, ident in self.selected_units() if kind == "g"]
        if not dissolve:
            return 0
        groups, group_of = self.model.grouping_snapshot()
        members = [i for g in dissolve for i in G.leaves(self.model, ("g", g))]
        for gid in dissolve:
            parent = groups[gid].parent_id
            for g in groups.values():
                if g.parent_id == gid:
                    g.parent_id = parent
            for iid, owner in group_of.items():
                if owner == gid:
                    group_of[iid] = parent
        for gid in dissolve:
            del groups[gid]
        self.history.execute(SetGrouping(groups, group_of, "Dégrouper", members))
        self.select_ids(members)
        return len(dissolve)

    def enter_group(self, group_id: str | None) -> None:
        if group_id is not None and group_id not in self.model.groups:
            return
        self.entered_group = group_id
        self.refresh_state()
        self.clearSelection()
        self._context_changed()

    def exit_group(self) -> None:
        if self.entered_group is None:
            return
        parent = self.model.groups[self.entered_group].parent_id
        self.enter_group(parent)

    def enter_group_at(self, scene_pos: QPointF) -> bool:
        """Double-clic : entre dans le groupe de l'objet cliqué (True si on est entré)."""
        item = self.item_at(scene_pos)
        if item is None:
            return False
        unit = G.unit_of(self.model, item.inst_id, self.entered_group)
        if unit is None or unit[0] != "g":
            return False
        self.enter_group(unit[1])
        self.select_unit_of(item.inst_id)
        return True

    def group_path(self) -> list[str]:
        return [self.model.groups[g].name for g in reversed(G.chain_of(self.model, self.entered_group))]

    # --- étages / calques -----------------------------------------------------------------------
    def edit_structure(self, name: str, fn: Callable[[list], object], remove_ids: list[str] | None = None):
        """Applique `fn` à une copie des étages puis l'exécute comme UNE commande annulable.
        Lève ValueError si l'opération est invalide (rien n'est modifié)."""
        floors = self.model.floors_copy()
        result = fn(floors)
        cmd = SetStructure(floors, name)
        if remove_ids:
            ids = list(remove_ids)
            cmds = [RemoveInstances(ids, name)]
            groups, group_of = self.model.grouping_snapshot()
            remaining = {k: v for k, v in group_of.items() if k not in set(ids)}
            pruned = G.prune_empty(groups, remaining)
            if len(pruned) != len(groups):
                cmds.append(SetGrouping(pruned, remaining, name))
            cmds.append(cmd)
            cmd = Macro(name, cmds)
        self.history.execute(cmd)
        return result

    def instances_in(self, floor_id: str, layer_id: str | None = None) -> list[Instance]:
        return [i for i in self.model.all()
                if i.floor_id == floor_id and (layer_id is None or i.layer_id == layer_id)]

    def select_content(self, floor_id: str, layer_id: str | None = None) -> int:
        ids = [i.id for i in self.instances_in(floor_id, layer_id)]
        self.select_ids(ids)
        return len(self.selected_ids())

    def move_content(self, floor_id: str, layer_id: str | None, dx: int, dy: int) -> int:
        """Déplace tout un étage (ou calque). Les éléments verrouillés ne bougent pas."""
        moves = {}
        for i in self.instances_in(floor_id, layer_id):
            if not self.model.is_locked(i):
                moves[i.id] = (i.x, i.y, i.x + dx, i.y + dy)
        if moves and (dx or dy):
            self.history.execute(MoveInstances(moves, f"Déplacer l'étage ({len(moves)} objet(s))"))
        return len(moves)

    def assign_selection_to_layer(self, floor_id: str, layer_id: str) -> int:
        changes = {}
        for i in self.selection_in_model_order():
            if (i.floor_id, i.layer_id) != (floor_id, layer_id):
                changes[i.id] = ((i.floor_id, i.layer_id), (floor_id, layer_id))
        if changes:
            self.history.execute(AssignLayer(changes, "Changer de calque"))
        return len(changes)

    def duplicate_floor(self, floor_id: str) -> str | None:
        src = self.model.find_floor(floor_id)
        if src is None:
            return None
        from sbs.domain.scene import Floor, Layer
        mapping = {layer.id: new_id() for layer in src.layers}
        copy = Floor(new_id(), f"{src.name} (copie)", src.elevation_px, src.visible, src.locked,
                     [Layer(mapping[layer.id], layer.name, layer.visible, layer.locked)
                      for layer in src.layers])
        floors = self.model.floors_copy()
        floors.insert(next(n for n, f in enumerate(floors) if f.id == floor_id) + 1, copy)
        new = [Instance(new_id(), i.asset_uuid, i.x, i.y, i.z_manual, i.variant, copy.id,
                        mapping[i.layer_id], None) for i in self.instances_in(floor_id)]
        self.history.execute(Macro("Dupliquer l'étage", [
            SetStructure(floors), PlaceInstancesWithGroups(new, [], "Dupliquer l'étage")]))
        return copy.id

    def duplicate_layer(self, floor_id: str, layer_id: str) -> str | None:
        from sbs.domain.scene import Layer
        src = self.model.find_layer(floor_id, layer_id)
        if src is None:
            return None
        copy = Layer(new_id(), f"{src.name} (copie)", src.visible, src.locked)
        floors = self.model.floors_copy()
        f = next(f for f in floors if f.id == floor_id)
        f.layers.insert(next(n for n, layer in enumerate(f.layers) if layer.id == layer_id) + 1, copy)
        new = [Instance(new_id(), i.asset_uuid, i.x, i.y, i.z_manual, i.variant, floor_id, copy.id, None)
               for i in self.instances_in(floor_id, layer_id)]
        self.history.execute(Macro("Dupliquer le calque", [
            SetStructure(floors), PlaceInstancesWithGroups(new, [], "Dupliquer le calque")]))
        return copy.id

    # --- copier / coller --------------------------------------------------------------------------
    def copy_payload(self) -> str | None:
        """Texte JSON de la sélection (None si rien de sélectionné)."""
        self.commit_positions()
        items = self.selection_in_model_order()
        if not items:
            return None
        return encode_instances(items, self.library, self.model)

    def paste_payload(self, text: str, dx: int, dy: int, name: str = "Coller") -> tuple[int, int]:
        """Colle avec un décalage ; renvoie (collés, ignorés car image inconnue)."""
        entries, clip_groups = decode_instances(text)  # ValueError si le contenu n'est pas le nôtre
        self._fix_active_target()
        gmap = {g.id: new_id() for g in clip_groups}
        new_groups = [Group(gmap[g.id], g.name, gmap.get(g.parent_id) if g.parent_id else self.entered_group)
                      for g in clip_groups]
        new: list[Instance] = []
        skipped = 0
        for e in entries:
            asset = self.library.get(e.asset_uuid)
            if asset is None and e.origin and e.source_id:
                asset = self.library.find_by_source(e.origin, e.source_id)
            if asset is None:
                skipped += 1
                continue
            f, layer = (e.floor_id, e.layer_id) if self.model.find_layer(e.floor_id, e.layer_id) \
                else (self.active_floor_id, self.active_layer_id)
            group = gmap.get(e.group_id) if e.group_id else self.entered_group
            new.append(Instance(new_id(), asset.uuid, e.x + dx, e.y + dy, e.z_manual, e.variant, f, layer, group))
        if new:
            used = {i.group_id for i in new}
            keep = [g for g in new_groups if g.id in used or any(h.parent_id == g.id for h in new_groups)]
            trial, trial_of = self.model.grouping_snapshot()
            trial.update({g.id: g for g in keep})
            try:
                validate_grouping(trial, trial_of)
            except ValueError:  # trop de niveaux une fois collé ici : on colle à plat dans le contexte
                keep = []
                for inst in new:
                    inst.group_id = self.entered_group
            self.history.execute(PlaceInstancesWithGroups(new, keep, f"{name} ({len(new)} objet(s))"))
            self.select_ids([i.id for i in new])
        return len(new), skipped

    def duplicate_selected(self, offset: int = 8) -> int:
        text = self.copy_payload()
        return self.paste_payload(text, offset, offset, "Dupliquer")[0] if text else 0

    # --- ressources : source commune ou instance seule -------------------------------------
    def count_uses(self, asset_uuid: str) -> int:
        return sum(1 for i in self.model.all() if i.asset_uuid == asset_uuid)

    def selected_asset(self):
        """Ressource commune de la sélection, ou None si vide / mélangée."""
        uuids = {i.asset_uuid for i in self.selection_in_model_order()}
        return self.library.get(uuids.pop()) if len(uuids) == 1 else None

    def edit_geometry(self, scope: str, pivot: tuple[int, int], anchors) -> str | None:
        """scope : "source" (toutes les utilisations) ou "instance" (sélection seulement).
        Renvoie None si fait, sinon un message d'erreur."""
        asset = self.selected_asset()
        ids = [i.id for i in self.selection_in_model_order()]
        if asset is None or not ids:
            return "Sélectionne un ou plusieurs objets du même module."
        try:
            if scope == "source":
                cmd = EditSourceGeometry(self.library, asset.uuid, pivot, anchors, ids)
            elif scope == "instance":
                cmd = DetachAndEdit(self.library, ids, pivot, anchors)
            else:
                return "Portée inconnue."
            self.history.execute(cmd)
        except (ValueError, LibraryError) as exc:
            return str(exc)
        self.select_ids(ids)
        return None
