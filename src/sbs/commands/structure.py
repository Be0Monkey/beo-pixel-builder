"""Commandes d'étages, calques et groupes (par instantané : fiables et simples à annuler)."""

from copy import deepcopy
from dataclasses import replace

from sbs.commands.base import Command
from sbs.domain.scene import Floor, Group, Instance, SceneModel


class SetStructure(Command):
    def __init__(self, floors: list[Floor], name: str = "Modifier les étages"):
        self.name = name
        self._new = deepcopy(floors)
        self._old: list[Floor] = []

    def do(self, model: SceneModel) -> None:
        self._old = model.floors_copy()
        model.set_floors(self._new)

    def undo(self, model: SceneModel) -> None:
        model.set_floors(self._old)


class AssignLayer(Command):
    def __init__(self, changes: dict[str, tuple[tuple[str, str], tuple[str, str]]],
                 name: str = "Changer de calque"):
        """changes : id -> ((ancien étage, ancien calque), (nouvel étage, nouveau calque))."""
        self.name = name
        self.changes = dict(changes)

    def do(self, model: SceneModel) -> None:
        for iid, (_, (f, layer)) in self.changes.items():
            model.set_layer(iid, f, layer)

    def undo(self, model: SceneModel) -> None:
        for iid, ((f, layer), _) in self.changes.items():
            model.set_layer(iid, f, layer)

    def affected_ids(self) -> list[str]:
        return list(self.changes)


class SetGrouping(Command):
    def __init__(self, groups: dict[str, Group], group_of: dict[str, str | None],
                 name: str = "Grouper", affected: list[str] | None = None):
        self.name = name
        self._new = (deepcopy(groups), dict(group_of))
        self._old: tuple[dict[str, Group], dict[str, str | None]] = ({}, {})
        self._affected = list(affected or [])

    def do(self, model: SceneModel) -> None:
        self._old = model.grouping_snapshot()
        model.set_grouping(*self._new)

    def undo(self, model: SceneModel) -> None:
        model.set_grouping(*self._old)

    def affected_ids(self) -> list[str]:
        return self._affected


class PlaceInstancesWithGroups(Command):
    """Ajoute des instances et leurs nouveaux groupes (coller, dupliquer, dupliquer un étage)."""

    def __init__(self, instances: list[Instance], groups: list[Group], name: str):
        self.name = name
        self._instances = [replace(i) for i in instances]
        self._groups = [replace(g) for g in groups]

    def do(self, model: SceneModel) -> None:
        g, a = model.grouping_snapshot()
        g.update({gr.id: replace(gr) for gr in self._groups})
        model.set_grouping(g, a)
        for inst in self._instances:
            model.add_instance(inst)

    def undo(self, model: SceneModel) -> None:
        model.remove([i.id for i in self._instances])
        g, a = model.grouping_snapshot()
        for gr in self._groups:
            g.pop(gr.id, None)
        model.set_grouping(g, a)

    def affected_ids(self) -> list[str]:
        return [i.id for i in self._instances]
