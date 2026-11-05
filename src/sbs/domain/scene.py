"""Modèle de la scène (sans dépendance à Qt) : instances de modules placées.

Position (x, y) = position du PIVOT du module (point de contact au sol), en pixels entiers.
Ordre d'affichage (voir docs/specs, décision D-C) : Z manuel d'abord (0 par défaut), puis
profondeur automatique (y du pivot), puis ordre d'insertion. Étages et calques : jalon J2.
"""

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, replace

from sbs.domain.ids import new_id


def _check_int(name: str, v: object) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(f"{name} doit être un entier (reçu : {v!r})")
    return v


@dataclass
class Instance:
    id: str
    asset_uuid: str
    x: int
    y: int
    z_manual: int = 0
    variant: str | None = None


class SceneModel:
    def __init__(self) -> None:
        self._instances: dict[str, Instance] = {}  # l'ordre du dict = ordre d'insertion
        self._listeners: list[Callable[[], None]] = []
        self._batch_depth = 0
        self._pending = False

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

    def snapshot(self) -> list[tuple]:
        """État complet, ordre d'insertion compris (utile aux tests d'annulation)."""
        return [(i.id, i.asset_uuid, i.x, i.y, i.z_manual, i.variant) for i in self._instances.values()]

    def add_instance(self, inst: Instance) -> None:
        """Ajoute une copie d'une instance existante (utilisé par les commandes)."""
        _check_int("x", inst.x), _check_int("y", inst.y), _check_int("z", inst.z_manual)
        if inst.id in self._instances:
            raise ValueError("identifiant d'instance déjà utilisé")
        self._instances[inst.id] = replace(inst)
        self._notify()

    def insert_many(self, indexed: list[tuple[int, Instance]]) -> None:
        """Réinsère des instances à leur rang d'origine (annulation d'une suppression)."""
        items = list(self._instances.values())
        for index, inst in sorted(indexed, key=lambda t: t[0]):
            if inst.id in self._instances or any(i.id == inst.id for i in items):
                raise ValueError("identifiant d'instance déjà utilisé")
            items.insert(min(index, len(items)), replace(inst))
        self._instances = {i.id: i for i in items}
        self._notify()

    def index_of(self, inst_id: str) -> int:
        return list(self._instances).index(inst_id)

    def replace(self, instances: list[Instance]) -> None:
        """Remplace tout le contenu (chargement / nouveau projet). Une seule notification."""
        new: dict[str, Instance] = {}
        for inst in instances:
            if inst.id in new:
                raise ValueError("identifiant d'instance en double")
            new[inst.id] = inst
        self._instances = new
        self._notify()

    def __len__(self) -> int:
        return len(self._instances)

    def __contains__(self, inst_id: str) -> bool:
        return inst_id in self._instances

    def get(self, inst_id: str) -> Instance:
        return self._instances[inst_id]

    def all(self) -> list[Instance]:
        return list(self._instances.values())

    def add(self, asset_uuid: str, x: int, y: int, inst_id: str | None = None) -> Instance:
        inst = Instance(inst_id or new_id(), asset_uuid, _check_int("x", x), _check_int("y", y))
        if inst.id in self._instances:
            raise ValueError("identifiant d'instance déjà utilisé")
        self._instances[inst.id] = inst
        self._notify()
        return inst

    def set_position(self, inst_id: str, x: int, y: int) -> None:
        inst = self._instances[inst_id]
        inst.x, inst.y = _check_int("x", x), _check_int("y", y)
        self._notify()

    def set_z_manual(self, inst_id: str, z: int) -> None:
        self._instances[inst_id].z_manual = _check_int("z", z)
        self._notify()

    def remove(self, inst_ids) -> list[Instance]:
        removed = [self._instances.pop(i) for i in list(inst_ids) if i in self._instances]
        if removed:
            self._notify()
        return removed

    def draw_order(self) -> list[str]:
        """Du plus loin (dessiné en premier) au plus proche. Déterministe : tri stable."""
        ordered = sorted(self._instances.values(), key=lambda i: (i.z_manual, i.y))
        return [i.id for i in ordered]
