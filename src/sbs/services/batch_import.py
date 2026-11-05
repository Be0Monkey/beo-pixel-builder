"""Import d'images en lot (fichiers ou dossiers) vers la bibliothèque.

Formats : PNG (copié tel quel, octet pour octet) ; GIF, BMP et WebP sont convertis en PNG RGBA
(pour un GIF/WebP animé, seule la première image est retenue). Les originaux ne sont jamais modifiés.
Une image illisible, trop grande ou vide est signalée et ignorée sans arrêter le lot.
"""

import hashlib
import io
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from sbs.services.library import Library, LibraryError

FORMATS = (".png", ".gif", ".bmp", ".webp")
MAX_SIDE = 4096
MAX_FILES = 20000
DEFAULT_CATEGORY = "importé"


@dataclass
class BatchReport:
    imported: list[str] = field(default_factory=list)  # uuid des nouveaux modules
    duplicates: int = 0  # contenu déjà présent (non réimporté)
    errors: list[str] = field(default_factory=list)
    cancelled: bool = False
    ignored: int = 0  # fichiers d'un format non géré rencontrés dans un dossier


def collect_files(paths: Iterable[Path], recursive: bool = True) -> tuple[list[Path], int]:
    """Développe fichiers et dossiers. Retourne (images à importer, nombre de fichiers ignorés)."""
    found: list[Path] = []
    ignored = 0
    seen: set[Path] = set()

    def add(p: Path, explicit: bool) -> None:
        nonlocal ignored
        if p.suffix.lower() in FORMATS:
            key = p.resolve()
            if key not in seen:
                seen.add(key)
                found.append(p)
        elif not explicit:
            ignored += 1
        else:
            found.append(p)  # demandé explicitement : sera signalé comme erreur de format
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            it = p.rglob("*") if recursive else p.glob("*")
            for f in sorted(it):
                if f.is_file() and not f.name.startswith("."):
                    add(f, False)
        else:
            add(p, True)
    return found[:MAX_FILES], ignored


def _to_png(path: Path) -> tuple[bytes, tuple[int, int]]:
    """PNG prêt à stocker. Lève ValueError avec un message compréhensible."""
    if path.suffix.lower() not in FORMATS:
        raise ValueError(f"format non géré ({path.suffix or 'sans extension'}) ; formats : "
                         + ", ".join(f[1:].upper() for f in FORMATS))
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"lecture impossible : {exc}") from exc
    try:
        with Image.open(io.BytesIO(raw)) as im:
            w, h = im.size  # lu dans l'en-tête, avant tout décodage
            if w < 1 or h < 1:
                raise ValueError("image vide")
            if w > MAX_SIDE or h > MAX_SIDE:
                raise ValueError(f"image trop grande ({w}×{h} ; maximum {MAX_SIDE}×{MAX_SIDE})")
            fmt = im.format
            if fmt == "PNG" and path.suffix.lower() == ".png":
                im.load()  # vérifie que les données se décodent vraiment
                return raw, (w, h)
            im.seek(0)
            rgba = im.convert("RGBA")
        out = io.BytesIO()
        rgba.save(out, "PNG")
        return out.getvalue(), (w, h)
    except ValueError:
        raise
    except Exception as exc:  # image corrompue, bombe de décompression, format interne douteux…
        raise ValueError(f"image illisible ({type(exc).__name__}) : {exc}") from exc


def find_local_by_sha(library: Library, sha256: str) -> str | None:
    with library.connect() as db:
        r = db.execute("SELECT uuid FROM assets WHERE origin='local' AND sha256=?", (sha256,)).fetchone()
    return r["uuid"] if r else None


def import_images(
    library: Library,
    files: list[Path],
    category: str = DEFAULT_CATEGORY,
    progress: Callable[[int, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> BatchReport:
    """Importe chaque image comme module « local » (pivot au milieu du bas)."""
    report = BatchReport()
    total = len(files)
    for i, f in enumerate(files):
        if cancelled is not None and cancelled():
            report.cancelled = True
            break
        if progress is not None:
            progress(i, total)
        try:
            png, (w, h) = _to_png(Path(f))
            sha = hashlib.sha256(png).hexdigest()
            if find_local_by_sha(library, sha) is not None:
                report.duplicates += 1
                continue
            name = Path(f).stem or "sprite"
            asset = library.create_asset(name, png, (w // 2, h - 1), category)
            report.imported.append(asset.uuid)
        except (ValueError, LibraryError, OSError) as exc:
            report.errors.append(f"{Path(f).name} : {exc}")
    if progress is not None and not report.cancelled:
        progress(total, total)
    return report
