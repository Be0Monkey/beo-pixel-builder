"""Commande : modifier l'ensemble des animations du projet (annulable)."""

from copy import deepcopy

from sbs.commands.base import Command
from sbs.domain.animation import Animation
from sbs.domain.scene import SceneModel


class SetAnimations(Command):
    def __init__(self, old: dict[str, Animation], new: dict[str, Animation], name: str = "Modifier les animations"):
        self.name = name
        self._old, self._new = deepcopy(old), deepcopy(new)

    def do(self, model: SceneModel) -> None:
        model.set_animations(self._new)

    def undo(self, model: SceneModel) -> None:
        model.set_animations(self._old)

    def affected_ids(self) -> list[str]:
        return []
