# 02 — Architecture technique proposée

> **Statut** : Python / PySide6 / local / Windows 11 sont retenus. Les détails ci-dessous sont des **propositions d’implémentation** pour Claude, non des décisions Q17–Q51 retrouvées.

## 1. Structure de code
Architecture modulaire, séparant **modèle**, **commandes**, **services**, **UI**, **rendu**, **import/export**. Éviter toute logique métier dans les widgets PySide6.

```text
sprite_builder_studio/
  pyproject.toml
  src/sbs/
    app.py
    domain/          # Projet, scène, modules, instances, calques, étages, animations
    commands/        # Commandes réversibles, historique undo/redo
    services/        # Bibliothèque, sauvegarde, versionnage, empreintes
    canvas/          # QGraphicsView/Scene et composants de manipulation
    pixel_editor/    # Raster pixel, palettes, outils, calques, timeline
    ui/              # MainWindow, docks, inspector, outils, dialogues
    formats/         # Import images, exports PNG/JSON/Godot
    previews/        # Fond, éclairage illustratif, rendu hors export
  tests/
    unit/
    integration/
    gui/
  docs/
  assets/
```

## 2. Pile recommandée
- **Python 3.12+** (version à figer après essais de compatibilité) ; **PySide6** pour widgets, événements, docking.
- **QGraphicsScene / QGraphicsView** pour le canvas de construction ; custom items pour instances, guides, poignées, ancrages. Alternatives OpenGL seulement après profilage.
- **QImage** pour bitmap pixel art et opérations ciblées ; **Pillow** pour import/export/atlas si utile. Éviter les conversions sRGB non contrôlées et les filtres bilinéaires.
- **SQLite** pour index permanent des ressources ; fichiers binaires des images sur disque, jamais tout en blob SQLite par défaut.
- **JSON** pour documents projet versionnés ; **zip** optionnel pour projet portable.
- **pytest**, `pytest-qt` pour tests, outils de lint et typage.
- Packaging Windows via **PyInstaller** ou **Nuitka**, à valider sur machine propre.

## 3. Modèle de données
```text
Project
  id, schema_version, name, created_at, updated_at
  scenes[] ; library_refs[] ; settings ; export_presets
Scene
  id, name, canvas_settings, floors[], loose_layers[], groups[], instances[]
Floor
  id, name, elevation_px, visible, locked, layers[]
Layer
  id, name, order, visible, locked, blend_mode
Asset
  uuid, source_id (ex. "angle_rdc_droit" du kit), name, category,
  relative_image_path, normal_path?, emission_path?, pixel_size,
  tags, pivot (= ancrage_px du kit), anchors[],
  variants[] (nom -> image, ex. "gres", "ocre"),
  scale {px_per_m, grid_cell_px, elevation_deg},
  mode (wall/deco/ground/slate/tower/...), depth?, tile{l,r,t,b}?,
  revision, checksum
Anchor
  id, name, local_x, local_y, connection_type
Instance
  id, asset_uuid, asset_revision?, variant_id?, x, y, scale_x,
  scale_y (entiers), flip_x, flip_y, floor_id, layer_id,
  z_override?, pivot_override?, detached_asset_uuid?
Group  (imbriquable, 3 niveaux max)
  id, child_ids[] (instances OU groupes), transform, metadata
Recipe / CompositeModule  (groupe enregistré en module)
  id, variants[], elements[{asset_ref, x, y}]   # format identique à recipes/*.json du kit
Animation
  id, frames[], fps, layer_refs
```
**Important :** ne pas utiliser les noms de fichiers comme clés primaires ; gérer les cycles de groupes (interdits) et les références cassées explicitement.

