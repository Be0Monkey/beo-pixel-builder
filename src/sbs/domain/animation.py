"""Animations image par image (sans Qt). Une image = un module de la bibliothèque (+ variante)."""

from dataclasses import dataclass, field

MAX_FRAMES = 256
MAX_HOLD = 100
MAX_FPS = 60


@dataclass
class Frame:
    asset_uuid: str
    variant: str | None = None
    hold: int = 1  # nombre de « tops » pendant lesquels l'image reste affichée


@dataclass
class Animation:
    id: str
    name: str = "Animation"
    fps: int = 8
    loop: bool = True
    frames: list[Frame] = field(default_factory=list)


def _int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate_animation(a: Animation) -> None:
    if not isinstance(a.id, str) or not a.id:
        raise ValueError("animation sans identifiant")
    if not isinstance(a.name, str) or not a.name.strip() or len(a.name) > 80:
        raise ValueError("le nom de l'animation doit faire de 1 à 80 caractères")
    if not _int(a.fps) or not (1 <= a.fps <= MAX_FPS):
        raise ValueError(f"cadence : un entier de 1 à {MAX_FPS} images par seconde")
    if not isinstance(a.loop, bool):
        raise ValueError("« boucle » doit être vrai ou faux")
    if len(a.frames) > MAX_FRAMES:
        raise ValueError(f"{MAX_FRAMES} images au maximum")
    for f in a.frames:
        if not isinstance(f.asset_uuid, str) or not f.asset_uuid:
            raise ValueError("une image d'animation n'a pas de module")
        if f.variant is not None and not isinstance(f.variant, str):
            raise ValueError("variante d'image incorrecte")
        if not _int(f.hold) or not (1 <= f.hold <= MAX_HOLD):
            raise ValueError(f"durée d'une image : un entier de 1 à {MAX_HOLD}")


def total_ticks(a: Animation) -> int:
    return sum(f.hold for f in a.frames)


def frame_index_at(a: Animation, t_ms: int) -> int:
    """Index de l'image affichée au temps t (millisecondes). Boucle ou reste sur la dernière image."""
    total = total_ticks(a)
    if not a.frames or total == 0:
        return -1
    tick = max(0, t_ms) * a.fps // 1000
    tick = tick % total if a.loop else min(tick, total - 1)
    for i, f in enumerate(a.frames):
        if tick < f.hold:
            return i
        tick -= f.hold
    return len(a.frames) - 1
