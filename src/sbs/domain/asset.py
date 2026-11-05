"""Ressource (sprite) de la bibliothèque. Sans dépendance à Qt."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Variant:
    name: str
    image_path: str  # relatif à la racine de la bibliothèque
    sha256: str


@dataclass(frozen=True)
class Asset:
    uuid: str
    source_id: str  # ex. "angle_rdc_droit" (id du kit) - jamais une clé primaire
    name: str
    category: str
    description: str
    width: int
    height: int
    pivot_x: int  # ancrage_px du kit
    pivot_y: int
    mode: str
    image_path: str
    normal_path: str | None
    emission_path: str | None
    sha256: str
    revision: int = 1
    variants: tuple[Variant, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)  # champs du kit conservés tels quels
    origin: str = ""  # ex. "kit"

    def image_for(self, variant: str | None) -> str:
        """Chemin de l'image à afficher pour une variante (base si absente ou inconnue)."""
        if variant:
            for v in self.variants:
                if v.name == variant:
                    return v.image_path
        return self.image_path
