"""Préférences utilisateur (JSON versionné, sauvegarde atomique, tolérant aux erreurs)."""

import json
from pathlib import Path
from typing import Any

from sbs.domain.schema import PREFERENCES_SCHEMA_VERSION
from sbs.services.atomic import write_text_atomic


class Preferences:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._data: dict[str, Any] = {}
        self.load_error: str | None = None
        self.load()

    def load(self) -> None:
        self._data = {}
        self.load_error = None
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("le fichier n'est pas un objet JSON")
            version = raw.get("schema_version")
            if version != PREFERENCES_SCHEMA_VERSION:
                raise ValueError(f"version de préférences non prise en charge : {version!r}")
            values = raw.get("values", {})
            if not isinstance(values, dict):
                raise ValueError("section 'values' invalide")
            self._data = values
        except (OSError, ValueError) as exc:  # JSONDecodeError hérite de ValueError
            # Préférences illisibles : on repart de zéro sans détruire le fichier.
            self.load_error = str(exc)
            self._data = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def save(self) -> None:
        payload = {"schema_version": PREFERENCES_SCHEMA_VERSION, "values": self._data}
        write_text_atomic(self.path, json.dumps(payload, indent=2, ensure_ascii=False))
