"""Validation réelle : la scène exportée est chargée par Godot 4 (sans interface) et comparée à l'appli.
Ignoré si Godot n'est pas trouvé (variable SBS_GODOT ou emplacement habituel)."""

import io
import json
import os
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from sbs.domain import structure as S
from sbs.domain.scene import SceneModel
from sbs.exporters import EXPORTERS, build_export_scene, run_export
from sbs.services.kit_importer import import_kit
from sbs.services.library import Library
from tests.unit.test_kit_importer import card, make_files, make_kit

CANDIDATES = [os.environ.get("SBS_GODOT", ""), r"D:\beostudio\godo\Godot_v4.7.2-stable_win64_console.exe"]
GODOT = next((c for c in CANDIDATES if c and Path(c).is_file()), None)
pytestmark = pytest.mark.skipif(GODOT is None, reason="Godot 4 introuvable (SBS_GODOT)")

VERIFY = '''extends SceneTree
func _init():
\tvar packed = load("res://NAME.tscn")
\tvar root = packed.instantiate()
\tget_root().add_child(root)
\tvar out = []
\t_walk(root, out)
\tprint("SBSJSON:" + JSON.stringify(out))
\tquit()

func _walk(n, out):
\tif n is Sprite2D:
\t\tvar img = n.texture.get_image()
\t\tvar transparent = 0
\t\tfor y in img.get_height():
\t\t\tfor x in img.get_width():
\t\t\t\tif img.get_pixel(x, y).a == 0.0:
\t\t\t\t\ttransparent += 1
\t\tout.append({"name": n.name, "path": str(root_path(n)), "pos": [n.position.x, n.position.y],
\t\t\t"offset": [n.offset.x, n.offset.y], "size": [img.get_width(), img.get_height()],
\t\t\t"transparent": transparent, "visible": veff(n), "centered": n.centered,
\t\t\t"filter": eff(n)})
\tfor c in n.get_children():
\t\t_walk(c, out)

func veff(n):
	while n is CanvasItem:
		if not n.visible:
			return false
		n = n.get_parent()
	return true

func eff(n):
	while n is CanvasItem:
		if n.texture_filter != 0:
			return n.texture_filter
		n = n.get_parent()
	return 0

func root_path(n):
\treturn n.get_parent().get_parent().name + "/" + n.get_parent().name
'''


def _png(size, hole):
    im = Image.new("RGBA", size, (200, 60, 40, 255))
    for x in range(hole):
        for y in range(hole):
            im.putpixel((x, y), (0, 0, 0, 0))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_godot_charge_la_scene_exportee_positions_ordre_transparence(tmp_path):
    cards = [card("mur_a", "murs"), card("toit_b", "toitures")]
    kit = make_kit(tmp_path / "kit", cards)
    for c in cards:
        make_files(kit, c)
    lib = Library(tmp_path / "lib")
    import_kit(lib, kit)
    mur, toit = sorted(lib.list_assets(), key=lambda a: a.source_id)
    lib.replace_image(mur.uuid, _png((16, 20), 5))   # 25 pixels transparents
    lib.replace_image(toit.uuid, _png((16, 20), 3))  # 9 pixels transparents

    m = SceneModel()
    fl = m.floors_copy()
    S.add_floor(fl, "Étage 1")
    S.add_floor(fl, "Toit")
    m.set_floors(fl)
    f0, f1, f2 = m.floors
    m.add(mur.uuid, 10, 50, floor_id=f0.id, layer_id=f0.layers[0].id)
    m.add(mur.uuid, 40, 20, floor_id=f0.id, layer_id=f0.layers[0].id)
    z = m.add(mur.uuid, 25, 90, floor_id=f0.id, layer_id=f0.layers[0].id)
    m.set_z_manual(z.id, -3)
    m.add(mur.uuid, 12, 30, floor_id=f1.id, layer_id=f1.layers[0].id)
    m.add(toit.uuid, 10, 5, floor_id=f2.id, layer_id=f2.layers[0].id)
    fl = m.floors_copy()
    S.set_visible(fl, f2.id, None, False)
    m.set_floors(fl)

    export = build_export_scene(m, lib, "village")
    dest = tmp_path / "projet"
    assert run_export(EXPORTERS["godot4"], export, dest, {"create_project": True}).ok
    (dest / "verify.gd").write_text(VERIFY.replace("NAME", "village"), encoding="utf-8")

    def godot(*args):
        return subprocess.run([GODOT, "--headless", "--path", str(dest), *args], capture_output=True,
                              text=True, timeout=45, encoding="utf-8", errors="replace")
    imp = godot("--import")
    assert imp.returncode == 0, imp.stdout + imp.stderr
    run = godot("--script", "res://verify.gd")
    line = next((x for x in run.stdout.splitlines() if x.startswith("SBSJSON:")), None)
    assert line, run.stdout + run.stderr
    got = json.loads(line[len("SBSJSON:"):])

    expected = [(f.name, layer.name, i) for f in export.floors for layer in f.layers for i in layer.items]
    assert len(got) == len(expected) == 5
    for g, (fname, lname, item) in zip(got, expected):  # même ORDRE de dessin que dans l'appli
        tex = export.textures[item.texture]
        assert g["name"] == item.name and g["pos"] == [item.x, item.y]
        assert g["offset"] == [-tex.pivot[0], -tex.pivot[1]] and g["size"] == [tex.width, tex.height]
        assert g["centered"] is False and g["filter"] == 1
        with Image.open(tex.source) as im:
            transparent = sum(1 for px in im.convert("RGBA").getdata() if px[3] == 0)
        assert g["transparent"] == transparent  # transparence identique au pixel près
        assert g["visible"] is item.visible
    assert [g["path"].split("/")[0] for g in got] == ["RDC", "RDC", "RDC", "Etage_1", "Toit"]
    assert got[0]["pos"] == [25, 90]  # z manuel -3 : le plus au fond
    assert got[-1]["visible"] is False