## 4. Règles de coordonnées / profondeur
- Définir un espace de **pixels logiques** fixe, indépendant des pixels physiques de l’écran (DPI).
- Le canevas stocke ses positions en unités de scène ; l’export raster se fait à résolution native ou facteur entier pour conserver le pixel art.
- Le pivot de profondeur = point de contact au sol du module (par défaut l'`ancrage_px` du kit), personnalisable. **Ordre de tri unique (D-C)** : étage > calque > Z manuel (0 par défaut) > profondeur auto (Y du pivot) > ordre d'insertion. Aucune autre règle. (Le Z manuel passe avant la profondeur auto : sinon il ne pourrait pas « forcer » un ordre.)
- **Valeurs de référence** : 16 px/m, case 32 px, élévation 30°. Lues dans les fiches du kit ; stockées par projet.
- Définir un ordre déterministe même en cas de valeurs identiques (ID/insertion), afin d’éviter des sprites qui « sautent » d’un rendu à l’autre.

## 5. Architecture des commandes
Chaque opération modifiant le document est une commande : `execute()` et `undo()` ; ex. PlaceInstance, Move, Resize, Group, ReparentLayer, PaintPixels, AddFloor, ChangeVariant, DetachInstance. Grouper les gestes de souris continus en **une seule** entrée dans l’historique.

## 5 bis. Import du kit (fiches JSON)
Le service Bibliothèque sait lire `metadata/modules_px/*.json` (voir `07`) : une fiche = un `Asset`. Les variantes (`__gres`, `__ocre`...) deviennent des `variants[]` du même asset, pas des assets séparés. Les recettes (`recipes/*.json`) sont importées comme modules composites. Les PNG sont **copiés** dans le dossier géré, avec SHA-256, comme tout import.

## 6. Bibliothèque & dépendances
- Lors d’un import, copier l’image vers un dossier géré par l’application, calculer SHA-256 et conserver chemin d’origine facultatif à titre informatif.
- Gestion des liens : **source commune** = modifications globales ; **détacher instance** = clone de ressource + mise à jour d’une seule instance.
- Effectuer les changements importants via transaction, sauvegarder les originaux, afficher les références affectées ; proposer de réparer un fichier manquant au chargement.
- Vignettes mises en cache avec invalidation sur modification de révision.

## 7. Sauvegarde sûre
- Sérialiser dans un fichier temporaire puis renommer de façon atomique ; conserver des backups horodatés avec rétention configurable.
- Autosave différé (sur changement), ne jamais écraser l’unique fichier de secours ; après crash proposer restauration, comparaison ou poursuite de la version précédente.
- Validation de schéma, migrations explicites et refus des versions incompatibles avec message clair. Zéro exécution de code arbitraire au chargement d’un projet.

## 8. Export
- Exports raster PNG RGBA : rectangle d’export explicite, exclusion des grilles/guides, ordre de couches déterministe, transparence conservée.
- Export des couches : noms stables et dimensions/offsets annoncés.
- Export JSON : coordonnées, pivots, ordre Z, étages, liens des sprites, animations si disponibles.
- Export Godot 4 : écrire des `z_index` fixes calculés par l'outil (décision D-F, plus prévisible que le `y_sort` de Godot), générer les ressources annexes et scène `.tscn` avec positions/pivots cohérents, **sans toucher au dossier du jeu** sauf action explicite ; tester sur un petit projet Godot isolé.
- Le format natif du projet **ne doit pas dépendre du format d’export**.

## 9. Performance & robustesse
- Lazy loading pour les miniatures, cache LRU pour pixmaps, rendu des items visibles seulement.
- Opérations longues (import de lots, calcul d’atlas, enregistrement de versions) en workers sans toucher à l’UI Qt depuis les threads.
- Limiter les copies géantes de bitmaps dans l’historique ; mémoire configurable et sauvegarde de checkpoints.
- Tester 1 000, 5 000 et 20 000 instances avec profilage avant toute promesse de performance.

## 10. Politique de compatibilité
- Windows 11, écran 1080p/1440p, DPI 100/125/150 %, souris/clavier.
- Support de fichiers PNG RGBA en premier ; tout autre format d’image est une extension après vérification.
- Export versionné, chemins relatifs, UTF-8 et noms de fichiers sûrs.
