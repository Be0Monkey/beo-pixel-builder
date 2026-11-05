"""Scène d'export neutre : tout ce qu'un exporteur a besoin de savoir, sans dépendance à Qt."""

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from sbs.domain.scene import SceneModel
from sbs.services.library import Library


@dataclass
class Texture:
    key: str                 # clé stable (uuid + variante)
    filename: str            # nom de fichier dans le dossier d'export (sans dossier)
    source: Path             # fichier PNG d'origine (copié tel quel : transparence intacte)
    asset_uuid: str
    source_id: str
    variant: str | None
    width: int
    height: int
    pivot: tuple[int, int]
    sha256: str


@dataclass
class ExportItem:
    id: str
    name: str                # nom lisible et unique parmi ses frères
    texture: str             # Texture.key
    x: int                   # position du pivot dans la scène
    y: int
    z_manual: int
    group_id: str | None
    draw_index: int          # rang global dans l'ordre de dessin (0 = tout au fond)
    visible: bool            # visibilité réelle (étage ET calque)


@dataclass
class ExportLayer:
    id: str
    name: str
    visible: bool
    locked: bool
    items: list[ExportItem] = field(default_factory=list)  # DANS L'ORDRE DE DESSIN


@dataclass
class ExportFloor:
    id: str
    name: str
    visible: bool
    locked: bool
    elevation_px: int
    layers: list[ExportLayer] = field(default_factory=list)  # du plus bas au plus haut


@dataclass
class ExportScene:
    name: str
    floors: list[ExportFloor]
    textures: dict[str, Texture]
    groups: list[dict]
    animations: list[dict]
    warnings: list[str] = field(default_factory=list)

    def item_count(self) -> int:
        return sum(len(layer.items) for f in self.floors for layer in f.layers)


def safe_name(text: str, fallback: str = "noeud") -> str:
    """Nom compatible Godot et système de fichiers (lettres, chiffres, _ et -)."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")  # É -> E
    cleaned = re.sub(r"[^0-9A-Za-z_\-]+", "_", text.strip()).strip("_")
    return cleaned[:60] or fallback


def _unique(name: str, used: set[str]) -> str:
    base, n = name, 2
    while name in used:
        name, n = f"{base}_{n}", n + 1
    used.add(name)
    return name


def build_export_scene(model: SceneModel, library: Library, name: str = "scene") -> ExportScene:
    order = {iid: n for n, iid in enumerate(model.draw_order())}
    textures: dict[str, Texture] = {}
    filenames: set[str] = set()
    warnings: list[str] = []
    floors: list[ExportFloor] = []
    by_layer: dict[tuple[str, str], list] = {}
    for inst in model.all():
        by_layer.setdefault((inst.floor_id, inst.layer_id), []).append(inst)
    for f in model.floors:
        ef = ExportFloor(f.id, f.name, f.visible, f.locked, f.elevation_px)
        for layer in f.layers:
            el = ExportLayer(layer.id, layer.name, layer.visible, layer.locked)
            names: set[str] = set()
            for inst in sorted(by_layer.get((f.id, layer.id), []), key=lambda i: order[i.id]):
                asset = library.get(inst.asset_uuid)
                if asset is None:
                    warnings.append(f"objet ignoré : module absent de la bibliothèque ({inst.asset_uuid})")
                    continue
                src = library.abs_path(asset.image_for(inst.variant))
                if not src.is_file():
                    warnings.append(f"objet ignoré : image absente ({asset.source_id})")
                    continue
                key = f"{asset.uuid}|{inst.variant or ''}"
                if key not in textures:
                    stem = safe_name(asset.source_id + (f"__{inst.variant}" if inst.variant else ""), "sprite")
                    fname = _unique(stem, filenames) + ".png"
                    textures[key] = Texture(key, fname, src, asset.uuid, asset.source_id, inst.variant,
                                            asset.width, asset.height, (asset.pivot_x, asset.pivot_y),
                                            hashlib.sha256(src.read_bytes()).hexdigest())
                el.items.append(ExportItem(
                    inst.id, _unique(safe_name(asset.source_id, "objet"), names), key, inst.x, inst.y,
                    inst.z_manual, inst.group_id, order[inst.id], f.visible and layer.visible))
            ef.layers.append(el)
        floors.append(ef)
    groups = [{"id": g.id, "name": g.name, "parent_id": g.parent_id} for g in model.groups.values()]
    anims = []
    for a in model.animations.values():
        frames = []
        for fr in a.frames:
            asset = library.get(fr.asset_uuid)
            tex = next((t for t in textures.values() if t.asset_uuid == fr.asset_uuid and t.variant == fr.variant), None)
            frames.append({"source_id": asset.source_id if asset else None, "variant": fr.variant,
                           "hold": fr.hold, "texture": tex.filename if tex else None})
        anims.append({"id": a.id, "name": a.name, "fps": a.fps, "loop": a.loop, "frames": frames})
    return ExportScene(safe_name(name, "scene"), floors, textures, groups, anims, warnings)
