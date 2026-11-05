import json

import pytest
from PIL import Image

from sbs.domain import structure as S
from sbs.domain.scene import Group, SceneModel
from sbs.exporters import EXPORTERS, build_export_scene, run_export
from sbs.exporters.base import MARKER
from sbs.exporters.godot import build_tscn
from sbs.exporters.model import safe_name
from sbs.services.kit_importer import import_kit
from sbs.services.library import Library
from tests.unit.test_kit_importer import card, make_files, make_kit


@pytest.fixture
def lib(tmp_path):
    cards = [card("mur a", "murs"), card("toit_b", "toitures")]
    kit = make_kit(tmp_path / "kit", cards)
    for c in cards:
        make_files(kit, c)
    lb = Library(tmp_path / "lib")
    import_kit(lb, kit)
    return lb


def _scene(lib):
    mur, toit = sorted(lib.list_assets(), key=lambda a: a.source_id)
    m = SceneModel()
    fl = m.floors_copy()
    S.add_floor(fl, "Toit")
    m.set_floors(fl)
    rdc, top = m.floors[0], m.floors[1]
    a = m.add(mur.uuid, 10, 50, floor_id=rdc.id, layer_id=rdc.layers[0].id)
    b = m.add(mur.uuid, 30, 20, floor_id=rdc.id, layer_id=rdc.layers[0].id)  # plus loin (y plus petit)
    c = m.add(toit.uuid, 10, 5, floor_id=top.id, layer_id=top.layers[0].id)
    m.set_z_manual(a.id, -1)
    fl = m.floors_copy()
    S.set_visible(fl, top.id, None, False)
    m.set_floors(fl)
    m.set_grouping({"g": Group("g", "Groupe", None)}, {a.id: "g", b.id: "g"})
    return m, (a, b, c)


def test_scene_d_export_suit_l_ordre_de_dessin(lib):
    m, (a, b, c) = _scene(lib)
    ex = build_export_scene(m, lib, "Mon village!")
    assert ex.name == "Mon_village"
    ordered = [i.id for f in ex.floors for layer in f.layers for i in layer.items]
    assert ordered == m.draw_order() and [i.draw_index for f in ex.floors for l in f.layers for i in l.items] == [0, 1, 2]
    assert ordered[0] == a.id  # z manuel -1 : tout au fond malgré un y plus grand
    roof = ex.floors[1].layers[0].items[0]
    assert roof.visible is False and ex.floors[0].layers[0].items[0].visible is True
    names = [i.name for i in ex.floors[0].layers[0].items]
    assert len(set(names)) == 2 and all(" " not in n for n in names)


def test_references_manquantes_sont_signalees_pas_fatales(lib):
    m, _ = _scene(lib)
    m.add("fantome", 0, 0)
    ex = build_export_scene(m, lib)
    assert ex.item_count() == 3 and any("absent" in w for w in ex.warnings)


def test_json_positions_pivots_et_images_identiques(tmp_path, lib):
    m, (a, b, c) = _scene(lib)
    rep = run_export(EXPORTERS["json"], build_export_scene(m, lib, "v"), tmp_path / "out")
    assert rep.ok and "v.json" in rep.files
    doc = json.loads((tmp_path / "out" / "v.json").read_text(encoding="utf-8"))
    assert doc["format"] == "sbs-scene-export" and len(doc["floors"]) == 2
    first = doc["floors"][0]["layers"][0]["items"][0]
    assert first["position"] == [10, 50] and first["top_left"] == [7, 33]  # pivot (3,17) du kit de test
    assert first["z_manual"] == -1 and first["group"] == "g" and first["draw_index"] == 0
    assert doc["floors"][1]["visible"] is False
    src = lib.list_assets()[0]
    t = doc["textures"][0]
    assert (tmp_path / "out" / t["file"]).read_bytes() is not None
    assert (tmp_path / "out" / "textures" / "mur_a.png").read_bytes() == lib.abs_path(
        next(x for x in lib.list_assets() if x.source_id == "mur a").image_path).read_bytes()
    assert src is not None


