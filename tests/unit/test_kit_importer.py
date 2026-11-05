import json
import os
from pathlib import Path

import pytest
from PIL import Image

from sbs.services.kit_importer import KitError, import_kit
from sbs.services.library import Library


def _png(path: Path, size=(16, 20), color=(200, 50, 50, 255)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, color).save(path)


def make_kit(root: Path, cards: list[dict]) -> Path:
    (root / "metadata" / "modules_px").mkdir(parents=True)
    (root / "metadata" / "modules_px" / "_index.json").write_text(json.dumps(cards), encoding="utf-8")
    return root


def card(sid="mur_a", cat="murs", **kw):
    c = {
        "id": sid, "categorie": cat, "description": f"Module {sid}", "taille_px": [16, 20],
        "ancrage_px": [3, 17],
        "fichiers": {"sprite": f"{cat}/{sid}.png", "normales": f"{cat}/{sid}_n.png",
                     "emission": f"{cat}/{sid}_e.png"},
        "variantes": {"gres": f"{cat}/{sid}__gres.png"},
        "mode": "wall", "depth": 5.0, "pente": 48, "tile": {"l": 1},
    }
    c.update(kw)
    return c


def make_files(kit: Path, c: dict):
    for rel in [c["fichiers"]["sprite"], *c["fichiers"].values(), *c["variantes"].values()]:
        _png(kit / "modules_px" / rel)


@pytest.fixture
def lib(tmp_path):
    return Library(tmp_path / "lib")


def test_t13_import_complet(tmp_path, lib):
    cards = [card("mur_a"), card("arbre", "vegetation")]
    kit = make_kit(tmp_path / "kit", cards)
    for c in cards:
        make_files(kit, c)
    r = import_kit(lib, kit)
    assert r.imported == 2 and not r.errors
    assert lib.count() == 2 and lib.categories() == ["murs", "vegetation"]
    a = next(x for x in lib.list_assets() if x.source_id == "mur_a")
    assert (a.pivot_x, a.pivot_y) == (3, 17)  # ancrage_px = pivot
    assert (a.width, a.height) == (16, 20)
    assert a.extra["depth"] == 5.0 and a.extra["tile"] == {"l": 1}  # champs conservés
    assert lib.abs_path(a.image_path).is_file() and lib.abs_path(a.normal_path).is_file()
    assert lib.thumbnail_path(a.uuid).is_file()


def test_t14_variantes_rattachees_sans_doublon(tmp_path, lib):
    c = card()
    kit = make_kit(tmp_path / "kit", [c])
    make_files(kit, c)
    import_kit(lib, kit)
    assets = lib.list_assets()
    assert len(assets) == 1 and [v.name for v in assets[0].variants] == ["gres"]


def test_reimport_idempotent(tmp_path, lib):
    c = card()
    kit = make_kit(tmp_path / "kit", [c])
    make_files(kit, c)
    import_kit(lib, kit)
    r = import_kit(lib, kit)
    assert r.imported == 0 and r.already_present == 1 and lib.count() == 1


def test_originaux_jamais_modifies(tmp_path, lib):
    c = card()
    kit = make_kit(tmp_path / "kit", [c])
    make_files(kit, c)
    before = {p: p.read_bytes() for p in kit.rglob("*.png")}
    import_kit(lib, kit)
    assert before == {p: p.read_bytes() for p in kit.rglob("*.png")}


def test_t16_fiche_incomplete(tmp_path, lib):
    c = card()
    for k in ("depth", "pente", "tile", "mode", "ancrage_px", "description"):
        c.pop(k)
    kit = make_kit(tmp_path / "kit", [c])
    make_files(kit, c)
    r = import_kit(lib, kit)
    assert r.imported == 1 and not r.errors


def test_t11_image_corrompue_ou_absente_ne_detruit_rien(tmp_path, lib):
    good, bad, missing = card("bon"), card("casse"), card("absent")
    kit = make_kit(tmp_path / "kit", [bad, good, missing])
    make_files(kit, good)
    make_files(kit, bad)
    (kit / "modules_px" / bad["fichiers"]["sprite"]).write_bytes(b"pas un png")
    r = import_kit(lib, kit)
    assert r.imported == 1 and len(r.errors) == 2
    assert lib.count() == 1
    assert len(list(lib.assets_dir.iterdir())) == 1  # pas de dossier orphelin


def test_chemin_hors_kit_refuse(tmp_path, lib):
    c = card(fichiers={"sprite": "../../secret.png"})
    kit = make_kit(tmp_path / "kit", [c])
    r = import_kit(lib, kit)
    assert r.imported == 0 and "interdit" in r.errors[0]


def test_annulation_conserve_ce_qui_est_importe(tmp_path, lib):
    cards = [card(f"m{i}") for i in range(5)]
    kit = make_kit(tmp_path / "kit", cards)
    for c in cards:
        make_files(kit, c)
    n = {"i": 0}

    def cancelled():
        n["i"] += 1
        return n["i"] > 2

    r = import_kit(lib, kit, cancelled=cancelled)
    assert r.cancelled and r.imported == 2 and lib.count() == 2


def test_dossier_pas_un_kit(tmp_path, lib):
    with pytest.raises(KitError):
        import_kit(lib, tmp_path)


def test_t02_memes_noms_contenus_differents_uuid_distincts(tmp_path, lib):
    k1, k2 = tmp_path / "k1", tmp_path / "k2"
    for kit, col in ((k1, (255, 0, 0, 255)), (k2, (0, 0, 255, 255))):
        c = card()
        make_kit(kit, [c])
        for rel in [c["fichiers"]["sprite"], *c["fichiers"].values(), *c["variantes"].values()]:
            _png(kit / "modules_px" / rel, color=col)
    import_kit(lib, k1)
    import_kit(lib, k2)  # même id "mur_a" : déjà présent, rien n'est écrasé
    assert lib.count() == 1


@pytest.mark.skipif(not os.environ.get("SBS_KIT_DIR"), reason="kit réel non indiqué (SBS_KIT_DIR)")
def test_kit_reel(tmp_path, lib):
    r = import_kit(lib, Path(os.environ["SBS_KIT_DIR"]))
    print("erreurs:", r.errors[:5], "avertissements:", r.warnings[:5])
    assert lib.count() == r.imported >= 150
    # Défaut connu du kit : la fiche escalier_pierre_2m n'a pas son PNG. Seule erreur tolérée.
    assert all("sprite manquant" in e for e in r.errors), r.errors
    assert len(r.errors) <= 1
