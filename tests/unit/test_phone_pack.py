"""Échanges avec la version téléphone : paquet bibliothèque (export) et paquet scène (import)."""

import base64
import io
import json

import pytest
from PIL import Image

from sbs.services import phone_pack as P
from sbs.services.library import Library


def png(size=(8, 10), color=(200, 60, 60, 255)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, "PNG")
    return buf.getvalue()


def scene_doc(modules, instances, name="Maison") -> str:
    return json.dumps({"format": P.SCENE_FORMAT, "version": 1, "name": name, "modules": modules,
                       "instances": instances})


def module(mid="m1", size=(8, 10), pivot=(4, 9), color=(200, 60, 60, 255), category="murs", name="Mur"):
    return {"id": mid, "name": name, "category": category, "w": size[0], "h": size[1], "px": pivot[0],
            "py": pivot[1], "png": base64.b64encode(png(size, color)).decode()}


def test_export_bibliotheque_contient_pivot_categorie_et_image(tmp_path):
    lib = Library(tmp_path / "lib")
    a = lib.create_asset("Mur long", png(), (3, 9), "murs")
    lib.set_tags(a.uuid, ["pierre"])
    out = tmp_path / "pack.json"
    assert P.export_library_pack(lib, out) == 1
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["format"] == P.LIB_FORMAT and doc["version"] == 1
    m = doc["modules"][0]
    assert (m["id"], m["name"], m["category"], m["w"], m["h"], m["px"], m["py"]) == (a.uuid, "Mur long", "murs", 8, 10, 3, 9)
    assert m["tags"] == ["pierre"] and base64.b64decode(m["png"]) == png()
    only = tmp_path / "murs.json"
    lib.create_asset("Toit", png(color=(10, 10, 200, 255)), (4, 9), "toits")
    assert P.export_library_pack(lib, only, categories=["toits"]) == 1


def test_import_scene_cree_les_modules_et_place_les_objets(tmp_path):
    lib = Library(tmp_path / "lib")
    text = scene_doc([module("p_1")], [{"module": "p_1", "x": 10, "y": 20, "z": 2}, {"module": "p_1", "x": -5, "y": 7}])
    pack = P.parse_scene_pack(text)
    res = P.import_scene_pack(lib, pack)
    assert (res.created, res.reused, lib.count()) == (1, 0, 1)
    assert [(i.x, i.y, i.z_manual) for i in res.instances] == [(10, 20, 2), (-5, 7, 0)]
    assert res.meta.name == "Maison"
    a = lib.get(res.instances[0].asset_uuid)
    assert (a.pivot_x, a.pivot_y, a.category, a.origin) == (4, 9, "murs", "local")
    assert {i.floor_id for i in res.instances} == {res.floors[0].id}


def test_import_reutilise_un_module_de_la_bibliotheque_par_son_identifiant(tmp_path):
    lib = Library(tmp_path / "lib")
    a = lib.create_asset("Mur", png(), (4, 9), "murs")
    pack = P.parse_scene_pack(scene_doc([module(a.uuid)], [{"module": a.uuid, "x": 1, "y": 2}]))
    res = P.import_scene_pack(lib, pack)
    assert (res.reused, res.created, lib.count()) == (1, 0, 1) and res.instances[0].asset_uuid == a.uuid


def test_import_deux_fois_ne_duplique_pas_les_dessins_du_telephone(tmp_path):
    lib = Library(tmp_path / "lib")
    text = scene_doc([module("p_1")], [{"module": "p_1", "x": 0, "y": 0}])
    P.import_scene_pack(lib, P.parse_scene_pack(text))
    res = P.import_scene_pack(lib, P.parse_scene_pack(text))
    assert (res.reused, res.created, lib.count()) == (1, 0, 1)


@pytest.mark.parametrize("text,msg", [
    ("pas du json", "illisible"),
    (json.dumps({"format": "autre"}), "pas un paquet scène"),
    (json.dumps({"format": P.SCENE_FORMAT, "version": 99, "modules": [], "instances": []}), "version"),
    (json.dumps({"format": P.SCENE_FORMAT, "version": 1, "modules": {}, "instances": []}), "listes"),
])
def test_paquet_illisible_message_clair(text, msg):
    with pytest.raises(P.PackError, match=msg):
        P.parse_scene_pack(text)


def test_paquet_invalide_est_refuse_sans_toucher_la_bibliotheque(tmp_path):
    bad_png = module("a")
    bad_png["png"] = base64.b64encode(b"pas une image").decode()
    wrong_size = module("b", size=(8, 10))
    wrong_size["w"] = 9
    cases = [
        scene_doc([bad_png], []),
        scene_doc([wrong_size], []),
        scene_doc([module("a", pivot=(99999, 0))], []),
        scene_doc([module("a"), module("a")], []),
        scene_doc([module("a")], [{"module": "inconnu", "x": 0, "y": 0}]),
        scene_doc([module("a")], [{"module": "a", "x": 1.5, "y": 0}]),
        scene_doc([module("a")], [{"module": "a", "x": True, "y": 0}]),
    ]
    lib = Library(tmp_path / "lib")
    for text in cases:
        with pytest.raises(P.PackError):
            P.parse_scene_pack(text)
    assert lib.count() == 0


def test_echec_en_cours_dimport_annule_les_modules_deja_crees(tmp_path):
    lib = Library(tmp_path / "lib")
    pack = P.parse_scene_pack(scene_doc([module("a"), module("b", color=(1, 2, 3, 255))], []))
    real = lib.create_asset
    calls = []

    def flaky(*args, **kw):
        calls.append(1)
        if len(calls) == 2:
            raise ValueError("disque plein")
        return real(*args, **kw)

    lib.create_asset = flaky
    with pytest.raises(P.PackError, match="disque plein"):
        P.import_scene_pack(lib, pack)
    assert lib.count() == 0


def test_pivot_sur_le_bord_bas_hors_image_est_accepte(tmp_path):
    """Cas réel du kit : pivot en y = hauteur (juste sous l'image)."""
    lib = Library(tmp_path / "lib")
    text = scene_doc([module("m1", size=(16, 34), pivot=(0, 34))], [{"module": "m1", "x": 5, "y": 6}])
    pack = P.parse_scene_pack(text)
    assert (pack.modules["m1"].px, pack.modules["m1"].py) == (0, 34)
    res = P.import_scene_pack(lib, pack)
    a = lib.list_assets()[0]
    assert (a.pivot_x, a.pivot_y) == (0, 34) and len(res.instances) == 1