def test_godot_tscn_ordre_noeuds_positions_offsets_et_filtre(lib):
    m, (a, b, c) = _scene(lib)
    text = build_tscn(build_export_scene(m, lib, "village"))
    assert text.startswith("[gd_scene load_steps=3 format=3]")
    assert "texture_filter = 1" in text and 'path="res://sprites/mur_a.png"' in text
    nodes = [line for line in text.splitlines() if line.startswith("[node")]
    assert nodes[0].startswith('[node name="village" type="Node2D"]')
    sprites = [n for n in nodes if "Sprite2D" in n]
    assert len(sprites) == 3
    assert text.index('"RDC/Calque_1"') < text.index('"Toit/Calque_1"')  # les étages restent dans l'ordre
    assert "position = Vector2(10, 50)" in text and "offset = Vector2(-3, -17)" in text
    assert "centered = false" in text and "visible = false" in text  # le toit est masqué
    assert 'metadata/sbs_group = "g"' in text and "metadata/sbs_z = -1" in text
    # premier sprite du RDC = celui dont le z manuel est le plus bas
    first = text[text.index('type="Sprite2D"'):]
    assert "Vector2(10, 50)" in first.split("[node")[0]
    assert build_tscn(build_export_scene(m, lib, "village"), "jeu/decor").count('res://jeu/decor/sprites/') == 2


def test_godot_projet_de_test_et_prefixe_invalide(tmp_path, lib):
    m, _ = _scene(lib)
    ex = build_export_scene(m, lib, "village")
    rep = run_export(EXPORTERS["godot4"], ex, tmp_path / "g", {"create_project": True})
    assert rep.ok and {"village.tscn", "project.godot", "sprites/mur_a.png"} <= set(rep.files)
    assert 'run/main_scene="res://village.tscn"' in (tmp_path / "g" / "project.godot").read_text(encoding="utf-8")
    bad = run_export(EXPORTERS["godot4"], ex, tmp_path / "g2", {"res_prefix": "../dehors"})
    assert not bad.ok and not (tmp_path / "g2").exists()


def test_securite_destination(tmp_path, lib):
    m, _ = _scene(lib)
    ex = build_export_scene(m, lib, "village")
    dest = tmp_path / "jeu"
    dest.mkdir()
    (dest / "village.tscn").write_text("MA SCENE DE JEU", encoding="utf-8")  # fichier qui n'est pas le nôtre
    rep = run_export(EXPORTERS["godot4"], ex, dest)
    assert not rep.ok and "existe déjà" in rep.error
    assert (dest / "village.tscn").read_text(encoding="utf-8") == "MA SCENE DE JEU"
    assert not (dest / "sprites").exists()  # rien n'a été écrit du tout
    # dossier non vide mais sans conflit : on ajoute sans rien écraser
    (dest / "village.tscn").unlink()
    (dest / "autre.txt").write_text("x", encoding="utf-8")
    assert run_export(EXPORTERS["godot4"], ex, dest).ok and (dest / "autre.txt").read_text(encoding="utf-8") == "x"
    # ré-export : seuls NOS fichiers sont remplacés
    assert run_export(EXPORTERS["godot4"], ex, dest).ok
    (dest / "sprites" / "intrus.png").write_bytes(b"1")
    assert (dest / MARKER).is_file() and (dest / "sprites" / "intrus.png").exists()


def test_scene_vide_et_erreurs_disque_sans_exception(tmp_path, lib):
    empty = build_export_scene(SceneModel(), lib)
    assert not run_export(EXPORTERS["json"], empty, tmp_path / "e").ok
    m, _ = _scene(lib)
    blocker = tmp_path / "fichier"
    blocker.write_text("x", encoding="utf-8")
    rep = run_export(EXPORTERS["json"], build_export_scene(m, lib), blocker / "sous")  # impossible
    assert not rep.ok and rep.error


def test_noms_surs():
    assert safe_name("../../etc/passwd") == "etc_passwd" and safe_name("   ") == "noeud"
    assert safe_name("Étage 1") == "Etage_1"
