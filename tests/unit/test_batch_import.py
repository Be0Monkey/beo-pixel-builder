"""Import d'images par lot : formats, doublons, erreurs, annulation."""

from pathlib import Path

from PIL import Image

from sbs.services.batch_import import MAX_SIDE, collect_files, import_images
from sbs.services.library import Library


def make(path: Path, color=(255, 0, 0, 255), size=(8, 6), fmt=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, color).save(path, fmt)
    return path


def test_formats_pivot_et_png_copie_tel_quel(tmp_path):
    lib = Library(tmp_path / "lib")
    files = [make(tmp_path / "in" / "a.png"), make(tmp_path / "in" / "b.bmp", (0, 255, 0, 255), fmt="BMP"),
             make(tmp_path / "in" / "c.webp", (0, 0, 255, 255), fmt="WEBP"), make(tmp_path / "in" / "d.gif", (255, 255, 0, 255), fmt="GIF")]
    r = import_images(lib, files, "meubles")
    assert len(r.imported) == 4 and not r.errors
    a = next(x for x in lib.list_assets() if x.name == "a")
    assert (a.width, a.height, a.pivot_x, a.pivot_y, a.category) == (8, 6, 4, 5, "meubles")
    assert lib.abs_path(a.image_path).read_bytes() == files[0].read_bytes()  # octet pour octet
    b = next(x for x in lib.list_assets() if x.name == "b")
    with Image.open(lib.abs_path(b.image_path)) as im:
        assert im.format == "PNG" and im.mode == "RGBA"


def test_t02_meme_nom_contenus_differents_et_doublons_exacts(tmp_path):
    lib = Library(tmp_path / "lib")
    f1 = make(tmp_path / "x" / "mur.png", (1, 2, 3, 255))
    f2 = make(tmp_path / "y" / "mur.png", (9, 9, 9, 255))
    r = import_images(lib, [f1, f2])
    assert len(set(r.imported)) == 2  # aucun écrasement, UUID distincts
    again = import_images(lib, [f1, f2])
    assert again.imported == [] and again.duplicates == 2  # même contenu : pas de doublon
    assert lib.count() == 2


def test_erreurs_signalees_sans_arreter_le_lot(tmp_path):
    lib = Library(tmp_path / "lib")
    bad = tmp_path / "cassee.png"
    bad.write_bytes(b"\x89PNG\r\n\x1a\nnimportequoi")
    txt = tmp_path / "notes.txt"
    txt.write_text("bonjour")
    big = make(tmp_path / "enorme.png", size=(MAX_SIDE + 1, 1))
    ok = make(tmp_path / "bon.png")
    r = import_images(lib, [bad, txt, big, tmp_path / "absent.png", ok])
    assert len(r.imported) == 1 and len(r.errors) == 4
    joined = " | ".join(r.errors)
    assert "cassee.png" in joined and "format non géré" in joined and "trop grande" in joined


def test_dossiers_recursifs_et_fichiers_ignores(tmp_path):
    make(tmp_path / "kit" / "a.png")
    make(tmp_path / "kit" / "sous" / "b.png")
    (tmp_path / "kit" / "lisez.txt").write_text("x")
    (tmp_path / "kit" / ".cache.png").write_bytes(b"x")
    files, ignored = collect_files([tmp_path / "kit"])
    assert sorted(f.name for f in files) == ["a.png", "b.png"] and ignored == 1
    files, _ = collect_files([tmp_path / "kit"], recursive=False)
    assert [f.name for f in files] == ["a.png"]


def test_annulation_et_progression(tmp_path):
    lib = Library(tmp_path / "lib")
    files = [make(tmp_path / f"{n}.png", (n, 0, 0, 255)) for n in range(5)]
    calls = []
    r = import_images(lib, files, progress=lambda i, n: calls.append((i, n)),
                      cancelled=lambda: len(calls) >= 3)
    assert r.cancelled and len(r.imported) == 3 and lib.count() == 3
    full = import_images(Library(tmp_path / "lib2"), files, progress=lambda i, n: None)
    assert len(full.imported) == 5 and not full.cancelled


def test_noms_accentues_et_chemin_avec_espaces(tmp_path):
    lib = Library(tmp_path / "ma bibliothèque")
    f = make(tmp_path / "dossier é à" / "Étagère rouge.png")
    r = import_images(lib, [f])
    assert len(r.imported) == 1 and lib.list_assets()[0].name == "Étagère rouge"


def test_import_de_1000_fichiers_progression_complete(tmp_path):
    import time
    lib = Library(tmp_path / "lib")
    files = []
    for n in range(1000):
        files.append(make(tmp_path / "in" / f"s{n:04d}.png", (n % 256, (n // 256) % 256, 0, 255), size=(8 + n % 5, 8)))
    ticks = []
    t = time.perf_counter()
    r = import_images(lib, files, progress=lambda i, n: ticks.append(i))
    elapsed = time.perf_counter() - t
    assert len(r.imported) == 1000 and not r.errors and lib.count() == 1000
    assert ticks[0] == 0 and ticks[-1] == 1000 and len(ticks) == 1001  # progression à chaque fichier
    assert elapsed < 60  # large marge ; mesuré ≈ quelques secondes
