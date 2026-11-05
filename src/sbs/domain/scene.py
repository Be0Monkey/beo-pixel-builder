"""Modèle de la scène (sans dépendance à Qt) : étages, calques, groupes, instances placées.

Position (x, y) = position du PIVOT du module (point de contact au sol), en pixels entiers.

Ordre d'affichage (décision D-C) : étage, puis calque, puis Z manuel (0 par défaut), puis
profondeur automatique (y du pivot), puis ordre d'insertion. L'étage 0 de la liste est le plus bas.
`Floor.elevation_px` est réservé (stocké, pas encore appliqué).
"""

from collections.abc import Callable
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field, replace

from sbs.domain.animation import Animation, validate_animation
from sbs.domain.ids import new_id

MAX_GROUP_DEPTH = 3


def _check_int(name: str, v: object) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(f"{name} doit être un entier (reçu : {v!r})")
    return v


@dataclass
class Layer:
    id: str
    name: str
    visible: bool = True
    locked: bool = False


@dataclass
class Floor:
    id: str
    name: str
    elevation_px: int = 0  # réservé
    visible: bool = True
    locked: bool = False
    layers: list[Layer] = field(default_factory=list)


@dataclass
class Group:
    id: str
    name: str = "Groupe"
    parent_id: str | None = None


@dataclass
class Instance:
    id: str
    asset_uuid: str
    x: int
    y: int
    z_manual: int = 0
    variant: str | None = None
    floor_id: str = ""
    layer_id: str = ""
    group_id: str | None = None


def default_floors() -> list[Floor]:
    return [Floor(new_id(), "RDC", layers=[Layer(new_id(), "Calque 1")])]


def validate_floors(floors: list[Floor]) -> None:
    if not floors:
        raise ValueError("il faut au moins un étage")
    seen: set[str] = set()
    for f in floors:
        if not f.layers:
            raise ValueError(f"l'étage « {f.name} » doit avoir au moins un calque")
        for ident in (f.id, *[layer.id for layer in f.layers]):
            if not isinstance(ident, str) or not ident or ident in seen:
                raise ValueError("identifiant d'étage ou de calque invalide ou en double")
            seen.add(ident)


def validate_grouping(groups: dict[str, Group], group_of: dict[str, str | None]) -> None:
    for g in groups.values():
        if g.parent_id is not None and g.parent_id not in groups:
            raise ValueError("groupe parent inconnu")
    for g in groups.values():
        depth, cur, visited = 1, g, {g.id}
        while cur.parent_id is not None:
            if cur.parent_id in visited:
                raise ValueError("cycle de groupes interdit")
            visited.add(cur.parent_id)
            cur = groups[cur.parent_id]
            depth += 1
        if depth > MAX_GROUP_DEPTH:
            raise ValueError(f"groupes imbriqués : {MAX_GROUP_DEPTH} niveaux au maximum")
    for gid in group_of.values():
        if gid is not None and gid not in groups:
            raise ValueError("un objet référence un groupe inconnu")


