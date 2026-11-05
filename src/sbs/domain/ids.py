"""Identifiants uniques : jamais de nom de fichier comme clé."""

import uuid


def new_id() -> str:
    """Nouvel identifiant UUID4 sous forme de texte."""
    return str(uuid.uuid4())


def is_valid_id(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(uuid.UUID(value)) == value.lower()
    except ValueError:
        return False
