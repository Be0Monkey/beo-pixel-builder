"""Commandes sur les instances placées."""

from dataclasses import replace

from sbs.commands.base import Command
from sbs.domain.scene import Instance, SceneModel


class PlaceInstances(Command):
    def __init__(self, instances: list[Instance], name: str = "Ajouter"):
        self.name = name
        self._instances = [replace(i) for i in instances]

    def do(self, model: SceneModel) -> None:
        for inst in self._instances:
            model.add_instance(inst)

    def undo(self, model: SceneModel) -> None:
        model.remove([i.id for i in self._instances])

    def affected_ids(self) -> list[str]:
        return [i.id for i in self._instances]


class RemoveInstances(Command):
    def __init__(self, ids: list[str], name: str = "Supprimer"):
        self.name = name
        self._ids = list(ids)
        self._removed: list[tuple[int, Instance]] = []

    def do(self, model: SceneModel) -> None:
        rank = model.index_map()
        self._removed = [(rank[i], replace(model.get(i))) for i in self._ids if i in rank]
        model.remove([inst.id for _, inst in self._removed])

    def undo(self, model: SceneModel) -> None:
        model.insert_many(self._removed)  # même rang qu'avant : l'ordre d'insertion est conservé

    def affected_ids(self) -> list[str]:
        return [inst.id for _, inst in self._removed]


class MoveInstances(Command):
    def __init__(self, moves: dict[str, tuple[int, int, int, int]], name: str = "Déplacer",
                 mergeable: bool = False):
        """moves : id -> (ancien x, ancien y, nouveau x, nouveau y)."""
        self.name = name
        self.mergeable = mergeable
        self.moves = dict(moves)

    def do(self, model: SceneModel) -> None:
        for inst_id, (_, _, nx, ny) in self.moves.items():
            model.set_position(inst_id, nx, ny)

    def undo(self, model: SceneModel) -> None:
        for inst_id, (ox, oy, _, _) in self.moves.items():
            model.set_position(inst_id, ox, oy)

    def affected_ids(self) -> list[str]:
        return list(self.moves)

    def merge(self, other: Command) -> bool:
        if not (isinstance(other, MoveInstances) and other.mergeable
                and self.mergeable and other.moves.keys() == self.moves.keys()):
            return False
        self.moves = {i: (self.moves[i][0], self.moves[i][1], other.moves[i][2], other.moves[i][3])
                      for i in self.moves}
        return True


class SetZ(Command):
    def __init__(self, changes: dict[str, tuple[int, int]], name: str = "Changer l'ordre"):
        """changes : id -> (ancien z, nouveau z)."""
        self.name = name
        self.changes = dict(changes)

    def do(self, model: SceneModel) -> None:
        for inst_id, (_, new) in self.changes.items():
            model.set_z_manual(inst_id, new)

    def undo(self, model: SceneModel) -> None:
        for inst_id, (old, _) in self.changes.items():
            model.set_z_manual(inst_id, old)

    def affected_ids(self) -> list[str]:
        return list(self.changes)


class Macro(Command):
    """Plusieurs commandes présentées comme une seule dans l'historique."""

    def __init__(self, name: str, commands: list[Command]):
        self.name = name
        self._commands = list(commands)

    def do(self, model: SceneModel) -> None:
        for c in self._commands:
            c.do(model)

    def undo(self, model: SceneModel) -> None:
        for c in reversed(self._commands):
            c.undo(model)

    def affected_ids(self) -> list[str]:
        return [i for c in self._commands for i in c.affected_ids()]
