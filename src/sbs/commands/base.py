"""Commande réversible : tout changement du document passe par une commande."""

from abc import ABC, abstractmethod

from sbs.domain.scene import SceneModel


class Command(ABC):
    name: str = "Modification"
    mergeable: bool = False  # peut fusionner avec la commande précédente (gestes continus)

    @abstractmethod
    def do(self, model: SceneModel) -> None: ...

    @abstractmethod
    def undo(self, model: SceneModel) -> None: ...

    def affected_ids(self) -> list[str]:
        """Instances à resélectionner après annulation/rétablissement."""
        return []

    def merge(self, other: "Command") -> bool:
        return False
