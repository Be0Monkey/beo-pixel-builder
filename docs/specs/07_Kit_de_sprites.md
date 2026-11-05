# 07 — Kit de sprites fourni (généré avec Blender)

> **Statut** : description **observée** dans le dossier `k_1793801705` (inventaire du 5 novembre 2026). Ce qui est déduit sans être écrit dans les fichiers est marqué *(hypothèse)*.

## 1. Origine et échelle
- Sprites rendus depuis **Blender**, en pixel art 3/4.
- Échelle commune écrite dans chaque fiche : **16 pixels par mètre**, **case de grille 32 px**, **élévation de caméra 30°**.
- « 1 m de hauteur = 13,86 px » = 16 × cos 30°. Une hauteur est donc raccourcie, une largeur non.

## 2. Contenu

| Dossier | Contenu | Quantité |
|---|---|---|
| `modules_px/<catégorie>/` | PNG des sprites, de leurs variantes, de leurs normales (`_n`) et émissions (`_e`) | 768 |
| `metadata/modules_px/` | une fiche JSON par module + `_index.json` (toutes les fiches réunies) | 163 fiches |
| `recipes/` | assemblages (maisons, ferme, forge...) en JSON | 18 |
| `assemblages/` | sprite, aperçu, normales, émission de chaque assemblage | 69 fichiers |
| `apercus/` | catalogue, village, scène avec lumière | 7 PNG |

Catégories (15) : batiments, clotures, commerce, decorations, details, etages, mobilier, murs, ouvertures, ponts, sacre, sols, toitures, tours, vegetation.

## 3. Convention de noms
- `angle_rdc_droit.png` : sprite de base.
- `angle_rdc_droit_n.png` : carte de normales. `angle_rdc_droit_e.png` : carte d'émission (lumière propre, fenêtres allumées...).
- `angle_rdc_droit__gres.png` : **variante** (double soulignement + nom). Variantes vues : blanc, bois_clair, gres, gris, ocre, rouge, tuile, vert (267 au total).

## 4. Fiche d'un module (exemple réel)
```json
{
 "id": "angle_rdc_droit",
 "categorie": "murs",
 "description": "Angle droit de RDC (chaîne d'angle), 1 m",
 "taille_px": [16, 44],
 "ancrage_px": [0, 41],
 "echelle": {"pixels_par_metre": 16, "case_grille_px": 32},
 "fichiers": {"sprite": "murs/angle_rdc_droit.png",
              "normales": "murs/angle_rdc_droit_n.png",
              "emission": "murs/angle_rdc_droit_e.png"},
 "variantes": {"gres": "murs/angle_rdc_droit__gres.png"},
 "couleurs": 10, "L_m": 1, "Lpx": 16, "Hpx": 41,
 "tile": {"l": 1, "r": 1, "t": 1},
 "mode": "wall", "depth": 5.0, "pente": 48
}
```

| Champ | Sens | Utilisation dans l'appli |
|---|---|---|
| `id` | identifiant du module dans le kit | `source_id` de l'Asset (l'UUID reste la vraie clé) |
| `taille_px` | largeur, hauteur du PNG | dimensions |
| `ancrage_px` | point d'accroche au sol, en pixels depuis le coin haut-gauche | **pivot** par défaut, et point de profondeur |
| `fichiers` | chemins relatifs | copie à l'import |
| `variantes` | nom → image | variantes de l'asset |
| `mode` | type de module : deco (80), wall (20), ground (18), slate (17), tower (9), opening (6), rampart (5), ivy, cone, chimney | catégorie technique *(hypothèse : type de construction Blender)* |
| `tile` | côtés (l, r, t, b) qui se raccordent *(hypothèse)* | base pour les futures règles de raccord |
| `depth`, `pente` | paramètres de génération Blender (5.0 et 48 presque partout) | à conserver, **ne pas interpréter** pour l'instant |
| `L_m`, `Lpx`, `Hpx`, `center`, `axis_m`, `axe_px`, `stack_px` | champs optionnels selon le module | à conserver tels quels |

**Règle de robustesse :** les champs optionnels peuvent manquer (3 fiches n'ont ni `depth` ni `pente`). L'import ne doit jamais échouer pour cela, et doit garder les champs inconnus.

## 5. Recette (assemblage)
```json
{"id": "boulangerie", "variantes": ["tuile", "ocre"],
 "elements": [{"m": "angle_rdc_gauche", "x": 0, "y": 0},
              {"m": "mur_rdc_porte_2m", "x": 16, "y": 0}, ...]}
```
- `m` = `id` d'un module ; `x`, `y` = position en pixels. Les `y` négatifs existent (objets posés devant).
- L'**ordre de la liste** est probablement l'ordre de dessin du kit *(hypothèse à vérifier en comparant avec `assemblages/boulangerie_sprite.png`)*.
- `variantes` : la recette existe en plusieurs finitions (ex. toit tuile, murs ocre).
- Une recette devient un **module composite** dans l'appli (décision D-E).

## 6. Points à vérifier au tout début de J1a
1. L'origine de `x, y` dans les recettes : coin haut-gauche du sprite, ou son ancrage ?
2. L'ordre de dessin des recettes : liste, ou tri par `y` ?
3. Le sens exact de `tile` et `mode`.
4. Comparer chaque recette importée avec son `*_sprite.png` : c'est le test T15.

Ne jamais modifier les fichiers du kit : l'import fait une **copie gérée**.