class SceneModel:
    def __init__(self) -> None:
        self._instances: dict[str, Instance] = {}  # l'ordre du dict = ordre d'insertion
        self._floors: list[Floor] = default_floors()
        self._groups: dict[str, Group] = {}
        self._animations: dict[str, Animation] = {}
        self._listeners: list[Callable[[], None]] = []
        self._batch_depth = 0
        self._pending = False

    # --- notifications --------------------------------------------------------
    def add_listener(self, fn: Callable[[], None]) -> None:
        self._listeners.append(fn)

    def _notify(self) -> None:
        if self._batch_depth > 0:
            self._pending = True
            return
        for fn in list(self._listeners):
            fn()

    @contextmanager
    def batch(self):
        """Regroupe plusieurs modifications en UNE notification (une commande = un rafraîchissement)."""
        self._batch_depth += 1
        try:
            yield
        finally:
            self._batch_depth -= 1
            if self._batch_depth == 0 and self._pending:
                self._pending = False
                self._notify()

    # --- lecture ---------------------------------------------------------------
    def __len__(self) -> int:
        return len(self._instances)

    def __contains__(self, inst_id: str) -> bool:
        return inst_id in self._instances

    def get(self, inst_id: str) -> Instance:
        return self._instances[inst_id]

    def all(self) -> list[Instance]:
        return list(self._instances.values())

    def index_of(self, inst_id: str) -> int:
        return list(self._instances).index(inst_id)

    @property
    def floors(self) -> list[Floor]:
        return self._floors  # lecture seule : on modifie via set_floors()

    @property
    def groups(self) -> dict[str, Group]:
        return self._groups

    @property
    def animations(self) -> dict[str, Animation]:
        return self._animations  # lecture seule : on modifie via set_animations()

    def animations_copy(self) -> dict[str, Animation]:
        return deepcopy(self._animations)

    def set_animations(self, animations: dict[str, Animation]) -> None:
        for key, a in animations.items():
            if key != a.id:
                raise ValueError("identifiant d'animation incohérent")
            validate_animation(a)
        self._animations = deepcopy(animations)
        self._notify()

    def floors_copy(self) -> list[Floor]:
        return deepcopy(self._floors)

    def find_floor(self, floor_id: str) -> Floor | None:
        return next((f for f in self._floors if f.id == floor_id), None)

    def find_layer(self, floor_id: str, layer_id: str) -> Layer | None:
        f = self.find_floor(floor_id)
        return next((layer for layer in f.layers if layer.id == layer_id), None) if f else None

    def default_target(self) -> tuple[str, str]:
        f = self._floors[0]
        return f.id, f.layers[0].id

    def is_visible(self, inst: Instance) -> bool:
        f, layer = self.find_floor(inst.floor_id), self.find_layer(inst.floor_id, inst.layer_id)
        return bool(f and layer and f.visible and layer.visible)

    def is_locked(self, inst: Instance) -> bool:
        f, layer = self.find_floor(inst.floor_id), self.find_layer(inst.floor_id, inst.layer_id)
        return bool(f is None or layer is None or f.locked or layer.locked)

    def snapshot(self) -> list[tuple]:
        """État complet, ordre d'insertion compris (utile aux tests d'annulation)."""
        return [(i.id, i.asset_uuid, i.x, i.y, i.z_manual, i.variant, i.floor_id, i.layer_id,
                 i.group_id) for i in self._instances.values()]

    def draw_order(self) -> list[str]:
        """Du plus loin (dessiné en premier) au plus proche. Déterministe : tri stable."""
        floor_idx = {f.id: n for n, f in enumerate(self._floors)}
        layer_idx = {(f.id, layer.id): n for f in self._floors for n, layer in enumerate(f.layers)}
        ordered = sorted(
            self._instances.values(),
            key=lambda i: (floor_idx.get(i.floor_id, -1), layer_idx.get((i.floor_id, i.layer_id), -1),
                           i.z_manual, i.y),
        )
        return [i.id for i in ordered]

    def draw_instances(self, visible_only: bool = True) -> list[Instance]:
        out = [self._instances[i] for i in self.draw_order()]
        return [i for i in out if self.is_visible(i)] if visible_only else out

    # --- instances --------------------------------------------------------------
    def _check_target(self, inst: Instance) -> None:
        if self.find_layer(inst.floor_id, inst.layer_id) is None:
            raise ValueError("étage ou calque inconnu")

    def add(self, asset_uuid: str, x: int, y: int, inst_id: str | None = None,
            floor_id: str = "", layer_id: str = "") -> Instance:
        if not floor_id or not layer_id:
            floor_id, layer_id = self.default_target()
        inst = Instance(inst_id or new_id(), asset_uuid, _check_int("x", x), _check_int("y", y),
                        floor_id=floor_id, layer_id=layer_id)
        self.add_instance(inst)
        return self._instances[inst.id]

    def add_instance(self, inst: Instance) -> None:
        """Ajoute une copie d'une instance (utilisé par les commandes)."""
        _check_int("x", inst.x), _check_int("y", inst.y), _check_int("z", inst.z_manual)
        if inst.id in self._instances:
            raise ValueError("identifiant d'instance déjà utilisé")
        if not inst.floor_id or not inst.layer_id:
            inst = replace(inst, floor_id=self.default_target()[0], layer_id=self.default_target()[1])
        self._check_target(inst)
        if inst.group_id is not None and inst.group_id not in self._groups:
            raise ValueError("groupe inconnu")
        self._instances[inst.id] = replace(inst)
        self._notify()

    def insert_many(self, indexed: list[tuple[int, Instance]]) -> None:
        """Réinsère des instances à leur rang d'origine (annulation d'une suppression)."""
        items = list(self._instances.values())
        for index, inst in sorted(indexed, key=lambda t: t[0]):
            if any(i.id == inst.id for i in items):
                raise ValueError("identifiant d'instance déjà utilisé")
            self._check_target(inst)
            items.insert(min(index, len(items)), replace(inst))
        self._instances = {i.id: i for i in items}
        self._notify()

    def set_position(self, inst_id: str, x: int, y: int) -> None:
        inst = self._instances[inst_id]
        inst.x, inst.y = _check_int("x", x), _check_int("y", y)
        self._notify()

    def set_z_manual(self, inst_id: str, z: int) -> None:
        self._instances[inst_id].z_manual = _check_int("z", z)
        self._notify()

    def set_layer(self, inst_id: str, floor_id: str, layer_id: str) -> None:
        if self.find_layer(floor_id, layer_id) is None:
            raise ValueError("étage ou calque inconnu")
        inst = self._instances[inst_id]
        inst.floor_id, inst.layer_id = floor_id, layer_id
        self._notify()

    def set_asset(self, inst_id: str, asset_uuid: str) -> None:
        """Rattache l'instance à une autre ressource (détachement, remplacement)."""
        if not isinstance(asset_uuid, str) or not asset_uuid:
            raise ValueError("identifiant de ressource invalide")
        self._instances[inst_id].asset_uuid = asset_uuid
        self._notify()

    def set_variant(self, inst_id: str, variant: str | None) -> None:
        if variant is not None and (not isinstance(variant, str) or not variant):
            raise ValueError("nom de variante invalide")
        self._instances[inst_id].variant = variant
        self._notify()

    def touch(self) -> None:
        """Prévient les écouteurs sans rien changer (ex. une ressource a été modifiée)."""
        self._notify()

    def remove(self, inst_ids) -> list[Instance]:
        removed = [self._instances.pop(i) for i in list(inst_ids) if i in self._instances]
        if removed:
            self._notify()
        return removed

    # --- structure : étages / calques -------------------------------------------------
    def set_floors(self, floors: list[Floor]) -> None:
        validate_floors(floors)
        ok = {(f.id, layer.id) for f in floors for layer in f.layers}
        if any((i.floor_id, i.layer_id) not in ok for i in self._instances.values()):
            raise ValueError("des objets utilisent encore un étage ou un calque supprimé")
        self._floors = deepcopy(floors)
        self._notify()

    # --- structure : groupes ---------------------------------------------------------------
    def grouping_snapshot(self) -> tuple[dict[str, Group], dict[str, str | None]]:
        return deepcopy(self._groups), {i.id: i.group_id for i in self._instances.values()}

    def set_grouping(self, groups: dict[str, Group], group_of: dict[str, str | None]) -> None:
        """Remplace groupes et appartenances. group_of ne concerne que des instances existantes."""
        full = {iid: group_of.get(iid) for iid in self._instances}
        validate_grouping(groups, full)
        self._groups = deepcopy(groups)
        for iid, gid in full.items():
            self._instances[iid].group_id = gid
        self._notify()

    # --- remplacement complet (ouverture d'un projet) -----------------------------------------
    def replace(self, instances: list[Instance], floors: list[Floor] | None = None,
                groups: dict[str, Group] | None = None,
                animations: dict[str, Animation] | None = None) -> None:
        new_floors = deepcopy(floors) if floors is not None else default_floors()
        validate_floors(new_floors)
        new_groups = deepcopy(groups) if groups is not None else {}
        target = (new_floors[0].id, new_floors[0].layers[0].id)
        ok = {(f.id, layer.id) for f in new_floors for layer in f.layers}
        new: dict[str, Instance] = {}
        for inst in instances:
            if inst.id in new:
                raise ValueError("identifiant d'instance en double")
            inst = replace(inst)
            if not inst.floor_id and not inst.layer_id:
                inst.floor_id, inst.layer_id = target
            if (inst.floor_id, inst.layer_id) not in ok:
                raise ValueError("un objet référence un étage ou un calque inconnu")
            new[inst.id] = inst
        validate_grouping(new_groups, {i.id: i.group_id for i in new.values()})
        new_anims = deepcopy(animations) if animations is not None else {}
        for key, a in new_anims.items():
            if key != a.id:
                raise ValueError("identifiant d'animation incohérent")
            validate_animation(a)
        self._instances, self._floors, self._groups = new, new_floors, new_groups
        self._animations = new_anims
        self._notify()
