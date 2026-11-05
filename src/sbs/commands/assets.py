"""Commandes qui touchent aux ressources (pivot, ancrages) : source commune ou instance seule."""

from dataclasses import replace

from sbs.commands.base import Command
from sbs.domain.scene import SceneModel
from sbs.services.library import Library


class EditSourceGeometry(Command):
    """Change pivot/ancrages de la SOURCE : toutes les instances liées sont concernées."""

    def __init__(self, library: Library, uuid: str, pivot: tuple[int, int], anchors, ids: list[str]):
        self.name = "Modifier la source"
        self.library, self.uuid, self.pivot, self.anchors = library, uuid, pivot, tuple(anchors)
        self._ids = list(ids)
        old = library.get(uuid)
        if old is None:
            raise ValueError("ressource inconnue")
        self._old = ((old.pivot_x, old.pivot_y), old.anchors, old.revision)
        library.check_geometry(old, pivot, anchors)  # refuse avant d'entrer dans l'historique

    def do(self, model: SceneModel) -> None:
        self.library.update_geometry(self.uuid, self.pivot, self.anchors)
        model.touch()

    def undo(self, model: SceneModel) -> None:
        pivot, anchors, revision = self._old
        self.library.update_geometry(self.uuid, pivot, anchors, revision=revision)
        model.touch()

    def affected_ids(self) -> list[str]:
        return self._ids


class DetachAndEdit(Command):
    """« Cette instance seulement » : clone la ressource, y rattache les instances choisies,
    puis modifie le clone. La source d'origine et les autres instances ne changent pas."""

    def __init__(self, library: Library, ids: list[str], pivot: tuple[int, int], anchors):
        self.name = "Modifier cette instance seulement"
        self.library, self.pivot, self.anchors = library, pivot, tuple(anchors)
        self._ids = list(ids)
        self._clone: str | None = None
        self._previous: dict[str, str] = {}

    def do(self, model: SceneModel) -> None:
        if self._clone is None:
            first = model.get(self._ids[0]).asset_uuid
            src = self.library.get(first)
            if src is None:
                raise ValueError("ressource inconnue")
            self.library.check_geometry(src, self.pivot, self.anchors)
            clone = self.library.clone_asset(first)
            self.library.update_geometry(clone.uuid, self.pivot, self.anchors)
            self._clone = clone.uuid
        self._previous = {i: model.get(i).asset_uuid for i in self._ids}
        with model.batch():
            for i in self._ids:
                model.set_asset(i, self._clone)

    def undo(self, model: SceneModel) -> None:
        with model.batch():
            for i, uuid in self._previous.items():
                model.set_asset(i, uuid)

    def affected_ids(self) -> list[str]:
        return self._ids


class SetVariant(Command):
    def __init__(self, changes: dict[str, tuple[str | None, str | None]], name: str = "Changer de variante"):
        """changes : id -> (ancienne variante, nouvelle variante)."""
        self.name = name
        self.changes = dict(changes)

    def do(self, model: SceneModel) -> None:
        for i, (_, new) in self.changes.items():
            model.set_variant(i, new)

    def undo(self, model: SceneModel) -> None:
        for i, (old, _) in self.changes.items():
            model.set_variant(i, old)

    def affected_ids(self) -> list[str]:
        return list(self.changes)
