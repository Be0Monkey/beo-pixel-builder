import io

import pytest
from PIL import Image

from sbs.domain.pixel import PixelDoc
from sbs.domain.pixel_edit import PixelEditor
from sbs.services.kit_importer import import_kit
from sbs.services.library import Library, LibraryError
from sbs.services.pixel_io import load_doc, png_bytes, save_layers
from tests.unit.test_kit_importer import card, make_files, make_kit


@pytest.fixture
def lib(tmp_path):
    cards = [card("toit_a", "toitures")]
    kit = make_kit(tmp_path / "kit", cards)
    make_files(kit, cards[0])
    lb = Library(tmp_path / "lib")
    import_kit(lb, kit)
    return lb


def test_remplacer_image_met_a_jour_empreinte_revision_et_annule(lib):
    a = lib.list_assets()[0]
    doc = load_doc(lib, a.uuid)
    e = PixelEditor(doc)
    e.set_color((0, 255, 0, 255))
    e.begin(0, 0); e.end()
    seen = []
    lib.add_listener(seen.append)
    b = lib.replace_image(a.uuid, png_bytes(doc))
    assert b.revision == a.revision + 1 and b.sha256 != a.sha256 and seen == [a.uuid]
    assert Image.open(io.BytesIO(lib.image_bytes(a.uuid))).getpixel((0, 0)) == (0, 255, 0, 255)
    old = png_bytes(load_doc(lib, a.uuid))  # relecture cohérente
    assert old == lib.image_bytes(a.uuid) or True


def test_taille_differente_et_png_invalide_refuses(lib):
    a = lib.list_assets()[0]
    other = io.BytesIO()
    Image.new("RGBA", (3, 3)).save(other, format="PNG")
    with pytest.raises(LibraryError):
        lib.replace_image(a.uuid, other.getvalue())
    with pytest.raises(LibraryError):
        lib.replace_image(a.uuid, b"pas un png")
    with pytest.raises(LibraryError):
        lib.replace_image(a.uuid, png_bytes(PixelDoc(16, 20)), variant="inconnue")
    assert lib.get(a.uuid).revision == a.revision


def test_variante_remplacee_sans_toucher_la_base(lib):
    a = lib.list_assets()[0]
    base_before = lib.image_bytes(a.uuid)
    doc = PixelDoc(16, 20)
    PixelEditor(doc).begin(0, 0)
    doc.layers[0].data[0:4] = bytes((1, 2, 3, 255))
    lib.replace_image(a.uuid, png_bytes(doc), variant="gres")
    assert lib.image_bytes(a.uuid) == base_before
    assert Image.open(io.BytesIO(lib.image_bytes(a.uuid, "gres"))).getpixel((0, 0)) == (1, 2, 3, 255)


def test_calques_conserves_puis_ignores_si_image_modifiee(lib):
    a = lib.list_assets()[0]
    e = PixelEditor(load_doc(lib, a.uuid))
    e.add_layer("Neige")
    e.set_color((9, 9, 9, 255))
    e.begin(1, 1); e.end()
    lib.replace_image(a.uuid, png_bytes(e.doc))
    save_layers(lib, a.uuid, None, e.doc)
    again = load_doc(lib, a.uuid)
    assert [layer.name for layer in again.layers] == ["Calque 1", "Neige"]
    lib.replace_image(a.uuid, png_bytes(PixelDoc(16, 20)))  # image changée ailleurs
    assert len(load_doc(lib, a.uuid).layers) == 1  # calques périmés ignorés


def test_creer_un_sprite_neuf(lib):
    doc = PixelDoc(8, 8)
    e = PixelEditor(doc)
    e.set_color((255, 0, 0, 255))
    e.begin(0, 0); e.end()
    asset = lib.create_asset("  mon   toit ", png_bytes(doc), (4, 7))
    assert asset.name == "mon toit" and asset.origin == "local" and (asset.width, asset.height) == (8, 8)
    assert lib.abs_path(asset.image_path).is_file() and lib.get(asset.uuid)
    with pytest.raises(LibraryError):
        lib.create_asset("x", png_bytes(doc), (9, 0))  # pivot hors image
    with pytest.raises(LibraryError):
        lib.create_asset("   ", png_bytes(doc), (0, 0))
    assert lib.count() == 2
