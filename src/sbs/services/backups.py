"""Sauvegardes versionnées d'un projet et récupération après un arrêt brutal.

Deux mécanismes complémentaires :

* `BackupStore` : à chaque enregistrement réussi, une copie datée du projet est rangée dans un
  dossier à part (les N plus récentes sont gardées). On peut rouvrir une ancienne version.
* `RecoveryStore` : une sauvegarde automatique du travail en cours (même non enregistré). Elle est
  effacée à l'enregistrement et à la fermeture normale ; si elle existe au démarrage suivant,
  c'est que l'application s'est arrêtée brutalement : on propose de la récupérer.

Toutes les écritures sont atomiques : une coupure en plein milieu laisse la copie précédente intacte.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sbs.services.atomic import write_text_atomic

DEFAULT_KEEP = 10
MAX_KEEP = 200
_SAFE = re.compile(r"[^A-Za-z0-9_-]")


def _safe_id(project_id: str) -> str:
    """Nom de dossier/fichier sûr dérivé d'un identifiant (jamais de chemin venant d'un fichier)."""
    cleaned = _SAFE.sub("", str(project_id))[:64]
    return cleaned or hashlib.sha256(str(project_id).encode("utf-8")).hexdigest()[:16]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class Version:
    path: Path
    created: str  # ISO, UTC
    size: int


class BackupStore:
    def __init__(self, root: Path, keep: int = DEFAULT_KEEP):
        self.root = Path(root)
        self.keep = max(1, min(int(keep), MAX_KEEP))

    def _dir(self, project_id: str) -> Path:
        return self.root / _safe_id(project_id)

    def snapshot(self, project_file: Path, project_id: str) -> Path | None:
        """Range une copie du fichier projet. None si identique à la dernière version ou si impossible
        (une sauvegarde de confort ne doit jamais faire échouer l'enregistrement)."""
        project_file = Path(project_file)
        try:
            data = project_file.read_text(encoding="utf-8")
            versions = self.versions(project_id)
            if versions and versions[0].path.read_text(encoding="utf-8") == data:
                return None
            now = datetime.now(UTC)
            name = now.strftime("%Y%m%dT%H%M%S_") + f"{now.microsecond:06d}Z.sbsproj"
            dest = self._dir(project_id) / name
            write_text_atomic(dest, data)
            self._prune(project_id)
            return dest
        except (OSError, UnicodeDecodeError):
            return None

    def versions(self, project_id: str) -> list[Version]:
        """Versions disponibles, de la plus récente à la plus ancienne."""
        d = self._dir(project_id)
        if not d.is_dir():
            return []
        out = []
        for f in sorted(d.glob("*.sbsproj"), reverse=True):
            try:
                out.append(Version(f, _stamp_to_iso(f.stem), f.stat().st_size))
            except OSError:
                continue
        return out

    def _prune(self, project_id: str) -> None:
        for v in self.versions(project_id)[self.keep:]:
            try:
                v.path.unlink()
            except OSError:
                pass


def _stamp_to_iso(stem: str) -> str:
    try:
        return datetime.strptime(stem.rstrip("Z"), "%Y%m%dT%H%M%S_%f").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return stem


@dataclass(frozen=True)
class RecoveryEntry:
    project_id: str
    file: Path
    name: str
    origin_path: str | None
    saved_at: str


class RecoveryStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _file(self, project_id: str) -> Path:
        return self.root / f"{_safe_id(project_id)}.sbsproj"

    def _info(self, project_id: str) -> Path:
        return self.root / f"{_safe_id(project_id)}.info.json"

    def write(self, project_id: str, text: str, name: str, origin_path: Path | None) -> Path:
        """Écrit d'abord le projet, puis ses informations (deux écritures atomiques). Si on s'arrête
        entre les deux, le projet reste récupérable (nom déduit du fichier)."""
        file = self._file(project_id)
        write_text_atomic(file, text)
        info = {"project_id": project_id, "name": name,
                "origin_path": str(origin_path) if origin_path else None,
                "saved_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")}
        write_text_atomic(self._info(project_id), json.dumps(info, ensure_ascii=False))
        return file

    def clear(self, project_id: str) -> None:
        for f in (self._file(project_id), self._info(project_id)):
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass

    def pending(self) -> list[RecoveryEntry]:
        """Récupérations disponibles, la plus récente d'abord."""
        if not self.root.is_dir():
            return []
        out: list[RecoveryEntry] = []
        for f in self.root.glob("*.sbsproj"):
            name, origin, saved, pid = f.stem, None, "", f.stem
            try:
                info = json.loads(self._info(f.stem).read_text(encoding="utf-8"))
                if isinstance(info, dict):
                    name = str(info.get("name") or name)
                    origin = info.get("origin_path") if isinstance(info.get("origin_path"), str) else None
                    saved = str(info.get("saved_at") or "")
                    pid = str(info.get("project_id") or pid)
            except (OSError, ValueError):
                pass
            if not saved:
                try:
                    saved = datetime.fromtimestamp(f.stat().st_mtime, UTC).strftime("%Y-%m-%d %H:%M:%S")
                except OSError:
                    continue
            out.append(RecoveryEntry(pid, f, name, origin, saved))
        out.sort(key=lambda e: e.saved_at, reverse=True)
        return out


def remove_leftovers(root: Path) -> int:
    """Supprime les fichiers temporaires `.tmp` laissés par une écriture interrompue."""
    n = 0
    root = Path(root)
    if root.is_dir():
        for f in root.rglob("*.tmp"):
            try:
                f.unlink()
                n += 1
            except OSError:
                pass
    return n


__all__ = ["BackupStore", "RecoveryStore", "RecoveryEntry", "Version", "remove_leftovers"]
