"""Opérations pures sur la liste des étages (appliquées à une copie, puis exécutées en commande)."""

from sbs.domain.ids import new_id
from sbs.domain.scene import Floor, Layer


def _floor(floors: list[Floor], floor_id: str) -> Floor:
    for f in floors:
        if f.id == floor_id:
            return f
    raise ValueError("étage inconnu")


def _layer(floors: list[Floor], floor_id: str, layer_id: str) -> tuple[Floor, Layer]:
    f = _floor(floors, floor_id)
    for layer in f.layers:
        if layer.id == layer_id:
            return f, layer
    raise ValueError("calque inconnu")


def add_floor(floors: list[Floor], name: str, above: str | None = None) -> Floor:
    new = Floor(new_id(), name, layers=[Layer(new_id(), "Calque 1")])
    idx = next((n + 1 for n, f in enumerate(floors) if f.id == above), len(floors))
    floors.insert(idx, new)
    return new


def add_layer(floors: list[Floor], floor_id: str, name: str) -> Layer:
    layer = Layer(new_id(), name)
    _floor(floors, floor_id).layers.append(layer)
    return layer


def rename(floors: list[Floor], floor_id: str, layer_id: str | None, name: str) -> None:
    name = name.strip()
    if not name:
        raise ValueError("le nom ne peut pas être vide")
    if layer_id is None:
        _floor(floors, floor_id).name = name
    else:
        _layer(floors, floor_id, layer_id)[1].name = name


def set_visible(floors: list[Floor], floor_id: str, layer_id: str | None, value: bool) -> None:
    (_floor(floors, floor_id) if layer_id is None else _layer(floors, floor_id, layer_id)[1]).visible = value


def set_locked(floors: list[Floor], floor_id: str, layer_id: str | None, value: bool) -> None:
    (_floor(floors, floor_id) if layer_id is None else _layer(floors, floor_id, layer_id)[1]).locked = value


def move_floor(floors: list[Floor], floor_id: str, delta: int) -> None:
    i = next((n for n, f in enumerate(floors) if f.id == floor_id), None)
    if i is None:
        raise ValueError("étage inconnu")
    j = i + delta
    if 0 <= j < len(floors):
        floors.insert(j, floors.pop(i))


def move_layer(floors: list[Floor], floor_id: str, layer_id: str, delta: int) -> None:
    f, layer = _layer(floors, floor_id, layer_id)
    i = f.layers.index(layer)
    j = i + delta
    if 0 <= j < len(f.layers):
        f.layers.insert(j, f.layers.pop(i))


def remove_floor(floors: list[Floor], floor_id: str) -> None:
    f = _floor(floors, floor_id)
    if len(floors) == 1:
        raise ValueError("on ne peut pas supprimer le dernier étage")
    floors.remove(f)


def remove_layer(floors: list[Floor], floor_id: str, layer_id: str) -> None:
    f, layer = _layer(floors, floor_id, layer_id)
    if len(f.layers) == 1:
        raise ValueError("un étage doit garder au moins un calque")
    f.layers.remove(layer)
