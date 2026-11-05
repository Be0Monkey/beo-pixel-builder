"""Socle des exporteurs : protocole, dossier de destination sûr, écriture atomique, rapport."""

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from sbs.exporters.model import ExportScene

MARKER = ".sbs_export.json"


class ExportRefused(Exception):
    """Message destiné à l'utilisateur : l'export n'a rien écrit."""


class Exporter(Protocol):
    name: str
    label: str

    def plan(self, scene: ExportScene, options: dict) -> dict[str, bytes | Path]:
        """Fichiers à écrire : chemin relatif (avec « / ») -> octets ou fichier à copier."""
        ...


@dataclass
class ExportReport:
    ok: bool
    exporter: str
    files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str = ""


def _check_relative(rel: str) -> None:
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts or rel.startswith(("/", "\\")) or ":" in rel:
        raise ExportRefused(f"chemin d'export interdit : {rel}")


def check_destination(dest: Path, files: dict[str, bytes | Path]) -> set[str]:
    """Règle de sécurité : on n'écrase jamais des fichiers qui ne sont pas les nôtres.
    - dossier absent ou vide : autorisé ;
    - dossier déjà exporté par l'appli (fichier marqueur) : seuls les fichiers listés peuvent être remplacés ;
    - tout autre dossier non vide : refusé, sauf pour un fichier qui n'existe pas encore (rien n'est écrasé).
    Renvoie les fichiers existants qui seront remplacés."""
    replaced: set[str] = set()
    owned: set[str] = set()
    marker = dest / MARKER
    if marker.is_file():
        try:
            owned = set(json.loads(marker.read_text(encoding="utf-8")).get("files", []))
        except (OSError, ValueError):
            owned = set()
    for rel in files:
        _check_relative(rel)
        target = dest / rel
        if target.exists():
            if rel not in owned:
                raise ExportRefused(f"« {rel} » existe déjà dans le dossier choisi et n'a pas été créé par "
                                    "cette appli : rien n'a été écrit. Choisis un dossier vide ou un autre nom.")
            replaced.add(rel)
    return replaced


def _atomic_write(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=target.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def run_export(exporter: Exporter, scene: ExportScene, dest: Path, options: dict | None = None) -> ExportReport:
    """Exécute un exporteur sans jamais lever d'exception vers l'appelant."""
    options = dict(options or {})
    try:
        if scene.item_count() == 0:
            raise ExportRefused("la scène ne contient aucun objet à exporter")
        files = exporter.plan(scene, options)
        dest = Path(dest)
        check_destination(dest, files)
        written: list[str] = []
        for rel, content in files.items():
            _atomic_write(dest / rel, content if isinstance(content, bytes) else Path(content).read_bytes())
            written.append(rel)
        _atomic_write(dest / MARKER, json.dumps({"exporter": exporter.name, "files": written},
                                                indent=1).encode("utf-8"))
        return ExportReport(True, exporter.name, written, list(scene.warnings))
    except ExportRefused as exc:
        return ExportReport(False, exporter.name, [], list(scene.warnings), str(exc))
    except Exception as exc:  # un exporteur ne doit jamais faire tomber l'application
        return ExportReport(False, exporter.name, [], list(scene.warnings), f"export impossible : {exc}")
