"""Dossier de données utilisateur."""

import os
from pathlib import Path


def user_data_dir() -> Path:
    override = os.environ.get("SBS_DATA_DIR")  # utile pour les tests
    if override:
        return Path(override)
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".config"
    return root / "SpriteBuilderStudio"
