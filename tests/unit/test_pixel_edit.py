import pytest

from sbs.domain.pixel import PixelDoc
from sbs.domain.pixel_edit import PixelEditor, check_color, line_points

RED, BLUE = (255, 0, 0, 255), (0, 0, 255, 255)


def ed(w=8, h=8):
    e = PixelEditor(PixelDoc(w, h))
    e.set_color(RED)
    return e


def px(e, x, y, layer=None):
    return e.doc.get(layer or e.doc.active, x, y)


def test_doc_valide_taille():
    for bad in ((0, 4), (4, 0), (513, 4), (4.5, 4)):
        with pytest.raises(ValueError):
            PixelDoc(*bad)


def test_crayon_un_geste_une_commande_et_trait_sans_trou():
    e = ed()
    e.begin(0, 0); e.move(5, 3); e.end()
    pts = list(line_points(0, 0, 5, 3))
    assert all(px(e, x, y) == RED for x, y in pts) and len(pts) == 6
    assert len(e._stack) == 1
    e.undo()
    assert all(px(e, x, y) == (0, 0, 0, 0) for x, y in pts) and not e.modified
    e.redo()
    assert px(e, 5, 3) == RED and e.modified


def test_gomme_et_hors_image():
    e = ed()
    e.begin(1, 1); e.end()
    e.tool = "eraser"
    e.begin(1, 1); e.move(20, 20); e.end()  # sortir de l'image ne plante pas
    assert px(e, 1, 1) == (0, 0, 0, 0)


def test_pipette_prend_la_couleur_visible_et_refuse_le_transparent():
    e = ed()
    e.begin(2, 2); e.end()
    e.tool = "picker"
    e.set_color(BLUE)
    assert e.begin(2, 2) and e.color == RED
    assert not e.begin(5, 5) and e.error


def test_remplissage_zone_fermee_et_selection():
    e = ed()
    for x in range(8):  # mur vertical à x=3
        e.begin(3, x); e.end()
    e.tool = "fill"
    e.set_color(BLUE)
    assert e.begin(0, 0)
    assert px(e, 2, 7) == BLUE and px(e, 3, 0) == RED and px(e, 4, 0) == (0, 0, 0, 0)
    e.undo()
    assert px(e, 0, 0) == (0, 0, 0, 0)
    e.set_selection(4, 0, 5, 1)
    e.begin(4, 0)
    assert px(e, 4, 0) == BLUE and px(e, 6, 0) == (0, 0, 0, 0) and px(e, 4, 2) == (0, 0, 0, 0)
    assert not e.begin(0, 5)  # hors sélection : rien


def test_selection_effacer_et_deplacer():
    e = ed()
    e.begin(1, 1); e.end()
    e.set_selection(1, 1, 2, 2)
    assert e.move_selection(3, 0) and px(e, 1, 1) == (0, 0, 0, 0) and px(e, 4, 1) == RED
    assert e.selection == (4, 1, 5, 2)
    assert e.delete_selection() and px(e, 4, 1) == (0, 0, 0, 0)
    e.undo(); e.undo()
    assert px(e, 1, 1) == RED
    e.clear_selection()
    assert not e.delete_selection()


def test_calques_visibilite_verrou_ordre_et_annulation():
    e = ed()
    base = e.doc.active
    e.begin(0, 0); e.end()
    assert e.add_layer()
    top = e.doc.active
    e.set_color(BLUE)
    e.begin(0, 0); e.end()
    assert e.doc.flatten_get(0, 0) == BLUE
    assert e.set_layer_visible(top.id, False) and e.doc.flatten_get(0, 0) == RED
    assert not e.begin(1, 1) and "masqué" in e.error  # calque actif masqué : refus
    e.set_layer_visible(top.id, True)
    e.set_layer_locked(top.id, True)
    assert not e.begin(1, 1) and "verrouillé" in e.error
    e.set_active(base.id)
    assert e.move_layer(+1) and e.doc.layers[-1].id == base.id
    assert e.doc.flatten_get(0, 0) == RED  # le calque de base est maintenant dessus
    for _ in range(7):  # trait, calque, trait, masquer, afficher, verrou, déplacement
        e.undo()
    assert len(e.doc.layers) == 1 and px(e, 0, 0) == (0, 0, 0, 0)


def test_au_moins_un_calque_et_limite():
    e = ed()
    assert not e.remove_layer() and e.error
    for _ in range(40):
        e.add_layer()
    assert len(e.doc.layers) == 32 and e.error


def test_palette_couleur_validation():
    e = ed()
    for bad in ((1, 2, 3), (256, 0, 0, 0), (1.5, 0, 0, 0), "rouge"):
        with pytest.raises(ValueError):
            check_color(bad)
    assert e.add_to_palette((1, 2, 3, 255)) and not e.add_to_palette((1, 2, 3, 255))


def test_etat_enregistre_et_branche_perdue():
    e = ed()
    e.begin(0, 0); e.end()
    e.mark_saved()
    assert not e.modified
    e.undo()
    assert e.modified
    e.begin(1, 1); e.end()  # nouvelle branche : l'état enregistré n'est plus atteignable
    assert e.modified


def test_remplacer_couleur_un_seul_ctrl_z():
    e = ed()
    e.begin(0, 0); e.move(3, 0); e.end()            # 4 pixels rouges
    e.set_color(BLUE)
    n = len(e._stack)
    assert e.replace_color(RED, BLUE) == 4
    assert all(px(e, x, 0) == BLUE for x in range(4)) and len(e._stack) == n + 1
    assert e.undo() and all(px(e, x, 0) == RED for x in range(4))


def test_outil_remplacer_clique_sur_un_pixel():
    e = ed()
    e.begin(1, 1); e.end(); e.begin(2, 2); e.end()
    e.set_color(BLUE); e.tool = "replace"
    assert e.begin(1, 1) and e.end() is False
    assert px(e, 1, 1) == BLUE and px(e, 2, 2) == BLUE


def test_remplacer_refus_clairs():
    e = ed()
    e.tool = "replace"
    assert e.begin(0, 0) is False and "transparent" in e.error   # pixel vide
    e.tool = "pencil"; e.begin(0, 0); e.end()
    assert e.replace_color(RED, RED) == 0 and "déjà" in e.error
    assert e.replace_color(BLUE, RED) == 0 and "aucun pixel" in e.error
    e.doc.active.locked = True
    assert e.replace_color(RED, BLUE) == 0 and "verrouillé" in e.error
