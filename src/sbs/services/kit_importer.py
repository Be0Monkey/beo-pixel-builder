"""Import du kit de sprites (fiches JSON). Voir docs/specs/07_Kit_de_sprites.md.

Règles : copie gérée (jamais de modification du kit), SHA-256, aucune écriture hors de la
bibliothèque, un module défectueux est signalé et ignoré sans arrêter l'import.
"""

import hashlib
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from sbs.domain.asset import Asset, Variant
from sbs.domain.ids import new_id
from sbs.services.library import Library
from sbs.services.thumbnails import make_thumbnail

ORIGIN = "kit"
_KNOWN = {
    "id", "categorie", "description", "taille_px", "ancrage_px", "fichiers", "variantes", "mode",
}


@dataclass
class ImportReport:
    imported: int = 0
    already_present: int = 0
    cancelled: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class KitError(Exception):
    pass


def _safe_join(base: Path, rel: str) -> Path:
    """Refuse les chemins absolus ou qui sortent du dossier du kit."""
    if not isinstance(rel, str) or not rel:
        raise KitError("chemin vide")
    p = (base / rel).resolve()
    if base.resolve() not in p.parents:
        raise KitError(f"chemin interdit : {rel!r}")
    return p


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_cards(kit_dir: Path) -> list[dict[str, Any]]:
    meta = kit_dir / "metadata" / "modules_px"
    index = meta / "_index.json"
    if index.exists():
        data = json.loads(index.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise KitError("_index.json n'est pas une liste")
        return data
    if not meta.is_dir():
        raise KitError("dossier metadata/modules_px introuvable : ce n'est pas un kit")
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(meta.glob("*.json")) if p.name != "_index.json"]


def _copy_png(src: Path, dst_dir: Path) -> tuple[str, tuple[int, int]]:
    """Vérifie que c'est un PNG lisible, le copie, renvoie (sha256, taille)."""
    try:
        with Image.open(src) as im:
            im.verify()
        with Image.open(src) as im:
            size = im.size
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise KitError(f"image illisible : {src.name} ({exc})") from exc
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst_dir / src.name)
    return _sha256(src), size


def import_kit(
    library: Library,
    kit_dir: Path,
    progress: Callable[[int, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> ImportReport:
    kit_dir = Path(kit_dir)
    report = ImportReport()
    try:
        cards = _read_cards(kit_dir)
    except (OSError, ValueError, KitError) as exc:
        raise KitError(f"kit illisible : {exc}") from exc
    sprites_root = kit_dir / "modules_px"
    total = len(cards)

    for i, card in enumerate(cards):
        if cancelled and cancelled():
            report.cancelled = True
            break
        if progress:
            progress(i, total)
        sid = card.get("id") if isinstance(card, dict) else None
        if not isinstance(sid, str) or not sid:
            report.errors.append(f"fiche {i} sans identifiant : ignorée")
            continue
        if library.has_source(ORIGIN, sid):
            report.already_present += 1
            continue
        uuid = new_id()
        dst_dir = library.assets_dir / uuid
        try:
            asset = _build_asset(library, card, sid, uuid, sprites_root, dst_dir, report)
            with library.connect() as db:
                library.insert_asset(db, ORIGIN, asset)
            make_thumbnail(library.abs_path(asset.image_path), library.thumbnail_path(uuid))
            report.imported += 1
        except (KitError, OSError, KeyError, TypeError, ValueError) as exc:
            shutil.rmtree(dst_dir, ignore_errors=True)  # rien de laissé à moitié
            library.thumbnail_path(uuid).unlink(missing_ok=True)
            report.errors.append(f"{sid} : {exc}")
    if progress and not report.cancelled:
        progress(total, total)
    return report


def _build_asset(library: Library, card: dict, sid: str, uuid: str, sprites_root: Path,
                 dst_dir: Path, report: ImportReport) -> Asset:
    files = card.get("fichiers") or {}
    sprite = _safe_join(sprites_root, files["sprite"])
    if not sprite.is_file():
        raise KitError(f"sprite manquant : {files['sprite']}")
    sha, size = _copy_png(sprite, dst_dir)
    declared = card.get("taille_px")
    if declared and list(declared) != list(size):
        report.warnings.append(f"{sid} : taille déclarée {declared} ≠ taille réelle {list(size)}")

    def optional(key: str) -> str | None:
        rel = files.get(key)
        if not rel:
            return None
        try:
            p = _safe_join(sprites_root, rel)
            if not p.is_file():
                raise KitError("absent")
            _copy_png(p, dst_dir)
            return f"assets/{uuid}/{p.name}"
        except KitError as exc:
            report.warnings.append(f"{sid} : {key} ignoré ({exc})")
            return None

    normal, emission = optional("normales"), optional("emission")
    variants: list[Variant] = []
    for vname, rel in (card.get("variantes") or {}).items():
        try:
            p = _safe_join(sprites_root, rel)
            if not p.is_file():
                raise KitError("absent")
            vsha, _ = _copy_png(p, dst_dir)
            variants.append(Variant(vname, f"assets/{uuid}/{p.name}", vsha))
        except KitError as exc:
            report.warnings.append(f"{sid} : variante {vname} ignorée ({exc})")

    anchor = card.get("ancrage_px") or [0, 0]
    return Asset(
        uuid=uuid, source_id=sid, name=sid, category=str(card.get("categorie") or "divers"),
        description=str(card.get("description") or ""), width=size[0], height=size[1],
        pivot_x=int(anchor[0]), pivot_y=int(anchor[1]), mode=str(card.get("mode") or ""),
        image_path=f"assets/{uuid}/{sprite.name}", normal_path=normal, emission_path=emission,
        sha256=sha, variants=tuple(variants),
        extra={k: v for k, v in card.items() if k not in _KNOWN},
    )
